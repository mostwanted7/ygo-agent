"""Fixtures for the native-seat tests. Unit tests need nothing; the rest skip without EDOPro (and mono/WindBot)."""

import contextlib
import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [p for p in (HERE, os.path.dirname(HERE)) if p not in sys.path]


@pytest.fixture(scope="session")
def engine():
    from ygo_agent.core import Engine, InstallError
    try:
        return Engine.load()
    except (InstallError, OSError) as e:
        pytest.skip(f"EDOPro install not available: {e}")


@pytest.fixture(scope="session")
def agent_db(engine):
    """The agent's card database from the real install (the native seats need every card, not the fixture set)."""
    from ygo_agent.agent.carddb import CardDB
    return CardDB(engine.install.root)


@pytest.fixture
def agent_cfg(tmp_path):
    from ygo_agent.config import load_config
    return load_config(local=None, overrides={"games_dir": str(tmp_path / "games"), "chat": "off"})


@pytest.fixture
def make_seat(engine, agent_db, agent_cfg, quiet):
    """make_seat(deck, backend="heuristic", **kw) -> an AgentSeat; closed (quietly) at the end of the test."""
    from ygo_agent.arena.native_seat import AgentSeat
    seats = []

    def make(deck, backend="heuristic", **kw):
        seat = AgentSeat.create(deck, backend, cfg=agent_cfg, db=agent_db, cards=engine.cards, **kw)
        seats.append(seat)
        return seat
    make.track = seats.append  # other seats a test makes, closed the same way
    yield make
    for s in seats:
        s.close()


@pytest.fixture
def quiet():
    """The agent prints every decision to the terminal; tests keep that out of the output."""
    with contextlib.redirect_stdout(io.StringIO()) as out:
        yield out

