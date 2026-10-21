"""Recognising the human's deck: their submitted list against the deck profiles, then EDOPro's deck folder."""

import os

from ygo_agent.agent.profile import Profile, parse_ydk
from ygo_agent.coach.detect import Detection, detect, overlap, counts, write_ydk


def lists(db, cfg, key):
    main, extra, _ = parse_ydk(Profile(key, db, cfg).ydk)
    return main, extra


def test_a_deck_profile_is_recognised(db, cfg):
    for key in ("saffira", "blackwing"):
        main, extra = lists(db, cfg, key)
        found = detect(main, extra, cfg, db)
        assert found.key == key and found.score == 1.0 and "decks/" + key in found.describe()


def test_a_few_changed_cards_still_match(db, cfg):
    main, extra = lists(db, cfg, "saffira")
    other, _ = lists(db, cfg, "blackwing")
    edited = other[:8] + main[8:]  # 8 of 40 main deck cards swapped
    found = detect(edited, extra, cfg, db)
    assert found.key == "saffira" and 0.6 <= found.score < 1.0


def test_an_unknown_deck(db, cfg, tmp_path):
    cfg["edopro_dir"] = str(tmp_path / "edopro")
    unrelated = [10000 + i for i in range(40)]
    found = detect(unrelated, [], cfg, db)
    assert found.key is None and found.profile is None and "doesn't match" in found.describe()
    # One of EDOPro's decks with the same list names it, though it has no profile to coach with.
    os.makedirs(tmp_path / "edopro" / "deck")
    write_ydk(str(tmp_path / "edopro" / "deck" / "Geargia Test.ydk"), unrelated, [], [])
    found = detect(unrelated, [], cfg, db)
    assert isinstance(found, Detection) and found.key is None and found.name == "Geargia Test" and found.score == 1.0
    assert "no deck profile" in found.describe()


def test_overlap_counts_copies():
    a = counts([1, 1, 1, 2, 3])
    assert overlap(a, counts([1, 2, 3, 4, 5])) == 3 / 5
    assert overlap(a, a) == 1.0 and overlap(counts([]), a) == 0.0
