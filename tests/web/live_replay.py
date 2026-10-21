"""A logged game replayed through a DuelBrain onto the bus, the way a live seat publishes it (GameLog's own
messages, not the recorded-game loader's): the stand-in for a live game in the panel's browser tests.

    python tests/web/live_replay.py games/<dir> [--port 7941] [--delay 0.4]   # serve it live, for a look
"""

import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [p for p in (HERE, os.path.dirname(HERE)) if p not in sys.path]

from ygo_agent.agent.brain import DuelBrain  # noqa: E402
from ygo_agent.agent.profile import Profile  # noqa: E402


def rows(game_dir):
    with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def replay_live(game_dir, cfg, db, game_id, delay=0.0, stop=None, deck=None, inject=None):
    """Feed game_dir's events and decisions to a DuelBrain whose backend answers what the game's log says it
    answered. Publishes as seat 0 of `game_id`; `delay` seconds before each decision. `inject`: {decision id: [extra
    messages]} fed right after that decision (a decision without a state gets the previous one's; give it an
    "answer" to script its reply). Returns the brain (closed)."""
    log = rows(game_dir)
    meta = json.load(open(os.path.join(game_dir, "meta.json"), encoding="utf-8"))
    answers = {r["msg"]["id"]: r["msg"].get("choice") for r in log if r["kind"] == "reply"}
    for extra in (inject or {}).values():
        answers.update({m["id"]: m.pop("answer") for m in extra if "answer" in m})
    cfg = json.loads(json.dumps(cfg, default=str))
    cfg["backends"]["replay"] = {"type": "scripted", "policy": lambda d: answers.get(d["id"]) or []}
    brain = DuelBrain(cfg, db, Profile(deck or meta.get("deck") or "saffira", db, cfg), prewarm=False,
                      backend={"name": "replay", **cfg["backends"]["replay"]}, fallback="heuristic",
                      game_id=game_id, seat=0, log_options={"echo": "off", "latest": False, "publish": True})
    try:
        for r in log:
            if stop is not None and stop.is_set():
                break
            msg = json.loads(json.dumps(r["msg"]))
            if r["kind"] == "event":
                brain.on_event(msg)
            elif r["kind"] == "decide":
                if delay:
                    time.sleep(delay)
                brain.on_decide(msg)
                for extra in (inject or {}).get(msg["id"], []):
                    extra = json.loads(json.dumps(extra))
                    if extra.get("t") == "decide":
                        extra.setdefault("state", json.loads(json.dumps(msg["state"])))
                        brain.on_decide(extra)
                    else:
                        brain.on_event(extra)
    finally:
        brain.close()
    return brain


def main(argv=None):
    import argparse
    from ygo_agent.agent.carddb import CardDB
    from ygo_agent.config import load_config
    from ygo_agent.web import server
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("--port", type=int, default=7941)
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--games-dir", default=os.path.join(os.path.dirname(HERE), "..", "games", "replays"))
    args = ap.parse_args(argv)
    cfg = load_config(local=None, overrides={"games_dir": os.path.abspath(args.games_dir), "chat": "off"})
    db = CardDB(cfg["edopro_dir"])
    srv = server.start(cfg, db, port=args.port)
    gid = f"live-replay-{int(time.time())}"
    print(f"{srv.url}?game={gid}", flush=True)
    time.sleep(2)
    threading.Thread(target=replay_live, args=(args.game_dir, cfg, db, gid, args.delay), daemon=True).start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.stop()


if __name__ == "__main__":
    main()
