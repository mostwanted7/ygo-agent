"""describe.py: the saved bridge fixtures render byte for byte as before Stage 3; the native seats' optional fields
and events render concisely (no EDOPro needed)."""

import hashlib
import json
import os

import pytest

from helpers import CASES, case_id, load_case
from ygo_agent.agent.describe import Describer

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "describe_golden.json")


def rendered(describer, case):
    """Every text describe.py makes from a case: event lines, and per decision its question, options, state, hint."""
    for m in case["messages"]:
        if m.get("t") == "event":
            yield describer.event(m) or ""
        elif m.get("t") == "decide":
            parts = [describer.question(m)] + describer.options(m)
            if m.get("state", {}).get("me"):
                parts.append(describer.state(m["state"]))
            if m["kind"] in ("select_card", "tribute", "select_unselect", "select_sum"):
                parts.append(describer.hint(m))
            yield "\n".join(parts)


# Lines that changed on purpose since the snapshot: (case, message index) -> what they read now.
FIXED = {
    # a Set Spell/Trap turning face-up used to read 'changes to ?.' (no name for S/T positions)
    ("saffira/main2-to-set-lance", 119): 'is flipped face-up.',
}


@pytest.mark.skipif(not CASES, reason="no saved cases")
@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_saved_fixtures_render_byte_identically(path, db):
    """The hashes were taken with describe.py as it was before Stage 3 (tests/native/fixtures)."""
    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)[case_id(path)]
    texts = list(rendered(Describer(db), load_case(path)))
    assert len(texts) == len(golden)
    for i, (text, want) in enumerate(zip(texts, golden)):
        fixed = FIXED.get((case_id(path), i))
        if fixed:
            assert text.endswith(fixed) and "?" not in text, text
            continue
        assert hashlib.sha256(text.encode()).hexdigest()[:16] == want, f"message {i} renders differently:\n{text}"


def test_spell_trap_flips_read_as_flips(db):
    d = Describer(db)
    code = next(iter(db.cards))
    flip = {"e": "pos_change", "id": code, "c": 1, "l": 8, "s": 2, "from": 0xA, "to": 0x5}
    assert d.event(flip).endswith("is flipped face-up.")
    assert d.event(dict(flip, l=4, to=0x1)).endswith("changes to face-up Attack.")


MONSTER = {"id": 0, "c": 0, "l": 4, "s": 0, "p": 1, "atk": 1800, "def": 1000, "lv": 4, "rk": 0, "lk": 0}


def card(db, **kw):
    code = next(iter(db.cards))
    return {**MONSTER, "id": code, **kw}


def test_native_fields_show_only_when_present(db):
    d = Describer(db)
    plain = card(db)
    base = d.card_line(plain)
    assert "Level" not in base and "Counter" not in base and "owned" not in base
    assert "Level 8 (printed 4)" in d.card_line(card(db, lv=8, blv=4))
    db.counters[0x1] = "Spell Counter"
    assert "2 Spell Counter(s)" in d.card_line(card(db, ctr=[[0x1, 2]]))
    assert "1 counter 0x99(s)" in d.card_line(card(db, ctr=[[0x99, 1]]))
    assert "owned by your opponent" in d.card_line(card(db, own=1))
    spell = card(db, l=8, s=6, p=5, sc=[1, 8])
    assert "Pendulum Scales 1/8" in d.card_line(spell)
    assert "Pendulum Scale 4" in d.card_line(card(db, l=8, s=7, p=5, sc=[4, 4]))
    equip = card(db, l=8, s=1, p=5, eq={"id": plain["id"], "c": 1, "l": 4, "s": 2})
    assert "equipped to" in d.card_line(equip) and "opponent's M3" in d.card_line(equip)
    assert "effects negated" in d.card_line(card(db, l=8, s=1, p=5, dis=True))
    assert d.card_line(card(db, l=8, s=1, p=5)) == d.name(plain)  # a plain face-up S/T card reads as before


def test_native_events(db):
    d = Describer(db)
    code = next(iter(db.cards))
    name = db.name(code)
    hand = {"id": code, "c": 1, "l": 2, "s": -1, "p": 0}
    assert d.event({"e": "confirm", "player": 0, "cards": [hand]}) == \
        f"Revealed to you: \"{name}\" (opponent's hand)."
    assert d.event({"e": "confirm", "player": 1, "cards": []}) is None
    mon = {**MONSTER, "id": code}
    assert "is equipped to" in d.event({"e": "equip", "card": dict(mon, l=8), "target": mon})
    db.counters[0x1] = "Spell Counter"
    assert d.event({"e": "counter", "card": mon, "type": 1, "count": 2, "add": True}).startswith(
        "2 Spell Counter(s) placed on")
    assert "removed from" in d.event({"e": "counter", "card": mon, "type": 1, "count": 1, "add": False})
    assert d.event({"e": "coin", "player": 1, "results": [1, 0]}) == "Opponent tosses a coin: heads, tails."
    assert d.event({"e": "dice", "player": 0, "results": [4]}) == "You roll a die: 4."
    assert d.event({"e": "declared", "player": 1, "kind": "card", "value": code}) == f'Opponent declared "{name}".'
    assert d.event({"e": "declared", "player": 1, "kind": "attribute", "value": 0x20}) == "Opponent declared DARK."
    assert d.event({"e": "declared", "player": 1, "kind": "race", "value": 0x2000}) == "Opponent declared Dragon."
    assert d.event({"e": "declared", "player": 1, "kind": "number", "value": 3}) == "Opponent declared the number 3."
    swap = d.event({"e": "swap", "cards": [dict(mon, c=1), dict(mon, s=3)]})
    assert swap.startswith("Control swap:") and "opponent's M1" in swap and "your M4" in swap
    flip = d.event({"e": "summoning", "id": code, "to": {"c": 0, "l": 4, "s": 0, "p": 1}, "special": False,
                    "flip": True})
    assert "Normal/Flip Summon" in flip
