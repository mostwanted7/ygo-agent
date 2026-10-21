"""Core prompts as decision-protocol decisions (docs/decision-protocol.md), and choices back into core responses.

    d = build(prompt, view)     # view: the seat's NativeView, fed with its message stream
    d.kind                      # "idle", "chain", ... or None: answered without asking (empty chain window, ...)
    d.fields                    # the kind's fields and options, as BrainBridge sends them (no t/id/state)
    d.encode([2])               # the agent's choice → core response bytes (ValueError if it can't be sent)
    d.decode(data)              # core response bytes → the choice in option indices (coach mode, parity tests)

Options are listed in BrainBridge's order with BrainBridge's conventions, so a saved choice means the same thing
here as in a WindBot game. Prompts the fork answers by itself (an empty or single forced chain window, a lone
position, yes/no 1989, rock-paper-scissors, counter removal, card and chain sorting) are answered here the same way
and never reach the agent.
"""

from __future__ import annotations

import random
import struct
from collections.abc import Callable
from dataclasses import dataclass, field

from ..core.constants import (LOCATION_MZONE, LOCATION_SZONE, POS_FACEDOWN_ATTACK, POS_FACEDOWN_DEFENSE,
                              POS_FACEUP_ATTACK, POS_FACEUP_DEFENSE)
from . import messages as M
from .announce import declarable_codes
from .messages import BattleAction, IdleAction, decode_cards

FIELD_ZONE, PENDULUM_ZONE = 0x100, 0x200
POSITIONS = (POS_FACEUP_ATTACK, POS_FACEDOWN_ATTACK, POS_FACEUP_DEFENSE, POS_FACEDOWN_DEFENSE)
TRIGGER_DESC = 221        # the generic "trigger effect" description; the bridge reports it as 0 (chain) / -1 (yes-no)
YESNO_AUTO = 1989         # a yes/no WindBot always answers yes without asking
ZONE_ORDER = (2, 1, 3, 0, 4, 6, 5)   # WindBot's zone preference among the allowed ones (middle first)
# SELECT_PLACE: the first group with a free zone is offered (WindBot GameBehavior.OnSelectPlace); bits of ~flag.
# (local player, location, test mask, shift, width)
_PLACE = ((0, LOCATION_MZONE, 0x7F, 0, 0x7F), (0, LOCATION_SZONE, 0x1F00, 8, 0x1F), (0, FIELD_ZONE, 0x2000, 0, 0),
          (0, PENDULUM_ZONE, 0xC000, 14, 0x3), (1, LOCATION_MZONE, 0x7F0000, 16, 0x7F),
          (1, LOCATION_SZONE, 0x1F000000, 24, 0x1F), (1, FIELD_ZONE, 0x20000000, 0, 0),
          (1, PENDULUM_ZONE, 0xC0000000, 30, 0x3))
_DISFIELD = (_PLACE[4], _PLACE[5], _PLACE[0], _PLACE[1], _PLACE[2], _PLACE[3], _PLACE[6], _PLACE[7])


class ChoiceError(ValueError):
    pass


@dataclass
class Decision:
    kind: str | None
    fields: dict = field(default_factory=dict)
    encoder: Callable[[list], bytes] | None = None
    decoder: Callable[[bytes], list | None] | None = None
    auto: bytes | None = None     # the response when kind is None
    note: str = ""                # why it was answered without asking

    def encode(self, choice: list) -> bytes:
        if self.kind is None:
            return self.auto
        if not isinstance(choice, list) or not all(isinstance(k, int) for k in choice):
            raise ChoiceError(f"not a list of integers: {choice!r}")
        return self.encoder(choice)

    def decode(self, data: bytes) -> list | None:
        """The choice (option indices; a code for announce_card, a zone bit for place) a response stands for, or
        None if it has no equivalent in the schema (e.g. unselecting a card)."""
        if self.decoder is None:
            return None
        try:
            return self.decoder(data)
        except (ValueError, IndexError, struct.error):
            return None


def _i32(data: bytes) -> int:
    return struct.unpack_from("<i", data.ljust(4, b"\0"))[0]


def _one(choice: list, n: int) -> int:
    if len(choice) != 1 or not 0 <= choice[0] < n:
        raise ChoiceError(f"need one index in 0..{n - 1}, got {choice}")
    return choice[0]


def _auto(response: bytes, note: str) -> Decision:
    return Decision(None, auto=response, note=note)


# --- main and battle phase ---------------------------------------------------------------------------------------

def _actions(options: list, actions: list, respond) -> tuple[Callable, Callable]:
    def encode(choice):
        return respond(*actions[_one(choice, len(actions))])

    def decode(data):
        v = _i32(data)
        key = (v & 0xFFFF, v >> 16)
        for k, (action, index) in enumerate(actions):
            if (int(action), index) == key:
                return [k]
        return None
    return encode, decode


def _idle(p: M.SelectIdleCmd, view) -> Decision:
    options, actions = [], []
    for i, a in enumerate(p.activatable):
        options.append({"a": "activate", "card": view.option_card(a), "desc": a.description})
        actions.append((IdleAction.ACTIVATE, i))
    for name, cards, action in (("summon", p.summonable, IdleAction.SUMMON),
                                ("spsummon", p.special_summonable, IdleAction.SPSUMMON),
                                ("set_monster", p.monster_settable, IdleAction.MSET),
                                ("set_spell", p.spell_settable, IdleAction.SSET),
                                ("reposition", p.repositionable, IdleAction.REPOSITION)):
        for i, c in enumerate(cards):
            options.append({"a": name, "card": view.option_card(c)})
            actions.append((action, i))
    if p.can_battle_phase:
        options.append({"a": "to_battle"})
        actions.append((IdleAction.BATTLE, 0))
    if p.can_end_phase:
        options.append({"a": "to_end"})
        actions.append((IdleAction.END, 0))
    enc, dec = _actions(options, actions, p.respond)
    return Decision("idle", {"options": options}, enc, dec)


def _battle(p: M.SelectBattleCmd, view) -> Decision:
    options, actions = [], []
    for i, a in enumerate(p.activatable):
        options.append({"a": "activate", "card": view.option_card(a), "desc": a.description})
        actions.append((BattleAction.ACTIVATE, i))
    for i, a in enumerate(p.attackable):
        options.append({"a": "attack", "card": view.option_card(a), "direct": a.direct_attack})
        actions.append((BattleAction.ATTACK, i))
    if p.can_main2:
        options.append({"a": "to_main2"})
        actions.append((BattleAction.MAIN2, 0))
    if p.can_end_phase:
        options.append({"a": "to_end"})
        actions.append((BattleAction.END, 0))
    enc, dec = _actions(options, actions, p.respond)
    return Decision("battle", {"options": options}, enc, dec)


# --- responses and questions --------------------------------------------------------------------------------------

def _chain(p: M.SelectChain, view) -> Decision:
    if not p.chains:
        return _auto(p.respond(None), "no effect can be activated")
    if len(p.chains) == 1 and p.forced:
        return _auto(p.respond(0), "a single mandatory activation")
    options = [{"a": "activate", "card": view.option_card(c),
                "desc": 0 if c.description == TRIGGER_DESC else c.description} for c in p.chains]

    def encode(choice):
        if not choice:
            if p.forced:
                raise ChoiceError("this activation is mandatory")
            return p.respond(None)
        return p.respond(_one(choice, len(options)))

    def decode(data):
        v = _i32(data)
        return [] if v < 0 else [v]
    return Decision("chain", {"options": options, "forced": p.forced}, encode, decode)


def _yes_no(respond) -> tuple[Callable, Callable]:
    def encode(choice):
        if choice not in ([0], [1]):
            raise ChoiceError("reply [1] or [0]")
        return respond(choice == [1])
    return encode, lambda data: [1 if _i32(data) == 1 else 0]


def _effect_yn(p: M.SelectEffectYn, view) -> Decision:
    desc = -1 if p.description in (0, TRIGGER_DESC) else p.description
    enc, dec = _yes_no(p.respond)
    return Decision("effect_yn", {"card": view.option_card(p.card), "desc": desc}, enc, dec)


def _yesno(p: M.SelectYesNo, view) -> Decision:
    if p.description == YESNO_AUTO:
        return _auto(p.respond(True), f"yes/no {YESNO_AUTO} is always answered yes")
    enc, dec = _yes_no(p.respond)
    return Decision("yesno", {"desc": p.description}, enc, dec)


def _option(p: M.SelectOption, view) -> Decision:
    options = list(p.options)
    return Decision("option", {"options": options}, lambda c: p.respond(_one(c, len(options))),
                    lambda data: [_i32(data)])


def _position(p: M.SelectPosition, view) -> Decision:
    options = [x for x in POSITIONS if p.positions & x]
    if len(options) == 1:
        return _auto(p.respond(options[0]), "a single position")

    def decode(data):
        pos = _i32(data)
        return [options.index(pos)] if pos in options else None
    return Decision("position", {"card_id": p.code, "options": options},
                    lambda c: p.respond(options[_one(c, len(options))]), decode)


# --- card selections ------------------------------------------------------------------------------------------------

def _cards(kind: str, p, view) -> Decision:
    options = [view.option_card(c) for c in p.cards]
    hint, view.hint = view.hint, 0

    def encode(choice):
        if not choice and p.cancelable:
            return p.respond(None)
        if len(set(choice)) != len(choice) or any(not 0 <= k < len(options) for k in choice):
            raise ChoiceError(f"indices must be distinct and in 0..{len(options) - 1}")
        return p.respond(list(choice))

    def decode(data):
        idx = decode_cards(data, len(options))
        return [] if idx is None else list(idx)
    return Decision(kind, {"options": options, "min": p.min, "max": p.max, "hint": hint,
                           "cancelable": p.cancelable}, encode, decode)


def _unselect(p: M.SelectUnselectCard, view) -> Decision:
    options = [view.option_card(c) for c in p.selectable]
    selected = [view.option_card(c) for c in p.selected]
    cancelable = p.cancelable or p.finishable

    def encode(choice):
        if not choice:
            if not cancelable:
                raise ChoiceError("a card must be picked")
            return p.respond(None)
        return p.respond(_one(choice, len(options)))

    def decode(data):
        r = M.Reader(data)
        if r.i32() == -1:
            return []
        k = r.i32()
        return [k] if 0 <= k < len(options) else None  # unselecting an already picked card isn't in the schema
    # WindBot keeps the selection hint for every step of an unselect selection (the agent's multi-picks rely on it).
    return Decision("select_unselect", {"options": options, "selected": selected, "min": p.min, "max": p.max,
                                        "hint": view.hint, "finishable": p.finishable, "cancelable": cancelable},
                    encode, decode)


def _sum_values(param: int) -> tuple[int, int]:
    """WindBot's OpParam1/OpParam2: the two values, the smaller first when there are two."""
    lo, hi = param & 0xFFFF, param >> 16
    return (hi, lo) if hi > 0 and lo > hi else (lo, hi)


def sum_ok(p: M.SelectSum, indices: list[int]) -> bool:
    """The core's own SELECT_SUM check (playerop.cpp)."""
    cards = list(p.must_select) + [p.selectable[i] for i in indices]
    params = [c.param for c in cards]
    if not p.at_least:
        if not p.min <= len(indices) <= p.max:
            return False

        def exact(i, acc):
            if acc == 0 or i == len(params):
                return False
            o1, o2 = params[i] & 0xFFFF, params[i] >> 16
            if i == len(params) - 1:
                return acc in (o1, o2)
            return (acc > o1 and exact(i + 1, acc - o1)) or (o2 > 0 and acc > o2 and exact(i + 1, acc - o2))
        return exact(0, p.sum)
    total = mx = 0
    mn = 1 << 31
    for param in params:
        o1, o2 = param & 0xFFFF, param >> 16
        ms = o2 if o2 and o2 < o1 else o1
        total += ms
        mx += max(o1, o2)
        mn = min(mn, ms)
    return mx >= p.sum and total - mn < p.sum


def _sum(p: M.SelectSum, view) -> Decision:
    options = []
    for c in p.selectable:
        d = view.option_card(c)
        d["v1"], d["v2"] = _sum_values(c.param)
        options.append(d)
    target = p.sum - sum(_sum_values(c.param)[0] for c in p.must_select)
    hint, view.hint = view.hint, 0

    def encode(choice):
        if len(set(choice)) != len(choice) or any(not 0 <= k < len(options) for k in choice):
            raise ChoiceError("indices must be distinct and in range")
        if not sum_ok(p, choice):
            raise ChoiceError("the engine would reject that sum")
        return p.respond(list(choice))
    return Decision("select_sum", {"options": options, "sum": target, "min": p.min,
                                   "max": p.max if p.max > 0 else 99, "hint": hint, "exact": not p.at_least},
                    encode, lambda data: list(decode_cards(data, len(options)) or []))


# --- zones ----------------------------------------------------------------------------------------------------------

def place_group(flag: int, disfield: bool = False) -> tuple[int, int, int]:
    """(local player, location, available bits) of the zone group a SELECT_PLACE/DISFIELD prompt is offered as."""
    free = ~flag & 0xFFFFFFFF
    for player, location, test, shift, width in (_DISFIELD if disfield else _PLACE):
        if free & test or test == 0xC0000000:
            if location == FIELD_ZONE:
                return player, location, 0x20
            return player, location, (free >> shift) & width
    return 0, LOCATION_MZONE, 0


def _zone_seq(location: int, bits: int) -> int | None:
    if location in (LOCATION_MZONE, LOCATION_SZONE):
        return next((z for z in ZONE_ORDER if bits >> z & 1), None)
    seq = None  # WindBot's field/pendulum logic: the last matching test wins
    if bits & 0x20:
        seq = 5
    if bits & 0x1:
        seq = 6
    if bits & 0x2:
        seq = 7
    return seq


def _place(p, view, disfield: bool) -> Decision:
    player, location, available = place_group(p.flag, disfield)
    card_id, view.hint = view.hint, 0
    core_player = view.team if player == 0 else 1 - view.team
    loc_byte = location if location in (LOCATION_MZONE, LOCATION_SZONE) else LOCATION_SZONE

    def encode(choice):
        if len(choice) != 1:
            raise ChoiceError("reply [mask]")
        bits = available & choice[0] or available
        seq = _zone_seq(location, bits)
        if seq is None:
            raise ChoiceError("no free zone in that mask")
        zones = [(core_player, loc_byte, seq)]
        # More than one zone wanted (rare): add the other free ones in the order the engine offers them.
        for z in (zone for zone in p.zones if zone != zones[0]):
            if len(zones) >= max(p.count, 1):
                break
            zones.append(z)
        return p.respond(zones)

    def decode(data):
        if len(data) < 3:
            return None
        pl, loc, seq = data[0], data[1], data[2]
        if pl != core_player:
            return None
        if location in (LOCATION_MZONE, LOCATION_SZONE):
            return [1 << seq] if loc == location else None
        if location == FIELD_ZONE:
            return [0x20] if (loc, seq) == (LOCATION_SZONE, 5) else None
        return [1 << (seq - 6)] if loc == LOCATION_SZONE and seq in (6, 7) else None
    return Decision("place", {"card_id": card_id, "player": player, "location": location,
                              "available": available}, encode, decode)


# --- declarations ---------------------------------------------------------------------------------------------------

def _announce_card(p: M.AnnounceCard, view) -> Decision:
    options = declarable_codes(view.cards, p.opcodes) if view.cards is not None else []
    allowed = set(options)

    def encode(choice):
        if len(choice) != 1:
            raise ChoiceError("reply [code]")
        code = choice[0]
        if code not in allowed and 0 <= code < len(options):
            code = options[code]  # an index (from a policy) instead of the code
        if code not in allowed:
            raise ChoiceError(f"{code} can't be declared here")
        return p.respond(code)
    return Decision("announce_card", {"options": options}, encode, lambda data: [_i32(data)])


def _announce_number(p: M.AnnounceNumber, view) -> Decision:
    options = list(p.options)
    return Decision("announce_number", {"options": options}, lambda c: p.respond(_one(c, len(options))),
                    lambda data: [_i32(data)])


def _flags(kind: str, p, width: int) -> Decision:
    options = [1 << b for b in range(width) if p.available >> b & 1]

    def encode(choice):
        if len(set(choice)) != p.count or len(choice) != p.count or any(not 0 <= k < len(options) for k in choice):
            raise ChoiceError(f"choose exactly {p.count} distinct options")
        return p.respond(sum(options[k] for k in choice))

    def decode(data):
        mask = int.from_bytes(data[:8 if width > 32 else 4].ljust(8, b"\0"), "little")
        return [k for k, bit in enumerate(options) if mask & bit]
    return Decision(kind, {"options": options, "count": p.count}, encode, decode)


# --- prompts the fork answers itself --------------------------------------------------------------------------------

def _counter(p: M.SelectCounter, view) -> Decision:
    """WindBot's default: take the counters from the cards in the order offered."""
    left, used = p.count, []
    for c in p.cards:
        take = min(left, c.counters)
        used.append(take)
        left -= take
    return _auto(p.respond(used), "counters are removed from the first cards offered")


_BUILDERS = {
    M.SelectIdleCmd: _idle,
    M.SelectBattleCmd: _battle,
    M.SelectChain: _chain,
    M.SelectEffectYn: _effect_yn,
    M.SelectYesNo: _yesno,
    M.SelectOption: _option,
    M.SelectPosition: _position,
    M.SelectCard: lambda p, v: _cards("select_card", p, v),
    M.SelectTribute: lambda p, v: _cards("tribute", p, v),
    M.SelectUnselectCard: _unselect,
    M.SelectSum: _sum,
    M.SelectPlace: lambda p, v: _place(p, v, False),
    M.SelectDisfield: lambda p, v: _place(p, v, True),
    M.AnnounceCard: _announce_card,
    M.AnnounceNumber: _announce_number,
    M.AnnounceAttrib: lambda p, v: _flags("announce_attrib", p, 7),
    M.AnnounceRace: lambda p, v: _flags("announce_race", p, 64),
    M.SelectCounter: _counter,
    M.SortCard: lambda p, v: _auto(p.respond(list(range(len(p.cards)))), "cards keep their order"),
    M.SortChain: lambda p, v: _auto(p.respond(None), "the chain keeps its default order"),
    M.RockPaperScissors: lambda p, v: _auto(p.respond(random.randint(1, 3)), "a random hand"),
}


def build(prompt: M.Prompt, view) -> Decision:
    """The decision for one core prompt, as the seat with this NativeView sees it."""
    builder = _BUILDERS.get(type(prompt))
    if builder is None:
        raise ValueError(f"no decision for {prompt.name}")
    return builder(prompt, view)
