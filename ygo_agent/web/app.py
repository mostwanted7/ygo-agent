"""The web app's API (only `ygo-agent web` serves it; a panel started by play/selfplay/teach/coach --web is the plain
panel): what this machine has (backends, WindBot deck AIs, EDOPro's decks), the decks with their playbook, tips,
pending notes and training, the jobs (web/jobs.py), and the relay that brings the jobs' live games in. server.py
routes the requests here; every handler returns (status, JSON-able object). docs/web.md has the endpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from types import SimpleNamespace

from .. import decks, paths
from ..trainer import notes, tips
from .jobs import DECK_NAME, Builder, JobError, JobRunner, training_dir

MAX_PLAYBOOK = 256 * 1024
MAX_TIP = 4000
MAX_MESSAGES = 20000      # per relay POST
GAME_ID = re.compile(r"^[\w:.+-]{1,200}$")
RECENT_GAMES = 12


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def read_json(path):
    text = read_text(path)
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def version():
    import ygo_agent
    found = getattr(ygo_agent, "__version__", None)
    if found:
        return found
    try:
        from importlib.metadata import version as dist_version
        return dist_version("ygo-agent")
    except Exception:
        return None


class App:
    def __init__(self, cfg, db, library, bus, jobs_dir=None, forward=None, runner=None, windbots=None):
        self.cfg = cfg
        self.db = db
        self.library = library
        self.bus = bus
        self.forward = {k: v for k, v in (forward or {}).items() if v}
        self._windbots = windbots  # ([bots], [problems]); found on first use (it reads every bot's deck)
        self.runner = runner or JobRunner(Builder(cfg, windbots=None, forward=self.forward), jobs_dir=jobs_dir)
        self.runner.on_change = self.job_changed

    def job_changed(self, job):
        """A job that ended mid-game (stopped, crashed) never sends its game's end: say so on the bus, or the game
        would stay "live" in every list."""
        if job.running:
            return
        for g in job.games:
            if g.get("ended"):
                continue
            g["ended"] = True
            if self.bus.seat_info(g["game_id"], g["seat"]) and not self.bus.seat_info(g["game_id"], g["seat"]).get(
                    "result"):
                self.bus.inject({"type": "meta", "game_id": g["game_id"], "seat": g["seat"], "result": "unfinished"})

    # ---- what this machine has ----

    def windbots(self):
        if self._windbots is None:
            self._windbots = legal_windbots(self.cfg, self.db)
        return self._windbots

    def builder(self):
        b = self.runner.builder
        if b.windbots is None:
            b.windbots = [w["name"] for w in self.windbots()[0]]
        return b

    def backends(self):
        from .. import backends
        out = []
        for name, profile in (self.cfg.get("backends") or {}).items():
            if not isinstance(profile, dict) or profile.get("type") == "scripted":
                continue
            row = {"name": name, "type": profile.get("type"), "model": profile.get("model"),
                   "effort": profile.get("effort"), "label": name, "ok": True, "problem": None}
            try:
                full = {"name": name, **profile}
                row["label"] = backends.label(full)
                backends.check(full)
            except Exception as e:
                row["ok"], row["problem"] = False, str(e)
            out.append(row)
        return out

    def info(self):
        from ..config import DEFAULT_PATH, LOCAL_PATH
        edopro = paths.resolve(self.cfg.get("edopro_dir", "~/Games/ProjectIgnis"))
        bots, problems = self.windbots()
        trainer, coach = self.cfg.get("trainer", {}), self.cfg.get("coach", {})
        local = self.forward.get("config") or LOCAL_PATH
        return 200, {
            "app": True, "version": version(), "root": paths.ROOT,
            "backends": self.backends(), "default_backend": self.cfg["agent"]["backend"],
            "default_deck": self.cfg.get("deck"), "rules": self.cfg["duel"]["rules"],
            "windbots": bots, "windbot_problems": problems,
            "join_available": os.path.isfile(paths.WINDBOT_EXE),
            "edopro_dir": edopro, "edopro_decks": edopro_decks(edopro),
            "decks_dirs": {"repo": decks.repo_dir(), "user": decks.user_dir(self.cfg)},
            "games_dir": self.library.games_dir, "jobs_dir": self.runner.dir,
            "config": {"default": DEFAULT_PATH, "local": local, "local_exists": os.path.isfile(local)},
            "room": {"port": self.cfg["room"]["port"], "password": bool(self.cfg["room"].get("password")),
                     "name": self.cfg.get("arena", {}).get("room_name", "ygo-agent"),
                     "time_limit": self.cfg.get("arena", {}).get("time_limit", 600)},
            "trainer": {"backend": trainer.get("backend") or self.cfg["agent"]["backend"],
                        "player_backend": trainer.get("player_backend") or self.cfg["agent"]["backend"],
                        "opponents": trainer.get("opponents") or []},
            "coach": {"opponent": coach.get("opponent", "windbot:Blue-Eyes"), "level": coach.get("level", "beginner"),
                      "time_limit": coach.get("time_limit", 1200)},
        }

    # ---- decks ----

    def resolve(self, name):
        """(folder, key, location) of a deck by name: a deck folder, or one a training run has started (it may not be
        a deck yet). None when there's neither."""
        if not isinstance(name, str) or not DECK_NAME.match(name):
            return None
        try:
            d = decks.find(name, self.cfg)
            return d.dir, d.key, d.location
        except decks.DeckError:
            pass
        folder = training_dir(name, self.cfg)
        return (folder, os.path.basename(folder), decks.location_of(folder, self.cfg)) if folder else None

    def game_index(self):
        """deck (lower case) → {"games": [folder names, newest first], "pending": n, "others": n}."""
        out = {}
        games_dir = self.library.games_dir
        try:
            names = sorted(os.listdir(games_dir), reverse=True)
        except OSError:
            return out
        for name in names:
            folder = os.path.join(games_dir, name)
            if name == "latest" or os.path.islink(folder):
                continue
            meta = notes.read_meta(folder)
            deck = str(meta.get("deck") or "").lower()
            if not deck:
                continue
            row = out.setdefault(deck, {"games": [], "pending": 0, "others": 0})
            row["games"].append(name)
            if os.path.isfile(os.path.join(folder, "feedback.md")):
                for n in notes.read(folder, meta):
                    if n.pending:
                        row["pending" if n.trusted else "others"] += 1
        return out

    def deck_rows(self):
        index = self.game_index()
        rows = decks.listing(self.cfg)
        keys = {r["key"].lower() for r in rows}
        for location, root in decks.roots(self.cfg):  # decks a training run has started but not finished setting up
            try:
                names = sorted(os.listdir(root))
            except OSError:
                continue
            for name in names:
                folder = os.path.join(root, name)
                if name.lower() not in keys and os.path.isdir(os.path.join(folder, "train")) and DECK_NAME.match(name):
                    interview = read_json(os.path.join(folder, "train", "interview.json"))
                    shown = interview.get("deck") if isinstance(interview, dict) and interview.get("deck") else name
                    rows.append({"key": name, "name": shown, "location": location, "dir": folder, "ydk": None,
                                 "ydk_ok": False, "playbook_bytes": 0, "rules": 0, "tests": 0, "training_only": True})
                    keys.add(name.lower())
        for row in rows:
            games = index.get(row["key"].lower(), {})
            row["tips"] = len(tips.entries(row["dir"]))
            row["pending_notes"] = games.get("pending", 0)
            row["other_notes"] = games.get("others", 0)
            row["games"] = len(games.get("games", []))
            row["train"] = train_status(row["dir"])
            last = games.get("games", [None])[0]
            row["last_game"] = self.game_brief(last) if last else None
        return rows

    def game_brief(self, name):
        s = self.library.summary(name)
        if not s:
            return None
        return {k: s.get(k) for k in ("name", "game_id", "deck_name", "opponent", "result", "mode", "backend",
                                      "started", "decisions", "turns", "notes")}

    def decks(self):
        return 200, {"decks": self.deck_rows(), "dirs": {"repo": decks.repo_dir(), "user": decks.user_dir(self.cfg)}}

    def deck(self, name):
        found = self.resolve(name)
        if not found:
            return 404, {"error": f"no deck {name!r}"}
        folder, key, location = found
        row = next((r for r in self.deck_rows() if r["key"].lower() == key.lower()), {})
        playbook = read_text(os.path.join(folder, "playbook.md"))
        pending = []
        others = 0
        for n in notes.for_deck(key, self.library.games_dir):
            if not n.pending:
                continue
            if not n.trusted:
                others += 1
                continue
            d = n.to_dict()
            d["recorded"] = n.game if self.library.path(n.game) else None
            pending.append(d)
        report = None
        for path in (os.path.join(folder, "train", "train-report.md"), os.path.join(folder, "train-report.md")):
            report = read_text(path)
            if report is not None:
                report = {"path": path, "markdown": report}
                break
        games = [self.game_brief(os.path.basename(g)) for g in notes.deck_games(key, self.library.games_dir)]
        learn_md = read_text(os.path.join(folder, "train", "learn.md"))
        # `learn` keeps the digest of the tips it last folded in (state.json's learn.tips_digest).
        state = read_json(os.path.join(folder, "train", "state.json")) or {}
        digest = tips.digest(folder)
        learned = (state.get("learn") or {}).get("tips_digest") if isinstance(state, dict) else None
        jobs = [j.to_dict() for j in self.runner.list() if j.deck and j.deck.lower() == key.lower()][:12]
        interview = read_json(os.path.join(folder, "train", "interview.json"))
        name = row.get("name") or key
        if row.get("training_only") and isinstance(interview, dict) and interview.get("deck"):
            name = interview["deck"]
        return 200, {
            **row, "name": name, "key": key, "location": location, "dir": folder, "playbook": playbook,
            "playbook_sha": sha(playbook), "tips_entries": tips.entries(folder), "tips_path": tips.path(folder),
            "pending": pending, "other_pending": others, "report": report,
            "tips_changed": bool(digest) and digest != learned,
            "interview": interview,
            "train": train_status(folder), "games_list": [g for g in games if g][:RECENT_GAMES],
            "learn_log": learn_md[-4000:] if learn_md else None, "jobs": jobs,
            "busy": next((j["id"] for j in jobs if j["running"] and j["kind"] in ("train", "learn", "train-interview")),
                         None)}

    def save_playbook(self, name, body):
        found = self.resolve(name)
        if not found:
            return 404, {"error": f"no deck {name!r}"}
        folder, key, _ = found
        text = body.get("text")
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_PLAYBOOK:
            return 400, {"error": f"text: the playbook, up to {MAX_PLAYBOOK // 1024} KiB"}
        busy = next((j for j in self.runner.running() if j.deck_lock and j.deck and j.deck.lower() == key.lower()), None)
        if busy:
            return 409, {"error": f"job {busy.id} ({busy.title}) is changing this deck; save after it ends"}
        path = os.path.join(folder, "playbook.md")
        current = read_text(path)
        if body.get("base") is not None and body.get("base") != sha(current):
            return 409, {"error": "the playbook changed on disk since you opened it: reload the page and edit again"}
        text = text.replace("\r\n", "\n").rstrip("\n") + "\n"
        history = None
        if current is not None:
            if current == text:
                return 200, {"ok": True, "sha": sha(text), "bytes": len(text.encode()), "history": None, "same": True}
            history = os.path.join(folder, "train", "history", f"playbook-{time.strftime('%Y%m%d-%H%M%S')}.md")
            os.makedirs(os.path.dirname(history), exist_ok=True)
            with open(history, "w", encoding="utf-8") as f:
                f.write(current)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        return 200, {"ok": True, "sha": sha(text), "bytes": len(text.encode()), "history": history}

    def deck_display_name(self, folder, key):
        data = read_json(os.path.join(folder, "deck.json")) or {}
        return data.get("name") or key

    def add_tip(self, name, body):
        found = self.resolve(name)
        if not found:
            return 404, {"error": f"no deck {name!r}"}
        folder, key, _ = found
        text, title = body.get("text"), body.get("title") or "Tip"
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TIP:
            return 400, {"error": f"text: the tip, 1 to {MAX_TIP} characters"}
        if not isinstance(title, str) or len(title) > 200:
            return 400, {"error": "title: up to 200 characters"}
        tips.add(folder, text, title, name=self.deck_display_name(folder, key))
        return 200, {"ok": True, "tips": tips.entries(folder)}

    def save_interview(self, name, body):
        found = self.resolve(name)
        if not found:
            return 404, {"error": f"no deck {name!r}"}
        folder, key, _ = found
        answers = body.get("answers")
        if not isinstance(answers, list) or len(answers) > 40:
            return 400, {"error": "answers: a list of {question, answer}"}
        clean = []
        for a in answers:
            if not isinstance(a, dict) or not isinstance(a.get("question", ""), str) \
                    or not isinstance(a.get("answer", ""), str) or len(a.get("answer") or "") > MAX_TIP:
                return 400, {"error": f"each answer: {{question, answer}} with up to {MAX_TIP} characters"}
            clean.append({"question": a.get("question") or "Tip", "answer": a.get("answer") or ""})
        display = (read_json(os.path.join(folder, "train", "interview.json")) or {}).get("deck")
        saved = tips.save_answers(folder, clean, name=display or self.deck_display_name(folder, key))
        return 200, {"ok": True, "saved": saved, "tips": tips.entries(folder)}

    # ---- jobs ----

    def job_dict(self, job, full=False, live=None):
        d = job.to_dict()
        live = {g["game_id"]: g for g in self.bus.games()} if live is None else live
        for g in d["games"]:
            s = live.get(g["game_id"])
            g["live"] = bool(s and s["live"]) and not g.get("ended")
            g["title"] = s["title"] if s else (g.get("name") or g["game_id"])
            g["on_bus"] = s is not None
            name = os.path.basename(g["dir"]) if g.get("dir") else None
            g["recorded"] = name if name and os.path.dirname(os.path.abspath(g["dir"])) == os.path.abspath(
                self.library.games_dir) and self.library.path(name) else None
        if full and job.kind == "doctor":
            d["result"] = self.runner.doctor_result(job)
        return d

    def jobs(self):
        live = {g["game_id"]: g for g in self.bus.games()}
        return 200, {"jobs": [self.job_dict(j, live=live) for j in self.runner.list()[:100]]}

    def job(self, job_id, offset=None):
        job = self.runner.get(job_id)
        if job is None:
            return 404, {"error": "no such job"}
        out = {"job": self.job_dict(job, full=True)}
        if offset is not None:
            out["output"] = self.runner.output(job, offset)
        return 200, out

    def start_job(self, body):
        kind, params = body.get("kind"), body.get("params") or {}
        try:
            job = self.runner.launch(self.builder().build(kind, params), params)
        except JobError as e:
            return e.status, {"error": str(e)}
        return 200, {"job": self.job_dict(job)}

    def stop_job(self, job_id):
        try:
            return 200, {"job": self.job_dict(self.runner.stop(job_id))}
        except JobError as e:
            return e.status, {"error": str(e)}

    def go_job(self, job_id):
        try:
            return 200, {"job": self.job_dict(self.runner.go(job_id))}
        except JobError as e:
            return e.status, {"error": str(e)}

    def shutdown(self, quick=False):
        self.runner.shutdown(quick=quick)

    # ---- the relay ----

    def relay(self, token, body):
        job = self.runner.by_token(token)
        if job is None:
            return 403, {"error": "unknown relay token"}
        messages = body.get("messages") or []
        if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
            return 400, {"error": "messages: a list"}
        kept = []
        for msg in messages:
            if isinstance(msg, dict) and isinstance(msg.get("type"), str) and isinstance(msg.get("game_id"), str) \
                    and GAME_ID.match(msg["game_id"]) and isinstance(msg.get("seat", 0), int):
                out = self.bus.inject(msg)
                if out is not None:
                    kept.append(out)
        waiting = body.get("waiting")
        if waiting is not None and not (isinstance(waiting, dict) and isinstance(waiting.get("text"), str)):
            waiting = None
        if isinstance(waiting, dict):
            waiting = {"text": waiting["text"][:300], "button": str(waiting.get("button") or "Continue")[:60]}
        self.runner.relayed(job, kept, waiting, has_waiting="waiting" in body)
        return 200, {"ok": True, "n": len(kept)}


def train_status(folder):
    """The training state of a deck folder: None, or {"status", "updated", "rounds", "cost"} from train/state.json."""
    state = read_json(os.path.join(folder, "train", "state.json"))
    if not isinstance(state, dict):
        return {"status": "interview", "updated": None, "cost": None} if os.path.isfile(
            os.path.join(folder, "train", "interview.json")) else None
    ledger = state.get("ledger") or []
    cost = sum((e.get("cost") or 0) for e in ledger if isinstance(e, dict))
    return {"status": state.get("status"), "updated": state.get("updated"), "cost": round(cost, 2)}


def edopro_decks(edopro_dir):
    folder = os.path.join(edopro_dir, "deck")
    try:
        names = sorted(f for f in os.listdir(folder) if f.lower().endswith(".ydk"))
    except OSError:
        return []
    return [{"name": f[:-4], "path": os.path.join(folder, f)} for f in names]


def legal_windbots(cfg, db):
    """([{"name", "deck", "difficulty"}], [problems]): EDOPro's WindBot deck AIs legal under the config's rules (the
    trainer's check: the bot plays those rules and its deck has no Link monsters under Master Rule 1-3)."""
    from ..arena.windbot import WindBotError, WindBotInstall, mono_path
    if mono_path() is None:
        return [], ["mono is not installed, so WindBot deck AIs can't play (an AI deck can be the opponent)"]
    root = paths.resolve(cfg.get("edopro_dir", "~/Games/ProjectIgnis"))
    try:
        install = WindBotInstall.find(root)
        bots = install.bots()
    except WindBotError as e:
        return [], [str(e)]
    from ..trainer.games import check_pool
    engine = SimpleNamespace(install=SimpleNamespace(root=root))
    try:
        ok, problems = check_pool([f"windbot:{b.name}" for b in bots], engine, db, rules=cfg["duel"]["rules"])
    except Exception as e:  # a broken bots.json or deck file mustn't take the app down
        return [], [f"couldn't check the WindBot deck AIs: {e}"]
    legal = {s.split(":", 1)[1] for s in ok}
    return [{"name": b.name, "deck": b.deck, "difficulty": b.difficulty} for b in bots if b.name in legal], problems
