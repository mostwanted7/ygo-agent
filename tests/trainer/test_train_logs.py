"""Reading game.md for reviews: the condensed log and the flagged problems."""

from ygo_agent.trainer import logs

GAME = """# Geargia — game started 2026-10-21 21:00

- DUEL START — you go first. LP 8000 vs 8000.
- Opponent draws 5 card(s).

## TURN 1 (your turn)

*Main Phase 1*


**Decision #1** — Main Phase: choose your next action. Reply with exactly one option index.

  - ✅ `[0]` Normal Summon "Geargiarsenal" (from hand)
  - `[1]` End your turn (go to the End Phase)

> **sonnet (claude-code)** (3.1s): Start the line.
>
> *Plan:* 1. Summon Geargiarsenal.
2. Tribute it for Geargiarmor.

- You Normal/Flip Summon "Geargiarsenal" to M1 (face-up Attack).

**Decision #2** — The game asks: "Select the card(s) to Special Summon". Choose between 1 and 1 card(s).

  - `[0]` "Geargiarmor" — your Deck
  - ✅ (pass / none)

> **FALLBACK (heuristic policy)**:
>
> ⚠️ sonnet gave no usable answer (invalid reply []: you must select at least one card)

> ✎ the engine can't take [3] (index out of range); the heuristic answers instead

- "Geargiarmor": your Deck → your M2
*End Phase*
"""


def test_blocks_parse_decisions_and_multiline_plans():
    decisions = [item for kind, item in logs.blocks(GAME) if kind == "decision"]
    assert [d["id"] for d in decisions] == [1, 2]
    d1, d2 = decisions
    assert d1["chosen"] == ['`[0]` Normal Summon "Geargiarsenal" (from hand)'] and len(d1["options"]) == 2
    assert d1["plan"] == "1. Summon Geargiarsenal.\n2. Tribute it for Geargiarmor."
    assert "FALLBACK" in d2["tag"] and len(d2["notes"]) == 2
    assert logs.decision_count(GAME) == 2 and logs.turns(GAME) == ["TURN 1 (your turn)"]


def test_condense_keeps_choices_reasons_and_warnings():
    c = logs.condense(GAME)
    assert '#1 Main Phase: choose your next action. → Normal Summon "Geargiarsenal" (from hand) — Start the line.' in c
    assert "plan: 1. Summon Geargiarsenal. / 2. Tribute it for Geargiarmor." in c
    assert "End your turn" not in c  # options not chosen are dropped
    assert "[FALLBACK (heuristic policy)]" in c and "⚠ sonnet gave no usable answer" in c
    assert "Opponent draws" not in c and "- You Normal/Flip Summon" in c


def test_problems():
    probs = logs.problems(GAME)
    assert len(probs) == 1 and probs[0].startswith("Decision #2: sonnet gave no usable answer")
    assert "engine can't take" in probs[0]
