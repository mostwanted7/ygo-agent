"""Who may see what: per-player and spectator filtering of core messages, and the field refreshes around them.

This mirrors EDOPro's own host (gframe/generic_duel.cpp: BeforeParsing / Sending / AfterParsing and
RefreshLocation/RefreshSingle) message by message, so an EDOPro client gets exactly what EDOPro's LAN host
would send it. Where EDOPro forwards a card code a player shouldn't learn, the arena is stricter (the
client never reads these fields, so this changes nothing on screen):

  * MSG_POS_CHANGE between two face-down positions: the code is zeroed for everyone but the controller.
  * MSG_SWAP: codes of face-down cards are zeroed for everyone but their controller.
  * MSG_CONFIRM_CARDS: private to the confirming player when *any* card (not just the first) is in a
    Deck or Extra Deck.
  * MSG_SELECT_SUM: codes of the opponent's face-down cards are zeroed (EDOPro does this for SELECT_CARD,
    SELECT_TRIBUTE and SELECT_UNSELECT_CARD only).

Multirole (the online server, YGOPro/CoreUtils.cpp) was compared too: it is looser in places (unknown hint
types go to everyone, only Deck confirmations are private) and stricter in one (Extra Deck refreshes reach
their owner only). The arena keeps EDOPro's choices, which is what a LAN EDOPro client expects; its RETRY
handling (re-send the prompt once) does follow Multirole, see duel.py.

Audiences are bit masks: TEAM0 / TEAM1 are the duelists of core team 0 (who went first) and team 1,
SPECTATORS everyone watching.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..core.constants import (HINT_CARD, HINT_SKILL, HINT_SKILL_COVER, HINT_SKILL_FLIP, HINT_SKILL_REMOVE,
                              LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE,
                              LOCATION_OVERLAY, LOCATION_REMOVED, LOCATION_SZONE, POS_FACEDOWN, POS_FACEUP, PROMPT_MESSAGES,
                              REFRESH_DECK, REFRESH_EXTRA, REFRESH_GRAVE, REFRESH_HAND, REFRESH_MZONE,
                              REFRESH_SHUFFLE_SET, REFRESH_SINGLE, REFRESH_SZONE, Msg)

TEAM0, TEAM1, SPECTATORS = 1, 2, 4
PLAYERS = TEAM0 | TEAM1
EVERYONE = TEAM0 | TEAM1 | SPECTATORS
WAITING = bytes([Msg.WAITING])

_U32 = struct.Struct("<I")
_ZERO = b"\0\0\0\0"


def team_bit(team: int) -> int:
    return TEAM0 if team == 0 else TEAM1 if team == 1 else 0


def others(team: int) -> int:
    """Everyone except the duelist of `team` (the opponent and the spectators)."""
    return EVERYONE & ~team_bit(team)


@dataclass(slots=True)
class Route:
    sends: list[tuple[int, bytes]] = field(default_factory=list)
    cache: bytes | None = None    # the spectator version, kept for spectators who join later (catch-up)
    record: bool = True           # the unfiltered message goes into the replay stream
    prompt_team: int | None = None

    def for_audience(self, audience: int) -> list[bytes]:
        return [data for mask, data in self.sends if mask & audience]


def _zero_code(raw: bytes, offset: int) -> bytes:
    return raw[:offset] + _ZERO + raw[offset + 4:]


def _hidden_after_move(location: int, position: int) -> bool:
    """generic_duel.cpp MSG_MOVE: the destination hides the card unless it's a GY or Xyz material."""
    return not (location & (LOCATION_GRAVE | LOCATION_OVERLAY)) and bool(
        location & (LOCATION_DECK | LOCATION_HAND) or position & POS_FACEDOWN)


def _strip_draw(raw: bytes) -> bytes:
    (n,) = _U32.unpack_from(raw, 2)
    out = bytearray(raw)
    for i in range(n):
        off = 6 + 8 * i
        if not _U32.unpack_from(raw, off + 4)[0] & POS_FACEUP:
            out[off:off + 4] = _ZERO
    return bytes(out)


def _strip_codes_list(raw: bytes, start: int) -> bytes:
    """Zero `n` u32 codes that follow a u32 count at `start` (SHUFFLE_HAND/EXTRA)."""
    (n,) = _U32.unpack_from(raw, start)
    return raw[:start + 4] + _ZERO * n + raw[start + 4 + 4 * n:]


def _strip_select(raw: bytes, player: int) -> bytes:
    """SELECT_CARD / SELECT_UNSELECT_CARD / SELECT_TRIBUTE: hide codes of cards the chooser doesn't control."""
    t = raw[0]
    out = bytearray(raw)
    off = 1 + 1 + (2 if t == Msg.SELECT_UNSELECT_CARD else 1) + 8
    for _ in range(2 if t == Msg.SELECT_UNSELECT_CARD else 1):
        (n,) = _U32.unpack_from(raw, off)
        off += 4
        step = 4 + 7 if t == Msg.SELECT_TRIBUTE else 4 + 10
        for _ in range(n):
            if raw[off + 4] != player:
                out[off:off + 4] = _ZERO
            off += step
    return bytes(out)


def _strip_sum(raw: bytes, player: int) -> bytes:
    out = bytearray(raw)
    off = 1 + 1 + 1 + 12
    for _ in range(2):
        (n,) = _U32.unpack_from(raw, off)
        off += 4
        for _ in range(n):
            con, pos = raw[off + 4], _U32.unpack_from(raw, off + 10)[0]
            if con != player and pos & POS_FACEDOWN and not raw[off + 5] & LOCATION_OVERLAY:
                out[off:off + 4] = _ZERO
            off += 18
    return bytes(out)


def _strip_tag_swap(raw: bytes) -> bytes:
    ecount, hcount = _U32.unpack_from(raw, 6)[0], _U32.unpack_from(raw, 14)[0]
    out = bytearray(raw)
    off = 22
    for _ in range(hcount + ecount):
        if not _U32.unpack_from(raw, off + 4)[0] & POS_FACEUP:
            out[off:off + 4] = _ZERO
        off += 8
    return bytes(out)


def _split(team: int, own: bytes, other: bytes) -> Route:
    """`own` to the duelist of `team`, `other` to their opponent and the spectators."""
    return Route([(team_bit(team), own), (others(team), other)], cache=other)


def route(raw: bytes, best_of: int = 1) -> Route:
    """How EDOPro's host distributes one core message (generic_duel.cpp GenericDuel::Sending)."""
    t = raw[0]
    if t == Msg.HINT:
        kind, player = raw[1], raw[2]
        if kind in (1, 2, 3, 5):
            return Route([(team_bit(player), raw)], record=False)
        if kind in (4, 6, 7, 8, 9, 11):
            return Route([(others(player), raw)])
        if kind in (HINT_CARD, HINT_SKILL_COVER, HINT_SKILL_FLIP, HINT_SKILL_REMOVE):
            return Route([(EVERYONE, raw)])
        if kind == HINT_SKILL:
            return Route([(team_bit(player), raw)])
        return Route([])  # EDOPro sends other hint types to nobody
    if t in PROMPT_MESSAGES:
        player = raw[1]
        if t in (Msg.SELECT_CARD, Msg.SELECT_TRIBUTE, Msg.SELECT_UNSELECT_CARD):
            raw = _strip_select(raw, player)
        elif t == Msg.SELECT_SUM:
            raw = _strip_sum(raw, player)
        return Route([(PLAYERS & ~team_bit(player), WAITING), (team_bit(player), raw)], record=False,
                     prompt_team=player)
    if t == Msg.WIN:
        return Route([(EVERYONE, raw)])
    if t == Msg.CONFIRM_CARDS:
        player, n = raw[1], _U32.unpack_from(raw, 2)[0]
        if any(raw[6 + 10 * i + 5] in (LOCATION_DECK, LOCATION_EXTRA) for i in range(n)):
            return Route([(team_bit(player), raw)])
        return Route([(EVERYONE, raw)], cache=raw)
    if t in (Msg.SHUFFLE_HAND, Msg.SHUFFLE_EXTRA):
        return _split(raw[1], raw, _strip_codes_list(raw, 2))
    if t == Msg.MOVE:
        con, loc, pos = raw[15], raw[16], _U32.unpack_from(raw, 21)[0]
        return _split(con, raw, _zero_code(raw, 1) if _hidden_after_move(loc, pos) else raw)
    if t == Msg.SET:
        hidden = _zero_code(raw, 1)
        return Route([(EVERYONE, hidden)], cache=hidden)
    if t == Msg.SPSUMMONING:
        con, pos = raw[5], _U32.unpack_from(raw, 11)[0]
        if not pos & POS_FACEDOWN:
            return Route([(EVERYONE, raw)], cache=raw)
        return _split(con, raw, _zero_code(raw, 1))
    if t == Msg.DRAW:
        return _split(raw[1], raw, _strip_draw(raw))
    if t == Msg.MISSED_EFFECT:
        return Route([(team_bit(raw[1]), raw)])
    if t == Msg.TAG_SWAP:
        return _split(raw[1], raw, _strip_tag_swap(raw))
    if t == Msg.MATCH_KILL:
        return Route([(EVERYONE, raw)] if best_of > 1 else [])
    if t == Msg.POS_CHANGE:
        con, prev, cur = raw[5], raw[8], raw[9]
        if prev & POS_FACEDOWN and cur & POS_FACEDOWN:
            return _split(con, raw, _zero_code(raw, 1))
        return Route([(EVERYONE, raw)], cache=raw)
    if t == Msg.SWAP:
        return _route_swap(raw)
    return Route([(EVERYONE, raw)], cache=raw)


def _route_swap(raw: bytes) -> Route:
    cards = [(1, raw[5], _U32.unpack_from(raw, 11)[0]), (15, raw[19], _U32.unpack_from(raw, 25)[0])]

    def view(team: int | None) -> bytes:
        out = raw
        for off, con, pos in cards:
            if pos & POS_FACEDOWN and con != team:
                out = _zero_code(out, off)
        return out
    obs = view(None)
    sends = [(TEAM0, view(0)), (TEAM1, view(1)), (SPECTATORS, obs)]
    return Route(sends, cache=obs)


# --- refreshes -----------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Refresh:
    """A query the host runs and sends as MSG_UPDATE_DATA (location) or MSG_UPDATE_CARD (single card).
    `replay_only` refreshes (the "pseudo" deck refresh) go into the replay stream and to nobody else."""
    controller: int
    location: int
    flags: int
    sequence: int | None = None
    replay_only: bool = False


def _both(location: int, flags: int) -> list[Refresh]:
    return [Refresh(0, location, flags), Refresh(1, location, flags)]


def _decks() -> list[Refresh]:
    return [Refresh(0, LOCATION_DECK, REFRESH_DECK, replay_only=True),
            Refresh(1, LOCATION_DECK, REFRESH_DECK, replay_only=True)]


def pre_refreshes(raw: bytes) -> list[Refresh]:
    """GenericDuel::BeforeParsing."""
    t = raw[0]
    if t in (Msg.SELECT_BATTLECMD, Msg.SELECT_IDLECMD):
        return _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE) + \
            _both(LOCATION_HAND, REFRESH_HAND)
    if t in (Msg.SELECT_CHAIN, Msg.NEW_TURN):
        return _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE)
    if t == Msg.FLIPSUMMONING:
        return [Refresh(raw[5], raw[6], REFRESH_SINGLE, _U32.unpack_from(raw, 7)[0])]
    return []


def post_refreshes(raw: bytes, custom_start: bool = False) -> list[Refresh]:
    """GenericDuel::AfterParsing. `custom_start`: after a MSG_RELOAD_FIELD from a custom start state, refresh
    every location (EDOPro never sends RELOAD_FIELD in network duels, so it has no rule for it beyond the
    Extra Decks)."""
    t = raw[0]
    if t in (Msg.SHUFFLE_HAND, Msg.DRAW):
        return [Refresh(raw[1], LOCATION_HAND, REFRESH_HAND)]
    if t == Msg.SHUFFLE_EXTRA:
        return [Refresh(raw[1], LOCATION_EXTRA, REFRESH_EXTRA)]
    if t == Msg.SWAP_GRAVE_DECK:
        return [Refresh(raw[1], LOCATION_GRAVE, REFRESH_GRAVE)]
    if t == Msg.REVERSE_DECK:
        return _decks()
    if t == Msg.SHUFFLE_SET_CARD:
        return _both(raw[1], REFRESH_SHUFFLE_SET)
    if t in (Msg.DAMAGE_STEP_START, Msg.DAMAGE_STEP_END):
        return _both(LOCATION_MZONE, REFRESH_MZONE)
    if t in (Msg.SUMMONED, Msg.SPSUMMONED, Msg.FLIPSUMMONED, Msg.CHAIN_SOLVED):
        return _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE)
    if t in (Msg.NEW_PHASE, Msg.CHAINED):
        return _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE) + \
            _both(LOCATION_HAND, REFRESH_HAND)
    if t == Msg.CHAIN_END:
        return _decks() + _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE) + \
            _both(LOCATION_HAND, REFRESH_HAND)
    if t == Msg.MOVE:
        pc, pl = raw[5], raw[6]
        cc, cl, cs = raw[15], raw[16], _U32.unpack_from(raw, 17)[0]
        if cl and not cl & LOCATION_OVERLAY and (cl != pl or pc != cc):
            return [Refresh(cc, cl, REFRESH_SINGLE, cs)]
        return []
    if t == Msg.POS_CHANGE:
        cc, cl, cs, pp, cp = raw[5], raw[6], raw[7], raw[8], raw[9]
        if pp & POS_FACEDOWN and cp & POS_FACEUP:
            return [Refresh(cc, cl, REFRESH_SINGLE, cs)]
        return []
    if t == Msg.SWAP:
        return [Refresh(raw[5], raw[6], REFRESH_SINGLE, _U32.unpack_from(raw, 7)[0]),
                Refresh(raw[19], raw[20], REFRESH_SINGLE, _U32.unpack_from(raw, 21)[0])]
    if t == Msg.TAG_SWAP:
        p = raw[1]
        return [Refresh(p, LOCATION_DECK, REFRESH_DECK, replay_only=True), Refresh(p, LOCATION_EXTRA, REFRESH_EXTRA),
                Refresh(0, LOCATION_MZONE, 0x3181FFF), Refresh(1, LOCATION_MZONE, 0x3181FFF),
                Refresh(0, LOCATION_SZONE, 0x3781FFF), Refresh(1, LOCATION_SZONE, 0x3781FFF),
                Refresh(0, LOCATION_HAND, REFRESH_HAND), Refresh(1, LOCATION_HAND, REFRESH_HAND)]
    if t == Msg.RELOAD_FIELD:
        out = _both(LOCATION_EXTRA, REFRESH_EXTRA)
        if custom_start:
            out += _decks() + _both(LOCATION_MZONE, REFRESH_MZONE) + _both(LOCATION_SZONE, REFRESH_SZONE) + \
                _both(LOCATION_HAND, REFRESH_HAND) + _both(LOCATION_GRAVE, REFRESH_GRAVE) + \
                _both(LOCATION_REMOVED, REFRESH_GRAVE)
        return out
    return []


def start_refreshes() -> list[Refresh]:
    """What EDOPro's host sends right after MSG_START: deck pseudo-refreshes (replay only), Extra Decks."""
    return _decks() + _both(LOCATION_EXTRA, REFRESH_EXTRA)
