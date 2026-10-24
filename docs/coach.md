# Coach mode

You play a deck in the real EDOPro client; the agent watches your seat, recommends a move for every decision with a
short, teachable reason, and writes a review of the game afterwards. It replaces the old terminal copilot.

```sh
ygo-agent coach --web                                   # deck recognised from what you submit, vs windbot:Blue-Eyes
ygo-agent coach --deck blackwing --level intermediate --opponent saffira:sonnet --web   # coach: opus (agent.backend)
ygo-agent coach --review games/<dir> [--review-backend opus]   # review a finished coach game again
```

Then in EDOPro: **LAN Mode**, Host address `127.0.0.1`, port `7911` (`--port`), **Join**, pick your deck, ready up.

- **The deck.** `--deck` names it (a folder in `decks/`, a `.ydk`, an EDOPro deck name). Without it, the deck you
  submit is matched against every deck profile (`decks/*/deck.ydk`, with `config.local.toml` overrides): the best
  overlap of at least 60% of the cards wins, and the terminal says which. An unknown deck is still coached, from
  `playbooks/general.md` and the card texts only (its list is saved to `games/coach-decks/<name>.ydk`); training it
  first (`ygo-agent train`) gives much better advice.
- **The opponent.** `--opponent` takes any seat spec: `windbot:<deck AI>` (the default, from `[coach] opponent`),
  `<deck>:<backend>` or `heuristic`. An AI opponent plays as in self-play; its reasoning stays out of the terminal and
  the panel (it knows its own hand), it doesn't take your `!notes`, and it still logs its own game folder.
- **Level.** `--level beginner` (the default) explains the idea behind each move in 2-3 sentences; `intermediate` is
  one terse sentence.
- **Time.** Your time limit still applies: `[coach] time_limit` (1200 s per turn) or `--time-limit` (0 = none).
  Reading the advice takes time, so keep it long.
- `--web` is recommended: the panel shows your hand and board, the coach's pick marked on the options, its reason
  and plan, whether you followed it, and after the game the review in its own tab.

## Live advice

The arena hosts the room, so it sees your seat exactly as your client does. A `SeatWatcher`
(`arena/native_seat.py`) builds the decision JSON an AI seat would get for it, your own view and nothing else, and
decodes each of your responses back into option indices. `coach/live.py` hooks into `run_games(on_room=...)`.

Nothing ever waits for the coach: the arena's callbacks only queue work. A brain thread keeps the game log, the duel
history and the panel current as the game goes, and asks the backend on an ask thread, one request at a time
(a `CoachBrain`, `coach/brain.py`: a DuelBrain in `coach` mode with one backend session per turn, opened while you
read the board). For each decision:

1. The `decision` is logged and published at once.
2. **Trivial decisions get no backend call** and show as `auto`: zone placement, a single option, a mandatory
   activation, "pick all of these", the next card of a selection the coach already advised, and anything the deck's
   `rules.py` answers (that one does show its pick, as `rule · <name>`).
3. Otherwise the coach is asked, always about the decision you are looking at now. Its `advice` (`choice`, `why`,
   `plan`) is published with `late: true` if you had already answered. An invalid reply gets one corrective re-ask,
   unless you have moved on.
4. Your move is logged as a reply with `source: "human"`, and `human_choice` says whether it `matched` the advice
   (whichever of the two comes second publishes it). It also goes into the coach's duel history ("The human chose
   ... (you had advised ...)"), so the next advice starts from what you actually played.
5. **When you're faster than the coach**, the decisions it never got to are dropped (no cost), except Main Phase,
   Battle Phase and chain decisions: once it has caught up, it gets a short "looking back" ask about them (your
   choice and the state at the time; one-sentence answer), for the review. At most the 4 most recent wait for that
   during the game, and 6 after it.

In the terminal, each advised decision is one block: the question, the coach's pick with its reason (and plan), then
`✓ you followed the coach` or `✗ you chose ...`, with the time you took. `--quiet` drops the event lines. At the end
of the game a summary line: how often you followed the coach, how long the advice took after each decision (mean and
p95), how many came late, and the cost.

## Notes

A `!note` typed in the duel chat, or the panel's note box, goes to the coached game's `feedback.md` as usual, tagged
`coach game`: `- (coach game, turn T, right after decision #N) text`. Chat notes are saved silently.

## The review

When the game ends (and the last looks back are in), `coach/review.py` asks the review backend (the coach's, or
`--review-backend` / `[coach] review_backend`) for one pass over:

- the duel log from your side, with every decision you made, the coach's advice and whether you followed it;
- every decision where you did something else (up to 18, the key ones first), each with its full state and options;
- the texts of the opponent's cards seen, your notes, the deck's playbook, `playbooks/general.md` and the card texts.

`review.md` in the game folder has a header (result, turns, how often you followed the coach) and the review:
**Summary**, the 3-6 **Key moments** (turn, decision number, what you did, what was better and why, the playbook rule
involved or the one worth adding), **What you did well**, and 2-3 things to **Practise next**. It is printed in the
terminal and pushed to the panel as a `review` message (its Review tab). `review-prompt.md` keeps what the reviewer
was shown, for checking its claims. With a non-LLM backend (heuristic, random) review.md just lists the divergences.
A duel the room aborts (Ctrl+C mid-game, a crash) gets no review; `--no-review` skips them all, and
`ygo-agent coach --review games/<dir>` writes one later.

## Files

The coached game's folder is the usual `games/<time>_<deck>-vs-<opponent>/`:

- `game.md`: each decision with your move ✅ (tag `human`, with your thinking time and the verdict) and the coach's
  advice as a `🎓 Coach` line; advice that came late is added where it arrived, naming its decision.
- `game.jsonl`: the decisions, `advice` rows (`id`, `choice`, `why`, `plan`, `source` = backend / `rule:<name>` /
  auto / skipped / failed, `seconds` of backend time, `after` = seconds from the decision to the advice, `late`,
  `hindsight`, `kind`) and your replies (`source: "human"`, `advised`, `matched`, `seconds`, `trivial`).
- `meta.json`: `mode: "coach"`, and `coach` with the level, the backend, the deck detection and the counts (advised,
  auto, skipped, looked back at, late, followed/diverged, advice latency mean and p95, your mean time).
- `replay.yrpX`, `feedback.md`, `review.md`, `review-prompt.md`.

`ygo-agent replay games/<dir> N` re-asks decision N with the current playbook, as for any game, and `ygo-agent web`
replays the game with its advice and review.

## Config

```toml
[coach]
opponent = "windbot:Blue-Eyes"
level = "beginner"
time_limit = 1200
review_backend = ""
review_timeout_seconds = 600
```

## Tests

`tests/coach/`: deck detection; the flow on a real logged game fed to a `CoachGame` with a scripted coach and a
scripted human who waits for the advice, answers while the coach thinks, or answers at once (late, looked back at,
skipped, auto, matched, the game log, notes, the review, a recorded replay of it); and two arena games
(integration) with the arena's Python client as the human (`tests/coach/human.py`, also runnable by hand), a
heuristic opponent and a scripted coach: a thoughtful human never gets late advice, an instant one always does.

## Known gaps

- Played from the real EDOPro GUI only a few times so far (two coached games on 2026-10-22, Geargia and Blackwing
  against Blue-Eyes); the arena's view of a human seat is the same one an EDOPro client gets, and the protocol is
  tested with the Python client.
- An unselect (taking a card back in a multi-pick) has no option index, so the coach can't compare it.
- The coach advises on the state it is given; its advice can be wrong, and the review is told it may be.
