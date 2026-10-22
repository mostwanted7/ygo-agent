"""Every core message (ygopro-core 11.0) as a dataclass, response encoders/decoders for every prompt, and a
one-line rendering for logs.

    msg = decode(raw)                 # raw starts with the MSG_* byte, as the core and STOC_GAME_MSG carry it
    if isinstance(msg, SelectIdleCmd):
        data = msg.respond(IdleAction.ACTIVATE, 0)
    decode_response(msg, data)        # -> {"action": "activate", "index": 0}
    render(msg, cards)                # -> 'SELECT_IDLECMD p0: summon [..] activate [..] bp ep'

Layouts were checked against the core's writers (playerop.cpp, operations.cpp, libduel.cpp, field.cpp) and
EDOPro's reader (duelclient.cpp ClientAnalyze).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field, fields
from enum import IntEnum
from typing import ClassVar

from ..core.constants import (LOCATION_MZONE, LOCATION_NAMES, LOCATION_SZONE, MSG_NAMES,
                              PHASE_NAMES, POSITION_NAMES, WIN_REASON_NAMES, Msg)
from .buffer import BufferUnderrun, LocInfo, Reader, Writer
from .query import CardQuery, FieldState, parse_card, parse_field, parse_location

_REGISTRY: dict[int, type["Message"]] = {}


class MessageError(ValueError):
    pass


def message(msg_type: int):
    def deco(cls):
        cls.TYPE = int(msg_type)
        _REGISTRY[int(msg_type)] = cls
        return cls
    return deco


@dataclass(slots=True)
class Message:
    TYPE: ClassVar[int] = 0
    raw: bytes = field(default=b"", repr=False, compare=False, kw_only=True)

    @property
    def type(self) -> int:
        return self.TYPE

    @property
    def name(self) -> str:
        return MSG_NAMES.get(self.type, f"MSG_{self.type}")

    @classmethod
    def read(cls, r: Reader) -> "Message":
        return cls()


@dataclass(slots=True)
class Prompt(Message):
    """A message that waits for a response from `player`."""

    def decode_response(self, data: bytes) -> dict:
        return {"raw": data.hex()}


# --- shared card references --------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CardRef:
    code: int
    controller: int
    location: int
    sequence: int
    position: int = 0

    @property
    def loc(self) -> LocInfo:
        return LocInfo(self.controller, self.location, self.sequence, self.position)


@dataclass(frozen=True, slots=True)
class Activatable(CardRef):
    description: int = 0
    client_mode: int = 0  # EFFECT_CLIENT_MODE_*: 0 normal, 1 resolve, 2 reset


@dataclass(frozen=True, slots=True)
class Attacker(CardRef):
    direct_attack: bool = False


@dataclass(frozen=True, slots=True)
class TributeCard(CardRef):
    release_param: int = 1  # how many tributes this card counts as


@dataclass(frozen=True, slots=True)
class CounterCard(CardRef):
    counters: int = 0


@dataclass(frozen=True, slots=True)
class SumCard(CardRef):
    param: int = 0  # level(s) it can count as: low 16 bits, and an alternative in the high 16 bits

    @property
    def values(self) -> tuple[int, ...]:
        lo, hi = self.param & 0xFFFF, self.param >> 16
        return (lo, hi) if hi else (lo,)


def _ref_loc(r: Reader) -> CardRef:
    code = r.u32()
    c, l, s, p = r.u8(), r.u8(), r.u32(), r.u32()
    return CardRef(code, c, l, s, p)


def _ref_seq32(r: Reader) -> CardRef:
    return CardRef(r.u32(), r.u8(), r.u8(), r.u32())


def _ref_seq8(r: Reader) -> CardRef:
    return CardRef(r.u32(), r.u8(), r.u8(), r.u8())


def _activatable(r: Reader, loc_info: bool) -> Activatable:
    code = r.u32()
    if loc_info:
        c, l, s, p = r.u8(), r.u8(), r.u32(), r.u32()
    else:
        c, l, s, p = r.u8(), r.u8(), r.u32(), 0
    return Activatable(code, c, l, s, p, r.u64(), r.u8())


def _list(r: Reader, item) -> list:
    return [item(r) for _ in range(r.u32())]


# --- response encoding helpers -----------------------------------------------------------------------------

def encode_int(value: int) -> bytes:
    return struct.pack("<i", value)


def encode_cards(indices: list[int] | None) -> bytes:
    """Card-list response (parse_response_cards type 0); None cancels (-1)."""
    if indices is None:
        return encode_int(-1)
    w = Writer().i32(0).u32(len(indices))
    for i in indices:
        w.u32(i)
    return w.getvalue()


def decode_cards(data: bytes, count: int) -> list[int] | None:
    """Any of the four card-list encodings (EDOPro's client picks the most compact); None = canceled."""
    r = Reader(data)
    kind = r.i32()
    if kind == -1:
        return None
    if kind == 3:
        bits = int.from_bytes(data[4:], "little")
        return [i for i in range(count) if bits >> i & 1]
    n = r.u32()
    if kind == 0:
        return [r.u32() for _ in range(n)]
    if kind == 1:
        return [r.u16() for _ in range(n)]
    if kind == 2:
        return [r.u8() for _ in range(n)]
    raise MessageError(f"unknown card response type {kind}")


def _i32(data: bytes) -> int:
    return struct.unpack_from("<i", data.ljust(4, b"\0"))[0]


# --- prompts -----------------------------------------------------------------------------------------------

class BattleAction(IntEnum):
    ACTIVATE = 0
    ATTACK = 1
    MAIN2 = 2
    END = 3


class IdleAction(IntEnum):
    SUMMON = 0
    SPSUMMON = 1
    REPOSITION = 2
    MSET = 3
    SSET = 4
    ACTIVATE = 5
    BATTLE = 6
    END = 7
    SHUFFLE = 8


@message(Msg.SELECT_BATTLECMD)
@dataclass(slots=True)
class SelectBattleCmd(Prompt):
    player: int
    activatable: list[Activatable]
    attackable: list[Attacker]
    can_main2: bool
    can_end_phase: bool

    @classmethod
    def read(cls, r):
        player = r.u8()
        act = _list(r, lambda r: _activatable(r, False))
        atk = _list(r, lambda r: Attacker(r.u32(), r.u8(), r.u8(), r.u8(), 0, bool(r.u8())))
        return cls(player, act, atk, bool(r.u8()), bool(r.u8()))

    @staticmethod
    def respond(action: BattleAction, index: int = 0) -> bytes:
        return encode_int(index << 16 | int(action))

    def decode_response(self, data):
        v = _i32(data)
        return {"action": BattleAction(v & 0xFFFF).name.lower(), "index": v >> 16}


@message(Msg.SELECT_IDLECMD)
@dataclass(slots=True)
class SelectIdleCmd(Prompt):
    player: int
    summonable: list[CardRef]
    special_summonable: list[CardRef]
    repositionable: list[CardRef]
    monster_settable: list[CardRef]
    spell_settable: list[CardRef]
    activatable: list[Activatable]
    can_battle_phase: bool
    can_end_phase: bool
    can_shuffle: bool

    @classmethod
    def read(cls, r):
        player = r.u8()
        summon, spsummon = _list(r, _ref_seq32), _list(r, _ref_seq32)
        repos = _list(r, _ref_seq8)
        mset, sset = _list(r, _ref_seq32), _list(r, _ref_seq32)
        act = _list(r, lambda r: _activatable(r, False))
        return cls(player, summon, spsummon, repos, mset, sset, act, bool(r.u8()), bool(r.u8()), bool(r.u8()))

    @staticmethod
    def respond(action: IdleAction, index: int = 0) -> bytes:
        return encode_int(index << 16 | int(action))

    def decode_response(self, data):
        v = _i32(data)
        return {"action": IdleAction(v & 0xFFFF).name.lower(), "index": v >> 16}


@message(Msg.SELECT_EFFECTYN)
@dataclass(slots=True)
class SelectEffectYn(Prompt):
    player: int
    card: CardRef
    description: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), _ref_loc(r), r.u64())

    @staticmethod
    def respond(yes: bool) -> bytes:
        return encode_int(1 if yes else 0)

    def decode_response(self, data):
        return {"yes": _i32(data) == 1}


@message(Msg.SELECT_YESNO)
@dataclass(slots=True)
class SelectYesNo(Prompt):
    player: int
    description: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u64())

    @staticmethod
    def respond(yes: bool) -> bytes:
        return encode_int(1 if yes else 0)

    def decode_response(self, data):
        return {"yes": _i32(data) == 1}


@message(Msg.SELECT_OPTION)
@dataclass(slots=True)
class SelectOption(Prompt):
    player: int
    options: list[int]  # effect descriptions

    @classmethod
    def read(cls, r):
        player, n = r.u8(), r.u8()
        return cls(player, [r.u64() for _ in range(n)])

    @staticmethod
    def respond(index: int) -> bytes:
        return encode_int(index)

    def decode_response(self, data):
        return {"index": _i32(data)}


@message(Msg.SELECT_CARD)
@dataclass(slots=True)
class SelectCard(Prompt):
    player: int
    cancelable: bool
    min: int
    max: int
    cards: list[CardRef]  # code is 0 for cards the chooser doesn't control (host filtering)

    @classmethod
    def read(cls, r):
        return cls(r.u8(), bool(r.u8()), r.u32(), r.u32(), _list(r, _ref_loc))

    @staticmethod
    def respond(indices: list[int] | None) -> bytes:
        return encode_cards(indices)

    def decode_response(self, data):
        idx = decode_cards(data, len(self.cards))
        return {"cancel": True} if idx is None else {"indices": idx}


@message(Msg.SELECT_TRIBUTE)
@dataclass(slots=True)
class SelectTribute(Prompt):
    player: int
    cancelable: bool
    min: int
    max: int
    cards: list[TributeCard]

    @classmethod
    def read(cls, r):
        player, cancel, mn, mx = r.u8(), bool(r.u8()), r.u32(), r.u32()
        cards = _list(r, lambda r: TributeCard(r.u32(), r.u8(), r.u8(), r.u32(), 0, r.u8()))
        return cls(player, cancel, mn, mx, cards)

    @staticmethod
    def respond(indices: list[int] | None) -> bytes:
        return encode_cards(indices)

    def decode_response(self, data):
        idx = decode_cards(data, len(self.cards))
        return {"cancel": True} if idx is None else {"indices": idx}


@message(Msg.SELECT_UNSELECT_CARD)
@dataclass(slots=True)
class SelectUnselectCard(Prompt):
    player: int
    finishable: bool
    cancelable: bool
    min: int
    max: int
    selectable: list[CardRef]
    selected: list[CardRef]  # picking one of these unselects it; its response index is len(selectable) + i

    @classmethod
    def read(cls, r):
        return cls(r.u8(), bool(r.u8()), bool(r.u8()), r.u32(), r.u32(), _list(r, _ref_loc), _list(r, _ref_loc))

    @staticmethod
    def respond(index: int | None) -> bytes:
        """`None` finishes (or cancels) the selection."""
        return encode_int(-1) if index is None else Writer().i32(1).i32(index).getvalue()

    def decode_response(self, data):
        r = Reader(data)
        return {"finish": True} if r.i32() == -1 else {"index": r.i32()}


@message(Msg.SELECT_CHAIN)
@dataclass(slots=True)
class SelectChain(Prompt):
    player: int
    special_count: int
    forced: bool
    hint_timing: int
    hint_timing_other: int
    chains: list[Activatable]

    @classmethod
    def read(cls, r):
        player, spe, forced, h0, h1 = r.u8(), r.u8(), bool(r.u8()), r.u32(), r.u32()
        return cls(player, spe, forced, h0, h1, _list(r, lambda r: _activatable(r, True)))

    @staticmethod
    def respond(index: int | None) -> bytes:
        return encode_int(-1 if index is None else index)

    def decode_response(self, data):
        v = _i32(data)
        return {"index": None if v < 0 else v}


def zone_bits(flag: int, player: int, include_disabled: bool = False) -> list[tuple[int, int, int]]:
    """Zones a SELECT_PLACE/DISFIELD prompt offers, as (player, location, sequence). A set bit in `flag` means
    the zone is NOT selectable; bits 0-6 own monster zones, 8-15 own spell/trap zones, +16 the opponent's."""
    out = []
    for side, shift in ((player, 0), (1 - player, 16)):
        for seq in range(7):
            if include_disabled or not flag >> (shift + seq) & 1:
                out.append((side, LOCATION_MZONE, seq))
        for seq in range(8):
            if include_disabled or not flag >> (shift + 8 + seq) & 1:
                out.append((side, LOCATION_SZONE, seq))
    return out


@dataclass(slots=True)
class _PlaceBase(Prompt):
    player: int
    count: int
    flag: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8(), r.u32())

    @property
    def zones(self) -> list[tuple[int, int, int]]:
        return zone_bits(self.flag, self.player)

    @staticmethod
    def respond(zones: list[tuple[int, int, int]]) -> bytes:
        return b"".join(bytes((p, loc, seq)) for p, loc, seq in zones)

    def decode_response(self, data):
        return {"zones": [tuple(data[i:i + 3]) for i in range(0, len(data) - 2, 3)][: max(self.count, 1)]}


@message(Msg.SELECT_PLACE)
@dataclass(slots=True)
class SelectPlace(_PlaceBase):
    pass


@message(Msg.SELECT_DISFIELD)
@dataclass(slots=True)
class SelectDisfield(_PlaceBase):
    pass


@message(Msg.SELECT_POSITION)
@dataclass(slots=True)
class SelectPosition(Prompt):
    player: int
    code: int
    positions: int  # POS_* bits allowed

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u32(), r.u8())

    @staticmethod
    def respond(position: int) -> bytes:
        return encode_int(position)

    def decode_response(self, data):
        return {"position": _i32(data)}


@message(Msg.SELECT_COUNTER)
@dataclass(slots=True)
class SelectCounter(Prompt):
    player: int
    counter_type: int
    count: int
    cards: list[CounterCard]

    @classmethod
    def read(cls, r):
        player, ctype, count = r.u8(), r.u16(), r.u16()
        cards = _list(r, lambda r: CounterCard(r.u32(), r.u8(), r.u8(), r.u8(), 0, r.u16()))
        return cls(player, ctype, count, cards)

    @staticmethod
    def respond(counts: list[int]) -> bytes:
        return b"".join(struct.pack("<h", c) for c in counts)

    def decode_response(self, data):
        return {"counts": [struct.unpack_from("<h", data, 2 * i)[0] for i in range(len(data) // 2)]}


@message(Msg.SELECT_SUM)
@dataclass(slots=True)
class SelectSum(Prompt):
    player: int
    at_least: bool  # core "select_mode" 1: reach the sum (Ritual-style); 0: hit it exactly with min..max cards
    sum: int
    min: int
    max: int
    must_select: list[SumCard]
    selectable: list[SumCard]

    @classmethod
    def read(cls, r):
        player, mode, acc, mn, mx = r.u8(), r.u8(), r.u32(), r.u32(), r.u32()

        def item(r):
            ref = _ref_loc(r)
            return SumCard(ref.code, ref.controller, ref.location, ref.sequence, ref.position, r.u32())
        return cls(player, bool(mode), acc, mn, mx, _list(r, item), _list(r, item))

    @staticmethod
    def respond(indices: list[int]) -> bytes:
        """Indices into `selectable` (the must-select cards are implied)."""
        return encode_cards(indices)

    def decode_response(self, data):
        return {"indices": decode_cards(data, len(self.selectable)) or []}


@dataclass(slots=True)
class _SortBase(Prompt):
    player: int
    cards: list[CardRef]

    @classmethod
    def read(cls, r):
        player = r.u8()
        return cls(player, _list(r, lambda r: CardRef(r.u32(), r.u8(), r.u32(), r.u32())))

    @staticmethod
    def respond(order: list[int] | None) -> bytes:
        """`order[i]` is the new position of card i; None keeps the default order."""
        return b"\xff" if order is None else bytes(order)

    def decode_response(self, data):
        return {"order": None if data[:1] == b"\xff" else list(data[:len(self.cards)])}


@message(Msg.SORT_CARD)
@dataclass(slots=True)
class SortCard(_SortBase):
    pass


@message(Msg.SORT_CHAIN)
@dataclass(slots=True)
class SortChain(_SortBase):
    pass


@message(Msg.ROCK_PAPER_SCISSORS)
@dataclass(slots=True)
class RockPaperScissors(Prompt):
    player: int

    @classmethod
    def read(cls, r):
        return cls(r.u8())

    @staticmethod
    def respond(hand: int) -> bytes:
        """1 scissors, 2 rock, 3 paper (EDOPro's order)."""
        return encode_int(hand)

    def decode_response(self, data):
        return {"hand": _i32(data)}


@message(Msg.ANNOUNCE_RACE)
@dataclass(slots=True)
class AnnounceRace(Prompt):
    player: int
    count: int
    available: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8(), r.u64())

    @staticmethod
    def respond(mask: int) -> bytes:
        return struct.pack("<Q", mask)

    def decode_response(self, data):
        return {"races": struct.unpack_from("<Q", data.ljust(8, b"\0"))[0]}


@message(Msg.ANNOUNCE_ATTRIB)
@dataclass(slots=True)
class AnnounceAttrib(Prompt):
    player: int
    count: int
    available: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8(), r.u32())

    @staticmethod
    def respond(mask: int) -> bytes:
        return struct.pack("<I", mask)

    def decode_response(self, data):
        return {"attributes": struct.unpack_from("<I", data.ljust(4, b"\0"))[0]}


@message(Msg.ANNOUNCE_CARD)
@dataclass(slots=True)
class AnnounceCard(Prompt):
    player: int
    opcodes: list[int]  # a stack program; see announce.py for evaluating it

    @classmethod
    def read(cls, r):
        player, n = r.u8(), r.u8()
        return cls(player, [r.u64() for _ in range(n)])

    @staticmethod
    def respond(code: int) -> bytes:
        return encode_int(code)

    def decode_response(self, data):
        return {"code": _i32(data)}


@message(Msg.ANNOUNCE_NUMBER)
@dataclass(slots=True)
class AnnounceNumber(Prompt):
    player: int
    options: list[int]

    @classmethod
    def read(cls, r):
        player, n = r.u8(), r.u8()
        return cls(player, [r.u64() for _ in range(n)])

    @staticmethod
    def respond(index: int) -> bytes:
        return encode_int(index)

    def decode_response(self, data):
        i = _i32(data)
        return {"index": i, "value": self.options[i] if 0 <= i < len(self.options) else None}


# --- duel flow ---------------------------------------------------------------------------------------------

@message(Msg.RETRY)
@dataclass(slots=True)
class Retry(Message):
    pass


@message(Msg.HINT)
@dataclass(slots=True)
class Hint(Message):
    hint_type: int
    player: int
    data: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8(), r.u64())


@message(Msg.WAITING)
@dataclass(slots=True)
class Waiting(Message):
    pass


@message(Msg.START)
@dataclass(slots=True)
class Start(Message):
    player_type: int  # 0 = you go first, 1 = second; high nibble set for spectators
    lp: tuple[int, int]
    deck: tuple[int, int]
    extra: tuple[int, int]

    @classmethod
    def read(cls, r):
        pt, lp0, lp1, d0, e0, d1, e1 = r.u8(), r.u32(), r.u32(), r.u16(), r.u16(), r.u16(), r.u16()
        return cls(pt, (lp0, lp1), (d0, d1), (e0, e1))


@message(Msg.WIN)
@dataclass(slots=True)
class Win(Message):
    player: int  # 2 = draw
    reason: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8())


@message(Msg.UPDATE_DATA)
@dataclass(slots=True)
class UpdateData(Message):
    player: int
    location: int
    cards: list[CardQuery | None]

    @classmethod
    def read(cls, r):
        player, loc = r.u8(), r.u8()
        return cls(player, loc, parse_location(r.rest()))


@message(Msg.UPDATE_CARD)
@dataclass(slots=True)
class UpdateCard(Message):
    player: int
    location: int
    sequence: int
    card: CardQuery | None

    @classmethod
    def read(cls, r):
        player, loc, seq = r.u8(), r.u8(), r.u8()
        return cls(player, loc, seq, parse_card(r.rest()))


@message(Msg.REQUEST_DECK)
@dataclass(slots=True)
class RequestDeck(Message):
    pass


@message(Msg.NEW_TURN)
@dataclass(slots=True)
class NewTurn(Message):
    player: int

    @classmethod
    def read(cls, r):
        return cls(r.u8())


@message(Msg.NEW_PHASE)
@dataclass(slots=True)
class NewPhase(Message):
    phase: int

    @classmethod
    def read(cls, r):
        return cls(r.u16())


# --- cards moving and revealing ----------------------------------------------------------------------------

@dataclass(slots=True)
class _ConfirmBase(Message):
    player: int  # who gets to see the cards
    cards: list[CardRef]

    @classmethod
    def read(cls, r):
        player = r.u8()
        return cls(player, _list(r, _ref_seq32))


@message(Msg.CONFIRM_DECKTOP)
@dataclass(slots=True)
class ConfirmDecktop(_ConfirmBase):
    pass


@message(Msg.CONFIRM_EXTRATOP)
@dataclass(slots=True)
class ConfirmExtratop(_ConfirmBase):
    pass


@message(Msg.CONFIRM_CARDS)
@dataclass(slots=True)
class ConfirmCards(_ConfirmBase):
    pass


@dataclass(slots=True)
class _PlayerOnly(Message):
    player: int

    @classmethod
    def read(cls, r):
        return cls(r.u8())


@message(Msg.SHUFFLE_DECK)
@dataclass(slots=True)
class ShuffleDeck(_PlayerOnly):
    pass


@message(Msg.REFRESH_DECK)
@dataclass(slots=True)
class RefreshDeck(Message):
    player: int | None = None

    @classmethod
    def read(cls, r):
        return cls(r.u8() if r.remaining else None)


@dataclass(slots=True)
class _ShuffleCodes(Message):
    player: int
    codes: list[int]  # new order; 0 for cards the viewer can't see

    @classmethod
    def read(cls, r):
        player = r.u8()
        return cls(player, [r.u32() for _ in range(r.u32())])


@message(Msg.SHUFFLE_HAND)
@dataclass(slots=True)
class ShuffleHand(_ShuffleCodes):
    pass


@message(Msg.SHUFFLE_EXTRA)
@dataclass(slots=True)
class ShuffleExtra(_ShuffleCodes):
    pass


@message(Msg.SWAP_GRAVE_DECK)
@dataclass(slots=True)
class SwapGraveDeck(Message):
    player: int
    deck_size: int
    extra_mask: bytes  # bit i set: card i of the old GY went to the Extra Deck

    @classmethod
    def read(cls, r):
        player, size = r.u8(), r.u32()
        return cls(player, size, r.bytes(r.u32()))


@message(Msg.SHUFFLE_SET_CARD)
@dataclass(slots=True)
class ShuffleSetCard(Message):
    location: int
    previous: list[LocInfo]
    current: list[LocInfo]  # location 0 when unchanged

    @classmethod
    def read(cls, r):
        loc, n = r.u8(), r.u8()
        return cls(loc, [r.loc() for _ in range(n)], [r.loc() for _ in range(n)])


@message(Msg.REVERSE_DECK)
@dataclass(slots=True)
class ReverseDeck(Message):
    pass


@message(Msg.DECK_TOP)
@dataclass(slots=True)
class DeckTop(Message):
    player: int
    sequence: int  # counted from the top
    code: int
    position: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u32(), r.u32(), r.u32())


@message(Msg.MOVE)
@dataclass(slots=True)
class Move(Message):
    code: int  # 0 when the viewer may not know the card
    previous: LocInfo
    current: LocInfo
    reason: int

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.loc(), r.loc(), r.u32())


@message(Msg.POS_CHANGE)
@dataclass(slots=True)
class PosChange(Message):
    code: int
    controller: int
    location: int
    sequence: int
    previous_position: int
    current_position: int

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.u8(), r.u8(), r.u8(), r.u8(), r.u8())


@message(Msg.SET)
@dataclass(slots=True)
class SetCard(Message):
    code: int
    location: LocInfo

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.loc())


@message(Msg.SWAP)
@dataclass(slots=True)
class Swap(Message):
    code1: int
    location1: LocInfo
    code2: int
    location2: LocInfo

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.loc(), r.u32(), r.loc())


@message(Msg.FIELD_DISABLED)
@dataclass(slots=True)
class FieldDisabled(Message):
    disabled: int  # zone bits, same layout as SELECT_PLACE seen from player 0

    @classmethod
    def read(cls, r):
        return cls(r.u32())


@dataclass(slots=True)
class _CardAt(Message):
    code: int
    location: LocInfo

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.loc())


@message(Msg.SUMMONING)
@dataclass(slots=True)
class Summoning(_CardAt):
    pass


@message(Msg.SPSUMMONING)
@dataclass(slots=True)
class SpSummoning(_CardAt):
    pass


@message(Msg.FLIPSUMMONING)
@dataclass(slots=True)
class FlipSummoning(_CardAt):
    pass


@message(Msg.SUMMONED)
@dataclass(slots=True)
class Summoned(Message):
    pass


@message(Msg.SPSUMMONED)
@dataclass(slots=True)
class SpSummoned(Message):
    pass


@message(Msg.FLIPSUMMONED)
@dataclass(slots=True)
class FlipSummoned(Message):
    pass


# --- chains --------------------------------------------------------------------------------------------------

@message(Msg.CHAINING)
@dataclass(slots=True)
class Chaining(Message):
    code: int
    location: LocInfo
    controller: int           # who activated it
    trigger_location: int
    trigger_sequence: int
    description: int
    chain_count: int          # the link number this becomes

    @classmethod
    def read(cls, r):
        return cls(r.u32(), r.loc(), r.u8(), r.u8(), r.u32(), r.u64(), r.u32())


@dataclass(slots=True)
class _ChainCount(Message):
    chain_count: int

    @classmethod
    def read(cls, r):
        return cls(r.u8())


@message(Msg.CHAINED)
@dataclass(slots=True)
class Chained(_ChainCount):
    pass


@message(Msg.CHAIN_SOLVING)
@dataclass(slots=True)
class ChainSolving(_ChainCount):
    pass


@message(Msg.CHAIN_SOLVED)
@dataclass(slots=True)
class ChainSolved(_ChainCount):
    pass


@message(Msg.CHAIN_NEGATED)
@dataclass(slots=True)
class ChainNegated(_ChainCount):
    pass


@message(Msg.CHAIN_DISABLED)
@dataclass(slots=True)
class ChainDisabled(_ChainCount):
    pass


@message(Msg.CHAIN_END)
@dataclass(slots=True)
class ChainEnd(Message):
    pass


@dataclass(slots=True)
class _LocList(Message):
    cards: list[LocInfo]

    @classmethod
    def read(cls, r):
        return cls([r.loc() for _ in range(r.u32())])


@message(Msg.CARD_SELECTED)
@dataclass(slots=True)
class CardSelected(_LocList):
    pass


@message(Msg.BECOME_TARGET)
@dataclass(slots=True)
class BecomeTarget(_LocList):
    pass


@message(Msg.REMOVE_CARDS)
@dataclass(slots=True)
class RemoveCards(_LocList):
    pass


@message(Msg.RANDOM_SELECTED)
@dataclass(slots=True)
class RandomSelected(Message):
    player: int
    cards: list[LocInfo]

    @classmethod
    def read(cls, r):
        player = r.u8()
        return cls(player, [r.loc() for _ in range(r.u32())])


# --- draws, damage, LP -------------------------------------------------------------------------------------

@message(Msg.DRAW)
@dataclass(slots=True)
class Draw(Message):
    player: int
    cards: list[tuple[int, int]]  # (code, position); code 0 when hidden from the viewer

    @property
    def codes(self) -> list[int]:
        return [c for c, _ in self.cards]

    @classmethod
    def read(cls, r):
        player = r.u8()
        return cls(player, [(r.u32(), r.u32()) for _ in range(r.u32())])


@dataclass(slots=True)
class _PlayerAmount(Message):
    player: int
    amount: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u32())


@message(Msg.DAMAGE)
@dataclass(slots=True)
class Damage(_PlayerAmount):
    pass


@message(Msg.RECOVER)
@dataclass(slots=True)
class Recover(_PlayerAmount):
    pass


@message(Msg.LPUPDATE)
@dataclass(slots=True)
class LpUpdate(_PlayerAmount):
    pass


@message(Msg.PAY_LPCOST)
@dataclass(slots=True)
class PayLpCost(_PlayerAmount):
    pass


@dataclass(slots=True)
class _TwoLocs(Message):
    card: LocInfo
    target: LocInfo

    @classmethod
    def read(cls, r):
        return cls(r.loc(), r.loc())


@message(Msg.EQUIP)
@dataclass(slots=True)
class Equip(_TwoLocs):
    pass


@message(Msg.CARD_TARGET)
@dataclass(slots=True)
class CardTarget(_TwoLocs):
    pass


@message(Msg.CANCEL_TARGET)
@dataclass(slots=True)
class CancelTarget(_TwoLocs):
    pass


@message(Msg.UNEQUIP)
@dataclass(slots=True)
class Unequip(Message):
    card: LocInfo

    @classmethod
    def read(cls, r):
        return cls(r.loc())


@dataclass(slots=True)
class _Counter(Message):
    counter_type: int
    controller: int
    location: int
    sequence: int
    count: int

    @classmethod
    def read(cls, r):
        return cls(r.u16(), r.u8(), r.u8(), r.u8(), r.u16())


@message(Msg.ADD_COUNTER)
@dataclass(slots=True)
class AddCounter(_Counter):
    pass


@message(Msg.REMOVE_COUNTER)
@dataclass(slots=True)
class RemoveCounter(_Counter):
    pass


# --- battle ------------------------------------------------------------------------------------------------

@message(Msg.ATTACK)
@dataclass(slots=True)
class Attack(Message):
    attacker: LocInfo
    target: LocInfo  # location 0 = direct attack

    @property
    def direct(self) -> bool:
        return self.target.location == 0

    @classmethod
    def read(cls, r):
        return cls(r.loc(), r.loc())


@message(Msg.BATTLE)
@dataclass(slots=True)
class Battle(Message):
    attacker: LocInfo
    attacker_atk: int
    attacker_def: int
    attacker_destroyed: int
    target: LocInfo
    target_atk: int
    target_def: int
    target_destroyed: int

    @classmethod
    def read(cls, r):
        return cls(r.loc(), r.i32(), r.i32(), r.u8(), r.loc(), r.i32(), r.i32(), r.u8())


@message(Msg.ATTACK_DISABLED)
@dataclass(slots=True)
class AttackDisabled(Message):
    pass


@message(Msg.DAMAGE_STEP_START)
@dataclass(slots=True)
class DamageStepStart(Message):
    pass


@message(Msg.DAMAGE_STEP_END)
@dataclass(slots=True)
class DamageStepEnd(Message):
    pass


@message(Msg.MISSED_EFFECT)
@dataclass(slots=True)
class MissedEffect(Message):
    location: LocInfo
    code: int

    @classmethod
    def read(cls, r):
        return cls(r.loc(), r.u32())


# --- coins, dice, hints --------------------------------------------------------------------------------------

@dataclass(slots=True)
class _Results(Message):
    player: int
    results: list[int]

    @classmethod
    def read(cls, r):
        player, n = r.u8(), r.u8()
        return cls(player, [r.u8() for _ in range(n)])


@message(Msg.TOSS_COIN)
@dataclass(slots=True)
class TossCoin(_Results):
    pass


@message(Msg.TOSS_DICE)
@dataclass(slots=True)
class TossDice(_Results):
    pass


@message(Msg.HAND_RES)
@dataclass(slots=True)
class HandRes(Message):
    hands: tuple[int, int]

    @classmethod
    def read(cls, r):
        v = r.u8()
        return cls((v & 0x3, v >> 2))


@message(Msg.CARD_HINT)
@dataclass(slots=True)
class CardHint(Message):
    location: LocInfo
    hint_type: int
    value: int

    @classmethod
    def read(cls, r):
        return cls(r.loc(), r.u8(), r.u64())


@message(Msg.PLAYER_HINT)
@dataclass(slots=True)
class PlayerHint(Message):
    player: int
    hint_type: int
    value: int

    @classmethod
    def read(cls, r):
        return cls(r.u8(), r.u8(), r.u64())


@dataclass(slots=True)
class _Text(Message):
    text: str

    @classmethod
    def read(cls, r):
        n = r.u16()
        text = r.bytes(n).decode("utf-8", errors="replace")
        if r.remaining:
            r.u8()  # the core writes a NUL after the text
        return cls(text)


@message(Msg.AI_NAME)
@dataclass(slots=True)
class AiName(_Text):
    pass


@message(Msg.SHOW_HINT)
@dataclass(slots=True)
class ShowHint(_Text):
    pass


@message(Msg.MATCH_KILL)
@dataclass(slots=True)
class MatchKill(Message):
    code: int

    @classmethod
    def read(cls, r):
        return cls(r.u32())


@message(Msg.TAG_SWAP)
@dataclass(slots=True)
class TagSwap(Message):
    player: int
    deck: int
    extra: int
    extra_faceup: int
    hand: int
    top_code: int
    hand_cards: list[tuple[int, int]]
    extra_cards: list[tuple[int, int]]

    @classmethod
    def read(cls, r):
        player, deck, extra, pcount, hand, top = r.u8(), r.u32(), r.u32(), r.u32(), r.u32(), r.u32()
        hc = [(r.u32(), r.u32()) for _ in range(hand)]
        ec = [(r.u32(), r.u32()) for _ in range(extra)]
        return cls(player, deck, extra, pcount, hand, top, hc, ec)


@message(Msg.RELOAD_FIELD)
@dataclass(slots=True)
class ReloadField(Message):
    state: FieldState

    @classmethod
    def read(cls, r):
        return cls(parse_field(r.rest()))


@dataclass(slots=True)
class Unknown(Message):
    """A message type this decoder doesn't know, or one that failed to decode (`error` says why)."""
    msg_type: int = 0
    payload: bytes = b""
    error: str = ""

    @property
    def type(self) -> int:
        return self.msg_type


# --- entry points --------------------------------------------------------------------------------------------

def decode(raw: bytes, strict: bool = False) -> Message:
    """Decode one core message. Unknown or malformed messages become `Unknown` unless `strict`."""
    if not raw:
        raise MessageError("empty message")
    cls = _REGISTRY.get(raw[0])
    if cls is None:
        if strict:
            raise MessageError(f"unknown message type {raw[0]}")
        return Unknown(msg_type=raw[0], payload=raw[1:], raw=raw)
    r = Reader(raw, 1)
    try:
        msg = cls.read(r)
    except (BufferUnderrun, ValueError) as e:
        if strict:
            raise MessageError(f"{MSG_NAMES.get(raw[0], raw[0])}: {e}") from None
        return Unknown(msg_type=raw[0], payload=raw[1:], error=str(e), raw=raw)
    if strict and r.remaining and cls.TYPE not in (Msg.UPDATE_DATA, Msg.UPDATE_CARD, Msg.RELOAD_FIELD):
        raise MessageError(f"{msg.name}: {r.remaining} trailing bytes")
    msg.raw = raw
    return msg


def decode_response(prompt: Prompt, data: bytes) -> dict:
    """What a response buffer chose, in terms of the prompt's own lists (for coach mode and logs)."""
    try:
        return prompt.decode_response(data)
    except (BufferUnderrun, ValueError, IndexError, struct.error) as e:
        return {"raw": data.hex(), "error": str(e)}


def message_types() -> dict[int, type[Message]]:
    return dict(_REGISTRY)


# --- rendering ---------------------------------------------------------------------------------------------

def _loc_str(loc: LocInfo | CardRef) -> str:
    c = loc.controller
    name = LOCATION_NAMES.get(loc.location & 0x7F, f"loc{loc.location:#x}")
    if loc.location & 0x80 and loc.location != 0x80:
        return f"p{c} overlay of {name}[{loc.sequence}]#{loc.position}"
    if loc.location == 0:
        return "-"
    return f"p{c} {name}[{loc.sequence}]"


class _Namer:
    def __init__(self, cards):
        self.cards = cards

    def __call__(self, code: int) -> str:
        if not code:
            return "(hidden)"
        if self.cards is None:
            return str(code)
        return self.cards.name(code)


def _refs(name, refs) -> str:
    return "[" + ", ".join(name(c.code) for c in refs) + "]"


def render(msg: Message, cards=None) -> str:
    """One readable line for logs. `cards` (a CardDatabase) turns codes into names."""
    n = _Namer(cards)
    t = msg.name
    try:
        special = _RENDER.get(type(msg))
        if special:
            return special(msg, n)
    except Exception:  # rendering must never break a log
        pass
    parts = []
    for f in fields(msg):
        if f.name == "raw":
            continue
        v = getattr(msg, f.name)
        if f.name in ("code", "code1", "code2"):
            v = n(v)
        elif isinstance(v, LocInfo):
            v = _loc_str(v)
        elif isinstance(v, list) and v and isinstance(v[0], CardRef):
            v = _refs(n, v)
        elif isinstance(v, bytes):
            v = v.hex()
        parts.append(f"{f.name}={v}")
    return f"{t} " + " ".join(parts) if parts else t


def _render_idle(m: SelectIdleCmd, n) -> str:
    bits = [f"SELECT_IDLECMD p{m.player}:"]
    for label, lst in (("summon", m.summonable), ("spsummon", m.special_summonable),
                       ("repos", m.repositionable), ("mset", m.monster_settable), ("sset", m.spell_settable),
                       ("activate", m.activatable)):
        if lst:
            bits.append(f"{label} {_refs(n, lst)}")
    bits += [x for x, ok in (("bp", m.can_battle_phase), ("ep", m.can_end_phase)) if ok]
    return " ".join(bits)


def _render_battle(m: SelectBattleCmd, n) -> str:
    bits = [f"SELECT_BATTLECMD p{m.player}:"]
    if m.activatable:
        bits.append(f"activate {_refs(n, m.activatable)}")
    if m.attackable:
        bits.append("attack [" + ", ".join(n(a.code) + ("*" if a.direct_attack else "") for a in m.attackable)
                    + "]")
    bits += [x for x, ok in (("m2", m.can_main2), ("ep", m.can_end_phase)) if ok]
    return " ".join(bits)


def _render_move(m: Move, n) -> str:
    return f"MOVE {n(m.code)}: {_loc_str(m.previous)} -> {_loc_str(m.current)} reason={m.reason:#x}"


def _render_hint(m: Hint, n) -> str:
    extra = f" ({n(m.data)})" if m.hint_type in (8, 10) else ""
    return f"HINT type={m.hint_type} p{m.player} data={m.data}{extra}"


_RENDER = {
    SelectIdleCmd: _render_idle,
    SelectBattleCmd: _render_battle,
    Move: _render_move,
    Hint: _render_hint,
    NewTurn: lambda m, n: f"NEW_TURN p{m.player}",
    NewPhase: lambda m, n: f"NEW_PHASE {PHASE_NAMES.get(m.phase, hex(m.phase))}",
    Draw: lambda m, n: f"DRAW p{m.player}: [{', '.join(n(c) for c in m.codes)}]",
    Chaining: lambda m, n: f"CHAINING #{m.chain_count} {n(m.code)} by p{m.controller} at {_loc_str(m.location)}",
    Damage: lambda m, n: f"DAMAGE p{m.player} {m.amount}",
    Recover: lambda m, n: f"RECOVER p{m.player} {m.amount}",
    LpUpdate: lambda m, n: f"LPUPDATE p{m.player} {m.amount}",
    PayLpCost: lambda m, n: f"PAY_LPCOST p{m.player} {m.amount}",
    Win: lambda m, n: f"WIN {'draw' if m.player > 1 else f'p{m.player}'} ({WIN_REASON_NAMES.get(m.reason, m.reason)})",
    Attack: lambda m, n: f"ATTACK {_loc_str(m.attacker)} -> {'direct' if m.direct else _loc_str(m.target)}",
    SelectChain: lambda m, n: (f"SELECT_CHAIN p{m.player}{' forced' if m.forced else ''}: {_refs(n, m.chains)}"),
    SelectCard: lambda m, n: (f"SELECT_CARD p{m.player} {m.min}-{m.max}{' cancelable' if m.cancelable else ''}: "
                              f"{_refs(n, m.cards)}"),
    SelectPosition: lambda m, n: (f"SELECT_POSITION p{m.player} {n(m.code)}: "
                                  + ", ".join(v for k, v in POSITION_NAMES.items() if m.positions & k)),
    SelectPlace: lambda m, n: (f"SELECT_PLACE p{m.player} x{m.count}: "
                               + " ".join(f"p{p}/{LOCATION_NAMES[l]}[{s}]" for p, l, s in m.zones)),
    UpdateData: lambda m, n: (f"UPDATE_DATA p{m.player} {LOCATION_NAMES.get(m.location, m.location)}: "
                              f"[{', '.join(n(c.code) if c else '-' for c in m.cards)}]"),
    UpdateCard: lambda m, n: (f"UPDATE_CARD p{m.player} {LOCATION_NAMES.get(m.location, m.location)}"
                              f"[{m.sequence}]: {n(m.card.code) if m.card else '-'}"),
}
