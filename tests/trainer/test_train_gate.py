"""Condense and section rewrites are gated on the saved regression cases: an edit that makes them fail more often gets
one fix-up try with the failing cases as feedback, else the previous text stays. The case runs are faked here, except
in the last test, which replays a real saved case with a scripted player."""

import json

from fake_trainer import PLAYBOOK, make_trainer
from ygo_agent.trainer import playbook as pb
from ygo_agent.trainer.pipeline import case_losses

CASE = "set-ash-as-blocker-empty-field"


def score(cases):
    return {"hash": "x", "good": sum(g for g, _ in cases.values()), "total": sum(r for _, r in cases.values()),
            "cases": {k: {"good": g, "repeat": r, "choices": [[0]] * r} for k, (g, r) in cases.items()}}


def fake_scores(t, by_marker):
    """case_score() by a marker word in the text; records which texts were measured."""
    t.measured = []

    def case_score(text, label, allow_last=False):
        t.measured.append(label)
        return next(s for marker, s in by_marker.items() if marker in text)
    t.case_score = case_score


def version(marker, extra=""):
    return PLAYBOOK.replace("Make Rank 4s.", f"Make Rank 4s. {marker}{extra}")


def test_case_losses_compares_the_cases_both_measured():
    base = score({"a": (2, 2), "b": (1, 2)})
    assert case_losses(base, score({"a": (2, 2), "b": (2, 2), "new": (0, 2)})) == []  # a new case doesn't count
    assert case_losses(base, score({"a": (1, 2), "b": (2, 2)})) == []  # the same total: a trade, not a drop
    assert case_losses(base, score({"a": (0, 2), "b": (1, 2)})) == ["a"]


def test_an_edit_that_keeps_the_cases_passing_is_kept(tmp_path, cfg, db):
    t = make_trainer(tmp_path, cfg, db, lambda task, prompt: None)
    fake_scores(t, {"OLD": score({CASE: (1, 2)}), "NEW": score({CASE: (2, 2)})})
    text, record = t.gate("r1.review.r1-g1", version("OLD"), version("NEW"), "section edits")
    assert "NEW" in text and record["kept"] == "after" and record["before"] == "1/2" and record["after"] == "2/2"
    assert not t.calls and t.ws.state["gate_last"]["good"] == 2  # no fix-up call; the new score is the baseline


def test_a_worse_edit_gets_one_fix_up_with_the_failing_cases(tmp_path, cfg, db):
    revised = version("FIXED")

    def answer(task, prompt):
        assert task == "condense" and prompt.startswith("# Task: fix a playbook section edits")
        return {"playbook": revised, "removed": ["put the blocker principle back"]}
    t = make_trainer(tmp_path, cfg, db, answer)
    fake_scores(t, {"OLD": score({CASE: (2, 2)}), "NEW": score({CASE: (0, 2)}), "FIXED": score({CASE: (2, 2)})})
    text, record = t.gate("r1.review.r1-g1", version("OLD"), version("NEW"), "section edits")
    assert "FIXED" in text and record["kept"] == "revised" and record["revised"] == "2/2"
    prompt = t.calls[0]["prompt"]
    assert f"Case `{CASE}`" in prompt and "Set \"Ash Blossom" in prompt  # the right option, in words
    assert "0/2 runs right, 2/2 with the previous text" in prompt
    assert "## The previous playbook" in prompt and "## The changed playbook" in prompt


def test_when_the_fix_up_fails_too_the_previous_text_stays(tmp_path, cfg, db):
    t = make_trainer(tmp_path, cfg, db, lambda task, prompt: {"playbook": version("FIXED"), "removed": []})
    fake_scores(t, {"OLD": score({CASE: (2, 2)}), "NEW": score({CASE: (1, 2)}), "FIXED": score({CASE: (1, 2)})})
    text, record = t.gate("r1.condense", version("OLD"), version("NEW"), "condense")
    assert "OLD" in text and record["kept"] == "before" and record["failures"] == [CASE]
    assert len(t.calls) == 1  # one retry only


def test_a_fix_up_that_breaks_the_template_is_not_measured(tmp_path, cfg, db):
    t = make_trainer(tmp_path, cfg, db, lambda task, prompt: {"playbook": "## Game plan\n\nFIXED\n", "removed": []})
    fake_scores(t, {"OLD": score({CASE: (2, 2)}), "NEW": score({CASE: (0, 2)}), "FIXED": score({CASE: (2, 2)})})
    text, record = t.gate("r1.condense", version("OLD"), version("NEW"), "condense")
    assert "OLD" in text and record["kept"] == "before" and "revised" not in record


def test_no_saved_cases_means_no_gate(tmp_path, cfg, db):
    t = make_trainer(tmp_path, cfg, db, lambda task, prompt: None, cases=())
    assert t.case_score(version("OLD"), "x") is None
    assert t.gate("r1.condense", version("OLD"), version("NEW"), "condense") == (version("NEW"), None)
    t = make_trainer(tmp_path / "off", cfg, db, lambda task, prompt: None, gate_repeat=0)
    assert t.case_score(version("OLD"), "x") is None


def test_condense_keeps_the_longer_playbook_when_the_cases_get_worse(tmp_path, cfg, db):
    long = version("OLD", " filler" * 1300)
    short = version("NEW")

    def answer(task, prompt):
        if prompt.startswith("# Task: tighten"):
            return {"playbook": short, "removed": ["the filler"]}
        return {"playbook": version("FIXED"), "removed": []}
    t = make_trainer(tmp_path, cfg, db, answer)
    t.write_playbook(long)
    assert len(long.encode()) > pb.LIMIT_BYTES
    fake_scores(t, {"OLD": score({CASE: (2, 2)}), "NEW": score({CASE: (0, 2)}), "FIXED": score({CASE: (1, 2)})})
    t.condense("final")
    assert t.playbook() == long
    result = t.ws.result("final.condense")
    assert result["accepted"] is False and result["gate"]["kept"] == "before"
    fake_scores(t, {"OLD": score({CASE: (2, 2)}), "NEW": score({CASE: (2, 2)})})
    t.ws.forget("final.condense")
    t.condense("final")
    assert t.playbook() == short and t.ws.result("final.condense")["gate"]["kept"] == "after"


def test_case_score_replays_the_cases_and_caches_by_text(tmp_path, cfg, db):
    asked = []
    cfg["backends"]["player"] = {"type": "scripted", "policy": lambda d: asked.append(d["id"]) or [1]}
    t = make_trainer(tmp_path, cfg, db, lambda task, prompt: None, player_backend="player")
    first = t.case_score(PLAYBOOK, "r1.condense.before")
    assert first["cases"][CASE] == {"good": 2, "repeat": 2, "choices": [[1], [1]]} and len(asked) == 2
    assert t.case_score(PLAYBOOK, "again") == first and len(asked) == 2  # cached: same text, same cases
    t.ws.set("gate_last", first)
    assert t.case_score(version("UNMEASURED"), "x", allow_last=True) == first and len(asked) == 2
    assert t.ws.read("gates/r1.condense.before.md") == PLAYBOOK
    assert [e["kind"] for e in t.ws.state["ledger"]] == ["test"]
    json.dumps(t.ws.state)  # the scores are checkpointed with the rest of the state
