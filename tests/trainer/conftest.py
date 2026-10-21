"""Fixtures for the trainer tests. No test here calls a model: the reviewer is a scripted backend."""

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
    from ygo_agent.agent.carddb import CardDB
    return CardDB(engine.install.root)


@pytest.fixture
def quiet():
    with contextlib.redirect_stdout(io.StringIO()) as out:
        yield out


@pytest.fixture
def decks_dir(tmp_path, monkeypatch):
    """decks/ and the user decks dir point at temporary folders, so a training run never touches the real decks.
    Returns the user decks dir, where `train` puts a new deck."""
    from ygo_agent import paths
    repo = tmp_path / "decks"
    repo.mkdir()
    monkeypatch.setattr(paths, "DECKS", str(repo))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    folder = tmp_path / "xdg" / "ygo-agent" / "decks"
    folder.mkdir(parents=True)
    return folder
