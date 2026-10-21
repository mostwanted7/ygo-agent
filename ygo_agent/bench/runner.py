"""Running a benchmark: every planned game through match.run_games(), K at a time, each result appended to
results.jsonl the moment it ends, so a crash, Ctrl+C or a usage limit loses only the games in flight.

A run folder (bench/results/<time>_<name>/) holds:
  spec.json       the plan (the latest invocation's settings, every invocation's command line)
  env.json        versions: core, scripts, card data, WindBot, decks, backends (with the model ids a probe saw)
  results.jsonl   one line per game (status done / aborted / error); the last "done" line of a game counts
  replays/        every game's EDOPro replay
  summary.json, report.md, chart.svg (report.py)
Game logs (game.md, prompts.jsonl, ...) go to <games_dir>/bench/<run folder>/<game>/ (games/ is git-ignored).
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from .. import paths
from ..agent.gamelog import BOLD, DIM, GREEN, RED, YELLOW, paint
from ..match import MatchError, SeatSpec, duration, run_games
from .spec import BenchSpec, Job, opponent_label

RESULTS = "results.jsonl"
RESULTS_ROOT = os.path.join(paths.ROOT, "bench", "results")
LLM_TYPES = ("claude-code", "anthropic", "openai")
# Errors that mean "you're out of model usage": the game fell back to the heuristic, so it isn't this backend's.
LIMIT = re.compile(r"usage limit|rate[ _-]?limit|hit your (usage |session |weekly )?limit|limit (reached|exceeded)"
                   r"|quota|credit balance|out of (extra )?usage|too many requests|\b429\b", re.I)
MAX_ERRORS_IN_A_ROW = 4


def rel(path: str | None) -> str | None:
    """Repo-relative when inside the repo (results stay valid if the checkout moves), else ~-abbreviated."""
    if not path:
        return None
    path = os.path.abspath(path)
    if path.startswith(paths.ROOT + os.sep):
        return os.path.relpath(path, paths.ROOT)
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --- results.jsonl ---------------------------------------------------------------------------------------------

def read_results(folder: str) -> list[dict]:
    """Every readable line (a half-written last line from a crash is skipped)."""
    path = os.path.join(folder, RESULTS)
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def finished(records: list[dict]) -> dict[str, dict]:
    """The counted record of each game: its last "done" line."""
    out = {}
    for r in records:
        if r.get("status") == "done":
            out[r["key"]] = r
    return out


def pending(jobs: list[Job], records: list[dict]) -> list[Job]:
    done = finished(records)
    return [j for j in jobs if j.key not in done]


class ResultsFile:
    def __init__(self, folder: str):
        self.path = os.path.join(folder, RESULTS)
        self.lock = threading.Lock()

    def append(self, record: dict) -> None:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self.lock, open(self.path, "a+b") as f:
            if f.tell() > 0:
                f.seek(f.tell() - 1)
                if f.read(1) != b"\n":  # a line a crash cut short: start on a fresh line
                    line = "\n" + line
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())


# --- one game -----------------------------------------------------------------------------------------------

def scan_prompts(path: str) -> dict:
    """Per-decision backend latency (a decision's asks summed, as agent/stats.py counts it), timeouts and
    usage-limit errors, from a seat's prompts.jsonl."""
    seconds, timeouts, limits, samples, limit_sample = {}, 0, 0, [], None
    try:
        f = open(path, encoding="utf-8")
    except OSError:
        return {"latencies": [], "timeouts": 0, "limit_errors": 0, "error_samples": []}
    with f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            info = rec.get("info") or {}
            if rec.get("id") is not None:
                seconds[rec["id"]] = seconds.get(rec["id"], 0.0) + float(info.get("seconds") or 0)
            err = info.get("error")
            if err:
                err = str(err)
                timeouts += err.startswith("timed out")
                if LIMIT.search(err):
                    limits += 1
                    limit_sample = limit_sample or err[:200]
                if len(samples) < 3 and err[:200] not in samples:
                    samples.append(err[:200])
    return {"latencies": [round(s, 2) for s in seconds.values()], "timeouts": timeouts, "limit_errors": limits,
            "limit_sample": limit_sample, "error_samples": samples}


def seat_record(seat) -> dict:
    d = {"spec": seat.spec, "kind": seat.kind, "name": seat.name, "deck": seat.deck, "label": seat.backend,
         "result": seat.result, "stats": seat.stats, "log_dir": rel(seat.log_dir)}
    if seat.kind == "agent" and seat.log_dir:
        d.update(scan_prompts(os.path.join(seat.log_dir, "prompts.jsonl")))
    return d


def force_first(position: int, rooms: set | None = None, mine: list | None = None):
    """An on_room hook: lobby `position` moves first in game 1 (a room otherwise lets the RPS winner choose, and
    the benchmark alternates who goes first). The RPS still runs, so clients see the usual sequence."""
    from ..arena.server import STATE_NONE, Client, Stage

    def hook(room):
        original = room._ask_first

        def ask_first(chooser):
            if room.match_results:  # a later game of a Bo3: the previous loser chooses, as usual
                return original(chooser)
            room.stage = Stage.CHOOSE_FIRST
            room.chooser = chooser
            for p in room.duelists():
                if isinstance(p, Client):
                    p.state = STATE_NONE
            room._first_chosen(chooser, chooser.pos == position)
        room._ask_first = ask_first
        if rooms is not None:
            import asyncio
            room._bench_loop = asyncio.get_running_loop()  # on_room runs in the room's event loop (for Ctrl+C)
            rooms.add(room)
            if mine is not None:
                mine.append(room)
    return hook


def game_config(cfg: dict, job: Job, logs: str) -> dict:
    g = copy.deepcopy(cfg)
    g["games_dir"] = logs
    g["chat"] = "off"
    random_profile = g.get("backends", {}).get(job.backend, {})
    if random_profile.get("type") == "random" and random_profile.get("seed") is None:
        random_profile["seed"] = job.seed  # baseline games are reproducible too
    return g


def play_one(job: Job, spec: BenchSpec, cfg: dict, db, engine, folder: str, rooms: set) -> dict:
    """Play one game and return its results.jsonl record."""
    logs = os.path.join(paths.resolve(cfg.get("games_dir", "games")), "bench", os.path.basename(folder), job.slug)
    if os.path.isdir(logs):
        shutil.rmtree(logs, ignore_errors=True)  # an earlier attempt that didn't count
    os.makedirs(logs, exist_ok=True)
    first = 0 if job.first == "player" else 1
    record = {"key": job.key, "deck": job.deck, "backend": job.backend, "opponent": job.opponent,
              "game": job.index + 1, "seed": job.seed, "first": job.first, "started": now()}
    t0 = time.monotonic()
    mine = []
    try:
        run = run_games(SeatSpec.parse(job.player_spec), SeatSpec.parse(job.opponent), games=1, rules=spec.rules,
                        seed=job.seed, first=first, out=logs, cfg=game_config(cfg, job, logs), db=db, engine=engine,
                        quiet=True, echo="off", tags=False, lan=False, port=None, time_limit=0,
                        timeout=spec.timeout, on_room=force_first(first, rooms, mine))
    except MatchError as e:
        return {**record, "status": "error", "error": str(e), "wall_seconds": round(time.monotonic() - t0, 1),
                "ended": now()}
    except Exception as e:  # a crash in one game mustn't end the benchmark
        return {**record, "status": "error", "error": f"{type(e).__name__}: {e}",
                "wall_seconds": round(time.monotonic() - t0, 1), "ended": now()}
    finally:
        for room in mine:
            rooms.discard(room)
    record["wall_seconds"] = round(time.monotonic() - t0, 1)
    record["ended"] = now()
    if not run.games:
        return {**record, "status": "error", "error": "the game didn't finish (room timeout or a seat failed)"}
    g = run.games[0]
    player, opponent = (seat_record(s) for s in g.seats)
    replay = None
    if g.replay and os.path.isfile(g.replay):
        replay = os.path.join("replays", job.slug + ".yrpX")
        os.makedirs(os.path.join(folder, "replays"), exist_ok=True)
        shutil.copyfile(g.replay, os.path.join(folder, replay))
    actual_first = "player" if g.first == 0 else "opponent"
    record.update({
        "status": "done", "result": player["result"],
        "winner": None if g.winner is None else ("player" if g.winner == 0 else "opponent"),
        "reason": g.reason, "turns": g.turns, "seconds": g.seconds, "first": actual_first,
        "duel_seed": g.seed, "retries": g.retries, "lua_errors": g.lua_errors, "replay": replay,
        "player": player, "opponent_seat": opponent, "path": run.path,
    })
    if actual_first != job.first:
        record["note"] = f"planned first: {job.first}"
    if not player.get("stats"):
        record.update(status="error", error="no stats from the benchmarked seat")
    limited = [s for s in (player, opponent) if s.get("limit_errors")]
    if limited:
        record["status"] = "aborted"
        record["error"] = "usage limit: " + "; ".join(s.get("limit_sample") or "" for s in limited)
    return record


def game_cost(record: dict) -> float:
    total = 0.0
    for seat in (record.get("player"), record.get("opponent_seat")):
        cost = ((seat or {}).get("stats") or {}).get("cost_usd")
        total += cost or 0.0
    return total


# --- probes and versions ------------------------------------------------------------------------------------------

def probe(profile: dict) -> dict:
    """One tiny real call per LLM backend before the games: it fails fast when the backend can't answer (no server,
    out of usage) and tells the claude CLI's actual model id."""
    kind = profile.get("type")
    if kind not in LLM_TYPES:
        return {"ok": True, "skipped": True}
    t0 = time.monotonic()
    if kind == "claude-code":
        from ..backends.claude_code import WORKDIR
        os.makedirs(WORKDIR, exist_ok=True)
        cmd = [profile.get("command", "claude"), "-p", "--output-format", "json", "--tools", "", "--setting-sources",
               "", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
               "--model", profile.get("model") or "opus"]
        if profile.get("effort"):
            cmd += ["--effort", profile["effort"]]
        cmd.append("Reply with the single word: ok")
        try:
            out = subprocess.run(cmd, cwd=WORKDIR, capture_output=True, text=True, timeout=180)
            data = json.loads(out.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300], "seconds": round(time.monotonic() - t0, 1)}
        error = (data.get("result") or "error result") if data.get("is_error") or not data else None
        return {"ok": error is None, "error": error and str(error)[:300], "limit": bool(error and LIMIT.search(error)),
                "model_ids": sorted(data.get("modelUsage") or {}), "seconds": round(time.monotonic() - t0, 1)}
    from .. import backends
    from ..agent.prompts import SCHEMA
    try:
        session = backends.open_session(profile, "Answer with JSON only.", SCHEMA)
        try:
            reply, info = session.ask(backends.Request('Reply with {"choice": [0], "why": "ok", "plan": ""}.',
                                                       {"kind": "probe", "options": []}, SCHEMA, 120))
        finally:
            session.close()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300], "seconds": round(time.monotonic() - t0, 1)}
    error = info.get("error") if reply is None else None
    return {"ok": reply is not None, "error": error and str(error)[:300], "limit": bool(error and LIMIT.search(error)),
            "model_ids": [profile.get("model")] if profile.get("model") else [],
            "seconds": round(time.monotonic() - t0, 1)}


def _sha(path: str) -> str | None:
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return None


def _newest_mtime(dirs: list[str], ext: str) -> float | None:
    newest = None
    for d in dirs:
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.name.endswith(ext) and e.is_file():
                        m = e.stat().st_mtime
                        newest = m if newest is None or m > newest else newest
        except OSError:
            continue
    return newest


def _date(ts: float | None) -> str | None:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else None


def environment(spec: BenchSpec, cfg: dict, db, engine, profiles: dict, decks: dict, bots: dict,
                probes: dict) -> dict:
    from importlib import metadata
    from ..agent.brain import META_KEYS
    from ..backends import label
    from ..core.constants import rule_set
    try:
        version = metadata.version("ygo-agent")
    except metadata.PackageNotFoundError:
        version = None
    install = engine.install
    try:
        cli = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        cli = None
    env = {
        "written": now(), "ygo_agent": version, "python": sys.version.split()[0],
        "core": {"version": ".".join(map(str, engine.core.version)), "path": rel(install.core_path)},
        "scripts": {"newest": _date(_newest_mtime(install.script_dirs, ".lua")), "dirs": len(install.script_dirs)},
        "cards": {"count": len(db.cards), "databases": len(install.cdb_paths),
                  "newest": _date(_newest_mtime(sorted({os.path.dirname(p) for p in install.cdb_paths}), ".cdb"))},
        "rules": {"name": spec.rules, "flags": hex(rule_set(spec.rules).flags), "text": rule_set(spec.rules).description},
        "decks": decks, "windbot": bots,
        "backends": {}, "claude_cli": cli,
    }
    for name, profile in profiles.items():
        env["backends"][name] = {**{k: profile[k] for k in META_KEYS if profile.get(k) not in (None, "")},
                                 "label": label(profile), "probe": probes.get(name)}
    return env


def windbot_ydk(assets: str, deck: str) -> str | None:
    """A WindBot deck AI's .ydk: Decks/AI_<deck>.ydk, matched ignoring case, spaces and dashes (the executor's
    [Deck] attribute names the file; for a few decks, e.g. "Rank V" = AI_Rank5, the names differ: then None)."""
    folder = os.path.join(assets, "Decks")
    want = re.sub(r"[^a-z0-9]", "", deck.lower())
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    for name in sorted(names):
        stem, ext = os.path.splitext(name)
        if ext == ".ydk" and stem.startswith("AI_") and re.sub(r"[^a-z0-9]", "", stem[3:].lower()) == want:
            return os.path.join(folder, name)
    return None


def deck_info(profile) -> dict:
    import importlib.util
    rules = None
    path = os.path.join(profile.dir, "rules.py")
    if os.path.isfile(path):
        try:
            spec = importlib.util.spec_from_file_location(f"_bench_rules_{profile.key}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            rules = len(getattr(module, "RULES", []))
        except Exception:
            rules = None
    playbook = profile.playbook_path if profile.playbook_path and os.path.isfile(profile.playbook_path) else None
    return {"name": profile.name, "ydk": rel(profile.ydk), "ydk_sha": _sha(profile.ydk), "main": len(profile.main),
            "extra": len(profile.extra), "playbook": rel(playbook), "playbook_sha": _sha(playbook) if playbook else None,
            "playbook_chars": os.path.getsize(playbook) if playbook else 0, "rules": rules}


# --- the run ----------------------------------------------------------------------------------------------------

class Bench:
    def __init__(self, spec: BenchSpec, folder: str, cfg: dict, *, argv: list[str] | None = None, out=print,
                 probe_backends: bool = True):
        self.spec, self.folder, self.cfg = spec.validate(), folder, cfg
        self.argv = argv
        self.say = out
        self.probe_backends = probe_backends
        self.results = ResultsFile(folder)
        self.lock = threading.Lock()
        self.stop_reason = None
        self.blocked_types: set[str] = set()   # backend types out of usage: their games aren't started
        self.skipped: dict[str, str] = {}       # backend -> why its games were skipped
        self.rooms: set = set()
        self.errors_in_a_row = 0
        self.played = 0

    # ---- setup ----

    def prepare(self):
        from ..agent.carddb import CardDB
        from ..arena.deck import DeckRules, check_deck, load_ydk
        from ..arena.windbot import WindBotError, WindBotInstall
        from ..config import ConfigError, backend as backend_profile
        from ..core import Engine, InstallError
        from ..core.constants import rule_set
        from ..match import load_profile
        from .. import backends
        try:
            self.engine = Engine.load(paths.resolve(self.cfg["edopro_dir"]))
        except (InstallError, OSError) as e:
            raise MatchError(f"can't load EDOPro's core: {e}") from None
        self.db = CardDB(self.cfg["edopro_dir"])
        try:
            forbidden = rule_set(self.spec.rules).forbidden_types
        except ValueError as e:
            raise MatchError(str(e)) from None
        legal = DeckRules(forbidden_types=forbidden)
        self.profiles, decks, bots = {}, {}, {}
        for name in self.spec.backends:
            try:
                self.profiles[name] = backend_profile(self.cfg, name)
                backends.check(self.profiles[name])
            except (ConfigError, backends.BackendError) as e:
                raise MatchError(f"backend {name}: {e}") from None
        for deck in self.spec.decks:
            profile = load_profile(deck, self.db, self.cfg)
            loaded = load_ydk(profile.ydk, self.engine.cards)
            err = check_deck(loaded.deck, self.engine.cards, legal, loaded.unknown)
            if err:
                raise MatchError(f"deck {deck} ({profile.ydk}) is not legal under {self.spec.rules}: {err}")
            decks[deck] = deck_info(profile)
        windbot = None
        for opponent in self.spec.opponents:
            seat = SeatSpec.parse(opponent)
            if seat.kind == "windbot":
                try:
                    windbot = windbot or WindBotInstall.find(self.engine.install.root)
                    bot = windbot.resolve(seat.deck)
                except WindBotError as e:
                    raise MatchError(str(e)) from None
                path = windbot_ydk(windbot.assets, bot.deck)
                if path:
                    loaded = load_ydk(path, self.engine.cards)
                    err = check_deck(loaded.deck, self.engine.cards, legal, loaded.unknown)
                    if err:
                        raise MatchError(f"WindBot deck {bot.name} is not legal under {self.spec.rules} ({err}); pick "
                                         "another opponent (docs/bench.md lists the legal ones)")
                bots[opponent] = {"name": bot.name, "deck": bot.deck, "difficulty": bot.difficulty,
                                  "exe": rel(windbot.exe), "fork": windbot.is_fork,
                                  "ydk_sha": _sha(path) if path else None}
            else:
                profile = load_profile(seat.deck, self.db, self.cfg)
                bots[opponent] = {"ai": True, "deck": deck_info(profile), "backend": seat.backend}
        probes = {}
        if self.probe_backends:
            for name, profile in self.profiles.items():
                if profile.get("type") in LLM_TYPES and self.spec.games_of(name) > 0:
                    self.say(paint(DIM, f"Checking backend {name} with one small call..."))
                    probes[name] = result = probe(profile)
                    if not result["ok"]:
                        self.skipped[name] = f"probe failed: {result.get('error')}"
                        if result.get("limit"):
                            self.blocked_types.add(profile["type"])
                        self.say(paint(RED, f"  {name}: {result.get('error')} — its games are skipped this time."))
                    elif result.get("model_ids"):
                        self.say(paint(DIM, f"  {name}: {', '.join(result['model_ids'])}, {result['seconds']}s"))
        self.env = environment(self.spec, self.cfg, self.db, self.engine, self.profiles, decks, bots, probes)
        old = os.path.join(self.folder, "env.json")
        if os.path.isfile(old):  # keep model ids seen by earlier invocations of a resumed run
            try:
                previous = json.load(open(old, encoding="utf-8"))
                for name, b in previous.get("backends", {}).items():
                    if name not in self.env["backends"] or not (self.env["backends"][name].get("probe") or {}).get("ok"):
                        self.env["backends"].setdefault(name, b)
                        if (b.get("probe") or {}).get("ok"):
                            self.env["backends"][name]["probe"] = b["probe"]
            except (OSError, ValueError):
                pass
        write_json(os.path.join(self.folder, "env.json"), self.env)
        self.write_spec()

    def write_spec(self):
        path = os.path.join(self.folder, "spec.json")
        history = []
        if os.path.isfile(path):
            try:
                history = json.load(open(path, encoding="utf-8")).get("invocations", [])
            except (OSError, ValueError):
                history = []
        history.append({"at": now(), "argv": self.argv})
        planned = sorted({j.key for j in self.spec.jobs()} | set(self._planned_before(path)))
        write_json(path, {"spec": self.spec.to_dict(), "invocations": history, "planned": planned})

    @staticmethod
    def _planned_before(path):
        try:
            return json.load(open(path, encoding="utf-8")).get("planned", [])
        except (OSError, ValueError):
            return []

    # ---- the games ----

    def spent(self) -> float:
        return sum(game_cost(r) for r in finished(read_results(self.folder)).values())

    def next_job(self, queue: list[Job]) -> Job | None:
        with self.lock:
            while queue and self.stop_reason is None:
                job = queue.pop(0)
                if job.backend in self.skipped:
                    continue
                if self.profiles[job.backend].get("type") in self.blocked_types or self._opponent_blocked(job):
                    continue
                if self.spec.budget_usd is not None and self.spent() >= self.spec.budget_usd:
                    self.stop_reason = f"budget of ${self.spec.budget_usd:g} reached"
                    return None
                return job
            return None

    def _opponent_blocked(self, job: Job) -> bool:
        seat = SeatSpec.parse(job.opponent)
        if seat.kind != "agent" or not seat.backend:
            return False
        profile = self.cfg.get("backends", {}).get(seat.backend, {})
        return profile.get("type") in self.blocked_types

    def worker(self, queue: list[Job], total: int):
        while True:
            job = self.next_job(queue)
            if job is None:
                return
            record = play_one(job, self.spec, self.cfg, self.db, self.engine, self.folder, self.rooms)
            if self.stop_reason == "interrupted":
                return  # Ctrl+C: this game may have been cut short; resume re-plays it
            self.results.append(record)
            self.report_game(record, total)

    def report_game(self, r: dict, total: int):
        with self.lock:
            self.played += 1
            n = self.played
            where = f"{r['deck']} · {r['backend']} vs {opponent_label(r['opponent'])} #{r['game']}"
            if r["status"] == "done":
                self.errors_in_a_row = 0
                stats = r["player"]["stats"] or {}
                word = {"win": paint(BOLD + ";" + GREEN, "WIN"), "loss": paint(BOLD + ";" + RED, "LOSS")}.get(
                    r["result"], paint(YELLOW, "DRAW"))
                cost = game_cost(r)
                bits = [f"{r['turns']} turns", duration(r["seconds"]), f"{stats.get('decisions', 0)} decisions"]
                if stats.get("invalid_replies"):
                    bits.append(f"{stats['invalid_replies']} invalid")
                if stats.get("by_source", {}).get("fallback"):
                    bits.append(f"{stats['by_source']['fallback']} fallbacks")
                if cost:
                    bits.append(f"${cost:.2f}")
                self.say(f"[{n}/{total}] {where} (going {'first' if r['first'] == 'player' else 'second'}): "
                         f"{word} — {', '.join(bits)}")
                return
            if r["status"] == "aborted":
                kinds = set()
                if r["player"].get("limit_errors"):
                    kinds.add(self.profiles[r["backend"]]["type"])
                opp = SeatSpec.parse(r["opponent"])
                if opp.kind == "agent" and opp.backend and (r.get("opponent_seat") or {}).get("limit_errors"):
                    kinds.add(self.cfg["backends"].get(opp.backend, {}).get("type"))
                self.blocked_types |= {k for k in kinds if k}
                self.say(paint(RED, f"[{n}/{total}] {where}: not counted — {r['error']}. No more "
                                    f"{'/'.join(sorted(k for k in kinds if k))} games are started; `--resume` "
                                    "continues once the usage resets."))
                return
            self.errors_in_a_row += 1
            self.say(paint(RED, f"[{n}/{total}] {where}: error — {r.get('error')}"))
            if self.errors_in_a_row >= MAX_ERRORS_IN_A_ROW:
                self.stop_reason = f"{self.errors_in_a_row} games in a row failed (last: {r.get('error')})"

    def run(self) -> dict:
        os.makedirs(self.folder, exist_ok=True)
        self.prepare()
        records = read_results(self.folder)
        jobs = self.spec.jobs()
        queue = pending(jobs, records)
        done = len(jobs) - len(queue)
        self.say(paint(BOLD, f"Benchmark {self.spec.name}: {len(jobs)} games planned"
                             + (f", {done} already done" if done else "") + f", {len(queue)} to play, "
                             f"{self.spec.parallel} at a time.") + paint(DIM, f"  Folder: {rel(self.folder)}"))
        started = time.monotonic()
        threads = [threading.Thread(target=self.worker, args=(queue, len(queue)), daemon=True, name=f"bench-{i + 1}")
                   for i in range(min(self.spec.parallel, len(queue)))]
        for t in threads:
            t.start()
        try:
            for t in threads:
                while t.is_alive():
                    t.join(0.5)
        except KeyboardInterrupt:
            self.stop_reason = "interrupted"
            for room in list(self.rooms):
                loop = getattr(room, "_bench_loop", None)
                if loop:
                    loop.call_soon_threadsafe(room.finished.set)
            self.say(paint(YELLOW, "\nStopped with Ctrl+C: the games in flight are dropped (`--resume` re-plays them)."))
        left = len(pending(jobs, read_results(self.folder)))
        if self.stop_reason and self.stop_reason != "interrupted":
            self.say(paint(YELLOW, f"Stopped early: {self.stop_reason}."))
        for name, why in self.skipped.items():
            self.say(paint(YELLOW, f"Skipped {name}: {why}"))
        if self.blocked_types:
            self.say(paint(YELLOW, f"Out of usage: {', '.join(sorted(self.blocked_types))} games were not started."))
        self.say(paint(DIM, f"{self.played} games in {duration(time.monotonic() - started)}; {left} of "
                            f"{len(jobs)} still to play."))
        return {"played": self.played, "left": left, "stop_reason": self.stop_reason}


def write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def new_folder(name: str, root: str = RESULTS_ROOT) -> str:
    from ..agent.gamelog import slug
    stem = os.path.join(root, f"{time.strftime('%Y-%m-%d_%H%M%S')}_{slug(name, 40)}")
    path, n = stem, 1
    while os.path.exists(path):
        n += 1
        path = f"{stem}-{n}"
    os.makedirs(path)
    return path


def latest_folder(name: str | None, root: str = RESULTS_ROOT) -> str | None:
    """The newest run folder (of this benchmark name, when given)."""
    from ..agent.gamelog import slug
    if not os.path.isdir(root):
        return None
    folders = sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, "spec.json")))
    if name:
        folders = [d for d in folders if d.split("_", 2)[-1] == slug(name, 40)]
    return os.path.join(root, folders[-1]) if folders else None
