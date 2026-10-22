"""Launch WindBot deck AIs that join the arena (or any EDOPro host) as players.

Uses the fork build (windbot-src/bin/Release/WindBot.exe) when present, else EDOPro's bundled WindBot. Bots run
"plain": no `Brain=` argument, so even the fork plays with its built-in deck AI. Each instance gets a scratch
AssetPath (Decks/Dialogs/bots.json linked in, crash.log and output written there) and its own process group,
so stopping it never leaves stray mono processes behind.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import weakref
from dataclasses import dataclass

from .. import paths


class WindBotError(RuntimeError):
    pass


@dataclass(frozen=True)
class BotInfo:
    name: str
    deck: str
    difficulty: int = 0
    master_rules: tuple[int, ...] = ()

    @property
    def description(self) -> str:
        rules = "/".join(str(r) for r in self.master_rules) or "?"
        return f"difficulty {self.difficulty}, Master Rule {rules}"


@dataclass(frozen=True)
class WindBotInstall:
    exe: str
    assets: str      # directory with Decks/, Dialogs/ and bots.json
    is_fork: bool

    @classmethod
    def find(cls, edopro_root: str | None = None, prefer_fork: bool = True) -> "WindBotInstall":
        candidates = []
        if prefer_fork and os.path.isfile(paths.WINDBOT_EXE):
            candidates.append((paths.WINDBOT_EXE, True))
        if edopro_root:
            candidates.append((os.path.join(edopro_root, "WindBot", "WindBot.exe"), False))
        for exe, fork in candidates:
            if os.path.isfile(exe) and os.path.isdir(os.path.join(os.path.dirname(exe), "Decks")):
                return cls(exe, os.path.dirname(exe), fork)
        raise WindBotError("no WindBot.exe found (build windbot-src with ./build.sh, or install EDOPro's WindBot)")

    def bots(self) -> list[BotInfo]:
        try:
            with open(os.path.join(self.assets, "bots.json"), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise WindBotError(f"cannot read bots.json in {self.assets}: {e}") from None
        return [BotInfo(b["name"], b["deck"], int(b.get("difficulty", 0)), tuple(b.get("masterRules", ())))
                for b in data]

    def resolve(self, ref: str) -> BotInfo:
        """A bot by its display name or deck name, case-insensitively ("Blue-Eyes", "blue-eyes", "ABC")."""
        key = ref.strip().lower()
        bots = self.bots()
        for attr in ("name", "deck"):
            for b in bots:
                if getattr(b, attr).lower() == key:
                    return b
        if os.path.isfile(os.path.join(self.assets, "Decks", f"AI_{ref}.ydk")):
            return BotInfo(ref, ref)
        raise WindBotError(f"unknown WindBot deck AI {ref!r}; try one of: {', '.join(b.name for b in bots)}")


def mono_path() -> str | None:
    return shutil.which("mono")


def db_paths_arg(cdb_paths: list[str]) -> str:
    """WindBot's DbPaths=: a base64 JSON array, loaded in order (later files override earlier ones)."""
    return base64.b64encode(json.dumps(list(cdb_paths)).encode()).decode()


_live: "weakref.WeakSet[WindBotProcess]" = weakref.WeakSet()


class WindBotProcess:
    def __init__(self, install: WindBotInstall, bot: BotInfo, name: str, port: int, *, host: str = "127.0.0.1",
                 version: int = 720937, cdb_paths: list[str] = (), scratch: str | None = None, hand: int = 0,
                 chat: bool = False, extra_args: dict[str, str] | None = None):
        self.install, self.bot, self.name, self.port, self.host = install, bot, name, port, host
        self.version, self.cdb_paths, self.hand, self.chat = version, list(cdb_paths), hand, chat
        self.extra_args = dict(extra_args or {})
        self.scratch = scratch
        self.proc: subprocess.Popen | None = None
        self._own_scratch = False

    def _prepare_assets(self) -> str:
        if self.scratch is None:
            self.scratch = tempfile.mkdtemp(prefix="windbot-")
            self._own_scratch = True
        os.makedirs(self.scratch, exist_ok=True)
        for entry in ("Decks", "Dialogs", "Executors", "bots.json"):
            src, dst = os.path.join(self.install.assets, entry), os.path.join(self.scratch, entry)
            if os.path.exists(src) and not os.path.lexists(dst):
                os.symlink(src, dst)
        return self.scratch

    def command(self) -> list[str]:
        mono = mono_path()
        if mono is None:
            raise WindBotError("mono is not installed (needed to run WindBot.exe)")
        args = {"Name": self.name, "Deck": self.bot.deck, "Host": self.host, "Port": str(self.port),
                "Version": str(self.version), "Chat": "true" if self.chat else "false", "Hand": str(self.hand),
                "AssetPath": self._prepare_assets()}
        if self.cdb_paths:
            args["DbPaths"] = db_paths_arg(self.cdb_paths)
        args.update(self.extra_args)
        return [mono, self.install.exe] + [f"{k}={v}" for k, v in args.items()]

    @property
    def log_path(self) -> str | None:
        return os.path.join(self.scratch, "windbot.log") if self.scratch else None

    def start(self) -> "WindBotProcess":
        cmd = self.command()
        log = open(self.log_path, "wb")
        try:
            self.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         cwd=self.scratch, start_new_session=True)
        finally:
            log.close()
        _live.add(self)
        return self

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def wait(self, timeout: float | None = None) -> int | None:
        if self.proc is None:
            return None
        try:
            return self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def stop(self, grace: float = 3.0) -> None:
        """SIGTERM the bot's process group, then SIGKILL whatever is left."""
        if self.proc is None:
            return
        if self.proc.poll() is None:
            for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 2.0)):
                try:
                    os.killpg(self.proc.pid, sig)
                except ProcessLookupError:
                    break
                deadline = time.monotonic() + wait
                while time.monotonic() < deadline and self.proc.poll() is None:
                    time.sleep(0.05)
                if self.proc.poll() is not None:
                    break
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass  # unreapable; nothing more a SIGKILL could do
        _live.discard(self)

    def crash_log(self) -> str:
        path = os.path.join(self.scratch or "", "crash.log")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def output(self) -> str:
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except (OSError, TypeError):
            return ""

    def problem(self) -> str | None:
        """Why this bot can't play, if its output says so (missing deck file, server refusal, crash)."""
        out = self.output()
        for line in out.splitlines():
            if "Failed to load deck" in line or "Server error" in line or "Tick Error" in line:
                return line.split("] ", 1)[-1].strip()
        if self.proc is not None and self.proc.poll() not in (None, 0):
            return f"exited with status {self.proc.returncode}"
        return None

    def cleanup(self) -> None:
        self.stop()
        if self._own_scratch and self.scratch:
            shutil.rmtree(self.scratch, ignore_errors=True)


async def watch_bots(room, seats: list[tuple[int, str]], procs: list[WindBotProcess], relaunch,
                     failed: list[str]) -> None:
    """Keep an arena room's WindBots playable. A bot that exits before its first match (or whose output says
    why it can't play) would leave the room waiting forever: `failed` gets the reason and the room is finished. A
    bot that left after a match is replaced with `relaunch(i)` once the room reopens. `seats[i]` is (lobby
    position, name) of `procs[i]`."""
    from .server import Stage
    while not room.finished.is_set():
        await asyncio.sleep(1.0)
        if room.stage is not Stage.LOBBY:
            continue
        for i, (pos, name) in enumerate(seats):
            p = procs[i]
            if room.slots[pos] is not None or p.running():
                continue
            problem = p.problem()
            if problem or room.matches_played == 0:
                failed.append(f"WindBot {name} can't play: {problem or 'it exited'} (see {p.log_path})")
                room.finished.set()
                return
            procs[i] = relaunch(i)


@atexit.register
def _stop_all() -> None:
    for p in list(_live):
        try:
            p.stop(grace=1.0)
        except Exception:
            pass
