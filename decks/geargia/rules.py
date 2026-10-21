"""Hard rules for the Geargia deck, checked before the model is asked (see decks/saffira/rules.py for examples).

Add a rule when a playbook lesson wasn't enough and the same mistake keeps happening, or for a fixed instruction with
no judgment in it. Each rule gets a ygo_agent.agent.rules.Context and returns None (let the model decide) or
Decide(choice, why).
"""

from ygo_agent.agent.rules import Decide  # noqa: F401

RULES = []
