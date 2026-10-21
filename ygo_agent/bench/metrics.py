"""Benchmark statistics: Wilson intervals, percentiles, per-group aggregation of game records, and a Bradley-Terry
rating. Pure functions over the records in results.jsonl (one dict per game, see runner.game_record)."""

from __future__ import annotations

import math
from collections import defaultdict

Z95 = 1.959964
TOKEN_KEYS = ("input", "output", "cache_read", "cache_write")


def wilson(successes: float, n: int, z: float = Z95) -> tuple[float, float] | None:
    """The Wilson score interval for a binomial proportion (95% by default); None without trials."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def percentile(values, q: float) -> float | None:
    """Nearest-rank percentile (the method agent/stats.py uses for the per-game p95)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _ratio(a, b):
    return a / b if b else None


def aggregate(records: list[dict]) -> dict:
    """Metrics over a group of finished games, all from the benchmarked seat's side (records with status "done")."""
    n = len(records)
    wins = sum(1 for r in records if r["result"] == "win")
    losses = sum(1 for r in records if r["result"] == "loss")
    draws = n - wins - losses
    first = [r for r in records if r.get("first") == "player"]
    second = [r for r in records if r.get("first") == "opponent"]
    stats = [r["player"]["stats"] for r in records if (r.get("player") or {}).get("stats")]
    decisions = sum(s["decisions"] for s in stats)
    src = defaultdict(int)
    for s in stats:
        for k, v in s["by_source"].items():
            src[k] += v
    replies = sum(s["replies"] for s in stats)
    invalid = sum(s["invalid_replies"] for s in stats)
    asks = sum(s["asks"] for s in stats)
    latencies = [x for r in records for x in (r.get("player") or {}).get("latencies") or ()]
    if not latencies:  # older records without per-decision latencies: the per-game means, weighted by asks
        timed = [(s["latency_mean_s"], s["asks"]) for s in stats if s.get("latency_mean_s") is not None]
        weight = sum(w for _, w in timed)
        lat_mean = sum(m * w for m, w in timed) / weight if weight else None
        lat_p50, lat_p95 = None, max((s["latency_p95_s"] for s in stats if s.get("latency_p95_s") is not None),
                                     default=None)
    else:
        lat_mean, lat_p50, lat_p95 = mean(latencies), percentile(latencies, 0.5), percentile(latencies, 0.95)
    tokens = {k: sum(s["tokens"].get(k, 0) for s in stats) for k in TOKEN_KEYS}
    costs = [s["cost_usd"] for s in stats if s.get("cost_usd") is not None]
    ci = wilson(wins, n)
    return {
        "games": n, "wins": wins, "losses": losses, "draws": draws,
        "win_rate": _ratio(wins, n), "ci95": list(ci) if ci else None,
        "first": {"games": len(first), "wins": sum(1 for r in first if r["result"] == "win")},
        "second": {"games": len(second), "wins": sum(1 for r in second if r["result"] == "win")},
        "turns_mean": mean(r["turns"] for r in records),
        "seconds_mean": mean(r["seconds"] for r in records),
        "decisions": decisions, "decisions_per_game": _ratio(decisions, len(stats)),
        "asks": asks, "replies": replies, "invalid_replies": invalid,
        "invalid_rate": _ratio(invalid, replies),
        "fallback_rate": _ratio(src["fallback"], decisions),
        "rule_share": _ratio(src["rule"], decisions),
        "backend_share": _ratio(src["backend"], decisions),
        "by_source": dict(src),
        "errors": sum(s["errors"] for s in stats),
        "timeouts": sum((r.get("player") or {}).get("timeouts", 0) for r in records),
        "engine_retries": sum(r.get("retries", 0) for r in records),
        "lua_errors": sum(r.get("lua_errors", 0) for r in records),
        "latency_mean_s": lat_mean, "latency_p50_s": lat_p50, "latency_p95_s": lat_p95,
        "tokens": tokens,
        "tokens_per_game": {k: v / len(stats) for k, v in tokens.items()} if stats else None,
        "cost_usd": sum(costs) if costs else None,
        "cost_per_game": sum(costs) / len(costs) if costs else None,
        "cost_known_games": len(costs),
    }


def group(records: list[dict], *keys: str) -> dict[tuple, list[dict]]:
    out = defaultdict(list)
    for r in records:
        out[tuple(r[k] for k in keys)].append(r)
    return dict(out)


def bradley_terry(games: list[tuple[str, str, float]], anchor: float = 1500.0, prior: float = 1.0,
                  iterations: int = 2000, tol: float = 1e-10) -> dict[str, float]:
    """Elo-scale ratings from (a, b, score of a) results (1 win, 0 loss, 0.5 draw), by the Bradley-Terry MM
    algorithm (Hunter 2004). Every entity also gets `prior` virtual wins and losses against a fixed player rated
    `anchor`, so an unbeaten or winless entity still gets a finite rating and sparse data shrinks toward `anchor`."""
    names = sorted({x for a, b, _ in games for x in (a, b)})
    if not names:
        return {}
    wins = defaultdict(float)
    pairs = defaultdict(float)
    for a, b, score in games:
        wins[a] += score
        wins[b] += 1 - score
        pairs[(a, b)] += 1
        pairs[(b, a)] += 1
    strength = {x: 1.0 for x in names}
    for _ in range(iterations):
        new = {}
        for i in names:
            denom = 2 * prior / (strength[i] + 1.0)
            for j in names:
                n = pairs.get((i, j))
                if n:
                    denom += n / (strength[i] + strength[j])
            new[i] = (wins[i] + prior) / denom
        delta = max(abs(math.log(new[x] / strength[x])) for x in names)
        strength = new
        if delta < tol:
            break
    return {x: anchor + 400 * math.log10(strength[x]) for x in names}
