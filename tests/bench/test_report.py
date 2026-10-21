"""Aggregation and reports from synthetic results (no EDOPro, no LLM)."""

import json
import os

import pytest

from bench_synthetic import record, stats, write
from ygo_agent.bench import metrics, report


def test_aggregate_counts_and_rates():
    recs = [record(game=1, result="win", turns=6, seconds=100, latencies=[1, 2, 3],
                   st=stats(decisions=40, backend=30, rule=4, fallback=2, invalid=3, replies=30, cost=1.0,
                            tokens=(10, 1000, 50000, 2000))),
            record(game=2, result="loss", turns=10, seconds=300, latencies=[4, 5], timeouts=1,
                   st=stats(decisions=60, backend=50, rule=6, fallback=0, invalid=1, replies=50, errors=1, cost=3.0,
                            tokens=(30, 3000, 150000, 4000))),
            record(game=3, result="draw", turns=20, seconds=200, latencies=[6],
                   st=stats(decisions=20, backend=10, rule=0, replies=10, cost=None))]
    a = metrics.aggregate(recs)
    assert (a["games"], a["wins"], a["losses"], a["draws"]) == (3, 1, 1, 1)
    assert a["win_rate"] == pytest.approx(1 / 3)
    assert a["ci95"] == pytest.approx(list(metrics.wilson(1, 3)))
    assert a["first"] == {"games": 2, "wins": 1} and a["second"] == {"games": 1, "wins": 0}
    assert a["turns_mean"] == pytest.approx(12) and a["seconds_mean"] == pytest.approx(200)
    assert a["decisions"] == 120 and a["decisions_per_game"] == pytest.approx(40)
    assert a["invalid_rate"] == pytest.approx(4 / 90)
    assert a["fallback_rate"] == pytest.approx(2 / 120) and a["rule_share"] == pytest.approx(10 / 120)
    assert a["errors"] == 1 and a["timeouts"] == 1
    # latency pooled over every decision of every game
    assert a["latency_mean_s"] == pytest.approx(3.5) and a["latency_p50_s"] == 3 and a["latency_p95_s"] == 6
    assert a["tokens"]["output"] == 4000 and a["tokens_per_game"]["cache_read"] == pytest.approx(200000 / 3)
    # cost: known for two games only
    assert a["cost_usd"] == pytest.approx(4.0) and a["cost_per_game"] == pytest.approx(2.0)
    assert a["cost_known_games"] == 2


def test_aggregate_without_per_decision_latencies_uses_game_means():
    recs = [record(game=1, st=stats(backend=10, latency=(2.0, 5.0))),
            record(game=2, st=stats(backend=30, latency=(4.0, 9.0)))]
    a = metrics.aggregate(recs)
    assert a["latency_mean_s"] == pytest.approx(3.5) and a["latency_p95_s"] == 9.0 and a["latency_p50_s"] is None


def test_aggregate_empty_group():
    a = metrics.aggregate([])
    assert a["games"] == 0 and a["win_rate"] is None and a["ci95"] is None and a["cost_per_game"] is None


def synthetic_run(tmp_path):
    recs = []
    plan = []
    for deck in ("saffira", "blackwing"):
        for opp in ("windbot:Blue-Eyes", "windbot:Branded"):
            for backend, wins in (("sonnet", 3), ("haiku", 1), ("heuristic", 0)):
                for g in range(1, 5):
                    cost = None if backend == "heuristic" else (2.0 if backend == "sonnet" else 0.2)
                    recs.append(record(deck, backend, opp, g, "win" if g <= wins else "loss",
                                       latencies=[] if backend == "heuristic" else [1.0 * g, 2.0],
                                       st=stats(cost=cost)))
                    plan.append(recs[-1]["key"])
    plan.append("saffira|sonnet|windbot:Blue-Eyes|5")  # planned, never played
    recs.append(record("saffira", "sonnet", "windbot:Blue-Eyes", 5, status="aborted", error="usage limit: hit"))
    # a game played twice: the earlier attempt errored, the later one counts
    recs.insert(0, record("saffira", "haiku", "windbot:Branded", 1, status="error", error="room timeout"))
    folder = str(tmp_path / "run")
    spec = {"spec": {"name": "synthetic", "decks": ["saffira", "blackwing"], "backends": ["sonnet", "haiku",
                                                                                         "heuristic"],
                     "opponents": ["windbot:Blue-Eyes", "windbot:Branded"], "games": 4, "games_for": {},
                     "seed": 1000}, "planned": plan}
    env = {"backends": {"sonnet": {"type": "claude-code", "model": "sonnet", "label": "sonnet (claude-code)",
                                   "probe": {"ok": True, "model_ids": ["claude-sonnet-5-5"]}},
                        "haiku": {"type": "claude-code", "model": "haiku"},
                        "heuristic": {"type": "heuristic"}},
           "windbot": {"windbot:Blue-Eyes": {"name": "Blue-Eyes", "deck": "Blue-Eyes", "difficulty": 2},
                       "windbot:Branded": {"name": "Branded", "deck": "Albaz", "difficulty": 3}},
           "rules": {"name": "MR3", "flags": "0xd1800", "text": "Master Rule 3"}}
    write(folder, recs, spec, env)
    return folder


def test_summary_and_report_files(tmp_path):
    folder = synthetic_run(tmp_path)
    summary = report.build(folder)
    for name in ("summary.json", "report.md", "chart.svg"):
        assert os.path.isfile(os.path.join(folder, name))
    assert summary["games"] == {"planned": 49, "done": 48, "aborted": 1, "errors": 1, "left": 1}
    names = [b["backend"] for b in summary["backends"]]
    assert names == ["sonnet", "haiku", "heuristic"]  # by rating
    sonnet = summary["backends"][0]
    assert (sonnet["games"], sonnet["wins"]) == (16, 12) and sonnet["model_ids"] == ["claude-sonnet-5-5"]
    assert sonnet["cost_per_game"] == pytest.approx(2.0)
    heuristic = summary["backends"][2]
    assert heuristic["baseline"] and heuristic["cost_per_game"] == 0.0 and heuristic["wins"] == 0
    assert len(summary["matchups"]) == 12 and all(m["games"] == 4 for m in summary["matchups"])
    assert {o["opponent"] for o in summary["opponents"]} == {"windbot:Blue-Eyes", "windbot:Branded"}
    assert [s["key"] for s in summary["skipped"]] == ["saffira|sonnet|windbot:Blue-Eyes|5"]
    md = open(os.path.join(folder, "report.md"), encoding="utf-8").read()
    assert "| 1 | sonnet | `claude-sonnet-5-5` | 16 | 12-4-0 | **75%**" in md
    assert "heuristic *(baseline)*" in md and "free" in md
    assert "(replays/saffira--sonnet--001.yrpX)" in md  # every game links its replay
    assert "saffira vs Blue-Eyes" in md  # the pivot
    svg = open(os.path.join(folder, "chart.svg"), encoding="utf-8").read()
    assert svg.startswith("<svg") and svg.count("<circle") >= 6 and "prefers-color-scheme: dark" in svg
    saved = json.load(open(os.path.join(folder, "summary.json")))
    assert saved["backends"][0]["backend"] == "sonnet"


def test_report_command_rebuilds(tmp_path, capsys):
    from ygo_agent import cli
    folder = synthetic_run(tmp_path)
    assert cli.main(["bench", "report", folder]) == 0
    out = capsys.readouterr().out
    assert "| # | Backend |" in out and os.path.isfile(os.path.join(folder, "report.md"))


def test_like_for_like_table_when_backends_played_different_counts(tmp_path):
    recs = [record(backend="opus", game=1, result="win")]
    recs += [record(backend="haiku", game=g, result="win" if g == 2 else "loss") for g in (1, 2, 3)]
    folder = str(tmp_path / "run")
    write(folder, recs, {"spec": {"name": "x", "backends": ["opus", "haiku"]}, "planned": [r["key"] for r in recs]})
    summary = report.build(folder)
    common = summary["common"]
    assert common["slots"] == 1 and common["games_numbers"] == [1]
    assert {b["backend"]: (b["wins"], b["games"]) for b in common["backends"]} == {"opus": (1, 1), "haiku": (0, 1)}
    md = open(os.path.join(folder, "report.md"), encoding="utf-8").read()
    assert "### Like for like" in md and "The 1 games every backend played (game 1" in md
