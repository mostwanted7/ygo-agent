import os

import pytest

from ygo_agent import paths
from ygo_agent.agent import prompts
from ygo_agent.agent.profile import Profile, deck_keys, parse_ydk


def test_decks_are_self_contained():
    assert {"saffira", "blackwing"} <= set(deck_keys())
    for key in deck_keys():
        main, extra, side = parse_ydk(os.path.join(paths.DECKS, key, "deck.ydk"))
        assert 40 <= len(main) <= 60 and len(extra) <= 15


def test_profile_uses_the_local_copy_by_default(db, cfg):
    p = Profile("saffira", db, cfg)
    assert p.ydk == os.path.join(paths.DECKS, "saffira", "deck.ydk")
    assert p.name == "Saffira" and p.get("go_first") is True
    assert len(p.main) == 40 and p.ids


def test_profile_override_points_at_an_external_ydk(db, cfg, tmp_path):
    ydk = tmp_path / "Mine.ydk"
    ydk.write_text("#main\n51296484\n51296484\n#extra\n!side\n")
    cfg["decks"] = {"saffira": {"ydk": str(ydk)}}
    p = Profile("saffira", db, cfg)
    assert p.ydk == str(ydk) and p.main == [51296484, 51296484] and p.extra == []
    cfg["decks"] = {"saffira": {"ydk": str(tmp_path / "missing.ydk")}}
    with pytest.raises(FileNotFoundError):
        Profile("saffira", db, cfg)


def test_unknown_deck(db, cfg):
    with pytest.raises(FileNotFoundError, match="saffira"):
        Profile("nope", db, cfg)


def test_system_prompt_modes(db, cfg):
    p = Profile("blackwing", db, cfg)
    play = p.system_prompt("play", "MR3")
    teach = p.system_prompt("teach", "MR3")
    coach = p.system_prompt("coach", "MR3", level="intermediate")
    for text in (play, teach):
        assert text.startswith("You are an expert Yu-Gi-Oh! duelist")
        assert "Master Rule 3" in text and "Master Rule 5" not in text and "Claude" not in text.split("# Your deck")[0]
        assert "# General strategy" in text and p.general_playbook.strip() in text
        assert "# Playbook (coaching notes — your default guide)" in text and p.playbook in text
        assert "choice: option indices" in text
    assert "human who is coaching you" in play and "# Teaching mode" not in play
    assert "spectator seat" in teach and "# Teaching mode" in teach and "# Coaching mode" not in teach
    # Coach mode: the human plays, the AI advises (tests/coach has the rest).
    assert coach.startswith("You are an expert Yu-Gi-Oh! duelist, coaching a human") and "Master Rule 3" in coach
    assert "# Coaching mode" in coach and "# Teaching mode" not in coach and "one terse sentence" in coach
    assert f"# The deck they play: {p.name}" in coach and p.playbook in coach and p.general_playbook.strip() in coach


def test_rules_from_flags():
    assert prompts.rules_from_flags(858112) == "MR3"
    assert prompts.rules_from_flags(0x2E800) == "MR5"
    assert prompts.rules_from_flags(0x2E800 | 0x10) == "MR5"  # pseudo-shuffle isn't a rule
    assert prompts.rules_from_flags(0x12345) is None and prompts.rules_from_flags(None) is None
    assert prompts.ruleset("mr4")[0] == "Master Rule 4"
    assert prompts.ruleset("Goat-ish house rules") == ("Goat-ish house rules", None)
    assert "Master Rule 3" in prompts.intro("play", "MR3") and "no Extra Monster Zone" in prompts.intro("play", "MR3")
