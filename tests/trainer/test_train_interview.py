"""The interview: the reviewer's questions about the deck, the owner's answers in tips.md, and the study writing the
playbook from them. A scripted reviewer; --phases study, so no duel and no EDOPro is needed."""

import contextlib
import functools
import io
import json
import os
import shutil

import pytest

from fake_trainer import GEARGIA, PLAYBOOK
from ygo_agent import cli
from ygo_agent.trainer import pipeline, tips
from ygo_agent.trainer.pipeline import Options, Trainer

QUESTIONS = [{"question": "Which Rank 4 do you make first?", "why": "So the playbook knows the Xyz priority."},
             {"question": "Go first or second?", "why": "Sets go_first."},
             {"question": "Anything else the agent should know about this deck?", "why": "duplicate: dropped"}]


def reviewer(cfg):
    calls = []

    def policy(req):
        calls.append(req)
        if req["task"] == "interview":
            assert "## Dossier" in req["prompt"] and "Most important first" in req["prompt"]
            return {"questions": QUESTIONS}
        if req["task"] == "study":
            return {"playbook": PLAYBOOK, "lines": [], "card_checks": [], "go_first": True, "go_first_reason": "x",
                    "open_questions": []}
        raise AssertionError(req["task"])
    cfg["backends"]["fake"] = {"type": "scripted", "policy": policy, "cost_per_call": 0.1}
    return calls


@pytest.fixture
def ydk(tmp_path):
    path = tmp_path / "Geargia.ydk"
    shutil.copyfile(os.path.join(GEARGIA, "deck.ydk"), path)
    return str(path)


@pytest.fixture
def dossier(monkeypatch):
    """A dossier without EDOPro: the study only needs its text and cards."""
    from ygo_agent.trainer.dossier import Dossier
    monkeypatch.setattr(Trainer, "dossier", lambda self, rebuild=False: Dossier("Geargia", [], "# Dossier\n",
                                                                               self.train_dir))


def trainer(cfg, db, ydk, decks_dir, **kw):
    o = Options(ydk=ydk, name="gear", backend="fake", phases=("study",), out=str(decks_dir / "gear"))
    return Trainer(o, cfg, db=db, quiet=True, **kw)


def run(t):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        status = t.run()
    return status, out.getvalue()


def test_questions_are_asked_in_a_terminal_and_become_tips(cfg, db, ydk, decks_dir, dossier, monkeypatch):
    calls = reviewer(cfg)
    answers = iter(["Dark Rebellion against a boss.", ""])  # the second is skipped, then Ctrl+D

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None
    monkeypatch.setattr("builtins.input", fake_input)
    status, out = run(trainer(cfg, db, ydk, decks_dir, interactive=True))
    assert status == "done" and [c["task"] for c in calls] == ["interview", "study"]
    deck = decks_dir / "gear"
    data = json.loads((deck / "train" / "interview.json").read_text())
    assert set(data) == {"deck", "created", "backend", "questions"} and data["deck"] == "gear"
    assert [(q["id"], q["question"]) for q in data["questions"]] == [
        ("q1", "Which Rank 4 do you make first?"), ("q2", "Go first or second?"),
        ("anything-else", "Anything else the agent should know about this deck?")]
    assert "Which Rank 4 do you make first?" in out and "So the playbook knows the Xyz priority." in out
    assert [(e["title"], e["text"]) for e in tips.entries(str(deck))] == [
        ("Which Rank 4 do you make first?", "Dark Rebellion against a boss.")]
    study = calls[1]["prompt"]
    assert "## The owner's tips" in study and "Dark Rebellion against a boss." in study
    state = json.loads((deck / "train" / "state.json").read_text())
    assert state["steps"]["interview"]["result"] == {"mode": "asked", "questions": 3, "answered": 1}
    assert state["learn"]["tips_digest"] == tips.digest(str(deck))  # learn won't fold these in again
    assert "Interview: 1 of 3 questions answered" in (deck / "train" / "train-report.md").read_text()


def test_without_a_terminal_the_questions_are_only_written(cfg, db, ydk, decks_dir, dossier):
    calls = reviewer(cfg)
    status, _ = run(trainer(cfg, db, ydk, decks_dir, interactive=False))
    assert status == "done" and [c["task"] for c in calls] == ["interview", "study"]
    deck = decks_dir / "gear"
    assert (deck / "train" / "interview.json").is_file() and not (deck / "tips.md").exists()
    assert "learn --deck gear --tip" in (deck / "train" / "trainer.log").read_text()


def test_tips_file_replaces_the_questions(cfg, db, ydk, decks_dir, dossier, tmp_path):
    calls = reviewer(cfg)
    notes = tmp_path / "notes.txt"
    notes.write_text("Always go first.\nKeep Limiter Removal for lethal.\n")
    status, _ = run(trainer(cfg, db, ydk, decks_dir, tips_file=str(notes)))
    assert status == "done" and [c["task"] for c in calls] == ["study"]
    deck = str(decks_dir / "gear")
    assert [e["title"] for e in tips.entries(deck)] == ["Owner's notes"]
    assert "Keep Limiter Removal for lethal." in calls[0]["prompt"]


def test_a_tips_md_file_keeps_its_sections(cfg, db, ydk, decks_dir, dossier, tmp_path):
    reviewer(cfg)
    other = tmp_path / "other"
    tips.save_answers(str(other), [{"question": "Go first?", "answer": "Yes."}, {"question": "Tip", "answer": "B."}])
    run(trainer(cfg, db, ydk, decks_dir, tips_file=str(other / "tips.md")))
    assert [e["title"] for e in tips.entries(str(decks_dir / "gear"))] == ["Go first?", "Tip"]


def test_no_interview_still_uses_an_existing_tips_md(cfg, db, ydk, decks_dir, dossier):
    calls = reviewer(cfg)
    tips.add(str(decks_dir / "gear"), "Gear Gigant X needs a Geargiano in the GY.")
    status, _ = run(trainer(cfg, db, ydk, decks_dir, interview="skip"))
    assert status == "done" and [c["task"] for c in calls] == ["study"]
    assert "Gear Gigant X needs a Geargiano in the GY." in calls[0]["prompt"]


def test_interview_only_then_resume_from_the_cli(cfg, db, ydk, decks_dir, dossier, monkeypatch):
    """The web app's flow: --interview-only, it saves the answers itself, then --resume --no-interview with its own
    options, which win over the saved ones."""
    calls = reviewer(cfg)
    o = Options(ydk=ydk, name="gear", backend="fake", phases=("study",), lab_hands=9)
    t = Trainer(o, cfg, db=db, quiet=True, interview="only", interactive=True)
    status, _ = run(t)
    deck = decks_dir / "gear"
    assert status == "interview ready" and [c["task"] for c in calls] == ["interview"]
    assert (deck / "train" / "interview.json").is_file() and not (deck / "playbook.md").exists()
    question = json.loads((deck / "train" / "interview.json").read_text())["questions"][0]["question"]
    tips.save_answers(str(deck), [{"question": question, "answer": "Castel first, against anything big."}])

    monkeypatch.setattr(pipeline, "Trainer", functools.partial(Trainer, db=db, interactive=True))
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked again"))
    args = cli.parser().parse_args(["train", "--name", "gear", "--resume", "--no-interview", "--lab-hands", "4"])
    conf = cli.configure(args)
    conf["backends"]["fake"] = cfg["backends"]["fake"]
    with contextlib.redirect_stdout(io.StringIO()):
        assert args.handler(args, conf) == 0
    assert [c["task"] for c in calls] == ["interview", "study"]
    assert "Castel first, against anything big." in calls[1]["prompt"]
    state = json.loads((deck / "train" / "state.json").read_text())
    assert state["options"]["lab_hands"] == 4 and state["options"]["phases"] == ["study"]
    assert state["steps"]["interview"]["result"]["mode"] == "skipped" and (deck / "playbook.md").is_file()


def test_interview_only_prints_where_the_questions_are(cfg, db, ydk, decks_dir, dossier, monkeypatch):
    reviewer(cfg)
    monkeypatch.setattr(pipeline, "Trainer", functools.partial(Trainer, db=db))
    args = cli.parser().parse_args(["train", ydk, "--name", "gear", "--interview-only", "--backend", "fake",
                                    "--phases", "study"])
    conf = cli.configure(args)
    conf["backends"]["fake"] = cfg["backends"]["fake"]
    with contextlib.redirect_stdout(io.StringIO()) as out:
        assert args.handler(args, conf) == 0
    assert f"Interview questions: {decks_dir / 'gear' / 'train' / 'interview.json'}" in out.getvalue()
    assert "--resume --no-interview" in out.getvalue()
