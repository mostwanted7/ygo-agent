"""The house style the trainer asks for and checks: principles first, conditions instead of scripts, an override
license, a lethal check, Known pitfalls last, at most 8 KB. The Geargia playbook is its reference example."""

import os
import re

from helpers import ROOT
from ygo_agent.agent.rules import Rules
from ygo_agent.trainer import playbook as pb
from ygo_agent.trainer import prompts, schemas
from ygo_agent.trainer.pipeline import EXAMPLE_DECKS, RULES_TEMPLATE

GEARGIA = os.path.join(ROOT, "decks", "geargia", "playbook.md")


def headings(text):
    return re.findall(r"`(## [^`]+)`", text)


def test_the_style_lists_the_template_in_order():
    assert [pb.key(h) for h in headings(prompts.SECTIONS)] == [pb.key(h) for h, _ in pb.TEMPLATE]
    assert pb.key(pb.TEMPLATE[-1][0]) == pb.key(pb.LESSONS_HEADING)
    assert {pb.key("## " + name) for name, _ in prompts.BUDGET} == {pb.key(h) for h, _ in pb.TEMPLATE}
    assert sum(kb for _, kb in prompts.BUDGET) <= pb.TARGET_KB[1] and pb.LIMIT_BYTES <= 8.5 * 1024


def test_the_prompts_ask_for_principles_an_override_license_and_a_lethal_check():
    style = prompts.STYLE
    for want in ("principles, not scripts", "deviate when a better play exists", "Consider X when Y",
                 "Lethal check", "non-obvious lethals", "always last", "never more than 8 KB"):
        assert want in style, want
    study = prompts.study("Deck", "dossier", "general", {"geargia": "x"}, agentic=True)
    assert "## The house style" in study and "for testing only" in study
    review = prompts.game_review("Deck", "playbook", {"id": "r1-g1"}, "log", [], agentic=True,
                                 open_questions=["Does X miss timing?"])
    for want in ("`no_judgment`", "`playbook_had`", "Known pitfall", "significant, repeatable",
                 "a deviation that was as good or better is not a mistake", "1. Does X miss timing?",
                 "`settled_questions`"):
        assert want in review, want
    condense = prompts.condense("playbook", 8)
    assert "regression cases" in condense and "Known pitfalls last" in condense


def test_the_review_schema_tracks_judgment_coverage_and_rule_cases():
    mistake = schemas.GAME_REVIEW["properties"]["mistakes"]["items"]["properties"]
    assert {"no_judgment", "playbook_had"} <= set(mistake)
    proposal = schemas.GAME_REVIEW["properties"]["rule_proposals"]["items"]
    assert proposal["required"] == ["rule", "decisions", "case", "code"]
    assert "settled_questions" in schemas.LAB_REVIEW["required"] and "repeated" not in schemas.GAME_REVIEW["properties"]


def test_the_geargia_playbook_is_in_the_house_style():
    text = open(GEARGIA, encoding="utf-8").read()
    assert pb.problems(text) == [] and len(text.encode()) <= 8 * 1024
    keys = [pb.key(h) for h, _ in pb.split(text)]
    template = [pb.key(h) for h, _ in pb.TEMPLATE]
    assert keys == [k for k in template if k in keys]  # the template's order
    assert "lethal check" in keys and keys[-1] == pb.key(pb.LESSONS_HEADING)
    assert EXAMPLE_DECKS[0] == "geargia"  # the study's first example


def test_the_rules_template_loads_and_imports_the_markers(tmp_path):
    (tmp_path / "rules.py").write_text(RULES_TEMPLATE.format(name="Test"))
    assert Rules(str(tmp_path)).deck_rules == []
    assert "@cases" in RULES_TEMPLATE and "--ablate-rules" in RULES_TEMPLATE
