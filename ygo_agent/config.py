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
FALLBACKS = ("bot", "heuristic")
CARD_TEXTS = ("full", "compact", "none")


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
    agent = cfg["agent"]
    if agent.get("fallback", "bot") not in FALLBACKS:
        raise ConfigError(f'agent.fallback must be one of {", ".join(FALLBACKS)} (got {agent.get("fallback")!r})')
    prefer = (cfg.get("decks") or {}).get("prefer") or ""
    if prefer not in ("", "user", "repo"):
        raise ConfigError(f'decks.prefer must be "user", "repo" or "" (got {prefer!r})')
    profile = backend(cfg)
    texts = profile.get("card_texts", agent.get("card_texts", "full"))
    if texts not in CARD_TEXTS:
        raise ConfigError(f'card_texts must be one of {", ".join(CARD_TEXTS)} (got {texts!r})')


def backend(cfg, name=None):
    """A backend profile (the active one by default), with its name filled in."""
    from .backends import TYPES
    name = name or cfg["agent"]["backend"]
    profile = cfg.get("backends", {}).get(name)
    if not isinstance(profile, dict):
        known = ", ".join(cfg.get("backends", {}))
        raise ConfigError(f"no backend profile {name!r}: add a [backends.{name}] table (profiles: {known})")
    if profile.get("type") not in TYPES:
        raise ConfigError(f"[backends.{name}] has type {profile.get('type')!r}; supported: {', '.join(TYPES)}")
    return {"name": name, **profile}


def deck_overrides(cfg, key):
    """Per-machine deck settings from [decks.<key>] (e.g. ydk = the EDOPro copy of the deck file). The [decks] table's
    own keys (user_dir, prefer) aren't decks."""
    value = (cfg.get("decks") or {}).get(key)
    return value if isinstance(value, dict) else {}
