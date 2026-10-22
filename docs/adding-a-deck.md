# Adding a deck

A deck the agent can play is a folder with the deck list, a playbook it reads on every decision, optional hard
rules, and saved regression cases. There are two ways to make one: let the trainer write it from a `.ydk`, or write
it by hand.

## With the trainer

```sh
ygo-agent train ~/Games/ProjectIgnis/deck/Chaos.ydk --name chaos   # reads the cards, asks you a few questions
ygo-agent play --deck chaos --web                                   # note its mistakes in the panel (or "!..." in chat)
ygo-agent learn --deck chaos                                        # folds your notes into the playbook
```

The trainer reads every card and its script, asks you a few questions about how the deck plays (your answers go to
the deck's `tips.md`), writes the playbook from both, tests it in a short lab and a couple of reviewed games, and
leaves the deck folder in your decks dir (`~/.local/share/ygo-agent/decks/chaos/`; `--into repo` puts it in
`decks/` instead) with a `train/` folder and `train-report.md` explaining every lesson. After that the deck improves
from your notes: `ygo-agent learn` reads the notes you typed while it played, checks them against the log and the
card scripts, fixes the playbook and saves a regression case for each decision. It works on hand-written decks too.
Edit the playbook as you like. [training.md](training.md) has the loop, the options and the costs; every step is also
in the web app (`ygo-agent web`).

## By hand

### The folder

Decks are looked up by folder name in `decks/` (the decks that ship with the repo) and then in your decks dir
(`[decks] user_dir`, default `~/.local/share/ygo-agent/decks/`); `ygo-agent decks` lists both. A name in both places
is an error unless `[decks] prefer = "user"` (or `"repo"`) says which wins.

```
decks/chaos/
  deck.ydk        the deck list (EDOPro's format)
  deck.json       {"name": "Chaos", "ydk": "deck.ydk", "go_first": true}
  playbook.md     what the model reads on every decision
  tips.md         your advice about the deck, in your words (optional; train and learn write the playbook from it)
  rules.py        hard rules (optional; RULES = [] to start)
  tests/          regression cases, *.json (created by ygo-agent replay --save)
```

`deck.json` keys: `name`, the deck's name in prompts and logs; `ydk`, the list, relative to the folder (default
`deck.ydk`); `go_first`, whether the agent chooses to go first when it wins the rock-paper-scissors (default true).

To play the copy of the list EDOPro's deck editor saves, so your edits carry over, point the deck at it in
`config.local.toml` (per machine, never in `deck.json`):

```toml
[decks.chaos]
ydk = "~/Games/ProjectIgnis/deck/Chaos.ydk"
```

A deck without a folder works too: `ygo-agent play --deck ~/Games/ProjectIgnis/deck/Chaos.ydk` (or just the name of
a deck in EDOPro's deck folder) plays it with `Chaos.md` next to the file as its playbook, if there is one, and
`playbooks/general.md` alone otherwise. Hard rules (`rules.py`) are only read from deck folders, never from next
to a loose `.ydk`, so playing a downloaded deck file never runs code that came with it.

### The playbook

The playbook is the deck's strategy as the model should hold it, read whole on every decision, so keep it under
about 8 KB. `decks/geargia/playbook.md` is the reference; its shape, in order:

1. **How to use this playbook**: principles, not scripts; deviate when the board calls for it and say why.
2. **Game plan**: what the deck is, how it wins, what a good first turn leaves, how it grinds and closes.
3. **Card roles**: short, by role, with only the rulings that decide plays (check them in the card scripts,
   `~/Games/ProjectIgnis/script/official/c<id>.lua`).
4. **Situational considerations**: the judgment calls as conditions with their reason ("consider X when Y, because
   Z"), which the model may override.
5. **Lethal check** (decks with boosts, burn or OTKs) and **Going second / breaking boards**.
6. **Known pitfalls**, always last: the specific, repeatable mistakes from reviewed games, one or two lines each,
   dated and naming the game.

Principles first, because games vary too much for step-by-step scripts. A lesson that holds for every deck goes in
`playbooks/general.md`, not the deck's playbook. `ygo-agent learn --deck chaos` turns the notes you typed during
games into playbook fixes on its own; `CLAUDE.md` describes the same loop done by hand: find the decision in
`game.md`, decide whether the cause was judgment (the playbook), the way the state was presented
(`ygo_agent/agent/describe.py`) or wrong card data (the script), and fix the section that was missing or wrong,
generalised beyond that game.

### Hard rules

`rules.py` lists plain functions in `RULES`. Each gets a `Context` and returns `None` (no opinion) or
`Decide(choice, why)`; rules run in order before the model is asked, after the built-in ones (go first, zone
placement, single-option prompts). The helpers in `ygo_agent/agent/rules.py`:

| helper | meaning |
|---|---|
| `ctx.kind`, `ctx.d`, `ctx.state` | the decision kind, the raw decision and its `state` (docs/decision-protocol.md) |
| `ctx.options`, `ctx.option_card(i)`, `ctx.option_name(i)`, `ctx.option_action(i)` | the options, and one option's card, card name or action (`activate`, `summon`, ...) |
| `ctx.find(name=, action=)` | indices of the options whose card name and/or action match |
| `ctx.names(side, zone)` | card names in `"me"`/`"opp"`'s `hand`, `mz`, `sz`, `gy`, `ban` or `extra` |
| `ctx.my_turn`, `ctx.turn`, `ctx.phase` | whose turn, the turn number, the phase bits |
| `ctx.chain_names()`, `ctx.last_chain_by_opponent()` | the current chain's card names; whether its newest link is the opponent's |
| `ctx.db`, `ctx.profile` | the card database (`db.name(code)`) and the deck profile |

```python
from ygo_agent.agent.rules import Decide, cases, shortcut

DRAW, STANDBY = 0x1, 0x2

@shortcut
def pass_empty_draw_standby_windows(ctx):
    """Nothing in this deck acts in an empty Draw/Standby Phase window: don't spend a model call on it."""
    if ctx.kind == "chain" and not ctx.d.get("forced") and not ctx.state.get("chain") and ctx.phase in (DRAW, STANDBY):
        return Decide([], "nothing worth doing in an empty Draw/Standby Phase window")
    return None

@cases("search-fodder-when-boss-in-hand")
def search_fodder_when_boss_in_hand(ctx):
    ...

RULES = [pass_empty_draw_standby_windows, search_fodder_when_boss_in_hand]
```

A rule overrides the model for every backend, so write one only for a mistake with no judgment in it that the
**play model** (`agent.backend`, Opus) repeats even with a playbook lesson, and save the case that proves it:
`@cases("<case>")` names the regression cases (below) that show the model needs the rule. `@shortcut` marks a rule
that only skips prompts that never matter (it saves model calls, not mistakes). If a weaker model made the mistake,
check the case with `ygo-agent test --deck chaos <case> --backend opus` before writing a rule. When the play model
changes, `ygo-agent test --deck chaos --ablate-rules` replays each rule's cases with that rule disabled and reports
the rules the model no longer needs. A rule that raises is skipped with a message, never stops the game.

### Regression cases

After a game, re-ask a decision with the current playbook and rules, and keep it as a case once it is fixed:

```sh
ygo-agent replay games/<game> 14                                   # re-ask decision #14 (the deck comes from the log)
ygo-agent replay games/<game> 14 --save set-trap-before-ending \
    --expect '[[3]]' --note "Set the trap in Main Phase 2 instead of ending from the Battle Phase"
ygo-agent test --deck chaos                                        # every case of the deck, 3 runs each
ygo-agent test --deck chaos set-trap-before-ending --repeat 5 --backend sonnet
```

`--expect` lists every acceptable choice (`'[[]]'` means pass; the order of a multi-card pick doesn't matter);
`--reject` lists only the choices that count as the old mistake, for a board that allows several good lines. The
case file keeps the decision's messages, the expectations, the note and where it came from. The model isn't
deterministic, so a case that passes only sometimes needs a stronger playbook line (or, by the rule above, a rule).
`.venv/bin/python -m pytest` checks every saved case without a model call: the decision still describes, the
expected and rejected choices are legal, and no rule contradicts the case.

## Sharing a deck

Copy the folder into `decks/` (or train it with `--into repo`), make sure `ygo-agent test --deck <name>` and `pytest`
pass, and open a pull request. Keep the trainer's `train/` folder out of it except `train-report.md` (the repo's
`.gitignore` already does), and the playbook within its size budget.
