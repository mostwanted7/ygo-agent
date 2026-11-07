"""Hard rules for the Galaxy-Eyes deck, checked before the model is asked.

A rule is only for a mistake with no judgment in it that the play model keeps making even with a playbook lesson.
Mark it with the regression cases that prove it (@cases("case-name")); `ygo-agent test --deck <deck> --ablate-rules`
replays them without the rule to find the rules a model no longer needs. Each rule gets a
ygo_agent.agent.rules.Context and returns None (let the model decide) or Decide(choice, why).
"""

from ygo_agent.agent.rules import Decide, cases  # noqa: F401

RULES = []
