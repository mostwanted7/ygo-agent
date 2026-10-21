"""Synthetic benchmark records, shaped like runner.play_one() writes them."""

import json
import os


def stats(decisions=40, backend=30, rule=4, auto=6, fallback=0, replies=None, invalid=0, errors=0, cost=None,
          tokens=(0, 0, 0, 0), latency=(None, None)):
    replies = backend if replies is None else replies
    return {"decisions": decisions,
            "by_source": {"backend": backend, "rule": rule, "auto": auto, "fallback": fallback, "pilot": 0},
            "asks": backend, "replies": replies, "invalid_replies": invalid,
            "invalid_rate": invalid / replies if replies else None, "errors": errors,
            "fallback_rate": fallback / decisions, "latency_mean_s": latency[0], "latency_p95_s": latency[1],
            "tokens": dict(zip(("input", "output", "cache_read", "cache_write"), tokens)),
            "cost_usd": cost, "sessions": 5, "rollovers": 0}


def record(deck="saffira", backend="sonnet", opponent="windbot:Blue-Eyes", game=1, result="win", turns=8,
           seconds=300.0, first=None, status="done", latencies=(), timeouts=0, st=None, **extra):
    first = first or ("player" if game % 2 else "opponent")
    r = {"key": f"{deck}|{backend}|{opponent}|{game}", "deck": deck, "backend": backend, "opponent": opponent,
         "game": game, "seed": 1000 + game - 1, "first": first, "status": status, "started": "2026-10-21 10:00:00",
         "ended": "2026-10-21 10:05:00"}
    if status == "done":
        r.update({"result": result, "winner": {"win": "player", "loss": "opponent"}.get(result), "reason": "LP",
                  "turns": turns, "seconds": seconds, "retries": 0, "lua_errors": 0,
                  "replay": f"replays/{deck}--{backend}--{game:03d}.yrpX",
                  "player": {"spec": f"{deck}:{backend}", "kind": "agent", "stats": st or stats(),
                             "latencies": list(latencies), "timeouts": timeouts, "limit_errors": 0},
                  "opponent_seat": {"spec": opponent, "kind": "windbot", "stats": None}})
    r.update(extra)
    return r


def write(folder, records, spec=None, env=None):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "results.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    if spec is not None:
        with open(os.path.join(folder, "spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f)
    if env is not None:
        with open(os.path.join(folder, "env.json"), "w", encoding="utf-8") as f:
            json.dump(env, f)
