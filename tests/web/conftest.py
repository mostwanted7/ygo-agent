import pytest

from web_helpers import play_case
from ygo_agent.web.bus import BUS
from ygo_agent.web.render import Renderer


@pytest.fixture
def bus(db):
    """The process-wide bus, switched on (as a running panel does) and cleared afterwards."""
    BUS.reset()
    BUS.activate(Renderer(db))
    yield BUS
    BUS.reset()


@pytest.fixture
def quiet_bus():
    BUS.reset()
    yield BUS
    BUS.reset()


@pytest.fixture
def played(cfg, db, scripted, quiet_bus):
    """A finished game folder in the temporary games dir, logged the way a live game is (no panel running)."""
    brain, case = play_case(cfg, db, scripted)
    brain.on_event({"t": "event", "e": "win", "result": 0, "reason": 1})
    brain.close()
    return brain.log.dir, case
