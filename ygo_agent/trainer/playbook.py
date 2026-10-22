"""Playbook edits from the reviewer's JSON: section replacements, dated pitfalls, verified-line markers, and the
evidence check that keeps unverified lessons out.

A playbook is Markdown split by "## " headings, principles first (TEMPLATE). The last section, Known pitfalls, holds
the specific mistakes from reviewed games (newest on top); the trainer adds them there itself, so a section
replacement can never rewrite or drop them. Older playbooks (decks/blackwing) keep their lessons section on top; it
counts as the same section. A section the deck's owner writes (Saffira's "Coaching lessons") is theirs: no edit,
condense or pitfall ever goes into it (`is_owner`, `keep_owner`).
"""

from __future__ import annotations

import difflib
import os
import re

LESSONS_HEADING = "## Known pitfalls (from reviewed games, newest first)"
NO_LESSONS = "None yet: specific mistakes from reviewed games go here, one or two lines each."
# The house style: (heading, required). Pitfalls always come last.
TEMPLATE = (("## How to use this playbook", True), ("## Game plan", True), ("## Card roles", True),
            ("## Situational considerations", True), ("## Lethal check", False),
            ("## Going second / breaking boards", False), ("## Example sequences", False), (LESSONS_HEADING, True))
REQUIRED = ("how to use", "game plan", "card roles", "situational considerations")
OWNER = ("coaching lessons", "owner")  # headings of sections the deck's owner writes
TARGET_KB = (5, 8)
LIMIT_BYTES = 8704  # above this (8.5 KB) a condense pass tightens it


# ---- sections -------------------------------------------------------------------------------------------------

def split(text: str) -> list[tuple[str | None, str]]:
    """[(heading line or None for the preamble, body)], in order."""
    sections: list[tuple[str | None, str]] = []
    heading, body = None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None or any(b.strip() for b in body):
                sections.append((heading, "\n".join(body).strip("\n")))
            heading, body = line.rstrip(), []
        else:
            body.append(line)
    if heading is not None or any(b.strip() for b in body):
        sections.append((heading, "\n".join(body).strip("\n")))
    return sections


def join(sections: list[tuple[str | None, str]]) -> str:
    parts = []
    for heading, body in sections:
        parts.append((heading + "\n\n" + body if body else heading) if heading else body)
    return "\n\n".join(p.strip("\n") for p in parts if p is not None).strip() + "\n"


def key(heading: str | None) -> str:
    """A heading's identity: lower case, no #, no parenthetical, no trailing colon."""
    if heading is None:
        return ""
    h = re.sub(r"^#+\s*", "", heading.strip()).lower()
    h = re.sub(r"\([^)]*\)", "", h)
    return re.sub(r"[\s:—-]+$", "", re.sub(r"\s+", " ", h)).strip()


def is_lessons(heading: str | None) -> bool:
    k = key(heading)
    return k.startswith(("lessons", "coaching lessons", "known pitfalls", "pitfalls"))


def is_owner(heading: str | None) -> bool:
    """A section the deck's owner writes, in their words (Saffira's "Coaching lessons"): never edited by the trainer."""
    k = key(heading)
    return bool(k) and (k.startswith(OWNER[0]) or any(word in k for word in OWNER[1:]))


def keep_owner(before: str, after: str) -> str:
    """`after` (a condensed or revised whole playbook) with the owner's sections exactly as they are in `before`, at
    the same place."""
    owned = [(i, h, b) for i, (h, b) in enumerate(split(before)) if is_owner(h)]
    if not owned:
        return after
    sections = [(h, b) for h, b in split(after) if not is_owner(h)]
    for i, h, b in owned:
        sections.insert(min(i, len(sections)), (h, b))
    return join(sections)


def find(sections, heading) -> int | None:
    k = key(heading)
    for i, (h, _) in enumerate(sections):
        if h is not None and key(h) == k:
            return i
    for i, (h, _) in enumerate(sections):  # "Main lines" matches "Main lines: Simoon + any Blackwing"
        if h is not None and (key(h).startswith(k) or k.startswith(key(h))) and min(len(k), len(key(h))) >= 6:
            return i
    return None


def apply_sections(text: str, replacements: list[dict]) -> tuple[str, list[str]]:
    """Apply [{"heading": "## X", "content": "..."}]: replace that section's body (matched by heading), add it
    before Known pitfalls (or at the end) when it's new, delete it when content is empty. The pitfalls section
    can't be replaced here. Returns (new text, change descriptions)."""
    sections = split(text)
    changes = []
    for r in replacements or []:
        heading = (r.get("heading") or "").strip()
        content = strip_heading(r.get("content") or "", heading).strip("\n")
        if not heading:
            continue
        if not heading.startswith("## "):
            heading = "## " + heading.lstrip("# ")
        if is_lessons(heading) or is_owner(heading):
            changes.append(f"ignored a replacement of the {'owner' if is_owner(heading) else 'lessons'} section "
                           f"({heading})")
            continue
        i = find(sections, heading)
        if i is not None and (is_lessons(sections[i][0]) or is_owner(sections[i][0])):
            changes.append(f"ignored a replacement of {sections[i][0]} (as {heading})")  # "## Known" matched it
            continue
        if i is None:
            if not content.strip():
                continue
            at = next((k for k, (h, _) in enumerate(sections) if is_lessons(h) and k > 0), None)
            at = find(sections, "## General principles") if at is None else at
            at = len(sections) if at is None else at
            sections.insert(at, (heading, content))
            changes.append(f"added {heading}")
        elif not content.strip():
            changes.append(f"removed {sections[i][0]}")
            del sections[i]
        else:
            old = sections[i][1]
            if old.strip() != content.strip():
                sections[i] = (sections[i][0] if key(sections[i][0]) == key(heading) else heading, content)
                changes.append(f"rewrote {heading} ({len(old)} → {len(content)} chars)")
    return join(sections), changes


def strip_heading(content: str, heading: str) -> str:
    """Section content the model returned with its own heading repeated on top."""
    lines = content.strip("\n").splitlines()
    if lines and lines[0].startswith("## ") and key(lines[0]) == key(heading):
        return "\n".join(lines[1:])
    return content


def ensure_lessons(text: str) -> str:
    """The pitfalls section exists (added last when missing)."""
    sections = split(text)
    if not any(is_lessons(h) for h, _ in sections):
        sections.append((LESSONS_HEADING, NO_LESSONS))
    return join(sections)


def add_lessons(text: str, tag: str, lessons: list[str], intro: str | None = None) -> str:
    """Put each lesson as a bullet ending in *(tag)* (the date and the game) at the top of the pitfalls section,
    below its intro line if it has one."""
    if not lessons:
        return text
    sections = split(ensure_lessons(text))
    i = next((k for k, (h, _) in enumerate(sections) if is_lessons(h) and not is_owner(h)), None)
    if i is None:  # the only lessons section is the owner's: the pitfalls get their own, last
        sections.append((LESSONS_HEADING, NO_LESSONS))
        i = len(sections) - 1
    heading, body = sections[i]
    body = body.replace(NO_LESSONS, "").strip("\n")
    lead, rest = [], body
    first = re.search(r"(?m)^(?:[-*] |\d+[.)] |### )", body)
    if body and (first is None or first.start() > 0):
        lead, rest = [body[:first.start() if first else len(body)].strip("\n")], body[first.start():] if first else ""
    elif intro and not body:
        lead = [intro]
    block = "\n".join(f"- {clean_lesson(t)} *({tag})*" for t in lessons)
    sections[i] = (heading, "\n\n".join(p for p in lead + [block + ("\n" + rest.strip("\n") if rest.strip() else "")]
                                        if p))
    return join(sections)


def clean_lesson(text: str) -> str:
    text = re.sub(r"^\s*(\d+[.)]|[-*])\s+", "", text.strip())
    return re.sub(r"\n\s*", " ", text)


def mark_verified(text: str, names: list[str], marker: str = "verified in lab") -> tuple[str, list[str]]:
    """Lines whose name appears on a line still marked *(unverified)*: swap the mark for *(marker)*."""
    changed = []
    out = []
    for line in text.splitlines():
        if "unverified" in line.lower():
            for name in names:
                if name and norm(name) and norm(name) in norm(line):
                    line = re.sub(r"\*?\((?:still )?unverified\)\*?", f"*({marker})*", line, flags=re.I)
                    changed.append(name)
                    break
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), changed


def problems(text: str) -> list[str]:
    """What a playbook in the house style must not lack: the required sections, Known pitfalls last, the size."""
    out = []
    keys = [key(h) for h, _ in split(text) if h]
    for want in REQUIRED:
        if not any(k.startswith(want) or want in k for k in keys):
            out.append(f"no '{want}' section")
    if not any(is_lessons("## " + k) for k in keys):
        out.append("no known pitfalls section")
    elif not is_lessons("## " + keys[-1]):
        out.append("known pitfalls is not the last section")
    size = len(text.encode())
    if size > LIMIT_BYTES:
        out.append(f"{size / 1024:.1f} KB, over the {TARGET_KB[1]} KB target")
    return out


def new_problems(before: str, after: str) -> list[str]:
    """The problems `after` has that `before` didn't (size aside): a rewrite may not lose a section, but a hand-written
    playbook outside the house style isn't held to it."""
    old = set(problems(before))
    return [p for p in problems(after) if "KB" not in p and p not in old]


def house_style(text: str) -> bool:
    """Has the house style's required sections (a trained playbook, or one rewritten in that style)."""
    return not [p for p in problems(text) if p.startswith("no '")]


def size_kb(text: str) -> float:
    return round(len(text.encode()) / 1024, 1)


# ---- evidence ---------------------------------------------------------------------------------------------------

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text).lower())).strip()


def quote_found(quote: str, text: str) -> bool:
    """Is `quote` in `text`, give or take punctuation, whitespace and a few words (models misquote slightly)?"""
    q, t = norm(quote), norm(text)
    if not q or len(q) < 6:
        return False
    if q in t:
        return True
    qt, tt = q.split(), t.split()
    if len(qt) < 4:
        return False
    m = difflib.SequenceMatcher(None, qt, tt, autojunk=False).find_longest_match(0, len(qt), 0, len(tt))
    return m.size >= max(4, int(0.7 * len(qt)))


class Evidence:
    """Checks the reviewer's evidence against the files it claims to quote.

    scripts_dir: the deck's scripts (c<id>.lua); more_scripts: other folders of scripts (e.g. the opponent's cards a
    game showed). logs: {name: path} of game logs the reviewer saw (game.md; a "decision" number must exist there).
    card_texts: {card name: text}."""

    def __init__(self, scripts_dir: str, logs: dict[str, str] | None = None, card_texts: dict[str, str] | None = None,
                 more_scripts: list[str] | None = None):
        self.scripts_dir = scripts_dir
        self.more_scripts = list(more_scripts or [])
        self.logs = logs or {}
        self.card_texts = card_texts or {}
        self._cache: dict[str, str] = {}

    def _read(self, path: str) -> str:
        if path not in self._cache:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    self._cache[path] = f.read()
            except OSError:
                self._cache[path] = ""
        return self._cache[path]

    def script(self, file: str) -> str:
        name = os.path.basename(str(file or "")).strip()
        lib = os.path.join(self.scripts_dir, "lib", name)
        if name and os.path.isfile(lib):
            return self._read(lib)
        if not re.fullmatch(r"c\d+\.lua", name):
            m = re.search(r"c?(\d{3,})", name)
            name = f"c{m.group(1)}.lua" if m else name
        for folder in [self.scripts_dir] + self.more_scripts:
            if os.path.isfile(os.path.join(folder, name)):
                return self._read(os.path.join(folder, name))
        return ""

    def check(self, item: dict) -> tuple[bool, str]:
        source = (item.get("source") or "").lower()
        quote = item.get("quote") or ""
        if source == "script":
            text = self.script(item.get("file") or "")
            if not text:
                return False, f"no script {item.get('file')!r}"
            return (True, f"script {item.get('file')}") if quote_found(quote, text) else (
                False, f"quote not in {item.get('file')}: {quote[:60]!r}")
        if source in ("log", "game", "engine"):
            logs = self.logs
            if item.get("file") and item["file"] in logs:
                logs = {item["file"]: logs[item["file"]]}
            for name, path in logs.items():
                text = self._read(path)
                decision = item.get("decision")
                if decision and f"Decision #{int(decision)}**" not in text:
                    continue
                if quote_found(quote, text):
                    return True, f"log {name}" + (f" #{decision}" if decision else "")
            return False, f"quote not found in the log: {quote[:60]!r}"
        if source in ("card", "card_text", "text"):
            for name, text in self.card_texts.items():
                if quote_found(quote, text):
                    return True, f"card text of {name}"
            return False, f"quote not in any card text: {quote[:60]!r}"
        return False, f"unknown evidence source {source!r}"

    def verify(self, items: list[dict]) -> tuple[bool, list[str]]:
        """(any item checks out, notes); a lesson needs at least one script or log item that does."""
        notes, ok = [], False
        for item in items or []:
            good, note = self.check(item)
            ok = ok or (good and (item.get("source") or "").lower() in ("script", "log", "game", "engine"))
            notes.append(("✓ " if good else "✗ ") + note)
        return ok, notes
