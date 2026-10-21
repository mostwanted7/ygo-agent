"""The rules policy: a reviewer's rule proposal becomes a hard rule only for a no-judgment mistake that the play model
made although the playbook already covered it, proven by a saved case; and only with --write-rules."""

from fake_trainer import PLAYBOOK, make_trainer
from ygo_agent.agent.rules import Rules
from ygo_agent.trainer import rulepolicy
from ygo_agent.trainer.pipeline import RULES_TEMPLATE

COVERED = "Consider Gear Gigant X when a Geargiano is in the GY"
MISTAKE = {"decision": 18, "no_judgment": True, "playbook_had": COVERED, "verified": True}
PROPOSAL = {"rule": "Loop Arsenal before Gear Gigant X.", "decisions": [18], "case": "loop-arsenal", "code": ""}
CODE = '''def loop_arsenal_first(ctx):
    """Tribute a non-negated Arsenal before Xyz Summoning."""
    picks = ctx.find(name="Geargiarsenal", action="activate")
    return Decide([picks[0]], "loop first") if picks else None
'''


def assess(proposal=PROPOSAL, mistakes=(MISTAKE,), player="opus", play_model="opus", playbook=PLAYBOOK,
           cases=("loop-arsenal",)):
    return rulepolicy.assess(proposal, list(mistakes), player=player, play_model=play_model, playbook=playbook,
                             cases=set(cases))


def test_a_proposal_that_meets_every_condition_qualifies():
    e = assess()
    assert e["qualifies"] and e["reasons"] == [] and e["case"] == "loop-arsenal" and e["decisions"] == [18]


def test_each_condition_is_checked():
    assert "needed judgment" in assess(mistakes=[{**MISTAKE, "no_judgment": False}])["reasons"][0]
    assert "not by the play model opus" in assess(player="sonnet")["reasons"][0]  # rules are calibrated to it
    assert "didn't cover it yet" in assess(mistakes=[{**MISTAKE, "playbook_had": ""}])["reasons"][0]
    made_up = {**MISTAKE, "playbook_had": "Always loop Arsenal three times"}  # not a quote of the playbook
    assert "didn't cover it yet" in assess(mistakes=[made_up])["reasons"][0]
    assert "no saved regression case" in assess(cases=())["reasons"][0]
    assert "no verified mistake" in assess(mistakes=[{**MISTAKE, "decision": 3}])["reasons"][0]
    assert len(assess(player="sonnet", cases=())["reasons"]) == 2


def test_write_rule_appends_a_loadable_rule_with_its_case(tmp_path):
    path = tmp_path / "rules.py"
    path.write_text(RULES_TEMPLATE.format(name="Geargia"))
    assert rulepolicy.write_rule(str(path), CODE, "loop-arsenal") == "loop_arsenal_first"
    rules = Rules(str(tmp_path)).deck_rules
    assert [r.__name__ for r in rules] == ["loop_arsenal_first"] and rules[0].cases == ("loop-arsenal",)
    second = CODE.replace("loop_arsenal_first", "second_rule")
    assert rulepolicy.write_rule(str(path), second, "other-case") == "second_rule"
    assert [r.__name__ for r in Rules(str(tmp_path)).deck_rules] == ["loop_arsenal_first", "second_rule"]
    assert rulepolicy.write_rule(str(path), CODE, "loop-arsenal") is None  # already there


def test_write_rule_refuses_anything_but_one_clean_function(tmp_path):
    path = tmp_path / "rules.py"
    path.write_text(RULES_TEMPLATE.format(name="Geargia"))
    before = path.read_text()
    for bad in ("def broken(ctx:\n    pass\n", CODE + "\ndef two(ctx):\n    return None\n",
                "import os\nos.system('true')\n" + CODE,  # nothing may run on import
                "@staticmethod\n" + CODE,
                "def no_args():\n    return None\n", "def boom(ctx):\n    return undefined_name\nraise SystemExit\n"):
        assert rulepolicy.write_rule(str(path), bad, "case") is None, bad
    assert path.read_text() == before


def test_old_rules_files_get_the_cases_import(tmp_path):
    path = tmp_path / "rules.py"
    path.write_text('"""Old rules."""\n\nfrom ygo_agent.agent.rules import Decide\n\nRULES = []\n')
    assert rulepolicy.write_rule(str(path), CODE, "loop-arsenal") == "loop_arsenal_first"
    assert Rules(str(tmp_path)).deck_rules[0].cases == ("loop-arsenal",)


def test_the_trainer_logs_proposals_and_writes_rules_only_with_the_flag(tmp_path, cfg, db):
    proposal = {**PROPOSAL, "case": "set-ash-as-blocker-empty-field", "code": CODE}
    for flag in (False, True):
        t = make_trainer(tmp_path / str(flag), cfg, db, lambda task, prompt: None, write_rules=flag,
                         player_backend="opus", play_model="opus")
        t.rule_proposals({"id": "r2-g1"}, [proposal, {**proposal, "decisions": [99]}], [MISTAKE], PLAYBOOK)
        md = t.ws.read("rule-proposals.md")
        assert "play model (opus)" in md and "no verified mistake" in md
        names = [r.__name__ for r in Rules(t.deck_dir).deck_rules]
        assert names == (["loop_arsenal_first"] if flag else [])
        assert ("**written to rules.py**" in md) == flag and ("**qualifies**" in md) == (not flag)
        assert [e["qualifies"] for e in t.ws.state["rule_proposals"]] == [True, False]
    t = make_trainer(tmp_path / "sonnet", cfg, db, lambda task, prompt: None, write_rules=True,
                     player_backend="sonnet", play_model="opus")
    t.rule_proposals({"id": "r2-g1"}, [proposal], [MISTAKE], PLAYBOOK)
    assert Rules(t.deck_dir).deck_rules == [] and "not by the play model opus" in t.ws.read("rule-proposals.md")
