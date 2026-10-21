"""describe / validate / rules over every decision in the saved regression cases."""

import copy
import os

import pytest

from conftest import CASES, case_id, load_case
from ygo_agent.agent.describe import Describer
from ygo_agent.agent.profile import Profile
from ygo_agent.agent.rules import Context, Rules
from ygo_agent.agent.validate import validate

pytestmark = pytest.mark.skipif(not CASES, reason="no saved cases")


def deck_of(path):
    return path.split(os.sep)[-3]


def decisions(case):
    return [m for m in case["messages"] if m.get("t") == "decide"]


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_every_decision_describes(path, db):
    describer = Describer(db)
    for d in decisions(load_case(path)):
        question = describer.question(d)
        options = describer.options(d)
        # "place" (zone choice) never reaches the model: a built-in rule leaves it to WindBot.
        assert question and (d["kind"] == "place" or "Decision of kind" not in question), d["kind"]
        assert len(options) == len(d.get("options", []))
        assert all(options), f"empty option text in decision #{d['id']}"
        if d.get("state", {}).get("me"):
            state = describer.state(d["state"])
            assert state.startswith("TURN ") and "YOUR HAND" in state and "OPPONENT MONSTERS" in state


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_events_describe(path, db):
    describer = Describer(db)
    lines = [describer.event(m) for m in load_case(path)["messages"] if m.get("t") == "event"]
    assert any(line and line.startswith("DUEL START") for line in lines)
    assert any(line and line.startswith("=== TURN") for line in lines)


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_expected_and_rejected_choices_are_legal(path):
    case = load_case(path)
    d = decisions(case)[-1]
    for choice in case.get("expect", []) + case.get("reject", []):
        assert validate(d, choice) is None, f"{choice} isn't even a legal reply"
    assert case["source"].startswith("games/"), "source must be a relative games/<dir> #N pointer"


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_rules_never_contradict_a_case(path, db, cfg):
    """A rule may answer a saved decision, but only with an accepted choice."""
    profile = Profile(deck_of(path), db, cfg)
    rules = Rules(profile.dir)
    case = load_case(path)
    for d in decisions(case):
        decided, source = rules.decide(Context(copy.deepcopy(d), db, Describer(db), profile))
        if decided is not None and decided.choice is not None:
            assert validate(d, decided.choice) is None, f"{source} gave an illegal reply to #{d['id']}"
    last = decisions(case)[-1]
    decided, source = rules.decide(Context(copy.deepcopy(last), db, Describer(db), profile))
    if decided is not None:
        assert not case.get("expect") or decided.choice in case["expect"], source
        assert decided.choice not in case.get("reject", []), source


def test_validate_kinds():
    assert validate({"kind": "idle", "options": [{}, {}]}, [1]) is None
    assert validate({"kind": "idle", "options": [{}, {}]}, [2])
    assert validate({"kind": "idle", "options": [{}, {}]}, [0, 1])
    assert validate({"kind": "chain", "options": [{}], "forced": False}, []) is None
    assert validate({"kind": "chain", "options": [{}], "forced": True}, [])
    assert validate({"kind": "effect_yn"}, [1]) is None
    assert validate({"kind": "effect_yn"}, [2])
    card = {"kind": "select_card", "options": [{}, {}, {}], "min": 1, "max": 2, "cancelable": False}
    assert validate(card, [0, 2]) is None
    assert validate(card, [])
    assert validate(dict(card, cancelable=True), []) is None
    assert validate(card, [1, 1])
    unselect = {"kind": "select_unselect", "options": [{}, {}], "min": 1, "max": 2}
    assert validate(unselect, [])
    assert validate(dict(unselect, finishable=True), []) is None
    assert validate(unselect, [1, 0]) is None  # partial picks: the agent plans the rest
    summ = {"kind": "select_sum", "options": [{"v1": 3, "v2": 0}, {"v1": 6, "v2": 0}, {"v1": 1, "v2": 0}],
            "min": 1, "max": 3, "sum": 6, "exact": False}
    assert validate(summ, [1]) is None
    assert validate(summ, [0, 2])
    assert validate(dict(summ, exact=True), [0, 2])
    assert validate({"kind": "announce_attrib", "options": [1, 2, 4], "count": 2}, [0, 2]) is None
    assert validate({"kind": "announce_attrib", "options": [1, 2, 4], "count": 2}, [0])
