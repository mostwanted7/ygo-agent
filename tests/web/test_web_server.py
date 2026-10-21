"""The panel's HTTP server, hit with urllib: static files, the APIs, card pictures (local, downloaded and cached,
placeholder), Server-Sent Events, and the feedback endpoint writing feedback.md."""

import json
import os
import shutil
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from web_helpers import play_case
from ygo_agent.web import server as web
from ygo_agent.web.bus import BUS
from ygo_agent.web.pics import PicStore

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture
def panel(cfg, db, played, tmp_path, quiet_bus):
    game_dir, _ = played
    pics = tmp_path / "edopro" / "pics"
    pics.mkdir(parents=True)
    card = next(iter(db.cards))
    (pics / f"{card}.jpg").write_bytes(JPEG)
    store = PicStore(str(tmp_path / "edopro"), db=db, cache_dir=str(tmp_path / "cache"), fetch=False)
    srv = web.start(cfg, db, port=0, pics=store)
    srv.game = os.path.basename(game_dir)
    srv.game_dir = game_dir
    srv.card = card
    yield srv
    srv.stop()


def get(srv, path, headers=None):
    req = urllib.request.Request(srv.url.rstrip("/") + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def post(srv, body, ctype="application/json", headers=None):
    data = json.dumps(body).encode() if not isinstance(body, bytes) else body
    req = urllib.request.Request(srv.url + "api/feedback", data=data, method="POST",
                                 headers={"Content-Type": ctype, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_static_files_and_apis(panel):
    status, ctype, body = get(panel, "/")
    assert status == 200 and ctype.startswith("text/html") and b"/static/app.js" in body
    for name in ("app.js", "style.css", "favicon.svg"):
        assert get(panel, f"/static/{name}")[0] == 200
    assert get(panel, "/static/../server.py")[0] == 404
    assert get(panel, "/static/%2e%2e/server.py")[0] == 404
    status, _, body = get(panel, "/api/games")
    games = json.loads(body)
    assert status == 200 and games["live"] == [] and [g["name"] for g in games["recorded"]] == [panel.game]
    status, _, body = get(panel, f"/api/recorded/{panel.game}")
    data = json.loads(body)
    assert status == 200 and data["summary"]["name"] == panel.game
    assert {"game_start", "decision", "reply", "event"} <= {m["type"] for m in data["messages"]}
    assert get(panel, "/api/recorded/..")[0] == 404
    assert get(panel, "/api/recorded/nope")[0] == 404
    assert get(panel, "/nothing")[0] == 404


def test_other_sites_are_refused(panel):
    assert get(panel, "/api/games", {"Host": "evil.example:7930"})[0] == 403
    assert post(panel, {"game_id": f"rec:{panel.game}", "text": "x"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert post(panel, b'{"text": "x"}', ctype="text/plain")[0] == 415  # a "simple" cross-site form post


def test_card_text(panel, db):
    status, _, body = get(panel, f"/cardinfo/{panel.card}")
    info = json.loads(body)
    assert status == 200 and info["name"] == db.name(panel.card) and info["type_line"] and "text" in info
    assert get(panel, "/cardinfo/1")[0] == 404


def test_card_pictures_local_placeholder_and_download(panel, db, tmp_path):
    status, ctype, body = get(panel, f"/card/{panel.card}.jpg")
    assert status == 200 and ctype == "image/jpeg" and body == JPEG
    other = [c for c in db.cards if c != panel.card][0]
    status, ctype, body = get(panel, f"/card/{other}.jpg")
    assert status == 200 and ctype == "image/svg+xml" and db.name(other).split()[0].encode() in body

    hits = []

    class Pics(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            ok = self.path == f"/pics/{other}.jpg"
            self.send_response(200 if ok else 404)
            self.send_header("Content-Length", str(len(JPEG) if ok else 0))
            self.end_headers()
            if ok:
                self.wfile.write(JPEG)

    remote = ThreadingHTTPServer(("127.0.0.1", 0), Pics)
    threading.Thread(target=remote.serve_forever, daemon=True).start()
    try:
        store = PicStore(str(tmp_path / "edopro"), db=db, cache_dir=str(tmp_path / "cache"),
                         urls=[f"http://127.0.0.1:{remote.server_address[1]}/pics/{{}}.jpg"])
        assert store.get(other) == (JPEG, "image/jpeg")
        assert os.path.exists(tmp_path / "cache" / f"{other}.jpg")
        assert store.get(other)[0] == JPEG and len(hits) == 1  # cached
        missing = 999999999
        assert store.get(missing)[1] == "image/svg+xml" and store.get(missing)[1] == "image/svg+xml"
        assert len(hits) == 2  # a failed download isn't retried right away
    finally:
        remote.shutdown()
        remote.server_close()


def test_edopro_picture_urls(tmp_path):
    from ygo_agent.web.pics import EDOPRO_DEFAULT_PICS, pic_urls
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "configs.json").write_text(json.dumps({"urls": [{"url": "default", "type": "pic"},
                                                                           {"url": "default", "type": "field"}]}))
    assert pic_urls(str(tmp_path)) == [EDOPRO_DEFAULT_PICS]
    (tmp_path / "config" / "user_configs.json").write_text(json.dumps({"urls": [{"url": "https://x/{}.jpg", "type": "pic"}]}))
    assert pic_urls(str(tmp_path)) == ["https://x/{}.jpg", EDOPRO_DEFAULT_PICS]


def read_events(sock_file, until):
    """Parse SSE frames until `until(msgs)` is true."""
    msgs, frame = [], {}
    while not until(msgs):
        line = sock_file.readline().decode().rstrip("\n")
        if line.startswith("id: "):
            frame["id"] = int(line[4:])
        elif line.startswith("data: "):
            frame["data"] = json.loads(line[6:])
        elif line == "" and frame:
            msgs.append({**frame["data"], "_id": frame.get("id")})
            frame = {}
    return msgs


def test_server_sent_events_backlog_resume_and_live(panel):
    for i in range(3):
        BUS.publish({"type": "event", "game_id": "g", "ev": {"t": "event", "e": "draw", "player": 0, "count": i}})
    host, port = panel.httpd.server_address[:2]
    sock = socket.create_connection((host, port), timeout=5)
    sock.sendall(b"GET /stream?game=g HTTP/1.1\r\nHost: 127.0.0.1\r\nLast-Event-ID: 1\r\n\r\n")
    f = sock.makefile("rb")
    assert f.readline().startswith(b"HTTP/1.1 200")
    while f.readline() not in (b"\r\n", b""):
        pass
    got = read_events(f, lambda ms: any(m["type"] == "caught_up" for m in ms))
    assert got[0]["type"] == "games" and got[0]["games"][0]["game_id"] == "g"
    backlog = [m for m in got if m["type"] == "event"]
    assert [m["seq"] for m in backlog] == [2, 3] and [m["_id"] for m in backlog] == [2, 3]
    assert backlog[0]["text"] == "You draw 1 card(s)."  # rendered by the server's describe.py
    BUS.publish({"type": "game_start", "game_id": "other", "deck_name": "Saffira"})
    BUS.publish({"type": "event", "game_id": "other", "ev": {"e": "draw", "player": 0, "count": 1}})
    BUS.publish({"type": "event", "game_id": "g", "ev": {"t": "event", "e": "draw", "player": 1, "count": 2}})
    live = read_events(f, lambda ms: len(ms) >= 2)
    assert live[0]["type"] == "game_start" and live[0]["_id"] is None  # another game's summary: no id
    assert live[1]["game_id"] == "g" and live[1]["_id"] == 4
    sock.close()


def test_feedback_for_a_recorded_game(panel):
    status, out = post(panel, {"game_id": f"rec:{panel.game}", "seat": 0, "decision": 4, "text": "  pass here  "})
    assert status == 200 and not out["live"] and out["n"] == 1 and out["context"].endswith("right after decision #4")
    with open(os.path.join(panel.game_dir, "feedback.md"), encoding="utf-8") as f:
        assert f.read() == f"- ({out['context']}) pass here\n"
    assert post(panel, {"game_id": f"rec:{panel.game}", "text": "   "})[0] == 400
    assert post(panel, {"game_id": "rec:nope", "text": "x"})[0] == 404
    assert post(panel, {"game_id": f"rec:{panel.game}", "text": "x", "decision": "seven"})[0] == 400


def test_feedback_for_a_live_game_goes_through_its_seat(panel, cfg, db, scripted):
    brain, _ = play_case(cfg, db, scripted, name="keep-vata-no-bwd")
    gid = brain.log.web.game_id
    status, out = post(panel, {"game_id": gid, "seat": 0, "text": "don't Veiler my Stratos"})
    assert status == 200 and out["live"] and out["context"] == f"turn {brain.turn}, right after decision #{brain.last_decision}"
    brain.close()
    with open(os.path.join(brain.log.dir, "feedback.md"), encoding="utf-8") as f:
        assert f.read() == f"- ({out['context']}) don't Veiler my Stratos\n"
    assert any(m["type"] == "feedback_ack" and m["who"] == "Web panel" for m in BUS.backlog(gid))


def test_a_busy_port_is_reported(cfg, db, panel):
    with pytest.raises(OSError, match="--web-port"):
        web.start(cfg, db, port=panel.httpd.server_address[1])


def test_feedback_for_a_demo_goes_to_the_recorded_folder(panel):
    BUS.publish({"type": "game_start", "game_id": "demo:x:1", "dir": panel.game_dir, "demo": True})
    status, out = post(panel, {"game_id": "demo:x:1", "decision": 2, "turn": 1, "text": "noted in a demo"})
    assert status == 200 and not out["live"] and out["context"] == "turn 1, right after decision #2"
    assert any(m["type"] == "feedback_ack" for m in BUS.backlog("demo:x:1"))
    with open(os.path.join(panel.game_dir, "feedback.md"), encoding="utf-8") as f:
        assert f.read().endswith("- (turn 1, right after decision #2) noted in a demo\n")


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_the_page_script_parses():
    import subprocess
    subprocess.run(["node", "--check", os.path.join(web.STATIC, "app.js")], check=True)
