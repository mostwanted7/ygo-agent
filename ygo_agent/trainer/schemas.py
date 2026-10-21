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
    text={"type": "string", "description": "a Known pitfall in the playbook's voice, generalised, one or two "
                                           "sentences: '**When X, do Y** because Z.' (Markdown)"},
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

SETTLED = arr(obj(question=INT, answer={"type": "string", "description": "one line: what the logs or scripts showed"}))

RULE_PROPOSAL = obj(
    rule={"type": "string", "description": "the rule in plain words"},
    decisions=arr(INT),
    case={"type": "string", "description": "the regression case that proves it: a name from test_cases or an "
                                           "existing case"},
    code={"type": "string", "description": "optional: the rule as one Python function 'def name(ctx):' returning "
                                           "None or Decide(choice, why); empty if none"},
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
    settled_questions=SETTLED,
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
        no_judgment={"type": "boolean", "description": "one answer was clearly right whatever the rest of the game"},
        playbook_had={"type": "string", "description": "the playbook line that already covered it, quoted verbatim; "
                                                       "empty if none"},
        verified=BOOL,
        evidence=EVIDENCE,
    )),
    significant_mistakes=INT,
    lessons=arr(LESSON),
    sections=arr(SECTION),
    confirmed_lines=arr({"type": "string", "description": "names of Example sequences this game showed working"}),
    test_cases=arr(TEST_CASE),
    general=arr(obj(text=STR, evidence=EVIDENCE)),
    rule_proposals=arr(RULE_PROPOSAL),
    settled_questions=SETTLED,
)

CONDENSE = obj(
    playbook={"type": "string", "description": "the complete tightened playbook (Markdown)"},
    removed=arr({"type": "string", "description": "what was cut or merged, one line each"}),
)
