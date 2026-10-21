"""Checks against the real EDOPro install (skipped without it)."""

import os

import pytest

from helpers import EDOPRO
from ygo_agent.agent.carddb import CardDB
from ygo_agent.agent.profile import Profile, parse_ydk

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def real_db():
    return CardDB(EDOPRO)


def test_card_database_loads(real_db):
    assert len(real_db.cards) > 10000 and real_db.db_paths
    assert real_db.name(56350972) == "Saffira, Queen of Dragons"
    assert real_db.system.get(506)  # hint strings come from strings.conf


def test_fixture_matches_the_install(real_db, db):
    """tests/fixtures/cards.json is a faithful extract (regenerate it with tests/fixtures/make_cards.py)."""
    for cid, card in db.cards.items():
        assert real_db.name(cid) == card.name


@pytest.mark.parametrize("key", ["saffira", "blackwing"])
def test_decks_build_full_prompts(real_db, cfg, key):
    p = Profile(key, real_db, cfg)
    text = p.system_prompt("play", "MR3")
    assert all(real_db.name(i) in text for i in p.main + p.extra)
    assert "(no data)" not in text


@pytest.mark.parametrize("name", ["Saffira", "Blackwing"])
def test_repo_copies_match_the_edopro_decks(name):
    """Informational: the repo's deck.ydk is a copy; the local config may point at the EDOPro file instead."""
    theirs = os.path.join(EDOPRO, "deck", f"{name}.ydk")
    if not os.path.exists(theirs):
        pytest.skip(f"{theirs} not found")
    ours = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "decks", name.lower(), "deck.ydk")
    assert parse_ydk(ours)[0] and parse_ydk(theirs)[0]
