"""Rule ablation (`ygo-agent test --ablate-rules`) with a scripted player: each rule's probes are replayed with that
rule disabled, and the verdict says whether the model still needs it. No model, no EDOPro."""

import json
import os
import shutil

from fake_trainer import GEARGIA, PLAYBOOK
from ygo_agent.agent import ablation, replay
from ygo_agent.agent.profile import Profile

SET_ASH = "set-ash-as-blocker-empty-field"  # turn 8: [1] Set Ash Blossom is right
DARK_REBELLION = "use-dark-rebellion-effect-before-ending"  # turn 4: [1] use Dark Rebellion is right
LOOP = "switch-to-attack-for-lethal"  # turn 6: no rule of this deck answers it

RULES = '''from ygo_agent.agent.rules import Decide, cases, shortcut


@cases("set-ash-as-blocker-empty-field")
def set_a_blocker(ctx):
    return Decide([1], "set a blocker") if ctx.kind == "idle" and ctx.turn == 8 else None


def use_dark_rebellion(ctx):  # no @cases: found because it answers a saved case
    return Decide([1], "halve it") if ctx.kind == "idle" and ctx.turn == 4 else None


@shortcut
def skip_window(ctx):  # never answers a saved case: probed with the decisions it answered in the logs
    return None


def never_fires(ctx):
    return None


RULES = [set_a_blocker, use_dark_rebellion, skip_window, never_fires]
'''


def make_deck(tmp_path):
    deck = tmp_path / "abl"
    (deck / "tests").mkdir(parents=True)
    shutil.copyfile(os.path.join(GEARGIA, "deck.ydk"), deck / "deck.ydk")
    (deck / "deck.json").write_text(json.dumps({"name": "Geargia", "ydk": "deck.ydk"}))
    (deck / "playbook.md").write_text(PLAYBOOK)
    (deck / "rules.py").write_text(RULES)
    for name in (SET_ASH, DARK_REBELLION):
        shutil.copyfile(os.path.join(GEARGIA, "tests", f"{name}.json"), deck / "tests" / f"{name}.json")
    return deck


def log_a_rule_decision(games, case_name, rule, choice, deck="abl", folder="2026-10-22_010101_abl-vs-x"):
    """A game log in which `rule` answered the last decision of a saved case."""
    game = games / folder
    game.mkdir(parents=True)
    (game / "meta.json").write_text(json.dumps({"deck": deck}))
    msgs = replay.load_case(os.path.join(GEARGIA, "tests", f"{case_name}.json"))["messages"]
    lines = [{"kind": "event" if m.get("t") == "event" else "decide", "msg": m} for m in msgs]
    lines.append({"kind": "reply", "msg": {"id": msgs[-1]["id"], "choice": choice, "source": f"rule:{rule}"}})
    (game / "game.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_ablation_verdicts(tmp_path, cfg, db, scripted, capsys):
    deck = make_deck(tmp_path)
    games = tmp_path / "games"
    log_a_rule_decision(games, LOOP, "skip_window", [2])
    log_a_rule_decision(games, LOOP, "skip_window", [2], deck="other", folder="2026-10-22_020202_x")
    # The model sets the blocker on its own and agrees with the shortcut, but ends the turn instead of using Dark
    # Rebellion.
    scripted["policy"] = lambda d: [1] if d["state"]["turn"] == 8 else [2]
    profile = Profile("abl", db, cfg, folder=str(deck))
    results = {r["rule"]: r for r in ablation.ablate(profile, cfg, db, repeat=2, folders=[str(games)])}
    assert results["set_a_blocker"]["verdict"] == "not needed"
    assert results["set_a_blocker"]["cases"] == [SET_ASH]
    assert [p["name"] for p in results["use_dark_rebellion"]["probes"]] == [DARK_REBELLION]
    assert results["use_dark_rebellion"]["verdict"] == "needed" and "0/2" in results["use_dark_rebellion"]["detail"]
    shortcut = results["skip_window"]
    assert [p["source"] for p in shortcut["probes"]] == ["log"]  # only the game of this deck
    assert shortcut["verdict"] == "shortcut" and shortcut["shortcut"]
    assert results["never_fires"]["verdict"] == "untested" and not results["never_fires"]["probes"]
    # each probe was really asked with its rule disabled: the model answered, not the rule
    assert sum(len(s.prompts) for s in scripted["sessions"]) == 2 * 3
    assert "NOT NEEDED: set_a_blocker" in capsys.readouterr().out


def test_disabling_a_rule_in_a_replay(tmp_path, cfg, db, scripted):
    deck = make_deck(tmp_path)
    scripted["policy"] = lambda d: [3]
    profile = Profile("abl", db, cfg, folder=str(deck))
    msgs = replay.load_case(str(deck / "tests" / f"{SET_ASH}.json"))["messages"]
    assert replay.replay(msgs, cfg, db, profile, "with-rule")["choice"] == [1]
    assert replay.replay(msgs, cfg, db, profile, "without", disabled=("set_a_blocker",))["choice"] == [3]


def test_multi_card_picks_match_in_any_order():
    case = {"messages": [{"kind": "select_card"}], "expect": [[0, 1, 5]], "reject": [[2, 3]]}
    assert replay.choice_ok(case, [5, 0, 1]) and not replay.choice_ok(case, [3, 2]) and not replay.choice_ok(case, [0])
    ordered = {"messages": [{"kind": "idle"}], "expect": [[1]], "reject": []}
    assert replay.choice_ok(ordered, [1]) and not replay.choice_ok(ordered, [2])
