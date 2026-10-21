"""Whole native games: heuristic vs heuristic and heuristic vs random, with every decision and event checked against
the protocol, describe.py, the agent's validation and the encoder (needs the EDOPro install)."""

import json
import os

import pytest

from native_helpers import play
from schema import decision_errors, event_errors
from ygo_agent.agent.describe import Describer
from ygo_agent.agent.validate import validate
from ygo_agent.arena.native_seat import AgentSeat
from ygo_agent.backends import random_
from ygo_agent.backends.heuristic import Policy

pytestmark = pytest.mark.integration


class CheckedSeat(AgentSeat):
    """Also checks that each response decodes back to the agent's choice (the option mapping is a bijection)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.roundtrips = []

    def _answer(self, prompt, decision, d, reply, retry):
        data = super()._answer(prompt, decision, d, reply, retry)
        self.roundtrips.append((d["kind"], reply.get("choice") if reply else None, decision.decode(data)))
        return data


def seat(cls, deck, backend, engine, db, cfg, **kw):
    return cls.create(deck, backend, cfg=cfg, db=db, cards=engine.cards, **kw)


def check_trace(trace, describer, policies):
    kinds = set()
    for m in trace:
        if m["t"] == "event":
            assert not event_errors(m), (event_errors(m), m)
            describer.event(m)
            continue
        assert not decision_errors(m), (decision_errors(m), {k: v for k, v in m.items() if k != "state"})
        kinds.add(m["kind"])
        if m["kind"] in ("game_over", "go_first"):
            continue
        assert describer.question(m) and "Decision of kind" not in describer.question(m) or m["kind"] == "place"
        options = describer.options(m)
        assert len(options) == len(m.get("options", [])) and all(options)
        assert describer.state(m["state"]).startswith("TURN ")
        for policy in policies:
            choice = policy.choose(m)
            assert validate(m, choice) is None, (m["kind"], choice)
    return kinds


@pytest.mark.parametrize("matchup", [("saffira", "heuristic", "blackwing", "heuristic"),
                                     ("blackwing", "heuristic", "saffira", "random")])
def test_native_games_complete(engine, agent_db, agent_cfg, quiet, matchup):
    deck_a, back_a, deck_b, back_b = matchup
    describer = Describer(agent_db)
    policies = [Policy(agent_db), random_.RandomPolicy(1)]
    kinds, stats = set(), []
    for seed in range(4):
        agent_cfg["backends"]["random"]["seed"] = seed
        a = seat(CheckedSeat, deck_a, back_a, engine, agent_db, agent_cfg)
        b = seat(CheckedSeat, deck_b, back_b, engine, agent_db, agent_cfg)
        a.trace, b.trace = [], []
        seats = (a, b) if seed % 2 else (b, a)
        duel = play(engine, seats, (seats[0].deck(engine), seats[1].deck(engine)), seed + 10)
        a.close()
        b.close()
        r = duel.result
        assert r.retries == 0 and not r.lua_errors and r.reason in (0x1, 0x2), r
        for s in (a, b):
            assert s.stats["errors"] == 0 and s.stats["timeouts"] == 0 and s.stats["rejected"] == 0, s.stats
            assert s.native.resyncs == 0 and s.native.misses == 0
            kinds |= check_trace(s.trace, describer, policies)
            for kind, choice, decoded in s.roundtrips:
                if choice is not None:
                    assert decoded == choice, (kind, choice, decoded)
            ids = [m["id"] for m in s.trace if m["t"] == "decide"]
            assert ids == list(range(1, len(ids) + 1))
            assert s.trace[0]["e"] == "room" and s.trace[-1]["kind"] == "game_over"
            stats.append(s.stats)
    assert {"idle", "battle", "chain", "select_card", "place", "game_over"} <= kinds, kinds


def test_native_game_logs_replay(engine, agent_db, agent_cfg, quiet, tmp_path):
    """The agent writes its usual game folder for a native game, and `ygo-agent replay` re-asks its decisions."""
    from ygo_agent.agent import replay
    from ygo_agent.agent.profile import Profile
    a = seat(AgentSeat, "saffira", "heuristic", engine, agent_db, agent_cfg)
    b = seat(AgentSeat, "blackwing", "heuristic", engine, agent_db, agent_cfg)
    play(engine, (a, b), (a.deck(engine), b.deck(engine)), 3)
    a.close()
    b.close()
    games = agent_cfg["games_dir"]
    dirs = sorted(d for d in os.listdir(games) if d != "latest")
    assert len(dirs) == 2 and all("-vs-" in d for d in dirs)
    folder = os.path.join(games, next(d for d in dirs if d.split("_")[2].startswith("saffira")))
    for name in ("game.md", "game.jsonl", "prompts.jsonl", "meta.json"):
        assert os.path.isfile(os.path.join(folder, name)), name
    meta = json.load(open(os.path.join(folder, "meta.json")))
    assert meta["deck"] == "saffira" and meta["backend"]["fallback"] == "heuristic" and meta["result"]
    first = json.loads(open(os.path.join(folder, "game.jsonl")).readline())
    assert first["msg"]["e"] == "room" and first["msg"]["duel_flags"] == 858112
    md = open(os.path.join(folder, "game.md")).read()
    assert "DUEL START" in md and "**Decision #1**" in md
    assert replay.game_deck(folder) == "saffira"
    agent_cfg["agent"]["backend"] = "heuristic"
    agent_cfg["games_dir"] = str(tmp_path / "replays")
    reply = replay.replay_one(folder, 5, agent_cfg, agent_db, Profile("saffira", agent_db, agent_cfg))
    assert reply["choice"] is not None


def test_native_vs_windbot_deck_ai(engine, agent_db, agent_cfg, quiet, tmp_path):
    """agent:saffira:heuristic against a WindBot deck AI through the arena host, two games."""
    from ygo_agent.arena.windbot import mono_path
    if mono_path() is None:
        pytest.skip("mono not installed")
    from ygo_agent.arena import cli
    code = cli.main(["bots", "--seat0", "agent:saffira:heuristic", "--seat1", "windbot:Blue-Eyes", "--games", "2",
                     "--no-lan", "--games-dir", agent_cfg["games_dir"], "--out", str(tmp_path / "arena"),
                     "--chat", "off", "--seed", "5", "--timeout", "600"])
    assert code == 0
    out = os.path.join(tmp_path, "arena")
    results = json.load(open(os.path.join(out, os.listdir(out)[0], "results.json")))["games"]
    assert len(results) == 2 and all(r["retries"] == 0 and not r["lua_errors"] for r in results)
    logs = [d for d in os.listdir(agent_cfg["games_dir"]) if d != "latest"]
    assert len(logs) == 2 and all("-vs-blue-eyes" in d for d in logs)
