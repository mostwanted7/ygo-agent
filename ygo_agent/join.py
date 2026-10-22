"""play --join: the agent's bot joins the LAN room you host in EDOPro (the WindBot fork in windbot-src, with its
BrainBridge connected to this process)."""

import base64
import json
import os
import re
import subprocess
import threading
import time

from . import cache, paths
from .agent import bridge_server
from .agent.gamelog import paint, BOLD, RED, YELLOW, DIM

DEFAULT_PROTOCOL_VERSION = 720937  # ClientVersion {41, 0, 11, 0}
HOST_VERSION = re.compile(r"Host version data: ([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})-([0-9A-F]{2})")


def protocol_version(cfg):
    """The configured version, else the one EDOPro reported last time, else the default."""
    return cfg["bot"].get("protocol_version") or cache.get("protocol_version") or DEFAULT_PROTOCOL_VERSION


def bot_args(cfg, db, profile, version):
    return {
        "Name": cfg["bot"]["name"],
        "Deck": "Agent",
        "DeckFile": profile.ydk,
        "Host": cfg["room"]["host"],
        "Port": cfg["room"]["port"],
        "HostInfo": cfg["room"].get("password", ""),
        "Brain": f"127.0.0.1:{cfg['bot']['brain_port']}",
        "Chat": "false",  # WindBot's own dialog lines; the agent's few lines are sent regardless
        "Hand": 0,
        "Version": version,
        "AssetPath": paths.WINDBOT,
        "DbPaths": base64.b64encode(json.dumps(db.db_paths).encode()).decode(),
    }


def bot_command(cfg, db, profile, version):
    return ["mono", paths.WINDBOT_EXE] + [f"{k}={v}" for k, v in bot_args(cfg, db, profile, version).items()]


def new_bot_log(cfg):
    """games/windbot/<time>.log, one file per bot run (a run is one match: one or more games)."""
    folder = os.path.join(paths.resolve(cfg.get("games_dir", "games")), "windbot")
    os.makedirs(folder, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    for n in range(1, 1000):
        path = os.path.join(folder, f"{stamp}.log" if n == 1 else f"{stamp}-{n}.log")
        try:
            open(path, "x").close()
            return path
        except FileExistsError:
            continue
    raise OSError(f"too many bot logs named {stamp} in {folder}")


def run_bot(runtime, version):
    """Runs the bot until it leaves the room; returns (exit code, host protocol version if it was rejected for one)."""
    cfg = runtime.cfg
    host_version = None
    log_path = new_bot_log(cfg)
    runtime.windbot_log = log_path
    print(paint(BOLD, f"\n▶ Sending {cfg['bot']['name']} to the room at {cfg['room']['host']}:{cfg['room']['port']} "
                      f"(bot output: {log_path})"))
    with open(log_path, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(bot_command(cfg, runtime.db, runtime.profile, version), cwd=paths.WINDBOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            log.write(line)
            log.flush()
            low = line.lower()
            match = HOST_VERSION.search(line)
            if match:
                host_version = int.from_bytes(bytes(int(b, 16) for b in match.groups()), "little")
            if "error" in low or "exception" in low or "failed" in low or "can't" in low:
                print(paint(RED, "  [bot] " + line.rstrip()))
            elif "brain" in low or "deck" in low or "connected" in low:
                print(paint(DIM, "  [bot] " + line.rstrip()))
        return proc.wait(), host_version


def play(runtime, brain_only=False):
    cfg = runtime.cfg
    bridge_server.start(runtime)
    print(paint(DIM, f"Brain listening on 127.0.0.1:{cfg['bot']['brain_port']}."))
    if brain_only:
        command = bot_command(cfg, runtime.db, runtime.profile, protocol_version(cfg))
        shown = ["HostInfo=<password>" if a.startswith("HostInfo=") and a != "HostInfo=" else a for a in command]
        print(paint(DIM, "Start the bot yourself with (from windbot-src/):\n  " + " ".join(shown)))
        threading.Event().wait()
    while True:
        print(paint(YELLOW, "\nIn EDOPro: LAN mode → Host Duel (set a long or no time limit), then wait in the room."))
        input(paint(BOLD, "Press Enter when the room is open... "))
        runtime.duel_started.clear()
        version = protocol_version(cfg)
        code, host_version = run_bot(runtime, version)
        if host_version and host_version != version:
            # EDOPro updated: remember its protocol version and go straight back in.
            print(paint(YELLOW, f"EDOPro uses protocol version {host_version}; caching it and retrying."))
            cache.put("protocol_version", host_version)
            runtime.duel_started.clear()
            code, host_version = run_bot(runtime, host_version)
        if runtime.duel_started.is_set():
            print(paint(DIM, f"Bot left the room (code {code})."))
        else:
            print(paint(RED, f"The bot never got into a duel. Is a room open at {cfg['room']['host']}:"
                             f"{cfg['room']['port']}? If it joined but left, check the deck/banlist settings and "
                             f"{runtime.windbot_log}."))
        again = input(paint(BOLD, "Play again? [Enter = yes, q = quit] ")).strip().lower()
        if again.startswith("q"):
            break
