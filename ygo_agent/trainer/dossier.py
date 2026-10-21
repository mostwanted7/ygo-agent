"""The deck dossier: everything the reviewer needs to know about a deck before it has seen a game.

    dossier = build(ydk, db, script_dirs, out_dir)   # writes out_dir/dossier.md, cards.json and scripts/
    dossier.text                                     # the Markdown the study prompt includes

For every card: its count, full text, type line, archetypes (decoded setcodes), the Lua script the engine runs (found
in EDOPro's search order, copied to scripts/c<id>.lua) and automatic hints read off the script (effect types, once-per-
turn limits, costs, "if"/"when" triggers, summon procedures, restrictions). Then the archetype map, the Main Deck's
Levels and Tuners next to the Extra Deck's Ranks/Levels, and each Extra Deck monster's summoning condition.
"""

from __future__ import annotations

import collections
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field

from ..agent.profile import parse_ydk

TYPE_TUNER, TYPE_XYZ, TYPE_SYNCHRO, TYPE_FUSION, TYPE_RITUAL, TYPE_LINK, TYPE_PENDULUM = (
    0x1000, 0x800000, 0x2000, 0x40, 0x80, 0x4000000, 0x1000000)
LIBS = ["utility.lua", "cards_specific_functions.lua", "constant.lua", "archetype_setcode_constants.lua"]
PROC_LIBS = {TYPE_XYZ: "proc_xyz.lua", TYPE_SYNCHRO: "proc_synchro.lua", TYPE_FUSION: "proc_fusion.lua",
             TYPE_RITUAL: "proc_ritual.lua", TYPE_PENDULUM: "proc_pendulum.lua"}
EFFECT_TYPES = [("EFFECT_TYPE_ACTIVATE", "card activation"), ("EFFECT_TYPE_IGNITION", "Ignition"),
                ("EFFECT_TYPE_QUICK_O", "Quick Effect"), ("EFFECT_TYPE_QUICK_F", "mandatory Quick Effect"),
                ("EFFECT_TYPE_TRIGGER_O", "optional trigger"), ("EFFECT_TYPE_TRIGGER_F", "mandatory trigger"),
                ("EFFECT_TYPE_EQUIP", "equip effect"), ("EFFECT_TYPE_FIELD", "field effect"),
                ("EFFECT_TYPE_CONTINUOUS", "continuous"), ("EFFECT_TYPE_SINGLE", "single")]
RESTRICTIONS = re.compile(r"EFFECT_CANNOT_[A-Z_]+|EFFECT_SPSUMMON_CONDITION|EFFECT_CANNOT_BE_[A-Z_]+_MATERIAL|"
                          r"EnableReviveLimit|AddCustomActivityCounter|RegisterFlagEffect|EFFECT_IMMUNE_EFFECT|"
                          r"EFFECT_INDESTRUCTABLE[A-Z_]*")
PROCEDURE = re.compile(r"^\s*((?:Xyz|Synchro|Fusion|Ritual|Pendulum|Link)\.\w+\(.*\)"
                       r"|aux\.Add\w+Procedure\w*\(.*\))\s*$", re.M)


@dataclass
class CardEntry:
    id: int
    name: str
    count: int
    section: str                    # main / extra / side
    type_line: str
    text: str
    kind: str                       # Monster / Spell / Trap
    level: int = 0                  # Level, Rank (Xyz) or Link rating
    tuner: bool = False
    extra_kind: str | None = None   # Xyz / Synchro / Fusion (Extra Deck monsters)
    archetypes: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)   # quoted names in the text ("Geargia", card names)
    script: str | None = None       # scripts/c<id>.lua (relative to the dossier folder), or None if missing
    hints: list[str] = field(default_factory=list)
    procedure: list[str] = field(default_factory=list)  # summon procedure calls from the script
    restrictions: list[str] = field(default_factory=list)


@dataclass
class Dossier:
    name: str
    cards: list[CardEntry]
    text: str
    folder: str
    missing_scripts: list[str] = field(default_factory=list)
    libs: list[str] = field(default_factory=list)

    def card(self, name_or_id) -> CardEntry | None:
        for c in self.cards:
            if c.id == name_or_id or c.name.lower() == str(name_or_id).lower():
                return c
        return None

    def by_name(self) -> dict[str, CardEntry]:
        return {c.name: c for c in self.cards}

    def main_codes(self) -> list[int]:
        return [c.id for c in self.cards if c.section == "main" for _ in range(c.count)]


# ---- setcodes -------------------------------------------------------------------------------------------------

def setcodes(value: int) -> list[int]:
    """The (up to 4) 16-bit archetype codes packed into a card's setcode."""
    return [code for code in ((value >> (16 * i)) & 0xFFFF for i in range(4)) if code]


def in_archetype(card_codes: list[int], archetype: int) -> bool:
    """Card.IsSetCard: the low 12 bits match and the sub-archetype bits of `archetype` are all set."""
    return any((c & 0xFFF) == (archetype & 0xFFF) and (c & archetype & 0xF000) == (archetype & 0xF000)
               for c in card_codes)


# ---- scripts --------------------------------------------------------------------------------------------------

def find_script(code: int, dirs: list[str], alias: int = 0) -> str | None:
    for cid in (code, alias):
        if not cid:
            continue
        for d in dirs:
            path = os.path.join(d, f"c{cid}.lua")
            if os.path.isfile(path):
                return path
    return None


def find_lib(name: str, dirs: list[str]) -> str | None:
    return next((os.path.join(d, name) for d in dirs if os.path.isfile(os.path.join(d, name))), None)


def script_hints(source: str) -> tuple[list[str], list[str], list[str]]:
    """(effect hints, summon procedures, restrictions) read off a card script. Automatic and incomplete: a summary
    to point the reviewer at the right lines, not a replacement for reading them."""
    effects: dict[str, list[str]] = {}
    order = []
    for line in source.splitlines():  # in order, so a Clone() copies what its source had set by then
        m = re.search(r"local\s+(e\d+)\s*=\s*(Effect\.CreateEffect\(\w+\)|(e\d+):Clone\(\))", line)
        if m:
            name = m.group(1)
            if name not in effects:
                order.append(name)
            effects[name] = list(effects.get(m.group(3), [])) if m.group(3) else []
            continue
        m = re.search(r"\b(e\d+):Set(\w+)\((.*)\)\s*$", line)
        if m and m.group(1) in effects:
            effects[m.group(1)].append(f"{m.group(2)}({m.group(3).strip()})")
    hints = []
    for name in order:
        calls = effects[name]
        get = lambda key: [c[len(key) + 1:-1] for c in calls if c.startswith(key + "(")]  # noqa: E731
        types = " ".join(get("Type"))
        kind = next((label for const, label in EFFECT_TYPES if const in types), None)
        bits = [kind] if kind else []
        for code in get("Code"):
            bits.append(code.replace("EVENT_", "on ").replace("EFFECT_", "").lower() if code.startswith("EVENT_")
                        else code)
        for r in get("Range"):
            bits.append(f"range {r.replace('LOCATION_', '').lower()}")
        for limit in get("CountLimit"):
            bits.append(count_limit(limit))
        props = " ".join(get("Property"))
        if "TRIGGER" in types:
            bits.append("'if' (DELAY: doesn't miss timing)" if "EFFECT_FLAG_DELAY" in props else
                        "'when' (no DELAY: can miss timing)")
        if "EFFECT_FLAG_CARD_TARGET" in props:
            bits.append("targets")
        for cost in get("Cost"):
            bits.append(f"cost {cost}")
        if get("Condition"):
            bits.append("has a condition")
        if len(bits) > (1 if kind else 0):
            hints.append(f"{name}: " + ", ".join(bits))
    procedures = [m.group(1) for m in PROCEDURE.finditer(source)]
    restrictions = sorted(set(RESTRICTIONS.findall(source)))
    return hints, procedures, restrictions


def count_limit(arg: str) -> str:
    parts = [p.strip() for p in re.split(r",(?![^{]*})", arg)]
    n = parts[0]
    if len(parts) == 1:
        return f"soft once per turn ({n}x per copy, SetCountLimit({arg}))"
    scope = parts[1]
    flags = " ".join(parts[2:])
    kind = "hard"
    if "OATH" in flags:
        kind = "hard (activation)"
    if "DUEL" in flags:
        return f"once per Duel (SetCountLimit({arg}))"
    shared = "shared with the card's other effects" if scope == "id" else f"key {scope}"
    return f"{kind} {n}x per turn ({shared}, SetCountLimit({arg}))"


def strip_lua(source: str) -> str:
    """A script without its comments and blank lines (inline prompts)."""
    out = []
    for line in source.splitlines():
        line = re.sub(r"--(?!\[\[).*$", "", line).rstrip()
        if line.strip():
            out.append(line)
    return "\n".join(out)


# ---- building -------------------------------------------------------------------------------------------------

def build(ydk: str, db, script_dirs: list[str], out_dir: str, name: str | None = None) -> Dossier:
    main, extra, side = parse_ydk(ydk)
    name = name or os.path.splitext(os.path.basename(ydk))[0]
    scripts_dir = os.path.join(out_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    entries: list[CardEntry] = []
    missing = []
    types_seen = 0
    seen = set()
    for section, ids in (("main", main), ("extra", extra), ("side", side)):
        counts = collections.Counter(ids)
        for cid in dict.fromkeys(ids):
            card = db.get(cid)
            if card is None:
                missing.append(f"card #{cid}: not in the card database")
                continue
            types_seen |= card.type
            entry = CardEntry(cid, card.name, counts[cid], section, card.type_line(), card.text.strip(),
                              "Monster" if card.type & 1 else "Spell" if card.type & 2 else "Trap",
                              level=card.level & 0xFF, tuner=bool(card.type & TYPE_TUNER))
            if card.type & 1 and card.type & (TYPE_XYZ | TYPE_SYNCHRO | TYPE_FUSION | TYPE_LINK):
                entry.extra_kind = ("Xyz" if card.type & TYPE_XYZ else "Synchro" if card.type & TYPE_SYNCHRO
                                    else "Link" if card.type & TYPE_LINK else "Fusion")
            entry.archetypes = [db.setnames.get(code, f"0x{code:x}") for code in setcodes(card.setcode)]
            entry.mentions = list(dict.fromkeys(re.findall(r'"([^"]+)"', card.text)))
            if cid not in seen:
                seen.add(cid)
                src = find_script(cid, script_dirs, card.alias)
                if src:
                    dst = os.path.join(scripts_dir, f"c{cid}.lua")
                    shutil.copyfile(src, dst)
                    entry.script = os.path.relpath(dst, out_dir)
                    with open(src, encoding="utf-8", errors="replace") as f:
                        entry.hints, entry.procedure, entry.restrictions = script_hints(f.read())
                elif not card.type & 0x10 or card.text.strip():  # Normal Monsters need no script
                    missing.append(f"{card.name} (c{cid}.lua)")
            entries.append(entry)
    libs = []
    lib_dir = os.path.join(scripts_dir, "lib")
    wanted = LIBS + [lib for bit, lib in PROC_LIBS.items() if types_seen & bit]
    for lib in wanted:
        src = find_lib(lib, script_dirs)
        if src:
            os.makedirs(lib_dir, exist_ok=True)
            shutil.copyfile(src, os.path.join(lib_dir, lib))
            libs.append(f"scripts/lib/{lib}")
    dossier = Dossier(name, entries, "", out_dir, missing, libs)
    dossier.text = render(dossier, db)
    with open(os.path.join(out_dir, "dossier.md"), "w", encoding="utf-8") as f:
        f.write(dossier.text)
    with open(os.path.join(out_dir, "cards.json"), "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in entries], f, indent=1, ensure_ascii=False)
    return dossier


def archetype_map(dossier: Dossier, db) -> list[str]:
    """Each archetype a card belongs to or names in quotes: its members in the deck and the cards that refer to it."""
    names = {v: k for k, v in db.setnames.items()}
    codes = {}
    for c in dossier.cards:
        card = db.get(c.id)
        for code in setcodes(card.setcode):
            codes[db.setnames.get(code, f"0x{code:x}")] = code
        for m in c.mentions:
            if m in names:
                codes.setdefault(m, names[m])
    lines = []
    for arch, code in sorted(codes.items()):
        members = [c for c in dossier.cards if in_archetype(setcodes(db.get(c.id).setcode), code)]
        refer = [c.name for c in dossier.cards if arch in c.mentions and c not in members]
        refer_in = [c.name for c in members if arch in c.mentions]
        line = f"- **{arch}** (0x{code:x}): members " + (", ".join(f"{c.name} x{c.count}" for c in members) or "none")
        if refer or refer_in:
            line += f"; named in the text of: {', '.join(refer_in + refer)}"
        lines.append(line)
    return lines


def level_tables(dossier: Dossier) -> list[str]:
    main = [c for c in dossier.cards if c.section == "main" and c.kind == "Monster"]
    by_level = collections.defaultdict(list)
    for c in main:
        by_level[c.level].append(c)
    lines = ["Main Deck monsters by Level (copies):"]
    for lv in sorted(by_level):
        cards = by_level[lv]
        lines.append(f"- Lv{lv} ({sum(c.count for c in cards)}): " + ", ".join(
            f"{c.name} x{c.count}" + (" (Tuner)" if c.tuner else "") for c in cards))
    extra = [c for c in dossier.cards if c.section == "extra"]
    if extra:
        lines.append("\nExtra Deck by kind and Rank/Level, with the summoning condition (first line of the text) and "
                     "the script's procedure:")
        for c in sorted(extra, key=lambda c: (c.extra_kind or "", c.level, c.name)):
            star = f"Rank {c.level}" if c.extra_kind == "Xyz" else f"Link-{c.level}" if c.extra_kind == "Link" \
                else f"Lv{c.level}"
            materials = c.text.split("\n")[0].strip()
            proc = f" — `{c.procedure[0]}`" if c.procedure else ""
            same = sum(m.count for m in main if m.level == c.level) if c.extra_kind == "Xyz" else None
            note = f" [Main Deck Lv{c.level}s: {same}]" if same is not None else ""
            lines.append(f"- {c.extra_kind} {star}: **{c.name}** x{c.count}: {materials}{proc}{note}")
    tuners = [c for c in main if c.tuner]
    if any(c.extra_kind == "Synchro" for c in extra):
        lines.append("\nTuners in the Main Deck: " + (", ".join(f"{c.name} (Lv{c.level}) x{c.count}" for c in tuners)
                                                      or "none"))
    return lines


def render(dossier: Dossier, db) -> str:
    main = [c for c in dossier.cards if c.section == "main"]
    extra = [c for c in dossier.cards if c.section == "extra"]
    side = [c for c in dossier.cards if c.section == "side"]
    out = [f"# Dossier: {dossier.name}", ""]
    out.append(f"Main Deck {sum(c.count for c in main)} cards, Extra Deck {sum(c.count for c in extra)}"
               + (f", Side Deck {sum(c.count for c in side)}" if side else "") + ".")
    out += ["", "## Decklist", ""]
    for title, cards in (("Main Deck", main), ("Extra Deck", extra), ("Side Deck", side)):
        if cards:
            out.append(f"{title}:")
            out += [f"- {c.count}x {c.name} [{c.type_line}]" for c in cards]
            out.append("")
    out += ["## Archetypes", ""] + archetype_map(dossier, db) + [""]
    out += ["## Levels, Ranks and summoning conditions", ""] + level_tables(dossier) + [""]
    out += ["## Cards", "",
            "Each card: its text, then hints read automatically off its script (effect types, once-per-turn limits "
            "with their SetCountLimit, costs, 'if'/'when' triggers, procedures, restrictions). The hints can be "
            "incomplete: the script itself is the authority.", ""]
    for c in main + extra + side:
        out.append(f"### {c.name} (x{c.count}, {c.section}) — {c.type_line}")
        if c.archetypes:
            out.append(f"Archetypes: {', '.join(c.archetypes)}")
        out.append(c.text)
        if c.script:
            out.append(f"Script: {c.script}")
        else:
            out.append("Script: none found")
        if c.procedure:
            out.append("Procedure: " + "; ".join(f"`{p}`" for p in c.procedure))
        if c.hints:
            out.append("Script hints: " + " | ".join(c.hints))
        if c.restrictions:
            out.append("Restrictions in the script: " + ", ".join(c.restrictions))
        out.append("")
    if dossier.missing_scripts:
        out += ["## Missing", ""] + [f"- {m}" for m in dossier.missing_scripts] + [""]
    return "\n".join(out)


def scripts_text(dossier: Dossier, names=None, limit: int | None = None) -> str:
    """The (comment-stripped) scripts of some cards (all by default), for inline prompts."""
    parts = []
    for c in dossier.cards:
        if not c.script or (names is not None and c.name not in names and c.id not in names):
            continue
        if any(p.startswith(f"### {c.script}") for p in parts):
            continue
        with open(os.path.join(dossier.folder, c.script), encoding="utf-8", errors="replace") as f:
            body = strip_lua(f.read())
        parts.append(f"### {c.script} — {c.name}\n```lua\n{body}\n```")
    text = "\n\n".join(parts)
    return text[:limit] if limit else text


def load(out_dir: str, name: str, db) -> Dossier:
    """A dossier built earlier (resume)."""
    with open(os.path.join(out_dir, "cards.json"), encoding="utf-8") as f:
        cards = [CardEntry(**c) for c in json.load(f)]
    with open(os.path.join(out_dir, "dossier.md"), encoding="utf-8") as f:
        text = f.read()
    libs = sorted(f"scripts/lib/{x}" for x in os.listdir(os.path.join(out_dir, "scripts", "lib"))) \
        if os.path.isdir(os.path.join(out_dir, "scripts", "lib")) else []
    return Dossier(name, cards, text, out_dir, [], libs)
