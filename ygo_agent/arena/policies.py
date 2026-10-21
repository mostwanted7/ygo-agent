"""Baseline in-process policies: `random` (any legal answer) and `simple` (summon, attack, pass on optional
chains). Both answer every prompt type with a response the core accepts, which makes them good stress tests."""

from __future__ import annotations

import itertools
import random

from ..core.constants import POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK, POS_FACEUP_DEFENSE, POS_FACEDOWN_ATTACK
from .announce import declarable_codes
from .messages import (AnnounceAttrib, AnnounceCard, AnnounceNumber, AnnounceRace, BattleAction, IdleAction,
                       Prompt, RockPaperScissors, SelectBattleCmd, SelectCard, SelectChain, SelectCounter,
                       SelectDisfield, SelectEffectYn, SelectIdleCmd, SelectOption, SelectPlace, SelectPosition,
                       SelectSum, SelectTribute, SelectUnselectCard, SelectYesNo, SortCard, SortChain)
from .seats import SeatView

_POSITIONS = (POS_FACEUP_ATTACK, POS_FACEUP_DEFENSE, POS_FACEDOWN_DEFENSE, POS_FACEDOWN_ATTACK)


def _bits(mask: int) -> list[int]:
    return [1 << i for i in range(64) if mask >> i & 1]


def sum_solution(p: SelectSum, rng: random.Random | None = None, tries: int = 2000) -> list[int]:
    """Indices into `p.selectable` that satisfy the core's SELECT_SUM check (playerop.cpp)."""
    must = [c.values for c in p.must_select]
    opts = list(range(len(p.selectable)))
    if rng:
        rng.shuffle(opts)

    def exact(vals: list[tuple[int, ...]], target: int) -> bool:
        if not vals:
            return target == 0
        head, rest = vals[0], vals[1:]
        return any(v <= target and exact(rest, target - v) for v in head)

    def ok(combo) -> bool:
        vals = must + [p.selectable[i].values for i in combo]
        if not p.at_least:
            return p.min <= len(combo) <= p.max and exact(vals, p.sum)
        mins = [min(v) for v in vals]
        return sum(max(v) for v in vals) >= p.sum and sum(mins) - min(mins, default=0) < p.sum
    lo = max(p.min, 0) if not p.at_least else 0
    hi = len(opts) if p.at_least else min(p.max, len(opts))
    n = 0
    for k in range(max(lo, 1) if not must else lo, hi + 1):
        for combo in itertools.combinations(opts, k):
            n += 1
            if ok(combo):
                return sorted(combo)
            if n > tries:
                return sorted(opts[:max(p.min, 1)])
    return sorted(opts[:max(p.min, 1)])


class RandomPolicy:
    """A uniformly random legal answer to every prompt (biased away from ending turns instantly)."""

    def __init__(self, seed: int | None = None, pass_rate: float = 0.5):
        self.rng = random.Random(seed)
        self.pass_rate = pass_rate
        self._announce_cache: dict[tuple, list[int]] = {}

    def __call__(self, p: Prompt, view: SeatView) -> bytes:
        rng = self.rng
        if isinstance(p, SelectIdleCmd):
            options = [(IdleAction.SUMMON, i) for i in range(len(p.summonable))]
            options += [(IdleAction.SPSUMMON, i) for i in range(len(p.special_summonable))]
            options += [(IdleAction.REPOSITION, i) for i in range(len(p.repositionable))]
            options += [(IdleAction.MSET, i) for i in range(len(p.monster_settable))]
            options += [(IdleAction.SSET, i) for i in range(len(p.spell_settable))]
            options += [(IdleAction.ACTIVATE, i) for i in range(len(p.activatable))]
            ends = ([(IdleAction.BATTLE, 0)] if p.can_battle_phase else []) + \
                ([(IdleAction.END, 0)] if p.can_end_phase else [])
            if not options or (ends and rng.random() < 0.25):
                options = ends or options
            return p.respond(*rng.choice(options))
        if isinstance(p, SelectBattleCmd):
            options = [(BattleAction.ATTACK, i) for i in range(len(p.attackable))]
            options += [(BattleAction.ACTIVATE, i) for i in range(len(p.activatable))]
            ends = ([(BattleAction.MAIN2, 0)] if p.can_main2 else []) + \
                ([(BattleAction.END, 0)] if p.can_end_phase else [])
            if not options or (ends and rng.random() < 0.3):
                options = ends or options
            return p.respond(*rng.choice(options))
        if isinstance(p, SelectChain):
            if not p.chains or (not p.forced and rng.random() < self.pass_rate):
                return p.respond(None)
            return p.respond(rng.randrange(len(p.chains)))
        if isinstance(p, (SelectEffectYn, SelectYesNo)):
            return p.respond(rng.random() < 0.5)
        if isinstance(p, SelectOption):
            return p.respond(rng.randrange(len(p.options)))
        if isinstance(p, SelectCard):
            n = len(p.cards)
            k = rng.randint(max(p.min, 1) if p.min else (0 if p.cancelable else 1), min(p.max, n))
            if k == 0:
                return p.respond(None)
            return p.respond(sorted(rng.sample(range(n), k)))
        if isinstance(p, SelectTribute):
            idx = list(range(len(p.cards)))
            rng.shuffle(idx)
            chosen, total = [], 0
            for i in idx:
                if total >= p.min:
                    break
                chosen.append(i)
                total += p.cards[i].release_param
            return p.respond(sorted(chosen))
        if isinstance(p, SelectUnselectCard):
            if p.finishable and (not p.selectable or rng.random() < 0.5):
                return p.respond(None)
            if p.selectable:
                return p.respond(rng.randrange(len(p.selectable)))
            if p.cancelable:
                return p.respond(None)
            return p.respond(len(p.selectable) + rng.randrange(len(p.selected)))
        if isinstance(p, (SelectPlace, SelectDisfield)):
            zones = p.zones
            rng.shuffle(zones)
            return p.respond(zones[:max(p.count, 1)])
        if isinstance(p, SelectPosition):
            return p.respond(rng.choice([x for x in _POSITIONS if p.positions & x]))
        if isinstance(p, SelectCounter):
            left, counts = p.count, [0] * len(p.cards)
            order = list(range(len(p.cards)))
            rng.shuffle(order)
            for i in order:
                take = min(left, p.cards[i].counters)
                counts[i], left = take, left - take
            return p.respond(counts)
        if isinstance(p, SelectSum):
            return p.respond(sum_solution(p, rng))
        if isinstance(p, (SortCard, SortChain)):
            if rng.random() < 0.5:
                return p.respond(None)
            order = list(range(len(p.cards)))
            rng.shuffle(order)
            return p.respond(order)
        if isinstance(p, RockPaperScissors):
            return p.respond(rng.randint(1, 3))
        if isinstance(p, AnnounceRace):
            return p.respond(sum(rng.sample(_bits(p.available), p.count)))
        if isinstance(p, AnnounceAttrib):
            return p.respond(sum(rng.sample(_bits(p.available), p.count)))
        if isinstance(p, AnnounceCard):
            key = tuple(p.opcodes)
            if key not in self._announce_cache:
                self._announce_cache[key] = declarable_codes(view.cards, p.opcodes)
            codes = self._announce_cache[key]
            return p.respond(rng.choice(codes) if codes else 0)
        if isinstance(p, AnnounceNumber):
            return p.respond(rng.randrange(len(p.options)))
        raise ValueError(f"no policy for {p.name}")


class SimplePolicy(RandomPolicy):
    """Summon or activate when possible, attack with everything, decline optional chains."""

    def __init__(self, seed: int | None = None):
        super().__init__(seed, pass_rate=1.0)
        self._actions = 0

    def __call__(self, p: Prompt, view: SeatView) -> bytes:
        if isinstance(p, SelectIdleCmd):
            if p.special_summonable and self._actions < 8:
                self._actions += 1
                return p.respond(IdleAction.SPSUMMON, 0)
            if p.summonable:
                return p.respond(IdleAction.SUMMON, 0)
            if p.activatable and self._actions < 8:
                self._actions += 1
                return p.respond(IdleAction.ACTIVATE, self.rng.randrange(len(p.activatable)))
            if p.monster_settable:
                return p.respond(IdleAction.MSET, 0)
            self._actions = 0
            if p.can_battle_phase:
                return p.respond(IdleAction.BATTLE)
            return p.respond(IdleAction.END)
        if isinstance(p, SelectBattleCmd):
            if p.attackable:
                return p.respond(BattleAction.ATTACK, 0)
            return p.respond(BattleAction.END if p.can_end_phase else BattleAction.MAIN2)
        if isinstance(p, SelectChain):
            return p.respond(0 if p.forced and p.chains else None)
        if isinstance(p, (SelectEffectYn, SelectYesNo)):
            return p.respond(True)
        return super().__call__(p, view)


POLICIES = {"random": RandomPolicy, "simple": SimplePolicy}
