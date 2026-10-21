"""The heuristic and random backends: always a legal reply on every saved decision, and sensible heuristic play."""

import copy

import pytest

from helpers import CASES, case_id, decisions, load_case
from ygo_agent import backends
from ygo_agent.agent.prompts import SCHEMA
from ygo_agent.agent.validate import validate
from ygo_agent.backends import Request
from ygo_agent.backends.heuristic import Policy, first_legal, sum_pick
from ygo_agent.backends.random_ import RandomPolicy


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_heuristic_and_random_are_always_legal(path, db):
    case = load_case(path)
    heuristic = Policy(db)
    randoms = [RandomPolicy(seed) for seed in range(5)]
    blind = Policy(None)  # without card data too
    for d in decisions(case):
        for policy in [heuristic, blind] + randoms:
            choice = policy.choose(copy.deepcopy(d))
            assert validate(d, choice) is None, (type(policy).__name__, d["kind"], d["id"], choice)
        assert validate(d, first_legal(d)) is None, (d["kind"], d["id"])


def test_random_is_seedable(db):
    d = decisions(load_case(CASES[0]))
    a = [RandomPolicy(7).choose(x) for x in d]
    assert a == [RandomPolicy(7).choose(x) for x in d]


def test_backends_answer_through_sessions(db):
    d = decisions(load_case(CASES[0]))[3]
    for kind in ("heuristic", "random"):
        session = backends.create({"name": kind, "type": kind, "seed": 3}, db=db).open_session("ignored", SCHEMA)
        reply, info = session.ask(Request("text", d, SCHEMA, 5))
        assert validate(d, reply["choice"]) is None and reply["why"] and info["replies"] == 1
        assert backends.label({"name": kind, "type": kind}) == kind
    reply, info = session.ask(Request("text only", None, SCHEMA, 5))
    assert reply is None and "decision" in info["error"]


# ---- heuristic behaviour on hand-made boards ----

def card(id_, c=0, l=0x4, s=0, p=0x1, atk=0, df=0, lv=4):
    return {"id": id_, "c": c, "l": l, "s": s, "p": p, "atk": atk, "def": df, "lv": lv, "rk": 0, "lk": 0}


def state(me_mz=(), opp_mz=(), turn_player=0, phase=0x8, chain=(), summon_player=-1, hand=()):
    def side(mz, h=()):
        zones = [None] * 7
        for c_ in mz:
            zones[c_["s"]] = c_
        return {"lp": 8000, "hand": list(h), "mz": zones, "sz": [None] * 8, "gy": [], "ban": [], "deck": 30,
                "extra": []}
    return {"turn": 3, "turn_player": turn_player, "phase": phase, "me": side(me_mz, hand), "opp": side(opp_mz),
            "chain": list(chain), "chain_targets": [], "last_summoned": [], "summon_player": summon_player,
            "battling": [None, None]}


def test_battle_attacks_only_into_weaker_monsters():
    mine = card(1, atk=2500)
    strong = card(2, c=1, s=1, atk=3000)
    d = {"kind": "battle", "state": state([mine], [strong]),
         "options": [{"a": "attack", "card": mine, "direct": False}, {"a": "to_main2"}, {"a": "to_end"}]}
    assert Policy().choose(d) == [1]  # don't attack into a stronger known monster
    weak = card(3, c=1, s=2, atk=1800)
    d["state"] = state([mine], [strong, weak])
    policy = Policy()
    assert policy.choose(d) == [0]
    target = {"kind": "select_card", "hint": 549, "min": 1, "max": 1, "cancelable": True,
              "state": d["state"], "options": [strong, weak]}
    assert policy.choose(target) == [1]
    d["options"][0]["direct"] = True
    d["state"] = state([mine], [strong])
    policy = Policy()
    assert policy.choose(d) == [0] and policy.why == "attack directly"


def test_main_phase_summons_the_strongest_and_sets_traps_before_ending(db):
    weak = card(1, l=0x2, atk=1000, lv=4)
    strong = card(2, l=0x2, atk=1900, lv=4)
    trap = {"id": 80254726, "c": 0, "l": 0x2, "s": -1, "p": 10, "atk": 0, "def": 0, "lv": 0, "rk": 0, "lk": 0}
    quick = dict(trap, id=27243130)  # Forbidden Lance: kept for the opponent's turn, never activated in Main Phase
    s = state(phase=0x4)
    d = {"kind": "idle", "state": s, "options": [{"a": "activate", "card": quick, "desc": 0},
                                                 {"a": "summon", "card": weak}, {"a": "summon", "card": strong},
                                                 {"a": "set_spell", "card": trap}, {"a": "to_end"}]}
    policy = Policy(db)
    assert policy.choose(d) == [2]
    d["options"] = [{"a": "set_spell", "card": trap}, {"a": "to_end"}]
    assert policy.choose(d) == [0] and "Set a trap" in policy.why
    assert policy.choose(d) == [0]
    assert policy.choose(d) == [1]  # never the same action more than twice a turn
    stronger = state([], [card(9, c=1, atk=2800)], phase=0x4)
    d = {"kind": "idle", "state": stronger, "options": [{"a": "summon", "card": strong},
                                                        {"a": "set_monster", "card": strong}, {"a": "to_end"}]}
    assert Policy(db).choose(d) == [1]  # Set rather than summon into a bigger monster


def test_chain_responds_only_to_the_opponent():
    hand_trap = card(10, l=0x2, atk=0)
    opts = [{"a": "activate", "card": hand_trap, "desc": 0}]
    mine = {"kind": "chain", "forced": False, "options": opts, "state": state(phase=0x4)}
    assert Policy().choose(mine) == []
    theirs = dict(mine, state=state(phase=0x4, turn_player=1, chain=[{"id": 5, "player": 1, "desc": 0}]))
    assert Policy().choose(theirs) == [0]
    summon = dict(mine, state=state(phase=0x4, turn_player=1, summon_player=1))
    assert Policy().choose(summon) == [0]
    quiet = dict(mine, state=state(phase=0x8, turn_player=1))
    assert Policy().choose(quiet) == []
    trigger = card(11, l=0x10)  # its own GY effect during its own turn
    own = {"kind": "chain", "forced": False, "options": [{"a": "activate", "card": trigger, "desc": 0}],
           "state": state(phase=0x4)}
    assert Policy().choose(own) == [0]
    forced = dict(mine, forced=True)
    assert Policy().choose(forced) == [0]


def test_targets_costs_and_yes_no():
    mine_weak, mine_strong = card(1, atk=500), card(2, s=1, atk=2500)
    theirs_weak, theirs_strong = card(3, c=1, atk=1000), card(4, c=1, s=1, atk=3000)
    opts = [mine_weak, mine_strong, theirs_weak, theirs_strong]
    base = {"kind": "select_card", "min": 1, "max": 1, "cancelable": False, "state": state(), "options": opts}
    assert Policy().choose(dict(base, hint=502)) == [3]   # destroy: their strongest
    assert Policy().choose(dict(base, hint=501, options=opts[:2])) == [0]  # discard: our weakest
    assert Policy().choose(dict(base, hint=509, options=opts[:2])) == [1]  # Special Summon: our best
    assert Policy().choose({"kind": "effect_yn", "state": state(), "card": mine_weak, "desc": 0}) == [1]
    assert Policy().choose({"kind": "yesno", "state": state(), "desc": 93}) == [0]
    unselect = {"kind": "select_unselect", "min": 1, "max": 2, "hint": 512, "finishable": True, "cancelable": True,
                "selected": [mine_weak], "state": state(), "options": [mine_strong]}
    assert Policy().choose(unselect) == []  # materials: stop as soon as the selection is valid


def test_select_sum_picks_the_cheapest_exact_set():
    opts = [dict(card(1, atk=2500), v1=6, v2=0), dict(card(2, s=1, atk=300), v1=4, v2=0),
            dict(card(3, s=2, atk=200), v1=2, v2=0)]
    d = {"kind": "select_sum", "sum": 6, "min": 1, "max": 3, "exact": False, "hint": 500, "state": state(),
         "options": opts}
    assert Policy().choose(d) == [1, 2]  # two small monsters instead of the 2500-ATK one
    assert sum_pick(dict(d, exact=True, sum=5), lambda i: 1) is None
    assert validate(d, first_legal(d)) is None


def test_place_and_announces():
    assert Policy().choose({"kind": "place", "state": state(), "available": 0b10100}) == [0b100]
    attr = {"kind": "announce_attrib", "count": 1, "options": [1, 2, 4], "state": state()}
    assert validate(attr, Policy().choose(attr)) is None
    assert Policy().choose({"kind": "announce_number", "options": [1, 2, 3], "state": state()}) == [2]
