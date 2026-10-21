"""The tolerant reply parser on the kinds of output weaker models really produce."""

import pytest

from ygo_agent.backends.parse import ParseError, normalize, parse_reply


def read(text):
    return normalize(parse_reply(text))


GOOD = [
    ('{"choice": [2], "why": "summon"}', [2], "summon"),
    ('```json\n{"choice": [1], "why": "fenced"}\n```', [1], "fenced"),
    ('```\n{"choice": [1], "why": "bare fence"}\n```', [1], "bare fence"),
    ('Sure! Here is my answer:\n{"choice": [0], "why": "prose first"}\nHope that helps.', [0], "prose first"),
    ('<think>\nThe opponent has 2500 ATK... I should pass. {"choice": [3]} maybe?\n</think>\n'
     '{"choice": [], "why": "keep the trap"}', [], "keep the trap"),
    ('Okay, let me think step by step. Option 2 is bad.\n</think>\n{"choice": [1], "why": "unopened think tag"}',
     [1], "unopened think tag"),
    ('<thinking>hmm</thinking>{"choice": [4], "why": "thinking tag"}', [4], "thinking tag"),
    ('{"choice": [1, 2,], "why": "trailing commas",}', [1, 2], "trailing commas"),
    ("{'choice': [0], 'why': 'single quotes'}", [0], "single quotes"),
    ('{choice: [3], why: "bare keys"}', [3], "bare keys"),
    ('{"choice": 2, "why": "int, not a list"}', [2], "int, not a list"),
    ('{"choice": "1", "why": "string number"}', [1], "string number"),
    ('{"choice": ["0", "2"], "why": "string numbers"}', [0, 2], "string numbers"),
    ('{"choice": [[1]], "why": "nested"}', [1], "nested"),
    ('{"choice": "pass", "why": "pass word"}', [], "pass word"),
    ('{"choice": null, "why": "null"}', None, None),
    ('{"answer": [1], "reason": "aliases"}', [1], "aliases"),
    ('{"choices": [0, 1], "reasoning": "plural alias"}', [0, 1], "plural alias"),
    ('2', [2], ""),
    ('[0, 3]', [0, 3], ""),
    ('[]', [], ""),
    ('Choice: 1', [1], ""),
    ('Final answer: [2].', [2], ""),
    ('{"why": "cut off mid', None, None),
    ('{"choice": [1], "why": "cut off mid-sent', [1], "cut off mid-sent"),
    ('{"choice": [1], "why": "line\nbreak in a string"}', [1], "line\nbreak in a string"),
    ('{"choice": [1], // a comment\n "why": "comments"}', [1], "comments"),
    ('{"choice": [1], "why": "True/None", "plan": None}', [1], "True/None"),
    ('Example: {"choice": [9]}. My real answer: {"choice": [0], "why": "last one wins"}', [0], "last one wins"),
    ('{"why": "why first", "choice": [5], "plan": "1. Summon\\n2. Attack"}', [5], "why first"),
    ('  \n{"choice":[1],"why":"spaces around"}  \n', [1], "spaces around"),
    ('{"choice": [1], "why": "brace } in string {"}', [1], "brace } in string {"),
]


@pytest.mark.parametrize("text,choice,why", GOOD, ids=[g[2] or g[0][:20] for g in GOOD])
def test_parses(text, choice, why):
    if choice is None:
        with pytest.raises(ParseError):
            read(text)
        return
    reply = read(text)
    assert reply["choice"] == choice
    assert reply["why"] == why


BAD = ["", "   ", "<think>only thinking, never answered</think>", "I would summon the dragon.",
       '{"why": "no choice field"}', '{"choice": ["Normal Summon Kris"], "why": "option text"}',
       '{"choice": true}', "yes"]


@pytest.mark.parametrize("text", BAD)
def test_rejects(text):
    with pytest.raises(ParseError):
        read(text)


def test_plan_and_why_are_kept():
    reply = read('{"choice": [0], "why": " x ", "plan": ["Summon", "Attack"]}')
    assert reply == {"choice": [0], "why": "x", "plan": "Summon\nAttack"}
    assert read('{"choice": [0], "why": "x", "plan": ""}')["plan"] is None
    assert read('{"choice": [0], "why": "x"}')["plan"] is None
