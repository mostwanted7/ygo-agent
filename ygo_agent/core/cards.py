"""Card data from EDOPro's .cdb files, in the form the core asks for (OCG_CardData) and for display."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from .constants import (SCOPE_LEGEND, SCOPE_RUSH, TYPE_FUSION, TYPE_LINK, TYPE_MONSTER, TYPE_RITUAL,
                        TYPE_SYNCHRO, TYPE_TOKEN, TYPE_XYZ)

_SELECT = ("select d.id, d.ot, d.alias, d.setcode, d.type, d.atk, d.def, d.level, d.race, d.attribute, "
           "d.category, t.name, t.desc, " + ", ".join(f"t.str{i}" for i in range(1, 17)) +
           " from datas d left join texts t on t.id = d.id")


def cdb_rows(path: str):
    """The rows of one .cdb, read-only: (id, ot, alias, setcode, type, atk, def, level, race, attribute, category,
    name, desc, str1..str16), with the texts columns None for a card that has no text row. The one place that
    reads EDOPro's card databases; the agent's CardDB and the core's CardDatabase both build on it."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        yield from con.execute(_SELECT)
    finally:
        con.close()


@dataclass(slots=True)
class CardData:
    code: int
    alias: int
    setcodes: tuple[int, ...]
    type: int
    level: int          # as the core wants it: negative levels kept, scales split off
    attribute: int
    race: int
    attack: int
    defense: int        # 0 for Link monsters (the cdb stores link markers in `def`)
    lscale: int
    rscale: int
    link_marker: int
    ot: int = 0
    category: int = 0
    name: str = ""
    text: str = ""
    strings: tuple[str, ...] = field(default=(), repr=False)

    @property
    def is_extra_deck(self) -> bool:
        """EDOPro's DeckManager rule: Fusion/Synchro/Xyz and Link monsters go to the Extra Deck."""
        if self.type & (TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ):
            return True
        return bool(self.type & TYPE_LINK and self.type & TYPE_MONSTER)

    @property
    def is_ritual_monster(self) -> bool:
        return bool(self.type & TYPE_RITUAL and self.type & TYPE_MONSTER)

    @property
    def is_token(self) -> bool:
        return bool(self.type & TYPE_TOKEN)

    @property
    def is_rush(self) -> bool:
        return bool(self.ot & SCOPE_RUSH)

    @property
    def is_legend(self) -> bool:
        return bool(self.ot & SCOPE_LEGEND)

    @property
    def base_code(self) -> int:
        """The code deck-limit checks count by (alternate artworks share their original's code)."""
        return self.alias or self.code


def _row_to_card(row) -> CardData:
    code, ot, alias, setcode, ctype, atk, dfn, level, race, attr, category, name, desc = row[:13]
    setcodes = tuple(s for s in ((setcode >> (16 * i)) & 0xFFFF for i in range(4)) if s)
    link_marker = 0
    if ctype & TYPE_LINK:
        link_marker, dfn = dfn, 0
    lv = -(level & 0xFF) if level < 0 else level & 0xFF
    return CardData(code=code, alias=alias, setcodes=setcodes, type=ctype, level=lv, attribute=attr,
                    race=race, attack=atk, defense=dfn, lscale=(level >> 24) & 0xFF,
                    rscale=(level >> 16) & 0xFF, link_marker=link_marker, ot=ot, category=category,
                    name=name or "", text=desc or "", strings=tuple(s or "" for s in row[13:29]))


class CardDatabase:
    """All cards from a list of .cdb files; a later file overrides an earlier one (EDOPro ParseDB)."""

    def __init__(self, paths: list[str]):
        self.paths = list(paths)
        self.cards: dict[int, CardData] = {}
        for path in self.paths:
            for row in cdb_rows(path):
                self.cards[row[0]] = _row_to_card(row)

    def __contains__(self, code: int) -> bool:
        return code in self.cards

    def __len__(self) -> int:
        return len(self.cards)

    def get(self, code: int) -> CardData | None:
        return self.cards.get(code)

    def name(self, code: int) -> str:
        card = self.cards.get(code)
        return card.name if card and card.name else (f"#{code}" if code else "?")

    def find(self, name: str) -> list[CardData]:
        """Exact (case-insensitive) name match first, else substring match."""
        key = name.strip().lower()
        exact = [c for c in self.cards.values() if c.name.lower() == key]
        return exact or [c for c in self.cards.values() if key in c.name.lower()]

    def resolve(self, ref: str | int) -> int:
        """A card code from `"12345"`, `12345` or a unique name."""
        if isinstance(ref, int) or str(ref).strip().isdigit():
            return int(ref)
        matches = self.find(str(ref))
        if not matches:
            raise KeyError(f"no card named {ref!r}")
        real = {c.code for c in matches if not c.alias}
        if len(real) != 1:
            names = ", ".join(sorted({c.name for c in matches})[:8])
            raise KeyError(f"card name {ref!r} is ambiguous: {names}")
        return real.pop()


class Strings:
    """`!system` / `!victory` / `!counter` / `!setname` entries from strings.conf (later files override)."""

    _LINE = re.compile(r"^!(\w+)\s+(0x[0-9a-fA-F]+|\d+)\s+(.*)$")

    def __init__(self, paths: list[str] = ()):
        self.tables: dict[str, dict[int, str]] = {}
        for path in paths:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        m = self._LINE.match(line.rstrip("\r\n"))
                        if m:
                            self.tables.setdefault(m.group(1), {})[int(m.group(2), 0)] = m.group(3)
            except OSError:
                continue

    def get(self, table: str, key: int, default: str = "") -> str:
        return self.tables.get(table, {}).get(key, default)

    def system(self, key: int) -> str:
        return self.get("system", key)
