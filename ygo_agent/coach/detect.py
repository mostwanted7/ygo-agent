"""Which deck is the human playing? Their submitted list against every deck profile (decks/ and the user decks dir), so
the coach can use that deck's playbook and rules; else against EDOPro's deck folder, just to give it a name."""

import collections
import os
from dataclasses import dataclass

from .. import decks, paths
from ..agent.profile import Profile, parse_ydk

MATCH = 0.6    # share of the cards in common to call it that deck (a few swapped cards still count)
NAMED = 0.85   # for naming a deck that has no profile


@dataclass
class Detection:
    key: str | None        # the deck profile (a deck folder's name), or None
    name: str              # a readable name for the deck
    score: float           # 0..1, the share of cards in common with the best match
    source: str = ""       # the .ydk it matched
    profile: Profile | None = None
    folder: str = ""       # the deck profile's folder

    def describe(self) -> str:
        if self.key:
            where = decks.short(self.folder) if self.folder else self.key
            return f"your deck matches the {self.name} profile ({where}, {self.score:.0%} of the cards)"
        if self.source:
            return f"your deck looks like {os.path.basename(self.source)} ({self.score:.0%}), which has no deck profile"
        return "your deck doesn't match any deck profile"


def counts(codes, db=None):
    """A multiset of card codes, alternate artworks folded into their original (alias)."""
    out = collections.Counter()
    for code in codes:
        card = db.get(code) if db is not None else None
        out[(card.alias or code) if card is not None and getattr(card, "alias", 0) else code] += 1
    return out


def overlap(a, b):
    """Cards in common over the bigger deck's size: 1.0 for the same list, 0 for nothing shared."""
    size = max(sum(a.values()), sum(b.values()))
    return sum((a & b).values()) / size if size else 0.0


def candidates(cfg, db):
    """(key, name, ydk, folder) of every deck profile, with config overrides (e.g. the EDOPro copy of a deck's .ydk).
    A name in both deck dirs without [decks] prefer is skipped: playing it would fail anyway."""
    for key in decks.keys(cfg):
        try:
            profile = Profile(key, db, cfg)
        except (FileNotFoundError, OSError, ValueError):
            continue
        yield key, profile.name, profile.ydk, profile.dir


def edopro_decks(cfg):
    folder = os.path.join(paths.resolve(cfg.get("edopro_dir", "~/Games/ProjectIgnis")), "deck")
    try:
        names = sorted(f for f in os.listdir(folder) if f.lower().endswith(".ydk"))
    except OSError:
        return []
    return [os.path.join(folder, f) for f in names]


def detect(main, extra, cfg, db=None) -> Detection:
    """The deck profile the list (main + extra codes) matches best, if any clears MATCH."""
    mine = counts(list(main) + list(extra), db)
    best = None
    for key, name, ydk, folder in candidates(cfg, db):
        try:
            m, x, _ = parse_ydk(ydk)
        except OSError:
            continue
        score = overlap(mine, counts(m + x, db))
        if best is None or score > best.score:
            best = Detection(key, name, score, ydk, folder=folder)
    if best and best.score >= MATCH:
        return best
    named = None
    for ydk in edopro_decks(cfg):
        try:
            m, x, _ = parse_ydk(ydk)
        except OSError:
            continue
        score = overlap(mine, counts(m + x, db))
        if named is None or score > named.score:
            named = Detection(None, os.path.splitext(os.path.basename(ydk))[0], score, ydk)
    if named and named.score >= NAMED:
        return named
    return Detection(None, "your deck", best.score if best else 0.0)


def write_ydk(path, main, extra, side=()):
    """The human's submitted list as a .ydk (coaching an unknown deck makes a Profile from it)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#created by ygo-agent coach\n#main\n")
        f.writelines(f"{c}\n" for c in main)
        f.write("#extra\n")
        f.writelines(f"{c}\n" for c in extra)
        f.write("!side\n")
        f.writelines(f"{c}\n" for c in side)
    return path
