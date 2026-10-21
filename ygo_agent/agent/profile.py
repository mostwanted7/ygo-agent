"""A deck profile: decks/<key>/ with deck.json, the .ydk, the playbook, rules.py and saved test cases."""

import collections
import json
import os

from .. import paths
from ..config import deck_overrides
from . import prompts

CARD_TEXT_MODES = ("full", "compact", "none")
COMPACT_COVERED, COMPACT_OTHER = 160, 300  # effect characters kept per card in "compact" mode


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


def find_playbook(ydk):
    """The playbook that goes with a loose .ydk file: <name>.md or <name>.playbook.md next to it, if there is one."""
    stem = os.path.splitext(ydk)[0]
    return next((p for p in (stem + ".playbook.md", stem + ".md") if os.path.isfile(p)), None)


class Profile:
    """The deck being played: decklist, card texts and the coaching playbook.

    Normally a folder decks/<key>/ (deck.json, the .ydk, playbook.md, rules.py, tests/). `ydk=` makes one from a
    loose .ydk file instead (e.g. a deck in EDOPro's deck folder), with an optional `playbook` file; its rules.py
    and tests/, if any, are looked up next to the .ydk."""

    def __init__(self, deck_key, db, cfg=None, ydk=None, playbook=None):
        self.key = deck_key
        self.db = db
        if ydk is not None:
            self.ydk = os.path.abspath(os.path.expanduser(ydk))
            if not os.path.isfile(self.ydk):
                raise FileNotFoundError(f"deck file not found: {self.ydk}")
            self.dir = os.path.dirname(self.ydk)
            self.settings = {"name": os.path.splitext(os.path.basename(self.ydk))[0]}
            self.playbook_path = playbook if playbook is not None else find_playbook(self.ydk)
            self.adhoc = True
        else:
            self._load_folder(deck_key, cfg)
        self.name = self.settings.get("name", deck_key)
        self.main, self.extra, self.side = parse_ydk(self.ydk)
        self.ids = set(self.main) | set(self.extra) | set(self.side)

    def _load_folder(self, deck_key, cfg):
        self.dir = os.path.join(paths.DECKS, deck_key)
        json_path = os.path.join(self.dir, "deck.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"no deck profile {deck_key!r}: {json_path} is missing "
                                    f"(decks: {', '.join(deck_keys())})")
        with open(json_path, encoding="utf-8") as f:
            self.settings = json.load(f)
        # config.local.toml [decks.<key>] wins, e.g. to play the EDOPro copy of the .ydk so its edits carry over.
        self.settings.update(deck_overrides(cfg or {}, deck_key))
        self.ydk = paths.resolve(self.settings.get("ydk", "deck.ydk"), self.dir)
        if not os.path.exists(self.ydk):
            raise FileNotFoundError(f"deck file for {deck_key!r} not found: {self.ydk}")
        self.playbook_path = os.path.join(self.dir, "playbook.md")
        self.adhoc = False

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
        return self._read(self.playbook_path, "(no playbook yet)") if self.playbook_path else "(no playbook yet)"

    @property
    def general_playbook(self):
        """Deck-agnostic strategy shared by every deck (playbooks/general.md)."""
        return self._read(os.path.join(paths.PLAYBOOKS, "general.md"), "")

    def decklist(self, with_types=False):
        def block(title, ids):
            counts = collections.Counter(ids)
            name = self.db.type_text if with_types else self.db.name
            return f"{title} ({len(ids)}):\n" + "\n".join(f"  {n}x {name(i)}" for i, n in counts.items())
        return block("Main Deck", self.main) + "\n" + block("Extra Deck", self.extra)

    def card_text(self, cid, mode="full", playbook=None):
        """One card as the prompt shows it: "full" text, "compact" (shortened; cards the playbook covers are cut
        shorter, since the playbook explains how to use them) or "none" (name and type line only)."""
        if mode == "none":
            return self.db.type_text(cid)
        if mode == "compact":
            covered = self.db.name(cid) in (self.playbook if playbook is None else playbook)
            return self.db.compact_text(cid, COMPACT_COVERED if covered else COMPACT_OTHER)
        return self.db.full_text(cid)

    def card_texts(self, mode="full"):
        playbook = self.playbook
        return "\n".join("- " + self.card_text(i, mode, playbook) for i in dict.fromkeys(self.main + self.extra))

    def system_prompt(self, mode="play", rules="MR3", card_texts="full", opponent=None):
        return prompts.system_prompt(self, mode, rules, card_texts, opponent)
