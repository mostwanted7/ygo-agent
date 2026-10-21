"""Backend type "random": a uniformly random legal reply to every decision. Seedable (`seed = N` in the profile)
for reproducible benchmark baselines."""

import random

from ..agent.validate import validate
from .base import Backend
from .heuristic import PolicySession, first_legal, lowest_bit, sum_pick


class RandomPolicy:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.why = "random"

    def choose(self, d):
        try:
            choice = self._choose(d)
        except (KeyError, TypeError, ValueError, IndexError):
            choice = None
        if choice is None or validate(d, choice) is not None:
            choice = first_legal(d)
        return choice

    def _choose(self, d):
        rng, kind, opts = self.rng, d["kind"], d.get("options", [])
        n = len(opts)
        if kind in ("effect_yn", "yesno", "go_first"):
            return [rng.randrange(2)]
        if kind == "chain":
            k = rng.randrange(n + (0 if d.get("forced") else 1))
            return [] if k == n else [k]
        if kind in ("select_card", "tribute"):
            lo, hi = d["min"], min(d["max"], n)
            sizes = list(range(lo, hi + 1)) + ([0] if lo > 0 and d.get("cancelable") else [])
            return sorted(rng.sample(range(n), rng.choice(sizes)))
        if kind == "select_unselect":
            stop = d.get("finishable") or d.get("cancelable")
            k = rng.randrange(n + (1 if stop else 0)) if n else 0
            return [] if k == n else [k]
        if kind == "select_sum":
            weights = {i: rng.random() for i in range(n)}
            return sum_pick(d, lambda i: 1 + int(1000 * weights[i]))
        if kind in ("announce_attrib", "announce_race"):
            return sorted(rng.sample(range(n), min(d.get("count", 1), n)))
        if kind == "place":
            free = [1 << b for b in range(32) if d.get("available", 0) >> b & 1]
            return [rng.choice(free)] if free else [lowest_bit(d.get("available", 0))]
        return [rng.randrange(n)] if n else []


class RandomBackend(Backend):
    TYPE = "random"

    def __init__(self, profile, db=None):
        super().__init__(profile, db)
        seed = profile.get("seed")
        self.policy = RandomPolicy(None if seed in (None, "") else int(seed))

    def open_session(self, system_prompt, schema):
        return PolicySession(self.policy)
