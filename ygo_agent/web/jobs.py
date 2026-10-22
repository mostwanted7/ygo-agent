"""Jobs: the CLI commands the web app runs for you (`ygo-agent web`; docs/web.md, "The app").

A job is one `python -m ygo_agent <argv>` subprocess, started in the repo with stdin closed, in its own process
group, its output in ~/.cache/ygo-agent/web-jobs/<id>.log. The argv is built here from validated parameters only:
every flag comes from this file, decks resolve through decks.find, backends must be config profiles, WindBot deck AIs
come from the legal list, numbers are range-checked and a .ydk path must be an existing .ydk file. Never a shell,
never free-form arguments.

Each job reaches the app's bus through the relay (web/relay.py): its own token in the environment, so the app knows
which job a live game belongs to. Stop is Ctrl+C for the whole process group (the trainer checkpoints, a room closes
and prints its results), then SIGTERM after 20 s and SIGKILL after 5 more; afterwards whatever is left of the job (a
WindBot in its own session, say) is found by the token in its environment and killed. Jobs that host a room (play,
teach, coach, selfplay with a spectator, play --join's bot) share the room port, so one runs at a time; training
and learning take their deck, so one runs per deck.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

from .. import decks, paths
from .relay import ENV_GO, ENV_TOKEN, ENV_URL

KINDS = ("play", "selfplay", "teach", "coach", "train-interview", "train", "learn", "doctor")
DECK_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
HOST = re.compile(r"^[A-Za-z0-9.:-]{1,253}$")
JOB_ID = re.compile(r"^[\w.-]{1,80}$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
LEVELS = ("beginner", "intermediate")
STOP_STEPS = ((signal.SIGINT, 20.0), (signal.SIGTERM, 5.0), (signal.SIGKILL, 5.0))
KEEP_JOBS = 200       # job files kept in the jobs folder (older ones are deleted)
CHUNK = 256 * 1024    # output bytes per request
TAIL = 64 * 1024      # what a page that opens a long log starts with


class JobError(Exception):
    """A request the app refuses: bad parameters (400), or a room/deck already in use (409)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def default_dir():
    return os.path.join(paths.CACHE, "web-jobs")


# ---- parameters → argv ---------------------------------------------------------------------------------------------

@dataclass
class Plan:
    kind: str
    argv: list           # after `ygo-agent`
    title: str
    room: dict | None = None   # how to join (host/port/password/spectator), when the job needs the room port
    deck: str | None = None    # the deck it works on
    deck_lock: bool = False    # train/learn: one job per deck


class Builder:
    """Turns a job's parameters into its argv. `windbots`: the WindBot deck AIs legal under the rules (names);
    `forward`: the app's own --config/--edopro-dir/--games-dir, passed on to the commands that take them."""

    def __init__(self, cfg, windbots=(), forward=None, join_available=None):
        self.cfg = cfg
        self.windbots = None if windbots is None else list(windbots)  # None: the app fills it in on first use
        self.forward = {k: v for k, v in (forward or {}).items() if v}
        self.join_available = os.path.isfile(paths.WINDBOT_EXE) if join_available is None else join_available

    def build(self, kind, params) -> Plan:
        if kind not in KINDS:
            raise JobError(f"unknown job kind {kind!r}; one of {', '.join(KINDS)}")
        if not isinstance(params, dict):
            raise JobError("params must be an object")
        return getattr(self, "build_" + kind.replace("-", "_"))(params)

    # ---- values ----

    def deck(self, value, what="deck"):
        if not isinstance(value, str) or not DECK_NAME.match(value.strip()):
            raise JobError(f"{what}: give a deck's name (letters, digits, - and _)")
        try:
            return decks.find(value.strip(), self.cfg).key
        except decks.DeckError as e:
            raise JobError(f"{what}: {e}") from None

    def backend(self, value, what="backend", default=None):
        name = value if value not in (None, "") else default if default is not None else self.cfg["agent"]["backend"]
        profiles = self.cfg.get("backends") or {}
        if not isinstance(name, str) or name not in profiles or not isinstance(profiles[name], dict):
            raise JobError(f"{what}: {name!r} is not a backend profile ({', '.join(profiles)})")
        return name

    def number(self, params, key, lo, hi, default=None, kind=int):
        value = params.get(key)
        if value in (None, ""):
            return default
        if isinstance(value, bool):
            raise JobError(f"{key} must be a number")
        try:
            number = kind(value) if kind is float else int(str(value).strip())
        except (TypeError, ValueError):
            raise JobError(f"{key} must be a{'n integer' if kind is int else ' number'}") from None
        if kind is float and not math.isfinite(number):
            raise JobError(f"{key} must be a number")
        if not lo <= number <= hi:
            raise JobError(f"{key} must be between {lo:g} and {hi:g}")
        return number

    def text(self, params, key, limit, default=None):
        value = params.get(key)
        if value in (None, ""):
            return default
        if not isinstance(value, str) or CONTROL.search(value) or len(value) > limit:
            raise JobError(f"{key}: up to {limit} characters, no control characters")
        return value.strip() or default

    def flag(self, params, key):
        value = params.get(key, False)
        if not isinstance(value, bool):
            raise JobError(f"{key} must be true or false")
        return value

    def windbot(self, name, what):
        if not isinstance(name, str) or not name.strip():
            raise JobError(f"{what}: name a WindBot deck AI")
        for bot in self.windbots or ():
            if bot.lower() == name.strip().lower():
                return bot
        legal = ", ".join(self.windbots or ()) or "none here (WindBot needs mono and EDOPro's WindBot)"
        raise JobError(f"{what}: {name!r} is not a WindBot deck AI legal under {self.cfg['duel']['rules']} ({legal})")

    def seat(self, value, what):
        """{"kind": "agent", "deck", "backend"} or {"kind": "windbot", "name"} → a seat spec (match.SeatSpec)."""
        if not isinstance(value, dict):
            raise JobError(f"{what}: give the seat as an object")
        kind = value.get("kind") or "agent"
        if kind == "windbot":
            return "windbot:" + self.windbot(value.get("name"), what)
        if kind != "agent":
            raise JobError(f"{what}: kind must be agent or windbot")
        return f"{self.deck(value.get('deck'), what)}:{self.backend(value.get('backend'), what)}"

    def ydk(self, value):
        if not isinstance(value, str) or not value.strip() or CONTROL.search(value):
            raise JobError("ydk: give the path of a .ydk file")
        path = os.path.realpath(os.path.expanduser(value.strip()))
        if not path.lower().endswith(".ydk") or not os.path.isfile(path):
            raise JobError(f"ydk: {value.strip()} is not a .ydk file")
        return path

    def room(self, params, spectator, kind="host"):
        port = self.number(params, "port", 1024, 65535)
        password = self.text(params, "password", 20, "")
        return port, password, {"kind": kind, "host": "127.0.0.1", "spectator": spectator, "password": password,
                                "port": port or self.cfg["room"]["port"],
                                "name": self.cfg.get("arena", {}).get("room_name", "ygo-agent")}

    def common(self, *keys):
        flags = {"config": "--config", "edopro_dir": "--edopro-dir", "games_dir": "--games-dir"}
        return [f"{flags[k]}={self.forward[k]}" for k in keys if k in self.forward]

    def room_flags(self, port, password):
        return ([f"--port={port}"] if port else []) + ([f"--password={password}"] if password else [])

    # ---- kinds ----

    def build_play(self, p):
        deck = self.deck(p.get("deck") or self.cfg["deck"])
        backend = self.backend(p.get("backend"))
        if self.flag(p, "join"):
            if not self.join_available:
                raise JobError("play --join needs the WindBot fork: run ./build.sh first")
            host = self.text(p, "host", 253)
            if host and not HOST.match(host):
                raise JobError("host: a host name or IP address")
            port, password, room = self.room(p, spectator=False, kind="join")
            room["host"] = host or self.cfg["room"].get("host", "127.0.0.1")
            argv = ["play", "--join", f"--deck={deck}", f"--backend={backend}"] + (
                [f"--host={host}"] if host else []) + self.room_flags(port, password)
            title = f"Duel {deck} ({backend}) in your EDOPro room"
        else:
            best_of = self.number(p, "best_of", 1, 5, 1)
            if best_of not in (1, 3, 5):
                raise JobError("best_of must be 1, 3 or 5")
            games = self.number(p, "games", 1, 99)
            limit = self.number(p, "time_limit", 0, 7200)
            port, password, room = self.room(p, spectator=False)
            argv = ["play", f"--deck={deck}", f"--backend={backend}", f"--best-of={best_of}"] + (
                [f"--games={games}"] if games else []) + (
                [f"--time-limit={limit}"] if limit is not None else []) + self.room_flags(port, password)
            title = f"Duel {deck} ({backend})" + (f", best of {best_of}" if best_of > 1 else "")
        return Plan("play", argv + ["--no-web"] + self.common("config", "edopro_dir", "games_dir"), title, room, deck)

    def build_selfplay(self, p):
        a, b = self.seat(p.get("a"), "seat A"), self.seat(p.get("b"), "seat B")
        games = self.number(p, "games", 1, 50, 1)
        best_of = self.number(p, "best_of", 1, 5, 1)
        if best_of not in (1, 3, 5):
            raise JobError("best_of must be 1, 3 or 5")
        pace = self.number(p, "pace", 0, 30, None, float)
        spectate = self.flag(p, "spectate")
        parallel = self.number(p, "parallel", 1, 4, 1)
        if spectate and parallel > 1:
            raise JobError("parallel games can't have a spectator")
        argv = ["selfplay", f"--a={a}", f"--b={b}", f"--games={games}", f"--best-of={best_of}"]
        argv += [f"--pace={pace:g}"] if pace else []
        argv += [f"--parallel={parallel}"] if parallel > 1 else []
        room = None
        if spectate:
            port, password, room = self.room(p, spectator=True)
            argv += ["--spectate"] + self.room_flags(port, password)
        title = f"AI vs AI: {seat_title(a)} vs {seat_title(b)}" + (f", {games} matches" if games > 1 else "")
        return Plan("selfplay", argv + ["--no-web"] + self.common("config", "edopro_dir", "games_dir"), title, room)

    def build_teach(self, p):
        deck = self.deck(p.get("deck") or self.cfg["deck"])
        backend = self.backend(p.get("backend"))
        opponent = self.seat(p.get("opponent") or {"kind": "windbot", "name": "Blue-Eyes"}, "opponent")
        games = self.number(p, "games", 1, 20, 1)
        pace = self.number(p, "pace", 0, 30, None, float)
        port, password, room = self.room(p, spectator=True)
        argv = ["teach", f"--deck={deck}", f"--backend={backend}", f"--opponent={opponent}", f"--games={games}"]
        argv += ([f"--pace={pace:g}"] if pace else []) + self.room_flags(port, password)
        return Plan("teach", argv + ["--no-web"] + self.common("config", "edopro_dir", "games_dir"),
                    f"{deck} ({backend}) teaches against {seat_title(opponent)}", room, deck)

    def build_coach(self, p):
        deck = self.deck(p["deck"]) if p.get("deck") else None
        backend = self.backend(p.get("backend"))
        coach = self.cfg.get("coach", {})
        opponent = self.seat(p.get("opponent") or {"kind": "windbot", "name": "Blue-Eyes"}, "opponent")
        level = p.get("level") or coach.get("level", "beginner")
        if level not in LEVELS:
            raise JobError(f"level must be one of {', '.join(LEVELS)}")
        games = self.number(p, "games", 1, 99)
        best_of = self.number(p, "best_of", 1, 5, 1)
        if best_of not in (1, 3, 5):
            raise JobError("best_of must be 1, 3 or 5")
        limit = self.number(p, "time_limit", 0, 7200)
        port, password, room = self.room(p, spectator=False)
        argv = ["coach"] + ([f"--deck={deck}"] if deck else []) + [
            f"--backend={backend}", f"--opponent={opponent}", f"--level={level}", f"--best-of={best_of}"]
        argv += ([f"--games={games}"] if games else []) + ([f"--time-limit={limit}"] if limit is not None else [])
        argv += self.room_flags(port, password)
        return Plan("coach", argv + ["--no-web"] + self.common("config", "edopro_dir", "games_dir"),
                    f"Coaching {deck or 'your deck'} ({backend}) against {seat_title(opponent)}", room, deck)

    def new_deck_name(self, value):
        if not isinstance(value, str) or not DECK_NAME.match(value.strip()):
            raise JobError("name: 1-40 letters, digits, - and _ (it becomes the deck's folder)")
        name = value.strip()
        try:
            decks.target(name, "user", self.cfg)  # a deck by that name in decks/ would clash with it
        except decks.DeckError as e:
            raise JobError(f"name: {e}") from None
        return name

    def build_train_interview(self, p):
        ydk = self.ydk(p.get("ydk"))
        name = self.new_deck_name(p.get("name"))
        display = self.text(p, "display_name", 60)
        argv = ["train", ydk, f"--name={name}"] + ([f"--display-name={display}"] if display else [])
        return Plan("train-interview", argv + ["--interview-only"] + self.common("config", "edopro_dir"),
                    f"Read the deck {name}", deck=name, deck_lock=True)

    def build_train(self, p):
        name = self.new_deck_name(p.get("name"))
        if not training_dir(name, self.cfg):
            raise JobError(f"no training started for {name!r}: read the deck first (the interview)")
        trainer = self.cfg.get("trainer", {})
        argv = ["train", f"--name={name}", "--resume", "--no-interview"]
        if p.get("backend"):
            argv.append(f"--backend={self.backend(p['backend'], 'reviewer', trainer.get('backend'))}")
        if p.get("player_backend"):
            argv.append(f"--player-backend={self.backend(p['player_backend'], 'player')}")
        for key, flag, lo, hi in (("games", "--games", 0, 10), ("lab_hands", "--lab-hands", 0, 30),
                                  ("max_rounds", "--max-rounds", 1, 5)):
            value = self.number(p, key, lo, hi)
            if value is not None:
                argv.append(f"{flag}={value}")
        budget = self.number(p, "budget_usd", 0.5, 500, None, float)
        if budget is not None:
            argv.append(f"--budget-usd={budget:g}")
        return Plan("train", argv + self.common("config", "edopro_dir"), f"Train {name}", deck=name, deck_lock=True)

    def build_learn(self, p):
        deck = self.deck(p.get("deck"))
        argv = ["learn", f"--deck={deck}"]
        if p.get("backend"):
            argv.append(f"--backend={self.backend(p['backend'])}")
        budget = self.number(p, "budget_usd", 0.5, 200, None, float)
        if budget is not None:
            argv.append(f"--budget-usd={budget:g}")
        return Plan("learn", argv + self.common("config", "edopro_dir", "games_dir"), f"Learn from the notes on {deck}",
                    deck=deck, deck_lock=True)

    def build_doctor(self, p):
        return Plan("doctor", ["doctor", "--json"] + self.common("config", "edopro_dir"), "Check the setup")


def seat_title(spec):
    """"geargia:heuristic" → "geargia (heuristic)", "windbot:Blue-Eyes" → "WindBot Blue-Eyes"."""
    head, _, tail = spec.partition(":")
    return f"WindBot {tail}" if head == "windbot" else f"{head} ({tail})"


def training_dir(name, cfg):
    """The deck folder a training run for `name` uses (the user decks dir first, then decks/), or None."""
    for location in ("user", "repo"):
        folder = os.path.join(decks.root_dir(location, cfg), name)
        if os.path.isdir(os.path.join(folder, "train")):
            return folder
    return None


def display_command(argv):
    """The equivalent terminal command (the room password masked)."""
    return "ygo-agent " + " ".join("--password=•••" if a.startswith("--password=") else shlex.quote(a) for a in argv)


# ---- the runner ----------------------------------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    kind: str
    title: str
    params: dict
    argv: list
    log: str
    room: dict | None = None
    deck: str | None = None
    deck_lock: bool = False
    status: str = "starting"   # starting, running, stopping, done, failed, stopped
    code: int | None = None
    started: float = 0.0
    ended: float | None = None
    pid: int | None = None
    error: str | None = None
    games: list = field(default_factory=list)   # [{"game_id", "seat", "dir", "name", "ended"}] learned from the relay
    waiting: dict | None = None                 # {"text", "button"} while the job waits for the app's button
    token: str = field(default="", repr=False)
    proc: object = field(default=None, repr=False)
    stop_requested: bool = False

    @property
    def running(self):
        return self.status in ("starting", "running", "stopping")

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "title": self.title, "params": self.params, "argv": self.argv,
                "command": display_command(self.argv), "status": self.status, "code": self.code,
                "running": self.running, "started": self.started, "ended": self.ended, "pid": self.pid,
                "log": self.log, "room": self.room, "deck": self.deck, "games": list(self.games),
                "waiting": self.waiting, "error": self.error}

    def record(self):
        """What is saved next to the log (no token, no process)."""
        return {k: v for k, v in self.to_dict().items() if k not in ("running", "command")}


def port_free(port):
    """Whether a room could listen on `port` (the arena binds every interface for rooms a human joins)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def processes_with(token):
    """PIDs of this user's processes whose environment holds the job's relay token (what a job leaves behind)."""
    needle = f"{ENV_TOKEN}={token}".encode()
    out = []
    try:
        names = os.listdir("/proc")
    except OSError:
        return out
    for name in names:
        if not name.isdigit() or int(name) == os.getpid():
            continue
        try:
            with open(f"/proc/{name}/environ", "rb") as f:
                if needle in f.read().split(b"\0"):
                    out.append(int(name))
        except OSError:
            continue
    return out


class JobRunner:
    def __init__(self, builder, jobs_dir=None, relay_url=None, prefix=None, cwd=None, on_change=None):
        self.builder = builder
        self.dir = jobs_dir or default_dir()
        os.makedirs(self.dir, mode=0o700, exist_ok=True)  # logs can hold a room password, records a live token
        self.relay_url = relay_url
        self.prefix = list(prefix or [sys.executable, "-m", "ygo_agent"])
        self.cwd = cwd or paths.ROOT
        self.on_change = on_change
        self.stop_steps = STOP_STEPS
        self._lock = threading.RLock()
        self._jobs = {}
        self._load()

    # ---- the record ----

    def _load(self):
        """Earlier jobs from the folder, newest last. One still marked running belongs to an app that is gone: its
        processes are stopped (found by their token; Ctrl+C first, in the background)."""
        orphans = []
        files = sorted((f for f in os.listdir(self.dir) if f.endswith(".json")), reverse=True)
        for stale in files[KEEP_JOBS:]:
            for ext in (".json", ".log"):
                try:
                    os.remove(os.path.join(self.dir, stale[:-5] + ext))
                except OSError:
                    pass
        for name in reversed(files[:KEEP_JOBS]):
            try:
                with open(os.path.join(self.dir, name), encoding="utf-8") as f:
                    data = json.load(f)
                job = Job(**{k: data.get(k) for k in ("id", "kind", "title", "params", "argv", "log")},
                          room=data.get("room"), deck=data.get("deck"), status=data.get("status") or "done",
                          code=data.get("code"), started=data.get("started") or 0, ended=data.get("ended"),
                          pid=data.get("pid"), error=data.get("error"), games=data.get("games") or [])
                token = data.get("token")
            except (OSError, ValueError, TypeError):
                continue
            if job.running:
                if token:
                    orphans.append(token)
                job.status, job.error = "stopped", job.error or "the app stopped before the job ended"
                job.ended = job.ended or time.time()
                self._save(job)
            job.waiting = None
            self._jobs[job.id] = job
        if orphans:
            threading.Thread(target=self._stop_orphans, args=(orphans,), daemon=True, name="job-orphans").start()

    def _stop_orphans(self, tokens):
        for sig, wait in self.stop_steps:
            left = [pid for token in tokens for pid in processes_with(token)]
            if not left:
                return
            for pid in left:
                _kill(pid, sig)
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline and any(processes_with(t) for t in tokens):
                time.sleep(0.2)

    def _save(self, job):
        data = job.record()
        if job.running:
            data["token"] = job.token  # so a restarted app can find what a crashed one left running
        tmp = os.path.join(self.dir, job.id + ".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            os.replace(tmp, os.path.join(self.dir, job.id + ".json"))
        except OSError:
            pass

    def _changed(self, job):
        self._save(job)
        if self.on_change:
            try:
                self.on_change(job)
            except Exception:
                pass

    def new_id(self, kind):
        stem = time.strftime("%Y%m%d-%H%M%S") + "-" + kind
        with self._lock:
            n, name = 1, stem
            while name in self._jobs or os.path.exists(os.path.join(self.dir, name + ".log")):
                n += 1
                name = f"{stem}-{n}"
            return name

    # ---- queries ----

    def get(self, job_id):
        if not isinstance(job_id, str) or not JOB_ID.match(job_id):
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def list(self):
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda j: (not j.running, -(j.started or 0)))

    def running(self):
        return [j for j in self.list() if j.running]

    def by_token(self, token):
        """The job a relay token belongs to. Compared in constant time against every job of this app session."""
        if not isinstance(token, str) or not token:
            return None
        found = None
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            if job.token and secrets.compare_digest(job.token.encode(), token.encode()):
                found = job
        return found

    # ---- starting ----

    def start(self, kind, params):
        """Validate, build the argv and launch. Raises JobError (400 for parameters, 409 for a busy room or deck)."""
        plan = self.builder.build(kind, params)
        return self.launch(plan, params)

    def launch(self, plan, params=None):
        with self._lock:
            if plan.room:
                busy = next((j for j in self._jobs.values() if j.running and j.room), None)
                if busy:
                    raise JobError(f"job {busy.id} ({busy.title}) is using the room; stop it first, one room at a "
                                   "time", 409)
            if plan.deck_lock:
                busy = next((j for j in self._jobs.values() if j.running and j.deck_lock and j.deck
                             and j.deck.lower() == plan.deck.lower()), None)
                if busy:
                    raise JobError(f"job {busy.id} ({busy.title}) is working on {plan.deck}; wait for it or stop it",
                                   409)
            if plan.room and plan.room.get("kind") == "host" and not port_free(plan.room["port"]):
                raise JobError(f"port {plan.room['port']} is in use: is EDOPro hosting a room, or another ygo-agent "
                               "running? Close it, or pick another port.", 409)
            job_id = self.new_id(plan.kind)
            job = Job(job_id, plan.kind, plan.title, dict(params or {}), list(plan.argv),
                      os.path.join(self.dir, job_id + ".log"), room=plan.room, deck=plan.deck,
                      deck_lock=plan.deck_lock, started=time.time(), token=secrets.token_urlsafe(24))
            self._jobs[job_id] = job
        go = self.go_path(job)
        env = dict(os.environ)
        env.update({ENV_TOKEN: job.token, ENV_GO: go, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"})
        if self.relay_url:
            env[ENV_URL] = self.relay_url
        try:
            if os.path.exists(go):
                os.remove(go)
            with open(job.log, "ab") as log:
                log.write(f"$ {display_command(job.argv)}    # {time.strftime('%Y-%m-%d %H:%M:%S')}\n".encode())
                log.flush()
                job.proc = subprocess.Popen(self.prefix + job.argv, cwd=self.cwd, stdin=subprocess.DEVNULL,
                                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        except OSError as e:
            job.status, job.error, job.ended = "failed", f"couldn't start: {e}", time.time()
            self._changed(job)
            return job
        job.pid = job.proc.pid
        job.status = "running"
        self._changed(job)
        threading.Thread(target=self._wait, args=(job,), daemon=True, name=f"job-{job.id}").start()
        return job

    def go_path(self, job):
        return os.path.join(self.dir, job.id + ".go")

    def _wait(self, job):
        code = job.proc.wait()
        self._cleanup(job)
        with self._lock:
            job.code = code
            job.ended = time.time()
            job.waiting = None
            job.status = "stopped" if job.stop_requested else ("done" if code == 0 else "failed")
        self._changed(job)

    def _cleanup(self, job):
        """Kill whatever the job left behind: its process group, then anything carrying its token."""
        try:
            os.killpg(job.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        for pid in processes_with(job.token):
            _kill(pid, signal.SIGKILL)
        try:
            os.remove(self.go_path(job))
        except OSError:
            pass

    # ---- controlling ----

    def stop(self, job_id):
        """Ctrl+C for the job's process group, then SIGTERM, then SIGKILL (in the background). Returns the job."""
        job = self.get(job_id)
        if job is None:
            raise JobError("no such job", 404)
        with self._lock:
            if not job.running or job.stop_requested:
                return job
            job.stop_requested = True
            job.status = "stopping"
        self._changed(job)
        threading.Thread(target=self._stop, args=(job,), daemon=True, name=f"stop-{job.id}").start()
        return job

    def _stop(self, job, steps=None):
        for sig, wait in steps or self.stop_steps:
            try:
                os.killpg(job.pid, sig)
            except (ProcessLookupError, PermissionError):
                return
            try:
                job.proc.wait(timeout=wait)
                return
            except subprocess.TimeoutExpired:
                continue

    def go(self, job_id):
        """The button for what the job waits for (the room is open; start without a spectator)."""
        job = self.get(job_id)
        if job is None:
            raise JobError("no such job", 404)
        if not job.running or not job.waiting:
            raise JobError("the job isn't waiting for anything", 409)
        with open(self.go_path(job), "w") as f:
            f.write("go\n")
        return job

    def shutdown(self, quick=False):
        """Stop every running job (the app is exiting): Ctrl+C to all at once, then SIGTERM/SIGKILL for the slow
        ones. `quick`: SIGKILL right away."""
        jobs = self.running()
        for job in jobs:
            job.stop_requested = True
            job.status = "stopping"
        steps = ((signal.SIGKILL, 5.0),) if quick else self.stop_steps
        threads = [threading.Thread(target=self._stop, args=(j, steps), daemon=True) for j in jobs if j.proc]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for job in jobs:  # the waiter threads record the end; don't leave before they have
            deadline = time.monotonic() + 5
            while job.running and time.monotonic() < deadline:
                time.sleep(0.05)

    # ---- what the relay tells about a job ----

    def relayed(self, job, messages, waiting=False, has_waiting=False):
        """Note the job's games from relayed messages, and what it waits for."""
        changed = False
        with self._lock:
            for msg in messages:
                kind, gid = msg.get("type"), msg.get("game_id")
                if kind not in ("game_start", "meta", "game_end"):
                    continue
                entry = next((g for g in job.games if g["game_id"] == gid and g["seat"] == msg.get("seat", 0)), None)
                if entry is None:
                    if kind != "game_start":
                        continue
                    entry = {"game_id": gid, "seat": msg.get("seat", 0), "dir": None, "name": None, "ended": False}
                    job.games.append(entry)
                    changed = True
                if msg.get("dir"):
                    entry["dir"], entry["name"] = msg["dir"], msg.get("name") or os.path.basename(msg["dir"])
                    changed = True
                if kind == "game_end" or msg.get("result"):
                    entry["ended"] = True
                    changed = True
            if has_waiting and job.running:
                job.waiting = waiting
                changed = True
        if changed:
            self._changed(job)

    # ---- output ----

    def output(self, job, offset=0, limit=CHUNK):
        """The log from byte `offset` (negative: the last TAIL bytes), whole lines only while the job runs, ANSI
        colours stripped. {"offset", "next", "size", "text"}."""
        try:
            size = os.path.getsize(job.log)
        except OSError:
            return {"offset": 0, "next": 0, "size": 0, "text": ""}
        if offset < 0:
            offset = max(0, size - TAIL)
        offset = min(offset, size)
        with open(job.log, "rb") as f:
            f.seek(offset)
            data = f.read(limit)
        if data and (job.running or len(data) == limit) and not data.endswith(b"\n"):
            cut = data.rfind(b"\n")
            if cut >= 0:
                data = data[:cut + 1]
            elif len(data) < limit:
                data = b""
        text = ANSI.sub("", data.decode("utf-8", "replace")).replace("\r\n", "\n")
        return {"offset": offset, "next": offset + len(data), "size": size, "text": text}

    def doctor_result(self, job):
        """A finished `doctor --json` job's results (its JSON array), or None."""
        if job.kind != "doctor" or job.running:
            return None
        try:
            with open(job.log, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            return None
        start = text.find("\n[")
        try:
            data = json.loads(text[start + 1:]) if start >= 0 else None
        except ValueError:
            return None
        return data if isinstance(data, list) else None


def _kill(pid, sig):
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass
