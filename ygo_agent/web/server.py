"""The web panel's HTTP server (stdlib only): static files, Server-Sent Events from the bus, card pictures and texts,
recorded games, and the feedback box. It binds 127.0.0.1 by default: it serves your game logs and writes notes.

    GET  /                      the panel (static/index.html); with `ygo-agent web`, the app around it
    GET  /stream?game=ID        SSE: the game list, then game ID's backlog and live messages (Last-Event-ID resumes)
    GET  /api/games             {"live": [...], "recorded": [...]}
    GET  /api/recorded/NAME     a recorded game as bus messages
    GET  /card/CODE.jpg         a card picture (EDOPro's pics, the download cache, a download, or a placeholder)
    GET  /cardinfo/CODE         the card's name, type line and text
    POST /api/feedback          {"game_id", "seat", "text", "decision"?, "turn"?} -> saved like a `!note`

The app (`ygo-agent web` only; web/app.py, docs/web.md) adds, for a client on this machine only:

    GET  /api/app               what this machine has: backends, WindBot deck AIs, EDOPro's decks, folders
    GET  /api/decks             every deck, with pending notes, tips and training
    GET  /api/decks/NAME        one deck: playbook, tips, pending notes, train report, interview, games, jobs
    POST /api/decks/NAME/playbook   {"text", "base"?}   (the old text goes to train/history/)
    POST /api/decks/NAME/tips       {"text", "title"?}
    POST /api/decks/NAME/interview  {"answers": [{"question", "answer"}]}
    GET  /api/jobs              the jobs, running first
    POST /api/jobs              {"kind", "params"} -> starts one (web/jobs.py)
    GET  /api/jobs/ID?offset=N  one job and its output from byte N (-1: the end)
    POST /api/jobs/ID/stop      Ctrl+C, then SIGTERM, then SIGKILL
    POST /api/jobs/ID/go        the button for what the job waits for
    POST /api/relay             a job's bus messages (X-Relay-Token: the job's token)
"""

import ipaddress
import json
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import paths
from ..agent.carddb import ATTRIBUTES, RACES
from .bus import BUS, sse
from .pics import PicStore
from .recorded import Library, append_feedback
from .render import Renderer

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
CARD = re.compile(r"^/card/(\d{1,10})(?:\.(?:jpg|png))?$")
CARD_INFO = re.compile(r"^/cardinfo/(\d{1,10})$")
RECORDED = re.compile(r"^/api/recorded/([\w.+-]+)$")
DECK = re.compile(r"^/api/decks/([\w-]{1,40})(?:/(playbook|tips|interview))?$")
JOB = re.compile(r"^/api/jobs/([\w.-]{1,80})(?:/(stop|go))?$")
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")
HEARTBEAT = 15   # seconds between SSE pings
STALL = 60       # seconds a stream write may block before the browser is given up (it reconnects)
MAX_BODY = 65536  # bytes a POST may carry (a note is 4000 characters at most)
MAX_PLAYBOOK_BODY = 1 << 20   # a playbook save (the text is at most 256 KiB, JSON-escaped)
MAX_RELAY_BODY = 8 << 20      # one relay batch from a job (the relay sends about 1 MiB at a time)
APP_MARK = 'data-mode="panel"'


def loopback(address):
    """Whether a client address is this machine (127.0.0.0/8, ::1, or ::ffff:127.x)."""
    try:
        ip = ipaddress.ip_address(str(address).split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def card_info(db, code):
    card = db.get(code)
    if not card:
        return None
    info = {"id": card.id, "name": card.name, "type_line": card.type_line(), "text": card.text.strip(),
            "type": card.type, "atk": card.atk, "def": card.defense, "level": card.level & 0xFF,
            "alias": card.alias, "extra": card.is_extra}
    if card.is_monster:
        info["attribute"] = ATTRIBUTES.get(card.attribute)
        info["race"] = "/".join(RACES[i] for i in range(len(RACES)) if card.race & (1 << i))
    if card.has(0x1000000):
        info["scale"] = (card.level >> 24) & 0xFF
    return info


class Panel:
    """What the request handlers share."""

    def __init__(self, db, games_dir, edopro_dir, bus=BUS, fetch_pics=True, pics=None, host="127.0.0.1"):
        self.db = db
        self.bus = bus
        self.library = Library(games_dir)
        self.pics = pics or PicStore(edopro_dir, db=db, fetch=fetch_pics)
        self.host = host
        self.stopping = threading.Event()
        self.app = None  # web/app.py's App when `ygo-agent web` serves the app

    def feedback(self, body):
        text = str(body.get("text") or "").strip()[:4000]
        if not text:
            return 400, {"error": "empty note"}
        gid = str(body.get("game_id") or "")
        try:
            seat = int(body.get("seat") or 0)
            decision = int(body["decision"]) if body.get("decision") is not None else None
            turn = int(body["turn"]) if body.get("turn") is not None else None
        except (TypeError, ValueError, OverflowError):
            return 400, {"error": "seat, decision and turn must be numbers"}
        ack = self.bus.feedback(gid, seat, text, decision=decision, turn=turn)  # a live seat: like a !note
        if ack is not None:
            return 200, {"ok": True, "live": True, **ack}
        # A recorded game (or a demo of one, or a live game a job relays): straight into its folder's feedback.md.
        if gid.startswith("rec:"):
            folder = self.library.path(gid[4:])
        else:
            folder = self.bus.seat_info(gid, seat).get("dir")
            folder = folder if folder and os.path.isfile(os.path.join(folder, "game.jsonl")) else None
            if folder and decision is None:  # a live game: the note follows its newest decision, like a !note
                decision, turn = self.bus.last_decision(gid, seat)
        if not folder:
            return 404, {"error": "no game takes notes under that id"}
        ack = append_feedback(folder, text, decision=decision, turn=turn)
        if self.bus.has(gid):
            self.bus.publish({"type": "feedback_ack", "game_id": gid, "seat": seat, "text": text,
                              "context": ack["context"], "who": "Web panel"})
        return 200, {"ok": True, "live": False, "file": os.path.join(folder, "feedback.md"), **ack}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ygo-agent-panel"
    panel: Panel = None  # set per server class in start()

    def log_message(self, *args):
        pass

    # ---- helpers ----

    def send_bytes(self, data, ctype, status=200, cache="no-cache"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8",
                        status)

    def local_request(self):
        """Refuse other sites' pages (DNS rebinding, cross-site POSTs): bound to a local address only local names
        pass; bound to an interface, an IP literal, localhost or the bound hostname (a rebinding attack needs a
        DNS name of its own, which none of those are)."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        origin = self.headers.get("Origin")
        return self.host_ok(host) and (not origin or self.host_ok(urlparse(origin).hostname))

    def host_ok(self, name):
        if not name or name in LOCAL_HOSTS:
            return True
        if self.panel.host in LOCAL_HOSTS:
            return False
        if name == self.panel.host:
            return True
        try:
            ipaddress.ip_address(name.strip("[]"))
            return True
        except ValueError:
            return False

    # ---- routes ----

    def do_HEAD(self):
        self.do_GET()

    def app_route(self, path):
        """Whether `path` is one of the app's endpoints (they answer a client on this machine only)."""
        return path == "/api/app" or path == "/api/decks" or path == "/api/jobs" or path == "/api/relay" \
            or path.startswith("/api/decks/") or path.startswith("/api/jobs/")

    def app_gate(self, path):
        """None when the request may go on to the app, else the refusal sent."""
        if not loopback(self.client_address[0]):
            return self.send_json({"error": "only from this machine"}, 403)
        if self.panel.app is None:
            if path == "/api/app":
                return self.send_json({"app": False, "jobs": False})
            return self.send_json({"error": "jobs are off: this panel belongs to a play/selfplay/teach/coach run; "
                                            "`ygo-agent web` serves the app"}, 404)
        return None

    def do_GET(self):
        if not self.local_request():
            return self.send_json({"error": "forbidden"}, 403)
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        try:
            if path in ("/", "/index.html"):
                return self.static("index.html")
            if path.startswith("/static/"):
                return self.static(path[len("/static/"):])
            if path == "/stream":
                return self.stream((query.get("game") or [""])[0], query)
            if self.app_route(path):
                if self.app_gate(path) is None:
                    self.app_get(path, query)
                return
            if path == "/api/games":
                return self.send_json({"live": self.panel.bus.games(), "recorded": self.panel.library.list()})
            m = RECORDED.match(path)
            if m:
                msgs = self.panel.library.load(m.group(1), self.panel.db)
                if msgs is None:
                    return self.send_json({"error": "no such game"}, 404)
                return self.send_json({"name": m.group(1), "summary": self.panel.library.summary(m.group(1)),
                                       "messages": msgs})
            m = CARD.match(path)
            if m:
                data, ctype = self.panel.pics.get(int(m.group(1)))
                cache = "max-age=300" if ctype == "image/svg+xml" else "max-age=604800"
                return self.send_bytes(data, ctype, cache=cache)
            m = CARD_INFO.match(path)
            if m:
                info = card_info(self.panel.db, int(m.group(1)))
                return self.send_json(info) if info else self.send_json({"error": "unknown card"}, 404)
            return self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def app_get(self, path, query):
        app = self.panel.app
        if path == "/api/app":
            status, out = app.info()
        elif path == "/api/decks":
            status, out = app.decks()
        elif path == "/api/jobs":
            status, out = app.jobs()
        else:
            m = DECK.match(path)
            j = JOB.match(path)
            if m and not m.group(2):
                status, out = app.deck(m.group(1))
            elif j and not j.group(2):
                try:
                    offset = int((query.get("offset") or [""])[0]) if query.get("offset") else None
                except ValueError:
                    offset = None
                status, out = app.job(j.group(1), offset)
            else:
                status, out = 404, {"error": "not found"}
        self.send_json(out, status)

    def do_POST(self):
        if not self.local_request():
            return self.send_json({"error": "forbidden"}, 403)
        path = urlparse(self.path).path
        app = self.app_route(path)
        if not app and path != "/api/feedback":
            return self.send_json({"error": "not found"}, 404)
        if app and self.app_gate(path) is not None:
            self.close_connection = True
            return
        if "json" not in (self.headers.get("Content-Type") or ""):
            return self.send_json({"error": "send JSON"}, 415)
        limit = MAX_RELAY_BODY if path == "/api/relay" else MAX_PLAYBOOK_BODY if path.endswith("/playbook") \
            else MAX_BODY
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > limit:
            self.close_connection = True  # the body stays unread, so the connection can't carry another request
            if length < 0:
                return self.send_json({"error": "bad Content-Length"}, 400)
            return self.send_json({"error": "too long"}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json({"error": "bad JSON"}, 400)
        body = body if isinstance(body, dict) else {}
        if not app:
            status, out = self.panel.feedback(body)
        else:
            status, out = self.app_post(path, body)
        self.send_json(out, status)

    def app_post(self, path, body):
        app = self.panel.app
        if path == "/api/relay":
            return app.relay(self.headers.get("X-Relay-Token") or "", body)
        if path == "/api/jobs":
            return app.start_job(body)
        m, j = DECK.match(path), JOB.match(path)
        if m and m.group(2):
            return getattr(app, {"playbook": "save_playbook", "tips": "add_tip",
                                 "interview": "save_interview"}[m.group(2)])(m.group(1), body)
        if j and j.group(2):
            return (app.stop_job if j.group(2) == "stop" else app.go_job)(j.group(1))
        return 404, {"error": "not found"}

    def static(self, rel):
        full = os.path.realpath(os.path.join(STATIC, rel))
        if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
            return self.send_json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        if rel == "index.html" and self.panel.app is not None:
            data = data.replace(APP_MARK.encode(), b'data-mode="app"', 1)
        self.send_bytes(data, ctype)

    def stream(self, game_id, query):
        try:
            after = int(self.headers.get("Last-Event-ID") or (query.get("after") or ["0"])[0])
        except ValueError:
            after = 0
        backlog, sub = self.panel.bus.subscribe(game_id, after)
        self.close_connection = True
        self.connection.settimeout(STALL)  # a browser that stops reading (a lid closed) frees its thread
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.write(sse({"type": "games", "games": self.panel.bus.games()}, event_id=False))
            for msg in backlog:
                self.wfile.write(sse(msg))
            self.wfile.write(sse({"type": "caught_up", "game_id": game_id}, event_id=False))
            self.wfile.flush()
            while not self.panel.stopping.is_set() and not sub.overflow:
                msg = sub.get(timeout=HEARTBEAT)
                if msg is None:
                    self.wfile.write(b": ping\n\n")
                else:
                    self.wfile.write(sse(msg, event_id=msg.get("game_id") == game_id))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            sub.close()


class WebServer:
    def __init__(self, httpd, panel):
        self.httpd = httpd
        self.panel = panel
        host, port = httpd.server_address[:2]
        self.url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"
        self.thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True)

    def stop(self):
        self.panel.stopping.set()
        self.httpd.shutdown()
        self.httpd.server_close()


def start(cfg, db, bus=BUS, host=None, port=None, games_dir=None, pics=None, app=None):
    """Serve the panel in a background thread and switch the bus on. Returns the WebServer (`.url`, `.stop()`).
    `app`: serve the web app too (`ygo-agent web`): a dict of web/app.py App keywords (forward, jobs_dir, runner,
    windbots); the jobs' relay points at this server."""
    web = cfg.get("web", {})
    host = host or web.get("host", "127.0.0.1")
    port = web.get("port", 7930) if port is None else port
    games = paths.resolve(games_dir or cfg.get("games_dir", "games"))
    panel = Panel(db, games, cfg.get("edopro_dir", "~/Games/ProjectIgnis"), bus=bus,
                  fetch_pics=web.get("fetch_pics", True), pics=pics, host=host)
    handler = type("PanelHandler", (Handler,), {"panel": panel})
    try:
        httpd = ThreadingHTTPServer((host, port), handler)
    except OSError as e:
        reason = os.strerror(e.errno) if e.errno else str(e)
        raise OSError(f"can't serve the web panel on {host}:{port} ({reason}). Is another panel running? "
                      "Pick another port (--web-port; for `ygo-agent web`, --port).") from None
    httpd.daemon_threads = True
    bus.activate(Renderer(db))
    server = WebServer(httpd, panel)
    if app is not None:
        from .app import App
        panel.app = App(cfg, db, panel.library, bus, **app)
        panel.app.runner.relay_url = server.url
    server.thread.start()
    return server
