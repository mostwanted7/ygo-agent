"""Hard-coded decisions that run before the model is asked.

A deck's rules live in decks/<deck>/rules.py as plain functions listed in RULES. Each one receives a
Context and returns None (no opinion) or Decide(choice, why). Use them for lessons that must never
be forgotten again; softer advice belongs in the playbook instead.
"""

import importlib.util
import os
from dataclasses import dataclass


@dataclass
class Decide:
    choice: list
    why: str


class Context:
    """Read-only helpers over one decision, so rules can be written in terms of card names."""

    def __init__(self, decision, db, describer, profile):
        self.d = decision
        self.kind = decision["kind"]
        self.state = decision["state"]
        self.db = db
        self.describer = describer
        self.profile = profile

    # Options
    @property
    def options(self):
        return self.d.get("options", [])

    def option_card(self, i):
        o = self.options[i]
        if isinstance(o, dict):
            return o.get("card", o if "id" in o else None)
        return None

    def option_name(self, i):
        c = self.option_card(i)
        return self.db.name(c["id"]) if c and c.get("id") else None

    def option_action(self, i):
        o = self.options[i]
        return o.get("a") if isinstance(o, dict) else None

    def find(self, name=None, action=None):
        """Indices of options whose card name and/or action match."""
        return [i for i in range(len(self.options))
                if (name is None or self.option_name(i) == name) and (action is None or self.option_action(i) == action)]

    # State
    def names(self, side, zone):
        cards = self.state[side][zone]
        return [self.db.name(c["id"]) for c in cards if c and c.get("id")]

    @property
    def my_turn(self):
        return self.state["turn_player"] == 0

    @property
    def turn(self):
        return self.state["turn"]

    @property
    def phase(self):
        return self.state["phase"]

    def chain_names(self):
        return [self.db.name(link["id"]) for link in self.state.get("chain", [])]

    def last_chain_by_opponent(self):
        chain = self.state.get("chain", [])
        return bool(chain) and chain[-1]["player"] == 1


def builtin_rules(ctx):
    """Prompts that never need the model."""
    if ctx.kind == "go_first":
        first = ctx.profile.get("go_first", True)
        return Decide([1 if first else 0], f"deck setting: go {'first' if first else 'second'}")
    if ctx.kind == "place":
        return Decide(None, "zone placement left to the default")
    if ctx.kind in ("position", "option", "announce_number", "announce_attrib", "announce_race") and len(ctx.options) == 1:
        return Decide([0], "only one choice")
    if ctx.kind == "announce_card" and len(ctx.options) > 150:
        return Decide(None, f"{len(ctx.options)} possible card names is too many to list; built-in AI declares one")
    return None


class Rules:
    def __init__(self, deck_dir):
        self.deck_rules = []
        path = os.path.join(deck_dir, "rules.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("deck_rules", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.deck_rules = list(getattr(module, "RULES", []))

    def decide(self, ctx):
        """Returns (Decide, rule name) or (None, None)."""
        result = builtin_rules(ctx)
        if result is not None:
            return result, "auto"
        for rule in self.deck_rules:
            try:
                result = rule(ctx)
            except Exception as e:  # a broken rule must not stop the game
                print(f"[rules] {rule.__name__} failed: {e!r}")
                continue
            if result is not None:
                return result, f"rule:{rule.__name__}"
        return None, None
