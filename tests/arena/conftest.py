"""Fixtures for the arena tests. Unit tests need nothing; integration tests skip without EDOPro / mono."""

import os
import shutil

import pytest

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _engine():
    from ygo_agent.core import Engine, InstallError
    try:
        return Engine.load()
    except (InstallError, OSError) as e:
        pytest.skip(f"EDOPro install not available: {e}")


@pytest.fixture(scope="session")
def engine():
    return _engine()


@pytest.fixture(scope="session")
def decks(engine):
    from ygo_agent.arena.deck import load_ydk
    out = {}
    for name in ("Saffira", "Blackwing"):
        path = os.path.join(engine.install.deck_dir, f"{name}.ydk")
        if not os.path.isfile(path):
            pytest.skip(f"deck {path} not found")
        out[name] = load_ydk(path, engine.cards).deck
    return out


@pytest.fixture(scope="session")
def windbot(engine):
    from ygo_agent.arena.windbot import WindBotError, WindBotInstall, mono_path
    if mono_path() is None:
        pytest.skip("mono not installed")
    try:
        return WindBotInstall.find(engine.install.root)
    except WindBotError as e:
        pytest.skip(str(e))


@pytest.fixture
def seven_zip():
    exe = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz")
    if exe is None:
        pytest.skip("7-Zip not installed")
    return exe
