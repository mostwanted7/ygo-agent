"""Hard rules for the Saffira deck, checked before the model is asked.

Add a rule when a playbook note wasn't enough and the same mistake keeps happening, or when the coaching is a
fixed instruction with no judgment in it. Each rule gets a ygo_agent.agent.rules.Context and returns None (let
the model decide) or Decide(choice, why). Rules can also just save time on prompts that never matter.
"""

from ygo_agent.agent.rules import Decide

DRAW, STANDBY = 0x1, 0x2
DECK = 0x1
HINT_ADD_TO_HAND = 506

SAFFIRA = "Saffira, Queen of Dragons"
WAYS_TO_SUMMON = {"Hymn of Light", "Prayers of the Voiceless Voice", "Saffira, Dragon Queen of the Voiceless Voice"}
CYBER_ANGELS = ["Cyber Angel Benten", "Cyber Angel Idaten"]  # in order of preference
RITUAL_SEARCHERS = {"Manju of the Ten Thousand Hands", "Preparation of Rites"}


def pass_empty_draw_standby_windows(ctx):
    """Nothing in this deck wants to act in an empty Draw/Standby Phase window; don't spend a model call on it."""
    if ctx.kind == "chain" and not ctx.d.get("forced") and not ctx.state.get("chain") and ctx.phase in (DRAW, STANDBY):
        return Decide([], "nothing worth doing in an empty Draw/Standby Phase window")
    return None


def search_cyber_angel_when_saffira_is_ready(ctx):
    """Coaching 2026-10-21: with Saffira and a way to summon her already in hand, Manju/Preparation of Rites
    search Tribute fodder (a Cyber Angel), not another Saffira."""
    if ctx.kind != "select_card" or ctx.d.get("hint") != HINT_ADD_TO_HAND:
        return None
    if not any(link["player"] == 0 and ctx.db.name(link["id"]) in RITUAL_SEARCHERS for link in ctx.state.get("chain", [])):
        return None
    hand = set(ctx.names("me", "hand"))
    if SAFFIRA not in hand or not hand & WAYS_TO_SUMMON or hand & set(CYBER_ANGELS):
        return None
    for angel in CYBER_ANGELS:
        picks = [i for i in ctx.find(name=angel) if ctx.option_card(i).get("l") == DECK]
        if picks:
            return Decide([picks[0]], f"Saffira and a way to summon her are already in hand, so {angel} "
                                      "comes as Tribute fodder (coaching)")
    return None


RULES = [
    pass_empty_draw_standby_windows,
    search_cyber_angel_when_saffira_is_ready,
]
