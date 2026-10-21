# Benchmarks

`ygo-agent bench` plays headless games to compare backends: the same decks, the same opponents and the same seeds
for every backend. It reports win rates with confidence intervals, a rating, game length, decision latency,
tokens, cost, and how often the model's replies were unusable.

```sh
ygo-agent bench smoke                       # no LLM, about a minute: checks the whole pipeline
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

`--dry-run` prints the plan, `--out DIR` picks the run folder, and `--no-probe` skips the check below.

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

`bench/results/<time>_<name>/`:

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

## Code and tests

`ygo_agent/bench/`: `spec.py` (the plan, seeds), `runner.py` (games through `match.run_games()`, results.jsonl,
resume, probes, versions), `metrics.py` (Wilson, percentiles, aggregation, Bradley-Terry), `report.py` and
`chart.py`. `tests/bench/` covers the statistics, aggregation and reports from synthetic results, the plan and seed
pairing, resume, budget and usage-limit stops with a fake game player, and one tiny real run (heuristic and
random against an in-process heuristic, no LLM) through the whole pipeline.

In WindBot rooms the benchmark decides who goes first through `run_games(on_room=...)`: it replaces the room's
first-player choice after the rock-paper-scissors (`runner.force_first`), since an arena room otherwise leaves it
to the RPS winner.
