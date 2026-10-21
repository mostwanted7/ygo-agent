"""Configuration: config/default.toml, then config.local.toml (gitignored), then CLI flags.

The result is a plain nested dict with the same layout as the TOML files. Nothing writes these files at runtime;
facts learned while running (like EDOPro's protocol version) go to the cache instead (see cache.py).
"""

import copy
import os
import tomllib

from .paths import CONFIG_DIR, ROOT

DEFAULT_PATH = os.path.join(CONFIG_DIR, "default.toml")
LOCAL_PATH = os.path.join(ROOT, "config.local.toml")
CHAT_MODES = ("banter", "off")


class ConfigError(Exception):
    pass


def merge(base, extra):
    """Recursively merge `extra` into a copy of `base`; tables merge, everything else is replaced."""
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read(path):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None


def load_config(local=LOCAL_PATH, overrides=None):
    cfg = _read(DEFAULT_PATH)
    if local and os.path.exists(local):
        cfg = merge(cfg, _read(local))
    if overrides:
        cfg = merge(cfg, overrides)
    check(cfg)
    return cfg


def check(cfg):
    if cfg.get("chat") not in CHAT_MODES:
        raise ConfigError(f'chat must be one of {", ".join(CHAT_MODES)} (got {cfg.get("chat")!r})')
    backend(cfg)


def backend(cfg):
    """The active backend profile, with its name filled in."""
    name = cfg["agent"]["backend"]
    profile = cfg.get("backends", {}).get(name)
    if not isinstance(profile, dict):
        raise ConfigError(f"agent.backend is {name!r}, but there is no [backends.{name}] table")
    return {"name": name, **profile}


def deck_overrides(cfg, key):
    """Per-machine deck settings from [decks.<key>] (e.g. ydk = the EDOPro copy of the deck file)."""
    return cfg.get("decks", {}).get(key, {})
