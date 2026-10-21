"""Coach mode for real: an arena room, the arena's Python client as the human (a simple policy), a heuristic
opponent and a scripted coach. Needs the EDOPro install (no mono, no LLM)."""

import asyncio
import json
import os
import socket
import threading
import time

import pytest

from helpers import first_valid
from human import play as human_play

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine():
    from ygo_agent.core import Engine, InstallError
    try:
        return Engine.load()
    except (InstallError, OSError) as e:
        pytest.skip(f"EDOPro install not available: {e}")


@pytest.fixture(scope="module")
def agent_db(engine):
    from ygo_agent.agent.carddb import CardDB
    return CardDB(engine.install.root)


@pytest.fixture
def agent_cfg(tmp_path):
    from ygo_agent.config import load_config
    return load_config(local=None, overrides={"games_dir": str(tmp_path / "games"), "chat": "off"})


@pytest.fixture
def live_bus(agent_db):
    from ygo_agent.web.bus import BUS
    from ygo_agent.web.render import Renderer
    BUS.reset()
    BUS.activate(Renderer(agent_db))
    yield BUS
    BUS.reset()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


REVIEW = "## Summary\nA scripted review.\n"


def run_coached(engine, agent_db, agent_cfg, *, human_delay, coach_delay, notes=(), seed=5):
    from ygo_agent.arena.deck import load_ydk
    from ygo_agent.coach.cli import reviewing
    from ygo_agent.coach.live import Coach
    from ygo_agent.config import backend
    from ygo_agent.match import SeatSpec, run_games
    asked = []  # one coached game: the coach, the run, the human client's log and the coach's asks

    def coach_policy(d):
        asked.append(d["id"])
        time.sleep(coach_delay)
        return {"choice": first_valid(d), "why": "scripted advice"}
    agent_cfg["backends"]["coach"] = {"type": "scripted", "policy": coach_policy}
    agent_cfg["backends"]["reviewer"] = {"type": "scripted", "policy": lambda d: {"choice": [], "why": REVIEW}}
    coach = Coach(agent_cfg, agent_db, backend=backend(agent_cfg, "coach"), cards=engine.cards, echo="off",
                  opponent={"kind": "agent", "deck": "Blackwing", "backend": "heuristic"},
                  review=reviewing(agent_cfg, agent_db, backend(agent_cfg, "reviewer"), "beginner"),
                  say=lambda *lines: None)
    port = free_port()
    deck = load_ydk(os.path.join(os.path.dirname(__file__), "..", "..", "decks", "saffira", "deck.ydk"),
                    engine.cards).deck
    out = {}

    def human():
        out["log"] = asyncio.run(human_play(port, deck, engine.cards, "simple", human_delay, notes, seed=seed))
    t = threading.Thread(target=human, daemon=True)
    t.start()
    run = run_games(SeatSpec("human"), SeatSpec.parse("heuristic:blackwing").with_(mode="selfplay"), games=1,
                    cfg=agent_cfg, db=agent_db, engine=engine, port=port, bind="127.0.0.1", lan=False, time_limit=0,
                    seed=seed, quiet=True, echo=("off", "off"), on_room=coach.attach, on_game=coach.on_game,
                    timeout=600)
    t.join(60)
    coach.close(timeout=60)
    return coach, run, out.get("log"), asked


def messages(bus, game):
    out = {}
    for m in bus.backlog(game.log.web.game_id):
        out.setdefault(m["type"], {})[m.get("id") or (m.get("decision") or {}).get("id")] = m
    return out


def test_a_coached_game_with_a_thoughtful_human(engine, agent_db, agent_cfg, live_bus):
    """The human thinks before every move, the coach answers at once: every advice is live, never late."""
    from ygo_agent.agent.gamelog import same_pick
    coach, run, log, asked = run_coached(engine, agent_db, agent_cfg, human_delay=0.3, coach_delay=0.0,
                                         notes=["!coach: tell me about Hymn of Light earlier"])
    assert run.games and log is not None and log.position == 0
    (game,) = coach.games
    assert coach.detection.key == "saffira" and game.brain.profile.key == "saffira"
    msgs = messages(live_bus, game)
    decisions = msgs["decision"]
    assert len(decisions) > 20 and set(msgs["advice"]) == {m["decision"]["id"] for m in decisions.values()}
    backend = {i: a for i, a in msgs["advice"].items() if a["source"] == "backend"}
    assert backend and all(not a["late"] and not a["hindsight"] for a in backend.values())
    for i, a in backend.items():
        h = msgs["human_choice"][i]
        assert h["advised"] == a["choice"] and h["matched"] == same_pick(h["choice"], a["choice"], a["kind"])
        assert msgs["reply"][i]["choice"] == h["choice"] and msgs["reply"][i]["source"] == "human"
    for i, a in msgs["advice"].items():
        if a["source"] == "auto":
            assert i not in asked
    folder = game.log.dir
    assert os.path.isfile(os.path.join(folder, "replay.yrpX"))
    assert run.games[0].seats[0].log_dir == folder
    notes = open(os.path.join(folder, "feedback.md"), encoding="utf-8").read()
    assert "coach game, turn" in notes and "tell me about Hymn of Light earlier" in notes
    review = open(os.path.join(folder, "review.md"), encoding="utf-8").read()
    assert review.startswith("# Coach review: Saffira") and "A scripted review." in review
    assert "review" in msgs
    meta = json.load(open(os.path.join(folder, "meta.json")))
    assert meta["mode"] == "coach" and meta["coach"]["late"] == 0 and meta["coach"]["advised"] == len(backend)
    # The AI opponent's notes and reasoning stay its own: it didn't take the human's !note, nor publish.
    opp = [d for d in os.listdir(agent_cfg["games_dir"]) if "blackwing" in d and d != os.path.basename(folder)]
    assert opp and not os.path.exists(os.path.join(agent_cfg["games_dir"], opp[0], "feedback.md"))
    assert {g["game_id"] for g in live_bus.games()} == {game.log.web.game_id}


def test_an_instant_human_gets_late_advice(engine, agent_db, agent_cfg, live_bus):
    """The human answers at once, the coach takes a moment: every advice is late (or a look back), the coach only
    asks about what matters, and the duel is never held up."""
    coach, run, log, asked = run_coached(engine, agent_db, agent_cfg, human_delay=0.0, coach_delay=0.05)
    (game,) = coach.games
    msgs = messages(live_bus, game)
    backend = {i: a for i, a in msgs["advice"].items() if a["source"] == "backend"}
    assert backend and all(a["late"] for a in backend.values())
    assert any(a["hindsight"] for a in backend.values())
    skipped = [i for i, a in msgs["advice"].items() if a["source"] == "skipped"]
    assert skipped and not set(skipped) & set(asked)
    kinds = {i: m["decision"]["kind"] for i, m in msgs["decision"].items()}
    assert all(kinds[i] in ("idle", "battle", "chain") for i in backend if backend[i]["hindsight"])
    assert os.path.isfile(os.path.join(game.log.dir, "review.md"))
