"""Feedback notes from played games, and which of them `ygo-agent learn` has already used.

A note is one line of a game folder's feedback.md, written by a `!note` in the duel chat or the web panel's note box
(agent/gamelog.py, web/recorded.py):

    - (turn 3, right after decision #14; from Web panel) Attack with Gadget before using Limiter Removal.

`learn` marks a note it has used with an indented line right under it, so the file itself says what is pending:

    - (turn 3, right after decision #14; from Web panel) Attack with Gadget before using Limiter Removal.
      - Learned 2026-10-22: new principle in Lethal check; case attack-before-limiter-removal

The older hand-written "  - Processed ..." lines count as learned too.

Whose notes count: the deck's owner is whoever sits at the web panel (it only serves this machine), or the human
who played the agent (`play`: the note's author is the Opponent). A Spectator's note, or an Opponent's in a game
the human didn't play, can come from anyone who joined the room: it is listed but only used when asked to.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass

NOTE = re.compile(r"^- \((.*?)\) (.*)$")
SUB = re.compile(r"^\s+- ")
DONE = re.compile(r"^\s+- (Learned|Processed)\b(.*)$")
DECISION = re.compile(r"decision #(\d+)")
TURN = re.compile(r"\bturn (\d+)")
AUTHOR = re.compile(r";\s*from (.+)$")
_lock = threading.Lock()


@dataclass
class Note:
    game_dir: str            # the game's log folder (absolute)
    game: str                # its folder name
    index: int               # the note's position among the file's notes (0-based)
    line: int                # its line in feedback.md (0-based) when read
    context: str             # "turn 3, right after decision #14"
    author: str              # "Web panel", "Opponent NAME", "Spectator NAME"
    text: str
    decision: int | None
    turn: int | None
    mode: str | None         # meta.json "mode": play, selfplay, teach, coach
    deck: str | None         # meta.json "deck": the deck folder's name
    learned: str | None      # the "Learned …"/"Processed …" line under it, if any

    @property
    def trusted(self) -> bool:
        """The deck owner's own note: typed in the web panel, or by the human who played the agent."""
        return self.author == "Web panel" or (self.author.startswith("Opponent") and self.mode == "play")

    @property
    def pending(self) -> bool:
        return self.learned is None

    @property
    def key(self) -> str:
        """Stable while the file only grows (a "Learned" line doesn't count): the game folder and the note's index."""
        return f"{self.game}:{self.index}"

    def to_dict(self) -> dict:
        return {**asdict(self), "trusted": self.trusted, "pending": self.pending, "key": self.key}


def read(game_dir: str, meta: dict | None = None) -> list[Note]:
    """Every note in the folder's feedback.md, learned or not."""
    game_dir = os.path.abspath(game_dir)
    try:
        with open(os.path.join(game_dir, "feedback.md"), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    meta = read_meta(game_dir) if meta is None else meta
    out: list[Note] = []
    for i, line in enumerate(lines):
        m = NOTE.match(line)
        if m:
            context, author = m.group(1), "Opponent"  # notes from before authors were recorded came from the chat
            a = AUTHOR.search(context)
            if a:
                context, author = context[:a.start()].strip(), a.group(1).strip()
            d, t = DECISION.search(context), TURN.search(context)
            out.append(Note(game_dir, os.path.basename(game_dir), len(out), i, context, author, m.group(2).strip(),
                            int(d.group(1)) if d else None, int(t.group(1)) if t else None,
                            meta.get("mode"), meta.get("deck"), None))
        elif out and SUB.match(line):
            done = DONE.match(line)
            if done and out[-1].learned is None:
                out[-1].learned = line.strip()[2:]
        # other lines end nothing: a note's sub-lines are the indented ones right under it
    return out


def read_meta(game_dir: str) -> dict:
    try:
        with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def deck_games(deck: str, games_dir: str) -> list[str]:
    """The game folders (directly under games_dir) where `deck` (a deck folder's name, any case) played, newest
    first. In a self-play game each seat has its own folder, so only the deck's own seat is listed."""
    want = deck.lower()
    out = []
    try:
        names = os.listdir(games_dir)
    except OSError:
        return []
    for name in names:
        folder = os.path.join(games_dir, name)
        if name == "latest" or os.path.islink(folder) or not os.path.isfile(os.path.join(folder, "meta.json")):
            continue
        if str(read_meta(folder).get("deck") or "").lower() == want:
            out.append(os.path.abspath(folder))
    return sorted(out, key=lambda p: os.path.basename(p), reverse=True)


def for_deck(deck: str, games_dir: str) -> list[Note]:
    """Every note from the deck's games, newest game first."""
    out = []
    for folder in deck_games(deck, games_dir):
        out.extend(read(folder))
    return out


def pending(deck: str, games_dir: str, include_untrusted: bool = False) -> list[Note]:
    """The notes `learn` still has to use: not learned yet, and the owner's own unless `include_untrusted`."""
    return [n for n in for_deck(deck, games_dir) if n.pending and (n.trusted or include_untrusted)]


def mark(note: Note, outcome: str, when: str | None = None) -> bool:
    """Record under the note that `learn` used it ("Learned <date>: <outcome>"). The file is read again right before
    it is rewritten, so a note appended meanwhile (a game still being played) isn't lost, and the note is found by its
    position among the notes (marking another one moves the lines). False when it isn't there any more."""
    path = os.path.join(note.game_dir, "feedback.md")
    entry = f"  - Learned {when or time.strftime('%Y-%m-%d')}: {' '.join(str(outcome).split())[:600] or 'used'}"
    with _lock:
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return False
        at = [i for i, line in enumerate(lines) if NOTE.match(line)]
        if note.index >= len(at) or note.text not in lines[at[note.index]]:
            return False
        at = at[note.index] + 1
        while at < len(lines) and SUB.match(lines[at]):
            at += 1
        lines.insert(at, entry)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    note.learned = entry.strip()[2:]
    return True
