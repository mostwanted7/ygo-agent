"""The plan (seed pairing, ordering), plan files, and the runner's resume / stop logic with a fake game player
(no EDOPro, no LLM)."""

import json
import os
import threading

import pytest

from bench_synthetic import record, stats
from ygo_agent.bench import runner
from ygo_agent.bench.spec import BenchSpec, SpecError, parse_games_for


def spec(**kw):
    base = dict(name="t", decks=["saffira", "blackwing"], backends=["sonnet", "haiku", "heuristic"],
                opponents=["windbot:Blue-Eyes", "windbot:Branded"], games=4, seed=500)
    base.update(kw)
    return BenchSpec(**base).validate()


def test_every_backend_gets_the_same_seeds_and_first_player():
    s = spec(games_for={"heuristic": 6, "sonnet": 2})
    jobs = s.jobs()
    by_pairing = {}
    for j in jobs:
        by_pairing.setdefault((j.deck, j.opponent, j.backend), []).append((j.index, j.seed, j.first))
    plans = {k: v for k, v in by_pairing.items()}
    for (deck, opp, backend), games in plans.items():
        n = s.games_of(backend)
        assert games == [(i, 500 + i, "player" if i % 2 == 0 else "opponent") for i in range(n)]
    # a shorter backend's games are a prefix of a longer one's
    assert plans[("saffira", "windbot:Blue-Eyes", "sonnet")] == plans[("saffira", "windbot:Blue-Eyes", "heuristic")][:2]
    assert len(jobs) == 2 * 2 * (6 + 4 + 2)
    assert len({j.key for j in jobs}) == len(jobs) and len({j.slug for j in jobs}) == len(jobs)


def test_jobs_advance_game_by_game():
    jobs = spec().jobs()
    indexes = [j.index for j in jobs]
    assert indexes == sorted(indexes)  # every pairing plays game 1 before any plays game 2
    first_round = [j for j in jobs if j.index == 0]
    assert len(first_round) == 2 * 2 * 3


def test_spec_validation():
    with pytest.raises(SpecError):
        spec(decks=[])
    with pytest.raises(SpecError):
        spec(opponents=["human"])
    with pytest.raises(SpecError):
        spec(games_for={"opus": 2})  # not benchmarked
    with pytest.raises(SpecError):
        spec(backends=["saffira:sonnet"])
    with pytest.raises(SpecError):
        BenchSpec.from_dict({"decks": "saffira", "colour": "blue"})
    assert parse_games_for("heuristic=30, opus=2") == {"heuristic": 30, "opus": 2}
    with pytest.raises(SpecError):
        parse_games_for("opus")


def test_plan_file(tmp_path):
    path = tmp_path / "mini.toml"
    path.write_text('decks = "saffira, blackwing"\nbackends = ["haiku", "random"]\nopponents = ["windbot:Blue-Eyes"]\n'
                    'games = 3\nbudget_usd = 0\n[games_for]\nrandom = 10\n')
    s = BenchSpec.load(str(path)).validate()
    assert s.name == "mini" and s.decks == ["saffira", "blackwing"] and s.games_of("random") == 10
    assert s.budget_usd is None and len(s.jobs()) == 2 * (3 + 10)


def test_repo_plan_files_are_valid():
    folder = os.path.join(os.path.dirname(__file__), "..", "..", "bench", "configs")
    for name in sorted(os.listdir(folder)):
        if name.endswith(".toml"):
            assert BenchSpec.load(os.path.join(folder, name)).validate().jobs()


# --- resume and stop logic, with a fake play_one --------------------------------------------------------------

class FakeBench(runner.Bench):
    """Bench without the engine: prepare() only sets the profiles."""

    def prepare(self):
        self.profiles = {b: {"name": b, "type": "heuristic" if b in ("heuristic", "random") else "claude-code"}
                         for b in self.spec.backends}
        self.db = self.engine = None
        self.write_spec()


@pytest.fixture
def fake_games(monkeypatch):
    """Replace play_one: outcome(job) -> a record (default: a win)."""
    played = []
    lock = threading.Lock()

    def install(outcome=None):
        def play_one(job, spec, cfg, db, engine, folder, rooms):
            with lock:
                played.append(job.key)
            if outcome:
                r = outcome(job)
                if r is not None:
                    return r
            return record(job.deck, job.backend, job.opponent, job.index + 1, "win", st=stats(cost=1.0))
        monkeypatch.setattr(runner, "play_one", play_one)
        return played
    return install


def run_bench(folder, **kw):
    s = spec(**kw)
    lines = []
    out = FakeBench(s, folder, {"backends": {}}, out=lines.append).run()
    return out, lines


def test_resume_skips_finished_games(tmp_path, fake_games):
    played = fake_games()
    folder = str(tmp_path / "run")
    os.makedirs(folder)
    total = len(spec().jobs())
    # an earlier invocation: two games done, one aborted, one errored, plus a half-written last line
    with open(os.path.join(folder, "results.jsonl"), "w") as f:
        for r in (record("saffira", "sonnet", "windbot:Blue-Eyes", 1), record("saffira", "haiku", "windbot:Blue-Eyes", 1),
                  record("saffira", "sonnet", "windbot:Branded", 1, status="aborted", error="usage limit"),
                  record("blackwing", "sonnet", "windbot:Branded", 1, status="error", error="boom")):
            f.write(json.dumps(r) + "\n")
        f.write('{"key": "half a li')
    out, _ = run_bench(folder, parallel=3)
    assert out["played"] == total - 2 and out["left"] == 0
    assert "saffira|sonnet|windbot:Blue-Eyes|1" not in played
    assert "saffira|sonnet|windbot:Branded|1" in played and "blackwing|sonnet|windbot:Branded|1" in played
    # resuming a finished run plays nothing
    played.clear()
    out, _ = run_bench(folder)
    assert out["played"] == 0 and played == []
    done = runner.finished(runner.read_results(folder))
    assert len(done) == total
    spec_file = json.load(open(os.path.join(folder, "spec.json")))
    assert len(spec_file["invocations"]) == 2 and len(spec_file["planned"]) == total


def test_usage_limit_stops_that_backend_type(tmp_path, fake_games):
    def outcome(job):
        if job.backend == "haiku":
            r = record(job.deck, job.backend, job.opponent, job.index + 1, status="aborted", error="usage limit: hit")
            r["player"] = {"limit_errors": 3}
            return r
    played = fake_games(outcome)
    out, lines = run_bench(str(tmp_path / "run"), parallel=1)
    # the first haiku game hits the limit: no more claude-code games start; the heuristic baseline keeps going
    first_haiku = next(i for i, k in enumerate(played) if "|haiku|" in k)
    assert all("|heuristic|" in k for k in played[first_haiku + 1:])
    assert sum("|heuristic|" in k for k in played) == 16
    assert any("not counted" in line for line in lines)
    assert out["left"] > 0


def test_budget_stops_new_games(tmp_path, fake_games):
    played = fake_games()  # every game costs $1
    out, lines = run_bench(str(tmp_path / "run"), parallel=1, budget_usd=5)
    assert len(played) == 5 and out["stop_reason"].startswith("budget")


def test_errors_in_a_row_stop_the_run(tmp_path, fake_games):
    played = fake_games(lambda job: record(job.deck, job.backend, job.opponent, job.index + 1, status="error",
                                           error="WindBot can't play"))
    out, _ = run_bench(str(tmp_path / "run"), parallel=1)
    assert len(played) == runner.MAX_ERRORS_IN_A_ROW and "in a row" in out["stop_reason"]
    assert runner.finished(runner.read_results(str(tmp_path / "run"))) == {}


def test_scan_prompts(tmp_path):
    path = tmp_path / "prompts.jsonl"
    rows = [{"id": 2, "info": {"seconds": 1.5}}, {"id": 2, "info": {"seconds": 0.5, "error": "invalid"}},
            {"id": 3, "info": {"seconds": 120.0, "error": "timed out after 120s"}},
            {"id": 4, "info": {"seconds": 0.1, "error": "Claude AI usage limit reached|1792620000"}},
            {"id": 5, "info": {"seconds": 0.2, "error": "You've hit your limit · resets 3am"}}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
    s = runner.scan_prompts(str(path))
    assert s["latencies"] == [2.0, 120.0, 0.1, 0.2]
    assert s["timeouts"] == 1 and s["limit_errors"] == 2 and len(s["error_samples"]) == 3
    assert runner.scan_prompts(str(tmp_path / "missing.jsonl"))["latencies"] == []
