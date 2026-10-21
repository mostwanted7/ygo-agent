"""describe.py: the saved bridge fixtures render exactly as the snapshot says; the native seats' optional fields and
events render concisely (no EDOPro needed).

The snapshot (fixtures/describe_golden.json) holds a hash per rendered message of the cases it lists. It was taken
before Stage 3 and re-taken on purpose since, each time with the count of messages that changed:
- Stage 3/4: a flipped Set Spell/Trap reads 'is flipped face-up', repeated Special Summon entries are numbered,
  '%ls' in an effect description names its card (18 messages; until Stage 9 the test mapped them back instead);
- Stage 9: "Go to the Battle Phase" states an attack when it could matter (2 of the 8 idle decisions that offer it),
  and an effect label that plainly doesn't fit gets a qualifier (Blackwing - Vata's on-field effect, labelled
  "Special Summon this card": 2 options and 2 chain lines). 6 messages.
  The Summon wording didn't change here: these logs have no `window`, so their Summons read as done, as before; in
  the history the model reads (lines/flush), 11 response windows right after a Summon show it in progress
  (test_history_lines_keep_every_event_line).
After a deliberate change to describe.py: `python tests/native/test_native_describe.py` re-takes it and prints how
many messages changed; say so in the change.
"""

import hashlib
import json
import os
import re
import sys

import pytest

if __name__ == "__main__":  # re-taking the snapshot: tests/ (helpers) and the repo on the path
    sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]
from helpers import CASES, case_id, load_case  # noqa: E402
from ygo_agent.agent.describe import Describer  # noqa: E402

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


def digests(db, case):
    return [hashlib.sha256(text.encode()).hexdigest()[:16] for text in rendered(Describer(db), case)]


@pytest.mark.skipif(not CASES, reason="no saved cases")
@pytest.mark.parametrize("path", CASES, ids=case_id)
def test_saved_fixtures_render_as_the_snapshot(path, db):
    with open(GOLDEN, encoding="utf-8") as f:
        snapshot = json.load(f)
    if case_id(path) not in snapshot:
        pytest.skip("case saved after the snapshot (e.g. by `replay --save` or the trainer)")
    golden = snapshot[case_id(path)]
    case = load_case(path)
    got = digests(db, case)
    assert len(got) == len(golden)
    texts = list(rendered(Describer(db), case))
    for i, (have, want) in enumerate(zip(got, golden)):
        assert have == want, f"message {i} renders differently:\n{texts[i]}"


def retake():
    """Re-take the snapshot for the cases it lists, and print what changed."""
    from ygo_agent.agent.carddb import CardDB
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, "tests", "fixtures", "cards.json"), encoding="utf-8") as f:
        db = CardDB.from_dict(json.load(f))
    with open(GOLDEN, encoding="utf-8") as f:
        old = json.load(f)
    new, changed, total = {}, 0, 0
    for path in CASES:
        if case_id(path) in old:
            new[case_id(path)] = digests(db, load_case(path))
            before = old[case_id(path)]
            total += len(new[case_id(path)])
            changed += sum(a != b for a, b in zip(new[case_id(path)], before)) + abs(len(before) - len(new[case_id(path)]))
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(new, f, indent=0)
        f.write("\n")
    print(f"{changed} of {total} messages changed")


@pytest.mark.skipif(not CASES, reason="no saved cases")
def test_history_lines_keep_every_event_line(db):
    """lines()/flush(), as DuelBrain uses them, give the same lines in the same order as event() on every saved case:
    a held Summon line only moves to the next message, or reads as in progress at a response window."""
    pending = re.compile(r'^(You are|Opponent is) (.+?)ing (".+") to (\S+), (.+) \(not complete yet: it can still be '
                         r'negated\)\.$')

    def done(line):
        m = pending.match(line)
        if not m:
            return line
        mine = m.group(1) == "You are"
        return f"{'You' if mine else 'Opponent'} {m.group(2)}{'' if mine else 's'} {m.group(3)} to {m.group(4)} ({m.group(5)})."
    shown = 0
    for path in CASES:
        case = load_case(path)
        plain, history = Describer(db), Describer(db)
        want, got = [], []
        for m in case["messages"]:
            if m.get("t") == "event":
                want += [t for t in [plain.event(m)] if t]
                got += history.lines(m)
            elif m.get("t") == "decide":
                got += history.flush(m)
        got += history.flush()
        shown += sum(1 for line in got if pending.match(line))
        assert [done(line) for line in got] == want, case_id(path)
    assert shown >= 11


def test_repeated_special_summon_entries_are_numbered(db):
    """Stage 3 found two Xyz-procedure options for one card reading identically."""
    d = Describer(db)
    code, other = list(db.cards)[:2]
    xyz = {"id": code, "c": 0, "l": 0x40, "s": -1}
    options = [{"a": "spsummon", "card": xyz}, {"a": "spsummon", "card": dict(xyz, id=other)},
               {"a": "spsummon", "card": xyz}, {"a": "to_end"}]
    lines = d.options({"kind": "idle", "options": options})
    assert len(set(lines)) == len(lines)
    assert "entry 1 of 2" in lines[0] and "entry 2 of 2" in lines[2] and "equivalent" in lines[0]
    assert lines[1].endswith("(by its own summoning procedure)")


def test_effect_descriptions_name_their_card(db):
    d = Describer(db)
    code = next(iter(db.cards))
    db.system[96] = 'Use the effect of "%ls" to avoid destruction?'
    q = d.question({"kind": "effect_yn", "card": {"id": code, "c": 0, "l": 0x10, "s": 0}, "desc": 96})
    assert f'Use the effect of "{db.name(code)}" to avoid destruction?' in q and "%ls" not in q


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
                    "flip": True, "window": True})
    assert flip.startswith("You are Flip Summoning")


def summon(code, c=1, s=2, special=True, **kw):
    return {"e": "summoning", "id": code, "to": {"c": c, "l": 4, "s": s, "p": 1}, "special": special, **kw}


def summoned(code, c=1, s=2, special=True):
    return {"e": "summoned", "id": code, "to": {"c": c, "l": 4, "s": s, "p": 1}, "special": special}


def test_a_summon_reads_as_in_progress_until_its_window_closes(db):
    """Stage 6 review: "Opponent Special Summons X" before the Solemn Strike window made the player think the Summon
    had resolved. A Summon in its window is in progress; one that goes through at once reads as before."""
    code, solemn = list(db.cards)[:2]
    name = db.name(code)
    d = Describer(db)
    # nothing happened in between: one line, the old wording
    assert d.lines(summon(code, window=True)) == []
    assert d.lines(summoned(code)) == [f'Opponent Special Summons "{name}" to M3 (face-up Attack).']
    # a decision in the window (flush): the model sees it in progress, then that it succeeded
    d.lines(summon(code, window=True))
    assert d.flush() == [f'Opponent is Special Summoning "{name}" to M3, face-up Attack (not complete yet: it can '
                         "still be negated)."]
    assert d.lines(summoned(code)) == [f'Opponent\'s Special Summon of "{name}" succeeded.']
    # negated: Solemn Strike, the card leaves the field, no `summoned`
    d.lines(summon(code, c=0, s=0, special=False, window=True))
    out = d.lines({"e": "chaining", "id": solemn, "card": {"id": solemn, "c": 1, "l": 8, "s": 1, "p": 5},
                   "player": 1, "desc": 0, "link": 1})
    assert out[0].startswith(f'You are Normal Summoning "{name}" to M1') and out[1].startswith("CL1: Opponent")
    gone = d.lines({"e": "move", "id": code, "from": {"c": 0, "l": 4, "s": 0, "p": 1},
                    "to": {"c": 0, "l": 0x10, "s": 0, "p": 1}, "reason": 0x41})
    assert gone == [f'"{name}": your M1 → your GY (destroyed, by effect) — its Summon was negated.']
    d.lines({"e": "chain_solved", "link": 1})
    d.lines({"e": "chain_end"})
    later = d.lines({"e": "move", "id": code, "from": {"c": 0, "l": 0x10, "s": 0, "p": 1},
                     "to": {"c": 0, "l": 0x20, "s": 0, "p": 1}, "reason": 0x40})
    assert "negated" not in later[0]


def test_a_summon_by_a_resolving_effect_has_no_window(db):
    code, reborn = list(db.cards)[:2]
    name = db.name(code)
    d = Describer(db)
    d.lines({"e": "chaining", "id": reborn, "card": {"id": reborn, "c": 0, "l": 8, "s": 0, "p": 5}, "player": 0,
             "desc": 0, "link": 1})
    assert d.lines(summon(code, c=0, window=False)) == [f'You Special Summon "{name}" to M3 (face-up Attack).']
    assert d.lines(summoned(code, c=0)) == []


def test_logs_without_window_read_as_before_except_at_a_response_window(db):
    """Older logs have no `window` and no `summoned`: nothing says when a Summon completed, so it reads as done, as it
    always did, except when a response window (a chain decision) comes right after a Summon made outside a chain."""
    code, reborn = list(db.cards)[:2]
    name = db.name(code)
    done = f'Opponent Special Summons "{name}" to M3 (face-up Attack).'
    old = Describer(db)
    assert old.event(summon(code)) == done
    assert old.event(summon(code, special=False)) == f'Opponent Normal/Flip Summons "{name}" to M3 (face-up Attack).'
    assert old.lines(summon(code)) == []
    assert old.lines({"e": "chain_solved", "link": 1})[0] == done  # the next event: it went through
    old.lines(summon(code))
    assert old.flush({"kind": "effect_yn"}) == [done]
    old.lines(summon(code))
    assert old.flush({"kind": "chain"}) == [f'Opponent is Special Summoning "{name}" to M3, face-up Attack (not '
                                            "complete yet: it can still be negated)."]
    old.lines({"e": "chaining", "id": reborn, "card": None, "player": 1, "desc": 0, "link": 1})
    assert old.lines(summon(code)) == [done]  # inside a chain: a resolving effect's Summon, never negatable
    assert old.flush({"kind": "chain"}) == []


def idle(me_mz, opp_mz, opp_lp=4000, phase=0x4, turn_player=0, battle=True):
    state = {"turn": 3, "turn_player": turn_player, "phase": phase,
             "me": {"lp": 8000, "hand": [], "mz": me_mz + [None] * (7 - len(me_mz)), "sz": [None] * 8, "gy": [],
                    "ban": [], "deck": 30, "extra": []},
             "opp": {"lp": opp_lp, "hand": [], "mz": opp_mz + [None] * (7 - len(opp_mz)), "sz": [None] * 8,
                     "gy": [], "ban": [], "deck": 30, "extra": []}}
    options = [{"a": "summon", "card": me_mz[0] if me_mz else None}] + (
        [{"a": "to_battle"}] if battle else []) + [{"a": "to_end"}]
    return {"kind": "idle", "options": options, "state": state}


def test_the_battle_phase_option_states_an_attack_when_it_could_matter(db):
    """Stage 6: the player "never went to the Battle Phase" with attackers ready. Facts on the option, only when the
    opponent has no monsters or the total ATK reaches their LP."""
    d = Describer(db)
    a, b = card(db, atk=1800), card(db, s=1, atk=1800)
    lines = d.options(idle([a, b], []))
    assert lines[1] == ("Go to the Battle Phase (attack available: your Attack Position monsters total 3600 ATK; "
                        "opponent LP 4000; opponent has no monsters)")
    assert lines[0] == d.option_line("idle", {"a": "summon", "card": a}) and lines[2].startswith("End your turn")
    wall = card(db, c=1, atk=2500)
    assert "opponent has 1 monster)" in d.options(idle([a, b], [wall], opp_lp=3600))[1]
    quiet = "Go to the Battle Phase"
    assert d.options(idle([a, b], [wall], opp_lp=3601))[1] == quiet           # not enough for game, and a blocker
    assert d.options(idle([a, dict(b, p=4)], []))[1].endswith("total 1800 ATK; opponent LP 4000; opponent has no "
                                                               "monsters)")  # a Defense Position monster can't attack
    assert d.options(idle([dict(a, att=True)], []))[1] == quiet              # already attacked
    assert d.options(idle([dict(a, atk=0)], []))[1] == quiet
    assert d.options(idle([], []))[1] == quiet
    assert d.options(idle([a], [], phase=0x100, battle=True))[1] == quiet     # not Main Phase 1
    assert d.options(idle([a], [], turn_player=1))[1] == quiet
    assert quiet not in "".join(d.options(idle([a], [], battle=False)))       # no Battle Phase to go to (turn 1)
    assert Describer(db, attack_note=False).options(idle([a, b], []))[1] == quiet


if __name__ == "__main__":
    retake()


VATA_LIKE = """local s,id=GetID()
function s.initial_effect(c)
	local e1=Effect.CreateEffect(c)
	e1:SetType(EFFECT_TYPE_FIELD)
	e1:SetCode(EFFECT_SPSUMMON_PROC)
	e1:SetRange(LOCATION_HAND)
	c:RegisterEffect(e1)
	local e2=Effect.CreateEffect(c)
	e2:SetDescription(aux.Stringid(id,0))
	e2:SetType(EFFECT_TYPE_IGNITION)
	e2:SetRange(LOCATION_MZONE)
	c:RegisterEffect(e2)
	local e3=Effect.CreateEffect(c)
	e3:SetDescription(aux.Stringid(id,1))
	e3:SetType(EFFECT_TYPE_SINGLE+EFFECT_TYPE_TRIGGER_O)
	e3:SetCode(EVENT_SUMMON_SUCCESS)
	c:RegisterEffect(e3)
	local e4=e3:Clone()
	e4:SetCode(EVENT_SPSUMMON_SUCCESS)
	c:RegisterEffect(e4)
	local e5=Effect.CreateEffect(c)
	e5:SetDescription(aux.Stringid(id,2))
	e5:SetType(EFFECT_TYPE_IGNITION)
	e5:SetRange(LOCATION_HAND)
	c:RegisterEffect(e5)
	local e6=Effect.CreateEffect(c)
	e6:SetDescription(aux.Stringid(id,2))
	e6:SetType(EFFECT_TYPE_IGNITION)
	e6:SetRange(LOCATION_GRAVE)
	c:RegisterEffect(e6)
	local e7=Effect.CreateEffect(c)
	e7:SetDescription(aux.Stringid(id,3))
	e7:SetProperty(EFFECT_FLAG_CLIENT_HINT)
	c:RegisterEffect(e7)
end
function s.op(e,tp)
	local e1=Effect.CreateEffect(e:GetHandler())
	e1:SetDescription(aux.Stringid(id,1))
	e1:SetRange(LOCATION_MZONE)
	c:RegisterEffect(e1)
end
"""


def test_card_scripts_are_read_for_labels_and_ranges():
    from ygo_agent.agent.cardscripts import parse
    effects = parse(VATA_LIKE, 99)
    assert [(e.family, e.label, e.range) for e in effects] == [
        (1, None, 0x2), (2, (99, 0), 0x4), (3, (99, 1), None), (3, (99, 1), None), (4, (99, 2), 0x2),
        (5, (99, 2), 0x10)]  # e7 is a client hint; s.op's effect isn't the card's own


def test_labels_that_dont_fit_get_a_qualifier(db, monkeypatch):
    """The exam's smoke review: Blackwing - Vata's on-field effect reads "Special Summon this card", so Haiku took it
    for the hand Summon and thought the Black-Winged Dragon effect wasn't offered."""
    from ygo_agent.agent.cardscripts import ScriptIndex
    code = next(c for c in db.cards if db.get(c).is_monster)
    monkeypatch.setattr(db, "_scripts", ScriptIndex(sources={code: VATA_LIKE}))
    labels = ["Special Summon this card", "Draw 1 card", "Special Summon this card from your hand"]
    monkeypatch.setattr(db.cards[code], "strings", labels + [""] * 13)
    d = Describer(db)
    on_field = {**MONSTER, "id": code, "l": 4, "s": 1}
    in_hand = {"id": code, "c": 0, "l": 2, "s": -1, "p": 0}
    in_gy = {"id": code, "c": 0, "l": 0x10, "s": 0, "p": 5}

    def option(card, idx):
        return d.option_line("idle", {"a": "activate", "card": card, "desc": (code << 20) | idx})
    assert option(on_field, 0).endswith('effect: "Special Summon this card" (the script\'s label for its Monster Zone '
                                        "effect, though this card is already on the field; see the card text)")
    assert option(in_hand, 0).endswith('effect: "Special Summon this card"')       # it fits there
    assert option(on_field, 1).endswith('effect: "Draw 1 card"')                    # one effect, cloned per event
    assert option(in_gy, 2).endswith("(this label is shared by 2 of this card's effects; this one works from the GY; "
                                     "see the card text)")
    assert "this label is shared by 2" in option(in_hand, 2)
    question = d.question({"kind": "effect_yn", "card": on_field, "desc": code << 20})
    assert "already on the field" in question and question.endswith("? Reply [1] for yes or [0] for no.")
    chain = d.event({"e": "chaining", "id": code, "card": on_field, "player": 1, "desc": code << 20, "link": 1})
    assert "already on the field" in chain
    # without a script the plain misfit still shows, without the zone
    monkeypatch.setattr(db, "_scripts", ScriptIndex(sources={}))
    assert option(on_field, 0).endswith("(the script's label, though this card is already on the field; see the card "
                                        "text)")
    assert option(in_gy, 2).endswith('effect: "Special Summon this card from your hand"')
