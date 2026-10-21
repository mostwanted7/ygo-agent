# ygo-agent

Play Yu-Gi-Oh! in EDOPro against an AI that pilots a real deck (Saffira and Blackwing so far). It shows every
decision and its reasoning in your terminal, and it gets better at the deck from your feedback after each game.
By default the AI is Claude, through your normal Claude Code login (no API key needed); it can also run on the
Anthropic API, any OpenAI-compatible server (Ollama, vLLM, llama.cpp, LM Studio, OpenRouter) or a built-in
heuristic player (see [docs/backends.md](docs/backends.md)).

## Setup

You need Linux, [EDOPro](https://projectignis.github.io/) in `~/Games/ProjectIgnis` (or set `edopro_dir`), Mono
(`mono`, `mcs`, `xbuild`) for the WindBot fork, Python 3.11 or newer, and the `claude` CLI, logged in.

```sh
./build.sh                                   # builds the WindBot fork in windbot-src/
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # optional: the `ygo-agent` command and pytest
```

Without the venv, `python3 -m ygo_agent …` and `./play.sh` do the same thing from the repo folder.

## Playing a game

1. In a terminal: `ygo-agent play` (options: `--deck blackwing`, `--backend sonnet`, `--best-of 3`, `--web`).
   The agent hosts a room (Master Rule 3 by default, `--rules MR5` etc.) and prints where it is.
2. In EDOPro: **LAN Mode**, type the **Host address `127.0.0.1`** and **port `7911`** (`--port` changes it), and
   **Join**. Type the address rather than waiting for the room list: EDOPro may not list the room, and its LAN
   Refresh button can crash EDOPro. Pick your deck, ready up, and the duel starts.
3. Play as many matches as you like (EDOPro offers a rematch); Ctrl+C closes the room and prints the results.

```sh
ygo-agent play --deck blackwing --backend sonnet --web     # with the browser panel at http://127.0.0.1:7930/
```

You get 600 s per turn (`--time-limit`, or `[arena] time_limit` in the config); the AI has no limit. The older way
still works: host the room yourself in EDOPro (LAN Mode → Host, with a long time limit), run `./play.sh` (the same as
`ygo-agent play --join`), and press **Enter** once you're in the room; the agent's bot (the WindBot fork) joins it.

While you play:
- The terminal shows every decision live: the options, what the AI picked, why, and its plan for the turn.
- The duel chat stays quiet apart from a few jokes per duel (`chat = "off"` in the config silences them).
- Type `!` followed by a note in the duel chat (e.g. `!don't Veiler my Stratos, save it`) to bookmark feedback at
  that exact moment. The bot confirms it with "Noted feedback #1." and the note is saved with the game log.

Add `--web` (to `play`, `selfplay`, `teach` or `coach`; `web.auto = true` in the config makes it the default) to
follow the duel in your browser as well, at http://127.0.0.1:7930/:
the board with card pictures, every decision with the options, the choice, the reasoning and the turn's plan, the
event log, and a feedback box that works like a `!note`. `ygo-agent web` browses and replays recorded games
(`←`/`→` steps through the decisions), and `ygo-agent web --demo games/<dir>` replays one live. See
[docs/web.md](docs/web.md).

![The web panel](docs/img/web-panel.png)

After the game:
- The log is in `games/latest/` (each game gets `games/<time>_<deck>-vs-<opponent>/`): `game.md` to read,
  `feedback.md` with your notes, `game.jsonl` and `prompts.jsonl` with the raw data, `meta.json` with the stats,
  and `replay.yrpX` (open it in EDOPro's replay menu; `play --join` games have `windbot.log` instead, and EDOPro
  saves their replay). `games/matches/<time>_.../` holds the run's `results.json` and every game's replay.
- Open Claude Code in this folder and tell it what the AI got wrong. It updates the deck's playbook and rules (see
  CLAUDE.md), and the next game uses them.

Options: `--backend sonnet` (faster, a bit weaker; also `haiku`, `api-opus`, `local`, `heuristic`, `random` or
your own profile), `--model`/`--effort` to override the profile's, `--deck blackwing` (any folder under `decks/`, a
`.ydk` file, or a deck in EDOPro's deck folder), `--port`/`--password` for the room, `--chat off`, `--web` (the
browser panel), `--games N` (close the room after N matches). With `--join`: `--host`, and `--brain-only` (run only
the agent and print the bot command). `ygo-agent play --help` lists them all. At the end of a game the terminal
prints the decision stats (who decided, latency, invalid replies, tokens, cost), which `meta.json` keeps too.

## Self-play: the AI against itself or a WindBot deck

```sh
ygo-agent selfplay --a saffira:opus --b blackwing:sonnet            # one game, AI vs AI
ygo-agent selfplay --a saffira:sonnet --b windbot:Blue-Eyes --games 10 --parallel 3 --quiet
ygo-agent selfplay --a saffira:heuristic --b blackwing:random --games 50 --parallel 4 --quiet   # no LLM: seconds
ygo-agent selfplay --a saffira:opus --b blackwing:opus --spectate --pace 2 --web   # watch it in EDOPro and the browser
```

A seat is `<deck>[:<backend>]` (deck: a folder in `decks/`, a `.ydk` path, or a deck in EDOPro's deck folder;
backend: a profile, default `agent.backend`), `heuristic`/`random` (no LLM; `heuristic:blackwing` picks the deck),
`windbot:<deck AI>` (EDOPro's WindBot deck AIs, listed by `python -m ygo_agent.arena list-bots`) or `human`.

- Two AI seats play in-process, straight on the game engine, with no network; `--parallel K` runs K games at a time,
  each seat with its own model sessions. A WindBot opponent joins an arena room on a free port (parallel games get a
  room each).
- `--spectate` hosts the room on `--port` (7911) and waits before each match until you join as a spectator
  (EDOPro: LAN Mode → Host address `127.0.0.1`, port 7911 → Join; both duelist seats are taken, so you watch) or
  press Enter. `--pace 2` makes every AI decision take at least 2 s, so you can follow.
- The terminal shows both seats' decisions, each line tagged with the seat, deck and backend (`[A Saffira·opus]`);
  `--quiet` shows only the key plays (activations, summons, attacks) and the results.
- At the end: wins, game lengths, and each AI seat's stats (decisions, latency, invalid replies, fallbacks, tokens,
  cost). Each seat logs every game to its own `games/<time>_<deck>-vs-<opponent>/` folder, so the feedback workflow
  below works on self-play games too.
- Options: `--games N`, `--best-of 3`, `--seed S` (reproducible), `--first a|b`, `--stack-a "Card,Card"` (put
  cards on top of A's Deck: its opening hand), `--rules MR5`, `--out DIR`.

From Python, `ygo_agent.match.run_games(seat_a, seat_b, games=N, ...)` does the same and returns every game's
result, which the trainer and the benchmark build on.

## Learning a deck (e.g. Blackwings)

- **Watch:** `ygo-agent teach --deck blackwing --web`. The AI plays against a WindBot deck AI (`--opponent
  windbot:Dragunity`, or another AI seat such as `saffira:sonnet`) and explains every play like a coach; its full plan
  for the turn appears in the terminal and the web panel. Join the room in EDOPro as a spectator (LAN Mode → Host
  address `127.0.0.1`, port 7911 → Join); the duel starts when you're in, or when you press Enter to watch only in the
  browser. As a spectator you can't see its hand in EDOPro, but the terminal and the panel show it. `--pace 3` slows
  it down; `--games N` plays more. The older way still works: host the room in EDOPro, sit as a spectator, add a
  WindBot with *Add AI*, and run `ygo-agent teach --join` (or `./play.sh --deck blackwing --teach`).
- **Be coached:** `ygo-agent coach --web`, then join from EDOPro as for `play` (LAN Mode → `127.0.0.1`, port 7911)
  with the deck you're learning. You play every move in EDOPro; for each decision the terminal and the web panel show
  the AI's recommendation with a short reason (`--level intermediate` for terse ones), then whether you followed it.
  After the game it writes `review.md` (the key moments, what was better and why, what you did well, what to practise)
  and shows it in the panel's Review tab. The deck is recognised from the list you submit (`--deck` to name it); the
  opponent is a WindBot deck AI by default (`--opponent saffira:sonnet` for an AI deck). Your time limit is 1200 s per
  turn (`--time-limit`). `ygo-agent coach --review games/<dir>` reviews a coached game again. See
  [docs/coach.md](docs/coach.md).
- No one coaches the bot on a deck you don't know yet, so after a game ask Claude Code to *review* it. It checks the
  plays against the card scripts and the engine log and updates the playbook (see CLAUDE.md).

## Training the AI on a new deck

```sh
ygo-agent train ~/Games/ProjectIgnis/deck/Geargia.ydk --name geargia --budget-usd 40
ygo-agent play --deck geargia
```

The trainer reads every card and its Lua script, writes a playbook in the style of the Saffira and Blackwing ones,
tests its lines in a lab (stacked opening hands against a dummy that never acts), plays games against WindBot deck
AIs, reviews each game against the scripts and the engine log, and repeats until a round shows no significant
mistakes. You get `decks/geargia/` (playbook, rules template, regression cases) and `decks/geargia/train/` with
everything it did and a `train-report.md`. Opus reviews and Sonnet plays by default (`--backend`,
`--player-backend`); `--resume` continues a stopped run. See [docs/training.md](docs/training.md).

## Benchmark

The AI piloting Saffira and Blackwing against two Master Rule 3 WindBot deck AIs, Blue-Eyes and Time Thief (Bo1),
on 2026-10-21. Every backend gets the same seeds, and the AI seat alternates between going first and second. This is
a **small-sample pilot** with wide intervals: 12 games each for Haiku and Sonnet, 4 for Opus (game 1 of each pairing
only, always going first), and 120 each for the baselines.

| Backend | Games | Win rate (95% CI) | Game 1 only (same deals, going first) | Time per game | Decision latency p50 · p95 | Cost per game | Invalid replies |
|---|---:|---|---:|---:|---:|---:|---:|
| Opus 5.5 (`opus`) | 4 | **100%** (51%–100%) | 4/4 | 2m51s | 2.7s · 7.5s | $1.15 | 0 of 186 |
| Sonnet 5.5 (`sonnet`) | 12 | **58%** (32%–81%) | 3/4 | 3m05s | 1.9s · 5.5s | $0.80 | 0 of 871 |
| Haiku 5.5 (`haiku`) | 12 | **58%** (32%–81%) | 1/4 | 3m03s | 1.6s · 9.0s | $0.06 | 0 of 754 |
| heuristic (no LLM) | 120 | **22%** (15%–30%) | 1/4 | 6s | – | free | – |
| random (no LLM) | 120 | **2%** (0%–6%) | 0/4 | 6s | – | free | – |

![Win rate with 95% CI, and cost per game against win rate](docs/bench/chart.svg)

Cost is the Claude Code CLI's figure at API prices (a subscription login isn't billed per call); no game needed a
fallback. The full report, with every game's EDOPro replay, the per-matchup tables, ratings and versions, is in
[bench/results/2026-10-21_212557_readme/report.md](bench/results/2026-10-21_212557_readme/report.md). Run it yourself
with `ygo-agent bench readme` (`--resume` extends a run on the same seeds), or benchmark a local model by adding an
OpenAI-compatible profile and running `ygo-agent bench --backends local,haiku,heuristic --decks saffira,blackwing
--opponents "windbot:Blue-Eyes,windbot:Time Thief" --games 6 --parallel 1`. See [docs/bench.md](docs/bench.md).

## Configuration

`config/default.toml` holds every setting with a comment. Put your own changes in `config.local.toml` at the repo root
(same layout, only the keys you change; it's gitignored), or pass CLI flags, which win over both files. For example,
to play the EDOPro copy of a deck so that edits made in EDOPro's deck editor carry over:

```toml
[decks.saffira]
ydk = "~/Games/ProjectIgnis/deck/Saffira.ydk"
```

Backends are named profiles under `[backends.NAME]` (type `claude-code`, `anthropic`, `openai`, `heuristic` or
`random`); a profile can also shrink the prompt for small-context models (`card_texts = "compact"`,
`history_lines`, `max_session_messages`). For example, a local model through Ollama:

```toml
[backends.qwen]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
card_texts = "compact"
```

and `ygo-agent play --backend qwen`. [docs/backends.md](docs/backends.md) covers every backend and key.

`[arena]` holds the settings of the rooms the agent hosts (a human's time limit, LAN discovery, the room name), and
`[web] auto = true` starts the web panel with every game (`--no-web` skips it once).

The rules stated to the AI are the room's own (`--rules`, Master Rule 3 by default; with `--join`, read from the
room when the bot joins), and so is the opponent: a human, another AI and its deck, or a WindBot deck AI. When
EDOPro updates its network protocol, the bot notices, retries with the new version and remembers it in
`~/.cache/ygo-agent/`.

## How it works

```
EDOPro (you / a spectator) ⇄ arena room (Python) ⇄ agent seats (in-process) ⇄ backend (default: claude -p, your Claude Code login)
                                              ⇅ WindBot deck AIs (opponents)
play --join:  EDOPro room ⇄ WindBot fork (windbot-src, C#) ⇄ agent (Python, port 7922) ⇄ backend
```

- `windbot-src/` is a fork of ProjectIgnis WindBot, branch `brain-bridge`, for `play --join` and the WindBot
  opponents. When started with `Brain=host:port`, its
  `BrainBridge` sends every decision (the visible board and the legal options) and every game event to the agent; if
  the agent can't answer, WindBot's own AI does. Without `Brain=` it is plain WindBot. Rebuild with `./build.sh`
  after changing it. The message format is in `docs/decision-protocol.md`.
- `ygo_agent/agent/` turns each decision into text, runs the deck's hard rules, asks the backend, checks the answer
  is legal and logs everything. Each game turn gets one backend session, so the AI remembers its plan during the
  turn (and a session that restarts mid-turn is told the plan and the turn's decisions so far).
  `ygo_agent/backends/` holds the backends.
- `playbooks/general.md`: strategy for every deck. `decks/<deck>/` holds what the AI learns about one deck:
  - `playbook.md`: strategy and coaching lessons, given to the AI on every decision.
  - `rules.py`: hard rules that override the AI, for mistakes a lesson didn't fix.
  - `tests/`: past mistakes saved as test cases.
  - `deck.ydk` (the deck list) and `deck.json` (its name, and whether to go first).
- `ygo_agent/web/`: the browser panel. Every game log publishes to an in-process bus that the panel's server streams
  to the page (docs/web.md).
- `ygo-agent replay games/latest 14` re-asks decision #14 with the current playbook and rules, and
  `ygo-agent test` re-runs every saved mistake.
- `ygo_agent/arena/`: the arena, a headless EDOPro host on the game engine (libocgcore) that seats the agent
  in-process ("native seats", no WindBot), EDOPro clients (you, spectators) and WindBot deck AIs, and writes EDOPro
  replays. `ygo_agent/match.py` runs matches on it: `play`, `selfplay`, `teach` and `coach` are built on its
  `run_games()`. `ygo_agent/coach/`: coach mode, the advice for a human's seat and the review after the game.
  `python -m ygo_agent.arena` has the low-level tools (`host`, `bots`, `selfplay-direct`, `list-bots`,
  `replay-info`).

## Tests

- `.venv/bin/python -m pytest`: unit tests (no EDOPro or model needed; the tests that read the EDOPro install skip
  without it). The API backends are tested against local mock servers; `pytest --live` adds one real claude-code
  call (and an Anthropic API call when `ANTHROPIC_API_KEY` is set).
- `tests/run_bridge_test.sh`: checks the C# ⇄ agent ⇄ model plumbing without EDOPro (real model calls, about a minute;
  `--model sonnet` makes it quicker).
- `tests/native/`: the arena's native agent seats (fairness, protocol conformance, parity with the WindBot bridge)
  and `run_games` (in-process and parallel games, a WindBot room, a spectator, the web panel, `selfplay` and `play`);
  `python tests/native/parity.py --games 5` prints a parity report. The LAN test binds UDP 7920: while an arena with
  LAN discovery runs, deselect it (`--deselect tests/arena/test_server.py::test_lan_discovery_reply`).
- `tests/coach/`: coach mode (deck detection; the advice flow with a scripted coach and human; two arena games with
  the arena's Python client as the human).
- `tests/bench/`: the benchmark's statistics, reports, seed pairing and resume logic, plus one tiny real run (no LLM);
  `ygo-agent bench smoke` runs the whole pipeline against a WindBot in about a minute.

## License

AGPL-3.0, like WindBot. See `LICENSE`.
