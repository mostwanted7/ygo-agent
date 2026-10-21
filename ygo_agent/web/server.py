"""The web panel's HTTP server (stdlib only): static files, Server-Sent Events from the bus, card pictures and texts,
recorded games, and the feedback box. It binds 127.0.0.1 by default: it serves your game logs and writes notes.

    GET  /                      the panel (static/index.html)
    GET  /stream?game=ID        SSE: the game list, then game ID's backlog and live messages (Last-Event-ID resumes)
    GET  /api/games             {"live": [...], "recorded": [...]}
    GET  /api/recorded/NAME     a recorded game as bus messages
    GET  /card/CODE.jpg         a card picture (EDOPro's pics, the download cache, a download, or a placeholder)
    GET  /cardinfo/CODE         the card's name, type line and text
    POST /api/feedback          {"game_id", "seat", "text", "decision"?, "turn"?} -> saved like a `!note`
"""

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
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")
HEARTBEAT = 15


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

    def feedback(self, body):
        text = str(body.get("text") or "").strip()[:4000]
        if not text:
            return 400, {"error": "empty note"}
        gid = str(body.get("game_id") or "")
        try:
            seat = int(body.get("seat") or 0)
            decision = int(body["decision"]) if body.get("decision") is not None else None
            turn = int(body["turn"]) if body.get("turn") is not None else None
        except (TypeError, ValueError):
            return 400, {"error": "seat, decision and turn must be numbers"}
        ack = self.bus.feedback(gid, seat, text, decision=decision, turn=turn)  # a live seat: like a !note
        if ack is not None:
            return 200, {"ok": True, "live": True, **ack}
        # A recorded game (or a demo of one): straight into its folder's feedback.md.
        if gid.startswith("rec:"):
            folder = self.library.path(gid[4:])
        else:
            folder = self.bus.seat_info(gid, seat).get("dir")
            folder = folder if folder and os.path.isfile(os.path.join(folder, "game.jsonl")) else None
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
        """Refuse other sites' pages (DNS rebinding, cross-site POSTs) when the panel is bound to a local address."""
        if self.panel.host not in LOCAL_HOSTS:
            return True
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host and host not in LOCAL_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            return False
        return True

    # ---- routes ----

    def do_HEAD(self):
        self.do_GET()

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

    def do_POST(self):
        if not self.local_request():
            return self.send_json({"error": "forbidden"}, 403)
        if urlparse(self.path).path != "/api/feedback":
            return self.send_json({"error": "not found"}, 404)
        if "json" not in (self.headers.get("Content-Type") or ""):
            return self.send_json({"error": "send JSON"}, 415)
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 65536)) or b"{}")
        except ValueError:
            return self.send_json({"error": "bad JSON"}, 400)
        status, out = self.panel.feedback(body if isinstance(body, dict) else {})
        self.send_json(out, status)

    def static(self, rel):
        full = os.path.realpath(os.path.join(STATIC, rel))
        if not full.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(full):
            return self.send_json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self.send_bytes(f.read(), ctype)

    def stream(self, game_id, query):
        try:
            after = int(self.headers.get("Last-Event-ID") or (query.get("after") or ["0"])[0])
        except ValueError:
            after = 0
        backlog, sub = self.panel.bus.subscribe(game_id, after)
        self.close_connection = True
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


def start(cfg, db, bus=BUS, host=None, port=None, games_dir=None, pics=None):
    """Serve the panel in a background thread and switch the bus on. Returns the WebServer (`.url`, `.stop()`)."""
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
                      "Pick another port with --web-port.") from None
    httpd.daemon_threads = True
    bus.activate(Renderer(db))
    server = WebServer(httpd, panel)
    server.thread.start()
    return server
