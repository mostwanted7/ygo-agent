"""Deck storage: the repo's decks/ plus the user decks dir, one lookup for every command (ygo_agent/decks.py)."""

import argparse
import json
import os
import shutil

import pytest

from ygo_agent import decks, paths
from ygo_agent.agent import replay
from ygo_agent.agent.profile import Profile, deck_keys
from ygo_agent.match import MatchError, load_profile

SAFFIRA = os.path.join(paths.ROOT, "decks", "saffira")


def make_deck(root, key, name=None, cases=0, rules=0):
    folder = root / key
    folder.mkdir(parents=True)
    shutil.copyfile(os.path.join(SAFFIRA, "deck.ydk"), folder / "deck.ydk")
    (folder / "deck.json").write_text(json.dumps({"name": name or key.title(), "ydk": "deck.ydk"}))
    (folder / "playbook.md").write_text(f"# {key}\n" + "x" * 2000)
    if rules:
        (folder / "rules.py").write_text("".join(f"def r{i}(ctx):\n    return None\n" for i in range(rules))
                                         + f"RULES = [{', '.join(f'r{i}' for i in range(rules))}]\n")
    (folder / "tests").mkdir()
    for i in range(cases):
        (folder / "tests" / f"case{i}.json").write_text(json.dumps({"messages": [], "source": "games/x #1"}))
    return str(folder)


@pytest.fixture
def roots(tmp_path, monkeypatch, cfg):
    """A repo decks/ and a user decks dir, both empty, in tmp_path."""
    repo, user = tmp_path / "repo-decks", tmp_path / "user-decks"
    repo.mkdir()
    user.mkdir()
    monkeypatch.setattr(paths, "DECKS", str(repo))
    cfg["decks"]["user_dir"] = str(user)
    return repo, user


def test_user_dir_follows_xdg_and_the_config(monkeypatch, cfg, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert decks.user_dir(cfg) == str(tmp_path / "xdg" / "ygo-agent" / "decks")
    monkeypatch.delenv("XDG_DATA_HOME")
    assert decks.user_dir(cfg) == os.path.expanduser("~/.local/share/ygo-agent/decks")
    cfg["decks"]["user_dir"] = "~/my-decks"
    assert decks.user_dir(cfg) == os.path.expanduser("~/my-decks")
    assert decks.roots(cfg)[0] == ("repo", paths.DECKS)


def test_both_roots_are_searched_repo_first(roots, cfg, db):
    repo, user = roots
    make_deck(repo, "saffira")
    mine = make_deck(user, "geargia", name="My Geargia")
    assert deck_keys(cfg) == ["geargia", "saffira"]
    assert [(d.key, d.location) for d in decks.scan(cfg)] == [("saffira", "repo"), ("geargia", "user")]
    found = decks.find("GEARGIA", cfg)
    assert found.dir == mine and found.location == "user" and found.key == "geargia"
    p = Profile("geargia", db, cfg)
    assert p.dir == mine and p.location == "user" and p.name == "My Geargia" and not p.adhoc
    assert Profile("saffira", db, cfg).location == "repo"
    # every command resolves a seat's deck the same way: by name (any case), or as a .ydk path
    assert load_profile("Geargia", db, cfg).dir == mine
    loose = load_profile(os.path.join(mine, "deck.ydk"), db, cfg)
    assert loose.adhoc and loose.ydk == os.path.join(mine, "deck.ydk")
    with pytest.raises(MatchError, match="no deck 'nope'"):
        load_profile("nope", db, cfg)


def test_a_name_in_both_roots_needs_a_preference(roots, cfg, db):
    repo, user = roots
    ours, theirs = make_deck(repo, "geargia"), make_deck(user, "Geargia")
    with pytest.raises(decks.DeckError, match="exists twice"):
        decks.find("geargia", cfg)
    with pytest.raises(FileNotFoundError, match='prefer = "user"'):
        Profile("geargia", db, cfg)
    with pytest.raises(MatchError, match="exists twice"):
        load_profile("geargia", db, cfg)
    cfg["decks"]["prefer"] = "user"
    assert decks.find("geargia", cfg).dir == theirs and Profile("geargia", db, cfg).dir == theirs
    cfg["decks"]["prefer"] = "repo"
    assert decks.find("geargia", cfg).dir == ours
    rows = {(r["key"], r["location"]): r for r in decks.listing(cfg)}
    assert rows["geargia", "repo"]["clash"] == "used" and rows["Geargia", "user"]["clash"] == "shadowed"
    cfg["decks"]["prefer"] = "nonsense"
    with pytest.raises(decks.DeckError, match="prefer"):
        decks.find("geargia", cfg)


def test_config_rejects_a_bad_preference():
    from ygo_agent.config import ConfigError, load_config
    with pytest.raises(ConfigError, match="decks.prefer"):
        load_config(local=None, overrides={"decks": {"prefer": "mine"}})
    assert load_config(local=None, overrides={"decks": {"prefer": "user"}})["decks"]["prefer"] == "user"


def test_replay_and_test_find_cases_in_the_user_dir(roots, cfg):
    repo, user = roots
    make_deck(repo, "saffira", cases=1)
    mine = make_deck(user, "geargia", cases=2)
    found = replay.case_paths(["saffira", "geargia"], cfg=cfg)
    assert len(found) == 3 and sum(p.startswith(mine) for p in found) == 2
    assert replay.case_paths(["geargia"], ["case1"], cfg) == [os.path.join(mine, "tests", "case1.json")]
    with pytest.raises(decks.DeckError):
        replay.case_paths(["nope"], cfg=cfg)
    game = os.path.join(str(user), "..", "game")
    os.makedirs(game)
    with open(os.path.join(game, "game.md"), "w", encoding="utf-8") as f:
        f.write("# Geargia — vs someone\n")
    assert replay.game_deck(game, cfg) == "geargia"  # an old log without meta.json: the deck's name in the title
    with open(os.path.join(game, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"deck": "mine", "deck_ydk": "/x/Mine.ydk"}, f)
    assert replay.game_deck(game, cfg) == "/x/Mine.ydk"


def test_coach_detection_sees_user_decks(roots, cfg, db):
    from ygo_agent.agent.profile import parse_ydk
    from ygo_agent.coach.detect import detect
    repo, user = roots
    mine = make_deck(user, "saffira2")
    main, extra, _ = parse_ydk(os.path.join(mine, "deck.ydk"))
    found = detect(main, extra, cfg, db)
    assert found.key == "saffira2" and found.folder == mine and "user-decks/saffira2" in found.describe()


def train_args(**kw):
    base = dict(deck_key="newdeck", out=None, into=None, resume=False)
    return argparse.Namespace(**{**base, **kw})


def test_train_writes_to_the_user_dir_unless_into_repo(roots, cfg):
    from ygo_agent.trainer.cli import deck_folder
    repo, user = roots
    assert deck_folder(train_args(), cfg) == os.path.join(str(user), "newdeck")
    assert deck_folder(train_args(into="repo"), cfg) == os.path.join(str(repo), "newdeck")
    assert deck_folder(train_args(out="somewhere"), cfg) == os.path.abspath("somewhere")
    make_deck(repo, "geargia")
    with pytest.raises(decks.DeckError, match="pick another --name"):
        deck_folder(train_args(deck_key="geargia"), cfg)  # it would clash with the repo's deck
    # a resume continues the run where it is: here, a run from before the user dir existed, in decks/
    os.makedirs(repo / "geargia" / "train")
    (repo / "geargia" / "train" / "state.json").write_text("{}")
    assert deck_folder(train_args(deck_key="geargia", resume=True), cfg) == os.path.join(str(repo), "geargia")


def test_trainer_treats_the_user_dir_as_a_deck_root(roots, cfg, db):
    from ygo_agent.trainer.pipeline import Options, Trainer
    repo, user = roots
    mine = make_deck(user, "newdeck")
    t = Trainer(Options(name="newdeck", ydk=os.path.join(mine, "deck.ydk")), cfg, db=db)
    assert t.deck_dir == mine  # the default is the user decks dir
    p = t.profile()
    assert p.dir == mine and not p.adhoc and p.location == "user"


def test_decks_command_lists_both_roots(roots, cfg, tmp_path, capsys):
    from ygo_agent import cli
    repo, user = roots
    make_deck(repo, "saffira", cases=2, rules=3)
    make_deck(user, "geargia", name="Gears")
    local = tmp_path / "local.toml"
    local.write_text(f'[decks]\nuser_dir = "{user}"\n')
    with pytest.raises(SystemExit) as end:
        cli.main(["decks", "--config", str(local)])
    assert end.value.code == 0
    text = capsys.readouterr().out
    lines = {line.split()[0]: line for line in text.splitlines() if line.startswith("  ") and "KB" in line}
    assert set(lines) == {"saffira", "geargia"}
    assert lines["saffira"].split()[1:5] == ["repo", "2.0", "KB", "3"] and lines["saffira"].split()[5] == "2"
    assert "user" in lines["geargia"] and "(Gears)" in lines["geargia"] and "deck.ydk" in lines["geargia"]
