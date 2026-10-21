"""Small persistent facts learned at runtime (e.g. EDOPro's protocol version), kept out of the config files."""

import json
import os

from .paths import CACHE

STATE = os.path.join(CACHE, "state.json")


def _read():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def get(key, default=None):
    return _read().get(key, default)


def put(key, value):
    state = _read()
    state[key] = value
    os.makedirs(CACHE, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)
