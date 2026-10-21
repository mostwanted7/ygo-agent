import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [p for p in (HERE, os.path.dirname(HERE)) if p not in sys.path]


@pytest.fixture
def bus(db):
    """The process-wide bus, switched on (as a running panel does) and cleared afterwards."""
    from ygo_agent.web.bus import BUS
    from ygo_agent.web.render import Renderer
    BUS.reset()
    BUS.activate(Renderer(db))
    yield BUS
    BUS.reset()
