"""The agent's hook: everything GameLog logs reaches the bus when a panel runs, and nothing does when it doesn't.
Played on a saved regression case, which is a real logged game."""

import json
import os

from helpers import CASES, load_case
from web_helpers import play_case
from ygo_agent.agent.brain import DuelBrain
from ygo_agent.agent.describe import Describer
from ygo_agent.agent.profile import Profile


def test_no_panel_no_messages(cfg, db, scripted, quiet_bus):
    brain, _ = play_case(cfg, db, scripted)
    assert quiet_bus.games() == [] and not brain.log.web.live
    brain.close()


def test_a_logged_game_through_the_bus(cfg, db, scripted, bus):
    brain, case = play_case(cfg, db, scripted)
    brain.on_event({"t": "event", "e": "win", "result": 0, "reason": 1})
    gid = brain.log.web.game_id
    msgs = bus.backlog(gid)
    brain.close()
    assert [m["seq"] for m in msgs] == list(range(1, len(msgs) + 1))
    kinds = [m["type"] for m in msgs]
    assert kinds[0] == "game_start" and msgs[0]["deck_name"] == "Blackwing" and msgs[0]["dir"]
    assert {"meta", "event", "decision", "reply", "game_end"} <= set(kinds)
    words = Describer(db)
    events = [m for m in msgs if m["type"] == "event"]
    assert len(events) == sum(1 for m in case["messages"] if m.get("t") == "event") + 1
    assert all(m["text"] == words.event(m["ev"]) for m in events if m["ev"]["e"] != "chat")
    decisions = [m for m in msgs if m["type"] == "decision"]
    replies = {m["id"]: m for m in msgs if m["type"] == "reply"}
    logged = [m for m in case["messages"] if m.get("t") == "decide"]
    assert [m["decision"]["id"] for m in decisions] == [d["id"] for d in logged]
    assert set(replies) == {d["id"] for d in logged}
    for m in decisions:
        assert m["question"] == words.question(m["decision"]) and len(m["options"]) == len(m["decision"].get("options", []))
        r = replies[m["decision"]["id"]]
        assert r["source"] and "sent" in r
        assert isinstance(r["choice"], list) or m["decision"]["kind"] == "place"  # zones are left to the bot
        if r["source"] == "backend":
            assert r["why"] == "scripted" and r["label"] and "seconds" in r["usage"]
    # Card names travel with the messages, so the browser can name every card on the board.
    named = set()
    for m in msgs:
        named |= set(m.get("cards", {}))
    on_board = Describer(db).ids_in_state(decisions[-1]["decision"]["state"])
    assert {str(i) for i in on_board} <= named
    assert msgs[-1]["type"] in ("game_end", "meta") and any(m["type"] == "game_end" and m["result"] == "win" for m in msgs)
    summary = bus.games()[0]
    assert summary["game_id"] == gid and summary["decisions"] == len(logged) and not summary["live"]


def test_a_select_unselect_pick_shows_every_card_planned(cfg, db, scripted, bus):
    """The bot is sent one pick per prompt; the panel shows the whole planned selection."""
    for path in CASES:
        case = load_case(path)
        multi = [m for m in case["messages"] if m.get("t") == "decide" and m["kind"] == "select_unselect"
                 and m.get("max", 1) > 1 and len(m.get("options", [])) > 1]
        if multi:
            break
    else:
        return
    deck = path.split(os.sep)[-3]
    target = multi[0]
    scripted["policy"] = lambda d: [0, 1] if d["id"] == target["id"] else None
    brain = DuelBrain(cfg, db, Profile(deck, db, cfg), prewarm=False)
    for m in case["messages"]:
        if m is target:
            brain.on_decide(json.loads(json.dumps(m)))
            break
        if m.get("t") == "event":
            brain.on_event(json.loads(json.dumps(m)))
    reply = [m for m in bus.backlog(brain.log.web.game_id) if m["type"] == "reply"][-1]
    brain.close()
    assert reply["id"] == target["id"] and reply["choice"] == [0, 1] and reply["sent"] == [0]


def test_coach_advice_and_the_humans_move_in_either_order(cfg, db, bus):
    """Coach mode: advice before the human's move, or after it (late); human_choice comes with whichever is second."""
    from ygo_agent.agent.gamelog import GameLog
    log = GameLog(cfg["games_dir"], "Saffira", game_id="coach-test")
    log.record("decide", {"t": "decide", "id": 1, "kind": "idle", "options": [{"a": "to_end"}, {"a": "to_battle"}],
                          "state": {}})
    log.advice(1, [1], why="attack first", source="backend", late=False, kind="idle")
    log.decision(1, "q", ["End", "Battle"], [1], "followed the coach", None, "human", 2.0, label="human", echo=False)
    log.record("reply", {"id": 1, "choice": [1], "source": "human"})
    log.record("decide", {"t": "decide", "id": 2, "kind": "select_unselect", "options": [{}, {}], "state": {}})
    log.decision(2, "q", ["A", "B"], [0], "answered before the coach's advice", None, "human", 0.5, label="human",
                 echo=False)
    log.record("reply", {"id": 2, "choice": [0], "source": "human"})
    log.advice(2, [0, 1], why="both", source="backend", late=True, kind="select_unselect")
    log.record("decide", {"t": "decide", "id": 3, "kind": "place", "state": {}})
    log.advice(3, None, why="nothing to advise", source="auto")
    log.decision(3, "q", [], [4], "", None, "human", 0.1, label="human", echo=False)
    log.record("reply", {"id": 3, "choice": [4], "source": "human", "trivial": True})
    log.close()
    msgs = [m for m in bus.backlog("coach-test") if m["type"] in ("advice", "reply", "human_choice")]
    assert [(m["type"], m["id"]) for m in msgs] == [("advice", 1), ("reply", 1), ("human_choice", 1), ("reply", 2),
                                                     ("advice", 2), ("human_choice", 2), ("advice", 3), ("reply", 3)]
    h1, h2 = msgs[2], msgs[5]
    assert h1 == {**h1, "choice": [1], "advised": [1], "matched": True}
    assert h2 == {**h2, "choice": [0], "advised": [0, 1], "matched": True}  # the first pick of the advised selection
    assert msgs[1]["source"] == "human" and msgs[4]["late"] is True and msgs[7]["trivial"] is True


def test_a_note_from_the_panel_is_saved_like_a_chat_note(cfg, db, scripted, bus):
    brain, case = play_case(cfg, db, scripted)
    gid = brain.log.web.game_id
    last = [m for m in case["messages"] if m.get("t") == "decide"][-1]
    ack = bus.feedback(gid, 0, "keep Chinook for their attack")
    assert ack == {"n": 1, "context": f"turn {brain.turn}, right after decision #{last['id']}"}
    brain.on_event({"t": "event", "e": "chat", "player": 1, "position": 0, "message": "!and use Shura", "source": "duelist"})
    ack2 = bus.feedback(gid, 0, "about an earlier one", decision=3, turn=1)
    assert ack2["n"] == 3 and ack2["context"] == "turn 1, right after decision #3"
    brain.close()
    with open(os.path.join(brain.log.dir, "feedback.md"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert lines == [f"- ({ack['context']}) keep Chinook for their attack",
                     f"- (turn {brain.turn}, right after decision #{last['id']}) and use Shura",
                     "- (turn 1, right after decision #3) about an earlier one"]
    with open(os.path.join(brain.log.dir, "game.md"), encoding="utf-8") as f:
        assert "**Web panel feedback**" in f.read()
    acks = [m for m in bus.backlog(gid) if m["type"] == "feedback_ack"]
    assert [a["who"] for a in acks] == ["Web panel", "Opponent", "Web panel"]
    # After the game's log is closed, a late note still lands in feedback.md.
    assert bus.feedback(gid, 0, "one more")["n"] == 4


def test_two_seats_of_one_game(cfg, db, scripted, bus):
    a, _ = play_case(cfg, db, scripted, game_id="selfplay-1", seat=0)
    b, _ = play_case(cfg, db, scripted, name="keep-vata-no-bwd", game_id="selfplay-1", seat=1)
    games = bus.games()
    a.close()
    b.close()
    assert len(games) == 1 and [s["seat"] for s in games[0]["seats"]] == [0, 1]
    seats = {m["seat"] for m in bus.backlog("selfplay-1") if m["type"] == "decision"}
    assert seats == {0, 1} and a.log.dir != b.log.dir
