"""The lab: the player plays one turn with a chosen hand against a dummy that never acts, and the trainer records
what it did and where it ended.

    hands = plan_hands(dossier, lines, count=10, seed=1)       # stacked line hands, random hands, going second
    result = run_hand(hand, engine, cfg, db, profile, backend, out_dir)

Going first, the board is recorded when turn 2 starts, the dummy's turn 2 is played out (it passes, so the player's
Set cards and quick effects get their windows) and the duel stops at turn 3; going second, the dummy passes turn 1 on
the fixed board (goldfish.COMMON_BOARD) and the player's turn 2 is recorded. Hands are stacked on top of the Deck,
so every hand is exactly the one planned, whatever the shuffle.
"""

from __future__ import annotations

import collections
import copy
import difflib
import os
import random
import shutil
from dataclasses import asdict, dataclass, field

from ..arena.duel import DuelConfig
from . import goldfish, logs

HAND = 5


@dataclass
class LabHand:
    id: str                       # hand-01, ...
    kind: str                     # line / random / second
    first: bool
    cards: list[int]              # stacked on top of the Deck: the opening hand, then the first draw going second
    names: list[str]
    seed: int
    line: str | None = None       # the line id the hand targets
    line_name: str | None = None
    missing: list[str] = field(default_factory=list)  # key cards the Main Deck doesn't have

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LabHand":
        return cls(**d)


def resolve_card(name: str, pool: dict[str, int]) -> int | None:
    """An exact (case-insensitive) Main Deck card name, else the closest one."""
    low = {n.lower(): c for n, c in pool.items()}
    if name.lower().strip() in low:
        return low[name.lower().strip()]
    close = difflib.get_close_matches(name.lower().strip(), list(low), n=1, cutoff=0.85)
    return low[close[0]] if close else None


def plan_hands(dossier, lines: list[dict], count: int, seed: int, second: int | None = None,
               prefix: str = "hand", random_hands: int | None = None) -> list[LabHand]:
    """`count` hands: one per line (in order; going-second lines get going-second hands), `random_hands` random
    going-first hands for coverage (default a quarter), and `second` going-second hands (default 2 if count >= 6),
    which the going-second lines use first."""
    main = dossier.main_codes()
    names = {c.id: c.name for c in dossier.cards}
    pool = {c.name: c.id for c in dossier.cards if c.section == "main"}
    if second is None:
        second = 2 if count >= 6 else 1 if count >= 4 else 0
    second = min(second, count)
    n_random = random_hands if random_hands is not None else max(1, count // 4) if count >= 2 else 0
    room = max(0, count - second - n_random)
    hands: list[LabHand] = []

    def make(kind, first, cards, line=None, missing=()):
        n = len(hands) + 1
        hands.append(LabHand(f"{prefix}-{n:02d}", kind, first, cards, [names.get(c, str(c)) for c in cards],
                             seed * 1000 + n, line.get("id") if line else None, line.get("name") if line else None,
                             list(missing)))

    def fill(keys: list[int], size: int, rng: random.Random) -> list[int]:
        rest = list(main)
        for k in keys:
            if k in rest:
                rest.remove(k)
        rng.shuffle(rest)
        return keys + rest[:max(0, size - len(keys))]

    line_slots = room
    for line in lines:
        going_second = line.get("going") == "second"
        if going_second and second <= 0:
            continue
        if not going_second and line_slots <= 0:
            continue
        keys, missing = [], []
        counts = collections.Counter(main)
        for name in (line.get("key_cards") or [])[:4]:
            code = resolve_card(name, pool)
            if code is None or counts[code] <= 0:
                missing.append(name)
                continue
            counts[code] -= 1
            keys.append(code)
        rng = random.Random(seed * 7919 + len(hands))
        size = HAND + (1 if going_second else 0)
        make("second" if going_second else "line", not going_second, fill(keys, size, rng), line, missing)
        if going_second:
            second -= 1
        else:
            line_slots -= 1
    while len(hands) < count - second:
        rng = random.Random(seed * 104729 + len(hands))
        make("random", True, fill([], HAND, rng))
    for _ in range(second):
        rng = random.Random(seed * 15485863 + len(hands))
        make("second", False, fill([], HAND + 1, rng))
    return hands[:count]


def lab_config(cfg: dict, games_dir: str) -> dict:
    out = copy.deepcopy(cfg)
    out["games_dir"] = os.path.abspath(games_dir)
    out["chat"] = "off"
    return out


def run_hand(hand: LabHand, engine, cfg: dict, db, profile, backend: dict, out_dir: str, *, rules: str = "mr3",
             echo: str = "key", tag: str | None = None, opponent_turn: bool = True) -> dict:
    """Play one lab turn. Returns the result dict (see lab-results.md): the end board, the condensed log, problems,
    the seat's stats and cost. The game log ends up in out_dir/<hand id>/. `opponent_turn`: going first, the dummy's
    turn 2 is played too (it passes everything), so Set Traps and quick effects get their windows."""
    from ..arena.deck import load_ydk
    from ..arena.native_seat import AgentSeat
    from ..arena.runner import run_duel
    deck = load_ydk(profile.ydk, engine.cards).deck
    tmp_games = os.path.join(out_dir, f".games-{hand.id}")
    seat = AgentSeat(f"{profile.name} (lab)"[:20], lab_config(cfg, tmp_games), db, profile, backend,
                     cards=engine.cards, mode="selfplay", opponent=None,
                     log_options={"echo": echo, "tag": tag, "latest": False})
    dummy = goldfish.goldfish_seat()
    player_team = 0 if hand.first else 1
    seats = (seat, dummy) if hand.first else (dummy, seat)
    own = 1 if hand.first else 2
    stop = goldfish.TurnStop(player_team, last_turn=own + (1 if hand.first and opponent_turn else 0),
                             cards=engine.cards, own_turn=own)
    start_state = None if hand.first else goldfish.common_board(team=0)
    duel = None
    try:
        duel = run_duel(engine, DuelConfig(rules=rules), (deck, deck.copy()), seats, seed=hand.seed,
                        stack={player_team: list(hand.cards)}, start_state=start_state, observers=[stop])
        result = duel.result
        pending = seat.collect()
        info = pending.result(timeout=300) if hasattr(pending, "result") else pending
    finally:
        seat.close()
        if duel is not None:
            duel.close()
    target = os.path.join(out_dir, hand.id)
    log_dir = info["dir"] if info else None
    if log_dir and os.path.isdir(log_dir):
        if os.path.isdir(target):
            shutil.rmtree(target)
        os.replace(log_dir, target)
        log_dir = target
    shutil.rmtree(tmp_games, ignore_errors=True)
    md = logs.read(os.path.join(target, "game.md")) if log_dir else ""
    stats = (info or {}).get("stats") or {}
    return {**hand.to_dict(), "log": target if log_dir else None,
            "board": stop.board, "board_text": goldfish.board_text(stop.board), "after": stop.after,
            "after_text": goldfish.board_text(stop.after) if stop.after else None,
            "condensed": logs.condense(md), "problems": logs.problems(md), "decisions": logs.decision_count(md),
            "engine_retries": result.retries, "lua_errors": list(result.lua_errors)[:5], "turns": result.turns,
            "stats": stats, "cost": stats.get("cost_usd") or 0.0}


def results_markdown(results: list[dict], lines: list[dict], board_text: str) -> str:
    """lab-results.md: what the reviewer reads, one section per hand."""
    by_id = {line.get("id"): line for line in lines}
    out = [f"# Lab results ({len(results)} hands)", ""]
    for r in results:
        line = by_id.get(r.get("line"))
        head = f"## {r['id']} — " + (f"line {r['line']} \"{r.get('line_name')}\"" if r.get("line") else
                                     "random hand") + (" (going first)" if r["first"] else " (going second)")
        out += [head, "", f"Hand: {', '.join(r['names'][:HAND])}" +
                (f"; first draw: {r['names'][HAND]}" if len(r['names']) > HAND else "")]
        if r.get("missing"):
            out.append(f"Key cards the Main Deck doesn't have: {', '.join(r['missing'])}")
        if line:
            out.append(f"Expected end board: {', '.join(line.get('expected_board') or []) or '(not given)'}")
        if not r["first"]:
            out.append(f"Opponent's board at the start: {board_text}")
        out += ["", "End board (your turn is over):", r.get("board_text") or "(none)", ""]
        if r.get("after_text"):
            out += ["After the dummy's turn (it only passed; your Set cards and quick effects had their windows):",
                    r["after_text"], ""]
        probs = r.get("problems") or []
        if r.get("engine_retries"):
            probs = probs + [f"the engine refused {r['engine_retries']} response(s)"]
        if r.get("lua_errors"):
            probs = probs + [f"Lua errors: {r['lua_errors']}"]
        out.append("Problems: " + ("; ".join(probs) if probs else "none"))
        out += ["", "What it did:", "```", (r.get("condensed") or "").strip(), "```", ""]
    return "\n".join(out)
