"""tips.md: the deck owner's own advice about how the deck plays, in their words.

The trainer's interview asks the owner a few questions about the deck and saves the answers here; the study writes the
playbook from them, every later review sees them (so a lesson never contradicts the owner without saying why), and
`ygo-agent learn` folds in tips added afterwards (`learn --tip`, the web app). The playbook is what the player reads;
this file is the owner's record, so nothing but the owner and these helpers writes it. Each tip is a section:

    ## <the question, or "Tip"> (2026-10-22)
    <the answer>
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

FILE = "tips.md"
HEADER = ("# Tips for {name}\n\n"
          "The deck owner's advice, in their own words. The trainer writes the playbook from it and `ygo-agent learn` "
          "folds new tips in. Edit freely.\n")
SECTION = re.compile(r"^## (.+?)(?: \((\d{4}-\d{2}-\d{2})\))?\s*$")


def path(deck_dir: str) -> str:
    return os.path.join(deck_dir, FILE)


def read(deck_dir: str) -> str:
    """The file's text, "" when there is none."""
    try:
        with open(path(deck_dir), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def entries(deck_dir: str) -> list[dict]:
    """[{"title", "date" (or None), "text"}] in file order. Text before the first section isn't a tip."""
    out = []
    for line in read(deck_dir).splitlines():
        m = SECTION.match(line)
        if m:
            out.append({"title": m.group(1).strip(), "date": m.group(2), "text": ""})
        elif out:
            out[-1]["text"] += line + "\n"
    for e in out:
        e["text"] = e["text"].strip()
    return [e for e in out if e["text"]]


def add(deck_dir: str, text: str, title: str = "Tip", name: str | None = None) -> bool:
    """Append one tip, dated today. False (nothing written) when the text is empty."""
    return save_answers(deck_dir, [{"question": title, "answer": text}], name) == 1


def save_answers(deck_dir: str, answers: list[dict], name: str | None = None) -> int:
    """Append the non-empty answers ([{"question", "answer"}]) as tips titled by their question; returns how many.
    `name`: the deck's display name for the header of a new file (default: the folder's name)."""
    keep = [(one_line(a.get("question") or "Tip") or "Tip", str(a.get("answer") or "").strip()) for a in answers]
    keep = [(q, a) for q, a in keep if a]
    if not keep:
        return 0
    os.makedirs(deck_dir, exist_ok=True)
    current = read(deck_dir)
    today = time.strftime("%Y-%m-%d")
    parts = [current.rstrip("\n") + "\n" if current else HEADER.format(name=name or os.path.basename(deck_dir))]
    for question, answer in keep:
        # A line starting "## " inside an answer would read back as a new section.
        answer = re.sub(r"(?m)^(#{1,6} )", r"\\\1", answer)
        parts.append(f"\n## {question} ({today})\n\n{answer}\n")
    with open(path(deck_dir), "w", encoding="utf-8") as f:
        f.write("".join(parts))
    return len(keep)


def digest(deck_dir: str) -> str:
    """A hash of the file ("" when there is none): `learn` compares it with the one it last folded in."""
    text = read(deck_dir)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text.strip() else ""


def key(tip: dict) -> str:
    """A tip's identity (its title and text), to tell the ones a playbook already took in from new or edited ones."""
    return hashlib.sha1(f"{tip['title']}\n{' '.join(tip['text'].split())}".encode()).hexdigest()[:12]


def seen(deck_dir: str) -> set[str]:
    """The keys of the tips the playbook has taken in, kept in deck.json ("tips_seen") so a shared deck carries
    them (train/ isn't shared)."""
    try:
        with open(os.path.join(deck_dir, "deck.json"), encoding="utf-8") as f:
            return set(json.load(f).get("tips_seen") or [])
    except (OSError, ValueError, AttributeError):
        return set()


def remember(deck_dir: str, tips: list[dict]) -> None:
    """Record that the playbook now reflects these tips (in deck.json; nothing happens without one)."""
    path = os.path.join(deck_dir, "deck.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    if not tips and "tips_seen" not in data:
        return
    data["tips_seen"] = sorted({key(t) for t in tips})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def one_line(text: str, limit: int = 200) -> str:
    return " ".join(str(text).split())[:limit]
