"""`python -m ygo_agent.arena` commands."""

import asyncio
import glob
import json
import os
import socket
import struct
import sys

import pytest

from arena_helpers import client_policy
from ygo_agent.arena.cli import main
from ygo_agent.arena.client import ArenaClient

pytestmark = pytest.mark.integration


def test_selfplay_direct_writes_logs_replays_and_results(engine, tmp_path, capsys):
    assert main(["selfplay-direct", "--games", "3", "--seed", "1", "--out", str(tmp_path),
                 "--stack-hand0", "Tour Guide From the Underworld"]) == 0
    out = capsys.readouterr().out
    assert "3 games in" in out and "0 with retries or Lua errors" in out
    (run_dir,) = glob.glob(str(tmp_path / "*direct_Saffira-vs-Blackwing"))
    results = json.load(open(os.path.join(run_dir, "results.json")))
    assert len(results["games"]) == 3
    assert sorted(os.listdir(run_dir)) == ["game-001.log", "game-001.yrpX", "game-002.log", "game-002.yrpX",
                                           "game-003.log", "game-003.yrpX", "results.json"]
    log = open(os.path.join(run_dir, "game-001.log")).read()
    assert "== turn 1" in log and "# result:" in log and "Tour Guide From the Underworld" in log
    assert main(["replay-info", os.path.join(run_dir, "game-002.yrpX"), "--resimulate"]) == 0
    info = capsys.readouterr().out
    assert "embedded yrp: True" in info and "verdict: same game" in info


def test_unknown_stack_card_is_an_error(engine, capsys):
    try:
        main(["selfplay-direct", "--no-output", "--stack-hand0", "No Such Card Anywhere"])
    except SystemExit as e:
        assert "no card named" in str(e)
    else:
        raise AssertionError("expected an error")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_host_command_with_an_ai_seat(engine, decks, tmp_path):
    port = free_port()

    async def scenario():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ygo_agent.arena", "host", "--port", str(port), "--seat1", "ai:random",
            "--deck1", "Blackwing", "--games", "1", "--no-lan", "--seed", "5", "--out", str(tmp_path),
            "--stack-hand0", "Tour Guide From the Underworld", "--time-limit", "120",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        banner = await asyncio.wait_for(proc.stdout.readline(), 30)
        assert f"port {port}" in banner.decode()
        human = await ArenaClient("Human", decks["Saffira"], client_policy(engine, 1)).connect("127.0.0.1", port)
        await human.wait(60)
        out = (await proc.stdout.read()).decode()
        return await proc.wait(), out, human
    rc, out, human = asyncio.run(asyncio.wait_for(scenario(), 90))
    assert rc == 0, out
    assert "game 1:" in out and "1 games:" in out
    draw = next(m for m in human.log.game if m[0] == 90 and m[1] == human.log.team)
    assert struct.unpack_from("<I", draw, 6)[0] == 10802915     # the stacked card is drawn first
    (run_dir,) = glob.glob(str(tmp_path / "*host_*"))
    assert os.path.isfile(os.path.join(run_dir, "game-001.yrpX"))
    assert human.log.host_info.time_limit == 120
