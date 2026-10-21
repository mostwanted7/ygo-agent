"""Checkpoints, resume and the budget."""

import pytest

from ygo_agent.trainer.llm import Reviewer, extract_json
from ygo_agent.trainer.workspace import BudgetExhausted, TrainerError, Workspace


def test_steps_survive_a_restart(tmp_path):
    ws = Workspace(str(tmp_path / "deck"), quiet=True)
    assert not ws.exists and not ws.done("study")
    ws.finish("study", {"lines": 3}, seconds=12.3)
    ws.finish("r1.lab.hand-01", {"file": "x"})
    ws.spend("study", "study", 2.5, 100)
    again = Workspace(str(tmp_path / "deck"), quiet=True)
    assert again.exists and again.done("study") and again.result("study") == {"lines": 3}
    assert again.spent == 2.5
    again.forget("r1.lab")
    assert not Workspace(str(tmp_path / "deck"), quiet=True).done("r1.lab.hand-01")
    assert (tmp_path / "deck" / "train" / "trainer.log").exists() or True


def test_other_versions_are_refused(tmp_path):
    ws = Workspace(str(tmp_path / "deck"), quiet=True)
    ws.state["version"] = 99
    ws.save()
    with pytest.raises(TrainerError):
        Workspace(str(tmp_path / "deck"), quiet=True)


def test_budget_uses_defaults_then_the_ledger(tmp_path):
    ws = Workspace(str(tmp_path / "deck"), budget=10.0, quiet=True)
    ws.check_budget("game", 3)  # 3 x $3 default
    with pytest.raises(BudgetExhausted):
        ws.check_budget("game", 4)
    ws.spend("r1.game.1", "game", 1.0)
    ws.spend("r1.game.2", "game", 1.0)
    assert ws.estimate("game") == 1.0 and ws.remaining() == 8.0
    ws.check_budget("game", 8)
    with pytest.raises(BudgetExhausted):
        ws.check_budget("game", 9)
    assert ws.affordable("game", 20) == 8
    assert Workspace(str(tmp_path / "other"), quiet=True).affordable("game", 20) == 20  # no budget


def test_reviewer_needs_an_llm_and_scripted_works():
    with pytest.raises(TrainerError):
        Reviewer({"name": "heuristic", "type": "heuristic"})
    seen = []
    rv = Reviewer({"name": "fake", "type": "scripted", "cost_per_call": 0.25,
                   "policy": lambda req: seen.append(req) or {"ok": req["task"]}})
    out, info = rv.ask("study", "system", "prompt", {"type": "object"})
    assert out == {"ok": "study"} and info["cost_usd"] == 0.25 and seen[0]["prompt"] == "prompt"
    assert not rv.agentic


def test_extract_json():
    assert extract_json('Here you go:\n```json\n{"a": 1, "b": [1, 2]}\n```') == {"a": 1, "b": [1, 2]}
    assert extract_json("<think>{x}</think> {\"a\": {\"b\": 2}} trailing") == {"a": {"b": 2}}
    assert extract_json("no json") is None


def test_sandbox_copies_only_what_is_asked(tmp_path, monkeypatch):
    from ygo_agent.trainer import llm
    monkeypatch.setattr(llm, "SANDBOX", str(tmp_path / "sandbox"))
    ws = tmp_path / "train"
    (ws / "scripts").mkdir(parents=True)
    (ws / "scripts" / "c1.lua").write_text("x")
    (ws / "dossier.md").write_text("d")
    (ws / "state.json").write_text("{}")
    (ws / "round-1" / "games" / "g").mkdir(parents=True)
    (ws / "round-1" / "games" / "g" / "game.md").write_text("g")
    (ws / "round-1" / "games" / "g" / "replay.yrpX").write_text("r")
    rv = Reviewer({"name": "opus", "type": "claude-code", "model": "opus"}, name="deck")
    assert rv.agentic
    box = rv.sync(str(ws), ["scripts", "dossier.md", "round-1/games/g", "missing.md"])
    assert sorted(p.name for p in (tmp_path / "sandbox" / "deck").rglob("*") if p.is_file()) == [
        "c1.lua", "dossier.md", "game.md"]
    assert box.startswith(str(tmp_path / "sandbox"))


def test_cli_options_resume_with_the_runs_own(tmp_path, monkeypatch):
    """train --resume keeps the run's options (not the config defaults); flags given on the command line win."""
    import json
    from ygo_agent import cli, paths
    from ygo_agent.trainer import pipeline
    monkeypatch.setattr(paths, "DECKS", str(tmp_path))
    seen = []

    class FakeTrainer:
        def __init__(self, opts, cfg, resume=False):
            seen.append((opts, resume))

        def run(self):
            return "done"
    monkeypatch.setattr(pipeline, "Trainer", FakeTrainer)
    (tmp_path / "geargia" / "train").mkdir(parents=True)
    (tmp_path / "geargia" / "train" / "state.json").write_text(json.dumps({"options": {
        "ydk": "/x/Geargia.ydk", "games": 2, "max_rounds": 2, "lab_hands": 9, "budget": 45.0,
        "phases": ["study", "lab"],
        "echo": "off", "player_backend": "sonnet"}}))
    args = cli.parser().parse_args(["train", "--name", "geargia", "--resume", "--budget-usd", "60"])
    assert args.handler(args, cli.configure(args)) == 0
    opts, resume = seen[-1]
    assert resume and opts.ydk == "/x/Geargia.ydk" and opts.games == 2 and opts.lab_hands == 9
    assert opts.budget == 60 and opts.phases == ("study", "lab") and opts.echo == "off"
    args = cli.parser().parse_args(["train", "new.ydk", "--name", "other", "--games", "3"])
    args.handler(args, cli.configure(args))
    opts, resume = seen[-1]
    assert not resume and opts.games == 3 and opts.lab_hands == 10 and opts.backend == "opus"  # [trainer] defaults
