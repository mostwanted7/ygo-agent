"""Query buffers: parsing, and EDOPro's owner/public re-serialization (CoreUtils::Query::GenerateBuffer)."""

import struct

from ygo_agent.arena import query as Q
from ygo_agent.core.constants import (POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK, QUERY_ATTACK, QUERY_CODE,
                                      QUERY_COVER, QUERY_END, QUERY_EQUIP_CARD, QUERY_IS_HIDDEN, QUERY_IS_PUBLIC,
                                      QUERY_LEVEL, QUERY_OWNER, QUERY_POSITION, QUERY_REASON, QUERY_REASON_CARD,
                                      QUERY_COUNTERS)


def entry(flag, payload=b""):
    return struct.pack("<HI", 4 + len(payload), flag) + payload


def card(code, position, *, public=0, hidden=None, attack=1800, extra=()):
    """In the core's own order (card::get_infos): COVER right after REASON, IS_PUBLIC always present."""
    parts = [entry(QUERY_CODE, struct.pack("<I", code)), entry(QUERY_POSITION, struct.pack("<I", position)),
             entry(QUERY_LEVEL, struct.pack("<I", 4)), entry(QUERY_ATTACK, struct.pack("<i", attack)),
             entry(QUERY_REASON, struct.pack("<I", 0)), entry(QUERY_COVER, struct.pack("<I", 0)),
             entry(QUERY_REASON_CARD, struct.pack("<BBII", 0, 0, 0, 0)), *extra,
             entry(QUERY_OWNER, b"\x00"), entry(QUERY_IS_PUBLIC, bytes((public,)))]
    if hidden is not None:
        parts.append(entry(QUERY_IS_HIDDEN, bytes((hidden,))))
    parts.append(entry(QUERY_END))
    return b"".join(parts)


def location(*cards):
    body = b"".join(c if c is not None else b"\0\0" for c in cards)
    return struct.pack("<I", len(body)) + body


def flags_of(buf):
    out, off = [], 0
    while off < len(buf):
        size, flag = struct.unpack_from("<HI", buf, off)
        out.append(flag)
        off += 2 + size
    return out


def test_full_view_sorts_fields_and_drops_empty_card_links():
    v = Q.card_views(card(1234, POS_FACEUP_ATTACK))
    flags = flags_of(v.full)
    assert flags == sorted(flags)                      # COVER moved to its place, before END
    assert QUERY_REASON_CARD not in flags              # it pointed at location 0
    assert flags[-1] == QUERY_END and QUERY_COVER in flags


def test_face_down_card_loses_private_fields_for_the_public_only():
    raw = card(5555, POS_FACEDOWN_DEFENSE)
    v = Q.card_views(raw)
    assert Q.parse_card(v.owner).code == 5555          # the owner knows their own set card
    pub = Q.parse_card(v.public)
    assert pub.code is None and pub.attack is None and pub.level is None
    assert pub.position == POS_FACEDOWN_DEFENSE and pub.owner == 0 and pub.reason == 0


def test_face_up_or_public_cards_stay_complete():
    assert Q.parse_card(Q.card_views(card(7, POS_FACEUP_ATTACK)).public).code == 7
    assert Q.parse_card(Q.card_views(card(8, POS_FACEDOWN_DEFENSE, public=1)).public).code == 8


def test_hidden_cards_are_stripped_even_for_their_owner():
    v = Q.card_views(card(9, POS_FACEDOWN_DEFENSE, hidden=1))
    assert Q.parse_card(v.owner).code is None
    assert Q.parse_card(v.full).code == 9              # the replay still has it


def test_location_views_keep_empty_slots():
    raw = location(card(1, POS_FACEUP_ATTACK), None, card(2, POS_FACEDOWN_DEFENSE))
    v = Q.location_views(raw)
    pub = Q.parse_location(v.public)
    assert [c.code if c else None for c in pub] == [1, None, None]
    assert pub[2] is not None and pub[2].position == POS_FACEDOWN_DEFENSE
    assert [c.code if c else None for c in Q.parse_location(v.owner)] == [1, None, 2]
    assert struct.unpack_from("<I", v.public)[0] == len(v.public) - 4


def test_parse_card_fields():
    counters = entry(QUERY_COUNTERS, struct.pack("<II", 1, 0x1001 | (3 << 16)))
    equip = entry(QUERY_EQUIP_CARD, struct.pack("<BBII", 1, 4, 2, 1))
    q = Q.parse_card(card(42, POS_FACEUP_ATTACK, attack=-2, extra=(equip, counters)))
    assert (q.code, q.attack, q.level) == (42, -2, 4)
    assert q.counters == {0x1001: 3}
    assert q.equip_card.controller == 1 and q.equip_card.sequence == 2
    assert q.reason_card is None and q.known


def test_view_cache_reuses_results():
    cache = Q.ViewCache(limit=2)
    raw = location(card(1, POS_FACEUP_ATTACK))
    assert cache.get(raw, True) is cache.get(raw, True)
    cache.get(location(card(2, 1)), True)
    cache.get(location(card(3, 1)), True)              # over the limit: cleared, still correct
    assert Q.parse_location(cache.get(raw, True).full)[0].code == 1


def test_parse_field():
    raw = struct.pack("<I", 0xD1800)
    for lp in (8000, 7000):
        raw += struct.pack("<I", lp) + b"\x01\x01" + struct.pack("<I", 2) + b"\0" * 6 + b"\0" * 8
        raw += struct.pack("<6I", 30, 5, 2, 1, 15, 0)
    raw += struct.pack("<I", 1) + struct.pack("<I", 99) + struct.pack("<BBII", 0, 8, 1, 1) + \
        struct.pack("<BBIQ", 0, 8, 1, 99 << 20)
    f = Q.parse_field(raw)
    assert f.players[1].lp == 7000 and f.players[0].mzone[0].overlay_count == 2
    assert f.players[0].mzone[1] is None and f.players[0].deck == 30
    assert f.chain[0].code == 99 and f.chain[0].description == 99 << 20


def test_field_lp_is_signed_after_overkill():
    raw = struct.pack("<I", 0)
    for lp in (6700, -2100):
        raw += struct.pack("<i", lp) + b"\0" * 15 + struct.pack("<6I", 30, 5, 0, 0, 15, 0)
    raw += struct.pack("<I", 0)
    state = Q.parse_field(raw)
    assert [p.lp for p in state.players] == [6700, -2100]
