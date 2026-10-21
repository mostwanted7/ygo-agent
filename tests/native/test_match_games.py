"""run_games() for real (needs the EDOPro install; the WindBot test also needs mono, no LLM): in-process games in
parallel, a room with a WindBot deck AI, a spectator holding the start, both seats of a duel on one web-panel game,
and the selfplay/play commands."""

import asyncio
import json
import os
import socket
import threading
import time

import pytest

from ygo_agent import cli
from ygo_agent.arena.client import ArenaClient
from ygo_agent.match import MatchError, SeatSpec, run_games
from ygo_agent.web.bus import BUS

pytestmark = pytest.mark.integration


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def windbot_available(engine):
    from ygo_agent.arena.windbot import WindBotError, WindBotInstall, mono_path
    if mono_path() is None:
        return False
    try:
        WindBotInstall.find(engine.install.root)
        return True
    except WindBotError:
        return False


def kw(agent_cfg, agent_db, engine, **extra):
    return {"cfg": agent_cfg, "db": agent_db, "engine": engine, "quiet": True, "lan": False, **extra}


def test_in_process_games_in_parallel(engine, agent_db, agent_cfg, quiet):
    run = run_games("saffira:heuristic", "blackwing:random", games=4, parallel=2, seed=40,
                    **kw(agent_cfg, agent_db, engine))
    assert run.path == "in-process" and not run.interrupted
    assert [(g.match, g.game) for g in run.games] == [(1, 1), (2, 1), (3, 1), (4, 1)]
    for g in run.games:
        assert g.winner in (0, 1, None) and g.turns > 0 and g.reason and g.seconds > 0 and g.retries == 0
        assert os.path.isfile(g.replay)
        for s in g.seats:
            assert s.kind == "agent" and s.stats["decisions"] > 0 and s.result in ("win", "loss", "draw")
            meta = json.load(open(os.path.join(s.log_dir, "meta.json")))
            assert meta["mode"] == "selfplay" and meta["match"]["match"] == g.match and meta["match"]["seat"] == s.role
            assert os.path.isfile(os.path.join(s.log_dir, "replay.yrpX"))
        a, b = g.seats
        assert a.log_dir != b.log_dir and {a.result, b.result} in ({"win", "loss"}, {"draw"})
    a, b, draws = run.wins()
    assert a + b + draws == 4
    saved = json.load(open(os.path.join(run.out, "results.json")))
    assert len(saved["games"]) == 4 and saved["seats"][0]["games"] == 4 and saved["wins"]["A"] == a
    assert run.seat_totals(1)["decisions"] == sum(g.seats[1].stats["decisions"] for g in run.games)
    assert any("Results (4 games)" in line for line in run.summary_lines())


def test_a_room_with_a_windbot_deck_ai(engine, agent_db, agent_cfg, quiet):
    if not windbot_available(engine):
        pytest.skip("mono or WindBot not available")
    run = run_games("saffira:heuristic", "windbot:Blue-Eyes", games=1, seed=3, timeout=300,
                    **kw(agent_cfg, agent_db, engine))
    assert run.path == "arena" and len(run.games) == 1
    g = run.games[0]
    me, bot = g.seats
    assert bot.kind == "windbot" and bot.name == "Blue-Eyes AI" and bot.stats is None
    assert me.stats["decisions"] > 0 and os.path.isfile(os.path.join(me.log_dir, "replay.yrpX"))
    meta = json.load(open(os.path.join(me.log_dir, "meta.json")))
    assert meta["opponent_info"] == {"kind": "windbot", "deck": "Blue-Eyes"} and meta["mode"] == "selfplay"
    assert g.winner in (0, 1) and os.path.isfile(g.replay)


def test_first_decides_who_goes_first_in_process_and_in_rooms(engine, agent_db, agent_cfg, quiet):
    """run_games(first=): the same option in-process and in a WindBot room (RoomConfig.first), no hooks."""
    for first in (0, 1):
        run = run_games("saffira:heuristic", "blackwing:random", games=2, seed=41, first=first,
                        **kw(agent_cfg, agent_db, engine))
        assert [g.first for g in run.games] == [first, first]
    with pytest.raises(MatchError, match="first"):
        run_games("saffira:heuristic", "blackwing:random", first=2, **kw(agent_cfg, agent_db, engine))
    if not windbot_available(engine):
        pytest.skip("mono or WindBot not available")
    for first in (1, 0):
        run = run_games("saffira:heuristic", "windbot:Blue-Eyes", games=1, seed=5, first=first, timeout=300,
                        **kw(agent_cfg, agent_db, engine))
        assert run.path == "arena" and [g.first for g in run.games] == [first]


def test_spectate_waits_for_a_spectator(engine, agent_db, agent_cfg, quiet):
    port = free_port()
    out = {}

    def play():
        out["run"] = run_games("saffira:heuristic", "blackwing:heuristic", games=2, spectate=True, port=port,
                               bind="127.0.0.1", **kw(agent_cfg, agent_db, engine))
    t = threading.Thread(target=play, daemon=True)
    t.start()

    async def watch():
        await asyncio.sleep(1.5)
        assert t.is_alive(), "the games started without waiting for a spectator"
        joined = time.time()
        client = ArenaClient("Watcher")
        await client.connect("127.0.0.1", port)
        while t.is_alive() and time.time() - joined < 120:
            await asyncio.sleep(0.1)
        await client.close()
        return client.log, joined
    log, joined = asyncio.run(watch())
    t.join(30)
    run = out["run"]
    assert len(run.games) == 2 and log.position == 7  # an observer
    assert sum(1 for raw in log.game if raw[0] == 4) == 2  # MSG_START: it watched both games (through the rematch)
    first_game_start = min(json.load(open(os.path.join(s.log_dir, "meta.json")))["started"]
                           for s in run.games[0].seats)
    assert time.mktime(time.strptime(first_game_start, "%Y-%m-%d %H:%M:%S")) >= int(joined) - 1


def test_both_seats_publish_to_one_web_game(engine, agent_db, agent_cfg, quiet):
    from ygo_agent.web.render import Renderer
    BUS.reset()
    BUS.activate(Renderer(agent_db))
    try:
        run = run_games("saffira:heuristic", "blackwing:heuristic", games=2, parallel=2, seed=9,
                        **kw(agent_cfg, agent_db, engine))
        games = BUS.games()
        assert len(games) == 2, [g["game_id"] for g in games]
        for summary in games:
            assert [s["seat"] for s in summary["seats"]] == [0, 1]
            assert {s["deck"] for s in summary["seats"]} == {"saffira", "blackwing"}
            backlog = BUS.backlog(summary["game_id"])
            assert {m["seat"] for m in backlog if m["type"] == "decision"} == {0, 1}
            assert sum(1 for m in backlog if m["type"] == "game_end") == 2
        assert len({g["game_id"] for g in games}) == 2 and all(g["game_id"].startswith(os.path.basename(run.out))
                                                                for g in games)
    finally:
        BUS.reset()


def test_setup_problems_are_match_errors(engine, agent_db, agent_cfg):
    with pytest.raises(MatchError, match="no deck"):
        run_games("no-such-deck:heuristic", "heuristic", **kw(agent_cfg, agent_db, engine))
    with pytest.raises(MatchError, match="no backend profile"):
        run_games("saffira:nope", "heuristic", **kw(agent_cfg, agent_db, engine))
    with pytest.raises(MatchError, match="human"):
        run_games("saffira:heuristic", "human", games=2, parallel=2, **kw(agent_cfg, agent_db, engine))
    with pytest.raises(MatchError, match="room"):
        run_games("saffira:heuristic", "heuristic", games=None, **kw(agent_cfg, agent_db, engine))


def test_selfplay_command(tmp_path, capsys):
    games = tmp_path / "games"
    cli.main(["selfplay", "--a", "saffira:heuristic", "--b", "random:blackwing", "--games", "2", "--parallel", "2",
              "--quiet", "--seed", "4", "--games-dir", str(games), "--chat", "off", "--no-web"])
    text = capsys.readouterr().out
    assert "Results (2 games)" in text and "A Saffira (heuristic)" in text and "B Blackwing (random)" in text
    runs = [d for d in os.listdir(games / "matches") if d != "latest"]
    assert len(runs) == 1 and json.load(open(games / "matches" / runs[0] / "results.json"))["path"] == "in-process"


def test_play_command_hosts_a_room_for_the_human(tmp_path, engine, capsys):
    """`play` with the arena's Python client standing in for the human's EDOPro."""
    from ygo_agent.arena.deck import load_ydk
    from ygo_agent.arena.policies import RandomPolicy

    class Cards:  # what RandomPolicy needs of a SeatView to declare card names
        cards = engine.cards
    port = free_port()
    deck = load_ydk(os.path.join(os.path.dirname(__file__), "..", "..", "decks", "blackwing", "deck.ydk"),
                    engine.cards).deck
    done = threading.Event()

    def human():
        async def go():
            await asyncio.sleep(1.0)
            policy = RandomPolicy(5)
            client = ArenaClient("Human", deck, lambda prompt: policy(prompt, Cards), rematch=False)
            await client.connect("127.0.0.1", port)
            await client.wait(240)
            await client.close()
            return client.log
        log = asyncio.run(go())
        done.log = log
        done.set()
    threading.Thread(target=human, daemon=True).start()
    cli.main(["play", "--backend", "heuristic", "--deck", "saffira", "--port", str(port), "--no-lan", "--no-web",
              "--games", "1", "--games-dir", str(tmp_path / "games"), "--chat", "off"])
    assert done.wait(30)
    text = capsys.readouterr().out
    assert f"port {port}" in text and "LAN Mode" in text and "Human joined the duelist seat" in text
    assert "Results (1 game)" in text and done.log.position == 1
    assert done.log.replay is not None  # EDOPro gets the replay at the end
