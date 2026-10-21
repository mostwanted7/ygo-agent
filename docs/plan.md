# ygo-agent: build plan

The orchestrating session maintains this file. Every subagent reads it first. Keep it current: when a stage
finishes, the orchestrator updates **Status** and adds anything later stages need to know to **Notes from
finished stages**.

## Goal

A public GitHub repo, `mostwanted7/ygo-agent` (AGPL-3.0). It provides LLM-driven Yu-Gi-Oh! players for EDOPro
on Linux that can:

1. **Play.** The AI duels a human, another AI (self-play, with a human watching if they like), or a WindBot
   deck AI.
2. **Teach.** It narrates its own plays for a spectator (teach), or coaches a human who plays in the real
   EDOPro UI (coach): live advice plus a review after the game.
3. **Use any backend.** Claude Code CLI, the Anthropic API, and anything OpenAI-compatible (Ollama, vLLM,
   llama.cpp, LM Studio, OpenRouter), plus non-LLM heuristic and random baselines. Each seat chooses its own
   backend.
4. **Train on a new deck.** Given a `.ydk` file, it studies the cards and scripts, tests combos in a lab,
   plays games, reviews them, and repeats until it has a good playbook.
5. **Benchmark.** Headless tournaments produce win rate, latency, token use and invalid-reply rate for each
   backend.

Further requirements:

- The AI's reasoning is shown in the terminal and in a local web panel.
- In-game chat is cut to rare joke lines; the explanation chat is removed.
- Every arena game writes an EDOPro replay file.

The rules target is roughly the pre-Link era: the user's rooms use **Master Rule 3** flags (`lastDuelParam
858112`). The engine enforces every rule. Our job is to state the real rule set in the prompt (never claim
MR5), and to make sure the state text doesn't break when Pendulum, Extra Monster Zones or Link cards appear.

The existing system works well. Keep its behaviour and quality: the decision JSON, `describe.py` text, the
playbooks, rules and regression cases. Generalise it; don't rewrite it for the sake of rewriting.

## Target architecture

```
                         ┌──────────────── arena (Python, headless host) ────────────────┐
 EDOPro client ──LAN────▶│ EDOPro network protocol · per-seat visibility filtering        │
 (human player /         │ duel driver on libocgcore (ctypes) · stacked hands · replays   │
  spectator)             │ seats:  native AI seat │ network seat (human / WindBot)          │
                         └────────────┬───────────────────────────────┬──────────────────┘
                                      │ decision JSON (BrainBridge schema)
 WindBot fork (C#) ──bridge TCP──────▶│                                ▼
 (legacy: joins a room the       agent (per seat): describe → rules → backend → validate
  user hosts in EDOPro;           playbooks/general.md + decks/<deck>/playbook.md + rules.py
  also WindBot deck AIs           logs games/<id>/…   web panel (SSE)   coach / trainer / bench
  as opponents)                   backends: claude-code | anthropic | openai-compatible | heuristic | random
```

- **Native AI seats** live inside the arena. The arena builds decisions straight from core messages plus core
  queries, filtered to what that player is allowed to see, and emits **the same JSON schema the C#
  BrainBridge emits today**. So the agent, `describe.py`, rules and saved tests work unchanged. The schema is
  documented in `docs/decision-protocol.md`.
- **The WindBot fork** stays for two jobs: joining a room the human hosts in EDOPro (legacy `play --join`),
  and running WindBot's built-in deck AIs as opponents.
- **Python package `ygo_agent`.** One CLI, `ygo-agent`, with subcommands `play`, `selfplay`, `coach`,
  `teach`, `train`, `lab`, `bench`, `replay`, `test` and `doctor`.

### Planned layout (adjust if there's a good reason, and record it here)

```
pyproject.toml  LICENSE  README.md  CLAUDE.md  config/default.toml
ygo_agent/
  cli.py  config.py  paths.py
  agent/      brain.py describe.py carddb.py rules.py validate.py gamelog.py prompts.py profile.py bridge_server.py
  backends/   base.py claude_code.py anthropic_api.py openai_compat.py heuristic.py random_.py
  core/       ocgcore.py (ctypes) cards.py (cdb → OCG_CardData) scripts.py (EDOPro search order) constants.py
  arena/      duel.py messages.py visibility.py protocol.py server.py seats.py native_seat.py replay.py windbot.py
  coach/  trainer/  bench/  web/
playbooks/general.md
decks/<name>/  deck.ydk  deck.json  playbook.md  rules.py  tests/*.json
windbot-src/   WindBot fork (own git repo, branch brain-bridge; becomes a submodule at publish time)
tests/         pytest: unit tests always; integration tests skip if EDOPro/core/mono are missing
docs/          plan.md, decision-protocol.md, architecture.md, …
```

## Ground rules for every subagent

- Read this file, `README.md`, `CLAUDE.md` and the files you'll touch before changing anything. Match the
  existing style: concise, readable Python and few comments, written to explain *why*.
- Stdlib first. Any dependency must be small and justified. Optional extras (`anthropic`, `openai` SDKs) are
  imported lazily and give a clear error message when missing. The target is Python ≥ 3.11; the machine runs
  3.14.
- Tests live in `tests/`. Use a venv at `.venv` (`python3 -m venv .venv && .venv/bin/pip install pytest`).
  Unit tests must not need EDOPro, mono or an LLM. Integration tests use the real
  `~/Games/ProjectIgnis` install and skip cleanly without it.
- **Never run git commit, push, or anything touching GitHub. The orchestrator commits.**
- Never edit `~/Games/ProjectIgnis` or the user's `.ydk` files there. Copies inside the repo are fine.
- Process hygiene: never use `pkill -f`/`pgrep -f` with a pattern that appears in your own command line. Kill
  by PID. Leave no background processes running when you finish.
- Real LLM calls go through the user's Claude Code login (`claude -p`). Use them when a stage needs them
  (smoke tests, trainer, bench), but prefer `--model sonnet` or `haiku` for plumbing checks.
- Finish with a short report: what changed (files), how you verified it (commands and results), what's left
  or risky, and anything the next stages must know. Don't claim anything you didn't run.

## Reference material

- `.spike/arena/`: the working feasibility prototype. It contains `ocgcore.py` (ctypes binding, card DB,
  script resolver), `selfplay.py` (a direct-core loop that decodes all 21 prompt types and has stacked-hand
  support) and `arena_server.py` (an asyncio EDOPro-protocol host with filtering). `run_bots.sh` runs two
  WindBots through it. `ref/` and `ref-net/` hold ygopro-core headers and EDOPro/Multirole network sources.
  - Results: 13 of 13 headless WindBot-vs-WindBot duels completed, with no RETRY and no Lua errors.
  - Facts:
    - Use `~/Games/ProjectIgnis/repositories/delta-bagooska/bin/libocgcore.so` (core 11.0). EDOPro loads this
      copy, not the one at the install root.
    - Load `constant.lua` and `utility.lua` yourself, searching scripts in EDOPro's order.
    - Load all `.cdb` files, with repo ones overriding.
    - An all-zero seed fails.
    - The host shuffles; `main[0]` ends up on top.
    - ClientVersion `{41,0,11,0}` = 720937; HostInfo handshake 0xF1016201.
    - MR5 = 0x2E800, MR3 = 858112.
    - Chat from EDOPro's host is `STOC_CHAT_2` (0xF3), which the WindBot fork ignores. That's why `!notes`
      never arrived.
- `windbot-src/ExecutorBase/Game/BrainBridge.cs` is the reference for the decision JSON, option ordering and
  reply semantics. `brain/server.py` holds the decision flow.

## Stages

Status: ☐ todo · ◐ in progress · ☑ done (verified by the orchestrator)

### Stage 0: Foundation ☑
- Package `ygo_agent` with the CLI. `brain/` moves into `ygo_agent/agent/` with its behaviour unchanged.
- Config moves to `config/default.toml`, with user overrides in `config.local.toml` (gitignored) and CLI
  flags on top. Nothing rewrites config at runtime; the detected protocol version is cached under
  `~/.cache/ygo-agent/`.
- Decks become self-contained: `decks/<name>/deck.ydk` is a copy of the user's file, and `deck.json` can
  point at an external `.ydk` (local override) so edits made in EDOPro still carry over.
- The deck-agnostic strategy moves out of `INTRO` into `playbooks/general.md`.
- Prompt wording becomes model-neutral ("You are an expert Yu-Gi-Oh! duelist…"). The rules sentence comes
  from the actual duel or config (MR3 by default). The opponent description depends on the mode (human
  opponent, AI opponent, spectator being taught).
- Chat: remove the explanation lines. Add a small `banter` module: rare short joke lines at duel start, on a
  big play, at the win and the loss (≤ 4 per duel; config `chat = "banter" | "off"`). Keep `!note` capture.
- Bugs:
  - The WindBot fork handles `STOC_CHAT_2`.
  - Fix the `select_unselect` fallback double-ask.
  - Log replies (and the action actually taken) in `game.jsonl`.
  - Reset state for Bo3 game 2+.
  - Give each game a unique log directory (`games/<ts>_<deckA>-vs-<deckB>/`, `latest` symlink).
  - The rest of the WindBot fork: rename `ClaudeExecutor` → `AgentExecutor` (deck name `Agent`, keep `Claude`
    as an alias), commit the fork changes on branch `brain-bridge` inside `windbot-src`, and make `build.sh`
    keep working.
- Repo hygiene: top-level `git init` (the orchestrator commits), `.gitignore` (`games/`, `bin/`, `.venv`,
  `config.local.toml`, `.spike/`, binaries), AGPL-3.0 `LICENSE`. Scrub absolute paths from test cases
  (`source` → relative). Delete `tests/BridgeTest.exe` and build it in the test script.
- `docs/decision-protocol.md`: the full bridge schema (events, decision kinds, options, reply semantics).
- pytest skeleton plus unit tests (describe/validate/rules on the saved test-case fixtures).
- Update `CLAUDE.md` and `README.md` for the new commands.
- Verify: unit tests pass; `tests/run_bridge_test.sh` passes; `ygo-agent replay --tests` runs (one case is
  enough for timing); `ygo-agent play --join` still launches WindBot correctly.

### Stage 1: Backends ☑ (after 0)
- `Backend.open_session(system_prompt) → Session.ask(text, schema, timeout) → (reply|None, info)`. `info`
  holds seconds, input/output/cache tokens, cost if known, and error.
  - `claude-code`: the current CLI. Pass the system prompt via a file or stdin, not argv.
  - `anthropic`: Messages API with prompt caching on the system prompt, structured output via a tool or
    `output_format`, and history kept per session.
  - `openai-compatible`: `/v1/chat/completions` with `response_format` json_schema when supported, else JSON
    mode, else prompt-and-parse. One repair retry.
  - `heuristic`: a sensible no-LLM policy, also used as the fallback in native seats.
  - `random`: uniform legal choice.
  - `scripted`: for tests.
- Named backend profiles in config (`[backends.opus] type="claude-code" model="opus" effort="medium"`,
  `[backends.local] type="openai" base_url=… model=…`). A seat picks one with `--backend NAME`. Allow a
  context budget for small models (history length, and an optional compact card-text mode).
- Carry the turn plan across session rollover: feed back the last `plan`.
- Tests: mock HTTP servers for the anthropic and openai backends; a real one-call smoke test for
  claude-code.

### Stage 2: Arena ◐ (parallel with 0; touches only `ygo_agent/core`, `ygo_agent/arena`, `tests/arena`)
- Turn the spike into production code:
  - core binding, card data, script loader;
  - duel driver with seed control, rules flags (mr1 to mr5), deck validation, stacked opening hands / custom
    start states;
  - EDOPro network host: lobby, RPS/first choice, duel loop, per-player and spectator filtering, refreshes,
    chat in both directions, surrender, time limit, Bo1/Bo3, spectator catch-up;
  - a WindBot launcher for opponents (WindBot deck AIs from EDOPro's `WindBot/bots.json`, or the fork with
    `Brain=`);
  - **EDOPro replay files** (`.yrpX`), so every game can be reopened in EDOPro.
- Tests: packet codec, filtering, and headless WindBot-vs-WindBot games (N seeds) as an integration test.
- User checkpoint: the user joins the arena from EDOPro (LAN → host 127.0.0.1) as a player and as a
  spectator, and opens a replay.

### Stage 3: Native AI seats ☐ (after 2, and after 0 for the agent API)
- `native_seat.py`: core prompts plus queries → BrainBridge-schema decisions and events, filtered to that
  player's view. Choices are encoded into core responses. When the agent returns nothing, the heuristic
  fallback answers.
- Add the state the core gives us for free (current Level/Rank, counters, equip targets, Pendulum scales).
  These are optional fields; `describe.py` shows them.
- Tests:
  - **Fairness test**: no hidden opponent information in any decision or event.
  - **Parity test**: the same seed and the same deterministic policy through a native seat and through a
    WindBot seat yield the same game, or a recorded list of known differences.
  - A full heuristic-vs-heuristic headless duel in CI-style integration tests.

### Stage 4: Multi-seat agent, self-play, watching ☐ (after 1 and 3)
- The agent is per seat, with its own deck profile, backend, mode and log. Several duels and seats run in one
  process.
- CLI:
  - `play` (arena hosts; human joins from EDOPro);
  - `play --join` (legacy: bot joins the room the user hosts);
  - `selfplay --a saffira:opus --b blackwing:local [--spectate --pace 2s] [--games N]`;
  - `teach` (AI plays and explains for a spectator).
- Reasoning goes to the terminal, cleanly per seat.

### Stage 5: Coach mode ☐ (after 4)
- The human plays in EDOPro. The arena builds that seat's decision JSON (the human's own view) and asks the
  coach agent for advice asynchronously. Advice appears in the terminal and the panel, marked "late" if the
  human answered first.
- The human's response is decoded back into option indices and compared with the advice.
- After the game: `review.md` covering the key divergences and why, against the playbook. The old terminal
  copilot is replaced by coach mode; remove it once coach works.

### Stage 6: Trainer ☐ (after 4; uses the lab from 2/3)
- `ygo-agent train path/to/deck.ydk --name foo [--backend opus] [--budget …]`:
  1. **Study**: card texts plus Lua scripts → card notes and a draft playbook in the house style (game plan,
     engine cards, main lines, Extra Deck usage, going second, locks).
  2. **Lab**: K seeded opening hands, solo turn against a passive opponent. Record end boards and engine
     rejections, mark lines verified or unverified, and fix broken lines.
  3. **Games**: games against WindBot deck AIs, reviewing each one with the Blackwing-style review (see
     CLAUDE.md). The output is dated lessons plus regression cases.
  4. **Converge**: stop when a review finds no significant mistakes, or when the budget runs out. Write
     `train-report.md` with the win-rate progression.
- The trainer backend can differ from the player backend. Prove it on a new deck from the user's
  `~/Games/ProjectIgnis/deck/` (e.g. Geargia or Chaos), and sanity-check it against the existing Saffira and
  Blackwing playbooks.

### Stage 7: Bench ☐ (after 4)
- `ygo-agent bench --decks … --backends … --opponents … --games N`. Output: `bench/results/<ts>/results.md`
  and `.json`, with win rate and CI, mean and p95 latency, tokens, invalid-reply and fallback rates, and game
  length.
- Run a real benchmark (e.g. claude-code opus/sonnet/haiku plus heuristic and random against WindBot decks)
  for the README table.

### Stage 8: Web panel ☐ (after 4; coach integration after 5)
- `--web` serves a local page (stdlib/asyncio HTTP plus SSE, vanilla JS, no build step). It shows the board
  with card images from `~/Games/ProjectIgnis/pics`, a live decision stream with reasoning and plan, coach
  advice, both seats in self-play, and a feedback box that does the job of `!note`.
- It should be good enough for a demo GIF.

### Stage 9: Polish and publish ☐
- `ygo-agent doctor`: checks the EDOPro dir, core version, scripts, mono, the fork build and backends.
- Docs: `architecture.md`, adding a deck, adding a backend. README with diagram, demo GIF, bench table and
  quick start.
- GitHub Actions: unit tests, plus a C# fork build if feasible.
- Publish, **only after the user confirms**:
  1. fork `ProjectIgnis/windbot` → `mostwanted7/windbot` and push branch `brain-bridge`;
  2. add `windbot-src` as a submodule;
  3. create the public repo `mostwanted7/ygo-agent` and push. Commit identity: Rebel <laki@hotmail.rs>.

## Notes from finished stages

**Stage 0 (commit b56c7fd).**
- Additions to the planned layout: `ygo_agent/join.py` (launches WindBot into a room the user hosts),
  `cache.py`, `agent/banter.py`, `agent/replay.py`, `agent/validate.py`. The `bridge_server.py` `Runtime`
  holds one `Match` per bot connection, with a fresh `DuelBrain` and log for each game.
- Backend seam: `backends.open_session(profile, system_prompt, SCHEMA)` → a session with
  `.ask(text, timeout) → (dict|None, info)`, `.alive`, `.messages` and `.close()`. Also `backends.check()` and
  `backends.label()`. `SCHEMA` lives in `agent/prompts.py`. Config has `[backends.NAME]` tables and
  `agent.backend`; `--backend`, `--model` and `--effort` override them. The claude-code backend still passes
  the system prompt on argv.
- Bridge additions: a `room` event (the room's real `duel_flags`), a `chat` event with `source`, and a
  `game_over` decision round trip after `win`, which lets the reply carry a final `say`. Ids restart at 1 per
  game. Native seats must emit these too.
- Fork commit 6610fbd on branch `brain-bridge` in windbot-src (not pushed). The bridge is active only with
  `Brain=`. Deck `Agent` (alias `Claude`).
- Tests: `tests/fixtures/cards.json` plus `CardDB.from_dict` (regenerate with `tests/fixtures/make_cards.py`)
  let tests run without EDOPro. There are 60 pytest tests.
- Still left to WindBot: `place`, and `announce_card` with more than 150 names.

**Stage 1.**
- Interface: `backends.create(profile, db)` → `Backend` (`.label`, `.check()`, `.describe()`,
  `.open_session(system_prompt, schema)`), then `session.ask(Request(text, decision, schema, timeout, error))`
  → `(reply|None, info)`. Info fields and per-game stats are documented in `docs/backends.md`, which Stage 7
  aggregates.
- Per-seat agent: `DuelBrain(cfg, db, profile, backend=<profile dict|Backend>, fallback="heuristic")`,
  then `on_event(ev)` / `on_decide(d)` → `{"id","choice","say"}`. With `fallback="heuristic"` the choice is
  never null except on `game_over`. That covers place, `announce_card` with more than 150 names, and backend
  failure; after a `retry` it answers at random.
- Native seats must catch exceptions themselves (`heuristic.Policy(db).choose(d)` / `first_legal(d)`) and
  emit `new_turn`, which drives pre-warming, per-turn sessions and the plan carry-over.
- Prompt budget: `card_texts = full|compact|none`. Saffira is 10.2k/8.4k/6.1k tokens, Blackwing
  13.9k/11.5k/8.0k.
- Not run against a real Ollama/vLLM server (only the mock), and no real Anthropic API calls (no key).
- Reply `source` is `backend`, not `llm`. The bot name defaults to `ygo-agent`. Shared test helpers are in
  `tests/helpers.py`.
