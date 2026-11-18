import json
import os
import time

import pytest

from helpers import CASES
from ygo_agent import paths
from ygo_agent.agent import replay
from ygo_agent.agent.gamelog import GameLog, slug


def test_game_dirs_are_unique_within_a_second(tmp_path):
    logs = [GameLog(str(tmp_path), "Saffira", deck_key="saffira", quiet=True) for _ in range(3)]
    names = [log.name for log in logs]
    assert len(set(names)) == 3
    assert names[1] == names[0] + "-2" or names[1][:17] != names[0][:17]  # or the clock ticked
    assert os.readlink(tmp_path / "latest") == names[-1]
    for log in logs:
        log.close()


def test_opponent_joins_the_folder_name(tmp_path):
    a = GameLog(str(tmp_path), "Saffira", deck_key="saffira", quiet=True)
    b = GameLog(str(tmp_path), "Saffira", deck_key="saffira", quiet=True)
    a.add_opponent("[AI] Blue-Eyes")
    b.add_opponent("[AI] Blue-Eyes")
    assert a.name.endswith("_saffira-vs-ai-blue-eyes")
    assert b.name != a.name and "-vs-ai-blue-eyes" in b.name
    a.record("event", {"e": "x"})  # files stay usable after the rename
    a.close()
    with open(os.path.join(a.dir, "game.jsonl"), encoding="utf-8") as f:
        assert json.loads(f.readline())["msg"] == {"e": "x"}
    assert os.readlink(tmp_path / "latest") == b.name
    b.close()


def test_named_logs_are_not_renamed(tmp_path):
    log = GameLog(str(tmp_path), "Saffira", name="test-case-1", latest=False, quiet=True)
    log.add_opponent("Rival")
    assert log.name == "test-case-1" and not os.path.exists(tmp_path / "latest")
    log.close()


def test_slug():
    assert slug("[AI] Blue-Eyes White") == "ai-blue-eyes-white"
    assert slug("???") == "unknown"
    assert len(slug("x" * 100)) == 24


def test_load_messages_skips_replies(tmp_path):
    game = tmp_path / "g"
    game.mkdir()
    rows = [{"kind": "event", "msg": {"t": "event", "e": "start"}},
            {"kind": "decide", "msg": {"t": "decide", "id": 1, "kind": "idle"}},
            {"kind": "reply", "msg": {"id": 1, "choice": [0]}},
            {"kind": "decide", "msg": {"t": "decide", "id": 2, "kind": "idle"}}]
    (game / "game.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    msgs = replay.load_messages(str(game), 2)
    assert [m.get("id") for m in msgs] == [None, 1, 2]
    with pytest.raises(LookupError):
        replay.load_messages(str(game), 9)


def test_case_source_is_relative(tmp_path):
    assert replay.case_source(os.path.join(paths.ROOT, "games", "2026-10-21_140420"), 105) == "games/2026-10-21_140420 #105"
    assert replay.case_source(str(tmp_path / "2026-01-01_000000_x"), 3) == "games/2026-01-01_000000_x #3"


def test_case_paths_by_name():
    if not CASES:
        pytest.skip("no saved cases")
    found = replay.case_paths(["saffira", "blackwing"], ["chinook-on-attack"])
    assert [os.path.basename(p) for p in found] == ["chinook-on-attack.json"]


def test_prune_games_keeps_the_newest_and_what_is_still_needed(tmp_path):
    from ygo_agent.agent.gamelog import prune_games

    def game(name, age=7200, notes=None):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "game.jsonl").write_text("{}\n")
        if notes:
            (folder / "feedback.md").write_text(notes)
        old = time.time() - age
        os.utime(folder / "game.jsonl", (old, old))
        os.utime(folder, (old, old))

    for day in range(1, 8):
        game(f"2026-10-0{day}_120000_saffira-vs-blue-eyes")
    game("2026-10-01_090000_saffira", notes="- (turn 3, right after decision #14; from Web panel) Attack first.\n")
    game("2026-10-01_080000_saffira", notes="- (turn 2; from Web panel) Set the trap.\n  - Learned 2026-10-02: done\n")
    game("2026-09-30_120000_geargia", age=60)  # still being written by another command
    os.symlink("2026-09-01_120000_blackwing", tmp_path / "latest")
    game("2026-09-01_120000_blackwing")
    (tmp_path / "matches").mkdir()
    (tmp_path / "replays" / "2026-01-01_000000_x").mkdir(parents=True)

    assert prune_games(str(tmp_path), 0) == []
    removed = prune_games(str(tmp_path), 3)
    assert removed == [f"2026-10-0{day}_120000_saffira-vs-blue-eyes" for day in (4, 3, 2, 1)] + \
        ["2026-10-01_080000_saffira"]
    assert sorted(os.listdir(tmp_path)) == [
        "2026-09-01_120000_blackwing", "2026-09-30_120000_geargia", "2026-10-01_090000_saffira",
        "2026-10-05_120000_saffira-vs-blue-eyes", "2026-10-06_120000_saffira-vs-blue-eyes",
        "2026-10-07_120000_saffira-vs-blue-eyes", "latest", "matches", "replays"]
