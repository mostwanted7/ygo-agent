"""Where things live. The package is used from a checkout of the repo, so everything is relative to it."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
DECKS = os.path.join(ROOT, "decks")
PLAYBOOKS = os.path.join(ROOT, "playbooks")
WINDBOT = os.path.join(ROOT, "windbot-src")
WINDBOT_EXE = os.path.join(WINDBOT, "bin", "Release", "WindBot.exe")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ygo-agent")


def resolve(path, base=ROOT):
    """Expand ~ and make relative paths relative to `base` (the repo by default)."""
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))
