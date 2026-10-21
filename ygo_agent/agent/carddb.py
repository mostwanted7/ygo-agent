"""Card database and string tables, read straight from an EDOPro install."""

import glob
import os
import re
import sqlite3
from dataclasses import dataclass, field

TYPE_NAMES = [
    (0x1, "Monster"), (0x2, "Spell"), (0x4, "Trap"), (0x10, "Normal"), (0x20, "Effect"),
    (0x40, "Fusion"), (0x80, "Ritual"), (0x100, "Trap Monster"), (0x200, "Spirit"),
    (0x400, "Union"), (0x800, "Gemini"), (0x1000, "Tuner"), (0x2000, "Synchro"),
    (0x4000, "Token"), (0x10000, "Quick-Play"), (0x20000, "Continuous"), (0x40000, "Equip"),
    (0x80000, "Field"), (0x100000, "Counter"), (0x200000, "Flip"), (0x400000, "Toon"),
    (0x800000, "Xyz"), (0x1000000, "Pendulum"), (0x4000000, "Link"),
]
ATTRIBUTES = {0x1: "EARTH", 0x2: "WATER", 0x4: "FIRE", 0x8: "WIND", 0x10: "LIGHT", 0x20: "DARK", 0x40: "DIVINE"}
RACES = [
    "Warrior", "Spellcaster", "Fairy", "Fiend", "Zombie", "Machine", "Aqua", "Pyro", "Rock",
    "Winged Beast", "Plant", "Insect", "Thunder", "Dragon", "Beast", "Beast-Warrior", "Dinosaur",
    "Fish", "Sea Serpent", "Reptile", "Psychic", "Divine-Beast", "Creator God", "Wyrm", "Cyberse",
    "Illusion", "Cyborg", "Magical Knight", "High Dragon", "Omega Psychic", "Celestial Warrior", "Galaxy",
]
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
    extra: dict = field(default_factory=dict)

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
    def __init__(self, edopro_dir):
        self.root = os.path.expanduser(edopro_dir)
        self.cards = {}
        self.system = {}
        self.victory = {}
        self.counters = {}
        self.setnames = {}
        # Later databases override earlier ones, so load the base files first and the update deltas last.
        paths = sorted(glob.glob(os.path.join(self.root, "expansions", "*.cdb")))
        paths.sort(key=lambda p: (os.path.basename(p) != "cards.cdb", p))
        paths += sorted(glob.glob(os.path.join(self.root, "repositories", "*", "*.cdb")))
        self.db_paths = paths
        for path in paths:
            self._load_cdb(path)
        self._load_strings(os.path.join(self.root, "config", "strings.conf"))
        for path in sorted(glob.glob(os.path.join(self.root, "expansions", "*.conf"))):
            self._load_strings(path)

    @classmethod
    def from_dict(cls, data):
        """A database from plain data (tests use this instead of an EDOPro install): {"cards": {id: [name, text,
        strings, type, level, atk, def, race, attribute, alias, setcode]}, "system": {id: text}, "victory": {...}}."""
        db = cls.__new__(cls)
        db.root, db.db_paths, db.counters, db.setnames = None, [], {}, {}
        db.cards = {int(k): Card(int(k), *v) for k, v in data.get("cards", {}).items()}
        db.system = {int(k): v for k, v in data.get("system", {}).items()}
        db.victory = {int(k): v for k, v in data.get("victory", {}).items()}
        return db

    def _load_cdb(self, path):
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            rows = con.execute(
                "select d.id, t.name, t.desc, d.type, d.level, d.atk, d.def, d.race, d.attribute, d.alias, d.setcode, "
                + ", ".join(f"t.str{i}" for i in range(1, 17))
                + " from datas d join texts t on d.id = t.id"
            )
            for row in rows:
                cid, name, desc, typ, level, atk, de, race, attr, alias, setcode = row[:11]
                self.cards[cid] = Card(cid, name or "", desc or "", [s or "" for s in row[11:]], typ or 0,
                                       level or 0, atk or 0, de or 0, race or 0, attr or 0, alias or 0, setcode or 0)
            con.close()
        except sqlite3.Error as e:
            print(f"[carddb] could not read {path}: {e}")

    def _load_strings(self, path):
        if not os.path.exists(path):
            return
        tables = {"!system": self.system, "!victory": self.victory, "!counter": self.counters, "!setname": self.setnames}
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\n").split(" ", 2)
                if len(parts) == 3 and parts[0] in tables:
                    try:
                        key = int(parts[1], 0)
                    except ValueError:
                        continue
                    tables[parts[0]][key] = parts[2]

    @property
    def scripts(self):
        """The card scripts (cardscripts.ScriptIndex), loaded on first use; none for a database built from_dict."""
        if getattr(self, "_scripts", None) is None:
            from .cardscripts import ScriptIndex
            self._scripts = ScriptIndex(self.root)
        return self._scripts

    def get(self, cid):
        return self.cards.get(cid)

    def name(self, cid):
        if not cid:
            return "unknown card"
        card = self.cards.get(cid)
        return card.name if card else f"card #{cid}"

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

    def desc(self, value, card_id=None):
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
