import glob
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ygo_agent.agent.carddb import CardDB  # noqa: E402
from ygo_agent.config import load_config  # noqa: E402

EDOPRO = os.path.expanduser("~/Games/ProjectIgnis")
CASES = sorted(glob.glob(os.path.join(ROOT, "decks", "*", "tests", "*.json")))


def case_id(path):
    return f"{path.split(os.sep)[-3]}/{os.path.splitext(os.path.basename(path))[0]}"


def pytest_collection_modifyitems(config, items):
    if os.path.exists(os.path.join(EDOPRO, "expansions", "cards.cdb")):
        return
    skip = pytest.mark.skip(reason=f"EDOPro install not found at {EDOPRO}")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def db():
    """Card data for the saved cases without an EDOPro install (tests/fixtures/make_cards.py makes it)."""
    with open(os.path.join(ROOT, "tests", "fixtures", "cards.json"), encoding="utf-8") as f:
        return CardDB.from_dict(json.load(f))


@pytest.fixture
def cfg(tmp_path):
    """The default config (no config.local.toml), logging into a temporary games folder."""
    return load_config(local=None, overrides={"games_dir": str(tmp_path / "games")})


def load_case(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class ScriptedSession:
    """Stands in for a backend session: answers each decision with policy(decision)."""

    def __init__(self, policy, brain_ref):
        self.policy = policy
        self.brain_ref = brain_ref
        self.messages = 0
        self.alive = True
        self.prompts = []

    def ask(self, text, timeout):
        self.messages += 1
        self.prompts.append(text)
        return {"choice": self.policy(self.brain_ref["decision"]), "why": "scripted", "plan": None}, {"seconds": 0.0}

    def close(self):
        self.alive = False


def first_valid(d):
    """A deterministic, usually-legal answer to any decision."""
    k = d["kind"]
    if k in ("effect_yn", "yesno", "go_first"):
        return [1]
    if k == "chain":
        return [0] if d.get("forced") else []
    if k in ("select_card", "tribute", "select_sum"):
        return list(range(d["min"]))
    if k in ("announce_attrib", "announce_race"):
        return list(range(d.get("count", 1)))
    return [0]


@pytest.fixture
def scripted(monkeypatch):
    """Patch the backend so DuelBrains get ScriptedSessions; returns a dict with the sessions and current decision."""
    from ygo_agent import backends
    state = {"decision": None, "sessions": [], "policy": first_valid}

    def open_session(profile, system_prompt, schema):
        s = ScriptedSession(lambda d: state["policy"](d), state)
        s.system_prompt = system_prompt
        state["sessions"].append(s)
        return s
    monkeypatch.setattr(backends, "open_session", open_session)
    return state
