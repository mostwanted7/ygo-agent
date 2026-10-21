"""Shared helpers for the web panel's tests (imported as `web_helpers`)."""

import json
import os

from helpers import ROOT, load_case
from ygo_agent.agent.brain import DuelBrain
from ygo_agent.agent.profile import Profile


def play_case(cfg, db, scripted, name="chinook-on-attack", deck="blackwing", **brain_args):
    """A saved regression case (a real logged game up to one decision) played through a DuelBrain."""
    case = load_case(os.path.join(ROOT, "decks", deck, "tests", f"{name}.json"))
    brain = DuelBrain(cfg, db, Profile(deck, db, cfg), prewarm=False, **brain_args)
    for m in case["messages"]:
        m = json.loads(json.dumps(m))
        if m.get("t") == "event":
            brain.on_event(m)
        else:
            scripted["decision"] = m
            brain.on_decide(m)
    return brain, case
