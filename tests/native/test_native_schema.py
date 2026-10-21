"""The protocol checks in schema.py describe the bridge: every message of the saved bridge fixtures passes them, and
they catch what they should (no EDOPro needed; native games are checked in test_native_games.py)."""

import copy

import pytest

from helpers import CASES, case_id, load_case
from schema import decision_errors, event_errors


@pytest.mark.skipif(not CASES, reason="no saved cases")
@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_bridge_fixtures_conform(path):
    for m in load_case(path)["messages"]:
        errors = decision_errors(m) if m.get("t") == "decide" else event_errors(m)
        assert not errors, (errors, m.get("kind") or m.get("e"))


@pytest.mark.skipif(not CASES, reason="no saved cases")
def test_schema_catches_broken_messages():
    d = next(m for m in load_case(CASES[0])["messages"] if m.get("t") == "decide" and m["kind"] == "idle")
    bad = copy.deepcopy(d)
    bad["options"].reverse()
    assert decision_errors(bad)  # out of order
    bad = copy.deepcopy(d)
    bad["state"]["me"]["mz"] = bad["state"]["me"]["mz"][:5]
    assert decision_errors(bad)
    bad = copy.deepcopy(d)
    bad["options"][0]["card"]["zz"] = 1
    assert decision_errors(bad)
    assert event_errors({"t": "event", "e": "move", "id": 1, "from": {}, "to": {}, "reason": 0})
    assert not event_errors({"t": "event", "e": "coin", "player": 0, "results": [1]})
    assert event_errors({"t": "event", "e": "nonsense"})
