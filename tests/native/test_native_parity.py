"""Parity with the WindBot bridge: the same games through the fork's BrainBridge and through a native seat give the
same decisions, option for option (needs mono and the fork build; see parity.py for the method)."""

import pytest

import parity

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def results(engine, tmp_path_factory):
    from ygo_agent.arena.windbot import WindBotError, WindBotInstall, mono_path
    if mono_path() is None:
        pytest.skip("mono not installed")
    try:
        if not WindBotInstall.find(engine.install.root).is_fork:
            pytest.skip("the WindBot fork isn't built (./build.sh)")
    except WindBotError as e:
        pytest.skip(str(e))
    return parity.run(2, 31, "saffira", "Blackwing", str(tmp_path_factory.mktemp("parity")))


def test_same_decisions_in_the_same_order(results):
    for r in results:
        c = r["counts"]
        n = c["compared"]
        assert n > 20 and c["bridge_decisions"] == c["native_decisions"] == n, c
        assert c["kind_match"] == c["count_match"] == n, (c, r["examples"])


def test_options_mean_the_same(results):
    """The bridge's choice, played by WindBot, decodes to the same option index in the native decision. The one
    known exception is WindBot's: when one card is listed twice (two summon procedures), it sends the last index."""
    for r in results:
        c = r["counts"]
        assert c["semantics_match"] + c.get("semantics_windbot_duplicate", 0) == c["compared"], r["examples"]


def test_text_matches_once_known_differences_are_removed(results):
    for r in results:
        c = r["counts"]
        assert c["normalized_options_match"] == c["compared"], [x[:1] + x[3:] for x in r["details"]]
        assert c["normalized_state_match"] >= 0.98 * c["compared"], [x[:1] + x[3:] for x in r["details"]]


def test_the_heuristic_plays_the_same(results):
    for r in results:
        c = r["counts"]
        assert c["policy_match"] >= 0.95 * c["compared"], r["examples"]
        if c["policy_match"] == c["compared"] and not c.get("semantics_windbot_duplicate"):
            assert c["free_identical"], c  # same choices, so the very same game
