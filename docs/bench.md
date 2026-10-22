# Benchmarks

`ygo-agent bench` plays headless games to compare backends: the same decks, the same opponents and the same seeds
for every backend. It reports win rates with confidence intervals, a rating, game length, decision latency,
tokens, cost, and how often the model's replies were unusable.

```sh
ygo-agent bench smoke                       # no LLM, about a minute: checks the whole pipeline (games/bench-smoke/)
ygo-agent bench readme                      # the README benchmark (bench/configs/readme.toml)
ygo-agent bench readme --resume             # continue its newest run; finished games are skipped
ygo-agent bench --decks saffira --backends sonnet,haiku,heuristic --opponents windbot:Blue-Eyes --games 6
ygo-agent bench report bench/results/<run>  # rebuild report.md, summary.json and chart.svg
ygo-agent bench report bench/results/<run> --publish docs/bench   # also copy the leaderboard and chart for the README
```

## Defining a benchmark

A plan is a TOML file in `bench/configs/` (pass its name or a path), or flags. Flags override the file.

| key / flag | default | meaning |
|---|---|---|
| `name` / `--name` | the file name | run folders are `bench/results/<time>_<name>/` |
| `decks` / `--decks saffira,blackwing` | | the AI-piloted decks (folders in `decks/`, `.ydk` paths, EDOPro deck names) |
| `backends` / `--backends opus,sonnet,heuristic` | | backend profiles (`[backends.NAME]` in the config); `heuristic` and `random` are the no-LLM baselines |
| `opponents` / `--opponents windbot:Blue-Eyes,…` | | WindBot deck AIs, or AI seats such as `blackwing:sonnet` or `heuristic:blackwing` (AI vs AI) |
| `games` / `--games N` | 6 | games per (deck, backend, opponent) |
| `[games_for]` / `--games-for heuristic=30,opus=2` | | per-backend game counts |
| `seed` / `--seed` | 1000 | the first seed of the shared seed list |
| `rules` / `--rules` | MR3 | the duel rules; decks (yours and the WindBots') must be legal under them |
| `parallel` / `--parallel K` | 3 | games at a time |
| `budget_usd` / `--budget-usd` | none | start no more games once the finished ones cost this much |
| `timeout` / `--timeout` | 5400 | seconds before a WindBot game is given up |
| `note` | | a line shown at the top of the report |
| `scratch` / `--scratch` | false | a test run: its folder goes under `games/bench-smoke/` (git-ignored) instead of `bench/results/`, so only deliberate runs land in the repo. `smoke` sets it |

`--dry-run` prints the plan, `--out DIR` picks the run folder (over `bench/results/` and `scratch`), and `--no-probe`
skips the check below.

**Same deals for everyone.** Game *i* (0-based) of every pairing uses seed `seed + i`, and the AI seat goes first
in game 1, 3, 5, … and second in game 2, 4, 6, …. The seed fixes the shuffle of both decks, so every backend gets
the same opening hands and deck order in game *i* (the tests check this), and a backend with fewer games plays a
prefix of the same list. Games run in order of *i* across all pairings, so a run cut short leaves the backends
comparable. Random baseline seats also take the game's seed, so they are reproducible.

**Before the games**, each LLM backend gets one tiny real call. It fails fast when a server is down or the
account is out of usage, and it records the model id the CLI actually used (e.g. `claude-sonnet-5-5`).

**Resume and extend.** Each game's result is appended to `results.jsonl` as soon as it ends (with fsync), so a
crash, Ctrl+C or a usage limit loses only the games in flight. `--resume` (the newest run of the plan, or
`--resume DIR`) plays only the games without a finished line. Raise `games` or add a backend in the plan and resume
to extend a run on the same seeds; the seed and rules of a run can't change.

**Usage limits.** When a game's backend replies with a usage or rate-limit error, that game is marked `aborted`
(the heuristic fallback played part of it, so it isn't that backend's game), no new games of that backend type
start, and the baselines carry on. Resume once the usage resets. Four failed games in a row (a broken WindBot, a
bad deck) stop the run.

## What a run writes

`bench/results/<time>_<name>/` (a `scratch` run such as `smoke`: `games/bench-smoke/<time>_<name>/`; `--out DIR`
anywhere):

- `results.jsonl`: one line per game attempt. `status` is `done`, `aborted` (out of usage) or `error`; the last
  `done` line of a game counts. A line has the deck, backend, opponent, game number, seed, who went first, the
  result, reason, turns, seconds, engine retries, the replay path, the core's duel seed, and for each seat its
  stats (the `meta.json` fields in [backends.md](backends.md#stats)), its per-decision latencies, timeouts, and
  the log folder.
- `replays/`: every game's EDOPro replay (`.yrpX`; open it in EDOPro's replay menu). The report links each one.
- `summary.json`: every number in the report.
- `report.md`: the leaderboard, wins by matchup, the per-matchup table, the opponents, notes (versions, decks,
  backends, model ids, rules, seeds) and the list of games.
- `chart.svg`: win rate with 95% CI per backend, and cost per game against win rate (plain SVG, light and dark).
- `spec.json` (the plan and every invocation) and `env.json` (versions: core, script and card-data dates, deck
  and playbook hashes, WindBot build, backend settings, claude CLI version).

The game logs (`game.md`, `prompts.jsonl`, …) go to `games/bench/<run folder>/<game>/`, outside git: a Sonnet game
log is about 1 MB.

## Reading the numbers

- **Win rate**: wins / games, with a [Wilson](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval)
  95% interval. Draws count as not won. With 6 games the interval is about ±30 points, so read small runs as a
  pilot: two backends whose intervals overlap widely aren't separated yet.
- **Going first / second**: the AI seat's wins when it went first and second. Yu-Gi-Oh! decks often care a lot.
- **Rating**: Bradley-Terry on the Elo scale (400 points = 10:1 odds), fitted over every game with backends and
  opponents as players, each with one virtual win and one virtual loss against a 1500-rated anchor. Unlike the
  pooled win rate it accounts for who each backend played, and it stays finite at 0% or 100%.
- **Turns**: both players' turns. **Time per game**: wall-clock seconds of the duel.
- **Decision latency**: the backend's seconds per decision it was asked, re-asks included, pooled over every
  decision (mean, median, 95th percentile). Decisions the rules or the agent answered themselves aren't counted.
- **Tokens per game**: input (uncached), output, and cache reads, from the backend's usage reports.
- **Cost per game**: the backend's own figure. For claude-code it is what the tokens would cost at API prices; a
  subscription login isn't billed per call. Baselines are free; `–` means unknown.
- **Invalid replies**: model outputs that couldn't be read or named an illegal option, over all outputs. The
  agent re-asks once with the reason, so an invalid reply usually costs time, not a bad move.
- **Fallbacks**: decisions the heuristic answered because the backend didn't (timeout, error, two invalid replies).
  A high rate means you're partly measuring the heuristic.
- **Rule-answered**: decisions a deck's hard rules (`decks/<deck>/rules.py`) made. They apply to every backend,
  baselines included, so the baselines measure "heuristic + the deck's rules".
- **Errors (timeouts)**: asks that got no output at all, and how many of them timed out.

## Benchmarking an open model

Any OpenAI-compatible server works (Ollama, vLLM, llama.cpp, LM Studio, OpenRouter; see
[backends.md](backends.md#openai-openai-compatible-servers)). Add a profile to `config.local.toml`:

```toml
[backends.qwen]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
num_ctx = 32768
card_texts = "compact"     # a smaller prompt for small contexts
price = { input = 0, output = 0 }   # local = free; for a hosted model, its USD per million tokens
```

Then benchmark it next to a reference, on the same seeds:

```sh
ygo-agent bench --name qwen --decks saffira,blackwing --backends qwen,haiku,heuristic \
    --opponents windbot:Blue-Eyes,windbot:Time\ Thief --games 6 --parallel 1
```

`--parallel 1` suits one local GPU (parallel games compete for it and inflate latency). To compare against an
existing run, use the same `seed`, decks and opponents: the per-game seeds then match the old run's games, and you
can resume the old run with `--backends qwen` added to put both in one report. Watch the invalid-reply and fallback
rates first: a model that can't follow the reply format ends up playing the heuristic's game.

## Choosing opponents

Under Master Rule 3, a deck with Link monsters is illegal, and the benchmark refuses it up front. These WindBot
deck AIs are MR3-legal and in `bots.json`, with the heuristic baseline's results against them (20 games each,
Saffira and Blackwing, 2026-10-21):

| WindBot deck AI | difficulty | heuristic wins | avg turns |
|---|---:|---:|---:|
| Branded | 3 | 0% | 5.7 |
| Blue-Eyes | 2 | 5% | 5.8 |
| Zoodiac | 3 | 5% | 6.3 |
| Toadally Awesome | 2 | 5% | 7.3 |
| ZEXAL Weapon | 2 | 5% | 7.8 |
| R5NK | 2 | 10% | 10.0 |
| Rainbow | 2 | 10% | 10.9 |
| Qliphort | 0 | 10% | 9.4 |
| Time Thief | 2 | 25% | 9.8 |
| Mathmech | 2 | 30% | 10.9 |
| Yosenju | 0 | 30% | 8.2 |
| Frog | 1 | 45% | 12.2 |
| Dragunity | 2 | 70% | 9.7 |

Burn, Horus and Normal Monster Mash are legal too (not scanned). Lightsworn Shaddoll Dino, Dark Magician, Blue-Eyes
Ritual and most newer decks run Link monsters. The README benchmark uses Blue-Eyes (strong,
fast) and Time Thief (mid-strength, longer games).

## Decision exam: comparing models without the luck of the draw

A handful of games per model mostly measures the opening hands. `ygo-agent bench exam` compares models on the same
decisions instead: real decision points from logged games, each re-asked of every candidate, then graded by a blind
judge (Opus by default) that can read the card scripts.

```sh
ygo-agent bench exam --select                     # sample 40 positions into bench/exams/main.json (no LLM, seconds)
ygo-agent bench exam --dry-run                    # list them, with a cost and time estimate
ygo-agent bench exam                              # opus, sonnet and haiku answer; opus judges; report.md
ygo-agent bench exam --judge opus,sonnet --games 4   # plus a second judge and a review of 4 whole games per model
ygo-agent bench exam --resume                     # continue the newest run of `main`
ygo-agent bench exam report bench/exams/results/<run>
```

**The positions.** `--select` scans every LLM-played game log under the games folder (`--sources`) for Saffira and
Blackwing (`--decks`) and keeps the decisions the model itself made, with a real choice: not the automatic answers,
not the ones a deck rule answers (today's rules), not the decision after an engine retry, and not a lone option. The
sample is stratified: the decks share the positions equally, and each deck's share goes 30% Main Phase, 20% chain
windows, 20% card selections (searches, targets, costs, materials), 12.5% Battle Phase (attacks and attack targets),
10% optional triggers and 7.5% the rest. Within a stratum the picks rotate over the models whose games they come from
and favour decisions where the answer matters: replies to an opponent's activation, summon or attack, searches and
targets, a Main Phase with many plays, and above all decisions where the heuristic policy disagrees with what the
model did. At most 3 positions come from one game, 3 decisions apart. The selection (game folder, decision number,
a hash of the decision) is saved in `bench/exams/<name>.json` and reproduces from `--seed`; `--resample` replaces it.

**The answers.** Each position is re-asked exactly as `ygo-agent replay` does: a fresh brain replays the game's
events up to the decision (with the current playbook, rules and describe.py), and a fresh session of the candidate
answers it. Every candidate sees the same prompt (checked per answer). A position that a rule answers now is
excluded. `--parallel` asks run at a time, and every answer (choice, why, plan, seconds, tokens, cost) is appended
to `answers.jsonl` as it lands, so `--resume` asks only what is missing or failed. When a candidate hits a usage
limit it stops and the others carry on.

**The judge.** For each position the judge gets what the player saw (the same message text), the deck's decklist,
`playbooks/general.md` and the playbook, the texts of the deck's cards in the position, and the distinct answers
labelled A, B, C… in a per-position random order, each as option text plus the player's reason (model names
scrubbed). It grades each answer `best | good | acceptable | mistake | blunder` with a reason, and says what it would
play itself and which answers are as good. Answers that make the same move (another copy of the same card, the same
cards in a different order) share one label, so identical choices always get the same grade. The judge is the
trainer's reviewer (`trainer/llm.py`): agentic `claude -p` with only Read/Grep/Glob in a sandbox of the card scripts,
so it can check rulings (`--inline-judge` turns the tools off). It grades `--judge-batch` positions per call (3, one
deck per call). Its prompts and tool transcripts are kept in the run's `judge/` folder.

**Checking the judge.** The report flags self-preference: the judge's own model graded best far more often than the
others when its answer differs from every other candidate's. In a share of the positions (`--probe`, 15%) where two
candidates made the same move with different reasons, the judge sees that move twice under two labels. How often the
two copies get the same grade measures its noise; the duplicate's grade is never scored. Replies that contradict
themselves (its own pick not graded best) are counted. A second judge (`--judge opus,sonnet`) grades the same
answers independently, and the report shows how often the two agree.

**Whole games (`--games K`).** A lighter version of the trainer's game review: the judge reads K logged games per
model from the benchmark run (`--games-from`, default the newest) and lists the verified mistakes (`blunder`,
`major`, `minor`). The model's name, its timing and its seat name are removed from the log first. It takes deals
that every model played (the same deck, opponent and seed), so the games are like-for-like.

**The report** (`bench/exams/results/<time>_<name>/report.md`, numbers in `summary.json`) has:
- the recommendation, and how sure it is;
- per model: the mean grade (best 4 … blunder 0, bootstrap 95% CI), the best and best-or-good rates, the mistake
  and blunder rates (Wilson CIs), agreement with the judge's own pick, and latency, cost and tokens per decision;
- paired per-position comparisons with a sign test;
- the results by decision kind and by deck;
- the judge checks;
- the five most instructive disagreements, quoted;
- the whole-game reviews, and every position's grades.

The recommendation is the cheapest model the exam can't tell apart from the best one: a paired difference whose 95%
interval reaches within a quarter grade of zero, and a mistake rate within 10 points. Its confidence is low under 20
graded positions or with a self-preference flag, and high when it is separated from every other candidate over 30
or more positions.

Every exam decision is a turn's first message (the whole duel log) in a fresh session. So its cost and latency per
decision are higher than in a game, where most decisions continue a session and pre-warming hides the start-up.

### Choosing the play model

On 2026-10-22 the exam picked the one Claude model the agent plays with
([report](../bench/exams/results/2026-10-22_014130_main/report.md)). 40 positions were sampled from 1982 usable
decisions in 35 logged games (19 Saffira, 21 Blackwing; from Haiku, Sonnet and Opus games). Opus, Sonnet and Haiku
each answered every position, and a blind Opus judge graded the answers. A second judge (Sonnet) re-graded them, and
4 like-for-like whole games per model from the README benchmark were reviewed blind.

| model | mean grade (95% CI) | best | mistake or blunder | blunder | latency mean · p95 | cost / decision | wins | significant mistakes / game |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Opus** | **3.73** (3.48–3.95) | 88% | 5% | 0% | 9.9 s · 17.8 s | $0.071 | 4 of 4 | **0.25** (0 blunders) |
| Sonnet | 3.30 (2.92–3.65) | 72% | 15% | 2.5% | 4.7 s · 7.6 s | $0.031 | 3 of 4 | 1.0 (0.25 blunders) |
| Haiku | 3.15 (2.77–3.52) | 62% | 15% | 2.5% | 7.5 s · 16.1 s | $0.002 | 1 of 4 | 2.0 (0.25 blunders) |

Exam latency and cost are for a turn's first message in a fresh session. In games, Opus cost $1.15 per game against
Sonnet's $0.80.

- **Paired, per position** (the same 40 positions): Opus − Sonnet +0.42 grade (95% CI +0.03 to +0.82; 10 better,
  27 tied, 3 worse; sign test p 0.09). Opus − Haiku +0.57 (+0.17 to +1.02; 12–26–2; p 0.013). Sonnet − Haiku +0.15
  (−0.30 to +0.60; p 0.79): no difference.
- **Self-preference.** Where its answer differed from every other candidate's, the Opus judge graded Opus best in
  75% of 8 positions, against 12% for Sonnet and 10% for Haiku. The Sonnet judge, which has no stake in Opus, ranks the
  models the same way: Opus 3.75, Sonnet 3.48, Haiku 3.25, with Opus − Sonnet +0.28 (+0.05 to +0.53) and
  Opus − Haiku +0.50 (+0.25 to +0.82, p 0.003). The two judges gave the same grade 68% of the time and grades
  within one 92% of the time.
- **Conclusion:** Opus is the default play model (`agent.backend`), also for teach, the coach and the trainer's
  player, and the deck rules are calibrated to it (confidence medium). Sonnet and Haiku can't be told apart, and
  both make several times more mistakes. Their profiles stay available for cheaper runs.

## Code and tests

`ygo_agent/bench/`: `spec.py` (the plan, seeds), `runner.py` (games through `match.run_games()`, results.jsonl,
resume, probes, versions), `metrics.py` (Wilson, percentiles, aggregation, Bradley-Terry), `report.py` and
`chart.py`. `tests/bench/` covers the statistics, aggregation and reports from synthetic results, the plan and seed
pairing, resume, budget and usage-limit stops with a fake game player, and one tiny real run (heuristic and
random against an in-process heuristic, no LLM) through the whole pipeline. The exam is `exam.py` (sampling, the
runs, aggregation, the report) and `judge.py` (blind labels, the judge's prompt and reply checks, its sandbox, the
whole-game review); `tests/bench/test_exam.py` covers sampling and filtering, labels, identical-choice grades,
aggregation and the self-preference flag, and a scripted run of the whole pipeline with resume, on game logs built
from the saved regression cases.

Who goes first is `run_games(first=...)`, in-process and in WindBot rooms alike (`RoomConfig.first`: the room
still runs the rock-paper-scissors, then starts game 1 with that seat instead of asking the RPS winner).
