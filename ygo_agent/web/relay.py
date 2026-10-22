"""The relay: how a command the web app started (a job, web/jobs.py) shows its games in the app.

The app starts every job with YGO_AGENT_RELAY (the app's URL) and YGO_AGENT_RELAY_TOKEN (that job's own token) in its
environment. `install()`, which the CLI calls once, then switches this process's bus on with the usual renderer (so
messages leave rendered, exactly as a panel here would show them) and a sink that batches them to the app's
`POST /api/relay` from a background thread. The app injects them into its own bus as they are. When the app is gone
the batches are dropped: a job never waits for the app. Every GameLog publishes through the bus, so play, selfplay,
teach, coach and the trainer's lab hands and games all show up live in the app.

Where a terminal would wait for Enter (the room you host is open; start without a spectator), a job tells the app
what it waits for (`wait_go`), and the app's button creates the file named by YGO_AGENT_GO_FILE.
"""

from __future__ import annotations

import atexit
import collections
import json
import os
import threading
import time
import urllib.request

from .bus import BUS

ENV_URL = "YGO_AGENT_RELAY"
ENV_TOKEN = "YGO_AGENT_RELAY_TOKEN"
ENV_GO = "YGO_AGENT_GO_FILE"
BATCH_BYTES = 1 << 20     # one POST carries about this much (the app takes up to 8 MiB)
MAX_QUEUED = 50000        # messages; past that the oldest are dropped (the app stalled)
RETRY_AFTER = 2.0         # seconds without posting after a failed POST (the app is gone or busy)

_relay = None


class LazyRenderer:
    """The bus renderer, built from the card database on first use: a job that never plays a game never loads it,
    and a command that loads the database anyway hands it over (`share_db`)."""

    def __init__(self, edopro_dir):
        self.edopro_dir = edopro_dir
        self._renderer = None
        self._lock = threading.Lock()

    def share(self, db):
        with self._lock:
            if self._renderer is None:
                from .render import Renderer
                self._renderer = Renderer(db)

    def __call__(self, msg):
        if self._renderer is None:
            with self._lock:
                if self._renderer is None:
                    from ..agent.carddb import CardDB
                    from .render import Renderer
                    self._renderer = Renderer(CardDB(self.edopro_dir))
        return self._renderer(msg)


class Relay:
    """Batches bus messages (and the job's waiting state) to the app's /api/relay from one daemon thread."""

    def __init__(self, url, token, timeout=10.0):
        self.url = url.rstrip("/") + "/"
        self.endpoint = self.url + "api/relay"
        self.token = token
        self.timeout = timeout
        self.renderer = None
        self._queue = collections.deque()
        self._cv = threading.Condition()
        self._waiting = None
        self._waiting_dirty = False
        self._busy = False
        self._quiet_until = 0.0
        self.sent = self.dropped = 0
        # No proxy: the app is on this machine, and an http_proxy variable must not route the games elsewhere.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._thread = threading.Thread(target=self._run, daemon=True, name="web-relay")
        self._thread.start()

    def __call__(self, msg):
        """The bus sink: queue and return at once."""
        with self._cv:
            self._queue.append(msg)
            while len(self._queue) > MAX_QUEUED:
                self._queue.popleft()
                self.dropped += 1
            self._cv.notify()

    def set_waiting(self, waiting):
        with self._cv:
            self._waiting = waiting
            self._waiting_dirty = True
            self._cv.notify()

    def flush(self, timeout=3.0):
        """Wait (up to `timeout`) until everything queued has been posted or dropped: at exit, so the game's end
        reaches the app."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while (self._queue or self._waiting_dirty or self._busy) and time.monotonic() < deadline:
                self._cv.wait(0.05)

    def _take(self):
        """The next batch, about BATCH_BYTES of messages; None when there is nothing to send."""
        batch, size = [], 0
        while self._queue and size < BATCH_BYTES:
            msg = self._queue.popleft()
            try:
                data = json.dumps(msg, ensure_ascii=False)
            except (TypeError, ValueError):
                self.dropped += 1
                continue
            batch.append(data)
            size += len(data)
        status = self._waiting_dirty
        self._waiting_dirty = False
        if not batch and not status:
            return None
        body = '{"messages": [' + ",".join(batch) + "]"
        if status:
            body += ', "waiting": ' + json.dumps(self._waiting, ensure_ascii=False)
        return (body + "}").encode("utf-8")

    def _run(self):
        while True:
            with self._cv:
                while not self._queue and not self._waiting_dirty:
                    self._busy = False
                    self._cv.notify_all()
                    self._cv.wait()
                self._busy = True
            if len(self._queue) < 50:
                time.sleep(0.05)  # a burst of events becomes one POST
            with self._cv:
                body = self._take()
                if time.monotonic() < self._quiet_until:
                    self.dropped += 1 if body else 0
                    body = None
            if body is not None:
                self._post(body)

    def _post(self, body):
        req = urllib.request.Request(self.endpoint, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-Relay-Token": self.token})
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                r.read()
            self.sent += 1
        except Exception:  # the app is gone, restarted or refused the batch: drop it and carry on
            self.dropped += 1
            self._quiet_until = time.monotonic() + RETRY_AFTER


class Stub:
    """What ensure_panel() returns in a job: the app is the panel."""

    def __init__(self, url):
        self.url = url
        self.panel = None

    def stop(self):
        pass


def install(cfg, bus=BUS, env=None):
    """Switch the bus on with a relay to the app, when this process is a web-app job. Returns the Relay or None."""
    global _relay
    env = os.environ if env is None else env
    url, token = env.get(ENV_URL), env.get(ENV_TOKEN)
    if not url or not token:
        return None
    if _relay is not None:
        return _relay
    relay = Relay(url, token)
    relay.renderer = LazyRenderer(cfg.get("edopro_dir", "~/Games/ProjectIgnis"))
    bus.activate(relay.renderer)
    bus.add_sink(relay)
    atexit.register(relay.flush)
    _relay = relay
    return relay


def active():
    return _relay is not None


def url():
    return _relay.url if _relay else None


def share_db(db):
    """Hand the command's card database to the renderer (else it loads its own on the first message)."""
    if _relay is not None and _relay.renderer is not None and db is not None and getattr(db, "cards", None):
        _relay.renderer.share(db)


def waiting(text, button=None):
    """Tell the app what this job waits for (None: nothing any more). The app shows it with a button."""
    if _relay is not None:
        _relay.set_waiting({"text": str(text)[:300], "button": str(button or "Continue")[:60]} if text else None)


def go_requested():
    """True once the app's user pressed the button (the go file is consumed)."""
    path = os.environ.get(ENV_GO)
    if not path or not os.path.exists(path):
        return False
    try:
        os.remove(path)
    except OSError:
        pass
    return True


def wait_go(prompt, button="Continue"):
    """The web app's version of input(prompt) for Enter: wait until the app's button is pressed. Ctrl+C (the job's
    Stop) interrupts it as it would input()."""
    print(prompt + f"(in the web app: \"{button}\")", flush=True)
    waiting(prompt.strip().rstrip("."), button)
    try:
        while not go_requested():
            time.sleep(0.25)
    finally:
        waiting(None)
    return ""
