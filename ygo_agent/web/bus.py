"""In-process pub/sub between the agent's seats (the publishers) and the web panel's browsers (the subscribers).

A message is a JSON-able dict `{type, game_id, seat, ts, seq, ...}`; docs/web.md lists every type. Each game keeps a
backlog, so a browser that opens mid-game catches up, and several games and seats can publish at once. Publishing is
a no-op until a server activates the bus, so the agent can always publish without caring whether a panel is open.
"""

import collections
import json
import queue
import threading
import time

# Also sent to browsers that watch another game: they keep the game list up to date.
SUMMARY_TYPES = ("game_start", "meta", "game_end")
SEAT_FIELDS = ("deck", "deck_name", "mode", "opponent", "first", "rules", "dir", "name", "result", "source")


class Subscription:
    """One browser's stream: the messages of one game, plus every game's summary messages."""

    MAX_QUEUED = 20000  # a browser this far behind is dropped; it reconnects and resumes from the backlog

    def __init__(self, bus, game_id):
        self.bus = bus
        self.game_id = game_id
        self._queue = queue.SimpleQueue()
        self.overflow = False

    def offer(self, msg):
        if msg.get("game_id") == self.game_id or msg.get("type") in SUMMARY_TYPES:
            if self._queue.qsize() >= self.MAX_QUEUED:
                self.overflow = True
                return
            self._queue.put(msg)

    def get(self, timeout=None):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self.bus.unsubscribe(self)


class Game:
    def __init__(self, game_id, backlog):
        self.id = game_id
        self.backlog = collections.deque(maxlen=backlog)
        self.seq = 0
        self.seats = {}
        self.started = None
        self.updated = None
        self.ended = False
        self.decisions = 0
        self.turn = 0

    def note(self, msg):
        """Keep the game-list summary current."""
        kind, seat = msg.get("type"), msg.get("seat", 0)
        info = self.seats.setdefault(seat, {"seat": seat})
        self.started = self.started or msg["ts"]
        self.updated = msg["ts"]
        if kind in ("game_start", "meta"):
            info.update({k: msg[k] for k in SEAT_FIELDS if msg.get(k) is not None})
            if isinstance(msg.get("backend"), dict) and msg["backend"].get("label"):
                info["label"] = msg["backend"]["label"]
        elif kind == "decision":
            self.decisions += 1
            self.turn = max(self.turn, (msg.get("decision") or {}).get("state", {}).get("turn") or 0)
        elif kind == "game_end":
            info["result"] = msg.get("result")
        self.ended = all(s.get("result") for s in self.seats.values())

    def summary(self):
        seats = [self.seats[k] for k in sorted(self.seats)]
        decks = [s.get("deck_name") or s.get("deck") or f"seat {s['seat']}" for s in seats]
        if len(seats) == 1:
            title = f"{decks[0]} vs {seats[0].get('opponent') or '?'}"
        else:
            title = " vs ".join(decks)
        return {"game_id": self.id, "title": title, "seats": seats, "started": self.started,
                "updated": self.updated, "live": not self.ended, "decisions": self.decisions, "turn": self.turn}


class Bus:
    def __init__(self, max_games=16, max_backlog=50000):
        self.max_games = max_games
        self.max_backlog = max_backlog
        self.active = False
        self.renderer = None   # callable(msg) -> msg with display text added (the server sets it; it has the card db)
        self._lock = threading.Lock()
        self._games = collections.OrderedDict()
        self._subs = set()
        self._feedback = {}

    def activate(self, renderer=None):
        if renderer is not None:
            self.renderer = renderer
        self.active = True

    def reset(self):
        """Forget everything and stop publishing (tests)."""
        with self._lock:
            self._games.clear()
            self._subs.clear()
            self._feedback.clear()
        self.active = False
        self.renderer = None

    # ---- publishing ----

    def publish(self, msg):
        """Add a message to its game's backlog and pass it on to every subscriber. Returns it with its `seq`."""
        if not self.active:
            return None
        msg = {"seat": 0, **msg}
        msg.setdefault("ts", round(time.time(), 3))
        if self.renderer:
            try:
                msg = self.renderer(msg)
            except Exception as e:  # the panel must never break a duel
                msg["render_error"] = str(e)
        with self._lock:
            game = self._games.get(msg["game_id"])
            if game is None:
                game = self._games[msg["game_id"]] = Game(msg["game_id"], self.max_backlog)
                self._evict()
            game.seq += 1
            msg["seq"] = game.seq
            game.backlog.append(msg)
            game.note(msg)
            subs = list(self._subs)
        for sub in subs:
            sub.offer(msg)
        return msg

    def _evict(self):
        while len(self._games) > self.max_games:
            victim = next((g for g in self._games.values() if g.ended), None) or next(iter(self._games.values()))
            del self._games[victim.id]
            for key in [k for k in self._feedback if k[0] == victim.id]:
                del self._feedback[key]

    # ---- subscribing ----

    def subscribe(self, game_id, after=0):
        """(backlog after `after`, subscription), taken together so that nothing is missed or sent twice."""
        sub = Subscription(self, game_id)
        with self._lock:
            game = self._games.get(game_id)
            backlog = [m for m in game.backlog if m["seq"] > after] if game else []
            self._subs.add(sub)
        return backlog, sub

    def unsubscribe(self, sub):
        with self._lock:
            self._subs.discard(sub)

    def backlog(self, game_id, after=0):
        with self._lock:
            game = self._games.get(game_id)
            return [m for m in game.backlog if m["seq"] > after] if game else []

    def games(self):
        """Summaries of the games on the bus, newest first."""
        with self._lock:
            out = [g.summary() for g in self._games.values()]
        return sorted(out, key=lambda g: g["started"] or 0, reverse=True)

    def has(self, game_id):
        with self._lock:
            return game_id in self._games

    def seat_info(self, game_id, seat):
        with self._lock:
            game = self._games.get(game_id)
            return dict(game.seats.get(seat, {})) if game else {}

    # ---- feedback from the panel ----

    def on_feedback(self, game_id, seat, handler):
        """handler(text, decision=None, turn=None) -> {"n", "context"}: saves a note like a `!note` from the chat."""
        with self._lock:
            self._feedback[(game_id, seat)] = handler

    def feedback(self, game_id, seat, text, decision=None, turn=None):
        """Route a note to the seat that owns it. None when no live seat takes notes for that game."""
        with self._lock:
            handler = self._feedback.get((game_id, seat))
        if handler is None:
            return None
        return handler(text, decision=decision, turn=turn)


BUS = Bus()


class Channel:
    """One seat of one game, as its publisher sees it (each GameLog has one). Sends nothing while the bus is off."""

    def __init__(self, game_id, seat=0, enabled=True, bus=None):
        self.game_id = game_id
        self.seat = seat
        self.enabled = enabled
        self.bus = bus or BUS

    @property
    def live(self):
        return self.enabled and self.bus.active

    def send(self, type_, **fields):
        if not self.live:
            return None
        try:
            # A deep copy: the publisher keeps changing its own dicts (the brain fills in a decision's state after
            # logging it) while browser threads serialize this one.
            fields = json.loads(json.dumps(fields))
            return self.bus.publish({"type": type_, "game_id": self.game_id, "seat": self.seat, **fields})
        except Exception:
            return None

    def on_feedback(self, handler):
        if self.live:
            self.bus.on_feedback(self.game_id, self.seat, handler)


def sse(msg, event_id=True):
    """One Server-Sent Events frame. The id (the game's seq) lets a reconnecting browser resume where it left off."""
    lines = []
    if event_id and msg.get("seq"):
        lines.append(f"id: {msg['seq']}")
    data = json.dumps(msg, separators=(",", ":"), ensure_ascii=False)
    lines += [f"data: {line}" for line in data.split("\n")]
    return ("\n".join(lines) + "\n\n").encode("utf-8")
