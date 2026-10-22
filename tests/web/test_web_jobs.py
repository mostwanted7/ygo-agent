"""The web app's jobs (ygo_agent/web/jobs.py): parameters → argv (whitelisted flags only, every value checked), and
the job lifecycle with a tiny fake command: output, Stop (Ctrl+C first, then SIGTERM), leftovers killed by token, one
room and one training per deck at a time, and the record a restarted app reads back."""

import json
import os
import signal
import sys
import textwrap
import time

import pytest

from ygo_agent.web.jobs import Builder, JobError, JobRunner, Plan, display_command, processes_with

BOTS = ["Blue-Eyes", "Dragunity"]


@pytest.fixture
def builder(cfg, tmp_path):
    cfg["decks"]["user_dir"] = str(tmp_path / "user-decks")
    return Builder(cfg, windbots=BOTS, join_available=True,
                   forward={"config": "/x/my.toml", "games_dir": "/g", "edopro_dir": None})


def argv(builder, kind, **params):
    return builder.build(kind, params).argv


def rejects(builder, kind, match, **params):
    with pytest.raises(JobError, match=match):
        builder.build(kind, params)


def test_play_argv(builder):
    assert argv(builder, "play", deck="Blackwing", backend="sonnet", best_of=3, password="pw", time_limit=900) == [
        "play", "--deck=blackwing", "--backend=sonnet", "--best-of=3", "--time-limit=900", "--password=pw",
        "--no-web", "--config=/x/my.toml", "--games-dir=/g"]
    plan = builder.build("play", {})
    assert plan.argv[:4] == ["play", "--deck=saffira", "--backend=opus", "--best-of=1"]
    assert plan.room == {"kind": "host", "host": "127.0.0.1", "spectator": False, "password": "", "port": 7911,
                         "name": "ygo-agent"}
    assert argv(builder, "play", join=True, deck="geargia", host="192.168.1.20", port=7912)[:6] == [
        "play", "--join", "--deck=geargia", "--backend=opus", "--host=192.168.1.20", "--port=7912"]
    builder.join_available = False
    rejects(builder, "play", "build.sh", join=True)


def test_selfplay_teach_coach_argv(builder):
    a = {"kind": "agent", "deck": "geargia", "backend": "heuristic"}
    b = {"kind": "windbot", "name": "blue-eyes"}
    plan = builder.build("selfplay", {"a": a, "b": b, "games": 3, "pace": 1.5, "spectate": True})
    assert plan.argv == ["selfplay", "--a=geargia:heuristic", "--b=windbot:Blue-Eyes", "--games=3", "--best-of=1",
                         "--pace=1.5", "--spectate", "--no-web", "--config=/x/my.toml", "--games-dir=/g"]
    assert plan.room["spectator"] and builder.build("selfplay", {"a": a, "b": a}).room is None
    assert argv(builder, "teach", deck="blackwing", opponent=b, pace=2)[:6] == [
        "teach", "--deck=blackwing", "--backend=opus", "--opponent=windbot:Blue-Eyes", "--games=1", "--pace=2"]
    assert argv(builder, "coach", opponent=a, level="intermediate")[:5] == [
        "coach", "--backend=opus", "--opponent=geargia:heuristic", "--level=intermediate", "--best-of=1"]
    assert argv(builder, "coach", deck="saffira")[1] == "--deck=saffira"
    rejects(builder, "selfplay", "parallel", a=a, b=a, spectate=True, parallel=2)
    rejects(builder, "coach", "level", level="expert")


def test_training_learn_doctor_argv(builder, cfg, tmp_path):
    ydk = tmp_path / "My Deck.ydk"
    ydk.write_text("#main\n")
    assert argv(builder, "train-interview", ydk=str(ydk), name="my-deck", display_name="My Deck") == [
        "train", str(ydk), "--name=my-deck", "--display-name=My Deck", "--interview-only", "--config=/x/my.toml"]
    rejects(builder, "train", "read the deck first", name="my-deck")
    (tmp_path / "user-decks" / "my-deck" / "train").mkdir(parents=True)
    assert argv(builder, "train", name="my-deck", backend="opus", player_backend="sonnet", games=2, lab_hands=6,
                max_rounds=1, budget_usd=12.5) == [
        "train", "--name=my-deck", "--resume", "--no-interview", "--backend=opus", "--player-backend=sonnet",
        "--games=2", "--lab-hands=6", "--max-rounds=1", "--budget-usd=12.5", "--config=/x/my.toml"]
    assert argv(builder, "train", name="my-deck")[-2:] == ["--no-interview", "--config=/x/my.toml"]
    assert argv(builder, "learn", deck="geargia", backend="sonnet", budget_usd=5) == [
        "learn", "--deck=geargia", "--backend=sonnet", "--budget-usd=5"]
    assert argv(builder, "doctor") == ["doctor", "--json", "--config=/x/my.toml"]
    plan = builder.build("learn", {"deck": "geargia"})
    assert plan.deck == "geargia" and plan.deck_lock and plan.room is None


def test_bad_parameters_are_refused(builder, tmp_path):
    rejects(builder, "nope", "unknown job kind")
    rejects(builder, "play", "deck", deck="../decks/x")
    rejects(builder, "play", "deck", deck="no-such-deck")
    rejects(builder, "play", "deck", deck=["saffira"])
    rejects(builder, "play", "backend", backend="gpt")
    rejects(builder, "play", "backend", backend="--model=x")
    rejects(builder, "play", "best_of", best_of=2)
    rejects(builder, "play", "best_of", best_of=True)
    rejects(builder, "play", "games", games=0)
    rejects(builder, "play", "time_limit", time_limit="1e9")
    rejects(builder, "play", "port", port=80)
    rejects(builder, "play", "password", password="a\nb")
    rejects(builder, "play", "password", password="x" * 21)
    rejects(builder, "play", "host", join=True, host="evil host; rm -rf")
    rejects(builder, "selfplay", "number", a={"kind": "agent", "deck": "geargia", "backend": "heuristic"},
            b={"kind": "agent", "deck": "saffira", "backend": "heuristic"}, pace="nan")
    rejects(builder, "selfplay", "not a WindBot", a={"kind": "windbot", "name": "Link Spam"}, b={"kind": "windbot",
                                                                                                "name": "Blue-Eyes"})
    rejects(builder, "selfplay", "agent or windbot", a={"kind": "human"}, b={"kind": "human"})
    rejects(builder, "selfplay", "object", a="geargia:opus", b="saffira:opus")
    rejects(builder, "learn", "budget_usd", deck="geargia", budget_usd=10000)
    # .ydk paths: an existing file ending in .ydk, after following links; names: a folder name, no clash with decks/
    real = tmp_path / "real.ydk"
    real.write_text("#main\n")
    (tmp_path / "passwd.ydk").symlink_to("/etc/passwd")
    for bad in ("/etc/passwd", str(tmp_path / "missing.ydk"), str(tmp_path / "passwd.ydk"), f"{real}\0.txt",
                str(tmp_path / "real.ydk" / ".." / ".." / "etc" / "passwd"), ""):
        rejects(builder, "train-interview", "ydk", ydk=bad, name="x")
    for bad in ("../x", "a b", "x" * 41, "-x", "", None, "blackwing"):
        rejects(builder, "train-interview", "name", ydk=str(real), name=bad)


def test_display_command_hides_the_password():
    assert display_command(["play", "--password=secret", "--deck=x y"]) == "ygo-agent play --password=••• '--deck=x y'"


# ---- the lifecycle, with a fake command ----

FAKE = textwrap.dedent("""
    import os, signal, subprocess, sys, time
    mode = sys.argv[1]
    def on_int(*a):
        print("got SIGINT", flush=True)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal.SIG_IGN if mode == "stubborn" else on_int)
    if mode == "leaves":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        print("child", child.pid, flush=True)
    if mode == "fails":
        print("oops", flush=True)
        sys.exit(3)
    print("ready", os.environ.get("YGO_AGENT_RELAY"), flush=True)
    for i in range(600):
        print("tick", i, flush=True)
        time.sleep(0.05)
""")


@pytest.fixture
def runner(cfg, tmp_path):
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    r = JobRunner(Builder(cfg, windbots=[]), jobs_dir=str(tmp_path / "jobs"), relay_url="http://127.0.0.1:1/",
                  prefix=[sys.executable, str(script)], cwd=str(tmp_path))
    r.stop_steps = ((signal.SIGINT, 1.0), (signal.SIGTERM, 1.0), (signal.SIGKILL, 2.0))
    yield r
    r.shutdown(quick=True)


def wait(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def output(runner, job):
    return runner.output(job, 0)["text"]


def test_a_job_runs_streams_and_stops_like_ctrl_c(runner):
    job = runner.launch(Plan("doctor", ["calm"], "a fake"))
    assert job.running and job.pid
    assert wait(lambda: "tick 3" in output(runner, job))
    text = output(runner, job)
    assert text.startswith("$ ygo-agent calm") and "ready http://127.0.0.1:1/" in text
    chunk = runner.output(job, 0)
    assert chunk["text"].endswith("\n") and runner.output(job, chunk["next"])["offset"] == chunk["next"]
    assert runner.output(job, -1)["offset"] == 0  # a short log is sent whole
    runner.stop(job.id)
    assert wait(lambda: not job.running)
    assert job.status == "stopped" and job.code == 0 and "got SIGINT" in output(runner, job)
    saved = json.load(open(os.path.join(runner.dir, job.id + ".json")))
    assert saved["status"] == "stopped" and "token" not in saved and saved["argv"] == ["calm"]


def test_stop_escalates_and_kills_what_the_job_left(runner):
    job = runner.launch(Plan("doctor", ["stubborn"], "ignores Ctrl+C"))
    assert wait(lambda: "tick 1" in output(runner, job))
    started = time.monotonic()
    runner.stop(job.id)
    assert wait(lambda: not job.running)
    assert job.status == "stopped" and job.code == -signal.SIGTERM and time.monotonic() - started >= 0.9

    job = runner.launch(Plan("doctor", ["leaves"], "starts a process in its own session"))
    assert wait(lambda: "child" in output(runner, job))
    child = int(output(runner, job).split("child ")[1].split()[0])
    assert processes_with(job.token) and child in processes_with(job.token)
    runner.stop(job.id)
    assert wait(lambda: not job.running)
    assert wait(lambda: not os.path.exists(f"/proc/{child}") or open(f"/proc/{child}/stat").read().split()[2] == "Z")


def test_exit_status_and_one_room_at_a_time(runner):
    job = runner.launch(Plan("doctor", ["fails"], "fails"))
    assert wait(lambda: not job.running) and job.status == "failed" and job.code == 3
    room = {"kind": "join", "host": "127.0.0.1", "port": 7911}
    first = runner.launch(Plan("play", ["calm"], "a room", room=dict(room)))
    with pytest.raises(JobError) as e:
        runner.launch(Plan("teach", ["calm"], "another room", room=dict(room)))
    assert e.value.status == 409 and first.id in str(e.value)
    deck = runner.launch(Plan("learn", ["calm"], "learn", deck="geargia", deck_lock=True))
    with pytest.raises(JobError, match="working on"):
        runner.launch(Plan("train", ["calm"], "train", deck="Geargia", deck_lock=True))
    other = runner.launch(Plan("learn", ["calm"], "another deck", deck="saffira", deck_lock=True))
    assert other.running and not runner.launch(Plan("selfplay", ["calm"], "no room")).room
    runner.stop(first.id)
    assert wait(lambda: not first.running)
    assert runner.launch(Plan("teach", ["calm"], "now it's free", room=dict(room))).running
    assert deck.running and [j.id for j in runner.list()][:1] != [job.id]  # running jobs first


def test_a_restarted_app_reads_the_jobs_back_and_stops_orphans(runner, cfg, tmp_path):
    job = runner.launch(Plan("doctor", ["calm"], "orphaned"))
    assert wait(lambda: "tick 1" in output(runner, job))
    # A second app on the same folder (the first one died without stopping its job).
    again = JobRunner(Builder(cfg, windbots=[]), jobs_dir=runner.dir)
    old = again.get(job.id)
    assert old.status == "stopped" and "app stopped" in old.error
    assert wait(lambda: job.proc.poll() is not None)  # killed by its token
    assert again.get("../etc") is None and again.get(job.id + "x") is None


def test_go_needs_a_waiting_job(runner):
    job = runner.launch(Plan("play", ["calm"], "waits", room={"kind": "join", "port": 1}))
    with pytest.raises(JobError, match="isn't waiting"):
        runner.go(job.id)
    runner.relayed(job, [], {"text": "Press Enter when the room is open", "button": "Open"}, has_waiting=True)
    runner.go(job.id)
    assert os.path.exists(runner.go_path(job))
    runner.relayed(job, [{"type": "game_start", "game_id": "g1", "seat": 0, "dir": "/x/g1", "name": "g1"},
                         {"type": "game_end", "game_id": "g1", "seat": 0, "result": "win"},
                         {"type": "event", "game_id": "g1"}], None, has_waiting=True)
    assert job.waiting is None and job.games == [{"game_id": "g1", "seat": 0, "dir": "/x/g1", "name": "g1",
                                                  "ended": True}]
