"""Applying reviewer JSON to a playbook: sections, lessons, verified marks, the evidence check, test cases."""

import json

from ygo_agent.trainer import playbook as pb
from ygo_agent.trainer import review

DRAFT = """## How to use this playbook

Principles, not scripts.

## Game plan

Make Rank 4s.

## Card roles

- **Geargiarsenal**: Tribute it for a Geargia.

## Situational considerations

- **Consider Gear Gigant X when a Geargiano is in the GY**, because it floats.

## Example sequences

**Line 1: Geargiarsenal + any Geargia** *(unverified)*
1. Normal Summon Geargiarsenal.

**Line 2: Geargiano Mk-II** *(unverified)*
1. Normal Summon Mk-II.

## Known pitfalls (from reviewed games, newest first)

None yet: specific mistakes from reviewed games go here, one or two lines each.
"""

OLD_STYLE = """## Lessons from games (newest first; these override everything below)

### 2026-10-21 game 1
1. **Old lesson.**

## Game plan

Make Rank 4s.
"""


def test_split_and_join_round_trip():
    assert pb.join(pb.split(DRAFT)) == DRAFT
    assert [pb.key(h) for h, _ in pb.split(DRAFT)][:2] == ["how to use this playbook", "game plan"]


def test_apply_sections_replaces_adds_and_deletes():
    text, changes = pb.apply_sections(DRAFT, [
        {"heading": "## Game plan", "content": "## Game plan\n\nXyz beatdown with traps."},  # heading repeated
        {"heading": "Going second / breaking boards", "content": "- Harpie's Feather Duster first."},
        {"heading": "## Card roles", "content": ""},
        {"heading": "## Known pitfalls", "content": "overwritten!"},
    ])
    sections = dict(pb.split(text))
    assert sections["## Game plan"] == "Xyz beatdown with traps."
    heads = [h for h, _ in pb.split(text)]
    assert heads.index("## Going second / breaking boards") == len(heads) - 2  # new sections go before the pitfalls
    assert heads[-1] == pb.LESSONS_HEADING and "## Card roles" not in heads
    assert "None yet" in text and "overwritten!" not in text
    assert any("ignored" in c for c in changes) and len(changes) == 4


def test_new_sections_in_an_old_style_playbook_go_at_the_end():
    text, _ = pb.apply_sections(OLD_STYLE, [{"heading": "## Lethal check", "content": "- Count."}])
    assert [h for h, _ in pb.split(text)][-1] == "## Lethal check"


def test_prefix_heading_match():
    text, _ = pb.apply_sections(DRAFT, [{"heading": "## Example sequences", "content": "**Line 1** new"}])
    assert "**Line 1** new" in text and "Line 2" not in text


def test_pitfalls_newest_first_with_their_tag():
    text = pb.add_lessons(DRAFT, "2026-10-21, r1-g1 vs X", ["**Do A** because B.", "2. **Do C.**"])
    text = pb.add_lessons(text, "2026-10-22, r2-g1 vs Y", ["**Do D.**"])
    body = dict(pb.split(text))[pb.LESSONS_HEADING]
    assert "None yet" not in body
    assert body.splitlines() == ["- **Do D.** *(2026-10-22, r2-g1 vs Y)*", "- **Do A** because B. *(2026-10-21, r1-g1 vs X)*",
                                 "- **Do C.** *(2026-10-21, r1-g1 vs X)*"]
    assert pb.split(text)[-1][0] == pb.LESSONS_HEADING and pb.problems(text) == []


def test_pitfalls_keep_an_intro_line_and_old_style_lessons_sections():
    intro = DRAFT.replace("None yet: specific mistakes from reviewed games go here, one or two lines each.",
                          "From reviewed games.")
    body = dict(pb.split(pb.add_lessons(intro, "t", ["**A.**"])))[pb.LESSONS_HEADING]
    assert body.startswith("From reviewed games.\n\n- **A.** *(t)*")
    old = pb.add_lessons(OLD_STYLE, "t", ["**New.**"])
    lessons = pb.split(old)[0][1]
    assert lessons.index("**New.**") < lessons.index("Old lesson")


def test_mark_verified():
    text, changed = pb.mark_verified(DRAFT, ["Line 1: Geargiarsenal + any Geargia", "Line 9"], "verified in lab")
    assert changed == ["Line 1: Geargiarsenal + any Geargia"]
    assert "**Line 1: Geargiarsenal + any Geargia** *(verified in lab)*" in text
    assert "**Line 2: Geargiano Mk-II** *(unverified)*" in text


def test_problems_and_ensure_lessons():
    assert pb.problems(DRAFT) == []
    bare = "## Game plan\n\nx\n"
    assert "no known pitfalls section" in pb.problems(bare) and "no 'card roles' section" in pb.problems(bare)
    assert pb.split(pb.ensure_lessons(bare))[-1][0] == pb.LESSONS_HEADING
    moved = DRAFT + "\n## Lethal check\n\n- Count.\n"
    assert "known pitfalls is not the last section" in pb.problems(moved)
    assert any("KB" in p for p in pb.problems(DRAFT + "x" * 9000))


def test_quote_matching_is_forgiving_but_not_blind():
    script = "\te1:SetCountLimit(1,id)\n\te1:SetCost(Cost.SelfTribute)\n"
    assert pb.quote_found("e1:SetCountLimit(1,id)", script)
    assert pb.quote_found("e1:SetCost( Cost.SelfTribute )", script)
    assert not pb.quote_found("Duel.Destroy(g,REASON_EFFECT)", script)
    assert not pb.quote_found("id", script)  # too short to prove anything


def test_evidence_and_lessons(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "c73428497.lua").write_text("e2:SetCost(Cost.SelfTribute)\n")
    (scripts / "lib").mkdir()
    (scripts / "lib" / "proc_xyz.lua").write_text("function Xyz.AddProcedure(c,f,lv,ct)\n")
    log = tmp_path / "game.md"
    log.write_text("**Decision #12** — Main Phase\n\n  - ✅ `[0]` Activate \"Geargiarsenal\"\n")
    ev = pb.Evidence(str(scripts), {"r1-g1": str(log)}, {"Geargiarsenal": "You can Tribute this card"})
    assert ev.check({"source": "script", "file": "c73428497.lua", "quote": "SetCost(Cost.SelfTribute)"})[0]
    assert ev.check({"source": "script", "file": "73428497", "quote": "SetCost(Cost.SelfTribute)"})[0]
    assert ev.check({"source": "script", "file": "lib/proc_xyz.lua",
                     "quote": "function Xyz.AddProcedure(c,f,lv,ct)"})[0]
    assert not ev.check({"source": "script", "file": "c1.lua", "quote": "SetCost(Cost.SelfTribute)"})[0]
    assert ev.check({"source": "log", "file": "r1-g1", "decision": 12, "quote": 'Activate "Geargiarsenal"'})[0]
    assert not ev.check({"source": "log", "decision": 13, "quote": 'Activate "Geargiarsenal"'})[0]
    good = {"text": "**Tribute Geargiarsenal first.**", "severity": "major",
            "evidence": [{"source": "script", "file": "c73428497.lua", "quote": "SetCost(Cost.SelfTribute)"}]}
    text_only = {"text": "**Text only.**", "evidence": [{"source": "card_text", "file": "Geargiarsenal",
                                                         "quote": "You can Tribute this card"}]}
    made_up = {"text": "**Made up.**", "evidence": [{"source": "script", "file": "c73428497.lua",
                                                     "quote": "Duel.Draw(tp,2,REASON_EFFECT)"}]}
    text, accepted, rejected = review.apply_lessons(DRAFT, [good, text_only, made_up], "2026-10-21 game r1-g1",
                                                    ev)
    assert [a["text"] for a in accepted] == ["**Tribute Geargiarsenal first.**"]
    assert {r["text"] for r in rejected} == {"**Text only.**", "**Made up.**"}  # a card text alone isn't enough
    assert "- **Tribute Geargiarsenal first.** *(2026-10-21 game r1-g1)*" in text
    again, accepted, rejected = review.apply_lessons(text, [good], "2026-10-22 game r2-g1", ev)
    assert not accepted and "already has" in rejected[0]["notes"][0] and again == text


def test_save_cases_checks_against_the_log(tmp_path):
    from ygo_agent.agent.profile import Profile
    game = tmp_path / "game"
    game.mkdir()
    d = {"t": "decide", "id": 3, "kind": "idle", "options": [{"a": "summon"}, {"a": "to_end"}],
         "state": {"turn": 1}}
    records = [{"kind": "event", "msg": {"t": "event", "e": "start"}}, {"kind": "decide", "msg": d},
               {"kind": "reply", "msg": {"id": 3, "choice": [1]}}]
    (game / "game.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")

    class P:
        dir = str(tmp_path / "deck")
    saved, problems = review.save_cases(P, str(game), [
        {"decision": 3, "name": "Summon first!", "expect": [[0]], "reject": [[1]], "note": "summon"},
        {"decision": 3, "name": "bad index", "expect": [[5]], "reject": [], "note": ""},
        {"decision": 9, "name": "missing", "expect": [[0]], "reject": [], "note": ""},
        {"decision": 3, "name": "fourth", "expect": [[0]], "reject": [], "note": "at most 3 per review"},
    ])
    assert [s["name"] for s in saved] == ["summon-first"]
    assert len(problems) == 2
    saved, problems = review.save_cases(P, str(game), [{"decision": 3, "name": "already done", "expect": [[1]],
                                                         "reject": [], "note": ""}])
    assert not saved and "already chose" in problems[0]
    case = json.loads((tmp_path / "deck" / "tests" / "summon-first.json").read_text())
    assert case["expect"] == [[0]] and case["reject"] == [[1]] and case["messages"][-1]["id"] == 3
    assert Profile  # the real save path is replay.save_case, used above
