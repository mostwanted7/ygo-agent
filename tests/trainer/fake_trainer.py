"""A Trainer on a tiny deck folder in a temporary directory, with a scripted reviewer: for the unit tests of the
gate and the rule proposals (no model, no EDOPro; setup() and the duels are never run)."""

import os
import shutil

from helpers import ROOT
from ygo_agent.trainer.pipeline import RULES_TEMPLATE, Options, Trainer
from ygo_agent.trainer.workspace import Workspace

GEARGIA = os.path.join(ROOT, "decks", "geargia")

PLAYBOOK = """## How to use this playbook

Principles, not scripts.

## Game plan

Make Rank 4s.

## Card roles

- **Geargiarsenal**: Tribute it for a Geargia.

## Situational considerations

- **Consider Gear Gigant X when a Geargiano is in the GY**, because it floats.

## Known pitfalls (from reviewed games, newest first)

None yet: specific mistakes from reviewed games go here, one or two lines each.
"""


def make_trainer(tmp_path, cfg, db, answer, cases=("set-ash-as-blocker-empty-field",), **opts):
    """`answer(task, prompt)` is the reviewer; `cases` are copied from decks/geargia/tests."""
    deck = tmp_path / "geartest"
    (deck / "tests").mkdir(parents=True)
    shutil.copyfile(os.path.join(GEARGIA, "deck.ydk"), deck / "deck.ydk")
    (deck / "playbook.md").write_text(PLAYBOOK)
    (deck / "rules.py").write_text(RULES_TEMPLATE.format(name="Geargia"))
    for name in cases:
        shutil.copyfile(os.path.join(GEARGIA, "tests", f"{name}.json"), deck / "tests" / f"{name}.json")
    calls = []

    def policy(req):
        calls.append(req)
        return answer(req["task"], req["prompt"])
    cfg["backends"]["fake"] = {"type": "scripted", "policy": policy, "cost_per_call": 0.0}
    t = Trainer(Options(ydk=None, name="geartest", backend="fake", out=str(deck), **opts), cfg, db=db, quiet=True)
    t.ws = Workspace(t.deck_dir, quiet=True)
    t.calls = calls
    return t
