"""Where deck profiles live, and the one lookup every command resolves a deck name through.

A deck profile is a folder with a deck.json (and the .ydk, playbook.md, rules.py, tests/). Two roots hold them,
searched in this order:

  repo  decks/ in the checkout: the curated decks that ship with ygo-agent.
  user  [decks] user_dir, by default $XDG_DATA_HOME/ygo-agent/decks (~/.local/share/ygo-agent/decks): your own decks.
        `ygo-agent train` writes there (unless --into repo), so training never dirties the checkout and an update
        never overwrites a deck you trained. Sharing one is a deliberate copy into decks/.

Names match ignoring case. A name in both roots is an error unless [decks] prefer = "user" (or "repo") says which
one wins, so a deck never silently shadows another.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass

from . import paths

LOCATIONS = ("repo", "user")


class DeckError(FileNotFoundError):
    """A deck name that doesn't resolve: no such deck, or one in both roots without [decks] prefer."""


@dataclass(frozen=True)
class DeckDir:
    key: str        # the folder's name
    location: str   # "repo" or "user"
    dir: str


def settings(cfg: dict | None) -> dict:
    """The [decks] keys. Its tables ([decks.<key>]) are per-deck overrides instead (see deck_settings)."""
    return {k: v for k, v in ((cfg or {}).get("decks") or {}).items() if not isinstance(v, dict)}


def user_dir(cfg: dict | None = None) -> str:
    configured = settings(cfg).get("user_dir")
    if configured:
        return paths.resolve(configured)
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "ygo-agent", "decks")


def repo_dir() -> str:
    return paths.DECKS


def roots(cfg: dict | None = None) -> list[tuple[str, str]]:
    """(location, folder) in search order."""
    return [("repo", repo_dir()), ("user", user_dir(cfg))]


def root_dir(location: str, cfg: dict | None = None) -> str:
    return dict(roots(cfg))[location]


def preference(cfg: dict | None = None) -> str:
    prefer = settings(cfg).get("prefer") or ""
    if prefer not in ("", *LOCATIONS):
        raise DeckError(f'[decks] prefer must be "user", "repo" or "" (got {prefer!r})')
    return prefer


def location_of(folder: str, cfg: dict | None = None) -> str | None:
    """"repo"/"user" when `folder` is a deck folder directly inside that root, else None."""
    parent = os.path.realpath(os.path.dirname(os.path.abspath(folder)))
    for location, root in roots(cfg):
        if parent == os.path.realpath(root):
            return location
    return None


def scan(cfg: dict | None = None) -> list[DeckDir]:
    """Every deck folder in both roots, repo first; a name in both appears twice."""
    out, seen = [], set()
    for location, root in roots(cfg):
        if os.path.realpath(root) in seen:  # user_dir pointed at decks/ itself
            continue
        seen.add(os.path.realpath(root))
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in names:
            folder = os.path.join(root, name)
            if os.path.isfile(os.path.join(folder, "deck.json")):
                out.append(DeckDir(name, location, folder))
    return out


def matches(name: str, cfg: dict | None = None) -> list[DeckDir]:
    want = (name or "").lower()
    return [d for d in scan(cfg) if d.key.lower() == want]


def find(name: str, cfg: dict | None = None) -> DeckDir:
    """The deck folder called `name` (any case). Raises DeckError when there's none, or one in each root and no
    [decks] prefer."""
    found = matches(name, cfg)
    if not found:
        known = ", ".join(keys(cfg)) or "none"
        raise DeckError(f"no deck {name!r} in {where(cfg)} (decks: {known})")
    if len({d.location for d in found}) > 1:
        prefer = preference(cfg)
        if not prefer:
            both = " and ".join(short(d.dir) for d in found)
            raise DeckError(f"deck {name!r} exists twice ({both}): rename one, or say which wins with "
                            '[decks] prefer = "user" (or "repo") in config.local.toml')
        found = [d for d in found if d.location == prefer]
    return next((d for d in found if d.key == name), found[0])


def keys(cfg: dict | None = None) -> list[str]:
    return sorted({d.key for d in scan(cfg)})


def where(cfg: dict | None = None) -> str:
    return " or ".join(short(root) for _, root in roots(cfg))


def short(path: str) -> str:
    """Repo-relative inside the checkout, ~-abbreviated under the home folder."""
    path = os.path.abspath(path)
    if path == paths.ROOT or path.startswith(paths.ROOT + os.sep):
        return os.path.relpath(path, paths.ROOT)
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def deck_settings(folder: str, key: str, cfg: dict | None = None) -> dict:
    """deck.json, with this machine's [decks.<key>] table on top (e.g. ydk = the EDOPro copy of the deck list, so
    edits made in EDOPro carry over)."""
    from .config import deck_overrides
    with open(os.path.join(folder, "deck.json"), encoding="utf-8") as f:
        data = json.load(f)
    data.update(deck_overrides(cfg or {}, key))
    return data


def rules_count(folder: str) -> int | None:
    """How many functions the deck's rules.py lists in RULES (0 without a rules.py, None if it doesn't load)."""
    from .agent.rules import load_rules
    try:
        return len(load_rules(os.path.join(folder, "rules.py")))
    except Exception:  # a listing must survive one deck's broken rules.py, whatever the error
        return None


def target(name: str, into: str, cfg: dict | None = None) -> str:
    """The folder a new deck called `name` goes to (`into` "user" or "repo"). Raises DeckError when the other root
    already has a deck by that name, since the two would then clash on every lookup."""
    if into not in LOCATIONS:
        raise DeckError(f"--into must be user or repo (got {into!r})")
    clash = [d for d in matches(name, cfg) if d.location != into]
    if clash:
        raise DeckError(f"there is already a deck {name!r} in {short(clash[0].dir)}: pick another --name, so the "
                        "two don't clash")
    return os.path.join(root_dir(into, cfg), name)


def listing(cfg: dict | None = None) -> list[dict]:
    """One row per deck folder for `ygo-agent decks`: key, name, location, playbook size, rules, tests, ydk."""
    rows = []
    entries = scan(cfg)
    counts = {}
    for d in entries:
        counts[d.key.lower()] = counts.get(d.key.lower(), 0) + 1
    try:
        prefer = preference(cfg)
    except DeckError:
        prefer = ""
    for d in entries:
        row = {"key": d.key, "location": d.location, "dir": d.dir, "name": d.key, "ydk": None, "ydk_ok": False,
               "playbook_bytes": 0, "rules": rules_count(d.dir), "tests": len(glob.glob(os.path.join(d.dir, "tests",
                                                                                                    "*.json")))}
        try:
            data = deck_settings(d.dir, d.key, cfg)
            row["name"] = data.get("name", d.key)
            row["ydk"] = paths.resolve(data.get("ydk", "deck.ydk"), d.dir)
            row["ydk_ok"] = os.path.isfile(row["ydk"])
        except (OSError, ValueError) as e:
            row["error"] = f"deck.json: {e}"
        playbook = os.path.join(d.dir, "playbook.md")
        if os.path.isfile(playbook):
            row["playbook_bytes"] = os.path.getsize(playbook)
        if counts[d.key.lower()] > 1:
            row["clash"] = "used" if prefer == d.location else ("shadowed" if prefer else "clash")
        rows.append(row)
    return rows
