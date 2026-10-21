"""The web panel's bus: backlog and catch-up, several games and seats, the Channel publishers use, SSE frames, and
the renderer that words messages the way describe.py does."""

import json

from ygo_agent.agent.describe import Describer
from ygo_agent.web.bus import Bus, Channel, sse
from ygo_agent.web.render import Renderer


def msg(game, kind="event", seat=0, **fields):
    return {"type": kind, "game_id": game, "seat": seat, **fields}


def test_nothing_is_published_until_a_panel_activates_the_bus():
    bus = Bus()
    assert bus.publish(msg("g")) is None
    assert Channel("g", bus=bus).send("event", ev={"e": "draw"}) is None
    assert bus.games() == []


def test_backlog_catch_up_and_live_messages():
    bus = Bus()
    bus.activate()
    for i in range(5):
        bus.publish(msg("a", n=i))
    bus.publish(msg("b", n=0))
    backlog, sub = bus.subscribe("a", after=2)
    assert [m["seq"] for m in backlog] == [3, 4, 5] and [m["n"] for m in backlog] == [2, 3, 4]
    bus.publish(msg("a", n=5))
    bus.publish(msg("b", n=1))                      # another game's event: not for this browser
    bus.publish(msg("b", "game_start", deck_name="Blackwing"))  # but its summary is (the game list)
    got = [sub.get(timeout=1), sub.get(timeout=1)]
    assert got[0]["game_id"] == "a" and got[0]["seq"] == 6
    assert got[1]["type"] == "game_start" and got[1]["game_id"] == "b"
    assert sub.get(timeout=0.05) is None
    sub.close()
    bus.publish(msg("a"))
    assert sub.get(timeout=0.05) is None
    assert [m["seq"] for m in bus.backlog("a", after=5)] == [6, 7]


def test_two_seats_of_one_game_and_the_game_list():
    bus = Bus()
    bus.activate()
    bus.publish(msg("g", "game_start", seat=0, deck_name="Saffira"))
    bus.publish(msg("g", "game_start", seat=1, deck_name="Blackwing"))
    bus.publish(msg("g", "meta", seat=1, backend={"label": "local (openai, qwen3:14b)"}))
    bus.publish(msg("g", "decision", seat=0, decision={"id": 1, "kind": "idle", "state": {"turn": 3}}))
    bus.publish(msg("solo", "game_start", deck_name="Saffira"))
    bus.publish(msg("solo", "meta", opponent="Rival"))
    games = {g["game_id"]: g for g in bus.games()}
    assert games["g"]["title"] == "Saffira vs Blackwing" and len(games["g"]["seats"]) == 2
    assert games["g"]["seats"][1]["label"] == "local (openai, qwen3:14b)"
    assert games["g"]["decisions"] == 1 and games["g"]["turn"] == 3 and games["g"]["live"]
    assert games["solo"]["title"] == "Saffira vs Rival"
    bus.publish(msg("g", "game_end", seat=0, result="win"))
    assert bus.seat_info("g", 0)["result"] == "win" and {g["game_id"]: g for g in bus.games()}["g"]["live"]
    bus.publish(msg("g", "game_end", seat=1, result="loss"))
    assert not {g["game_id"]: g for g in bus.games()}["g"]["live"]


def test_old_games_are_evicted_finished_ones_first():
    bus = Bus(max_games=2)
    bus.activate()
    bus.publish(msg("a", "game_start"))
    bus.publish(msg("b", "game_start"))
    bus.publish(msg("b", "game_end", result="win"))
    bus.on_feedback("b", 0, lambda *a, **k: {})
    bus.publish(msg("c", "game_start"))
    assert {g["game_id"] for g in bus.games()} == {"a", "c"}
    assert bus.feedback("b", 0, "late note") is None


def test_the_channel_sends_a_copy():
    bus = Bus()
    bus.activate()
    decision = {"id": 1, "state": {"me": {"extra": [{"id": 0}]}}}
    Channel("g", seat=1, bus=bus).send("decision", decision=decision)
    decision["state"]["me"]["extra"] = [{"id": 123}]  # the brain fills it in after logging
    m = bus.backlog("g")[0]
    assert m["seat"] == 1 and m["decision"]["state"]["me"]["extra"] == [{"id": 0}]
    assert Channel("g", enabled=False, bus=bus).send("event") is None  # quiet logs (replay, tests) stay quiet


def test_feedback_goes_to_the_seat_that_owns_the_game():
    bus = Bus()
    bus.activate()
    got = []
    bus.on_feedback("g", 1, lambda text, decision=None, turn=None: got.append((text, decision)) or {"n": 1})
    assert bus.feedback("g", 1, "save Veiler", decision=7) == {"n": 1}
    assert got == [("save Veiler", 7)]
    assert bus.feedback("g", 0, "wrong seat") is None


def test_a_renderer_failure_never_stops_a_message():
    bus = Bus()
    bus.activate(lambda m: 1 / 0)
    assert bus.publish(msg("g"))["render_error"]


def test_sse_frames():
    frame = sse({"type": "event", "game_id": "g", "seq": 3, "text": "line\nbreak"})
    assert frame.startswith(b"id: 3\ndata: ") and frame.endswith(b"\n\n")
    assert frame.count(b"\n") == 3  # JSON escapes newlines, so one data line
    assert json.loads(frame.decode().split("data: ", 1)[1])["text"] == "line\nbreak"
    assert not sse({"type": "games", "seq": 3}, event_id=False).startswith(b"id:")
    assert "é".encode() in sse({"type": "x", "text": "é"})


def test_the_renderer_uses_describe_words(db):
    render = Renderer(db)
    words = Describer(db)
    turn = {"t": "event", "e": "new_turn", "turn": 3, "player": 1}
    assert render(msg("g", ev=turn))["text"] == words.event(turn) == "=== TURN 3 (opponent's turn) ==="
    chat = render(msg("g", ev={"t": "event", "e": "chat", "player": 7, "position": 0, "message": "gg",
                               "source": "spectator"}))
    assert chat["text"] == 'A spectator says in chat: "gg"'
    note = render(msg("g", ev={"t": "event", "e": "chat", "player": 1, "position": 0, "message": "!save it"}))
    assert note["text"] is None  # !notes show up as feedback_ack instead
    card = next(iter(db.cards))
    d = {"id": 4, "kind": "select_card", "min": 1, "max": 1, "hint": 0, "cancelable": False,
         "options": [{"id": card, "c": 0, "l": 2, "s": 0, "p": 10}],
         "state": {"turn": 1, "turn_player": 0, "phase": 4, "chain": [],
                   "me": {"lp": 8000, "hand": [{"id": card, "c": 0, "l": 2, "s": 0, "p": 10}], "mz": [None] * 7,
                          "sz": [None] * 8, "gy": [], "ban": [], "deck": 30, "extra": []},
                   "opp": {"lp": 8000, "hand": [], "mz": [None] * 7, "sz": [None] * 8, "gy": [], "ban": [],
                           "deck": 30, "extra": []}}}
    out = render(msg("g", "decision", decision=d))
    assert out["question"] == words.question(d) and out["options"] == words.options(d)
    assert out["hint_text"] and out["cards"][str(card)]["n"] == db.name(card)
    again = render(msg("g", "decision", decision=d))
    assert "cards" not in again  # each card's brief goes out once per game
    assert "cards" in render(msg("other", "decision", decision=d))


def test_a_browser_that_falls_far_behind_is_dropped(monkeypatch):
    """It reconnects with Last-Event-ID and resumes from the backlog, instead of the queue growing forever."""
    monkeypatch.setattr("ygo_agent.web.bus.Subscription.MAX_QUEUED", 3)
    bus = Bus()
    bus.activate()
    _, sub = bus.subscribe("g")
    for _ in range(5):
        bus.publish(msg("g"))
    assert sub.overflow and [sub.get(timeout=0.1)["seq"] for _ in range(3)] == [1, 2, 3]
    assert [m["seq"] for m in bus.backlog("g", after=3)] == [4, 5]
