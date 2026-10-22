"""`ygo-agent learn`: the owner's notes and new tips folded into a deck's playbook by a scripted reviewer (no model,
no EDOPro). The game is a fake log made from a saved case's messages, so the regression case it proposes is real."""

import contextlib
import io
import json
import os
import shutil

import pytest

from fake_trainer import GEARGIA, PLAYBOOK
from ygo_agent import cli
from ygo_agent.agent.profile import parse_ydk
from ygo_agent.trainer import learn, notes, tips
from ygo_agent.trainer import playbook as pb

CASE = os.path.join(GEARGIA, "tests", "set-ash-as-blocker-empty-field.json")  # decision #183: [1] = Set Ash Blossom
GAME = "2026-10-22_130750_geartest-vs-blue-eyes-ai"
GAME_MD = """# Geargia — game started 2026-10-22 13:07

## TURN 9 (your turn)

**Decision #182** — Response window: you may activate one of these cards/effects now.

  - ✅ (pass / none)

**Decision #183** — Main Phase: choose your next action. Reply with exactly one option index.

  - `[0]` Normal Summon "Ash Blossom & Joyous Spring" (from hand)
  - `[1]` Set "Ash Blossom & Joyous Spring" face-down in Defense Position (counts as your Normal Summon)
  - `[2]` Go to the Battle Phase
  - ✅ `[3]` End your turn (go to the End Phase)

> **opus (claude-code)** (3.1s): Nothing useful to do with an empty field; ending the turn.

- Opponent draws 1 card(s).
"""
NOTE = "With an empty field, Set Ash Blossom as a blocker instead of ending the turn."
SCRIPT_QUOTE = {"source": "script", "file": "c73428497.lua", "decision": 0, "quote": "e2:SetCost(Cost.SelfTribute)"}
SITUATIONAL = ("- **Consider Gear Gigant X when a Geargiano is in the GY**, because it floats.\n"
               "- **Set a blocker when your field is empty** and they have attackers, because a face-down monster "
               "costs them an attack.")


def reply(**over):
    out = {"summary": "Blockers matter.", "tips": [], "open_questions": [],
           "notes": [{"note": 1, "decision": 183, "verdict": "applied", "outcome": "new principle on blockers"}],
           "sections": [{"heading": "## Situational considerations", "content": SITUATIONAL}],
           "lessons": [{"text": "**When Geargiarsenal is on the field, Tribute it** for a body.", "decisions": [183],
                        "severity": "major", "evidence": [SCRIPT_QUOTE]}],
           "test_cases": [{"decision": 183, "name": "set blocker on empty field", "expect": [[1]], "reject": [],
                           "note": "Set Ash Blossom as a blocker."}]}
    out.update(over)
    return out


@pytest.fixture
def deck(decks_dir, db):
    """A user deck folder "geartest" with a hand-written playbook and a dossier, so learn needs no EDOPro."""
    folder = decks_dir / "geartest"
    (folder / "tests").mkdir(parents=True)
    shutil.copyfile(os.path.join(GEARGIA, "deck.ydk"), folder / "deck.ydk")
    (folder / "deck.json").write_text(json.dumps({"name": "Geargia", "ydk": "deck.ydk"}))
    (folder / "playbook.md").write_text(PLAYBOOK)
    train = folder / "train"
    (train / "scripts").mkdir(parents=True)
    main, extra, _ = parse_ydk(str(folder / "deck.ydk"))
    cards = [{"id": c, "name": db.name(c), "count": 1, "section": section, "type_line": "", "text": "",
              "kind": "Monster"} for section, ids in (("main", main), ("extra", extra)) for c in dict.fromkeys(ids)]
    (train / "cards.json").write_text(json.dumps(cards))
    (train / "dossier.md").write_text("# Dossier\n")
    (train / "scripts" / "c73428497.lua").write_text("e2:SetCost(Cost.SelfTribute)\n")
    return folder


def game(cfg, deck_key="geartest", mode="play", feedback=f"- (turn 9, right after decision #183; from Web panel) {NOTE}\n"):
    folder = os.path.join(cfg["games_dir"], GAME)
    os.makedirs(folder)
    with open(CASE, encoding="utf-8") as f:
        msgs = json.load(f)["messages"]
    with open(os.path.join(folder, "game.jsonl"), "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(json.dumps({"kind": "decide" if m.get("t") == "decide" else "event", "msg": m}) + "\n")
        f.write(json.dumps({"kind": "reply", "msg": {"id": 183, "choice": [3]}}) + "\n")
    with open(os.path.join(folder, "game.md"), "w", encoding="utf-8") as f:
        f.write(GAME_MD)
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"deck": deck_key, "mode": mode, "opponent": "Blue-Eyes AI", "result": "loss", "first": False,
                   "backend": {"label": "opus (claude-code)"}}, f)
    with open(os.path.join(folder, "feedback.md"), "w", encoding="utf-8") as f:
        f.write(feedback)
    return folder


def reviewer(cfg, answer):
    calls = []

    def policy(req):
        calls.append(req)
        return answer(req["task"], req["prompt"])
    cfg["backends"]["fake"] = {"type": "scripted", "policy": policy, "cost_per_call": 0.25}
    return calls


def run(cfg, db, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return learn.run(cfg, "geartest", reviewer="fake", gate_repeat=0, quiet=True, db=db, **kw)


def test_a_note_becomes_a_principle_a_pitfall_and_a_case(cfg, db, deck):
    folder = game(cfg)
    calls = reviewer(cfg, lambda task, prompt: reply())
    result = run(cfg, db)
    assert result["status"] == "done" and len(calls) == 1 and calls[0]["task"] == "learn"
    prompt = calls[0]["prompt"]
    for want in (f'game "{GAME}"', "right after decision #183; from Web panel", NOTE, "**Decision #183**",
                 '`[1]` Set "Ash Blossom', "**Decision #182**", "The owner played against the AI player",
                 "## The current playbook"):
        assert want in prompt, want
    text = (deck / "playbook.md").read_text()
    assert "Set a blocker when your field is empty" in text
    assert "Tribute it** for a body. *(" in text and "owner's note on game 2026-10-22_130750)*" in text
    assert pb.problems(text) == []
    case = json.loads((deck / "tests" / "set-blocker-on-empty-field.json").read_text())
    assert case["expect"] == [[1]] and case["messages"][-1]["id"] == 183
    lines = open(os.path.join(folder, "feedback.md")).read().splitlines()
    assert lines[1].startswith("  - Learned ") and "applied: new principle on blockers" in lines[1]
    assert "[edited: Situational considerations, Known pitfalls]" in lines[1]
    assert lines[1].endswith("case set-blocker-on-empty-field")
    assert notes.pending("geartest", cfg["games_dir"]) == []
    state = json.loads((deck / "train" / "state.json").read_text())
    assert "options" not in state and state["learn"]["runs"][0]["notes"] == 1  # learn's state only, not a run
    assert state["learn"]["runs"][0]["cases"] == ["set-blocker-on-empty-field"]
    run_dir = deck / "train" / "learn" / result["run"]
    for f in ("report.md", "learn.log", f"calls/{GAME}.prompt.md", f"calls/{GAME}.reply.json",
              f"playbook-after-{GAME}.md", f"games/{GAME}/condensed.md"):
        assert (run_dir / f).exists(), f
    report = (run_dir / "report.md").read_text()
    assert "| #183 |" in report and "set-blocker-on-empty-field" in report and "$0.25" in report
    assert "1 note(s) from 1 game(s) (applied 1)" in (deck / "train" / "learn.md").read_text()
    calls.clear()
    assert run(cfg, db)["status"] == "nothing to learn" and calls == []  # marked: never used twice
    from ygo_agent.trainer.workspace import has_run
    assert not has_run(str(deck))  # `train --resume` doesn't take learn's state for a training run


def test_nothing_pending_means_no_call_and_no_files(cfg, db, deck):
    calls = reviewer(cfg, lambda task, prompt: reply())
    assert run(cfg, db)["status"] == "nothing to learn" and calls == []
    assert not (deck / "train" / "state.json").exists() and not (deck / "train" / "learn").exists()


def test_new_tips_get_a_call_of_their_own_and_only_once(cfg, db, deck):
    tips.add(str(deck), "Use Geargiagear at the end of the opponent's turn.", name="Geargia")

    def answer(task, prompt):
        assert "# Task: fold the owner's new tips" in prompt and "**NEW**" in prompt and "Geargiagear" in prompt
        return reply(notes=[], test_cases=[], lessons=[], tips=[{"tip": 1, "verdict": "already_covered",
                                                                   "outcome": "Situational considerations says it"}])
    calls = reviewer(cfg, answer)
    result = run(cfg, db)
    assert result["status"] == "done" and len(calls) == 1
    assert result["tips"] == [{"tip": 1, "verdict": "already_covered", "outcome": "Situational considerations says it",
                               "title": "Tip"}]
    state = json.loads((deck / "train" / "state.json").read_text())["learn"]
    assert state["tips_digest"] == tips.digest(str(deck)) and len(state["tips_seen"]) == 1
    calls.clear()
    assert run(cfg, db)["status"] == "nothing to learn" and calls == []
    tips.add(str(deck), "Gagaga Cowboy in Defense burns for 800.")
    assert learn.tips_status(str(deck))["new"] == [2]


def test_tips_ride_along_with_the_first_game(cfg, db, deck):
    game(cfg)
    tips.add(str(deck), "Gagaga Cowboy finishes OTKs.")
    calls = reviewer(cfg, lambda task, prompt: reply(tips=[{"tip": 1, "verdict": "applied", "outcome": "Lethal"}]))
    assert run(cfg, db)["status"] == "done" and len(calls) == 1
    assert "**NEW**" in calls[0]["prompt"] and NOTE in calls[0]["prompt"]
    assert learn.tips_status(str(deck))["new"] == []


def test_owner_sections_are_never_edited(cfg, db, deck):
    owner = "## Coaching lessons (from your opponent — these override everything below)\n\n- Keep Ash for their turn."
    hand_written = owner + "\n\n## Game plan\n\nMake Rank 4s.\n\n## Engine cards\n\n- Arsenal.\n"
    (deck / "playbook.md").write_text(hand_written)
    game(cfg)
    calls = reviewer(cfg, lambda task, prompt: reply(sections=[
        {"heading": "## Coaching lessons", "content": "- rewritten"}, {"heading": "## Coaching", "content": ""},
        {"heading": "## Engine cards", "content": "- Arsenal: Tribute it for a Geargia."}]))
    assert run(cfg, db)["status"] == "done"
    text = (deck / "playbook.md").read_text()
    assert text.startswith(owner + "\n") and "rewritten" not in text
    assert "Tribute it for a Geargia" in text
    sections = pb.split(text)
    assert pb.is_lessons(sections[-1][0]) and not pb.is_owner(sections[-1][0])  # the pitfall got its own section
    assert "Tribute it** for a body" in sections[-1][1]
    assert "hand-written, not in the house style" in calls[0]["prompt"]


def test_keep_owner_and_new_problems():
    owner = "## Coaching lessons\n\n- Mine."
    before = owner + "\n\n## Game plan\n\nA.\n"
    assert pb.keep_owner(before, "## Game plan\n\nB.\n") == before.replace("A.", "B.")
    assert pb.keep_owner(before, "## Coaching lessons\n\n- changed\n\n## Game plan\n\nB.\n").startswith(owner)
    # a hand-written playbook isn't held to the house style, only to keeping what it had
    assert pb.new_problems(before, pb.keep_owner(before, "## Game plan\n\nB.\n")) == []
    assert pb.new_problems(before, "## Game plan\n\nB.\n") == ["no known pitfalls section"]
    assert pb.new_problems(PLAYBOOK, "## Game plan\n\nB.\n")  # a house-style one may not lose its sections
    assert not pb.house_style(before) and pb.house_style(PLAYBOOK)


def test_a_reverted_edit_is_reported_in_the_note(cfg, db, deck, monkeypatch):
    from ygo_agent.trainer.pipeline import Trainer
    game(cfg)
    reviewer(cfg, lambda task, prompt: reply(lessons=[], test_cases=[]) if task == "learn" else
             {"playbook": PLAYBOOK + "\nFIXED\n", "removed": []})
    score = {"hash": "x", "good": 0, "total": 2, "cases": {"c": {"good": 0, "repeat": 2, "choices": [[0], [0]]}}}

    def case_score(self, text, label, allow_last=False):
        return {**score, "good": 2, "cases": {"c": {**score["cases"]["c"], "good": 2}}} if text == PLAYBOOK else score
    monkeypatch.setattr(Trainer, "case_score", case_score)
    monkeypatch.setattr(Trainer, "failure_details", lambda self, names, base, new: [])
    assert run(cfg, db)["status"] == "done"
    assert (deck / "playbook.md").read_text() == PLAYBOOK
    line = open(os.path.join(cfg["games_dir"], GAME, "feedback.md")).read().splitlines()[1]
    assert "not applied: the edit made saved cases fail (2/2 → 0/2)" in line


def test_spectator_notes_wait_for_include_spectators(cfg, db, deck):
    game(cfg, feedback="- (turn 9, right after decision #183; from Spectator bob) Bad play.\n")
    calls = reviewer(cfg, lambda task, prompt: reply())
    assert run(cfg, db) == {"deck": "geartest", "name": "Geargia", "skipped_untrusted": 1,
                            "status": "nothing to learn"}
    assert run(cfg, db, include_untrusted=True)["status"] == "done"
    assert "Not the owner's" in calls[0]["prompt"]


def test_a_missing_verdict_leaves_the_note_pending(cfg, db, deck):
    game(cfg)
    reviewer(cfg, lambda task, prompt: reply(notes=[]))
    assert run(cfg, db)["status"] == "done"
    assert len(notes.pending("geartest", cfg["games_dir"])) == 1


def test_cli_list_json_tip_and_game_filter(cfg, db, deck, tmp_path):
    folder = game(cfg, feedback=f"- (turn 9, right after decision #183; from Web panel) {NOTE}\n"
                                "- (turn 9, right after decision #183; from Spectator bob) Meh.\n")
    games = str(tmp_path / "games")

    def cli_run(*argv):
        args = cli.parser().parse_args(["learn", "--deck", "geartest", "--games-dir", games, *argv])
        conf = cli.configure(args)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = args.handler(args, conf)
        return code, out.getvalue()
    code, out = cli_run("--tip", "Gear Gigant X only with a Geargiano in the GY.", "--json")
    assert code == 0 and json.loads(out)["tips"] == 1
    code, out = cli_run("--list", "--json")
    info = json.loads(out)
    assert code == 0 and set(info) == {"deck", "name", "dir", "games_dir", "notes", "to_learn", "tips", "pending"}
    assert info["to_learn"] == 1 and info["pending"] is True and info["tips"]["new"] == [1]
    assert set(info["tips"]) == {"path", "count", "changed", "new"}
    first, second = info["notes"]
    assert (first["trusted"], first["used"], first["decision"], first["game"]) == (True, True, 183, GAME)
    assert (second["trusted"], second["used"], second["author"]) == (False, False, "Spectator bob")
    assert {"game_dir", "key", "text", "context", "turn", "pending", "learned"} <= set(first)
    code, out = cli_run("--list", "--json", "--game", folder, "--include-spectators")
    assert json.loads(out)["to_learn"] == 2
    code, out = cli_run("--list")
    assert "[not yours: Spectator bob" in out and "learns 1 note(s) and the new tips" in out
    with pytest.raises(SystemExit):
        cli_run("--list", "--game", "no-such-game")
