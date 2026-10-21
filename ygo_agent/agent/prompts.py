"""The system prompt: who the AI is in this mode, the rules in force, the general strategy, the deck and its playbook."""

# Reply format every backend must produce.
SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "array", "items": {"type": "integer"},
                   "description": "Option indices, in the format the decision asks for."},
        "why": {"type": "string", "description": "1-3 short sentences explaining the decision."},
        "plan": {"type": "string", "description": "Optional: your plan for the rest of this turn, when it changes."},
    },
    "required": ["choice", "why"],
}

# EDOPro duel-mode flag sets (ocgapi_constants.h DUEL_MODE_*), so the prompt can name the rules the room really uses.
_OLD = 0x40000 | 0x10000 | 0x80000  # SPSUMMON_ONCE_OLD_NEGATE | RETURN_TO_DECK_TRIGGERS | CANNOT_SUMMON_OATH_OLD
_MR1 = 0x100 | 0x200 | 0x400 | _OLD
DUEL_MODES = {
    "MR1": _MR1,
    "MR2": 0x200 | 0x400 | _OLD,
    "MR3": 0x800 | 0x1000 | _OLD,
    "MR4": 0x800 | 0x2000 | _OLD,
    "MR5": 0x800 | 0x2000 | 0x4000 | 0x8000 | 0x20000,
    "GOAT": _MR1 | 0x4 | 0x8 | 0x20 | 0x8000000 | 0x10000000 | 0x20000000 | 0x40000000 | 0x80000000
            | 0x100000000 | 0x200000000 | 0x400000000,
    "SPEED": 0x400000 | 0x200000 | 0x8000 | 0x20000,
    "RUSH": 0x400000 | 0x200000 | 0x100000 | 0x200 | 0x4000000 | 0x800000 | 0x1000000 | 0x2000000 | 0x8000
            | 0x20000 | 0x800000000,
}
NON_RULE_FLAGS = 0x1 | 0x10 | 0x40 | 0x80  # test mode, pseudo shuffle, simple AI, relay

RULESETS = {
    "MR1": ("Master Rule 1", None),
    "MR2": ("Master Rule 2", None),
    "MR3": ("Master Rule 3",
            "Extra Deck monsters are summoned to your Main Monster Zones (there is no Extra Monster Zone), the "
            "Pendulum Zones are separate from your Spell & Trap Zones, and Link Monsters aren't allowed"),
    "MR4": ("Master Rule 4",
            "a monster Special Summoned from the Extra Deck must go to an Extra Monster Zone or a zone a Link "
            "Monster points to, and your Pendulum Zones are your leftmost and rightmost Spell & Trap Zones"),
    "MR5": ("Master Rule 5",
            "Fusion, Synchro and Xyz Monsters can be summoned from the Extra Deck to any Main Monster Zone, Link "
            "Monsters and face-up Pendulum Monsters from the Extra Deck must go to an Extra Monster Zone or a zone a "
            "Link Monster points to, and your Pendulum Zones are your leftmost and rightmost Spell & Trap Zones"),
    "GOAT": ("GOAT format rules", None),
    "SPEED": ("Speed Duel rules", None),
    "RUSH": ("Rush Duel rules", None),
}


def rules_from_flags(flags):
    """The ruleset key for an EDOPro room's duel flags, or None if they're a custom mix."""
    if flags is None:
        return None
    flags &= ~NON_RULE_FLAGS
    return next((key for key, value in DUEL_MODES.items() if value == flags), None)


def ruleset(rules):
    """(name, short description or None) for a ruleset key like "MR3", or for free text from the config."""
    return RULESETS.get(str(rules).upper(), (str(rules), None))


MODES = {
    "play": {
        "situation": "Your opponent is a human who is coaching you: after each game they review your decisions, and "
                     "their lessons are written into the playbook below. Play to win, and play the way the playbook "
                     "says.",
        "reader": "The human reads these in the terminal, during or after the game.",
    },
    "teach": {
        "situation": "A human is watching from the spectator seat to learn this deck from you; your opponent is another "
                     "player (an AI or a human). Your games are reviewed afterwards and the lessons are written into "
                     "the playbook below. Play to win, and play the way the playbook says.",
        "reader": "The human learning the deck reads these live.",
    },
    "copilot": {
        "situation": "A human who is learning this deck plays it with you: you recommend each decision and they make "
                     "the final call. Your opponent is another player (an AI or a human). Your games are reviewed "
                     "afterwards and the lessons are written into the playbook below. Play to win, and play the way "
                     "the playbook says.",
        "reader": "The human learning the deck reads these live.",
    },
}

INTRO = """You are an expert Yu-Gi-Oh! duelist, playing a duel as a bot under {rules} (EDOPro engine). {situation}

How this works:
{rules_line}- Each message gives you what happened since your last decision, the full current game state, and one decision.
- Only the listed options are legal right now; the game engine generated them. Answer with option indices.
- Many decisions are follow-ups to an action you just chose (targets, materials, positions, costs, which
  card to search). Stay consistent with your plan.
- Reply with:
  choice: option indices, in the format the decision asks for
  why: 1-3 short, concrete sentences (name the cards and the line). {reader}
  plan: (optional) your plan for the rest of the turn, whenever it changes."""

TEACH = """# Teaching mode
A human is watching to learn this deck from you. Write "why" like a coach talking to a student: what the action
does, why it is right now, and how it sets up the next steps; mention the main alternative you rejected when that
is instructive. Keep each "why" under about 80 words. Whenever your plan for the turn changes, give the full
remaining line in "plan" as short numbered steps."""

COPILOT = """The human is piloting this deck: they see your recommendation and then choose themselves, so the action
actually taken can differ from your suggestion. Always re-read the events and the state instead of assuming your
suggestion was followed, and adapt the plan to what they did."""


def intro(mode="play", rules="MR3"):
    name, detail = ruleset(rules)
    m = MODES[mode]
    rules_line = f"- The rules are {name}: {detail}. The engine enforces every rule.\n" if detail else ""
    return INTRO.format(rules=name, situation=m["situation"], rules_line=rules_line, reader=m["reader"])


def system_prompt(profile, mode="play", rules="MR3"):
    general = profile.general_playbook
    parts = [intro(mode, rules)]
    if general:
        parts.append("\n\n# General strategy\n" + general.strip())
    if mode in ("teach", "copilot"):
        parts.append("\n\n" + TEACH)
    if mode == "copilot":
        parts.append("\n" + COPILOT)
    parts.append(f"\n\n# Your deck: {profile.name}\n{profile.decklist()}\n\n## Card texts\n{profile.card_texts()}"
                 f"\n\n# Playbook (coaching notes — follow these)\n{profile.playbook}\n")
    return "".join(parts)
