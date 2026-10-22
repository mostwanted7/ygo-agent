# Training the agent on a deck

## What a trained deck is

A trained deck is a **guidebook**, not a model. Nothing is fine-tuned and there are no weights: the agent is the same
LLM for every deck, and what it knows about yours is a folder of text it reads while it plays:

- `playbook.md`: the strategy, read on every decision, so the player doesn't spend its time on the basics or make
  basic mistakes. Principles first ("consider X when Y, because Z"), a few checked rulings, and at the bottom the
  Known pitfalls: specific mistakes from reviewed games. 5-8 KB.
- `tips.md`: your own advice about the deck, in your words. The trainer writes the playbook from it and never
  contradicts it silently; nothing but you (and the commands that save your answers) writes it.
- `tests/*.json`: regression cases, past decisions with a known right answer. Every edit to the playbook is replayed
  against them, so a fix can't quietly break what already worked.
- `rules.py`, rarely: hard rules for a mistake the play model keeps making even with the playbook (see Hard rules).

Because it is all text, any backend can play a trained deck, you can read and edit every line of it, and a deck is
shared by copying its folder.

## The loop

1. **Give it the deck.**

   ```sh
   ygo-agent train ~/Games/ProjectIgnis/deck/Geargia.ydk --name geargia
   ```

   The deck folder goes to your decks dir (`~/.local/share/ygo-agent/decks/geargia/`; `--into repo` puts it in
   `decks/`). The trainer reads every card and the Lua script the engine runs for it (the dossier).

2. **It interviews you.** It asks three to six questions about this deck that only someone who plays it can answer:
   how it wins, the main lines and their key cards, going first or second, which Extra Deck monsters matter, what not
   to do, and "Anything else the agent should know about this deck?". Answer in a sentence or two; Enter skips a
   question, Ctrl+D ends the interview. The answers go to `<deck>/tips.md`.
   `--tips FILE` uses a text file you wrote instead of the questions, `--no-interview` skips them (a `tips.md` already
   in the folder is still used), and without a terminal the questions are only written to `train/interview.json`.

3. **It writes the guidebook** (the study): one reviewer session writes `playbook.md` from the dossier and your tips.
   Your tips win over its own reading of the cards, unless a card's script contradicts one: then it follows the
   script and lists the conflict as an open question for you in `train/train-report.md`.

4. **It practises.** It plays a few first turns with stacked hands against a dummy that does nothing (the lab), then
   a couple of games against WindBot deck AIs, reviews each one against the scripts and the engine log, and corrects
   the playbook. The defaults are light: 6 lab hands, 2 games, 1 round. `--lab-hands 10 --games 4 --max-rounds 3`
   is a deeper run; extra rounds stop early once a round's games show no major mistake.

5. **You play it**, and type a note when it does something obviously wrong: in the web panel's note box, or as a
   duel chat message starting with `!` in EDOPro (`!attack the halved Blue-Eyes, not Azure-Eyes`). Each note is
   saved in that game's `feedback.md`, right after the decision it follows.

   ```sh
   ygo-agent play --deck geargia --web
   ```

6. **It learns from your notes.**

   ```sh
   ygo-agent learn --deck geargia --list     # what is pending; no model call
   ygo-agent learn --deck geargia            # learn it
   ygo-agent learn --deck geargia --tip "Use Geargiagear at the end of the opponent's turn."
   ```

   For each game with notes, one reviewer session reads your notes, the decisions they follow, the playbook, your tips
   and the card scripts (the opponent's too). It checks each claim against the log and the scripts (you are usually
   right about strategy; rulings get checked), fixes the playbook, saves a regression case for the decision, and
   writes its verdict under your note in `feedback.md`: applied (and where), already covered, or why it disagrees.
   Tips you added since the playbook last took them in are folded in the same way. `learn` never plays a game.

Then repeat 5 and 6. Every step also exists in the web app: `ygo-agent web`, then Decks → New deck (pick the `.ydk`,
answer the questions, start training) or Learn on a deck's page.

The commands work on any deck folder, trained or hand-written: `ygo-agent learn --deck saffira` works too, and
builds the dossier first if the deck has none.

## What it costs, and how long

The costs are the Claude Code CLI's API-price figures; a Claude Code subscription isn't billed per call, so read them
as a measure of how much of your usage a step takes.

| step | measured | setup |
|---|---|---|
| interview questions (one call, no tools) | $0.08, 10 s | Sonnet, Rose Garden (2026-10-22) |
| study only (`--phases study`) | about $1.2, 4-5 min | Opus, Geargia |
| a whole training run, older and heavier settings | $14.3, about 50 min (Geargia, 2026-10-21) | 15 lab hands and 4 games with Sonnet playing, 2 rounds, Opus reviewing |
| `learn`, one game with two notes plus four tips | $0.08 and 20 s for the review, $0.56 and 2 min for the case check (8 cases, before and after) | Sonnet reviewing and replaying the cases once each (2026-10-22) |
| `train-compare`, 3 paired games | about $11, 15 min | Opus playing (2026-10-22) |

With the new defaults (Opus reviewing and playing, 6 lab hands, 2 games, 1 round), a training run should cost
roughly **$8-12 and 30-45 minutes**. That is an estimate from the measured steps above (Opus costs about 1.4x Sonnet
per game), not a measured run. With the defaults (Opus, cases replayed twice), a `learn` run should cost about $1-3
per game with notes, most of it the case check; `--gate-repeat 1` halves that, `--gate-repeat 0` turns it off.

## Reference

### What it produces

```
<name>/
  deck.ydk  deck.json         a copy of the deck file; the name, and go_first as the study decided
  playbook.md                 the playbook the agent reads on every decision
  tips.md                     your tips (the interview's answers, --tips, learn --tip, the web app)
  rules.py                    RULES = [] unless --write-rules wrote a rule that qualifies (see Hard rules)
  tests/*.json                regression cases from the reviews and from learn (ygo-agent test --deck <name>)
  train/
    train-report.md           the run: interview, rounds, win rates, the lab table, pitfalls, case checks, rules, cost
    state.json                the checkpoint: every finished step, the cost ledger, lines, case scores, questions;
                              "learn" holds learn's own state (the tips it took in, its runs)
    trainer.log               what the run did, with timestamps
    interview.json            the questions: {"deck", "created", "backend", "questions": [{"id", "question", "why"}]}
    dossier.md cards.json     the deck dossier; scripts/c<id>.lua (and scripts/lib/) are the scripts it used
    examples/                 the playbooks the study was shown (never the deck's own)
    study/                    playbook-draft.md, card-checks.md (each script citation, checked or not)
    round-N/                  lab/ (hands, logs, lab-results.md), games/, reviews/, the playbook at each step
    gates/                    each text replayed against the saved cases, and those replays
    calls/                    every reviewer call: the prompt, the reply, the transcript and the files it read
    general-proposals.md      lessons the reviewer thinks hold for every deck (never applied automatically)
    rule-proposals.md         proposed hard rules, and whether each qualifies
    tests-final.txt           the regression cases re-run against the final playbook
    learn.md                  one line per learn run
    learn/<time>/             a learn run: report.md, learn.log, calls/, gates/, the playbook after each call
```

### How training works

1. **Study.** The dossier lists the deck with counts, every card's text and type line, its archetypes, the Main
   Deck's Levels next to the Extra Deck's Ranks/Levels, each Extra Deck monster's summoning condition, and hints read
   off each Lua script (once-per-turn limits, costs, "if"/"when" triggers, procedures, restrictions). The interview's
   questions are written from it. The study writes the draft playbook in the house style (`decks/geargia/playbook.md`
   is the reference), the deck's standard plays in structured form for the lab, and the rulings it checked, each with
   a verbatim quote of the script line, which is checked against the file (`study/card-checks.md`).
2. **Lab.** The player plays turn 1 with stacked hands: the key cards of each standard play plus random fill, random
   hands, and a couple of going-second turns into a fixed board (Blue-Eyes White Dragon, a face-down monster, two Set
   traps). The opponent ends every phase and passes every chain, and the end board comes straight from the engine.
   The reviewer marks each play verified / partial / failed / not tested and corrects the sections that need it.
3. **Games.** Games against the opponent pool, alternating who goes first. A WindBot deck AI is accepted only if
   its `bots.json` entry allows the rules and its deck has no Link monsters. Each game is reviewed the way CLAUDE.md's
   "Decks without a coach" says: turn by turn, judging each play on the board (a deviation that was as good is not a
   mistake), looking for fallbacks, engine rejections, unused resources, Extra Deck locks, missed lethal and chain
   timing. A missing principle becomes a section rewrite; only a significant, repeatable mistake becomes a Known
   pitfall.
4. **Converge.** Rounds repeat until a round's reviews find no major mistake, or `--max-rounds` or the budget runs
   out. The saved cases are re-run against the final playbook, and `train-report.md` is written.

The player defaults to the **play model** (`agent.backend`, Opus), so the lessons, the case check and the rules
policy are calibrated to the model that will play the deck; `--player-backend sonnet` is cheaper, but its mistakes
are not necessarily Opus's. The reviewer is `--backend` (default `trainer.backend`, Opus).

### How learn works

- **Whose notes count.** Yours: notes typed in the web panel (it only serves this machine), and notes from the human
  who played the agent (`play`). A spectator's note, or an AI opponent's chat line in self-play, can come from anyone
  in the room: `--list` shows them marked, and only `--include-spectators` uses them (the reviewer is told they
  aren't yours).
- **One call per game.** The reviewer gets the notes, every decision a note follows with all its options, the game
  log, the playbook, your tips and the scripts of the cards in the game, the opponent's included. Its reply goes
  through the same checks as a training review (below). New tips ride along with the first call, or get a call of
  their own when there are no notes.
- **The note is marked.** Under each note it writes `  - Learned <date>: <verdict>: <what changed or why not>
  [edited: <the sections that really changed>]; case <name>`. A marked note is never used again; a note the reviewer
  gave no verdict for stays pending. An edit the case check rejected is marked "not applied" with the reason.
- **Options.** `--game DIR` (only that game; repeatable), `--backend` (the reviewer), `--player-backend` (replays
  the cases; default the play model), `--gate-repeat N`, `--budget-usd` (per run), `--inline`, `--games-dir`.
  `--list --json` prints `{"deck", "name", "dir", "games_dir", "notes": [every pending note, with "trusted" and
  "used"], "to_learn", "tips": {"path", "count", "changed", "new"}, "pending"}`. Exit codes: 0 done or nothing to
  learn, 2 stopped (budget, usage limit, error, Ctrl+C: the notes learned so far stay marked), 1 a bad argument.

### What keeps it honest

- **No lesson without evidence.** Every Known pitfall must quote a script line or the game log (with the decision
  number); the quote is checked against the file, give or take punctuation. Pitfalls that fail, or repeat one already
  in the playbook, are dropped and listed in the report.
- **No rewrite that loses behaviour.** Every section rewrite, condense and learn edit is replayed against the saved
  cases with the player's backend (`--gate-repeat` runs each, default 2; 0 turns it off). If the cases pass less
  often than with the previous text, the reviewer gets one retry with the failing cases; if that doesn't hold either,
  the previous text stays.
- **Regression cases are checked too:** the decision must exist in the log, the choices must be legal for it, and
  the case must not "expect" what the player actually did.
- **Your words stay yours.** Section edits, condenses and fix-ups never touch Known pitfalls (the trainer writes those
  itself, dated and naming the game) or a section you wrote (Saffira's "Coaching lessons"); a hand-written playbook
  keeps its own layout when it is condensed. A tip is never contradicted silently: a conflict with a script becomes
  an open question.
- **The reviewer can't write anything.** With the claude-code backend it runs `claude -p` with only Read, Grep and
  Glob, `--permission-mode dontAsk --restricted`, no settings, MCP servers or slash commands, in a sandbox folder
  (`~/.cache/ygo-agent/trainer/<name>/`) holding copies of what the task needs. It returns JSON; the trainer applies
  it. With `--inline`, or the anthropic/openai backends, the prompt carries the excerpts instead.

### Hard rules

A hard rule (`rules.py`) overrides the model, so it is only for a mistake with no judgment in it that the **play
model** makes even though the playbook already covered it, and a saved regression case must prove it. Each review
records whether a mistake needed judgment and quotes the playbook line that already covered it; proposals are
assessed against those conditions (`trainer/rulepolicy.py`), all of them go to `train/rule-proposals.md`, and the ones
that qualify are written into `rules.py` (with `@cases`) only with `--write-rules`. With another player than the play
model, nothing qualifies by itself: check the case with `ygo-agent test --deck <name> <case> --backend opus` first.
`ygo-agent test --deck <name> --ablate-rules` reports the rules a new play model no longer needs.

### Budget, checkpoints, usage limits

- Every training step (the interview, the study, each lab hand, each game, each review) is checkpointed in
  `train/state.json`; `--resume` skips what is done and never asks the questions again. Options given with
  `--resume` win over the run's own. Ctrl+C, a budget stop or a crash lose at most the step in progress.
- `--interview-only` stops after writing `train/interview.json`; answer in `tips.md`, then
  `ygo-agent train --name <name> --resume --no-interview` (the web app does exactly this).
- `--budget-usd N`: before each paid step the trainer compares what is spent plus an estimate with the budget and
  stops cleanly, still writing the report. For `learn` the budget is per run.
- A usage or rate-limit error stops with `stopped: usage limit`; `--resume` (or `learn` again) after the reset
  finishes it.

### Reviewing the output

1. Read `train/train-report.md`: the interview, the win rate per round, which plays the lab verified, the pitfalls
   and the rejected ones, the case checks, the rule proposals and the open questions (tip conflicts among them).
2. Read `playbook.md` against the scripts (`train/scripts/`); lines still marked *(unverified)* haven't been seen
   working in the engine. Edit it freely: it is yours.
3. `ygo-agent test --deck <name>` re-runs the saved cases; delete the ones you disagree with.
4. `ygo-agent train-compare --name <name>` plays the same games (opponent, seeds, who goes first) with the trained
   playbook, the study draft and none, to see what the training bought.
