"""Regenerates tests/fixtures/cards.json: the card data the unit tests need, taken from the EDOPro install.

    .venv/bin/python tests/fixtures/make_cards.py

Only the cards and strings the saved test cases and the decks refer to, and no card texts, so the unit tests run
without EDOPro and the fixture stays small.
"""

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from ygo_agent.agent.carddb import CardDB  # noqa: E402
from ygo_agent.agent.profile import parse_ydk  # noqa: E402


def walk(value, ids, descs, key=None):
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, ids, descs, k)
    elif isinstance(value, list):
        for v in value:
            walk(v, ids, descs, key)
    elif isinstance(value, int) and not isinstance(value, bool):
        if key in ("id", "card_id", "ov"):
            ids.add(value)
        elif key in ("desc", "hint", "options", "reason"):
            descs.add(value)
            if value >= 1 << 20:
                ids.add(value >> 20)


def main():
    db = CardDB(os.path.expanduser("~/Games/ProjectIgnis"))
    ids, descs = set(), set()
    for path in glob.glob(os.path.join(ROOT, "decks", "*", "tests", "*.json")):
        with open(path, encoding="utf-8") as f:
            walk(json.load(f)["messages"], ids, descs)
    for path in glob.glob(os.path.join(ROOT, "decks", "*", "deck.ydk")):
        for part in parse_ydk(path):
            ids.update(part)
    cards = {}
    for cid in sorted(ids):
        c = db.get(cid)
        if c:
            cards[cid] = [c.name, "", c.strings, c.type, c.level, c.atk, c.defense, c.race, c.attribute, c.alias,
                          c.setcode]
    system = {k: v for k, v in db.system.items() if k in descs}
    with open(os.path.join(HERE, "cards.json"), "w", encoding="utf-8") as f:
        json.dump({"cards": cards, "system": system, "victory": db.victory}, f, separators=(",", ":"))
    print(f"{len(cards)} cards, {len(system)} system strings")


if __name__ == "__main__":
    main()
