"""Per-game decision statistics: printed when the game ends and written to meta.json under "stats".

The field names are stable (the benchmark aggregates them); docs/backends.md documents each one.
"""

import collections
import math

SOURCES = ("backend", "rule", "auto", "fallback", "pilot")
TOKENS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")


def source_group(source):
    return "rule" if source.startswith("rule") else source


def p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]


class GameStats:
    def __init__(self):
        self.by_source = collections.Counter()
        self.asks = 0          # session.ask() calls (a corrective re-ask is a second call)
        self.replies = 0       # model outputs received (a session's own repair retry is a second one)
        self.invalid = 0       # outputs that couldn't be read, or named an illegal choice
        self.errors = 0        # asks that got no output at all (timeout, HTTP error, crashed session)
        self.latencies = []    # seconds the backend took per decision it was asked (all its asks together)
        self.tokens = collections.Counter()
        self.cost = None
        self.sessions = 0
        self.rollovers = 0     # sessions that started mid-turn (message limit, crash, timeout)

    def decision(self, source):
        self.by_source[source_group(source)] += 1

    def ask(self, info):
        self.asks += 1
        self.replies += info.get("replies", 0)
        self.invalid += info.get("invalid", 0)
        if not info.get("replies") and info.get("error"):
            self.errors += 1
        for key in TOKENS:
            self.tokens[key] += info.get(key) or 0
        if info.get("cost_usd") is not None:
            self.cost = (self.cost or 0) + info["cost_usd"]

    def summary(self):
        decisions = sum(self.by_source.values())
        mean = sum(self.latencies) / len(self.latencies) if self.latencies else None
        return {
            "decisions": decisions,
            "by_source": {s: self.by_source.get(s, 0) for s in SOURCES},
            "asks": self.asks,
            "replies": self.replies,
            "invalid_replies": self.invalid,
            "invalid_rate": round(self.invalid / self.replies, 4) if self.replies else None,
            "errors": self.errors,
            "fallback_rate": round(self.by_source["fallback"] / decisions, 4) if decisions else None,
            "latency_mean_s": round(mean, 2) if mean is not None else None,
            "latency_p95_s": round(p95(self.latencies), 2) if self.latencies else None,
            "tokens": {k.replace("_tokens", ""): self.tokens.get(k, 0) for k in TOKENS},
            "cost_usd": round(self.cost, 4) if self.cost is not None else None,
            "sessions": self.sessions,
            "rollovers": self.rollovers,
        }

    def line(self, label):
        s = self.summary()
        src = s["by_source"]
        bits = [f"{s['decisions']} decisions: {src['backend']} by {label}, {src['rule']} by rules, "
                f"{src['auto']} automatic, {src['fallback']} fallbacks"]
        if src["pilot"]:
            bits[0] += f", {src['pilot']} by the pilot"
        if s["latency_mean_s"] is not None:
            bits.append(f"latency mean {s['latency_mean_s']}s / p95 {s['latency_p95_s']}s")
        if s["replies"]:
            bits.append(f"invalid replies {s['invalid_replies']}/{s['replies']}")
        tokens = s["tokens"]
        if any(tokens.values()):
            bits.append(f"tokens in {tokens['input']} (+{tokens['cache_read']} cached, {tokens['cache_write']} "
                        f"cache writes) / out {tokens['output']}")
        if s["cost_usd"] is not None:
            bits.append(f"cost ${s['cost_usd']:.4f}")
        return "; ".join(bits) + "."
