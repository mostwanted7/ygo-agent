"""What the reviewer is told: who it is, the house style of a playbook, and the tasks (the interview questions, study,
lab review, game review, condense, revise: the retry when an edit made saved regression cases fail, and learn: the
owner's notes on a game). The tasks follow CLAUDE.md's coaching procedure ("Decks without a coach"). Every task that
writes the playbook sees the owner's tips (tips.py)."""

from __future__ import annotations

import json

RULES_TEXT = {
    "MR3": "Master Rule 3: Extra Deck monsters are summoned to the Main Monster Zones (there is no Extra Monster "
           "Zone), "
           "the Pendulum Zones are separate from the Spell & Trap Zones, and Link Monsters don't exist.",
}

SYSTEM = """You are an expert Yu-Gi-Oh! player and coach who also knows the EDOPro engine and its Lua card scripts. \
You are training an AI player on one deck. Your job is the deck's playbook: the guide the AI player reads on EVERY \
decision while it plays this deck in EDOPro under {rules} It also gets the general playbook, the decklist and every \
card's full text, so the playbook doesn't restate card texts: it says how to think about the cards, when they are \
worth using, and the rulings that aren't obvious from the text. Games vary a lot, so it teaches principles the player \
applies to the board in front of it, not scripts it follows blindly.

What is true, in order: what the engine did (a game or lab log), the card's Lua script (what the engine runs), the \
card text. Never write a claim about how a card works that you haven't checked in its script; when the text and the \
script seem to differ, the script wins. Never write a lesson you haven't verified against a script or a log.

Playbook text must be GENERALIZED: reusable conditions, actions, reasons and rulings only. Never include dates, \
game IDs, decision numbers, match results, opponent performance, praise, anecdotes, provenance tags or verification \
history. Keep evidence and source references in the structured review/report fields, outside the playbook. A \
pitfall is a concrete reusable caution: omit an empty pitfalls section, and never write "None yet", "None \
outstanding", or commentary about a resolved mistake. Update an existing principle rather than duplicating it.

{tools}"""

TOOLS_AGENTIC = """You have read-only tools (Read, Grep, Glob) in a working folder that holds: scripts/c<id>.lua (the \
script of every card in the deck; scripts/lib/ has the shared helpers such as proc_xyz.lua and utility.lua), \
dossier.md (the decklist, texts, archetypes, Levels and summoning conditions), playbook.md (the current playbook), \
examples/ (playbooks of other decks) and the logs the task names. Open the script of every card whose behaviour you \
rely on, and grep the logs for what really happened. You can't write files: your structured reply is your whole \
output, and the trainer applies it."""

TOOLS_INLINE = """Everything you need is in the message: the card texts, the relevant Lua scripts and the logs."""

SECTIONS = """1. `## How to use this playbook`: two or three sentences: these are principles, not scripts; read the board \
and deviate when a better play exists, saying why in `why`; trust the engine's options over the text.
2. `## Game plan`: what kind of deck it is (e.g. "Rank 4 stun-beatdown"), how it wins, what a good first turn \
leaves on the board, how it grinds, and how it closes games.
3. `## Card roles`: short, grouped by role (starters and extenders, searchers, walls, Extra Deck answers, traps, hand \
traps): what each card is for in this deck, plus only the rulings that decide plays and aren't obvious from the text \
(hard or soft once per turn, cost vs effect, "when" triggers that miss timing, what counts as an archetype member, \
summoning conditions, locks), each checked in the script. Keep citations in the report, outside the playbook. \
One line of how-to-use beats three of what-it-does.
4. `## Situational considerations`: the judgment calls, each as a condition with its reason: "**Consider X when Y**, \
because Z". Which plays fit which hands and boards, when a card is worth more held than used, which Extra Deck \
monster fits which board, what to search given the hand, when to commit and when to just set up. Give the trade-off \
so the player can weigh it against the board, never an unconditional script.
5. `## Lethal check` (whenever the deck has ATK boosts, burn, extra attackers or OTK potential): how to count the most \
damage this turn with this deck's pieces: the attackers still makeable, boosts and whether they stack, burn \
finishers, ways to remove blockers, and the non-obvious lethals (with one worked example).
6. `## Going second / breaking boards`: how the deck gets through an established board, in what order, and when to \
just build instead.
7. `## Example sequences` (optional, at most three, short): common starting conditions and a useful route. \
Examples, not scripts; no match histories or verification labels.
8. `## Known pitfalls` (optional): always last when present. Only concrete, reusable cautions not already covered \
elsewhere. Omit this section when empty; never add a placeholder or a note about a resolved mistake."""

STYLE = f"""## The house style of a playbook

Principles first. A playbook teaches how to think about the deck, so the player can read any board and still make \
the right play, including one the playbook never described. Specific facts that keep causing mistakes go to the \
bottom, in Known pitfalls, not into the principles. Of the examples below, only geargia (when shown) follows this \
style; the older ones are organised differently: borrow their depth and voice, not their layout. Sections, in this \
order:

{SECTIONS}

Voice: second person, short sentences, concrete card names. Every line should change a decision; say why, so the \
player can tell when the reason doesn't apply. No history, no sources, no filler, no restating card texts. Size: 5-8 \
KB of Markdown, never more than 8 KB: it is read on every decision, so cut anything that doesn't change one."""

GOLD_NOTE = """Things earlier playbooks learned the hard way, which apply to any deck:
- The AI picks one engine-generated option at a time and already has every card text: tell it what matters and why.
- A condition with its reason lets the player deviate sensibly; an unconditional rule makes it follow the text into a \
bad play when the board is different.
- State locks and once-per-turn limits in the card's own line, where the decision is made.
- Remind it to check what is still in the Deck and Extra Deck before a play that needs a specific card.
- Players miss lethal more than anything else: a deck with damage boosts or burn needs its own Lethal check."""


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


def _questions(questions: list[str] | None) -> str:
    if not questions:
        return "- none"
    return "\n".join(f"{n}. {q}" for n, q in enumerate(questions, 1))


TIPS_RULE = """The deck's owner wrote these tips: how they play this deck, in their own words. They win over your \
own reading of the cards, so the playbook follows them and never contradicts one silently. Only a card's script (or \
what the engine did in a log) beats a tip: then follow the script, and add an open question that names the tip and the \
script line, so the owner can settle it."""
TIPS_LIMIT = 12000


def tips_text(tips: list[dict] | None, new: list[int] | None = None) -> str:
    """The owner's tips (tips.entries()), numbered; `new` marks the numbers not folded into the playbook yet."""
    out = []
    for n, t in enumerate(tips or [], 1):
        when = f" ({t['date']})" if t.get("date") else ""
        mark = " **NEW**" if new and n in new else ""
        out.append(f"{n}. **{t['title']}**{when}{mark}\n   " + t["text"].strip().replace("\n", "\n   "))
    text = "\n".join(out)
    return text if len(text) <= TIPS_LIMIT else text[:TIPS_LIMIT] + "\n   [… cut: the rest is in tips.md]"


def _tips_section(tips: list[dict] | None, intro: str = "") -> str:
    if not tips:
        return ""
    return f"\n\n## The owner's tips\n\n{TIPS_RULE}{' ' + intro if intro else ''}\n\n{tips_text(tips)}"


STUDY_TIPS = ("Write the playbook from the dossier AND these tips: turn each one into principles in the sections where "
              "the decision is made, in the house style and with its reason (not pasted verbatim); where a tip names a "
              "line or a priority, that is the deck's main line or priority.")
LAB_TIPS = ("A lab hand that shows a tip's line failing is a fact for an open question, not a reason to drop the tip "
            "from the playbook silently.")
REVIEW_TIPS = "A play that followed a tip is not a mistake unless the board made the tip's reason not apply."


def study(name: str, dossier_text: str, general: str, examples: dict[str, str], agentic: bool,
          scripts: str | None = None, tips: list[dict] | None = None) -> str:
    parts = [f"""# Task: write the first playbook for the deck "{name}"

Study the deck: the dossier below has the decklist with counts, every card's text, the archetypes, the Main Deck's \
Levels next to the Extra Deck's Ranks/Levels and summoning conditions, and hints read off each script. \
{"The scripts are in scripts/: read them." if agentic else "The scripts are at the end of this message."} Work out how \
the deck really plays: its engine, what it does with real hands (count the copies: a play that needs a 1-of plus a \
2-of is rare), how it uses its Extra Deck, how it wins and how fast, how it plays going second, and which \
once-per-turn limits and locks constrain it. Then write the playbook.

{STYLE}

{GOLD_NOTE}

## Also return
- `lines`: the deck's standard turn-1 plays (and a going-second one), in structured form, for a lab where the AI \
plays turn 1 with a stacked hand against a dummy that does nothing: the id (L1, L2, ...), a name (use the name of the \
matching Example sequence when there is one), going first or second, the key cards (exact Main Deck names, at most 4: \
the lab fills the rest of the hand at random), the expected end board (exact names), and the steps in short. These \
are for testing only: the playbook keeps at most three of them, as Example sequences.
- `card_checks`: the rulings you checked in the scripts, one per fact: the card, the script file (c<id>.lua), the \
fact, and a short verbatim quote of the script line that proves it (e.g. `e1:SetCountLimit(1,id)`). At least one for \
every key card. They are checked mechanically against the files; misquotes are dropped.
- `go_first`: whether this deck should choose to go first when it wins the die roll, and `go_first_reason` (an \
owner's tip about going first or second decides it, unless the scripts show it can't work).
- `open_questions`: what you couldn't settle from the texts and scripts (the lab will test engine behaviour), and \
every conflict between an owner's tip and a script.{_tips_section(tips, STUDY_TIPS)}

## The general playbook (the AI already gets it; don't repeat it)

{general.strip() or "(empty)"}

## Examples (other decks)

{_examples(examples, agentic)}

## Dossier

{dossier_text.strip()}"""]
    if scripts:
        parts.append(f"## Scripts (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


def lab_review(name: str, playbook: str, results: str, lines: list[dict], round_no: int, player: str,
               board_text: str, agentic: bool, scripts: str | None = None, hands_dir: str = "",
               open_questions: list[str] | None = None, tips: list[dict] | None = None) -> str:
    kb = len(playbook.encode()) / 1024
    parts = [f"""# Task: check the playbook against the lab (round {round_no})

The AI player ({player}) played turn 1 of some lab games with the deck "{name}", reading the playbook below as in a \
real game, against a dummy opponent that never acts or responds. Going first, the hand was stacked: the key cards of \
one of the deck's standard plays (`lines` below) plus random cards, or a random hand; then the dummy's turn 2 was \
played too (it only draws and passes), so Set Traps and quick effects had their windows, and the duel stopped when \
turn 3 began. Going second (if any), it had 6 cards and the \
opponent started with this board: {board_text}. The lab results below give, for each hand: the hand, the line it \
targets, what the player did (a condensed engine log: its decisions and reasons, the summons and activations), the \
end board, and the problems (engine rejections, invalid replies, fallbacks). \
{f"The full logs are in {hands_dir}<hand>/game.md." if agentic else ""}

1. For each line in `lines` below, decide:
   - verified: a hand that targets it reached the expected board (or a better one), with no engine rejection;
   - partial: it worked with changes: give the corrected steps;
   - failed: the engine didn't allow a step (which one, and why: check the script), or the line can't work;
   - not_tested: no hand reached the point where the line applies.
   Only the log counts. A player who deviated from the line isn't wrong by itself: judge the end board. When a \
correct line was missed, put it in `player_errors` with the wording that would fix it.
2. Correct the playbook. Return each section you change whole, with its heading, in `sections`:
   - fix the card rulings and considerations the lab disproved (check the script before you write the fix), and turn \
what the hands showed into conditions ("consider X when Y, because Z"), not new step-by-step scripts;
   - fix failed steps in Example sequences; keep verification status in `verification`, not in the playbook;
   - random hands show what the deck does with an ordinary draw: if no principle covers a common hand, add one.
   Keep the playbook within 8 KB (now {kb:.1f} KB): when you add, cut what matters less. Don't touch Known pitfalls.
3. `new_lines`: lines you added or changed that need a lab test next round (structured as below; keep the ids of \
existing lines). `lessons`: only for a clear, repeatable mistake worth a Known pitfall, one or two sentences, with \
evidence (a script or log quote; unverifiable lessons are dropped). `settled_questions`: the open questions below \
that the logs or scripts now answer (number and one-line answer). `open_questions`: new ones for a human, including \
an owner's tip the lab contradicts.{_tips_section(tips, LAB_TIPS)}

## Lines under test

```json
{json.dumps(lines, indent=1, ensure_ascii=False)}
```

## Open questions so far

{_questions(open_questions)}

## The current playbook

{playbook.strip()}

## Lab results

{results.strip()}"""]
    if scripts:
        parts.append(f"## Scripts of the cards involved (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


def game_review(name: str, playbook: str, game: dict, log_ref: str, problems: list[str], agentic: bool,
                scripts: str | None = None, recent_lessons: list[str] | None = None,
                open_questions: list[str] | None = None, tips: list[dict] | None = None) -> str:
    result = {"win": "won", "loss": "lost", "draw": "drew"}.get(game.get("result"), "finished")
    first = "first" if game.get("first") else "second"
    probs = "\n".join(f"- {p}" for p in problems) or "- none"
    kb = len(playbook.encode()) / 1024
    recent = "\n".join(f"- {t}" for t in (recent_lessons or [])) or "- none yet"
    parts = [f"""# Task: review game "{game['id']}" and improve the playbook

The AI player ({game.get('backend', 'the player')}) played {name} against {game.get('opponent_text', 'an opponent')} \
and {result} in {game.get('turns', '?')} turns, going {first} ({game.get('reason', '')}). You are its coach: it is \
checking the basics of the deck's playbook. {log_ref}

These practice games test common combos, obvious errors and contradictions. Revise the general guidance only \
when the evidence supports a reusable correction. Do not turn an individual game's sequence, result, opponent \
behavior or successful play into a playbook entry. Keep those details in the review report.

Go through the game turn by turn, the way a coach reviews a student's game:
- Judge each play on the board, not on whether it followed the playbook: the playbook is guidance, and a deviation \
that was as good or better is not a mistake (if it was better, improve the principle it broke).
- Judge each play only by what the player could know at that moment, never by what a face-down card turned out to \
be or how it worked out: a risky play that happened to work is still risky. Several lines are often equally good; \
call a play a mistake only if it was clearly worse with what was known.
- Look for: decisions the fallback made and "engine rejected"/"can't take" notes (listed below); unused resources \
(searches not taken, the Normal Summon unused, once-per-turn effects or triggers skipped, a card left in hand that had \
a use this turn); wrong Extra Deck choices or locks; zone clogging; self-damage; missed lethal (add up the most damage \
it could have dealt, boosts and burn included); bad chain timing (hand traps or negation wasted on small effects or \
held too long, responding too early); attacks into face-down or bigger monsters; Spells/Traps never Set.
- Verify each candidate mistake before you keep it: the options listed at that decision show what was possible, and \
the script decides the ruling. Drop what you can't verify. "major" means it plausibly cost the game or a lot of \
resources; "minor" otherwise. Don't count the opponent's luck or a weak draw as a mistake.
- For each mistake also say whether it needed judgment (`no_judgment`: true only when one answer was clearly right \
whatever the rest of the game, e.g. a missed trigger or a misread ruling), and quote the playbook line it played \
with that already covered it (`playbook_had`, verbatim; "" if nothing did).

Then return:
- `mistakes` (all you verified) and `significant_mistakes` (how many are major).
- `sections`: the main way to improve the playbook. When a mistake shows a principle is missing, wrong or misleading, \
rewrite that section whole (with the heading), as conditions with reasons, generalised beyond this game. Don't touch \
Known pitfalls. The playbook is {kb:.1f} KB of an 8 KB budget: when you add text, cut text that matters less. Correct \
failed steps in Example sequences when needed. Record working lines only in `confirmed_lines`, without adding \
verification history to the playbook.
- `lessons`: only for significant, repeatable mistakes that a principle can't carry (a ruling the player keeps \
misreading, an engine quirk, a matchup trap). Each becomes a Known pitfall: one or two sentences, generalised ("**When \
X, do Y** because Z", not this game's exact board), with `evidence`: at least one short verbatim quote from a script \
(file c<id>.lua) or from this game's log (file "{game['id']}", with the decision number). Lessons without evidence \
that checks out are discarded. Don't repeat what the playbook or the recent lessons (below) already say.
- `test_cases`: for the clearest mistakes, a regression case: the decision number, a short-kebab-case name, the \
acceptable choices (`expect`, e.g. [[2]] or [[0],[1]]; [[]] means pass; list every acceptable choice, not just the \
best) and/or the wrong choice (`reject`), and a note. The choices are option indices of that decision as the log \
lists them. Only decisions whose right answer is clear from that decision alone; at most 3.
- `rule_proposals`: only for a no-judgment mistake that the playbook already covered (`playbook_had`) and the player \
made anyway: the rule in plain words, the decisions that show it, the regression case that proves it (a name from \
your `test_cases` or an existing case), and optionally the rule as a Python function `def name(ctx):` that returns \
None or `Decide(choice, why)` (ctx is ygo_agent.agent.rules.Context: ctx.kind, ctx.options, ctx.find(name=, action=), \
ctx.names(side, zone), ctx.my_turn, ctx.phase, ctx.chain_names()). Everything else belongs in the playbook.
- `general`: lessons that hold for every deck (timing, rules), proposed for the general playbook (a human decides).
- `settled_questions`: the open questions below that this game or the scripts answer (number and one-line answer).
- `open_questions`: what a human must settle, e.g. an owner's tip (below) that this game or a script contradicts \
(name both); usually none.{_tips_section(tips, REVIEW_TIPS)}

## Problems the engine and the agent flagged

{probs}

## Recent lessons (already in the playbook)

{recent}

## Open questions so far

{_questions(open_questions)}

## The current playbook

{playbook.strip()}"""]
    if scripts:
        parts.append(f"## Scripts of the cards in this game (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)


BUDGET = [("How to use this playbook", 0.4), ("Game plan", 0.5), ("Card roles", 2.0),
          ("Situational considerations", 1.8), ("Lethal check", 1.0), ("Going second / breaking boards", 0.6),
          ("Example sequences", 0.5), ("Known pitfalls", 1.2)]

CONDENSE_RULES = """- Keep the house style's section order and headings, principles first and Known pitfalls last.
- Turn step-by-step scripts into conditions with their reasons ("consider X when Y, because Z"); keep at most three \
short Example sequences.
- Known pitfalls: fold the ones a principle now covers into that principle and drop them from the list; merge \
pitfalls that say the same thing; keep each one or two sentences. Omit the section if nothing remains.
- Keep every checked ruling and the Lethal check's numbers. Remove dates, game references, source citations, \
verification labels, results, praise and resolved-mistake commentary.
- Keep the point of every owner's tip (when tips are listed below): cut its wording, never what it says.
- Copy a section the deck's owner wrote (e.g. "Coaching lessons") exactly as it is: it is theirs.
- Cut repetition, generic advice the general playbook covers, game anecdotes and restated card texts. Don't add claims."""
KEEP_STRUCTURE = """- This playbook is hand-written, not in the house style: keep its own sections, headings and order, and \
its lessons section where it is; tighten inside each section."""


def condense_rules(keep_structure: bool = False) -> str:
    """The condense rules; for a hand-written playbook, without the house style's layout."""
    if not keep_structure:
        return CONDENSE_RULES
    return KEEP_STRUCTURE + "\n" + CONDENSE_RULES.split("\n", 1)[1]


def condense(playbook: str, limit_kb: int, previous_kb: float | None = None, tips: list[dict] | None = None,
             keep_structure: bool = False) -> str:
    budget = "\n".join(f"- {name}: about {kb} KB" for name, kb in BUDGET)
    again = (f"\n\nThis is a second pass: the first one only got it to {previous_kb} KB. Cut harder: use the section "
             "budgets as limits." if previous_kb else "")
    return f"""# Task: tighten the playbook to at most {limit_kb} KB

The playbook below has grown past its size target. The AI player reads it on every decision, so every line must earn \
its place. Rewrite it whole, within these section budgets:
{budget}

{condense_rules(keep_structure)}

The result is checked against the saved regression cases: a version that makes the player fail a case it passed is \
rejected. Return the whole playbook in `playbook` and a line per cut or merge in `removed`.{again}

## The house style

{SECTIONS}{_tips_section(tips)}

## The playbook ({len(playbook.encode()) / 1024:.1f} KB)

{playbook.strip()}"""


def failures_text(failures: list[dict]) -> str:
    out = []
    for f in failures:
        out.append(f"### Case `{f['name']}`: {f.get('note') or ''}\n"
                   f"- Decision: {f.get('question') or '?'}\n"
                   f"- Right: {'; '.join(f.get('expected') or []) or 'anything but the wrong choice'}\n"
                   + (f"- Wrong: {'; '.join(f['rejected'])}\n" if f.get("rejected") else "")
                   + f"- With the new text the player chose: {'; '.join(f.get('chose') or []) or '?'} "
                     f"({f.get('after')} runs right, {f.get('before')} with the previous text)")
    return "\n\n".join(out)


def revise(before: str, after: str, failures: list[dict], limit_kb: int, what: str = "edit",
           tips: list[dict] | None = None, keep_structure: bool = False) -> str:
    return f"""# Task: fix a playbook {what} that broke saved regression cases

The playbook was changed (the {what} below). Replayed against the saved regression cases (past decisions with a known \
right answer), the AI player now gets these wrong more often than it did with the previous text. Return the changed \
playbook with what the player needs to get them right restored: put the missing principle or pitfall back, in the \
house style, without undoing the {what}'s other improvements, and stay within {limit_kb} KB.

{condense_rules(keep_structure)}

Return the whole playbook in `playbook` and a line per change in `removed`.

## The cases that got worse

{failures_text(failures)}

## The house style

{SECTIONS}{_tips_section(tips)}

## The previous playbook ({len(before.encode()) / 1024:.1f} KB)

{before.strip()}

## The changed playbook ({len(after.encode()) / 1024:.1f} KB)

{after.strip()}"""


# ---- the interview ----

LAST_QUESTION = {"id": "anything-else", "question": "Anything else the agent should know about this deck?",
                 "why": "Whatever the questions above missed: a pet line, a matchup, a habit to avoid."}


def interview(name: str, dossier_text: str, tips: list[dict] | None = None) -> str:
    said = f"\n\n## What the owner already told you (don't ask it again)\n\n{tips_text(tips)}" if tips else ""
    return f"""# Task: interview the deck's owner

Before you write the playbook for "{name}", you can ask its owner, an experienced player of this deck, a few \
questions. Read the dossier below (every card, its text, and what its script does), then write 3 to 6 questions that \
someone who plays this deck can answer in a sentence or two, and whose answers would change how the playbook tells the \
AI to play. Ask what the cards alone don't tell you, for example:
- how the deck wins, and how fast;
- its main lines and their key cards, and which starter it prefers;
- going first or second, and what changes;
- which Extra Deck monsters matter, and when;
- what not to do: the traps a new player of this deck falls into;
- choices between cards: what to search, what to keep in hand, what to send to the GY.

Name the cards. One thing per question, in plain words. Don't ask what the card texts answer. Most important first. \
For each, `why`: what the answer changes in the playbook, in one short sentence the owner reads (e.g. "So the playbook \
knows which Rank 4 to make first."). A last question, "{LAST_QUESTION['question']}", is always added: don't write \
it.{said}

## Dossier

{dossier_text.strip()}"""


# ---- learn: the owner's notes and tips ----

MODES = {
    "play": "The owner played against the AI player",
    "selfplay": "The owner watched the AI player in a game against another AI",
    "teach": "The owner watched the AI player play and explain its moves",
    "coach": "The owner played this game themselves while the AI coached them. Every move in the log is the owner's; "
             "the coach's advice is the line under each decision marked as the coach's, and the coach reads the same "
             "playbook, so a note about the advice is a note about the playbook. In the game",
}
LEARN_STYLE = """- Keep the playbook's style: principles first, each a condition with its reason ("**Consider X when Y**, \
because Z") that the player may override when the board calls for it, generalised beyond this game, exact card names, \
no step-by-step scripts."""
LEARN_STYLE_OWN = """- This playbook is hand-written, not in the house style: keep its own sections, order and voice; \
still phrase what you add as a condition with its reason, generalised beyond this game."""
LEARN_RULES = """- Never edit the Known pitfalls section or a section the owner wrote (e.g. "Coaching lessons"): \
pitfalls go in `lessons`, and the owner's sections are theirs.
- All playbook edits and `lessons` must be reusable guidance: no dates, game IDs, decision numbers, match results, \
opponent assessments, verification labels or empty/resolved-pitfall commentary.
- The playbook is {kb:.1f} KB of an 8 KB budget: when you add, cut what matters less in the same section.
- `open_questions`: what a human must settle (a note or a tip that a script contradicts: name both); usually none.
- `summary`: two or three sentences on what this taught the playbook."""
NEW_TIPS = """The tips marked **NEW** were added since the playbook last took the tips in. Fold each into the playbook: \
check any ruling it states in the card's script, then put it where the decision is made, as a principle in the \
playbook's style and with its reason (not pasted verbatim), unless the playbook already says the same. Give a verdict \
for each NEW tip in `tips` (by its number), as for a note."""


def learn(name: str, playbook: str, *, game: dict | None = None, notes: list[dict] | None = None,
          decisions: str = "", log_ref: str = "", problems: list[str] | None = None, tips: list[dict] | None = None,
          new_tips: list[int] | None = None, agentic: bool = False, scripts: str | None = None,
          house_style: bool = True) -> str:
    """The owner's notes on one game (`game`, `notes`), the NEW tips, or both, in one task."""
    kb = len(playbook.encode()) / 1024
    style = LEARN_STYLE if house_style else LEARN_STYLE_OWN
    rules = style + "\n" + LEARN_RULES.format(kb=kb)
    tips_part = ""
    if tips:
        tips_part = f"\n\n## The owner's tips\n\n{TIPS_RULE}" + (f"\n\n{NEW_TIPS}" if new_tips else "") + \
                    f"\n\n{tips_text(tips, new_tips)}"
    if agentic:
        others = ", and of the other cards the log names (mostly the opponent's)," if game else ""
        where = (f"The scripts of the deck's cards{others} are in scripts/ (scripts/lib/ has the shared helpers); "
                 "dossier.md has every card of the deck with its text and what its script does; playbook.md is the "
                 "playbook.")
    else:
        where = "The scripts of the cards involved are at the end of this message."
    if game is None:
        parts = [f"""# Task: fold the owner's new tips into the playbook of "{name}"

The deck's owner added tips about how they play this deck. {where} There is no game to look at: `notes` and \
`test_cases` stay empty.

{rules}{tips_part}

## The current playbook

{playbook.strip()}"""]
    else:
        result = {"win": "won", "loss": "lost", "draw": "drew"}.get(game.get("result"), "finished")
        first = {True: "first", False: "second"}.get(game.get("first"), "first or second (unknown)")
        mode = MODES.get(game.get("mode"), "The owner watched this game")
        listed = "\n".join(
            f"{n['n']}. ({n['context']}; from {n['author']}) {n['text']}"
            + ("" if n.get("trusted") else "\n   [Not the owner's: someone else in the room typed it. Apply it only "
                                           "if the log and the scripts clearly back it.]") for n in notes or [])
        probs = "\n".join(f"- {p}" for p in problems or []) or "- none"
        opponent = game.get("opponent") or "an opponent"
        parts = [f"""# Task: learn from the owner's notes on game "{game['id']}"

{mode}: the AI player ({game.get('backend') or 'the agent'}) played {name} against {opponent} and {result} in \
{game.get('turns') or '?'} turns, going {first}. While it played, the owner typed the notes \
below. Each was saved right after the decision it follows ("right after decision #14"): it is about that decision, or \
one shortly before it. {log_ref} {where}

The owner knows this deck and how they want it played. On strategy (what to prioritise, when to commit, which line is \
better), take a note as right unless the log shows it misread the board. On rulings (how a card or the engine works), \
check every claim in the card's script and in the log before you write it: when a script contradicts a note, the \
script wins, and the verdict says so.

For each note:
1. Find the decision it is about: its options, what the player chose, and the reason it gave.
2. Check the claim against the board at that point (the log) and the scripts of the cards involved.
3. Give a verdict in `notes` (by the note's number, with the decision it is about):
   - `applied`: you changed the playbook so the player gets it right next time;
   - `already_covered`: the playbook already says it plainly, where the decision is made, and nothing needs to \
change (quote the line in `outcome`). If the player missed a line that is there, ask whether it is in the wrong place \
or too weak: then strengthen or move it, and the verdict is `applied`;
   - `disagree`: the log or a script shows the note is wrong, or the play was as good: say why.
   `outcome` is one line the owner reads: what changed (the section and the gist), or why not.
4. Fix the playbook for what you apply. When a principle is missing, wrong or misleading, rewrite that section whole \
in `sections` (its heading and its whole new body, keeping the rest of its content). A specific, repeatable mistake \
that a principle can't carry (a misread ruling, an engine quirk) becomes a Known pitfall in `lessons`: one or two \
sentences, "**When X, do Y** because Z", with `evidence`: a short verbatim quote of a script (file c<id>.lua) or of \
this game's log (file "{game['id']}", with the decision number); a lesson whose evidence doesn't check out is dropped. \
Prefer a principle over a pitfall.
5. For each decision you apply a note to, propose a regression case in `test_cases` when its right answer is clear \
from that decision alone: the decision number, a short-kebab-case name, every acceptable choice in `expect` (option \
indices as the log lists them, e.g. [[2]] or [[0],[3]]; [[]] means pass), or only the blunder in `reject` when \
several plays were fine, and a one-sentence note. The choice the player made can't be in `expect`.

{rules}{tips_part}

## The notes

{listed}

## The decisions they follow (as the log shows them, every option listed)

{decisions.strip() or "(not found in the log)"}

## Problems the engine and the agent flagged

{probs}

## The current playbook

{playbook.strip()}"""]
    if scripts:
        parts.append(f"## Scripts of the cards involved (comments stripped)\n\n{scripts}")
    return "\n\n".join(parts)
