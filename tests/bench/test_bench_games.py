"""A tiny real benchmark through the whole pipeline: heuristic and random Saffira against an in-process heuristic
Blackwing (no WindBot, no LLM; needs the EDOPro install), then a resume, the report, and the seed pairing."""

import contextlib
import glob
import io
import json
import os

import pytest

from ygo_agent.bench import BenchSpec, build_report, runner

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def install():
    from ygo_agent.core import Engine, InstallError
    try:
        Engine.load()
    except (InstallError, OSError) as e:
        pytest.skip(f"EDOPro install not available: {e}")


def opening_hand(log_dir):
    """The seat's hand at its first decision."""
    for line in open(os.path.join(log_dir, "game.jsonl"), encoding="utf-8"):
        rec = json.loads(line)
        if rec["kind"] == "decide":
            return sorted(c["id"] for c in rec["msg"]["state"]["me"]["hand"])


def test_tiny_benchmark(install, tmp_path):
    from ygo_agent.config import load_config
    cfg = load_config(local=None, overrides={"games_dir": str(tmp_path / "games")})
    spec = BenchSpec(name="tiny", decks=["saffira"], backends=["heuristic", "random"],
                     opponents=["blackwing:heuristic"], games=2, games_for={"heuristic": 3}, seed=77, parallel=2)
    folder = str(tmp_path / "run")
    lines = []
    with contextlib.redirect_stdout(io.StringIO()):
        out = runner.Bench(spec, folder, cfg, out=lines.append).run()
    assert out == {"played": 5, "left": 0, "stop_reason": None}
    records = runner.read_results(folder)
    assert len(records) == 5 and all(r["status"] == "done" for r in records)
    for r in records:
        assert r["result"] in ("win", "loss", "draw") and r["turns"] > 0 and r["path"] == "in-process"
        assert r["first"] == ("player" if r["game"] % 2 else "opponent") and r["seed"] == 77 + r["game"] - 1
        assert os.path.isfile(os.path.join(folder, r["replay"]))
        p = r["player"]
        assert p["stats"]["decisions"] > 0 and len(p["latencies"]) == p["stats"]["asks"] > 0
        assert p["log_dir"] and os.path.isdir(p["log_dir"]) and r["opponent_seat"]["stats"]["decisions"] > 0
    # the same seed and first player give both backends the same opening hand
    by_key = {(r["backend"], r["game"]): r for r in records}
    for game in (1, 2):
        assert opening_hand(by_key["heuristic", game]["player"]["log_dir"]) == \
            opening_hand(by_key["random", game]["player"]["log_dir"])
    assert opening_hand(by_key["heuristic", 1]["player"]["log_dir"]) != \
        opening_hand(by_key["heuristic", 2]["player"]["log_dir"])
    # every game's logs live under games_dir/bench/<run folder>/
    logs = glob.glob(str(tmp_path / "games" / "bench" / "run" / "*" / "*" / "game.md"))
    assert len([p for p in logs if "/latest/" not in p]) == 10
    env = json.load(open(os.path.join(folder, "env.json")))
    assert env["core"]["version"] and env["decks"]["saffira"]["main"] == 40 and env["rules"]["name"] == "MR3"

    # a resume with more games plays only the new ones
    spec.games_for = {"heuristic": 4}
    with contextlib.redirect_stdout(io.StringIO()):
        out = runner.Bench(spec, folder, cfg, out=lines.append).run()
    assert out["played"] == 1 and len(runner.finished(runner.read_results(folder))) == 6

    summary = build_report(folder)
    assert summary["games"]["done"] == 6 and summary["games"]["left"] == 0
    assert {b["backend"]: b["games"] for b in summary["backends"]} == {"heuristic": 4, "random": 2}
    md = open(os.path.join(folder, "report.md"), encoding="utf-8").read()
    assert "## Leaderboard" in md and "blackwing:heuristic" in md and md.count("[replay](replays/") == 6
