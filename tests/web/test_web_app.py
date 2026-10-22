"""The web app (`ygo-agent web`): its API over urllib (decks, playbook saves with history, tips, interview answers,
jobs), the relay (token, loopback only, messages injected as they were rendered, notes on a relayed game landing in
its folder), the child side of the relay, and a play/selfplay/teach/coach panel staying the plain panel."""

import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request

import pytest

from ygo_agent.web import relay, server as web
from ygo_agent.web.bus import BUS, Bus
from ygo_agent.web.pics import PicStore

FAKE = "import time\nprint('fake job', flush=True)\nfor i in range(400):\n    time.sleep(0.05)\n"


@pytest.fixture
def user_deck(cfg, tmp_path):
    """A deck of the user's own (in a temporary user decks dir), with a playbook."""
    cfg["decks"]["user_dir"] = str(tmp_path / "user-decks")
    folder = tmp_path / "user-decks" / "mydeck"
    folder.mkdir(parents=True)
    (folder / "deck.json").write_text(json.dumps({"name": "My Deck", "ydk": "deck.ydk"}))
    (folder / "deck.ydk").write_text("#main\n")
    (folder / "playbook.md").write_text("## Game plan\n\nAttack.\n")
    return folder


@pytest.fixture
def app(cfg, db, played, tmp_path, user_deck, quiet_bus):
    store = PicStore(str(tmp_path / "edopro"), db=db, cache_dir=str(tmp_path / "cache"), fetch=False)
    srv = web.start(cfg, db, port=0, pics=store, app={"jobs_dir": str(tmp_path / "jobs"),
                                                     "windbots": ([{"name": "Blue-Eyes", "deck": "Blue-Eyes",
                                                                    "difficulty": 2}], [])})
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    srv.runner = srv.panel.app.runner
    srv.runner.prefix = [sys.executable, str(script)]
    srv.runner.stop_steps = ((signal.SIGINT, 2.0), (signal.SIGKILL, 2.0))
    srv.game_dir = played[0]
    yield srv
    srv.panel.app.shutdown(quick=True)
    srv.stop()


def call(srv, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(srv.url.rstrip("/") + path, data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_app_info_and_the_page(app, cfg):
    status, info = call(app, "/api/app")
    assert status == 200 and info["app"] is True and info["default_backend"] == cfg["agent"]["backend"]
    assert "test" not in {b["name"] for b in info["backends"]}  # the tests' scripted profile isn't offered
    assert [w["name"] for w in info["windbots"]] == ["Blue-Eyes"]
    assert {"opus", "heuristic", "random"} <= {b["name"] for b in info["backends"]}
    assert info["games_dir"] and info["decks_dirs"]["user"].endswith("user-decks")
    with urllib.request.urlopen(app.url, timeout=5) as r:
        page = r.read().decode()
    assert 'data-mode="app"' in page and "/static/shell.js" in page
    with urllib.request.urlopen(app.url + "static/shell.js", timeout=5) as r:
        assert r.status == 200


def test_decks_notes_playbook_tips_and_interview(app, user_deck, cfg):
    games = os.path.dirname(app.game_dir)
    other = os.path.join(games, "2026-10-22_120000_mydeck")
    os.makedirs(other)
    open(os.path.join(other, "game.jsonl"), "w").close()
    with open(os.path.join(other, "meta.json"), "w") as f:
        json.dump({"deck": "mydeck", "mode": "play"}, f)
    with open(os.path.join(other, "feedback.md"), "w") as f:
        f.write("- (turn 3, right after decision #14; from Web panel) Attack first.\n"
                "- (turn 4, right after decision #20; from Spectator bob) Bad play.\n")
    status, data = call(app, "/api/decks")
    row = next(d for d in data["decks"] if d["key"] == "mydeck")
    assert status == 200 and row["pending_notes"] == 1 and row["other_notes"] == 1 and row["name"] == "My Deck"
    assert {"blackwing", "saffira"} <= {d["key"] for d in data["decks"]}

    status, deck = call(app, "/api/decks/MyDeck")
    assert status == 200 and deck["key"] == "mydeck" and deck["playbook"].startswith("## Game plan")
    assert [n["text"] for n in deck["pending"]] == ["Attack first."] and deck["other_pending"] == 1
    assert deck["pending"][0]["decision"] == 14 and deck["pending"][0]["recorded"] == os.path.basename(other)
    assert call(app, "/api/decks/nope")[0] == 404 and call(app, "/api/decks/..%2f..")[0] == 404

    # The playbook: saved, the old one kept in train/history, a stale base or an oversized text refused.
    status, out = call(app, "/api/decks/mydeck/playbook", {"text": "## Game plan\r\n\r\nAttack twice.", "base": deck["playbook_sha"]})
    assert status == 200 and out["history"] and open(out["history"]).read() == "## Game plan\n\nAttack.\n"
    assert open(user_deck / "playbook.md").read() == "## Game plan\n\nAttack twice.\n"
    assert call(app, "/api/decks/mydeck/playbook", {"text": "x", "base": deck["playbook_sha"]})[0] == 409
    assert call(app, "/api/decks/mydeck/playbook", {"text": "x" * (300 * 1024)})[0] == 400
    assert call(app, "/api/decks/mydeck/playbook", raw=b"{}", headers={"Content-Length": str(2 << 20)})[0] == 413

    status, out = call(app, "/api/decks/mydeck/tips", {"text": "Keep Gold Gadget for a turn you can Xyz."})
    assert status == 200 and out["tips"][0]["text"].startswith("Keep Gold Gadget")
    assert call(app, "/api/decks/mydeck/tips", {"text": "  "})[0] == 400
    status, out = call(app, "/api/decks/mydeck/interview", {"answers": [{"question": "Go first?", "answer": "Yes."},
                                                                       {"question": "Skipped", "answer": ""}]})
    assert status == 200 and out["saved"] == 1 and [t["title"] for t in out["tips"]] == ["Tip", "Go first?"]
    assert open(user_deck / "tips.md").read().startswith("# Tips for My Deck")
    assert call(app, "/api/decks/mydeck/interview", {"answers": "nope"})[0] == 400


def test_a_deck_being_trained_shows_its_interview(app, cfg, tmp_path):
    folder = tmp_path / "user-decks" / "chaos" / "train"
    folder.mkdir(parents=True)
    (folder / "interview.json").write_text(json.dumps({"deck": "Chaos", "questions": [
        {"id": "win", "question": "How does it win?", "why": "the game plan"}]}))
    status, deck = call(app, "/api/decks/chaos")
    assert status == 200 and deck["name"] == "Chaos" and deck["training_only"] and deck["interview"]["questions"]
    assert deck["train"]["status"] == "interview"
    status, out = call(app, "/api/decks/chaos/interview", {"answers": [{"question": "How does it win?",
                                                                       "answer": "Big attacks."}]})
    assert status == 200 and (tmp_path / "user-decks" / "chaos" / "tips.md").read_text().startswith("# Tips for Chaos")


def test_jobs_api_start_output_stop(app):
    assert call(app, "/api/jobs", {"kind": "play", "params": {"deck": "../x"}})[0] == 400
    assert call(app, "/api/jobs", {"kind": "rm", "params": {}})[0] == 400
    status, out = call(app, "/api/jobs", {"kind": "doctor", "params": {}})
    job = out["job"]
    assert status == 200 and job["running"] and job["command"] == "ygo-agent doctor --json"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "fake job" not in call(app, f"/api/jobs/{job['id']}?offset=0")[1]["output"]["text"]:
        time.sleep(0.1)
    status, one = call(app, f"/api/jobs/{job['id']}?offset=0")
    assert status == 200 and "fake job" in one["output"]["text"] and one["output"]["next"] > 0
    assert call(app, "/api/jobs/nope")[0] == 404 and call(app, "/api/jobs/nope/stop", {})[0] == 404
    assert call(app, f"/api/jobs/{job['id']}/go", {})[0] == 409
    assert call(app, f"/api/jobs/{job['id']}/stop", {})[0] == 200
    while time.monotonic() < deadline and call(app, f"/api/jobs/{job['id']}")[1]["job"]["running"]:
        time.sleep(0.1)
    assert call(app, f"/api/jobs/{job['id']}")[1]["job"]["status"] == "stopped"
    assert [j["id"] for j in call(app, "/api/jobs")[1]["jobs"]] == [job["id"]]


def test_the_relay_injects_messages_and_notes_land_in_the_game_folder(app, monkeypatch):
    status, out = call(app, "/api/jobs", {"kind": "doctor", "params": {}})
    job = app.runner.get(out["job"]["id"])
    gid = "run-m1"
    batch = {"messages": [
        {"type": "game_start", "game_id": gid, "seat": 0, "deck": "blackwing", "deck_name": "Blackwing",
         "dir": app.game_dir, "name": os.path.basename(app.game_dir), "seq": 99},
        {"type": "event", "game_id": gid, "seat": 0, "ev": {"t": "event", "e": "draw", "player": 0, "count": 1}},
        {"type": "decision", "game_id": gid, "seat": 0, "decision": {"id": 7, "kind": "idle", "state": {"turn": 2}}},
        "not a message", {"type": "event", "game_id": "../bad id", "seat": 0}],
        "waiting": {"text": "Waiting for a spectator before game 1", "button": "Start without a spectator"}}
    assert call(app, "/api/relay", batch)[0] == 403
    assert call(app, "/api/relay", batch, headers={"X-Relay-Token": job.token[:-1] + "x"})[0] == 403
    status, res = call(app, "/api/relay", batch, headers={"X-Relay-Token": job.token})
    assert status == 200 and res["n"] == 3
    backlog = BUS.backlog(gid)
    assert [m["seq"] for m in backlog] == [1, 2, 3]       # numbered by the app's bus, not the job's
    assert "text" not in backlog[1] and "question" not in backlog[2]  # not rendered again
    assert job.waiting["button"] == "Start without a spectator" and job.games[0]["dir"] == app.game_dir
    status, one = call(app, f"/api/jobs/{job.id}")
    assert one["job"]["games"][0]["live"] and one["job"]["games"][0]["recorded"] == os.path.basename(app.game_dir)
    assert call(app, f"/api/jobs/{job.id}/go", {})[0] == 200 and os.path.exists(app.runner.go_path(job))

    # A note on the relayed live game: its seat lives in the job, so it goes to the game's folder.
    status, ack = call(app, "/api/feedback", {"game_id": gid, "seat": 0, "text": "Keep the trap."})
    assert status == 200 and not ack["live"] and ack["file"] == os.path.join(app.game_dir, "feedback.md")
    assert "right after decision #7" in open(ack["file"]).read().splitlines()[-1]

    # A stopped job's unfinished game is ended on the bus, so no list shows it live forever.
    app.runner.stop(job.id)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and job.running:
        time.sleep(0.05)
    assert BUS.seat_info(gid, 0)["result"] == "unfinished"
    assert not next(g for g in BUS.games() if g["game_id"] == gid)["live"]


def test_app_endpoints_answer_this_machine_only(app, monkeypatch):
    monkeypatch.setattr(web, "loopback", lambda address: False)
    for path in ("/api/app", "/api/decks", "/api/jobs", "/api/decks/mydeck"):
        assert call(app, path)[0] == 403
    assert call(app, "/api/jobs", {"kind": "doctor"})[0] == 403
    assert call(app, "/api/relay", {"messages": []})[0] == 403
    assert call(app, "/api/games")[0] == 200  # the panel's own endpoints keep their Host/Origin checks only
    monkeypatch.undo()
    assert call(app, "/api/jobs", {"kind": "doctor"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert call(app, "/api/jobs", raw=b'{"kind": "doctor"}', headers={"Content-Type": "text/plain"})[0] == 415


def test_loopback_addresses():
    assert web.loopback("127.0.0.1") and web.loopback("127.8.0.1") and web.loopback("::1")
    assert web.loopback("::ffff:127.0.0.1") and not web.loopback("192.168.1.5") and not web.loopback("nope")


def test_a_play_panel_has_no_jobs(cfg, db, tmp_path, quiet_bus):
    store = PicStore(str(tmp_path / "edopro"), db=db, cache_dir=str(tmp_path / "cache"), fetch=False)
    srv = web.start(cfg, db, port=0, pics=store)
    try:
        assert call(srv, "/api/app") == (200, {"app": False, "jobs": False})
        assert call(srv, "/api/jobs")[0] == 404 and call(srv, "/api/relay", {"messages": []})[0] == 404
        with urllib.request.urlopen(srv.url, timeout=5) as r:
            assert 'data-mode="panel"' in r.read().decode()
    finally:
        srv.stop()


# ---- the job's side of the relay ----

def test_the_relay_sender_batches_to_the_app(app, cfg):
    status, out = call(app, "/api/jobs", {"kind": "doctor", "params": {}})
    token = app.runner.get(out["job"]["id"]).token
    child = Bus()
    sender = relay.Relay(app.url, token)
    child.activate(lambda m: {**m, "text": "rendered in the job"})
    child.add_sink(sender)
    for i in range(120):
        child.publish({"type": "event", "game_id": "child-g", "ev": {"e": "draw", "count": i}})
    sender.set_waiting({"text": "The room is open?", "button": "Go"})
    sender.flush(5)
    got = BUS.backlog("child-g")
    assert len(got) == 120 and got[0]["text"] == "rendered in the job" and sender.sent >= 1 and sender.dropped == 0
    assert app.runner.get(out["job"]["id"]).waiting == {"text": "The room is open?", "button": "Go"}


def test_the_relay_never_blocks_when_the_app_is_gone():
    sender = relay.Relay("http://127.0.0.1:9/", "token", timeout=1)
    bus = Bus()
    bus.activate()
    bus.add_sink(sender)
    started = time.monotonic()
    for i in range(1000):
        bus.publish({"type": "event", "game_id": "g", "ev": {}})
    assert time.monotonic() - started < 1
    sender.flush(3)
    assert sender.dropped >= 1 and sender.sent == 0


def test_install_only_with_the_app_environment(cfg, monkeypatch):
    monkeypatch.setattr(relay, "_relay", None)
    bus = Bus()
    assert relay.install(cfg, bus=bus, env={}) is None and not bus.active and not relay.active()
    r = relay.install(cfg, bus=bus, env={relay.ENV_URL: "http://127.0.0.1:9/", relay.ENV_TOKEN: "t"})
    assert r and bus.active and relay.active() and relay.url() == "http://127.0.0.1:9/"
    assert isinstance(bus.renderer, relay.LazyRenderer)
    from ygo_agent.match import ensure_panel
    import ygo_agent.match as match
    monkeypatch.setattr(match, "_PANEL", None)
    assert ensure_panel(cfg, None).url == "http://127.0.0.1:9/"  # the app is the panel: no server starts
    go = os.path.join(os.path.dirname(__file__), "..", "..", "nonexistent-go-file")
    monkeypatch.setenv(relay.ENV_GO, go)
    assert not relay.go_requested()
