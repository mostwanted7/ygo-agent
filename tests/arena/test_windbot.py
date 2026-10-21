"""WindBot deck AIs through the arena (needs mono and a WindBot build; skipped otherwise)."""

import asyncio

import pytest

from arena_helpers import client_policy
from ygo_agent.arena import server as S
from ygo_agent.arena.client import ArenaClient
from ygo_agent.arena.duel import DuelConfig
from ygo_agent.arena.replay import parse_replay, streams_match
from ygo_agent.arena.runner import replay_duel
from ygo_agent.arena.windbot import WindBotProcess, db_paths_arg

pytestmark = pytest.mark.integration


def test_bot_list(windbot):
    bots = windbot.bots()
    assert len(bots) > 20 and windbot.resolve("blue-eyes").deck == "Blue-Eyes"
    assert windbot.resolve("BlueEyesMaxDragon").name == "Blue-Eyes Ritual"


def test_db_paths_arg_is_base64_json():
    import base64
    import json
    assert json.loads(base64.b64decode(db_paths_arg(["/a.cdb", "/b.cdb"]))) == ["/a.cdb", "/b.cdb"]


def test_windbot_vs_windbot(engine, windbot, tmp_path):
    async def scenario():
        room = S.Room(engine, S.RoomConfig(duel=DuelConfig(rules="mr5"), max_matches=2, rematch=True, seed=4,
                                           lan_discovery=False, reserved={0: "WB-A", 1: "WB-B"}))
        server = S.ArenaServer(room, "127.0.0.1", 0)
        await server.start()
        bots = [WindBotProcess(windbot, windbot.resolve(deck), name, server.port, version=room.version.as_int,
                               cdb_paths=engine.install.cdb_paths, scratch=str(tmp_path / name)).start()
                for deck, name in (("Blue-Eyes", "WB-A"), ("Lightsworn", "WB-B"))]
        try:
            await asyncio.wait_for(room.finished.wait(), 240)
        finally:
            await server.close()
            for b in bots:
                b.stop()
                assert not b.running()
        return room, bots
    room, bots = asyncio.run(scenario())
    assert len(room.games) == 2
    for duel, result in room.games:
        assert result.retries == 0 and not result.lua_errors and result.reason in (0x1, 0x2)
        rep = parse_replay(duel.replay.yrpx())
        again = replay_duel(engine, rep)
        assert streams_match(again.replay.packets, rep.packets)
        again.close()
    assert all(not b.crash_log() for b in bots)


def test_windbot_vs_python_client(engine, windbot, decks, tmp_path):
    async def scenario():
        room = S.Room(engine, S.RoomConfig(duel=DuelConfig(rules="mr3"), max_matches=1, rematch=False, seed=2,
                                           lan_discovery=False, reserved={1: "WB"}))
        server = S.ArenaServer(room, "127.0.0.1", 0)
        await server.start()
        bot = WindBotProcess(windbot, windbot.resolve("Blackwing"), "WB", server.port,
                             cdb_paths=engine.install.cdb_paths, scratch=str(tmp_path / "wb")).start()
        human = await ArenaClient("Human", decks["Saffira"], client_policy(engine, 1)).connect("127.0.0.1",
                                                                                              server.port)
        try:
            await asyncio.wait_for(room.finished.wait(), 180)
        finally:
            await server.close()
            bot.stop()
        return room, human
    room, human = asyncio.run(scenario())
    (duel, result), = room.games
    assert result.retries == 0 and set(duel.names) == {"Human", "WB"}
    assert human.log.replay is not None


def test_host_command_relaunches_the_windbot_for_the_next_match(engine, windbot, decks, tmp_path):
    import socket
    import sys
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    async def scenario():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ygo_agent.arena", "host", "--port", str(port), "--seat1", "windbot:Blackwing",
            "--games", "2", "--no-lan", "--seed", "3", "--out", str(tmp_path), "--time-limit", "0",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        await asyncio.wait_for(proc.stdout.readline(), 30)
        for n in range(2):  # two humans, one after the other; each declines the rematch
            human = await ArenaClient(f"Human{n}", decks["Saffira"], client_policy(engine, n)).connect(
                "127.0.0.1", port)
            await human.wait(120)
            await human.close()
            await asyncio.sleep(1.5)  # the room reopens after a second
        out = (await asyncio.wait_for(proc.stdout.read(), 60)).decode()
        return await proc.wait(), out
    rc, out = asyncio.run(asyncio.wait_for(scenario(), 300))
    assert rc == 0, out
    assert out.count("started WindBot Blackwing") == 2 and "2 games:" in out
