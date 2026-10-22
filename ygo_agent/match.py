"""Matches between two seats: the one API that play, selfplay and teach run games through (and the trainer and the
bench after them).

    from ygo_agent.match import SeatSpec, run_games
    run = run_games(SeatSpec.parse("saffira:opus"), SeatSpec.parse("windbot:Blue-Eyes"), games=4, parallel=2)
    for g in run.games:
        print(g.winner, g.turns, g.reason, g.seats[0].stats["invalid_rate"], g.seats[0].log_dir, g.replay)

Seat specs (`SeatSpec.parse`):
  <deck>[:<backend>]   an AI seat. The deck is a deck folder's name (in decks/ or the user decks dir, see
                       ygo_agent/decks.py), a path to a .ydk (its playbook, if any, is <name>.md next to it) or a deck
                       in EDOPro's deck folder; the backend is a [backends.NAME] profile (default: agent.backend).
  heuristic, random    the no-LLM baselines on the config's deck; heuristic:<deck> names the deck.
  windbot:<deck AI>    one of EDOPro's WindBot deck AIs (`python -m ygo_agent.arena list-bots`).
  human                someone who joins from EDOPro.

Two AI seats with nobody watching play in-process, straight on the core (no sockets), `parallel` matches at a time,
each seat with its own backend sessions. A WindBot or human seat, or `spectate`, puts the games in an arena room that
speaks EDOPro's protocol (`parallel` rooms at a time on free ports when only WindBots join them). Either way every AI
seat logs to its usual games/<time>_<deck>-vs-<opponent>/ folder, both seats of a duel share one web-panel game, and
the run's folder (games/matches/<time>_<a>-vs-<b>/) gets results.json and an EDOPro replay of every game.
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field

from . import paths
from .agent.gamelog import BLUE, BOLD, DIM, GREEN, MAGENTA, RED, YELLOW, emit, paint, slug

POLICY_SHORTHANDS = ("heuristic", "random")
ROLES = ("A", "B")
TAG_COLORS = (BOLD + ";" + BLUE, BOLD + ";" + MAGENTA)
PROFILE_NAME = re.compile(r"[A-Za-z0-9_.+-]+")
RESULT_WORDS = {0: "win", 1: "loss"}


class MatchError(Exception):
    """A problem with the setup the user can fix: a bad seat spec, a missing deck or WindBot, a busy port..."""


# --- seat specs ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SeatSpec:
    kind: str                     # "agent", "windbot" or "human"
    deck: str | None = None       # agent: deck folder, .ydk path or EDOPro deck name (None: the config's); windbot: AI
    backend: str | None = None    # agent: backend profile name (None: the config's agent.backend)
    playbook: str | None = None   # agent with a loose .ydk: its playbook file (default: <name>.md next to it)
    mode: str | None = None       # agent: the prompt mode (default: "play" against a human, else "selfplay")
    name: str | None = None       # agent: its player name in the duel (default "<deck> (<backend>)")

    @classmethod
    def parse(cls, text: str) -> "SeatSpec":
        text = (text or "").strip()
        if not text:
            raise MatchError("empty seat spec")
        head, _, rest = text.partition(":")
        low = head.lower()
        if low == "human" and not rest:
            return cls("human")
        if low == "windbot":
            if not rest.strip():
                raise MatchError("a WindBot seat needs a deck AI name, e.g. windbot:Blue-Eyes")
            return cls("windbot", deck=rest.strip())
        if low in POLICY_SHORTHANDS:
            return cls("agent", deck=rest.strip() or None, backend=low)
        deck, sep, tail = text.rpartition(":")
        if sep and deck and PROFILE_NAME.fullmatch(tail) and not tail.lower().endswith(".ydk"):
            return cls("agent", deck=deck, backend=tail)
        return cls("agent", deck=text)

    @classmethod
    def coerce(cls, value: "SeatSpec | str") -> "SeatSpec":
        return value if isinstance(value, SeatSpec) else cls.parse(value)

    def with_(self, **changes) -> "SeatSpec":
        return dataclasses.replace(self, **changes)

    def __str__(self) -> str:
        if self.kind == "human":
            return "human"
        if self.kind == "windbot":
            return f"windbot:{self.deck}"
        return (self.deck or "(default deck)") + (f":{self.backend}" if self.backend else "")


SPEC_HELP = ("<deck>[:<backend>] (deck: a deck in decks/ or your decks dir, a .ydk path or an EDOPro deck name), "
             "heuristic[:<deck>], random[:<deck>], windbot:<deck AI> or human")


def load_profile(deck: str | None, db, cfg: dict, playbook: str | None = None):
    """A deck Profile: a deck folder in decks/ or the user decks dir (by name, any case: decks.find), a .ydk path, or
    a deck in EDOPro's deck folder."""
    from . import decks
    from .agent.profile import Profile
    key = deck or cfg["deck"]
    if decks.matches(key, cfg):
        try:
            return Profile(key, db, cfg)
        except FileNotFoundError as e:  # also decks.DeckError: the name is in both deck dirs
            raise MatchError(str(e)) from None
    edopro_decks = os.path.join(paths.resolve(cfg.get("edopro_dir", "~/Games/ProjectIgnis")), "deck")
    candidates = [key, key + ".ydk"]
    if os.path.isdir(edopro_decks) and os.sep not in key:
        wanted = {key.lower(), key.lower() + ".ydk"}
        candidates += [os.path.join(edopro_decks, f) for f in sorted(os.listdir(edopro_decks)) if f.lower() in wanted]
    for path in candidates:
        path = os.path.expanduser(path)
        if os.path.isfile(path) and path.lower().endswith(".ydk"):
            return Profile(slug(os.path.splitext(os.path.basename(path))[0]), db, cfg, ydk=path, playbook=playbook)
    raise MatchError(f"no deck {key!r}: not a deck in {decks.where(cfg)} ({', '.join(decks.keys(cfg)) or 'none'}), "
                     f"a .ydk file, or a deck in {edopro_decks}")


# --- results ------------------------------------------------------------------------------------------------------

@dataclass
class SeatResult:
    role: str                   # "A" (lobby position 0) or "B" (position 1)
    spec: str
    kind: str                   # agent / windbot / human
    name: str                   # the player name in the duel
    deck: str                   # deck name ("" for a human: unknown)
    backend: str | None = None  # agent seats: the backend label, e.g. "sonnet (claude-code)"
    result: str | None = None   # win / loss / draw, for this seat
    log_dir: str | None = None  # agent seats: the game's log folder (game.md, game.jsonl, meta.json, replay.yrpX)
    stats: dict | None = None   # agent seats: meta.json's "stats" (docs/backends.md)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class GameResult:
    match: int                  # 1, 2, ... (a Bo3 match has several games)
    game: int                   # the game's number within its match
    winner: int | None          # 0 = seat A, 1 = seat B, None = draw
    reason: str                 # e.g. "LP reached 0"
    turns: int
    seconds: float
    first: int                  # the seat that went first
    seed: int | None
    seats: list[SeatResult]
    replay: str | None = None   # the .yrpX (in the run's folder; each AI seat's log folder has a copy)
    retries: int = 0            # responses the engine refused
    lua_errors: int = 0
    best_of: int = 1

    @property
    def label(self) -> str:
        return str(self.match) if self.best_of == 1 else f"{self.match}.{self.game}"

    @property
    def winner_name(self) -> str | None:
        return None if self.winner is None else self.seats[self.winner].name

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["winner_role"] = None if self.winner is None else ROLES[self.winner]
        return d


@dataclass
class RunResult:
    specs: list[str]
    names: list[str]            # "A Saffira (sonnet)"-style descriptions of the two seats
    games: list[GameResult] = field(default_factory=list)
    out: str | None = None      # the run's folder
    web_url: str | None = None
    interrupted: bool = False
    path: str = ""              # "in-process" or "arena"

    def wins(self) -> tuple[int, int, int]:
        a = sum(1 for g in self.games if g.winner == 0)
        b = sum(1 for g in self.games if g.winner == 1)
        return a, b, len(self.games) - a - b

    def seat_totals(self, index: int) -> dict | None:
        """One AI seat's stats over every game (sums; latency means weighted by asks; the worst p95)."""
        stats = [g.seats[index].stats for g in self.games if g.seats[index].stats]
        if not stats:
            return None
        total = {"games": len(stats), "decisions": sum(s["decisions"] for s in stats),
                 "by_source": {k: sum(s["by_source"].get(k, 0) for s in stats) for k in stats[0]["by_source"]},
                 "asks": sum(s["asks"] for s in stats), "replies": sum(s["replies"] for s in stats),
                 "invalid_replies": sum(s["invalid_replies"] for s in stats), "errors": sum(s["errors"] for s in stats),
                 "tokens": {k: sum(s["tokens"].get(k, 0) for s in stats) for k in stats[0]["tokens"]},
                 "sessions": sum(s["sessions"] for s in stats), "rollovers": sum(s["rollovers"] for s in stats)}
        costs = [s["cost_usd"] for s in stats if s.get("cost_usd") is not None]
        total["cost_usd"] = round(sum(costs), 4) if costs else None
        timed = [(s["latency_mean_s"], s["asks"]) for s in stats if s.get("latency_mean_s") is not None]
        weight = sum(n for _, n in timed)
        total["latency_mean_s"] = round(sum(m * n for m, n in timed) / weight, 2) if weight else None
        p95 = [s["latency_p95_s"] for s in stats if s.get("latency_p95_s") is not None]
        total["latency_p95_max_s"] = max(p95) if p95 else None
        total["invalid_rate"] = round(total["invalid_replies"] / total["replies"], 4) if total["replies"] else None
        n = total["decisions"]
        total["fallback_rate"] = round(total["by_source"].get("fallback", 0) / n, 4) if n else None
        return total

    def to_dict(self) -> dict:
        a, b, draws = self.wins()
        return {"specs": self.specs, "names": self.names, "path": self.path, "out": self.out,
                "interrupted": self.interrupted, "wins": {"A": a, "B": b, "draws": draws},
                "seats": [self.seat_totals(0), self.seat_totals(1)], "games": [g.to_dict() for g in self.games]}

    def summary_lines(self) -> list[str]:
        """The end-of-run report the CLI prints: wins, game lengths, and each AI seat's stats."""
        if not self.games:
            return [paint(YELLOW, "No game was finished.")]
        a, b, draws = self.wins()
        lines = [paint(BOLD, f"\nResults ({len(self.games)} game{'s' if len(self.games) != 1 else ''}): "
                             f"{self.names[0]}  {a} - {b}  {self.names[1]}" + (f"  ({draws} draws)" if draws else ""))]
        lines.append(paint(DIM, f"  {'game':>5}  {'winner':<24} {'reason':<16} {'turns':>5} {'time':>8}  first"))
        for g in self.games:
            who = "draw" if g.winner is None else f"{ROLES[g.winner]} {g.seats[g.winner].name}"
            lines.append(f"  {g.label:>5}  {who[:24]:<24} {g.reason[:16]:<16} {g.turns:>5} "
                         f"{duration(g.seconds):>8}  {ROLES[g.first]}")
        turns = [g.turns for g in self.games]
        secs = [g.seconds for g in self.games]
        lines.append(f"  Game length: {sum(turns) / len(turns):.1f} turns on average ({min(turns)}-{max(turns)}), "
                     f"{duration(sum(secs) / len(secs))} per game.")
        for i in (0, 1):
            t = self.seat_totals(i)
            if not t:
                continue
            src = t["by_source"]
            bits = [f"{t['decisions']} decisions in {t['games']} game(s) (backend {src.get('backend', 0)}, rules "
                    f"{src.get('rule', 0)}, auto {src.get('auto', 0)}, fallback {src.get('fallback', 0)})"]
            if t["latency_mean_s"] is not None:
                bits.append(f"latency mean {t['latency_mean_s']}s / worst p95 {t['latency_p95_max_s']}s")
            bits.append(f"invalid replies {t['invalid_replies']}/{t['replies']}"
                        + (f" ({t['invalid_rate']:.1%})" if t["invalid_rate"] is not None else ""))
            bits.append(f"fallback rate {t['fallback_rate']:.1%}" if t["fallback_rate"] is not None else "")
            if any(t["tokens"].values()):
                tok = t["tokens"]
                bits.append(f"tokens in {tok['input']} (+{tok['cache_read']} cached) / out {tok['output']}")
            if t["cost_usd"] is not None:
                bits.append(f"cost ${t['cost_usd']:.4f}")
            lines.append(f"  {self.names[i]}: " + "; ".join(b for b in bits if b) + ".")
        if self.out:
            lines.append(paint(YELLOW, f"  Run folder: {self.out} (results.json, game-*.yrpX replays). Each AI seat's "
                                       "game log (game.md) is in the folder its results list as log_dir."))
        return lines


def duration(seconds: float) -> str:
    seconds = float(seconds or 0)
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}m{s:02d}s" if m < 60 else f"{m // 60}h{m % 60:02d}m"


def join_instructions(port: int, spectator: bool) -> list[str]:
    who = "as a spectator (both duelist seats are taken)" if spectator else "and take the free duelist seat"
    return [f"In EDOPro: LAN Mode → type Host address 127.0.0.1 and port {port} → Join, {who}.",
            "  (Type the address: EDOPro's LAN room list may not show the room, and its Refresh button can crash "
            "EDOPro.)"]


# --- the stdin "press Enter" helper for spectator waits -------------------------------------------------------------

class _Enter:
    """One daemon thread reading stdin lines, so a wait can end on Enter without leaving a reader behind."""
    _instance = None

    def __init__(self):
        self.pressed = threading.Event()
        threading.Thread(target=self._read, daemon=True, name="stdin-enter").start()

    def _read(self):
        while True:
            try:
                line = sys.stdin.readline()
            except (OSError, ValueError):
                return
            if not line:
                return
            self.pressed.set()

    @classmethod
    def wait(cls, prompt: str) -> None:
        """input(prompt), unless the reader thread already owns stdin (a spectator wait started it)."""
        if cls._instance is None:
            input(prompt)
            return
        cls._instance.pressed.clear()
        print(prompt, end="", flush=True)
        cls._instance.pressed.wait()

    @classmethod
    def get(cls) -> "_Enter | None":
        try:
            interactive = sys.stdin is not None and sys.stdin.isatty()
        except (AttributeError, ValueError):
            interactive = False
        if not interactive:
            return None
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def wait_for_enter(prompt: str) -> None:
    """Wait for Enter (works after a spectator wait, whose reader thread keeps stdin)."""
    _Enter.wait(prompt)


# --- the run ------------------------------------------------------------------------------------------------------

@dataclass
class _Seat:
    """A seat spec resolved against the config, the card data and the installed WindBots."""
    role: str
    index: int
    spec: SeatSpec
    name: str = ""
    deck_name: str = ""
    profile: object = None
    backend: dict | None = None
    label: str | None = None
    bot: object = None
    mode: str | None = None
    echo: str = "all"
    tag: str | None = None

    @property
    def kind(self) -> str:
        return self.spec.kind

    def opponent_info(self) -> dict:
        """How the other seat's prompt describes this one (prompts.opponent_text)."""
        if self.kind == "agent":
            return {"kind": "agent", "deck": self.deck_name, "backend": self.backend.get("type")}
        if self.kind == "windbot":
            return {"kind": "windbot", "deck": self.bot.name}
        return {"kind": "human"}

    def describe(self) -> str:
        if self.kind == "agent":
            return f"{self.role} {self.deck_name} ({self.backend['name']})"
        if self.kind == "windbot":
            return f"{self.role} WindBot {self.bot.name}"
        return f"{self.role} human"


class _Run:
    def __init__(self, a, b, *, games, rules, seed, best_of, pace, parallel, spectate, web, web_port, out, stack,
                 cfg, db, engine, quiet, echo, tags, port, bind, lan, password, time_limit, timeout, first,
                 start_state, on_game, on_room, room_name):
        from .config import load_config
        self.cfg = cfg if cfg is not None else load_config()
        self.specs = (SeatSpec.coerce(a), SeatSpec.coerce(b))
        self.games = games
        self.rules = rules
        self.seed = seed
        self.best_of = best_of
        self.pace = float(pace or 0)
        self.parallel = max(1, int(parallel or 1))
        self.spectate = spectate
        self.web, self.web_port = web, web_port
        self.stack_spec = stack or {}
        self.quiet = quiet
        self.echo, self.tags = echo, tags
        self.port, self.bind, self.lan, self.password = port, bind, lan, password
        self.time_limit, self.timeout = time_limit, timeout
        self.first, self.start_state = first, start_state
        self.on_game, self.on_room = on_game, on_room
        self.room_name = room_name
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._loops: list[tuple[asyncio.AbstractEventLoop, object]] = []  # (loop, room) of each running room
        self._db, self._engine = db, engine
        self.windbot = None
        self._live = set()
        self.network = spectate or any(s.kind in ("windbot", "human") for s in self.specs)
        if best_of not in (1, 3, 5):
            raise MatchError("best_of must be 1, 3 or 5")
        if games is not None and games < 1:
            raise MatchError("games must be at least 1")
        if first not in (None, 0, 1):
            raise MatchError("first must be 0 (seat A), 1 (seat B) or None (RPS)")
        if games is None and not self.network:
            raise MatchError("an open-ended run (games=None) needs a room: a human or WindBot seat, or spectate")
        if self.network and self.parallel > 1 and (spectate or any(s.kind == "human" for s in self.specs)):
            raise MatchError("parallel games can't have a human or a spectator: run them one at a time")
        self.result = RunResult(specs=[str(s) for s in self.specs], names=[], path="arena" if self.network
                                else "in-process")
        self.out_base = out

    # ---- setup ----

    @property
    def db(self):
        if self._db is None:
            from .agent.carddb import CardDB
            self._db = CardDB(self.cfg["edopro_dir"])
            if not self._db.cards:
                raise MatchError(f"no EDOPro card databases found in {self._db.root} (set edopro_dir)")
        return self._db

    @property
    def engine(self):
        if self._engine is None:
            from .core import Engine, InstallError
            try:
                self._engine = Engine.load(paths.resolve(self.cfg["edopro_dir"]))
            except (InstallError, OSError) as e:
                raise MatchError(f"can't load EDOPro's core: {e}") from None
        return self._engine

    def duel_config(self):
        from .arena.duel import DuelConfig
        from .core.constants import rule_set
        try:
            rule_set(str(self.rules))
        except ValueError as e:
            raise MatchError(str(e)) from None
        return DuelConfig(rules=str(self.rules).lower(), best_of=self.best_of)

    def resolve(self) -> list[_Seat]:
        from .config import ConfigError, backend as backend_profile
        from . import backends
        seats = []
        for index, spec in enumerate(self.specs):
            s = _Seat(ROLES[index], index, spec)
            if spec.kind == "agent":
                s.profile = load_profile(spec.deck, self.db, self.cfg, spec.playbook)
                try:
                    s.backend = backend_profile(self.cfg, spec.backend)
                except ConfigError as e:
                    raise MatchError(f"seat {s.role}: {e}") from None
                try:
                    backends.check(s.backend)
                except backends.BackendError as e:
                    raise MatchError(f"seat {s.role}: {e}") from None
                s.label = backends.label(s.backend)
                s.deck_name = s.profile.name
                s.name = (spec.name or f"{s.profile.name} ({s.backend['name']})")[:19]
            elif spec.kind == "windbot":
                from .arena.windbot import WindBotError, WindBotInstall, mono_path
                if mono_path() is None:
                    raise MatchError("WindBot seats need mono (the WindBot deck AIs are a .NET program)")
                try:
                    self.windbot = self.windbot or WindBotInstall.find(self.engine.install.root)
                    s.bot = self.windbot.resolve(spec.deck)
                except WindBotError as e:
                    raise MatchError(str(e)) from None
                s.deck_name = s.bot.name
                s.name = f"{s.bot.name} AI"[:19]
            elif spec.kind == "human":
                s.name = "human"
            else:
                raise MatchError(f"unknown seat kind {spec.kind!r}")
            seats.append(s)
        a, b = seats
        if a.name == b.name:
            a.name, b.name = a.name[:17] + " A", b.name[:17] + " B"
        for s, other in ((a, b), (b, a)):
            if s.kind == "agent":
                s.mode = s.spec.mode or ("play" if other.kind == "human" else "selfplay")
        self.terminal(seats)
        self.result.names = [s.describe() for s in seats]
        return seats

    def terminal(self, seats):
        """Who prints what: one AI seat prints everything, as `play` always has; with two, the second prints only its
        decisions (the first prints the events), and each line is tagged with the seat; quiet: key plays only."""
        agents = [s for s in seats if s.kind == "agent"]
        echo = self.echo
        if echo is None:
            if self.quiet:
                echo = "key"
            elif len(agents) == 2:
                teach = [s for s in agents if s.mode == "teach"]
                echo = tuple("all" if s.mode == "teach" else "off" for s in seats) if len(teach) == 1 else \
                    ("all", "decisions")
            else:
                echo = "all"
        if isinstance(echo, str):
            echo = (echo, echo)
        tags = self.tags if self.tags is not None else (len(agents) == 2 or self.parallel > 1)
        for s in seats:
            s.echo = echo[s.index]
            if tags and s.kind == "agent":
                s.tag = f"{s.role} {s.deck_name}·{s.backend['name']}"

    def prepare(self):
        self.seats = self.resolve()
        engine = self.engine
        self.config = self.duel_config()
        from .arena.deck import DeckRules, check_deck, load_ydk
        rules = DeckRules(forbidden_types=self.config.forbidden_types)
        self.decks = {}
        for s in self.seats:
            if s.kind != "agent":
                continue
            loaded = load_ydk(s.profile.ydk, engine.cards)
            err = check_deck(loaded.deck, engine.cards, rules, loaded.unknown)
            if err:
                raise MatchError(f"seat {s.role}: {s.profile.ydk} is not legal under {self.rules}: {err}")
            self.decks[s.index] = loaded.deck
        self.stack = {}
        for seat, cards in (self.stack_spec or {}).items():
            index = ROLES.index(seat.upper()) if isinstance(seat, str) else int(seat)
            try:
                self.stack[index] = [c if isinstance(c, int) else engine.cards.resolve(str(c).strip()) for c in cards]
            except KeyError as e:
                raise MatchError(f"stack: {e.args[0]}") from None
        from .arena.gamelog import game_dir
        base = self.out_base
        label = "-vs-".join(slug(str(s), 28) for s in self.specs)
        if base is None:
            base = os.path.join(paths.resolve(self.cfg.get("games_dir", "games")), "matches")
            self.out = game_dir(base, label)
            _link_latest(base, os.path.basename(self.out))
        else:
            os.makedirs(base, exist_ok=True)
            self.out = os.path.abspath(base)  # results.json and log_dir hold absolute paths either way
        self.result.out = self.out
        self.name = os.path.basename(self.out)
        # The web panel's game ids start with this. A folder the caller chose (the trainer's runs/r1-g1, a bench's)
        # isn't unique on its own, and an app that relays several runs would merge their games.
        self.tag = self.name if base is None else f"{self.name}-{hashlib.sha1(self.out.encode()).hexdigest()[:6]}"
        if self.web:
            self.result.web_url = ensure_panel(self.cfg, self.db, self.web_port).url

    # ---- seats ----

    def agent_seat(self, s: _Seat, game_tag: str | None = None):
        from .arena.native_seat import AgentSeat
        other = self.seats[1 - s.index]
        tag = None
        if s.tag:
            tag = paint(TAG_COLORS[s.index], f"[{game_tag + ' ' if game_tag else ''}{s.tag}]")
        log_options = {"tag": tag, "echo": s.echo, "latest": s.index == 0 or other.kind != "agent"}
        return AgentSeat(s.name, self.cfg, self.db, s.profile, s.backend, cards=self.engine.cards, pace=self.pace,
                         position=s.index, mode=s.mode, opponent=other.opponent_info(), log_options=log_options)

    # ---- results ----

    def say(self, *lines):
        emit(lines)

    def seat_results(self, names, winner) -> list[SeatResult]:
        out = []
        for s in self.seats:
            result = "draw" if winner is None else ("win" if winner == s.index else "loss")
            out.append(SeatResult(s.role, str(s.spec), s.kind, names[s.index] or s.name, s.deck_name, s.label, result))
        return out

    def attach(self, seat_result: SeatResult, game: GameResult):
        """Runs on an AI seat's brain thread once its game is over: its log folder and stats, plus the replay."""
        def fill(info):
            seat_result.log_dir = info["dir"]
            seat_result.stats = info["stats"]
            seat_result.result = info["result"] or seat_result.result
            log = info.get("log")
            if log is None:
                return
            meta = {"run": self.out, "match": game.match, "game": game.game, "seat": seat_result.role}
            if game.replay:
                try:
                    shutil.copyfile(game.replay, os.path.join(info["dir"], "replay.yrpX"))
                    meta["replay"] = "replay.yrpX"
                except OSError:
                    pass
            log.write_meta(match=meta)
        return fill

    def write_replay(self, data: bytes | None, match: int, game: int) -> str | None:
        if not data:
            return None
        name = f"game-{match:03d}.yrpX" if self.best_of == 1 else f"game-{match:03d}-{game}.yrpX"
        path = os.path.join(self.out, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def add_game(self, game: GameResult):
        with self._lock:
            self.result.games.append(game)
            self.result.games.sort(key=lambda g: (g.match, g.game))
            self.save()
        who = "draw" if game.winner is None else f"{ROLES[game.winner]} {game.seats[game.winner].name} wins"
        color = GREEN if game.winner is not None else YELLOW
        problems = (f", {game.retries} engine retries" if game.retries else "") + (
            f", {game.lua_errors} Lua errors" if game.lua_errors else "")
        self.say(paint(BOLD + ";" + color, f"game {game.label}: {who}") + f" — {game.reason}, {game.turns} turns, "
                 f"{duration(game.seconds)} ({ROLES[game.first]} went first{problems})")
        if self.on_game:
            try:
                self.on_game(game)
            except Exception as e:  # a caller's hook must not stop the run
                self.say(paint(RED, f"on_game hook failed: {e!r}"))

    def save(self):
        if not getattr(self, "out", None):
            return
        tmp = os.path.join(self.out, "results.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.result.to_dict(), f, indent=2)
            f.write("\n")
        os.replace(tmp, os.path.join(self.out, "results.json"))

    # ---- in-process ----

    def run_inprocess(self):
        matches = list(range(1, self.games + 1))
        jobs = iter(matches)
        errors = []

        def worker():
            while not self._stop.is_set():
                with self._lock:
                    n = next(jobs, None)
                if n is None:
                    return
                try:
                    self.play_inprocess(n)
                except Exception as e:  # one broken match mustn't take the others down
                    if self._stop.is_set():
                        return  # Ctrl+C closed its seats under it
                    import traceback
                    errors.append((n, e))
                    self.say(paint(RED, f"match {n} failed:\n{traceback.format_exc()}"))
        threads = [threading.Thread(target=worker, daemon=True, name=f"match-{i + 1}")
                   for i in range(min(self.parallel, len(matches)))]
        for t in threads:
            t.start()
        try:
            for t in threads:
                while t.is_alive():
                    t.join(0.2)
        except KeyboardInterrupt:
            self._stop.set()
            self.result.interrupted = True
            for seat in list(self._live):
                seat.close(timeout=2)
        if errors and not self.result.games:
            raise errors[0][1]

    def play_inprocess(self, n: int):
        from .arena.gamelog import GameLog as ArenaLog
        from .arena.native_seat import link
        from .arena.runner import run_match
        game_tag = f"g{n}" if self.parallel > 1 else None
        agents = [self.agent_seat(s, game_tag) for s in self.seats]
        with self._lock:
            self._live |= set(agents)
        link(*agents, match_id=f"{self.tag}-m{n}")
        decks = (self.decks[0], self.decks[1])
        seed = None if self.seed is None else self.seed + n - 1
        arena_log = ArenaLog(os.path.join(self.out, f"match-{n:03d}.log"), self.engine.cards)

        def on_game(rec, duel):
            r = rec.result
            game = GameResult(n, rec.index + 1, rec.winner_seat, self.reason(r.reason), r.turns, round(rec.seconds, 2),
                              rec.first, rec.seed, self.seat_results([a.name for a in agents], rec.winner_seat),
                              retries=r.retries, lua_errors=len(r.lua_errors), best_of=self.best_of)
            game.replay = self.write_replay(rec.replay, n, rec.index + 1)
            for seat, sr in zip(agents, game.seats):
                pending = seat.collect(self.attach(sr, game))
                if hasattr(pending, "result"):
                    pending.result(timeout=300)
            self.add_game(game)
        try:
            run_match(self.engine, self.config, decks, tuple(agents), best_of=self.best_of, seed=seed, first=self.first,
                      stack=self.stack or None, start_state=self.start_state, observers=[arena_log], on_game=on_game)
        finally:
            arena_log.close()
            for seat in agents:
                seat.close()
            with self._lock:
                self._live -= set(agents)

    def reason(self, code) -> str:
        from .core.constants import WIN_REASON_NAMES
        return WIN_REASON_NAMES.get(code) or self.db.victory.get(code) or f"reason {code:#x}"

    # ---- arena rooms ----

    def run_network(self):
        human = any(s.kind == "human" for s in self.seats)
        rooms = 1 if self.games is None else min(self.parallel, self.games)
        if rooms == 1:
            numbers = None if self.games is None else list(range(1, self.games + 1))
            try:
                asyncio.run(self.room(0, numbers, human))
            except KeyboardInterrupt:
                self.result.interrupted = True
            return
        shares = [list(range(i + 1, self.games + 1, rooms)) for i in range(rooms)]
        errors = []

        def run_room(i):
            try:
                asyncio.run(self.room(i, shares[i], human))
            except Exception as e:
                errors.append(e)
                self.say(paint(RED, f"room {i + 1} failed: {e!r}"))
        threads = [threading.Thread(target=run_room, args=(i,), daemon=True, name=f"room-{i + 1}")
                   for i in range(rooms)]
        for t in threads:
            t.start()
        try:
            for t in threads:
                while t.is_alive():
                    t.join(0.2)
        except KeyboardInterrupt:
            self.result.interrupted = True
            self._stop.set()
            for loop, room in list(self._loops):
                loop.call_soon_threadsafe(room.finished.set)
            for t in threads:
                t.join(10)
        for e in errors:
            if isinstance(e, MatchError) and not self.result.games:
                raise e

    async def room(self, room_no: int, numbers: list[int] | None, human: bool):
        from .arena.native_seat import add_to_room, link
        from .arena.server import ArenaServer, Room, RoomConfig, RoomObserver
        from .arena.windbot import WindBotProcess, watch_bots
        watched = human or self.spectate
        reserved, bots = {}, []
        for s in self.seats:
            if s.kind == "windbot":
                reserved[s.index] = s.name
                bots.append(s)
        rc = RoomConfig(name=self.room_name, password=self.password, duel=self.config, best_of=self.best_of,
                        time_limit=self.time_limit if human else 0, rematch=True,
                        max_matches=None if numbers is None else len(numbers),
                        seed=None if self.seed is None else self.seed + room_no, stack=dict(self.stack),
                        first=self.first, reserved=reserved, lan_discovery=bool(self.lan and watched))
        room = Room(self.engine, rc)
        self._loops.append((asyncio.get_running_loop(), room))
        game_tag = f"r{room_no + 1}" if self.parallel > 1 else None
        agents = {}
        try:
            for s in self.seats:
                if s.kind == "agent":
                    seat = self.agent_seat(s, game_tag)
                    agents[s.index] = seat
                    add_to_room(room, s.index, seat, self.decks[s.index])
        except ValueError as e:
            for seat in agents.values():
                seat.close()
            raise MatchError(str(e)) from None
        if agents:
            link(*agents.values(), match_id=self.tag + (f"-r{room_no + 1}" if self.parallel > 1 else ""))
        if self.spectate:
            room.gate = self.spectator_gate
        if self.on_room:
            self.on_room(room)
        run, started, failed = self, [time.monotonic()], []

        class Recorder(RoomObserver):
            def on_join(self, p):
                if p.pos is not None and p.pos >= 2:
                    run.say(paint(BOLD + ";" + GREEN, f"{p.name or 'Someone'} joined as a spectator."))
                elif human and p.name not in reserved.values():
                    run.say(paint(BOLD + ";" + GREEN, f"{p.name} joined the duelist seat {p.pos}."))

            def on_leave(self, p):
                if p.name and p.name not in reserved.values():
                    run.say(paint(DIM, f"{p.name} left the room."))

            def on_game_start(self, room, duel):
                started[0] = time.monotonic()

            def on_game_end(self, room, duel, result):
                run.room_game_end(room, duel, result, agents, numbers, started[0])

            def on_deck_rejected(self, p, error):
                run.say(paint(RED, f"{p.name}'s deck was rejected: {error}"))
                if p.name in reserved.values():
                    failed.append(f"{p.name}'s deck is not legal under these rules ({error})")
                    room.finished.set()
        room.room_observers.append(Recorder())
        if not os.environ.get("YGO_AGENT_NO_ARENA_LOG"):
            from .arena.gamelog import GameLog as ArenaLog
            prefix = f"room{room_no + 1}-" if self.parallel > 1 else ""
            room.duel_observer_factory = lambda room, index: [ArenaLog(
                os.path.join(self.out, f"{prefix}game-{index + 1:03d}.log"), self.engine.cards)]
        bind = self.bind if self.bind is not None else (None if watched else "127.0.0.1")
        port = (self.port if self.port is not None else 7911) if watched else 0
        server = ArenaServer(room, bind, port)
        try:
            await server.start()
        except OSError as e:
            for seat in agents.values():
                seat.close()
            raise MatchError(f"can't host the room on port {port}: {e.strerror or e}. Is EDOPro (or another "
                             "ygo-agent) hosting on it? Pick another port with --port.") from None
        room.listen_port = server.port
        if human:
            self.say(paint(BOLD + ";" + YELLOW, f"\nThe room is open on port {server.port}."),
                     *[paint(YELLOW, line) for line in join_instructions(server.port, spectator=False)],
                     paint(DIM, "Waiting for you to join. Ctrl+C closes the room."))
        procs: list[WindBotProcess] = []

        def launch(s) -> WindBotProcess:
            p = WindBotProcess(self.windbot, s.bot, s.name, server.port, version=room.version.as_int,
                               cdb_paths=self.engine.install.cdb_paths,
                               scratch=os.path.join(self.out, f"windbot-{s.role}" + (
                                   f"-r{room_no + 1}" if self.parallel > 1 else "") + f"-{room.matches_played + 1}"))
            p.start()
            return p

        watcher = None
        try:
            procs += [launch(s) for s in bots]
            if bots:
                watcher = asyncio.get_running_loop().create_task(watch_bots(
                    room, [(s.index, s.name) for s in bots], procs, lambda i: launch(bots[i]), failed))
            await server.serve(timeout=self.timeout)
        except asyncio.TimeoutError:
            self.say(paint(RED, f"Timed out after {self.timeout}s (room stage: {room.stage.value})."))
        except asyncio.CancelledError:
            self._stop.set()  # Ctrl+C: don't wait for a decision in progress
            raise
        finally:
            if watcher:
                watcher.cancel()
            for p in procs:
                p.stop()
            interrupted = self.result.interrupted or self._stop.is_set()
            for seat in agents.values():
                await asyncio.get_running_loop().run_in_executor(None, lambda seat=seat: seat.close(
                    timeout=2 if interrupted else 60))
        if failed:
            raise MatchError("; ".join(failed))

    def room_game_end(self, room, duel, result, agents, numbers, started):
        index = room.matches_played  # this game's match hasn't been counted yet
        match = numbers[index] if numbers and index < len(numbers) else index + 1
        game_no = len(room.match_results) + 1
        positions = room.team_positions
        winner = None if result.is_draw else positions[result.winner]
        names = [room.slots[i].name if room.slots[i] else "" for i in (0, 1)]
        game = GameResult(match, game_no, winner, self.reason(result.reason), result.turns,
                          round(time.monotonic() - started, 2), positions[0], duel.seed,
                          self.seat_results(names, winner), retries=result.retries,
                          lua_errors=len(result.lua_errors), best_of=self.best_of)
        game.replay = self.write_replay(duel.replay.yrpx() if duel.replay else None, match, game_no)
        for index, seat in agents.items():
            seat.collect(self.attach(game.seats[index], game))  # after the seat has seen the whole game
        self.add_game(game)

    async def spectator_gate(self, room):
        """Hold the match until someone watches: a spectator joins, or Enter is pressed (in a web-app job: the app's
        "Start without a spectator" button)."""
        from .web import relay
        if room.observers:
            return
        enter = _Enter.get()
        if enter:
            enter.pressed.clear()
        n = len(self.result.games) + 1
        lines = [paint(BOLD + ";" + YELLOW, f"\nWaiting for a spectator before game {n}.")]
        lines += [paint(YELLOW, line) for line in join_instructions(room.listen_port, spectator=True)]
        if enter:
            lines.append(paint(DIM, "Or press Enter to start without one."))
        if relay.active():
            lines.append(paint(DIM, "Or press \"Start without a spectator\" in the web app."))
            relay.waiting(f"Waiting for a spectator before game {n}", "Start without a spectator")
        if self.result.web_url:
            lines.append(paint(DIM, f"The web panel shows the game too: {self.result.web_url}"))
        self.say(*lines)
        try:
            while not room.observers and not (enter and enter.pressed.is_set()) and not self._stop.is_set() \
                    and not relay.go_requested():
                await asyncio.sleep(0.2)
        finally:
            relay.waiting(None)
        if room.observers:
            await asyncio.sleep(1.0)  # let the spectator's client settle into the room first

    # ---- entry ----

    def run(self) -> RunResult:
        self.prepare()
        try:
            if self.network:
                self.run_network()
            else:
                self.run_inprocess()
        finally:
            self.save()
        return self.result


def _link_latest(base, name):
    link = os.path.join(base, "latest")
    try:
        if os.path.islink(link):
            os.remove(link)
        os.symlink(name, link)
    except OSError:
        pass


_PANEL = None


def ensure_panel(cfg, db, port=None):
    """The web panel of this process (started on first use). Live games publish to it. In a job of the web app the
    app is the panel: the bus already relays to it (web/relay.py), so no server starts."""
    global _PANEL
    from .web import relay
    if _PANEL is None and relay.active():
        relay.share_db(db)
        _PANEL = relay.Stub(relay.url())
    if _PANEL is None:
        from .web import server
        try:
            _PANEL = server.start(cfg, db, port=port)
        except OSError as e:
            raise MatchError(str(e)) from None
    return _PANEL


def run_games(seat_a: SeatSpec | str, seat_b: SeatSpec | str, games: int | None = 1, *, rules: str = "mr3",
              seed: int | None = None, best_of: int = 1, pace: float = 0.0, parallel: int = 1, spectate: bool = False,
              web: bool = False, web_port: int | None = None, out: str | None = None,
              stack: dict | None = None, cfg: dict | None = None, db=None, engine=None, quiet: bool = False,
              echo=None, tags: bool | None = None, port: int | None = None, bind: str | None = None,
              lan: bool = True, password: str = "", time_limit: int = 600, timeout: float | None = None,
              first: int | None = None, start_state=None, on_game=None, on_room=None,
              room_name: str = "ygo-agent") -> RunResult:
    """Play `games` matches (each `best_of` 1, 3 or 5) between seat A (lobby position 0) and seat B (position 1).

    Seats are SeatSpecs or spec strings (see the module docstring). Returns a RunResult: `games` holds one GameResult
    per game (winner, reason, turns, seconds, the replay, and per seat its log folder and meta.json stats), `out` the
    run's folder. Raises MatchError for setup problems; Ctrl+C ends the run early with `interrupted` set.

    rules: mr1-mr5, goat, speed, rush. seed: reproducible games (match n uses seed + n - 1). pace: minimum seconds per
    AI decision, for watchers. parallel: matches at a time (in-process, or one room each when only WindBots join).
    spectate: host a room and wait for a spectator (or Enter) before each match. web: serve the panel in this
    process (`web_port`; the URL is in `web_url`). out: the run's folder (default games/matches/<time>_<a>-vs-<b>).
    stack: {seat: [card codes or names]} put on top of that seat's Deck (the first 5 are its opening hand).
    quiet: only key plays and results in the terminal (`echo` sets it per seat: all/decisions/key/off; `tags`
    prefixes each AI seat's lines). games=None: open-ended (a room with a human: until Ctrl+C).
    port/bind/lan/password/time_limit/room_name: the room, when there is one (port None: a free port, unless a
    human or spectator must find it: then pass it). first: the seat (0 = A, 1 = B) that goes first in game 1 of every
    match, in-process and in rooms alike; None: the RPS winner chooses. Later games of a Bo3: the loser chooses.
    on_game(GameResult) runs after each game; on_room(Room) when a room is created (coach mode hooks in there)."""
    run = _Run(seat_a, seat_b, games=games, rules=rules, seed=seed, best_of=best_of, pace=pace, parallel=parallel,
               spectate=spectate, web=web, web_port=web_port, out=out, stack=stack, cfg=cfg, db=db, engine=engine,
               quiet=quiet, echo=echo, tags=tags, port=port, bind=bind, lan=lan, password=password,
               time_limit=time_limit, timeout=timeout, first=first, start_state=start_state, on_game=on_game,
               on_room=on_room, room_name=room_name)
    return run.run()
