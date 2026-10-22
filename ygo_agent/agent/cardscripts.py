"""What a card's Lua script says about its effects, for describe.py: which card string labels which effect, where
each effect works from (SetRange) and what it does (SetCode, e.g. EFFECT_CANNOT_ATTACK). An option's text is the
label the script gave the effect (SetDescription), and scripts sometimes reuse one label for different effects, or
give an effect the wrong one (Blackwing - Vata's on-field effect is labelled "Special Summon this card"). Only
s.initial_effect is read, line by line, the way the official scripts are written; anything it can't follow is simply
left out.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

RANGES = {"LOCATION_DECK": 0x1, "LOCATION_HAND": 0x2, "LOCATION_MZONE": 0x4, "LOCATION_SZONE": 0x8,
          "LOCATION_GRAVE": 0x10, "LOCATION_REMOVED": 0x20, "LOCATION_EXTRA": 0x40, "LOCATION_FZONE": 0x100,
          "LOCATION_PZONE": 0x200, "LOCATION_ONFIELD": 0xC}

_INIT = re.compile(r"^function\s+[\w.]+\.initial_effect\s*\(")
_CREATE = re.compile(r"^\s*(?:local\s+)?(\w+)\s*=\s*Effect\.CreateEffect\(")
_CLONE = re.compile(r"^\s*(?:local\s+)?(\w+)\s*=\s*(\w+):Clone\(\)")
_DESC = re.compile(r"^\s*(\w+):SetDescription\(\s*aux\.Stringid\(\s*(id|\d+)\s*,\s*(\d+)\s*\)\s*\)")
_RANGE = re.compile(r"^\s*(\w+):SetRange\(([^)]*)\)")
_CODE = re.compile(r"^\s*(\w+):SetCode\(\s*(\w+)\s*\)")
_HINT = re.compile(r"^\s*(\w+):SetProperty\(.*EFFECT_FLAG_CLIENT_HINT")
_REGISTER = re.compile(r"^\s*c:RegisterEffect\(\s*(\w+)")


@dataclass
class Effect:
    family: int                       # its Effect.CreateEffect; a Clone() belongs to the effect it copies
    label: tuple[int, int] | None = None   # (card code, string index) of its SetDescription
    range: int | None = None          # SetRange as location bits
    hint: bool = False                # a client hint (EFFECT_FLAG_CLIENT_HINT), not something to activate
    code: str | None = None           # SetCode, as written (EFFECT_DISABLE, EVENT_SUMMON_SUCCESS, ...)
    registered: bool = False


def parse(source: str, code: int) -> list[Effect]:
    """The effects s.initial_effect registers on the card."""
    effects, current, family, inside = [], {}, 0, False
    for line in source.splitlines():
        if not inside:
            inside = bool(_INIT.match(line))
            continue
        if line.rstrip() == "end":
            break
        if m := _CREATE.match(line):
            family += 1
            current[m.group(1)] = Effect(family)
            effects.append(current[m.group(1)])
        elif m := _CLONE.match(line):
            src = current.get(m.group(2))
            if src is not None:
                current[m.group(1)] = Effect(src.family, src.label, src.range, src.hint, src.code)
                effects.append(current[m.group(1)])
        elif m := _DESC.match(line):
            if m.group(1) in current:
                owner = code if m.group(2) == "id" else int(m.group(2))
                current[m.group(1)].label = (owner, int(m.group(3)))
        elif m := _RANGE.match(line):
            if m.group(1) in current:
                bits = [RANGES.get(part.strip()) for part in re.split(r"[+|]", m.group(2))]
                current[m.group(1)].range = None if None in bits else sum(bits)
        elif m := _CODE.match(line):
            if m.group(1) in current:
                current[m.group(1)].code = m.group(2)
        elif m := _HINT.match(line):
            if m.group(1) in current:
                current[m.group(1)].hint = True
        elif m := _REGISTER.match(line):
            if m.group(1) in current:
                current[m.group(1)].registered = True
    return [e for e in effects if e.registered and not e.hint]


class ScriptIndex:
    """Card scripts from the EDOPro install (its search order), parsed once per card. `sources` ({code: Lua text})
    stands in for the install in tests."""

    def __init__(self, edopro_dir: str | None = None, sources: dict[int, str] | None = None):
        self.root = edopro_dir
        self.sources = sources
        self._dirs = None
        self._cache: dict[int, list[Effect]] = {}

    @property
    def dirs(self) -> list[str]:
        if self._dirs is None:
            self._dirs = []
            if self.root:
                from ..core.install import EdoproInstall, InstallError
                try:
                    self._dirs = EdoproInstall.find(self.root).script_dirs
                except (InstallError, OSError):
                    pass
        return self._dirs

    def source(self, code: int) -> str | None:
        if self.sources is not None:
            return self.sources.get(code)
        for d in self.dirs:
            path = os.path.join(d, f"c{code}.lua")
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    return f.read()
        return None

    def effects(self, code: int) -> list[Effect]:
        if code not in self._cache:
            source = self.source(code) if code else None
            self._cache[code] = parse(source, code) if source else []
        return self._cache[code]

    def labelled(self, code: int, label: tuple[int, int]) -> list[Effect]:
        """The card's effects that carry this label."""
        return [e for e in self.effects(code) if e.label == label]

    def codes(self, code: int) -> set[str]:
        """The SetCode of every effect the card registers on itself."""
        return {e.code for e in self.effects(code) if e.code}
