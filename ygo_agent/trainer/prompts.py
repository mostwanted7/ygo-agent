"""What the reviewer is told: who it is, the house style of a playbook, and the four tasks (study, lab review, game
review, condense). The tasks follow CLAUDE.md's coaching procedure ("Decks without a coach")."""

from __future__ import annotations

import json

RULES_TEXT = {
    "MR3": "Master Rule 3: Extra Deck monsters are summoned to the Main Monster Zones (there is no Extra Monster "
           "Zone), "
           "the Pendulum Zones are separate from the Spell & Trap Zones, and Link Monsters don't exist.",
}

SYSTEM = """You are an expert Yu-Gi-Oh! player and coach who also knows the EDOPro engine and its Lua card scripts. \
You are training an AI player on one deck. Your job is the deck's playbook: the strategy guide the AI player reads on \
EVERY decision while it plays this deck in EDOPro under {rules} It also gets the general playbook, the decklist and \
every card's full text, so the playbook doesn't restate card texts: it says how and when to use the cards, in which \
order, and the rulings that aren't obvious from the text.

What is true, in order: what the engine did (a game or lab log), the card's Lua script (what the engine runs), the \
card text. Never write a claim about how a card works that you haven't checked in its script; when the text and the \
script seem to differ, the script wins. Never write a lesson you haven't verified against a script or a log.

{tools}"""

TOOLS_AGENTIC = """You have read-only tools (Read, Grep, Glob) in a working folder that holds: scripts/c<id>.lua (the \
script of every card in the deck; scripts/lib/ has the shared helpers such as proc_xyz.lua and utility.lua), \
dossier.md (the decklist, texts, archetypes, Levels and summoning conditions), playbook.md (the current playbook), \
examples/ (gold-standard playbooks of other decks) and the logs the task names. Open the script of every card whose \
behaviour you rely on, and grep the logs for what really happened. You can't write files: your structured reply is \
your whole output, and the trainer applies it."""

TOOLS_INLINE = """Everything you need is in the message: the card texts, the relevant Lua scripts and the logs."""

STYLE = """## The house style of a playbook

Look at the examples: they are what good looks like (written by an expert after a few games with these decks). A \
playbook has these sections, in this order:

1. `## Lessons from games (newest first; these override everything below)`: empty at first ("None yet: lessons \
from reviewed games go here."). The trainer adds lessons there; never write lessons into it yourself.
2. `## Status of this playbook`: two or three sentences: built from the card texts and scripts; lines marked \
*(unverified)* haven't been played in the engine yet; if the engine offers something different from what a line \
expects, trust the engine's options and adapt. Keep it that short later too: the *(verified ...)* marks belong on \
the lines themselves.
3. `## Game plan`: what kind of deck it is (e.g. "Xyz beatdown", "Ritual midrange"), how it wins, the board it wants \
to end turn 1 on, and how it grinds.
4. `## Engine cards`: one bullet per card that makes the deck work: **bold name**, what it does in practice and how \
to use it here, with the rulings that decide plays (hard or soft once per turn, cost vs effect, "if" vs "when" \
triggers that can miss timing, targeting, summoning conditions, what it can't be used as, the locks it applies). Say \
which cards count as archetype members and which don't when that matters.
5. `## Support cards`: tech cards, hand traps, removal, Spells/Traps: when to use each and what to save it for.
6. `## Extra Deck`: grouped by role (e.g. Rank 4 removal, Rank 4 protection), what each is made from in this deck \
and when to make it. Say plainly which Extra Deck monsters this Main Deck can't make (or only rarely).
7. `## Main lines`: the standard turn-1 lines as numbered steps, each under a heading or bold title that names its \
starting cards ("**Line 1: Geargiarsenal + any Geargia**"), each marked *(unverified)*, each ending with the final \
board. Cover the common 1- and 2-card starts, and what to do with a hand that has no starter.
8. `## Going second / breaking boards`: how this deck gets through an established board: removal, its order, \
when to commit, and when to just set up instead.
9. `## Locks and once-per-turn rules to respect`: a short list of the limits that break combos if forgotten.
10. `## General principles`: deck-specific habits. Cover the decisions the AI makes most often: for each searcher, \
what to take given what is already in hand ("with Saffira and a way to summon her in hand, search Tribute fodder, not \
a second Saffira"); what recurring effects should get back (e.g. a hand trap that's good in this matchup); which \
cards are worth spending as costs or materials and which never are; when protection overlaps (a lock that already \
covers what a held negate would). Not generic Yu-Gi-Oh advice: the general playbook (below) already covers that.

Voice: second person, imperative, concrete card names, short sentences. Every instruction should change a decision \
("When X, do Y because Z"). Bold the key instruction of a bullet. Mark the rulings you checked in a script that are \
easy to get wrong with a short "(script: ...)" note, e.g. "(script: hard once per turn, shared by both effects)". No \
history, no sources, no filler. Size: 9-12 KB of Markdown, and never more than 13 KB (the examples are about 9 and 13 \
KB): it is read on every decision, so cut anything that doesn't change one. Don't restate card texts the AI already \
has; one line of how-to-use beats three of what-it-does."""

GOLD_NOTE = """Things the examples learned the hard way, which apply to any deck:
- The AI chooses one engine-generated option at a time; numbered steps with exact card names are what it follows best.
- Name the exact card to search or send at each step ("add **Sudri**"), and the fallback when it isn't available.
- Remind it to check what is still in the Deck and Extra Deck before a line that needs a specific card.
- Locks ("only DARK monsters from the Extra Deck this turn") and once-per-turn limits must be stated where the line \
uses them, not only in a list at the end."""


def system(rules: str, agentic: bool) -> str:
    rules_text = RULES_TEXT.get(str(rules).upper(), f"{rules} rules.")
    return SYSTEM.format(rules=rules_text, tools=TOOLS_AGENTIC if agentic else TOOLS_INLINE)


def _examples(examples: dict[str, str], agentic: bool) -> str:
    if not examples:
        return "(no examples available)"
    if agentic:
        return ("Read these first: " + ", ".join(f"examples/{name}.md" for name in examples) +
                f" ({', '.join(f'{len(t.encode()) // 1024} KB' for t in examples.values())}).")
    return "\n\n".join(f"### Example: {name}\n\n{text.strip()}" for name, text in examples.items())


def study(name: str, dossier_text: str, general: str, examples: dict[str, str], agentic: bool,
          scripts: str | None = None) -> str:
    parts = [f"""# Task: write the first playbook for the deck "{name}"

Study the deck: the dossier below has the decklist with counts, every card's text, the archetypes, the Main Deck's \
Levels next to the Extra Deck's Ranks/Levels and summoning conditions, and hints read off each script. \
{"The scripts are in scripts/: read them." if agentic else "The scripts are at the end of this message."} Work out how \
the deck really plays: its engine, its best turn-1 lines with real hands (count the copies: a line that needs a \
1-of plus a 2-of is rare), how it uses its Extra Deck, how it plays going second, and which once-per-turn limits and \
locks constrain it. Then write the playbook.

{STYLE}

{GOLD_NOTE}

## Also return
- `lines`: every line of your "Main lines" (and a going-second line if you wrote one) in structured form, for a lab \
where the AI plays turn 1 with a stacked hand against a dummy that does nothing: the id (L1, L2, ...), the name as the \
playbook writes it, going first or second, the key cards (exact Main Deck names, at most 4: the lab fills the rest of \
the hand at random), the expected end board (exact names), and the steps in short.
- `card_checks`: the rulings you checked in the scripts, one per fact: the card, the script file (c<id>.lua), the \
fact, and a short verbatim quote of the script line that proves it (e.g. `e1:SetCountLimit(1,id)`). At least one for \
every engine card. They are checked mechanically against the files; misquotes are dropped.
- `go_first`: whether this deck should choose to go first when it wins the die roll, and `go_first_reason`.
- `open_questions`: what you couldn't settle from the texts and scripts (the lab will test engine behaviour).

## The general playbook (the AI already gets it; don't repeat it)

{general.strip() or "(empty)"}

## Style examples (other decks)

{_examples(examples, agentic)}

## Dossier

{dossier_text.strip()}"""]
    if scripts:
        parts.append(f"## Scripts (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


def lab_review(name: str, playbook: str, results: str, lines: list[dict], round_no: int, player: str,
               board_text: str, agentic: bool, scripts: str | None = None, hands_dir: str = "") -> str:
    parts = [f"""# Task: check the playbook's lines against the lab (round {round_no})

The AI player ({player}) played turn 1 of some lab games with the deck "{name}", reading the playbook below as in a \
real game, against a dummy opponent that never acts or responds. Going first, the hand was stacked: the key cards of \
one of the playbook's lines plus random cards, or a random hand; then the dummy's turn 2 was played too (it only \
draws and passes), so Set Traps and quick effects had their windows, and the duel stopped when turn 3 began. Going \
second (if any), it had 6 cards and the \
opponent started with this board: {board_text}. The lab results below give, for each hand: the hand, the line it \
targets, what the player did (a condensed engine log: its decisions and reasons, the summons and activations), the \
end board, and the problems (engine rejections, invalid replies, fallbacks). \
{f"The full logs are in {hands_dir}<hand>/game.md." if agentic else ""}

1. For each line in `lines` below, decide:
   - verified: a hand that targets it reached the expected board (or a better one) by the line's steps, with no \
engine rejection;
   - partial: it worked with changes: give the corrected steps;
   - failed: the engine didn't allow a step (which one, and why: check the script), or the line can't work;
   - not_tested: no hand reached the point where the line applies.
   Only the log counts. When the player deviated from a correct line, the line isn't disproved: put the deviation in \
`player_errors` and make the wording clearer.
2. Correct the playbook. Return each section you change whole, with its heading, in `sections`:
   - in the lines, replace *(unverified)* with *(verified in lab)* for verified lines; fix failed and partial steps \
(check the script before you write the fix);
   - add the better lines and sequences you found in the logs, marked *(unverified)* unless a log shows them working;
   - random hands show what the deck does with an ordinary draw: if the playbook has no plan for a common hand, add one;
   - fix any card ruling the lab disproved (Engine cards, Locks...).
   Keep the playbook within 8-13 KB and don't touch the lessons section.
3. `new_lines`: lines you added or changed that need a lab test next round (structured as below; keep the ids of \
existing lines). `lessons`: only for a clear, general mistake the playbook should warn about, with evidence (a script \
or log quote; unverifiable lessons are dropped). `open_questions`: what a human should check.

## Lines under test

```json
{json.dumps(lines, indent=1, ensure_ascii=False)}
```

## The current playbook

{playbook.strip()}

## Lab results

{results.strip()}"""]
    if scripts:
        parts.append(f"## Scripts of the cards involved (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


def game_review(name: str, playbook: str, game: dict, log_ref: str, problems: list[str], agentic: bool,
                scripts: str | None = None, recent_lessons: list[str] | None = None) -> str:
    result = {"win": "won", "loss": "lost", "draw": "drew"}.get(game.get("result"), "finished")
    first = "first" if game.get("first") else "second"
    probs = "\n".join(f"- {p}" for p in problems) or "- none"
    kb = len(playbook.encode()) / 1024
    recent = "\n".join(f"- {t}" for t in (recent_lessons or [])) or "- none yet"
    parts = [f"""# Task: review game "{game['id']}" and turn its mistakes into lessons

The AI player ({game.get('backend', 'the player')}) played {name} against {game.get('opponent_text', 'an opponent')} \
and {result} in {game.get('turns', '?')} turns, going {first} ({game.get('reason', '')}). You are its coach: it is \
learning the deck and nobody else reviews its games. {log_ref}

Go through the game turn by turn, the way a coach reviews a student's game:
- Compare what it did with the playbook's main lines and plans; note where it deviated and whether that was better or \
worse.
- Look for: decisions the fallback made and "engine rejected"/"can't take" notes (listed below); unused resources \
(searches not taken, the Normal Summon unused, once-per-turn effects or triggers skipped, a card left in hand that had \
a use this turn); wrong Extra Deck choices or locks; zone clogging; self-damage; missed lethal (add up the damage it \
could have dealt); bad chain timing (hand traps or negation wasted on small effects or held too long, responding too \
early); attacks into face-down or bigger monsters; Spells/Traps never Set (a Quick-Play Spell or Trap in hand does \
nothing on the opponent's turn).
- Verify each candidate mistake before you keep it: the options listed at that decision show what was possible, and \
the script decides the ruling. Drop what you can't verify. "major" means it plausibly cost the game or a lot of \
resources; "minor" otherwise. Don't count the opponent's luck or a weak draw as a mistake.

Then return:
- `mistakes` (all you verified) and `significant_mistakes` (how many are major).
- `lessons`: for the major mistakes and the clear minor ones: one concrete instruction each, in the playbook's \
voice ("**When X, do Y** because Z."), with `evidence`: at least one short verbatim quote from a script (file \
c<id>.lua) or from this game's log (file "{game['id']}", with the decision number). Lessons without evidence that \
checks out are discarded. Don't repeat what the playbook or the recent lessons (below) already say; if the playbook \
said it and the player broke it anyway, put that in `repeated` instead (a candidate for a hard rule).
- `sections`: playbook sections whose text was wrong or misleading, rewritten whole (with the heading). Don't touch \
the lessons section. The playbook is {kb:.1f} KB of a 13 KB budget: when you add text, cut text that matters \
less. Promote lines this game showed working from *(unverified)* to *(verified in game)* and name them in \
`confirmed_lines`.
- `test_cases`: for the clearest mistakes, a regression case: the decision number, a short-kebab-case name, the \
acceptable choices (`expect`, e.g. [[2]] or [[0],[1]]; [[]] means pass) and/or the wrong choice (`reject`), and a \
note. The choices are option indices of that decision as the log lists them. Only decisions whose right answer is \
clear from that decision alone; at most 3.
- `general`: lessons that hold for every deck (timing, rules), proposed for the general playbook (a human decides).
- `rule_proposals`: fixed instructions with no judgment in them, worth hard-coding, in plain words.

## Problems the engine and the agent flagged

{probs}

## Recent lessons (already in the playbook)

{recent}

## The current playbook

{playbook.strip()}"""]
    if scripts:
        parts.append(f"## Scripts of the cards in this game (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


BUDGET = [("Lessons from games", 1.5), ("Status of this playbook", 0.3), ("Game plan", 0.5), ("Engine cards", 2.3),
          ("Support cards", 1.7), ("Extra Deck", 1.4), ("Main lines", 3.2), ("Going second / breaking boards", 1.4),
          ("Locks and once-per-turn rules to respect", 0.5), ("General principles", 0.5)]


def condense(playbook: str, limit_kb: int, previous_kb: float | None = None) -> str:
    budget = "\n".join(f"- {name}: about {kb} KB" for name, kb in BUDGET)
    again = (f"\n\nThis is a second pass: the first one only got it to {previous_kb} KB. Cut harder: use the section "
             "budgets as limits." if previous_kb else "")
    return f"""# Task: tighten the playbook to at most {limit_kb} KB

The playbook below has grown past its size target. The AI player reads it on every decision, so every line must earn \
its place. Rewrite it whole, within these section budgets:
{budget}

- Keep the section order and headings of the house style. Keep the lessons section first: keep the newest one or two \
blocks, and fold older lessons into the body section they belong to (then drop them from the lessons section).
- Status of this playbook: two or three sentences. The *(verified ...)* marks live on the lines themselves; don't \
list what was verified here.
- Keep every verified fact, every "(script: ...)" ruling, every *(verified ...)* mark, and the steps of each line \
(numbered, with exact card names). Merge lines that share their steps ("Line 1 with Monster Reborn: ...").
- Cut repetition (the same advice in two sections), generic advice, game anecdotes and explanations of what a card's \
text already says. Don't add new claims.
Return the whole playbook in `playbook` and a line per cut or merge in `removed`.{again}

## The playbook ({len(playbook.encode()) / 1024:.1f} KB)

{playbook.strip()}"""
