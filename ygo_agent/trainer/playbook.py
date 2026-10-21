"""Playbook edits from the reviewer's JSON: section replacements, dated lessons, verified-line markers, and the
evidence check that keeps unverified lessons out.

A playbook is Markdown split by "## " headings. The lessons section comes first (newest lessons on top); the trainer
adds lessons there itself, so a section replacement can never rewrite or drop them.
"""

from __future__ import annotations

import difflib
import os
import re

LESSONS_HEADING = "## Lessons from games (newest first; these override everything below)"
NO_LESSONS = "None yet: lessons from reviewed games go here."
REQUIRED = ("game plan", "engine cards", "extra deck", "main lines")
TARGET_KB = (8, 13)
LIMIT_BYTES = 14500  # above this the round ends with a condense pass


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
    return k.startswith("lessons") or k.startswith("coaching lessons")


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
    before "General principles" (or at the end) when it's new, delete it when content is empty. The lessons section
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
        if is_lessons(heading):
            changes.append(f"ignored a replacement of the lessons section ({heading})")
            continue
        i = find(sections, heading)
        if i is None:
            if not content.strip():
                continue
            at = find(sections, "## General principles")
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
    sections = split(text)
    if not any(is_lessons(h) for h, _ in sections):
        sections.insert(0 if sections and sections[0][0] is not None else 1 if sections else 0,
                        (LESSONS_HEADING, NO_LESSONS))
    return join(sections)


def add_lessons(text: str, header: str, lessons: list[str], intro: str | None = None) -> str:
    """Put a dated "### header" block with numbered lessons at the top of the lessons section."""
    if not lessons:
        return text
    sections = split(ensure_lessons(text))
    i = next(k for k, (h, _) in enumerate(sections) if is_lessons(h))
    heading, body = sections[i]
    body = body.replace(NO_LESSONS, "").strip("\n")
    lead, rest = [], body
    if body and not body.lstrip().startswith("###"):
        # keep the section's intro paragraph (before the first ### block) on top
        parts = re.split(r"(?m)^(?=### )", body, maxsplit=1)
        lead, rest = [parts[0].strip("\n")], parts[1] if len(parts) > 1 else ""
    elif intro and not body:
        lead = [intro]
    block = f"### {header}\n" + "\n".join(f"{n}. {clean_lesson(t)}" for n, t in enumerate(lessons, 1))
    sections[i] = (heading, "\n\n".join(p for p in lead + [block, rest.strip("\n")] if p))
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
    """What a playbook in the house style must not lack."""
    out = []
    keys = [key(h) for h, _ in split(text) if h]
    for want in REQUIRED:
        if not any(k.startswith(want) or want in k for k in keys):
            out.append(f"no '{want}' section")
    if not any(is_lessons("## " + k) for k in keys):
        out.append("no lessons section")
    size = len(text.encode())
    if size > LIMIT_BYTES:
        out.append(f"{size / 1024:.1f} KB, over the {TARGET_KB[1]} KB target")
    return out


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

    scripts_dir: the deck's scripts (c<id>.lua). logs: {name: path} of game logs the reviewer saw (game.md; a
    "decision" number must exist there). card_texts: {card name: text}."""

    def __init__(self, scripts_dir: str, logs: dict[str, str] | None = None, card_texts: dict[str, str] | None = None):
        self.scripts_dir = scripts_dir
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
        return self._read(os.path.join(self.scripts_dir, name))

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
