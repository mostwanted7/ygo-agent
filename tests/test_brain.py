"""The decision flow end to end with a scripted backend: fixtures, logging, copilot, Bo3 routing, chat."""

import json
import os

import pytest

from helpers import CASES, case_id, load_case
from ygo_agent.agent.bridge_server import Match, Runtime
from ygo_agent.agent.brain import DuelBrain
from ygo_agent.agent.profile import Profile


def run(brain, messages, scripted):
    replies = []
    for m in messages:
        m = json.loads(json.dumps(m))
        if m.get("t") == "event":
            brain.on_event(m)
        else:
            scripted["decision"] = m
            replies.append(brain.on_decide(m))
    return replies


def records(game_dir):
    with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_fixture_plays_through(path, db, cfg, scripted):
    case = load_case(path)
    profile = Profile(path.split(os.sep)[-3], db, cfg)
    brain = DuelBrain(cfg, db, profile, prewarm=False)
    replies = run(brain, case["messages"], scripted)
    brain.close()
    decisions = [m for m in case["messages"] if m.get("t") == "decide"]
    assert [r["id"] for r in replies] == [d["id"] for d in decisions]
    for d, r in zip(decisions, replies):
        if r["choice"] is not None and d["kind"] == "announce_card":
            assert r["choice"][0] in d["options"]  # announce_card replies with the card id itself
        elif r["choice"] is not None and d["kind"] == "select_unselect":
            assert len(r["choice"]) <= 1  # one pick per prompt; the rest is planned
    says = [r["say"] for r in replies if r["say"]]
    assert len(says) <= 4 and all(not s.startswith("[") for s in says), says  # banter only, no explanations
    # Every decision got its reply logged, with where it came from.
    recs = records(brain.log.dir)
    logged = [r["msg"] for r in recs if r["kind"] == "reply"]
    assert [r["id"] for r in logged] == [d["id"] for d in decisions]
    assert all(r["source"] for r in logged)
    # The prompt is model-neutral and states the configured rules.
    system = scripted["sessions"][0].system_prompt
    assert system.startswith("You are an expert Yu-Gi-Oh! duelist") and "Master Rule 3" in system
    assert "Master Rule 5" not in system and "You are Claude" not in system
    assert "# General strategy" in system and "Quick-Play Spell" in system


def test_room_flags_set_the_rules(db, cfg, scripted):
    profile = Profile("saffira", db, cfg)
    brain = DuelBrain(cfg, db, profile, prewarm=False, room={"t": "event", "e": "room", "duel_flags": 0x2E800})
    assert brain.rules_key == "MR5"
    assert "Master Rule 5" in brain.system_prompt
    brain.close()


def test_feedback_note_and_spectator_chat(db, cfg, scripted):
    profile = Profile("saffira", db, cfg)
    brain = DuelBrain(cfg, db, profile, prewarm=False)
    brain.on_event({"t": "event", "e": "chat", "player": 1, "position": 0, "message": "!save Veiler", "source": "duelist"})
    brain.on_event({"t": "event", "e": "chat", "player": 0, "position": 0, "message": "my own line", "source": "duelist"})
    brain.on_event({"t": "event", "e": "chat", "player": 7, "position": 0, "message": "nice", "source": "spectator"})
    brain.on_event({"t": "event", "e": "chat", "player": 8, "position": 0, "message": "joined", "source": "system"})
    assert brain.say_queue == ["Noted feedback #1."]
    assert brain.history == ['A spectator says in chat: "nice"']
    with open(os.path.join(brain.log.dir, "feedback.md"), encoding="utf-8") as f:
        assert "save Veiler" in f.read()
    brain.close()


def copilot_case():
    return next(p for p in CASES if p.endswith("main2-to-set-lance.json"))


def test_copilot_logs_the_move_actually_taken(db, cfg, scripted, monkeypatch):
    cfg["mode"] = "copilot"
    case = load_case(copilot_case())
    profile = Profile("saffira", db, cfg)
    brain = DuelBrain(cfg, db, profile, prewarm=False)
    for m in case["messages"][:-1]:
        if m.get("t") == "event":
            brain.on_event(json.loads(json.dumps(m)))
    d = json.loads(json.dumps(case["messages"][-1]))
    scripted["decision"] = d
    scripted["policy"] = lambda _: [2]          # the agent suggests ending the turn
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")  # the pilot goes to Main Phase 2 instead
    reply = brain.on_decide(d)
    assert reply["choice"] == [1]
    rec = [r["msg"] for r in records(brain.log.dir) if r["kind"] == "reply"][-1]
    assert rec["choice"] == [1] and rec["suggested"] == [2] and rec["source"] == "pilot"
    with open(os.path.join(brain.log.dir, "game.md"), encoding="utf-8") as f:
        md = f.read().split(f"**Decision #{d['id']}**")[-1]
    assert "✅ `[1]`" in md and "✅ `[2]`" not in md and "The pilot chose [1]" in md
    assert brain.history[-1].startswith("The pilot chose")
    brain.close()


def ev(e, **fields):
    return {"t": "event", "e": e, **fields}


def test_match_starts_a_fresh_game_for_each_game_of_a_bo3(db, cfg, scripted):
    profile = Profile("saffira", db, cfg)
    match = Match(Runtime(cfg, db, profile), prewarm=False)
    state = {"turn": 1, "turn_player": 0, "phase": 4, "chain": [],
             "me": {"lp": 8000, "hand": [], "mz": [], "sz": [], "gy": [], "ban": [], "deck": 30, "extra": []},
             "opp": {"lp": 8000, "hand": [], "mz": [], "sz": [], "gy": [], "ban": [], "deck": 30, "extra": []}}

    def decide(i, kind="position", **fields):
        d = {"t": "decide", "id": i, "kind": kind, "state": state, "card_id": 56350972, "options": [1], **fields}
        scripted["decision"] = d
        return match.on_message(d)

    assert match.on_message(ev("room", duel_flags=858112, best_of=3)) is None
    assert decide(1, "go_first", options=[])["choice"] == [1]
    match.on_message(ev("start", first=True, lp=[8000, 8000], names=["Agent", "Rival"]))
    game1 = match.brain
    assert decide(2)["choice"] == [0]
    match.on_message(ev("win", result=1, reason=1))
    end = decide(3, "game_over", result=1, reason=1)
    assert end["choice"] is None and end["say"]  # the loss line rides on the game_over reply
    match.on_message(ev("chat", player=1, position=0, message="!good game", source="duelist"))
    assert match.brain is game1  # a note typed after the game still belongs to it
    decide(1)  # game 2: decision ids restart, and a new brain/log takes over
    game2 = match.brain
    assert game2 is not game1 and game2.room["duel_flags"] == 858112
    match.on_message(ev("start", first=False, lp=[8000, 8000], names=["Agent", "Rival"]))
    assert match.brain is game2 and game2.started
    match.close()
    assert game1.log.dir != game2.log.dir
    assert game1.log.dir.endswith("-vs-rival") and "-vs-rival" in game2.log.dir
    assert os.path.exists(os.path.join(game1.log.dir, "feedback.md"))
    assert not os.path.exists(os.path.join(game2.log.dir, "feedback.md"))
    kinds = [r["kind"] for r in records(game1.log.dir)]
    assert kinds[0] == "event" and "reply" in kinds
    with open(os.path.join(game1.log.dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["deck"] == "saffira" and meta["result"] == "loss" and meta["opponent"] == "Rival"
    assert meta["rules"] == "MR3"
    latest = os.path.join(cfg["games_dir"], "latest")
    assert os.path.realpath(latest) == os.path.realpath(game2.log.dir)
