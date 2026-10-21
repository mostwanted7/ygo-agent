"""native_decide: core prompts → bridge-schema decisions, choices → responses, responses → choices (no EDOPro)."""

import struct

import pytest

from ygo_agent.arena import messages as M
from ygo_agent.arena.native_decide import ChoiceError, build, place_group, sum_ok
from ygo_agent.arena.native_view import Card, NativeView
from ygo_agent.core.cards import CardData
from ygo_agent.core.constants import OPCODE_ISCODE

HAND, MZONE, SZONE, GY, EXTRA, DECK = 0x2, 0x4, 0x8, 0x10, 0x40, 0x1


def i32(data):
    return struct.unpack("<i", data[:4])[0]


@pytest.fixture
def view():
    """Team 1's view (so local and core controllers differ), with a few tracked cards."""
    v = NativeView(1)
    v.piles[(1, HAND)] = [Card(1, 100), Card(2, 200)]
    v.piles[(1, EXTRA)] = [Card(3, 300)]
    v.zones[(1, MZONE)][2] = Card(4, 400, 1)
    v.zones[(0, MZONE)][0] = Card(5, 0, 8)      # the opponent's face-down monster
    v.piles[(1, DECK)] = [Card(6), Card(7)]
    return v


def roundtrip(d):
    for k in range(len(d.fields.get("options", []))):
        assert d.decode(d.encode([k])) == [k]


def ref(code, c, loc, seq, pos=0):
    return M.CardRef(code, c, loc, seq, pos)


def test_idle_order_and_codes(view):
    act = M.Activatable(100, 1, HAND, 0, 0, 1234 << 20, 0)
    p = M.SelectIdleCmd(1, summonable=[ref(200, 1, HAND, 1)], special_summonable=[ref(300, 1, EXTRA, 0)] * 2,
                        repositionable=[ref(400, 1, MZONE, 2)], monster_settable=[ref(200, 1, HAND, 1)],
                        spell_settable=[], activatable=[act], can_battle_phase=True, can_end_phase=True,
                        can_shuffle=False)
    d = build(p, view)
    assert [o["a"] for o in d.fields["options"]] == ["activate", "summon", "spsummon", "spsummon", "set_monster",
                                                     "reposition", "to_battle", "to_end"]
    assert d.fields["options"][0]["desc"] == 1234 << 20
    first = d.fields["options"][1]["card"]
    assert first["id"] == 200 and first["c"] == 0 and first["l"] == HAND and first["s"] == -1  # hand: s -1
    assert d.fields["options"][5]["card"]["s"] == 2
    # One card listed twice (two summon procedures): each option keeps its own core index.
    assert i32(d.encode([2])) == 0 << 16 | 1 and i32(d.encode([3])) == 1 << 16 | 1
    assert i32(d.encode([6])) == 6 and i32(d.encode([7])) == 7
    roundtrip(d)
    with pytest.raises(ChoiceError):
        d.encode([8])


def test_battle(view):
    p = M.SelectBattleCmd(1, activatable=[], attackable=[M.Attacker(400, 1, MZONE, 2, 0, True)], can_main2=True,
                          can_end_phase=False)
    d = build(p, view)
    assert d.fields["options"] == [{"a": "attack", "card": d.fields["options"][0]["card"], "direct": True},
                                   {"a": "to_main2"}]
    assert i32(d.encode([0])) == 1 and i32(d.encode([1])) == 2
    roundtrip(d)


def test_chain_windows(view):
    assert build(M.SelectChain(1, 0, False, 0, 0, []), view).kind is None
    forced = build(M.SelectChain(1, 0, True, 0, 0, [M.Activatable(400, 1, MZONE, 2, 1, 221, 0)]), view)
    assert forced.kind is None and i32(forced.auto) == 0
    two = [M.Activatable(400, 1, MZONE, 2, 1, 221, 0), M.Activatable(100, 1, HAND, 0, 0, 5 << 20, 0)]
    d = build(M.SelectChain(1, 0, False, 0, 0, two), view)
    assert d.kind == "chain" and d.fields["options"][0]["desc"] == 0 and d.fields["forced"] is False
    assert i32(d.encode([])) == -1 and d.decode(d.encode([])) == []
    roundtrip(d)
    with pytest.raises(ChoiceError):
        build(M.SelectChain(1, 0, True, 0, 0, two), view).encode([])


def test_questions(view):
    d = build(M.SelectEffectYn(1, ref(400, 1, MZONE, 2, 1), 221), view)
    assert d.fields["desc"] == -1 and d.fields["card"]["id"] == 400
    assert i32(d.encode([1])) == 1 and d.decode(d.encode([0])) == [0]
    assert build(M.SelectYesNo(1, 1989), view).kind is None
    assert build(M.SelectYesNo(1, 30), view).fields == {"desc": 30}
    assert build(M.SelectPosition(1, 400, 0x4), view).kind is None
    pos = build(M.SelectPosition(1, 400, 0x1 | 0x4 | 0x8), view)
    assert pos.fields == {"card_id": 400, "options": [1, 4, 8]} and i32(pos.encode([2])) == 8
    roundtrip(pos)
    opt = build(M.SelectOption(1, [10, 20]), view)
    assert opt.fields["options"] == [10, 20] and i32(opt.encode([1])) == 1


def test_select_card_hints_and_cancel(view):
    view.hint = 506
    p = M.SelectCard(1, True, 1, 2, [ref(0, 0, MZONE, 0, 8), ref(100, 1, HAND, 0), ref(55, 1, DECK, 1)])
    d = build(p, view)
    assert d.fields["hint"] == 506 and view.hint == 0  # used up, as WindBot does
    opp, mine, deck = d.fields["options"]
    assert opp["id"] == 0 and opp["c"] == 1 and opp["s"] == 0
    assert deck["id"] == 55 and deck["s"] == -1  # never a Deck sequence
    assert i32(d.encode([])) == -1 and d.decode(d.encode([])) == []
    assert d.decode(d.encode([0, 2])) == [0, 2]
    with pytest.raises(ChoiceError):
        d.encode([1, 1])
    p0 = M.SelectCard(1, False, 0, 1, [ref(100, 1, HAND, 0)])
    assert build(p0, view).encode([]) == M.encode_cards([])


def test_unselect_keeps_the_hint(view):
    view.hint = 511
    p = M.SelectUnselectCard(1, True, False, 1, 2, [ref(100, 1, HAND, 0)], [ref(200, 1, HAND, 1)])
    d = build(p, view)
    assert d.fields["hint"] == 511 and view.hint == 511 and d.fields["cancelable"] is True
    assert d.fields["selected"][0]["id"] == 200
    assert i32(d.encode([])) == -1 and d.decode(d.encode([0])) == [0]
    assert d.decode(M.SelectUnselectCard.respond(1)) is None  # unselecting isn't in the schema


def test_select_sum(view):
    must = [M.SumCard(400, 1, MZONE, 2, 1, 4)]
    cards = [M.SumCard(100, 1, HAND, 0, 0, (2 << 16) | 3), M.SumCard(200, 1, HAND, 1, 0, 4)]
    exact = M.SelectSum(1, False, 8, 1, 2, must, cards)
    d = build(exact, view)
    assert d.fields["sum"] == 4 and d.fields["exact"] is True
    assert (d.fields["options"][0]["v1"], d.fields["options"][0]["v2"]) == (2, 3)
    assert sum_ok(exact, [1]) and not sum_ok(exact, [0])
    with pytest.raises(ChoiceError):
        d.encode([0])
    assert d.decode(d.encode([1])) == [1]
    ritual = M.SelectSum(1, True, 6, 0, 0, [], [M.SumCard(100, 1, HAND, 0, 0, 4), M.SumCard(200, 1, HAND, 1, 0, 4)])
    r = build(ritual, view)
    assert r.fields["max"] == 99 and r.fields["exact"] is False
    assert sum_ok(ritual, [0, 1]) and not sum_ok(ritual, [0])
    many = M.SelectSum(1, True, 6, 0, 0, [], [M.SumCard(i, 1, HAND, 0, 0, 4) for i in range(3)])
    assert not sum_ok(many, [0, 1, 2])  # a card it doesn't need: the engine refuses that


def test_place_groups_and_zone_order(view):
    # own Monster Zones 0, 2 and 3 free (a set bit means "not selectable")
    flag = ~((1 << 0) | (1 << 2) | (1 << 3)) & 0xFFFFFFFF
    assert place_group(flag) == (0, MZONE, 0b1101)
    view.hint = 4031928
    d = build(M.SelectPlace(1, 1, flag), view)
    assert d.fields == {"card_id": 4031928, "player": 0, "location": MZONE, "available": 0b1101}
    assert d.encode([0b1101]) == bytes((1, MZONE, 2))           # WindBot's order: the middle zone first
    assert d.encode([0b1]) == bytes((1, MZONE, 0))
    assert d.encode([0b10]) == bytes((1, MZONE, 2))             # not free: WindBot's order among the free ones
    assert d.decode(d.encode([0b1000])) == [0b1000]
    two = build(M.SelectPlace(1, 2, flag), view).encode([0b1])
    assert len(two) == 6 and two[:3] == bytes((1, MZONE, 0))
    pend = ~((1 << 14) | (1 << 15)) & 0xFFFFFFFF
    p = build(M.SelectPlace(1, 1, pend), view)
    assert p.fields["location"] == 0x200 and p.fields["available"] == 0b11
    assert p.encode([0b01]) == bytes((1, SZONE, 6)) and p.encode([0b11]) == bytes((1, SZONE, 7))
    assert p.decode(p.encode([0b01])) == [0b01]
    opp = ~((1 << 16) | (1 << 1)) & 0xFFFFFFFF
    assert place_group(opp, disfield=True) == (1, MZONE, 0b1)
    dis = build(M.SelectDisfield(1, 1, opp), view)
    assert dis.encode([1]) == bytes((0, MZONE, 0))  # the opponent's zone, in core player terms


def test_declarations(view):
    attr = build(M.AnnounceAttrib(1, 2, 0x1 | 0x20 | 0x10), view)
    assert attr.fields == {"options": [0x1, 0x10, 0x20], "count": 2}
    assert struct.unpack("<I", attr.encode([0, 2]))[0] == 0x21 and attr.decode(attr.encode([0, 2])) == [0, 2]
    with pytest.raises(ChoiceError):
        attr.encode([0])
    race = build(M.AnnounceRace(1, 1, 1 << 40 | 1 << 2), view)
    assert race.fields["options"] == [1 << 2, 1 << 40] and race.decode(race.encode([1])) == [1]
    num = build(M.AnnounceNumber(1, [3, 5, 7]), view)
    assert i32(num.encode([2])) == 2 and num.decode(num.encode([2])) == [2]

    class Cards:
        cards = {c: CardData(code=c, alias=0, setcodes=(), type=0x21, level=4, attribute=1, race=1, attack=0,
                             defense=0, lscale=0, rscale=0, link_marker=0) for c in (111, 222)}
    view.cards = Cards()
    card = build(M.AnnounceCard(1, []), view)  # an empty program declares nothing...
    assert card.fields["options"] == []
    program = [111, OPCODE_ISCODE]  # exactly card 111
    named = build(M.AnnounceCard(1, program), view)
    assert named.fields["options"] == [111]
    assert i32(named.encode([111])) == 111 and i32(named.encode([0])) == 111  # a code, or an index into the list
    with pytest.raises(ChoiceError):
        named.encode([222])


def test_prompts_answered_without_asking(view):
    counter = build(M.SelectCounter(1, 0x1, 3, [M.CounterCard(400, 1, MZONE, 2, 0, 2),
                                               M.CounterCard(500, 0, SZONE, 1, 0, 5)]), view)
    assert counter.kind is None and counter.auto == struct.pack("<hh", 2, 1)
    sort = build(M.SortCard(1, [M.CardRef(1, 1, DECK, 0), M.CardRef(2, 1, DECK, 1)]), view)
    assert sort.kind is None and sort.auto == bytes((0, 1))
    assert build(M.SortChain(1, [M.CardRef(1, 1, MZONE, 0)]), view).auto == b"\xff"
    assert 1 <= i32(build(M.RockPaperScissors(1), view).auto) <= 3
