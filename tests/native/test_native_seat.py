"""AgentSeat behaviour: worker thread and awaitables, pace, timeouts and errors, RETRY, chat, Bo3 game boundaries,
and the arena CLI's agent: seats (needs the EDOPro install; no mono, no LLM)."""

import asyncio
import inspect
import json
import os
import threading
import time

import pytest

from native_helpers import play
from ygo_agent.arena import cli
from ygo_agent.arena import messages as M
from ygo_agent.arena.duel import Duel, DuelConfig, Pending
from ygo_agent.arena.native_seat import AgentSeat
from ygo_agent.arena.runner import run_match
from ygo_agent.arena.seats import SeatFeed, SeatView
from ygo_agent.backends.heuristic import Policy
from ygo_agent.core.constants import WIN_REASON_TIMED_OUT

pytestmark = pytest.mark.integration


def scripted(policy):
    return {"name": "test", "type": "scripted", "policy": policy}


def custom_seat(make_seat, agent_cfg, agent_db, engine, policy, **kw):
    """A seat with a scripted backend (its policy runs on the seat's worker thread)."""
    base = make_seat("saffira")
    kw.setdefault("threaded", True)  # a scripted backend would otherwise answer inline
    seat = AgentSeat("Scripted", agent_cfg, agent_db, base.profile, scripted(policy), cards=engine.cards, **kw)
    make_seat.track(seat)
    return seat


async def drive(engine, seats, decks, seed, limit=10 ** 6, on_step=None):
    """A duel on the running event loop, awaiting the seats' answers like the arena server does."""
    names = (seats[0].name, seats[1].name)
    duel = Duel(engine, DuelConfig(), decks, names, seed=seed,
                observers=[SeatFeed(s, t) for t, s in enumerate(seats)])
    for t, s in enumerate(seats):
        s.bind(SeatView(duel, t))
    step = duel.start()
    n = 0
    while isinstance(step, Pending) and n < limit:
        answer = seats[step.team].choose(step.message, step.retry)
        if inspect.isawaitable(answer):
            answer = await answer
        step = duel.respond(answer)
        n += 1
        if on_step:
            on_step(n)
    duel.close()
    return duel


def test_slow_backend_runs_off_the_event_loop(make_seat, agent_cfg, agent_db, engine, quiet):
    heuristic = Policy(agent_db)
    threads = set()

    def slow(d):
        threads.add(threading.current_thread().name)
        time.sleep(0.12)
        return heuristic.choose(d)
    a = custom_seat(make_seat, agent_cfg, agent_db, engine, slow)
    b = make_seat("blackwing")
    gaps = []

    async def scenario():
        last = [time.monotonic()]
        stop = asyncio.Event()

        async def ticker():
            while not stop.is_set():
                now = time.monotonic()
                gaps.append(now - last[0])
                last[0] = now
                await asyncio.sleep(0.01)
        task = asyncio.create_task(ticker())
        await drive(engine, (a, b), (a.deck(engine), b.deck(engine)), 7, limit=150)
        stop.set()
        await task
    asyncio.run(scenario())
    assert a.stats["decisions"] >= 5 and a.stats["errors"] == 0 and a.stats["timeouts"] == 0
    assert threads and all(t.startswith("agent-") for t in threads)
    assert max(gaps) < 0.1, f"the event loop stalled for {max(gaps):.2f}s"


def test_pace_sets_a_minimum_time_per_decision(make_seat, engine, quiet):
    a, b = make_seat("saffira", pace=0.05), make_seat("blackwing")
    times = []

    async def scenario():
        last = [time.monotonic()]

        def step(n):
            times.append(time.monotonic() - last[0])
            last[0] = time.monotonic()
        await drive(engine, (a, b), (a.deck(engine), b.deck(engine)), 3, limit=40, on_step=step)
    started = time.monotonic()
    asyncio.run(scenario())
    assert a.stats["decisions"] >= 3
    assert time.monotonic() - started >= 0.05 * a.stats["decisions"]


def test_errors_and_timeouts_fall_back_to_the_heuristic(make_seat, agent_cfg, agent_db, engine, quiet):
    release = threading.Event()
    calls = [0]

    def flaky(d):
        calls[0] += 1
        if calls[0] % 3 == 1:
            raise RuntimeError("backend exploded")
        if calls[0] % 3 == 2 and not release.is_set():
            release.wait(1.0)  # longer than the seat's guard below
        return Policy(agent_db).choose(d)
    a = custom_seat(make_seat, agent_cfg, agent_db, engine, flaky, timeout=0.2)
    b = make_seat("blackwing")
    duel = asyncio.run(drive(engine, (a, b), (a.deck(engine), b.deck(engine)), 5, limit=60))
    release.set()
    a.close()
    assert duel.retries == 0
    assert a.stats["errors"] >= 1 and a.stats["timeouts"] >= 1 and a.stats["fallbacks"] >= 2, a.stats


def test_after_a_retry_the_same_response_is_not_sent_again(make_seat, quiet):
    seat = make_seat("saffira")
    prompt = M.SelectIdleCmd(0, [], [], [], [], [], [], True, True, False)
    first = seat.choose(prompt, False)
    seat.on_message(M.Retry())
    second = seat.choose(prompt, True)
    assert first != second and seat.stats["retries"] == 1
    assert any("engine rejected" in line for line in seat.brain.history)


def test_chat_notes_are_saved_and_acknowledged(make_seat, agent_cfg, engine, quiet):
    said = []

    class Noted(AgentSeat):
        def choose(self, prompt, retry):
            if self.next_id == 3 and not said:
                self.room_chat("!keep the hand trap for their turn", "duelist", "Human")
                self.room_chat("good luck", "spectator", "Watcher")
            return super().choose(prompt, retry)
    base = make_seat("saffira")
    a = Noted("Noted", agent_cfg, base.db, base.profile, base.backend, cards=engine.cards, chat=said.append)
    b = make_seat("blackwing")
    play(engine, (a, b), (a.deck(engine), b.deck(engine)), 11)
    a.close()
    assert said and "Noted feedback #1" in said[0]
    folder = a.brain.log.dir
    assert "keep the hand trap" in open(os.path.join(folder, "feedback.md")).read()
    assert 'A spectator says in chat: "good luck"' in open(os.path.join(folder, "game.md")).read()


def test_bo3_games_get_their_own_logs_and_ids(make_seat, agent_cfg, engine, quiet):
    a, b = make_seat("saffira"), make_seat("blackwing")
    a.trace, b.trace = [], []
    match = run_match(engine, DuelConfig(), (a.deck(engine), b.deck(engine)), (a, b), best_of=3, seed=21)
    a.close()
    b.close()
    games = len(match.games)
    assert games >= 2
    for s in (a, b):
        assert [m["e"] for m in s.trace if m.get("e") == "room"] == ["room"]
        overs = [i for i, m in enumerate(s.trace) if m.get("kind") == "game_over"]
        assert len(overs) == games
        for start, end in zip([-1] + overs[:-1], overs):
            ids = [m["id"] for m in s.trace[start + 1:end + 1] if m["t"] == "decide"]
            assert ids and ids[0] == 1 and ids == sorted(ids)
        assert s.stats["games"] == games
    logs = [d for d in os.listdir(agent_cfg["games_dir"]) if d != "latest"]
    assert len(logs) == 2 * games


def test_seat_specs():
    assert cli._seat_spec("agent:saffira") == ("agent", "saffira")
    assert cli._seat_spec("agent:saffira:opus") == ("agent", "saffira:opus")
    with pytest.raises(Exception):
        cli._seat_spec("agent:")
    with pytest.raises(Exception):
        cli._seat_spec("robot:x")


def test_bots_command_with_agent_seats(engine, tmp_path, quiet):
    """Two in-process seats (an agent and a random policy) through the arena host, no network client at all."""
    code = cli.main(["bots", "--seat0", "agent:saffira:heuristic", "--seat1", "ai:random", "--deck1", "Blackwing",
                     "--games", "1", "--no-lan", "--games-dir", str(tmp_path / "games"), "--out",
                     str(tmp_path / "arena"), "--chat", "off", "--seed", "3", "--timeout", "300"])
    assert code == 0
    logs = [d for d in os.listdir(tmp_path / "games") if d != "latest"]
    assert len(logs) == 1 and "-vs-random-ai" in logs[0]
    first = json.loads(open(tmp_path / "games" / logs[0] / "game.jsonl").readline())
    assert first["msg"]["e"] == "room" and first["msg"]["time_limit"] == 0


def test_watcher_builds_and_decodes_another_players_decisions(make_seat, engine, quiet):
    """Coach mode's building blocks: a random player's prompts as decisions, its responses as option indices."""
    from ygo_agent.agent.validate import validate
    from ygo_agent.arena.native_seat import SeatWatcher
    from ygo_agent.arena.policies import RandomPolicy
    from ygo_agent.arena.seats import PolicySeat
    from schema import decision_errors
    seen = []
    a = make_seat("saffira")
    for seed in range(3):
        watcher = SeatWatcher(1, engine.cards, on_choice=lambda d, c: seen.append((d, c)))
        b = PolicySeat("Random", RandomPolicy(seed))
        play(engine, (a, b), (a.deck(engine), make_seat("blackwing").deck(engine)), 40 + seed, observers=[watcher])
    assert len(seen) > 100
    unmapped = 0
    for d, choice in seen:
        assert not decision_errors(d), decision_errors(d)
        if choice is None:
            unmapped += 1
            assert d["kind"] == "select_unselect"  # unselecting a picked card has no option index
        elif d["kind"] == "announce_card":
            assert choice[0] in d["options"]
        else:
            assert validate(d, choice) is None or d["kind"] == "select_unselect", (d["kind"], choice)
    assert unmapped < len(seen) // 10


def test_agent_seat_in_a_room_with_a_client(make_seat, engine, quiet):
    """A network player (the stand-in for EDOPro) against an agent seat: the duel runs, the player's `!note` is
    saved and acknowledged in the room's chat, and the agent's time doesn't count against anyone."""
    from ygo_agent.arena import server as S
    from ygo_agent.arena.client import ArenaClient, chat_texts
    from ygo_agent.arena.native_seat import add_to_room
    from ygo_agent.arena.policies import RandomPolicy

    class Cards:
        cards = engine.cards
    policy, sent = RandomPolicy(3), []
    agent = make_seat("saffira")

    async def scenario():
        room = S.Room(engine, S.RoomConfig(duel=DuelConfig(rules="mr3"), max_matches=1, rematch=False, seed=9,
                                           lan_discovery=False, time_limit=60))
        add_to_room(room, 1, agent, agent.deck(engine))
        server = S.ArenaServer(room, "127.0.0.1", 0)
        await server.start()

        def play_and_note(prompt):
            if not sent:
                client.chat("!you should keep Veiler for my turn")
                sent.append(True)
            return policy(prompt, Cards)
        client = ArenaClient("Human", make_seat("blackwing").deck(engine), play_and_note)
        await client.connect("127.0.0.1", server.port)
        try:
            await asyncio.wait_for(room.finished.wait(), 240)
        finally:
            await client.close()
            await server.close()
        return room, client
    room, client = asyncio.run(scenario())
    (duel, result), = room.games
    assert result.retries == 0 and result.reason != WIN_REASON_TIMED_OUT
    agent.close()
    assert any("Noted feedback #1" in t for t in chat_texts(client.log))
    assert "keep Veiler" in open(os.path.join(agent.brain.log.dir, "feedback.md")).read()


def test_linked_seats_share_the_web_panel_game_id(make_seat, engine, quiet):
    from ygo_agent.arena.native_seat import link
    a, b = make_seat("saffira"), make_seat("blackwing")
    assert link(a, b, match_id="selfplay-test") == "selfplay-test"
    match = run_match(engine, DuelConfig(), (a.deck(engine), b.deck(engine)), (a, b), best_of=1, seed=5)
    assert len(match.games) == 1
    assert a.brain.game_id == b.brain.game_id == "selfplay-test-g1"
    assert (a.brain.seat, b.brain.seat) == (0, 1)
