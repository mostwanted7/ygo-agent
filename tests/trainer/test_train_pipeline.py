"""The whole pipeline on a tiny budget: a scripted reviewer, the heuristic player, in-process opponents. Real duels,
so it needs the EDOPro install; no model is called."""

import json
import os

import pytest

from ygo_agent.trainer import playbook as pb
from ygo_agent.trainer.pipeline import Options, Trainer
from ygo_agent.trainer.workspace import TrainerError

pytestmark = pytest.mark.integration

PLAYBOOK = """## How to use this playbook

Principles, not scripts: deviate when the board calls for it.

## Game plan

Make Rank 4s.

## Card roles

- **Geargiarsenal**: Tribute it to Special Summon a Geargia from the Deck (script: Cost.SelfTribute).
- **Gear Gigant X**: 2 Level 4 Machines.

## Situational considerations

- **Consider Gear Gigant X when a Geargiano is in the GY**, because its float then has a target.

## Example sequences

**Line 1: Geargiarsenal + any Geargia** *(unverified)*
1. Normal Summon Geargiarsenal, Tribute it for Geargiarmor.

## Known pitfalls (from reviewed games, newest first)

None yet: specific mistakes from reviewed games go here, one or two lines each.
"""
QUOTE = {"source": "script", "file": "c73428497.lua", "decision": 0, "quote": "e2:SetCost(Cost.SelfTribute)"}


def policy(calls):
    def answer(req):
        calls.append(req["task"])
        t = req["task"]
        if t == "study":
            return {"playbook": PLAYBOOK, "go_first": False, "go_first_reason": "traps want the opponent to commit",
                    "open_questions": ["does Geargiarmor's flip miss timing?"],
                    "lines": [{"id": "L1", "name": "Line 1: Geargiarsenal + any Geargia", "going": "first",
                               "key_cards": ["Geargiarsenal"], "expected_board": ["Geargiarmor"], "steps": "NS"}],
                    "card_checks": [{"card": "Geargiarsenal", "file": "c73428497.lua", "fact": "cost",
                                     "quote": "e2:SetCost(Cost.SelfTribute)"},
                                    {"card": "Geargiarsenal", "file": "c73428497.lua", "fact": "made up",
                                     "quote": "e9:SetCountLimit(5,id)"}]}
        if t == "lab-review":
            assert "Lab results" in req["prompt"] and "hand-01" in req["prompt"]
            return {"verification": [{"line": "L1", "status": "verified", "hands": ["hand-01"], "reason": "ok"}],
                    "sections": [{"heading": "## Going second / breaking boards", "content": "- Duster first."}],
                    "new_lines": [], "lessons": [], "player_errors": [], "open_questions": []}
        if t == "review":
            assert "Task: review game" in req["prompt"]
            return {"summary": "fine", "significant_mistakes": 1,
                    "mistakes": [{"decision": 1, "turn": 1, "what": "x", "better": "y", "severity": "major",
                                  "kind": "strategy", "verified": True, "evidence": [QUOTE]}],
                    "lessons": [{"text": "**When Geargiarsenal is on the field, Tribute it** for a body.",
                                 "decisions": [1], "severity": "major", "evidence": [QUOTE]},
                                {"text": "**An invented ruling.**", "decisions": [], "severity": "minor",
                                 "evidence": [{**QUOTE, "quote": "Duel.Draw(tp,3,REASON_EFFECT)"}]}],
                    "repeated": [], "sections": [], "confirmed_lines": [], "general": [
                        {"text": "Set Quick-Plays before ending.", "evidence": [QUOTE]}],
                    "test_cases": [{"decision": 1, "name": "first decision", "expect": [], "reject": [[99]],
                                    "note": "illegal index: dropped"}], "rule_proposals": []}
        raise AssertionError(t)
    return answer


def make(cfg_dir, calls, budget=None, resume=False, rounds=2, games=1, cost=0.5, engine=None, db=None):
    from ygo_agent.config import load_config
    cfg = load_config(local=None, overrides={"games_dir": str(cfg_dir / "games"), "chat": "off"})
    cfg["backends"]["fake"] = {"type": "scripted", "policy": policy(calls), "cost_per_call": cost}
    o = Options(ydk=os.path.join(engine.install.deck_dir, "Geargia.ydk"), name="geartest", backend="fake",
                player_backend="heuristic", opponents=["heuristic:saffira", "windbot:Dark Magician"], lab_hands=3,
                games=games, max_rounds=rounds, budget=budget, lab_parallel=2, parallel=1, test_repeat=1, echo="off")
    return Trainer(o, cfg, db=db, engine=engine, resume=resume, quiet=True)


@pytest.fixture
def geargia(engine):
    if not os.path.isfile(os.path.join(engine.install.deck_dir, "Geargia.ydk")):
        pytest.skip("no Geargia.ydk in the EDOPro deck folder")


def test_dry_run_of_the_whole_pipeline(tmp_path, decks_dir, engine, agent_db, geargia, quiet):
    calls = []
    t = make(tmp_path, calls, engine=engine, db=agent_db)
    assert t.run() == "done"
    deck = decks_dir / "geartest"
    train = deck / "train"
    for f in ("deck.ydk", "deck.json", "rules.py", "playbook.md"):
        assert (deck / f).is_file(), f
    assert json.loads((deck / "deck.json").read_text()) == {"name": "Geargia", "ydk": "deck.ydk", "go_first": False}
    assert "RULES = []" in (deck / "rules.py").read_text()
    for f in ("dossier.md", "cards.json", "scripts/c73428497.lua", "study/playbook-draft.md", "study/card-checks.md",
              "round-1/lab/lab-results.md", "round-1/lab/hand-01/game.md", "round-1/playbook.md",
              "general-proposals.md", "train-report.md", "calls/study.prompt.md", "calls/study.reply.json"):
        assert (train / f).exists(), f
    assert calls.count("study") == 1 and calls.count("lab-review") == 1  # round 2: L1 verified, no lab
    assert calls.count("review") == 2
    text = (deck / "playbook.md").read_text()
    assert "*(verified in lab)*" in text and "## Going second / breaking boards" in text
    assert text.count("Tribute it** for a body") == 1  # the second game repeated it: deduplicated
    assert "invented ruling" not in text
    state = json.loads((train / "state.json").read_text())
    assert state["pool"] == ["heuristic:saffira"]  # Dark Magician has Link monsters: dropped
    assert state["steps"]["study"]["result"]["card_checks"] == {"total": 2, "verified": 1}
    assert state["verification"]["L1"]["status"] == "verified"
    assert len(state["rejected_lessons"]) >= 2 and not state.get("tests_saved")
    assert state["status"] == "done" and abs(state["ledger"][0]["cost"] - 0.5) < 1e-9
    report = (train / "train-report.md").read_text()
    for want in ("| 1 | 3 | 1 | 1 |", "Lines (lab verification)", "Pitfalls rejected", "does Geargiarmor"):
        assert want in report, want
    assert pb.problems(text) == []


def test_budget_stop_and_resume(tmp_path, decks_dir, engine, agent_db, geargia, quiet):
    calls = []
    # $0.5 per reviewer call and $3.2 to spend: the study (estimated $3) and the lab review ($2) fit, then a game
    # (estimated $3 before any has been played) would go over.
    t = make(tmp_path, calls, budget=3.2, rounds=1, engine=engine, db=agent_db)
    assert t.run() == "stopped: budget"
    state = json.loads((decks_dir / "geartest" / "train" / "state.json").read_text())
    assert "study" in state["steps"] and "r1.lab.review" in state["steps"]
    assert "r1.game.r1-g1" not in state["steps"] and state["status"] == "stopped: budget"
    assert "stopped: budget" in (decks_dir / "geartest" / "train" / "train-report.md").read_text()
    with pytest.raises(TrainerError):  # a finished or stopped run isn't restarted by accident
        make(tmp_path, calls, budget=5, rounds=1, engine=engine, db=agent_db).run()
    calls.clear()
    t = make(tmp_path, calls, budget=10, rounds=1, resume=True, engine=engine, db=agent_db)
    assert t.run() == "done"
    assert calls == ["review"]  # only what was missing
    state = json.loads((decks_dir / "geartest" / "train" / "state.json").read_text())
    assert "r1.review.r1-g1" in state["steps"] and state["status"] == "done"


def test_refuses_to_train_over_a_gold_deck(tmp_path, decks_dir, engine, agent_db, geargia, quiet):
    (decks_dir / "geartest").mkdir()
    (decks_dir / "geartest" / "playbook.md").write_text("gold")
    with pytest.raises(TrainerError):
        make(tmp_path, [], engine=engine, db=agent_db).run()
