"""Demo mode: a recorded game published to the bus at a watchable pace, as if it were being played right now (for
trying the panel out, and for recording the README's GIF)."""

import os
import threading
import time

from .bus import BUS
from .recorded import load_game

QUIET_EVENTS = ("chain_end", "draw", "chat", "room")
FINAL_META = ("result", "ended", "stats")


def pace(prev, msg):
    """Seconds to wait before `msg` at speed 1: roughly the real rhythm, squeezed so nothing drags."""
    kind = msg.get("type")
    if kind == "event":
        e = (msg.get("ev") or {}).get("e")
        if e == "new_turn":
            return 1.6
        if e in QUIET_EVENTS or not msg.get("text"):
            return 0.05
        return 0.6 if e in ("attack", "chaining", "summoning", "damage", "win") else 0.35
    if kind == "decision":
        hidden = (msg.get("decision") or {}).get("kind") == "place"
        return 0.05 if hidden else 0.5
    if kind == "reply":
        if prev and prev.get("type") == "decision" and (prev.get("decision") or {}).get("kind") == "place":
            return 0.05
        if msg.get("source") in ("backend", "pilot", "human"):  # the "thinking" the panel shows, then time to read
            return min(max(msg.get("seconds") or 1.0, 1.0), 6.0) + (1.2 if msg.get("why") else 0)
        return 0.4
    if kind in ("advice", "human_choice"):
        return 0.8
    return 0


class Demo:
    def __init__(self, game_dir, db, speed=2.0, bus=BUS, loop=False):
        self.game_dir = game_dir
        self.name = os.path.basename(os.path.realpath(game_dir))
        self.messages = load_game(game_dir, db, self.name)
        self.speed = max(float(speed), 0.01)
        self.bus = bus
        self.loop = loop
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.game_id = None

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.is_set():
            self.play_once()
            if not self.loop:
                return
            self.stop_event.wait(5)

    def play_once(self):
        self.game_id = f"demo:{self.name}:{int(time.time())}"
        prev, outcome = None, {}
        for msg in self.messages:
            if self.stop_event.wait(pace(prev, msg) / self.speed):
                return
            out = {k: v for k, v in msg.items() if k not in ("seq", "recorded")}
            out.update(game_id=self.game_id, ts=round(time.time(), 3))
            if out["type"] == "game_start":
                out["demo"] = True
            elif out["type"] == "meta":
                # A finished game's meta.json knows the result; the demo is live until its game_end.
                outcome.update({k: out.pop(k) for k in FINAL_META if k in out})
            self.bus.publish(out)
            prev = msg
        if outcome:
            self.bus.publish({"type": "meta", "game_id": self.game_id, "seat": 0, "ts": round(time.time(), 3), **outcome})
