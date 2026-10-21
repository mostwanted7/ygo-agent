"""Per-game output under games/arena/<id>/: a compact readable log, the EDOPro replay, and result.json."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict

from ..core.cards import CardDatabase
from ..core.constants import WIN_REASON_NAMES, Msg
from .duel import VIEW_FULL, Duel, DuelObserver, DuelResult
from .messages import Message, Prompt, decode_response, render

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO_ROOT, "games", "arena")
_QUIET = {Msg.UPDATE_DATA, Msg.UPDATE_CARD, Msg.HINT, Msg.WAITING, Msg.CARD_HINT, Msg.PLAYER_HINT}


def game_dir(base: str | None, label: str) -> str:
    """A fresh directory `<base>/<timestamp>_<label>` (suffixed if it exists)."""
    base = base or DEFAULT_OUT
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "game"
    stem = os.path.join(base, f"{time.strftime('%Y%m%d-%H%M%S')}_{safe}")
    path, n = stem, 1
    while os.path.exists(path):
        n += 1
        path = f"{stem}-{n}"
    os.makedirs(path)
    return path


class GameLog(DuelObserver):
    """Writes one line per public event (unfiltered view), each prompt and each decoded response."""
    views = frozenset({VIEW_FULL})

    def __init__(self, path: str, cards: CardDatabase | None, names: tuple[str, str] = ("p0", "p1")):
        self.path = path
        self.cards = cards
        self.names = names
        self._f = open(path, "w", encoding="utf-8")
        self.turn = 0

    def _w(self, line: str) -> None:
        self._f.write(line + "\n")

    def on_start(self, duel: Duel) -> None:
        self.names = duel.names
        self._w(f"# {duel.names[0]} (team 0, goes first) vs {duel.names[1]} (team 1)")
        self._w(f"# seed {duel.seed} core seed {list(duel.core_seed)} flags {duel.config.flags:#x}")

    def on_message(self, view: int, msg: Message) -> None:
        if msg.type == Msg.NEW_TURN:
            self.turn += 1
            self._w(f"\n== turn {self.turn}: {self.names[getattr(msg, 'player', 0)]}")
        if msg.type in _QUIET:
            return
        self._w("  " + render(msg, self.cards))

    def on_prompt(self, team: int, prompt: Prompt, retry: bool) -> None:
        self._w(f"  > {self.names[team]}{' (retry)' if retry else ''}: {render(prompt, self.cards)}")

    def on_response(self, team: int, prompt: Prompt, data: bytes) -> None:
        self._w(f"  < {self.names[team]}: {json.dumps(decode_response(prompt, data))}")

    def on_end(self, duel: Duel, result: DuelResult) -> None:
        who = "draw" if result.is_draw else self.names[result.winner]
        self._w(f"\n# result: {who} ({WIN_REASON_NAMES.get(result.reason, result.reason)}), turns {result.turns}, "
                f"responses {result.responses}, retries {result.retries}, lua errors {len(result.lua_errors)}")
        for err in result.lua_errors:
            self._w(f"# lua error: {err}")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


def write_result(path: str, duel: Duel, extra: dict | None = None) -> dict:
    r = duel.result
    data = {
        "names": list(duel.names),
        "winner": None if r is None or r.is_draw else r.winner,
        "winner_name": None if r is None or r.is_draw else duel.names[r.winner],
        "reason": None if r is None else WIN_REASON_NAMES.get(r.reason, r.reason),
        "seed": duel.seed,
        "core_seed": list(duel.core_seed),
        "flags": duel.config.flags,
        "result": asdict(r) if r else None,
    }
    if extra:
        data.update(extra)
    with open(os.path.join(path, "result.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def write_replay(path: str, duel: Duel, name: str = "replay.yrpX") -> str | None:
    if duel.replay is None:
        return None
    out = os.path.join(path, name)
    with open(out, "wb") as f:
        f.write(duel.replay.yrpx())
    return out
