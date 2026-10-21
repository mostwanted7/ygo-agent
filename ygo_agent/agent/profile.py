"""A deck profile: decks/<key>/ with deck.json, the .ydk, the playbook, rules.py and saved test cases."""

import collections
import json
import os

from .. import paths
from ..config import deck_overrides
from . import prompts


def parse_ydk(path):
    """(main, extra, side) card id lists from a .ydk file."""
    main, extra, side = [], [], []
    section = main
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line == "#main":
                section = main
            elif line == "#extra":
                section = extra
            elif line == "!side":
                section = side
            elif line.isdigit():
                section.append(int(line))
    return main, extra, side


def deck_keys():
    return sorted(k for k in os.listdir(paths.DECKS) if os.path.exists(os.path.join(paths.DECKS, k, "deck.json")))


class Profile:
    """The deck being played: decklist, card texts and the coaching playbook."""

    def __init__(self, deck_key, db, cfg=None):
        self.key = deck_key
        self.dir = os.path.join(paths.DECKS, deck_key)
        json_path = os.path.join(self.dir, "deck.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"no deck profile {deck_key!r}: {json_path} is missing "
                                    f"(decks: {', '.join(deck_keys())})")
        with open(json_path, encoding="utf-8") as f:
            self.settings = json.load(f)
        # config.local.toml [decks.<key>] wins, e.g. to play the EDOPro copy of the .ydk so its edits carry over.
        self.settings.update(deck_overrides(cfg or {}, deck_key))
        self.name = self.settings.get("name", deck_key)
        self.ydk = paths.resolve(self.settings.get("ydk", "deck.ydk"), self.dir)
        if not os.path.exists(self.ydk):
            raise FileNotFoundError(f"deck file for {deck_key!r} not found: {self.ydk}")
        self.main, self.extra, self.side = parse_ydk(self.ydk)
        self.ids = set(self.main) | set(self.extra) | set(self.side)
        self.db = db

    def get(self, key, default=None):
        return self.settings.get(key, default)

    @staticmethod
    def _read(path, missing=None):
        if not os.path.exists(path):
            return missing
        with open(path, encoding="utf-8") as f:
            return f.read()

    @property
    def playbook(self):
        return self._read(os.path.join(self.dir, "playbook.md"), "(no playbook yet)")

    @property
    def general_playbook(self):
        """Deck-agnostic strategy shared by every deck (playbooks/general.md)."""
        return self._read(os.path.join(paths.PLAYBOOKS, "general.md"), "")

    def decklist(self):
        def block(title, ids):
            counts = collections.Counter(ids)
            return f"{title} ({len(ids)}):\n" + "\n".join(f"  {n}x {self.db.name(i)}" for i, n in counts.items())
        return block("Main Deck", self.main) + "\n" + block("Extra Deck", self.extra)

    def card_texts(self):
        seen, lines = set(), []
        for i in self.main + self.extra:
            if i not in seen:
                seen.add(i)
                lines.append("- " + self.db.full_text(i))
        return "\n".join(lines)

    def system_prompt(self, mode="play", rules="MR3"):
        return prompts.system_prompt(self, mode, rules)
