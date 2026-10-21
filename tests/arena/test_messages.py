"""The message decoder against real core buffers (captured from 150 games), and every response encoder."""

import json
import os
import struct

import pytest

from ygo_agent.arena import messages as M
from ygo_agent.arena.buffer import LocInfo, Writer
from ygo_agent.core.constants import MSG_NAMES, Msg

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
with open(os.path.join(FIXTURES, "messages.json")) as f:
    CAPTURED = {name: [bytes.fromhex(h) for h in hexes] for name, hexes in json.load(f).items()}


@pytest.mark.parametrize("name", sorted(CAPTURED))
def test_captured_messages_decode_strictly(name):
    for raw in CAPTURED[name]:
        msg = M.decode(raw, strict=True)
        assert msg.name == name
        assert msg.raw == raw
        assert M.render(msg)  # never raises, never empty


def test_capture_covers_the_common_messages():
    must = {"MOVE", "DRAW", "CHAINING", "SELECT_IDLECMD", "SELECT_BATTLECMD", "SELECT_CHAIN", "SELECT_CARD",
            "SELECT_PLACE", "SELECT_POSITION", "SELECT_EFFECTYN", "SELECT_YESNO", "SELECT_OPTION",
            "SELECT_UNSELECT_CARD", "SELECT_SUM", "SELECT_TRIBUTE", "UPDATE_DATA", "UPDATE_CARD", "WIN",
            "NEW_TURN", "NEW_PHASE", "HINT", "START", "SELECT_COUNTER", "ANNOUNCE_CARD"}
    assert must <= set(CAPTURED)


def test_every_message_type_has_a_decoder():
    known = set(M.message_types())
    unused = {Msg.BE_CHAIN_TARGET, Msg.CREATE_RELATION, Msg.RELEASE_RELATION, Msg.CUSTOM_MSG}  # never emitted
    assert {int(m) for m in Msg} - {int(u) for u in unused} <= known


def test_unknown_and_truncated_messages():
    assert isinstance(M.decode(bytes([200, 1, 2])), M.Unknown)
    bad = M.decode(bytes([Msg.MOVE, 1, 2]))
    assert isinstance(bad, M.Unknown) and bad.error
    with pytest.raises(M.MessageError):
        M.decode(bytes([Msg.MOVE, 1, 2]), strict=True)


def _loc(c, l, s, p=0):
    return LocInfo(c, l, s, p).pack()


def test_synthetic_layouts_for_rare_messages():
    """Messages the captured games didn't produce, built from the core's writers."""
    cases = {
        Msg.TOSS_COIN: (bytes([Msg.TOSS_COIN, 1, 2, 1, 0]), lambda m: m.results == [1, 0]),
        Msg.TOSS_DICE: (bytes([Msg.TOSS_DICE, 0, 1, 6]), lambda m: m.results == [6]),
        Msg.HAND_RES: (bytes([Msg.HAND_RES, 1 + (3 << 2)]), lambda m: m.hands == (1, 3)),
        Msg.ROCK_PAPER_SCISSORS: (bytes([Msg.ROCK_PAPER_SCISSORS, 1]), lambda m: m.player == 1),
        Msg.ANNOUNCE_RACE: (bytes([Msg.ANNOUNCE_RACE, 0, 1]) + struct.pack("<Q", 0x2001),
                            lambda m: m.available == 0x2001),
        Msg.DECK_TOP: (bytes([Msg.DECK_TOP, 1]) + struct.pack("<III", 0, 89631139, 0x4),
                       lambda m: m.code == 89631139),
        Msg.SWAP: (bytes([Msg.SWAP]) + struct.pack("<I", 5) + _loc(0, 4, 1, 1) + struct.pack("<I", 6)
                   + _loc(1, 4, 2, 1), lambda m: m.location2.controller == 1),
        Msg.SHUFFLE_SET_CARD: (bytes([Msg.SHUFFLE_SET_CARD, 4, 2]) + _loc(0, 4, 0, 8) + _loc(0, 4, 1, 8)
                               + _loc(0, 4, 1, 8) + _loc(0, 0, 0, 0), lambda m: len(m.current) == 2),
        Msg.SWAP_GRAVE_DECK: (bytes([Msg.SWAP_GRAVE_DECK, 0]) + struct.pack("<II", 3, 1) + b"\x05",
                              lambda m: m.extra_mask == b"\x05"),
        Msg.REMOVE_CARDS: (bytes([Msg.REMOVE_CARDS]) + struct.pack("<I", 1) + _loc(0, 4, 2, 1),
                           lambda m: m.cards[0].sequence == 2),
        Msg.CANCEL_TARGET: (bytes([Msg.CANCEL_TARGET]) + _loc(0, 8, 1, 1) + _loc(1, 4, 0, 1),
                            lambda m: m.target.controller == 1),
        Msg.MATCH_KILL: (bytes([Msg.MATCH_KILL]) + struct.pack("<I", 12345), lambda m: m.code == 12345),
        Msg.AI_NAME: (bytes([Msg.AI_NAME]) + struct.pack("<H", 3) + b"Bot\0", lambda m: m.text == "Bot"),
        Msg.TAG_SWAP: (bytes([Msg.TAG_SWAP, 0]) + struct.pack("<5I", 30, 1, 0, 1, 0) + struct.pack("<II", 7, 10)
                       + struct.pack("<II", 8, 5), lambda m: m.hand_cards == [(7, 10)]),
        Msg.CONFIRM_EXTRATOP: (bytes([Msg.CONFIRM_EXTRATOP, 0]) + struct.pack("<IIBBI", 1, 99, 0, 0x40, 3),
                               lambda m: m.cards[0].code == 99),
        Msg.RELOAD_FIELD: (bytes([Msg.RELOAD_FIELD]) + struct.pack("<I", 0xD1800) + (struct.pack("<I", 8000)
                           + b"\0" * 15 + struct.pack("<6I", 35, 5, 0, 0, 15, 0)) * 2 + struct.pack("<I", 0),
                           lambda m: m.state.players[1].hand == 5),
    }
    for t, (raw, check) in cases.items():
        msg = M.decode(raw, strict=True)
        assert msg.type == t, MSG_NAMES[t]
        assert check(msg), MSG_NAMES[t]


# --- responses ---------------------------------------------------------------------------------------------

def test_idle_and_battle_encoding():
    assert M.SelectIdleCmd.respond(M.IdleAction.ACTIVATE, 2) == struct.pack("<i", 2 << 16 | 5)
    assert M.SelectIdleCmd.respond(M.IdleAction.END) == struct.pack("<i", 7)
    assert M.SelectBattleCmd.respond(M.BattleAction.ATTACK, 1) == struct.pack("<i", 1 << 16 | 1)
    idle = M.decode(CAPTURED["SELECT_IDLECMD"][0])
    assert idle.decode_response(idle.respond(M.IdleAction.SUMMON, 3)) == {"action": "summon", "index": 3}


def test_card_selection_encodings_all_decode():
    p = M.SelectCard(player=0, cancelable=True, min=1, max=3, cards=[M.CardRef(1, 0, 2, i) for i in range(10)])
    assert p.respond([0, 4]) == struct.pack("<iIII", 0, 2, 0, 4)
    assert p.decode_response(p.respond([0, 4])) == {"indices": [0, 4]}
    assert p.decode_response(p.respond(None)) == {"cancel": True}
    # EDOPro's client picks the most compact form: type 1 (u16), 2 (u8) or 3 (bit field)
    assert M.decode_cards(struct.pack("<iIHH", 1, 2, 3, 9), 10) == [3, 9]
    assert M.decode_cards(struct.pack("<iIBB", 2, 2, 3, 9), 10) == [3, 9]
    assert M.decode_cards(struct.pack("<iI", 3, (1 << 3) | (1 << 9)), 10) == [3, 9]


def test_simple_prompt_encodings():
    assert M.SelectChain.respond(None) == struct.pack("<i", -1)
    assert M.SelectChain.respond(2) == struct.pack("<i", 2)
    assert M.SelectEffectYn.respond(True) == struct.pack("<i", 1)
    assert M.SelectYesNo.respond(False) == struct.pack("<i", 0)
    assert M.SelectOption.respond(1) == struct.pack("<i", 1)
    assert M.SelectPosition.respond(0x8) == struct.pack("<i", 8)
    assert M.SelectUnselectCard.respond(None) == struct.pack("<i", -1)
    assert M.SelectUnselectCard.respond(4) == struct.pack("<ii", 1, 4)
    assert M.SelectCounter.respond([1, 0, 2]) == struct.pack("<hhh", 1, 0, 2)
    assert M.SortCard.respond(None) == b"\xff"
    assert M.SortCard.respond([1, 0, 2]) == b"\x01\x00\x02"
    assert M.SelectPlace.respond([(0, 4, 2)]) == b"\x00\x04\x02"
    assert M.AnnounceRace.respond(0x2000) == struct.pack("<Q", 0x2000)
    assert M.AnnounceAttrib.respond(0x10) == struct.pack("<I", 0x10)
    assert M.AnnounceCard.respond(89631139) == struct.pack("<i", 89631139)
    assert M.AnnounceNumber.respond(3) == struct.pack("<i", 3)
    assert M.RockPaperScissors.respond(2) == struct.pack("<i", 2)


def test_place_zones_follow_the_flag_layout():
    # Everything blocked except own monster zone 2 and the opponent's spell/trap zone 1.
    flag = 0xFFFFFFFF & ~(1 << 2) & ~(1 << (16 + 8 + 1))
    p = M.SelectPlace(player=1, count=1, flag=flag)
    assert p.zones == [(1, 0x4, 2), (0, 0x8, 1)]


def test_every_captured_prompt_decodes_its_own_response_shape():
    from ygo_agent.core.constants import PROMPT_MESSAGES
    for name, raws in CAPTURED.items():
        msg = M.decode(raws[0])
        if msg.type in PROMPT_MESSAGES:
            assert isinstance(msg, M.Prompt)
            assert hasattr(msg, "player")


def test_render_uses_card_names():
    class Names:
        def name(self, code):
            return {89631139: "Blue-Eyes White Dragon"}.get(code, str(code))
    raw = bytes([Msg.MOVE]) + struct.pack("<I", 89631139) + _loc(0, 2, 0, 10) + _loc(0, 4, 2, 1) + \
        struct.pack("<I", 0)
    assert "Blue-Eyes White Dragon" in M.render(M.decode(raw), Names())
    hidden = bytes([Msg.MOVE]) + struct.pack("<I", 0) + _loc(1, 1, 0, 10) + _loc(1, 2, 3, 10) + struct.pack("<I", 0)
    assert "(hidden)" in M.render(M.decode(hidden))


def test_writer_roundtrip():
    w = Writer().u8(1).u16(2).u32(3).i32(-4).u64(5).loc(LocInfo(1, 4, 2, 8))
    assert w.getvalue() == struct.pack("<BHIiQ", 1, 2, 3, -4, 5) + struct.pack("<BBII", 1, 4, 2, 8)
