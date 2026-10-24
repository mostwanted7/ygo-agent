"""The TCP server the WindBot fork's BrainBridge connects to: newline-delimited JSON, one connection per match.

Each game of the match gets its own DuelBrain (and so its own log and history); see
docs/decision-protocol.md for the messages.
"""

import json
import os
import socket
import threading
import traceback

from .brain import DuelBrain
from .gamelog import paint, BOLD, RED


class Runtime:
    """What the launcher and the brain server share: the config, the deck, and what the current bot run is doing."""

    def __init__(self, cfg, db, profile):
        self.cfg = cfg
        self.db = db
        self.profile = profile
        self.duel_started = threading.Event()  # tells "never got into a duel" apart from a finished one
        self.windbot_log = None                # output file of the current bot run, linked from each game's folder


class Match:
    """One bot connection. A new game starts with its first decision or `start` event after the previous `win`."""

    def __init__(self, runtime, prewarm=True):
        self.runtime = runtime
        self.prewarm = prewarm
        self.room = None
        self.brain = None
        self.games = 0

    def new_brain(self):
        if self.brain:
            self.brain.close()
        rt = self.runtime
        self.brain = DuelBrain(rt.cfg, rt.db, rt.profile, prewarm=self.prewarm, runtime=rt, room=self.room)
        self.games += 1
        return self.brain

    def brain_for(self, msg):
        b = self.brain
        if msg.get("t") == "event" and msg.get("e") == "room":
            self.room = msg
            return b  # kept for the next games' logs; the current game (if any) records it too
        starts = msg.get("t") == "event" and msg.get("e") == "start"
        decides = msg.get("t") == "decide" and msg.get("kind") != "game_over"
        if b is None or (b.over and (starts or decides)) or (starts and b.started):
            return self.new_brain()
        return b

    def on_message(self, msg):
        """Returns the reply for a decision, or None for an event."""
        brain = self.brain_for(msg)
        if msg.get("t") == "event":
            if brain is not None:
                try:
                    brain.on_event(msg)
                except Exception:
                    print(paint(RED, "[brain] event handling failed:\n" + traceback.format_exc()))
            return None
        if msg.get("t") == "decide":
            try:
                return brain.on_decide(msg)
            except Exception:
                print(paint(RED, "[brain] decision failed, falling back:\n" + traceback.format_exc()))
                return {"id": msg.get("id"), "choice": None, "say": None}
        return None

    def close(self):
        if self.brain:
            self.brain.close()
            self.brain = None


def handle(conn, runtime):
    match = Match(runtime)
    reader = conn.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    writer = conn.makefile("w", encoding="utf-8", newline="\n")
    try:
        for line in reader:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            reply = match.on_message(msg)
            if reply is not None:
                writer.write(json.dumps(reply) + "\n")
                writer.flush()
    except (ConnectionError, OSError) as e:
        print(paint(RED, f"[brain] connection error: {e}"))
    finally:
        match.close()
        for f in (reader, writer, conn):  # the socket only really closes once its file objects are closed too
            try:
                f.close()
            except OSError:
                pass
        print(paint(BOLD, "[brain] bot disconnected."))


def listen(port, host="127.0.0.1"):
    """Bind the server socket now, so a busy port is reported before anything claims to be listening."""
    try:
        return socket.create_server((host, port), reuse_port=False)
    except OSError as e:
        reason = os.strerror(e.errno) if e.errno else str(e)
        raise OSError(f"can't listen on {host}:{port} ({reason}). Is another ygo-agent already running? "
                      "Stop it, or pick another port with --brain-port.") from None


def serve(srv, runtime):
    """Accept bot connections until the server socket is closed, one thread each, so a stale connection can never
    block the next duel."""
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return  # the socket was closed (shutdown): not an error
        threading.Thread(target=handle, args=(conn, runtime), daemon=True).start()


def start(runtime):
    """Bind the brain port and serve in a background thread. Returns the bound socket."""
    srv = listen(runtime.cfg["bot"]["brain_port"])
    threading.Thread(target=serve, args=(srv, runtime), daemon=True).start()
    return srv
