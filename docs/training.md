# Training the agent on a new deck

`ygo-agent train` turns a `.ydk` into a deck folder the agent can play from. It does what Opus did by hand for
Saffira and Blackwing: read every card and its script, write a guide, try the lines, play a few games, review them
against the scripts and the engine log, and correct itself until a round of games shows no significant mistakes.

```sh
ygo-agent train ~/Games/ProjectIgnis/deck/Geargia.ydk --name geargia            # defaults: opus reviews, sonnet plays
ygo-agent train ~/Games/ProjectIgnis/deck/Geargia.ydk --name geargia --budget-usd 40 \
    --lab-hands 9 --games 2 --max-rounds 2 --opponents windbot:Blue-Eyes,windbot:Dragunity
ygo-agent train --name geargia --resume                                         # continue a stopped run
ygo-agent train ~/Games/ProjectIgnis/deck/Chaos.ydk --name chaos --phases study  # only the draft playbook
ygo-agent train-compare --name geargia --games 2                                 # trained vs draft vs no playbook
```

Then play it like any other deck: `ygo-agent play --deck geargia`, `ygo-agent selfplay --a geargia:sonnet ...`.

## The playbook it writes

Principles first, because games vary too much for scripts: the player reads the board and is told to deviate when a
better play exists. `decks/geargia/playbook.md` is the reference, and the study's first example. Sections, in order:

1. **How to use this playbook**: principles, not scripts; deviate and say why; trust the engine's options.
2. **Game plan**: what the deck is, how it wins, what a good first turn leaves, how it grinds and closes.
3. **Card roles**: short, by role, with only the rulings that decide plays (checked in the scripts).
4. **Situational considerations**: the judgment calls as conditions with reasons ("consider X when Y, because Z").
5. **Lethal check** (for decks with boosts, burn or OTKs): how to count the most damage this turn, non-obvious lethals.
6. **Going second / breaking boards**.
7. **Example sequences** (optional, at most three, marked *(unverified)* until the lab or a game shows them).
8. **Known pitfalls**, always last: the specific mistakes from reviewed games, one or two lines each, dated and naming
   the game. The trainer adds them; reviews prefer fixing a principle over adding a pitfall.

The budget is 5-8 KB; above 8.5 KB a condense pass folds pitfalls into principles and tightens the rest.

## What it produces

The deck folder is `<user decks dir>/<name>/` (`~/.local/share/ygo-agent/decks/<name>/` unless `[decks] user_dir`
says otherwise), or `decks/<name>/` in the repo with `--into repo`:

```
<name>/
  deck.ydk  deck.json         a copy of the deck file; the name, and go_first as the study decided
  playbook.md                 the playbook the agent reads on every decision
  rules.py                    RULES = [] unless --write-rules wrote a rule that qualifies (see Hard rules)
  tests/*.json                regression cases from the reviews (ygo-agent test --deck <name>)
  train/
    train-report.md           rounds, win rates, the lab table, pitfalls, case checks, mistakes by model, rules, cost
    state.json                the checkpoint: every finished step, the cost ledger, lines, case scores, questions
    trainer.log               what the run did, with timestamps
    dossier.md cards.json     the deck dossier; scripts/c<id>.lua (and scripts/lib/) are the scripts it used
    examples/                 the playbooks the study was shown (never the deck's own)
    study/                    playbook-draft.md, card-checks.md (each script citation, checked or not)
    round-N/lab/              hand-NN/ (game logs), hand-NN.json, lab-results.md
    round-N/games/            the games' logs (game.md, ...) and runs/<id>/ (results.json, replays)
    round-N/reviews/          each game's condensed log and the reviewer's JSON
    round-N/playbook*.md      the playbook before the games, after the lab, after each review, at the end of the round
    gates/                    each text replayed against the saved cases, and those replays
    calls/                    every reviewer call: the prompt, the reply, the transcript and the files it read
    general-proposals.md      lessons the reviewer thinks hold for every deck (never applied automatically)
    rule-proposals.md         proposed hard rules, and whether each qualifies
    tests-final.txt           the regression cases re-run against the final playbook
```

## How it works

1. **Study.** The dossier lists the deck with counts, every card's text and type line, its archetypes (decoded
   setcodes, with the sub-archetype rule), the Main Deck's Levels next to the Extra Deck's Ranks/Levels, each Extra
   Deck monster's summoning condition, and hints read off each Lua script (effect type, `SetCountLimit` = soft/hard
   once per turn, costs, "if"/"when" triggers, procedures, restrictions). The scripts are the ones the engine runs
   (EDOPro's search order, repositories first). The reviewer writes the draft playbook in the house style, the deck's
   standard plays in structured form for the lab (they don't go into the playbook as scripts), and the rulings it
   checked with a verbatim quote of the script line; each quote is checked against the file (`study/card-checks.md`).
2. **Lab.** The player plays turn 1 with stacked hands: the key cards of each standard play plus random fill, random
   hands for coverage, and (by default 2) going-second turns with 6 cards into a fixed board (Blue-Eyes White Dragon,
   a face-down monster, two Set traps). The opponent is a dummy that ends every phase and passes every chain
   (`trainer/goldfish.py`), and the duel stops when the next turn starts, with the end board recorded straight from
   the engine. The reviewer gets each hand, the condensed log, the end board and the problems (engine rejections,
   invalid replies, fallbacks), marks each play verified / partial / failed / not tested, and corrects the sections
   that need it. Later rounds re-test only what isn't verified yet.
3. **Games.** Games against the opponent pool, alternating who goes first (the agent is made the one that chooses).
   A WindBot deck AI is accepted only if its `bots.json` entry allows the rules and its deck has no Link monsters
   (Dark Magician, Blue-Eyes Ritual, Sacred Beast and others are refused under Master Rule 3). Each game is
   reviewed as CLAUDE.md's "Decks without a coach" says: turn by turn, judging each play on the board (a deviation
   from the playbook that was as good or better is not a mistake), looking for fallbacks, engine rejections, unused
   resources, Extra Deck locks, zone clogging, self-damage, missed lethal and chain timing. A mistake that shows a
   missing principle becomes a section rewrite; only a significant, repeatable one becomes a Known pitfall.
4. **Converge.** Rounds of lab + games repeat until a round's reviews find no major mistake, or `--max-rounds` or the
   budget runs out. The saved regression cases are re-run against the final playbook with the player's backend, and
   `train-report.md` is written.

### What keeps it honest

- **No lesson without evidence.** Every pitfall must quote a script line or the game log (with the decision number).
  The trainer checks each quote against the file (punctuation- and whitespace-insensitive, with a little slack for
  misquotes). Pitfalls that fail, or repeat one already in the playbook, are not applied and are listed in the report.
- **No rewrite that loses behaviour.** Every condense pass and every section rewrite from a lab or game review is
  replayed against the saved regression cases with the player's backend (`--gate-repeat` runs each, default 2; 0
  turns it off). If the cases pass less often than with the previous text, the reviewer gets one retry with the
  failing cases (the decision, the right option, what the player chose); if that doesn't hold either, the previous
  text stays. The scores are cached by text; a text that wasn't measured is compared with the last accepted score.
- **Regression cases are checked too:** the decision must exist in that game's log, the choices must be legal for it,
  and the case must not "expect" what the player actually did. The reviewer is asked to list every acceptable choice.
  They are saved with `replay.save_case`, like `ygo-agent replay --save`.
- **Open questions get pruned:** each lab and game review sees the open questions so far and settles the ones its
  logs and the scripts answer; the report lists only what is still open.
- **The reviewer can't write anything.** With the claude-code backend it is agentic: `claude -p` with only Read, Grep
  and Glob, `--permission-mode dontAsk --restricted`, no settings, MCP servers or slash commands, in a sandbox folder
  outside the repo (`~/.cache/ygo-agent/trainer/<name>/`) that holds copies of what the task needs: the scripts, the
  dossier, the playbook, the examples and the logs under review. It returns JSON; the trainer applies it. With
  `--inline`, or the anthropic/openai backends, the prompt carries the excerpts instead (the scripts of the cards
  involved, the condensed log).
- Section edits can't touch Known pitfalls; the trainer writes those itself, newest first, tagged with the date and
  the game.

### Hard rules

A hard rule (rules.py) overrides the model, so it is only for a mistake with no judgment in it that the **play
model** (`agent.backend`, or `[trainer] play_model`) makes even though the playbook already covered it, and a saved
regression case must prove it. For every mistake the review records whether it needed judgment and quotes the
playbook line that already covered it (checked against the playbook the game was played with); the report counts
mistakes by model. A rule proposal is assessed against those conditions (`trainer/rulepolicy.py`): all of them go to
`train/rule-proposals.md` with the reasons, and the ones that qualify are written into rules.py (with `@cases`) only
with `--write-rules`. With the defaults (Sonnet plays, Opus is the play model) nothing qualifies by itself: check
the case with `ygo-agent test --deck <name> <case> --backend opus` first. Since rules are calibrated to one model,
`ygo-agent test --deck <name> --ablate-rules` replays each rule's cases with that rule disabled (or, for a rule with
no case, the decisions it answered in the game logs) and reports the rules the model no longer needs.

### Budget, checkpoints, usage limits

- Every step (the study, each lab hand, each game, each review) is checkpointed in `train/state.json`;
  `--resume` skips what's done. Ctrl+C, a budget stop or a crash lose at most the step in progress.
- `--budget-usd N`: before each paid step the trainer compares what is spent plus an estimate (the average of that
  kind of step so far) with the budget, and stops cleanly, still writing the report. Reviewer calls also get
  `--max-budget-usd` with what's left. The costs are the CLI's API-price figures; a Claude Code subscription isn't
  billed per call, so treat them as a measure of usage.
- A usage or rate-limit error (from the reviewer, or in a player's game log) stops the run with
  `stopped: usage limit`; `--resume` after the reset finishes it. A game the player's backend couldn't finish is
  not counted.

## Reviewing and accepting the output

1. Read `train/train-report.md`: the win rate per round, which plays the lab verified, the pitfalls, the rejected
   ones, the case checks, the rule proposals and the open questions.
2. Read the deck's `playbook.md` against the scripts (`train/scripts/`). Lines still marked *(unverified)* haven't
   been seen working in the engine. Edit it freely: it's yours now, and the usual feedback loop (CLAUDE.md) applies.
3. Look at `train/general-proposals.md` and `train/rule-proposals.md`, and copy what you agree with.
4. `ygo-agent test --deck <name>` re-runs the saved cases; delete the ones you disagree with.
5. To see what the training bought, `ygo-agent train-compare --name <name>` plays the same games (opponent, seeds,
   who goes first) with the trained playbook, the study draft and none.

## Costs and times observed

Geargia (2026-10-21, before the principle-first style and the case gate), Opus reviewing through Claude Code
(agentic), Sonnet playing, 2 rounds of 2 games against WindBot Blue-Eyes and Dragunity, a 9-hand lab in round 1 and 6
hands in round 2. In API-price dollars (a subscription isn't billed per call):

| step | calls | cost | time |
|---|---|---|---|
| study (dossier + draft playbook, 31 file reads) | 1 | $1.22 | 4 min |
| lab hands (Sonnet, 3 at a time) | 15 | $2.64 | 11 min |
| lab reviews | 2 | $1.28 | 3 min |
| games (2 at a time, 3-13 turns) | 4 | $4.55 | 17 min |
| game reviews | 4 | $3.25 | 11 min |
| condense passes | 3 | $0.80 | 3 min |
| regression cases (7 cases x2) | 2 | $0.59 | 3 min |
| **total** | | **$14.3** | **about 50 min of wall time** |

The case gate adds one replay of the saved cases per checked edit: 7 cases x2 on Sonnet took 14 calls, $0.28 and
1.5 minutes per text (2026-10-22), so a round with a lab review, a few game reviews and a condense adds a dollar or
two. A study-only run (`--phases study`) is one Opus call: about $1.2 and 4-5
minutes.

Still to run after a usage reset (it plays 6 Sonnet games, about $6-10 and 20 minutes):

```sh
ygo-agent train-compare --name geargia --games 2 --opponent windbot:Blue-Eyes --parallel 3
```
