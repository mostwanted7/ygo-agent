import json
import os

import pytest

from helpers import CASES, EDOPRO, ROOT, case_id, first_valid, load_case  # noqa: F401
from ygo_agent.agent.carddb import CardDB
from ygo_agent.config import load_config


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="also run the tests that make real model calls")


def pytest_collection_modifyitems(config, items):
    edopro = os.path.exists(os.path.join(EDOPRO, "expansions", "cards.cdb"))
    live = config.getoption("--live") or os.environ.get("YGO_AGENT_LIVE") == "1"
    for item in items:
        if "live" in item.keywords:
            if not live:
                item.add_marker(pytest.mark.skip(reason="real model calls: run with --live (or YGO_AGENT_LIVE=1)"))
        elif "integration" in item.keywords and not edopro:
            item.add_marker(pytest.mark.skip(reason=f"EDOPro install not found at {EDOPRO}"))


@pytest.fixture(scope="session")
def db():
    """Card data for the saved cases without an EDOPro install (tests/fixtures/make_cards.py makes it)."""
    with open(os.path.join(ROOT, "tests", "fixtures", "cards.json"), encoding="utf-8") as f:
        return CardDB.from_dict(json.load(f))


@pytest.fixture
def cfg(tmp_path):
    """The default config (no config.local.toml), logging into a temporary games folder."""
    return load_config(local=None, overrides={"games_dir": str(tmp_path / "games")})


@pytest.fixture
def scripted(cfg):
    """Make `cfg` use a scripted backend that answers each decision with state["policy"](decision).
    state["sessions"] collects the sessions (each has .system_prompt, .prompts and .requests)."""
    state = {"sessions": [], "policy": first_valid}
    cfg["backends"]["test"] = {"type": "scripted", "policy": lambda d: state["policy"](d),
                               "sessions": state["sessions"]}
    cfg["agent"]["backend"] = "test"
    return state
