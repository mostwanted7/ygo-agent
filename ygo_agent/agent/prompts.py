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


# Who the AI is playing against and who reads its reasoning, per mode. {opponent} is opponent_text(): the opponent
# described as precisely as the match knows it (a human, another AI and its deck, a WindBot deck AI).
MODES = {
    "play": {
        "situation": "Your opponent is {opponent}. Your games are reviewed afterwards and the lessons are written into "
                     "the playbook below. Play to win. Follow the playbook by default, but when the board clearly calls for a better play, make it and say why.",
        "reader": "The human reads these in the terminal, during or after the game.",
    },
    "selfplay": {
        "situation": "This is a practice game: your opponent is {opponent}. Your games are reviewed afterwards and the "
                     "lessons are written into the playbook below. Play to win. Follow the playbook by default, but when the board clearly calls for a better play, make it and say why.",
        "reader": "They are read after the game, and live by anyone watching.",
    },
    "teach": {
        "situation": "A human is watching from the spectator seat to learn this deck from you; your opponent is "
                     "{opponent}. Your games are reviewed afterwards and the lessons are written into the playbook "
                     "below. Play to win. Follow the playbook by default, but when the board clearly calls for a better play, make it and say why.",
        "reader": "The human learning the deck reads these live.",
    },
    "coach": {
        "role": "coaching a human through a duel",
        "situation": "A human who is learning this deck plays it in EDOPro, and you coach them live; their opponent is "
                     "{opponent}. You see the duel from their side of the table: \"you\" and \"your\" in the log "
                     "and the state mean the human you coach.",
        "reader": "The human reads it live, while deciding.",
    },
}
# play mode against a human (or against whoever joined the room the user hosts: play --join).
COACHING_HUMAN = ("Your opponent is a human who is coaching you: after each game they review your decisions, and their "
                  "lessons are written into the playbook below. Play to win. Follow the playbook by default, but when the board clearly calls for a better play, make it and say why.")
POLICIES = {"heuristic": "a simple rule-based bot", "random": "a bot that makes random legal moves"}


def opponent_text(opponent=None):
    """The opponent in a few words. `opponent`: {"kind": "human" | "agent" | "windbot", "deck": deck name,
    "backend": backend type (agent), "name": player name}, or None when the match doesn't know (play --join)."""
    if not opponent:
        return "another player (an AI or a human)"
    kind, deck, name = opponent.get("kind"), opponent.get("deck"), opponent.get("name")
    if kind == "human":
        return "a human player" + (f" ({name})" if name else "")
    if kind == "windbot":
        return "WindBot, EDOPro's built-in scripted AI" + (f", playing its {deck} deck" if deck else "")
    who = POLICIES.get(opponent.get("backend"), "another AI") if kind == "agent" else "another player"
    return who + (f" playing {deck}" if deck else "")


def situation(mode="play", opponent=None):
    if mode == "play" and (not opponent or opponent.get("kind") == "human"):
        return COACHING_HUMAN
    return MODES[mode]["situation"].format(opponent=opponent_text(opponent))


INTRO = """You are an expert Yu-Gi-Oh! duelist, {role} under {rules} (EDOPro engine). {situation}

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

COACH = """# Coaching mode
You advise a human {who}. For every decision they face you get the view they have (their hand, their field, what
they know about the opponent) and recommend one move:
- choice: the one option you recommend, in the format the decision asks for.
- why: {why}
- plan: the line you recommend for the rest of the turn, as short numbered steps, whenever it changes.
They make every move themselves and often play something else, so read the events and the state each time instead
of assuming your advice was followed, and adapt your plan to what they actually did. The playbook below is what they
are learning: base your advice on it, and say which playbook rule a move follows when one does. Never invent card
effects: every card's text is in this prompt or in the messages, and its restrictions (Attribute, Type, Level, once
per turn, what it can summon) count as much as its effect.
Some messages ask about a decision the human already answered before your advice was ready. Answer those the same
way, with a one-sentence why: they go into the review after the game."""

COACH_LEVELS = {
    "beginner": ("who is new to this deck", "2-3 short sentences a learner can follow: what the move does, why it is "
                 "right now, and the idea behind it (e.g. why a negation waits for their turn, why you summon before "
                 "you attack). Name the cards. Warn about the likely mistake when there is one."),
    "intermediate": ("who knows the basics of this deck", "one terse sentence, like a teammate whispering: the card "
                     "and the reason. Mention the alternative only when it is close."),
}


def intro(mode="play", rules="MR3", opponent=None):
    name, detail = ruleset(rules)
    rules_line = f"- The rules are {name}: {detail}. The engine enforces every rule.\n" if detail else ""
    return INTRO.format(role=MODES[mode].get("role", "playing a duel as a bot"), rules=name,
                        situation=situation(mode, opponent), rules_line=rules_line, reader=MODES[mode]["reader"])


def system_prompt(profile, mode="play", rules="MR3", card_texts="full", opponent=None, level=None):
    """card_texts: "full", "compact" or "none" (no card-text section; the decklist carries the type lines).
    `opponent`: see opponent_text(). `level`: coach mode's student, "beginner" or "intermediate"."""
    general = profile.general_playbook
    parts = [intro(mode, rules, opponent)]
    if general:
        parts.append("\n\n# General strategy\n" + general.strip())
    if mode == "teach":
        parts.append("\n\n" + TEACH)
    if mode == "coach":
        who, why = COACH_LEVELS.get(level or "beginner", COACH_LEVELS["beginner"])
        parts.append("\n\n" + COACH.format(who=who, why=why))
    deck = "The deck they play" if mode == "coach" else "Your deck"
    if card_texts == "none":
        parts.append(f"\n\n# {deck}: {profile.name}\n{profile.decklist(with_types=True)}")
    else:
        parts.append(f"\n\n# {deck}: {profile.name}\n{profile.decklist()}\n\n## Card texts\n"
                     f"{profile.card_texts(card_texts)}")
    parts.append(f"\n\n# Playbook (coaching notes — your default guide)\n{profile.playbook}\n")
    return "".join(parts)
