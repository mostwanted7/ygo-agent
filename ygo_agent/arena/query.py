"""Core query buffers (OCG_DuelQuery / QueryLocation / QueryField): parsing and EDOPro's visibility rules.

A card's query is a list of entries `u16 size, u32 flag, payload` ending with QUERY_END; an empty zone is a
lone `u16 0`. A location query is `u32 total size` followed by one card query per slot.

`card_views` re-serializes a card the way EDOPro's host does (CoreUtils::Query::GenerateBuffer): fields in
ascending flag order, REASON_CARD/EQUIP_CARD dropped when they point nowhere, and the private fields (code,
type, stats, ...) removed for viewers who may not see the card.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..core.constants import (POS_FACEUP, QUERY_ALIAS, QUERY_ATTACK, QUERY_ATTRIBUTE, QUERY_BASE_ATTACK,
                              QUERY_BASE_DEFENSE, QUERY_CODE, QUERY_COUNTERS, QUERY_COVER, QUERY_DEFENSE,
                              QUERY_END, QUERY_EQUIP_CARD, QUERY_IS_HIDDEN, QUERY_IS_PUBLIC, QUERY_LEVEL,
                              QUERY_LINK, QUERY_LSCALE, QUERY_OVERLAY_CARD, QUERY_OWNER, QUERY_POSITION,
                              QUERY_RACE, QUERY_RANK, QUERY_REASON, QUERY_REASON_CARD, QUERY_RSCALE,
                              QUERY_STATUS, QUERY_TARGET_CARD, QUERY_TYPE)
from .buffer import LocInfo, Reader

PRIVATE_QUERIES = (QUERY_CODE | QUERY_ALIAS | QUERY_TYPE | QUERY_LEVEL | QUERY_RANK | QUERY_ATTRIBUTE | QUERY_RACE
                   | QUERY_ATTACK | QUERY_DEFENSE | QUERY_BASE_ATTACK | QUERY_BASE_DEFENSE | QUERY_STATUS
                   | QUERY_LSCALE | QUERY_RSCALE | QUERY_LINK)

_H = struct.Struct("<H")
_HI = struct.Struct("<HI")
_I = struct.Struct("<I")
EMPTY_SLOT = b"\0\0"


# --- fast raw-entry filtering (visibility) -------------------------------------------------------------------

def _split_card(buf: bytes, off: int) -> tuple[list[tuple[int, int, int]] | None, int]:
    """Entries of the card at `off` as (flag, start, end) slices, and the offset after it."""
    (size,) = _H.unpack_from(buf, off)
    if size == 0:
        return None, off + 2
    entries = []
    while True:
        size, flag = _HI.unpack_from(buf, off)
        end = off + 2 + size
        entries.append((flag, off, end))
        off = end
        if flag == QUERY_END:
            return entries, off


def _card_out(buf: bytes, entries, public: bool, check_hidden: bool) -> bytes:
    """One card as EDOPro's GenerateBuffer(is_for_public_buffer=public, check_hidden) writes it."""
    if entries is None:
        return EMPTY_SLOT
    position = is_public = is_hidden = 0
    for flag, start, end in entries:
        if flag == QUERY_POSITION:
            (position,) = _I.unpack_from(buf, start + 6)
        elif flag == QUERY_IS_PUBLIC:
            is_public = buf[start + 6]
        elif flag == QUERY_IS_HIDDEN:
            is_hidden = buf[start + 6]
    strip = (public or (check_hidden and is_hidden)) and not (is_public or position & POS_FACEUP)
    parts = []
    for flag, start, end in sorted(entries):
        if strip and flag & PRIVATE_QUERIES:
            continue
        if (flag == QUERY_REASON_CARD or flag == QUERY_EQUIP_CARD) and buf[start + 7] == 0:
            continue  # loc_info with location 0: no such card
        parts.append(buf[start:end])
    return b"".join(parts)


@dataclass(frozen=True, slots=True)
class Views:
    """The same query as the replay (full), the owner and everyone else (public) get it."""
    full: bytes
    owner: bytes
    public: bytes


def card_views(raw: bytes) -> Views:
    entries, _ = _split_card(raw, 0)
    return Views(_card_out(raw, entries, False, False), _card_out(raw, entries, False, True),
                 _card_out(raw, entries, True, True))


def location_views(raw: bytes) -> Views:
    (total,) = _I.unpack_from(raw, 0)
    off, end = 4, 4 + total
    full, owner, public = [], [], []
    while off < end:
        entries, off = _split_card(raw, off)
        full.append(_card_out(raw, entries, False, False))
        owner.append(_card_out(raw, entries, False, True))
        public.append(_card_out(raw, entries, True, True))

    def pack(parts):
        body = b"".join(parts)
        return _I.pack(len(body)) + body
    return Views(pack(full), pack(owner), pack(public))


class ViewCache:
    """Memoizes views by raw buffer; consecutive refreshes of an unchanged zone are the common case."""

    def __init__(self, limit: int = 4096):
        self._cache: dict[tuple[bool, bytes], Views] = {}
        self.limit = limit

    def get(self, raw: bytes, location: bool) -> Views:
        key = (location, raw)
        v = self._cache.get(key)
        if v is None:
            if len(self._cache) >= self.limit:
                self._cache.clear()
            v = self._cache[key] = location_views(raw) if location else card_views(raw)
        return v


# --- structured parsing ------------------------------------------------------------------------------------

@dataclass(slots=True)
class CardQuery:
    """One card's queried fields. Fields that weren't queried (or were stripped) are None."""
    flags: int = 0
    code: int | None = None
    position: int | None = None
    alias: int | None = None
    type: int | None = None
    level: int | None = None
    rank: int | None = None
    attribute: int | None = None
    race: int | None = None
    attack: int | None = None
    defense: int | None = None
    base_attack: int | None = None
    base_defense: int | None = None
    reason: int | None = None
    reason_card: LocInfo | None = None
    equip_card: LocInfo | None = None
    target_cards: list[LocInfo] = field(default_factory=list)
    overlay_cards: list[int] = field(default_factory=list)
    counters: dict[int, int] = field(default_factory=dict)  # counter type -> count
    owner: int | None = None
    status: int | None = None
    is_public: bool | None = None
    lscale: int | None = None
    rscale: int | None = None
    link: int | None = None
    link_marker: int | None = None
    is_hidden: bool | None = None
    cover: int | None = None

    @property
    def known(self) -> bool:
        """True when the viewer was allowed to see what card this is."""
        return bool(self.code)


_SIMPLE = {
    QUERY_CODE: ("code", "u32"), QUERY_POSITION: ("position", "u32"), QUERY_ALIAS: ("alias", "u32"),
    QUERY_TYPE: ("type", "u32"), QUERY_LEVEL: ("level", "u32"), QUERY_RANK: ("rank", "u32"),
    QUERY_ATTRIBUTE: ("attribute", "u32"), QUERY_RACE: ("race", "u64"), QUERY_ATTACK: ("attack", "i32"),
    QUERY_DEFENSE: ("defense", "i32"), QUERY_BASE_ATTACK: ("base_attack", "i32"),
    QUERY_BASE_DEFENSE: ("base_defense", "i32"), QUERY_REASON: ("reason", "u32"), QUERY_OWNER: ("owner", "u8"),
    QUERY_STATUS: ("status", "u32"), QUERY_LSCALE: ("lscale", "u32"), QUERY_RSCALE: ("rscale", "u32"),
    QUERY_COVER: ("cover", "u32"),
}


def _parse_card(r: Reader) -> CardQuery | None:
    if r.u16() == 0:
        return None
    r.pos -= 2
    q = CardQuery()
    while True:
        size, flag = r.u16(), r.u32()
        end = r.pos + size - 4
        q.flags |= flag
        if flag == QUERY_END:
            return q
        simple = _SIMPLE.get(flag)
        if simple:
            setattr(q, simple[0], getattr(r, simple[1])())
        elif flag == QUERY_IS_PUBLIC:
            q.is_public = bool(r.u8())
        elif flag == QUERY_IS_HIDDEN:
            q.is_hidden = bool(r.u8())
        elif flag in (QUERY_REASON_CARD, QUERY_EQUIP_CARD):
            loc = r.loc()
            if loc.location:
                setattr(q, "reason_card" if flag == QUERY_REASON_CARD else "equip_card", loc)
        elif flag == QUERY_TARGET_CARD:
            q.target_cards = [r.loc() for _ in range(r.u32())]
        elif flag == QUERY_OVERLAY_CARD:
            q.overlay_cards = [r.u32() for _ in range(r.u32())]
        elif flag == QUERY_COUNTERS:
            for _ in range(r.u32()):
                v = r.u32()
                q.counters[v & 0xFFFF] = v >> 16
        elif flag == QUERY_LINK:
            q.link, q.link_marker = r.u32(), r.u32()
        r.pos = end


def parse_card(raw: bytes) -> CardQuery | None:
    return _parse_card(Reader(raw)) if raw else None


def parse_location(raw: bytes) -> list[CardQuery | None]:
    """A location query (as from OCG_DuelQueryLocation or MSG_UPDATE_DATA) → one entry per slot."""
    if not raw:
        return []
    r = Reader(raw)
    end = 4 + r.u32()
    out = []
    while r.pos < end:
        out.append(_parse_card(r))
    return out


# --- OCG_DuelQueryField ------------------------------------------------------------------------------------

@dataclass(slots=True)
class ZoneInfo:
    position: int
    overlay_count: int


@dataclass(slots=True)
class PlayerField:
    lp: int
    mzone: list[ZoneInfo | None]
    szone: list[ZoneInfo | None]
    deck: int
    hand: int
    grave: int
    removed: int
    extra: int
    extra_faceup: int  # face-up Pendulum monsters in the Extra Deck


@dataclass(slots=True)
class ChainLink:
    code: int
    location: LocInfo          # where the activated card is now
    controller: int            # who activated it
    trigger_location: int
    trigger_sequence: int
    description: int


@dataclass(slots=True)
class FieldState:
    """OCG_DuelQueryField (also the payload of MSG_RELOAD_FIELD). Public information only."""
    options: int
    players: tuple[PlayerField, PlayerField]
    chain: list[ChainLink]


def parse_field(raw: bytes) -> FieldState:
    r = Reader(raw)
    options = r.u32()
    players = []
    for _ in range(2):
        lp = r.i32()  # the core can leave LP below zero after lethal damage
        zones = []
        for _count in (7, 8):
            row = []
            for _ in range(_count):
                if r.u8():
                    row.append(ZoneInfo(r.u8(), r.u32()))
                else:
                    row.append(None)
            zones.append(row)
        players.append(PlayerField(lp, zones[0], zones[1], r.u32(), r.u32(), r.u32(), r.u32(), r.u32(), r.u32()))
    chain = []
    for _ in range(r.u32()):
        chain.append(ChainLink(r.u32(), r.loc(), r.u8(), r.u8(), r.u32(), r.u64()))
    return FieldState(options, (players[0], players[1]), chain)
