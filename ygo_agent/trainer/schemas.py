"""The reviewer's reply formats. Every property is required (strict structured-output servers want that); "nothing"
is an empty string or list."""

STR = {"type": "string"}
INT = {"type": "integer"}
BOOL = {"type": "boolean"}


def arr(item):
    return {"type": "array", "items": item}


def obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


EVIDENCE = arr(obj(
    source={"type": "string", "enum": ["script", "log", "card_text"],
            "description": "script: a card's Lua script; log: a game/lab log (game.md); card_text: the card text"},
    file={"type": "string", "description": "script: c<id>.lua (or lib/<name>.lua); log: the log's name as given "
                                           "in the task; card_text: the card name"},
    decision={"type": "integer", "description": "log: the decision number the quote is from (0 if none)"},
    quote={"type": "string", "description": "a short verbatim excerpt (one line) that proves the point"},
))

SECTION = obj(heading={"type": "string", "description": "the section's '## ' heading"},
              content={"type": "string", "description": "the whole new body of the section (Markdown, without the "
                                                        "heading); empty to delete the section"})

LINE = obj(
    id={"type": "string", "description": "L1, L2, ... (keep ids stable across rounds)"},
    name={"type": "string", "description": "the line's name as the playbook writes it"},
    going={"type": "string", "enum": ["first", "second"]},
    key_cards=arr({"type": "string", "description": "exact Main Deck card names the hand needs (at most 4)"}),
    expected_board=arr({"type": "string", "description": "exact card names on the field (and key cards in hand) at "
                                                         "the end of the turn"}),
    steps={"type": "string", "description": "the steps, short"},
)

LESSON = obj(
    text={"type": "string", "description": "one concrete instruction in the playbook's voice: '**When X, do Y** "
                                           "because Z.' (Markdown, one paragraph)"},
    decisions=arr(INT),
    severity={"type": "string", "enum": ["major", "minor"]},
    evidence=EVIDENCE,
)

TEST_CASE = obj(
    decision=INT,
    name={"type": "string", "description": "short-kebab-case name"},
    expect=arr(arr(INT)),
    reject=arr(arr(INT)),
    note={"type": "string", "description": "what the case checks, one sentence"},
)

STUDY = obj(
    playbook={"type": "string", "description": "the complete playbook (Markdown)"},
    lines=arr(LINE),
    card_checks=arr(obj(card=STR, file=STR, fact=STR, quote=STR)),
    go_first=BOOL,
    go_first_reason=STR,
    open_questions=arr(STR),
)

LAB_REVIEW = obj(
    verification=arr(obj(
        line={"type": "string", "description": "the line id (L1...) or its name"},
        status={"type": "string", "enum": ["verified", "partial", "failed", "not_tested"]},
        hands=arr(STR),
        reason={"type": "string", "description": "what the log showed; for a failure, which step the engine "
                                                 "refused and why (check the script)"},
    )),
    sections=arr(SECTION),
    new_lines=arr(LINE),
    lessons=arr(LESSON),
    player_errors=arr({"type": "string", "description": "places where the line was right but the player didn't "
                                                        "follow it (and the wording that would fix it)"}),
    open_questions=arr(STR),
)

GAME_REVIEW = obj(
    summary={"type": "string", "description": "3-6 sentences: how the game went and why it was won or lost"},
    mistakes=arr(obj(
        decision=INT, turn=INT,
        what={"type": "string"},
        better={"type": "string", "description": "what it should have done"},
        severity={"type": "string", "enum": ["major", "minor"]},
        kind={"type": "string", "enum": ["strategy", "rules", "sequencing", "resource", "presentation", "engine"]},
        verified=BOOL,
        evidence=EVIDENCE,
    )),
    significant_mistakes=INT,
    lessons=arr(LESSON),
    repeated=arr({"type": "string", "description": "a playbook instruction the player had and still broke"}),
    sections=arr(SECTION),
    confirmed_lines=arr({"type": "string", "description": "names of playbook lines this game showed working"}),
    test_cases=arr(TEST_CASE),
    general=arr(obj(text=STR, evidence=EVIDENCE)),
    rule_proposals=arr(STR),
)

CONDENSE = obj(
    playbook={"type": "string", "description": "the complete tightened playbook (Markdown)"},
    removed=arr({"type": "string", "description": "what was cut or merged, one line each"}),
)
