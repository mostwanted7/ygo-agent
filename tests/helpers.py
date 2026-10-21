"""Shared test helpers. (Imported as `helpers`, not from conftest: tests/arena has its own conftest module.)"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EDOPRO = os.path.expanduser("~/Games/ProjectIgnis")
CASES = sorted(glob.glob(os.path.join(ROOT, "decks", "*", "tests", "*.json")))


def case_id(path):
    return f"{path.split(os.sep)[-3]}/{os.path.splitext(os.path.basename(path))[0]}"


def load_case(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def decisions(case):
    return [m for m in case["messages"] if m.get("t") == "decide"]


def first_valid(d):
    """A deterministic, usually-legal answer to any decision."""
    k = d["kind"]
    if k in ("effect_yn", "yesno", "go_first"):
        return [1]
    if k == "chain":
        return [0] if d.get("forced") else []
    if k in ("select_card", "tribute", "select_sum"):
        return list(range(d["min"]))
    if k in ("announce_attrib", "announce_race"):
        return list(range(d.get("count", 1)))
    return [0]
