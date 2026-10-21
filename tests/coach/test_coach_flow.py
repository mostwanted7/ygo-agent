"""Coach mode's flow without the arena: a real logged game (a saved Saffira case) fed to a CoachGame decision by
decision, as the arena's SeatWatcher would, with a scripted coach and a scripted "human" who sometimes waits for the
advice, sometimes answers while the coach is thinking, and sometimes answers at once."""

import json
import os
import time

import pytest

from helpers import ROOT, first_valid, load_case
from ygo_agent.agent.profile import Profile
from ygo_agent.coach.cli import reviewing
from ygo_agent.coach.live import Coach, CoachGame
from ygo_agent.config import backend
from ygo_agent.web.recorded import load_game

CASE = os.path.join(ROOT, "decks", "saffira", "tests", "main2-to-set-lance.json")
REVIEW = "## Summary\nScripted review.\n\n## Key moments\n### Turn 3, decision #9: a moment\n- **You:** x\n"


def wait(cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    raise AssertionError("timed out")


def human_pick(d):
    """The scripted human: what the coach would say (first_valid) on even ids, something else on odd ones."""
    pick = first_valid(d)
    options = d.get("options", [])
    if d["id"] % 2 and d["kind"] in ("idle", "battle") and len(options) > 1:
        return [len(options) - 1]
    if d["id"] % 2 and d["kind"] == "chain" and not d.get("forced"):
        return [0] if pick == [] else []
    return pick


@pytest.fixture
def coached(cfg, db, bus):
    asked, slow = [], set()

    def coach_policy(d):
        asked.append(d["id"])
        if d["id"] in slow:
            time.sleep(0.3)
        return {"choice": first_valid(d), "why": f"coach says {first_valid(d)}", "plan": "1. scripted plan"}
    cfg["backends"]["coach"] = {"type": "scripted", "policy": coach_policy}
    cfg["backends"]["reviewer"] = {"type": "scripted", "policy": lambda d: {"choice": [], "why": REVIEW}}
    profile = Profile("saffira", db, cfg)
    coach = Coach(cfg, db, backend=backend(cfg, "coach"), profile=profile, echo="off",
                  review=reviewing(cfg, db, backend(cfg, "reviewer"), "beginner"), say=lambda *lines: None)
    game = CoachGame(coach, 1, profile, None)
    coach.game, coach.games = game, [game]
    yield coach, game, asked, slow
    coach.close(timeout=10)


def play(game, asked, slow, modes):
    """Feed the case; `modes(index) -> "wait" | "mid" | "instant"` for the n-th decision the human gets."""
    msgs = [json.loads(json.dumps(m)) for m in load_case(CASE)["messages"]]
    n, picks = 0, {}
    for m in msgs:
        if m.get("t") == "event":
            game.on_event(m)
            continue
        if m["kind"] == "go_first":  # decided in the lobby, not by a watched seat
            continue
        mode = modes(n)
        n += 1
        did = m["id"]
        if mode == "mid":
            slow.add(did)
        game.on_decision(m)
        if mode != "instant":
            wait(lambda: did in game.recs)
            rec = game.recs[did]
            if mode == "wait":
                wait(lambda: rec.advice is not None)
            elif rec.status != "auto":
                wait(lambda: did in asked)
        picks[did] = human_pick(m)
        game.on_choice(m, picks[did])
    game.on_event({"t": "event", "e": "win", "result": 0, "reason": 1})
    game.submit(game.finish_when_drained)
    wait(lambda: game.finished, 20)
    return picks


def by_type(bus, gid):
    out = {}
    for m in bus.backlog(gid):
        out.setdefault(m["type"], []).append(m)
    return out


def test_advice_late_and_matched(coached, bus, cfg):
    coach, game, asked, slow = coached
    picks = play(game, asked, slow, lambda i: ("wait", "mid", "instant")[i % 3])
    coach.close(timeout=20)
    gid = game.log.web.game_id
    msgs = by_type(bus, gid)
    decisions = {m["decision"]["id"]: m["decision"] for m in msgs["decision"]}
    advice = {m["id"]: m for m in msgs["advice"]}
    humans = {m["id"]: m for m in msgs["human_choice"]}
    replies = {m["id"]: m for m in msgs["reply"]}
    assert set(decisions) == set(picks) == set(replies) == set(advice)
    recs = game.recs
    for did, d in decisions.items():
        a, r, rec = advice[did], replies[did], recs[did]
        assert r["source"] == "human" and r["choice"] == picks[did]
        if rec.status == "auto":
            assert did not in asked  # trivial, a rule or a planned pick: no backend call
            assert a["source"] in ("auto",) or a["source"].startswith("rule")
            continue
        if a["source"] == "skipped":
            assert did not in asked and a["choice"] is None and d["kind"] not in ("idle", "battle", "chain")
            assert did not in humans
            continue
        if a["source"] == "failed":  # the scripted coach's answer was illegal twice (a select_sum): no advice
            assert did in asked and a["choice"] is None and did not in humans  # re-asked only if still live
            continue
        assert a["source"] == "backend" and did in asked and a["choice"] == first_valid(d)
        assert humans[did]["matched"] == (picks[did] == a["choice"]) and humans[did]["advised"] == a["choice"]
        mode = ("wait", "mid", "instant")[sorted(picks).index(did) % 3]
        if mode == "wait":
            assert a["late"] is False and not a["hindsight"]
        elif mode == "mid":
            assert a["late"] is True and not a["hindsight"]
        else:
            assert a["late"] is True and a["hindsight"]  # answered before the ask started: a look back
    stats = json.load(open(os.path.join(game.log.dir, "meta.json")))["coach"]
    kinds = {did: decisions[did]["kind"] for did in decisions}
    assert stats["late"] >= 1 and stats["hindsight"] >= 1 and stats["skipped"] >= 1 and stats["auto"] >= 1
    assert stats["followed"] >= 1 and stats["diverged"] >= 1
    assert all(kinds[did] not in ("place",) for did in asked)
    # The order on the panel: a live advice comes before the human's move, a late one after it.
    seq = {(m["type"], m.get("id")): m["seq"] for m in bus.backlog(gid)}
    for did, a in advice.items():
        if a["source"] == "backend":
            if not a["late"]:
                assert seq[("advice", did)] < seq[("reply", did)]
            assert seq[("human_choice", did)] > max(seq[("advice", did)], seq[("reply", did)])


def test_logs_review_and_notes(coached, bus, cfg, db):
    coach, game, asked, slow = coached
    game.on_event({"t": "event", "e": "chat", "player": 0, "position": 0, "message": "!the coach should keep Veiler",
                   "source": "duelist"})
    play(game, asked, slow, lambda i: "wait")
    gid = game.log.web.game_id
    ack = bus.feedback(gid, 0, "a note from the panel")
    coach.close(timeout=20)
    folder = game.log.dir
    with open(os.path.join(folder, "feedback.md"), encoding="utf-8") as f:
        notes = f.read().splitlines()
    assert notes[0].startswith("- (coach game, turn ") and notes[0].endswith("the coach should keep Veiler")
    assert notes[1] == f"- ({ack['context']}) a note from the panel" and "coach game" in ack["context"]
    # game.md marks the human's own moves and the coach's advice.
    md = open(os.path.join(folder, "game.md"), encoding="utf-8").read()
    assert "> **human** (" in md and "🎓 **Coach**" in md and "**Player feedback**" in md
    rows = [json.loads(line) for line in open(os.path.join(folder, "game.jsonl"), encoding="utf-8")]
    assert all(r["msg"]["source"] == "human" for r in rows if r["kind"] == "reply")
    assert any(r["kind"] == "advice" and r["msg"]["source"] == "backend" for r in rows)
    meta = json.load(open(os.path.join(folder, "meta.json")))
    assert meta["mode"] == "coach" and meta["coach"]["level"] == "beginner" and meta["stats"]["by_source"]["human"] > 0
    # The review: review.md, the panel's review message, and what the reviewer was asked.
    review = open(os.path.join(folder, "review.md"), encoding="utf-8").read()
    assert review.startswith("# Coach review: Saffira") and "Scripted review." in review
    prompt = open(os.path.join(folder, "review-prompt.md"), encoding="utf-8").read()
    assert "DUEL LOG" in prompt and "✓ as the coach advised" in prompt and "the coach should keep Veiler" in prompt
    reviews = by_type(bus, gid)["review"]
    assert len(reviews) == 1 and reviews[0]["markdown"] == review and reviews[0]["path"].endswith("review.md")
    # A recorded coach game replays with its advice, the human's choices and the review.
    replayed = load_game(folder, db)
    types = [m["type"] for m in replayed]
    assert "advice" in types and "human_choice" in types and types[-1] == "review"
    live_pairs = {(m["type"], m["id"]) for m in by_type(bus, gid)["human_choice"]}
    rec_pairs = {(m["type"], m["id"]) for m in replayed if m["type"] == "human_choice"}
    assert live_pairs == rec_pairs


def test_the_coach_prompt(coached, db):
    coach, game, asked, slow = coached
    prompt = game.brain.system_prompt
    assert prompt.startswith("You are an expert Yu-Gi-Oh! duelist, coaching a human through a duel")
    assert "# Coaching mode" in prompt and "new to this deck" in prompt and "# The deck they play: Saffira" in prompt
    assert "piloting" not in prompt and "playing a duel as a bot" not in prompt
    terse = Profile("saffira", db, coach.cfg).system_prompt("coach", "MR3", level="intermediate")
    assert "one terse sentence" in terse and "new to this deck" not in terse
