"""The card database as the agent sees it: names, type lines and effect texts for prompts and logs.

Built on the core's view of the EDOPro install (core/install.py finds the .cdb, strings and script files the way
EDOPro does; core/cards.py reads them). A Card keeps the raw .cdb values (the level word with its Pendulum Scales,
the setcode word, a Link monster's markers in `defense`), which the prompt and web code read; the core's CardData
splits them the way the engine wants them.
"""

import os
import re
import sqlite3
from dataclasses import dataclass

from ..core.cards import Strings, cdb_rows
from ..core.constants import ATTRIBUTE_NAMES, RACE_NAMES
from ..core.install import EdoproInstall, InstallError

TYPE_NAMES = [
    (0x1, "Monster"), (0x2, "Spell"), (0x4, "Trap"), (0x10, "Normal"), (0x20, "Effect"),
    (0x40, "Fusion"), (0x80, "Ritual"), (0x100, "Trap Monster"), (0x200, "Spirit"),
    (0x400, "Union"), (0x800, "Gemini"), (0x1000, "Tuner"), (0x2000, "Synchro"),
    (0x4000, "Token"), (0x10000, "Quick-Play"), (0x20000, "Continuous"), (0x40000, "Equip"),
    (0x80000, "Field"), (0x100000, "Counter"), (0x200000, "Flip"), (0x400000, "Toon"),
    (0x800000, "Xyz"), (0x1000000, "Pendulum"), (0x4000000, "Link"),
]
ATTRIBUTES = ATTRIBUTE_NAMES
RACES = [RACE_NAMES[1 << i] for i in range(32)]  # by bit index
EXTRA_TYPES = 0x40 | 0x2000 | 0x800000 | 0x4000000


def shorten(text, name):
    """Card text with the same meaning in fewer tokens: no "unofficial text" notes, one line, short limit clauses."""
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("* The above text"))
    text = re.sub(r"\s+", " ", text).strip()
    q = re.escape(f'"{name}"')
    text = re.sub(rf"You can only use (this|each) effect of {q} once per turn\.",
                  lambda m: f"({m.group(1).capitalize()} effect: once per turn.)", text)
    text = re.sub(rf"You can only activate 1 {q} per turn\.", "(Activate once per turn.)", text)
    return re.sub(rf"You can only use 1 {q} effect per turn, and only once that turn\.",
                  "(Only 1 of its effects per turn.)", text)


@dataclass
class Card:
    id: int
    name: str
    text: str
    strings: list
    type: int
    level: int
    atk: int
    defense: int
    race: int
    attribute: int
    alias: int = 0
    setcode: int = 0

    @classmethod
    def from_row(cls, row):
        """A Card from a core.cards.cdb_rows() row."""
        cid, _ot, alias, setcode, typ, atk, de, level, race, attr, _category, name, desc = row[:13]
        return cls(cid, name or "", desc or "", [s or "" for s in row[13:29]], typ or 0, level or 0, atk or 0,
                   de or 0, race or 0, attr or 0, alias or 0, setcode or 0)

    def has(self, bit):
        return bool(self.type & bit)

    @property
    def is_monster(self):
        return self.has(0x1)

    @property
    def is_extra(self):
        return self.is_monster and bool(self.type & EXTRA_TYPES)

    def type_line(self):
        names = [n for bit, n in TYPE_NAMES if self.type & bit and n not in ("Monster",)]
        if self.is_monster:
            attr = ATTRIBUTES.get(self.attribute, "?")
            race = "/".join(RACES[i] for i in range(len(RACES)) if self.race & (1 << i)) or "?"
            lv = self.level & 0xFF
            if self.has(0x4000000):
                stars = f"Link-{lv}"
            elif self.has(0x800000):
                stars = f"Rank {lv}"
            else:
                stars = f"Lv{lv}"
            atk = "?" if self.atk < 0 else str(self.atk)
            stats = f"{atk} ATK" if self.has(0x4000000) else f"{atk}/{'?' if self.defense < 0 else self.defense}"
            scale = ""
            if self.has(0x1000000):
                scale = f" Scale {(self.level >> 24) & 0xFF}"
            return f"{attr} {race} {stars} {'/'.join(names)} {stats}{scale}"
        kind = "Spell" if self.has(0x2) else "Trap"
        sub = [n for n in names if n not in ("Spell", "Trap")]
        return f"{'/'.join(sub) + ' ' if sub else ''}{kind}"


class CardDB:
    """Every card and string table of an EDOPro install. `cards` is empty when the folder isn't one (callers say
    so); `install` is its core.install.EdoproInstall then, else None."""

    def __init__(self, edopro_dir):
        self.root = os.path.abspath(os.path.expanduser(edopro_dir))
        self.cards = {}
        self._scripts = None
        try:
            self.install = EdoproInstall.find(self.root)
        except InstallError:
            self.install = None
        # Later databases override earlier ones (expansions/, then each repository's deltas), as in EDOPro.
        self.db_paths = list(self.install.cdb_paths) if self.install else []
        for path in self.db_paths:
            self._load_cdb(path)
        strings = Strings(self.install.strings_paths if self.install else ())
        self.system = strings.tables.setdefault("system", {})
        self.victory = strings.tables.setdefault("victory", {})
        self.counters = strings.tables.setdefault("counter", {})
        self.setnames = strings.tables.setdefault("setname", {})

    @classmethod
    def from_dict(cls, data):
        """A database from plain data (tests use this instead of an EDOPro install): {"cards": {id: [name, text,
        strings, type, level, atk, def, race, attribute, alias, setcode]}, "system": {id: text}, "victory": {...}}."""
        db = cls.__new__(cls)
        db.root, db.install, db.db_paths, db.counters, db.setnames, db._scripts = None, None, [], {}, {}, None
        db.cards = {int(k): Card(int(k), *v) for k, v in data.get("cards", {}).items()}
        db.system = {int(k): v for k, v in data.get("system", {}).items()}
        db.victory = {int(k): v for k, v in data.get("victory", {}).items()}
        return db

    def _load_cdb(self, path):
        try:
            for row in cdb_rows(path):
                self.cards[row[0]] = Card.from_row(row)
        except sqlite3.Error as e:
            print(f"[carddb] could not read {path}: {e}")

    @property
    def scripts(self):
        """The card scripts (cardscripts.ScriptIndex), loaded on first use; empty for a database built from_dict."""
        if self._scripts is None:
            from ..core.scripts import ScriptLoader
            from .cardscripts import ScriptIndex
            self._scripts = ScriptIndex(loader=ScriptLoader(self.install.script_dirs) if self.install else None)
        return self._scripts

    def get(self, cid):
        return self.cards.get(cid)

    def name(self, cid):
        if not cid:
            return "unknown card"
        card = self.cards.get(cid)
        return card.name if card and card.name else f"card #{cid}"

    def full_text(self, cid):
        card = self.cards.get(cid)
        if not card:
            return f"card #{cid}: (no data)"
        return f'"{card.name}" [{card.type_line()}]: {card.text.strip()}'

    def type_text(self, cid):
        """Name and type line only (no effect text), for small-context prompts."""
        card = self.cards.get(cid)
        return f'"{card.name}" [{card.type_line()}]' if card else f"card #{cid}: (no data)"

    def compact_text(self, cid, limit=None):
        """full_text without the boilerplate, with the usual once-per-turn clauses shortened, and the effect cut at
        a sentence boundary near `limit` characters (marked with …)."""
        card = self.cards.get(cid)
        if not card:
            return f"card #{cid}: (no data)"
        text = shorten(card.text, card.name)
        if limit and len(text) > limit:
            cut = text[:limit]
            end = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(": "))
            text = (cut[:end + 1] if end > limit // 2 else cut[:cut.rfind(" ")]) + " …"
        return f'"{card.name}" [{card.type_line()}]: {text}'

    def desc(self, value):
        """Resolve an effect/hint description id to text (card strings are encoded as code << 20 | index)."""
        if value is None or value < 0:
            return None
        if value >= (1 << 20):
            code, idx = value >> 20, value & 0xFFFFF
            card = self.cards.get(code)
            if card and idx < 16 and card.strings[idx]:
                return card.strings[idx]
            return f"effect {idx + 1} of {self.name(code)}"
        if value == 0:
            return None
        return self.system.get(value)
