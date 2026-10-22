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

### Stage 2: Arena ☑ (parallel with 0; touches only `ygo_agent/core`, `ygo_agent/arena`, `tests/arena`)
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

### Stage 3: Native AI seats ☑ (after 2, and after 0 for the agent API)
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

### Stage 4: Multi-seat agent, self-play, watching ☑ (after 1 and 3)
- The agent is per seat, with its own deck profile, backend, mode and log. Several duels and seats run in one
  process.
- CLI:
  - `play` (arena hosts; human joins from EDOPro);
  - `play --join` (legacy: bot joins the room the user hosts);
  - `selfplay --a saffira:opus --b blackwing:local [--spectate --pace 2s] [--games N]`;
  - `teach` (AI plays and explains for a spectator).
- Reasoning goes to the terminal, cleanly per seat.

### Stage 5: Coach mode ☑ (after 4)
- The human plays in EDOPro. The arena builds that seat's decision JSON (the human's own view) and asks the
  coach agent for advice asynchronously. Advice appears in the terminal and the panel, marked "late" if the
  human answered first.
- The human's response is decoded back into option indices and compared with the advice.
- After the game: `review.md` covering the key divergences and why, against the playbook. The old terminal
  copilot is replaced by coach mode; remove it once coach works.

### Stage 6: Trainer ☑ (after 4; uses the lab from 2/3)
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

### Stage 7: Bench ☑ (after 4)
- `ygo-agent bench --decks … --backends … --opponents … --games N`. Output: `bench/results/<ts>/results.md`
  and `.json`, with win rate and CI, mean and p95 latency, tokens, invalid-reply and fallback rates, and game
  length.
- Run a real benchmark (e.g. claude-code opus/sonnet/haiku plus heuristic and random against WindBot decks)
  for the README table.

### Stage 8: Web panel ☑ (panel, replay browser, demo, live self-play and coach wiring)
- `--web` serves a local page (stdlib/asyncio HTTP plus SSE, vanilla JS, no build step). It shows the board
  with card images from `~/Games/ProjectIgnis/pics`, a live decision stream with reasoning and plan, coach
  advice, both seats in self-play, and a feedback box that does the job of `!note`.
- It should be good enough for a demo GIF.

### Stage 9: Polish and publish ◐ (polish done 2026-10-22; publishing waits for the user)
- **Deck storage, agreed with the user (2026-10-21).** The repo ships curated decks in `decks/<name>/`:
  playbook, rules, tests, ydk, deck.json and train-report.md. `decks/*/train/` is gitignored, apart from the
  report, because it holds logs, prompts, copied scripts and card text. User-trained decks go to a
  personal decks dir (e.g. `~/.local/share/ygo-agent/decks/`, configurable), which is also searched, so
  training never dirties the repo and updates never clobber it. Sharing a deck is a deliberate copy into
  `decks/` plus a PR. `train` writes to the user dir by default (`--into repo` writes to `decks/`).
- ☑ `ygo-agent doctor`: checks the EDOPro dir, core version, scripts, mono, the fork build and backends.
- ☑ Docs: `architecture.md`, adding a deck, adding a backend. README with diagram, demo GIF, bench table and
  quick start.
- ☑ GitHub Actions: unit tests (3.11-3.13), plus the C# fork build in the mono image.
- ☑ Review pass: one card-db reader, the exam split into a package, leaks and races fixed, security findings
  applied (see the Status below).
- Publish, **only after the user confirms**:
  1. fork `ProjectIgnis/windbot` → `mostwanted7/windbot` and push branch `brain-bridge`;
  2. add `windbot-src` as a submodule;
  3. create the public repo `mostwanted7/ygo-agent` and push.

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

**Stage 2.**
- Check: re-simulating the user's EDOPro-hosted `_LastReplay.yrpX` gives a message stream byte-identical
  to EDOPro's.
- Games run: 600 direct-core games, 40 over TCP with Python clients and a spectator, 30 WindBot-vs-WindBot.
  All had 0 retries and 0 Lua errors.
- Seats: subclass `arena.Seat` and implement `choose(prompt, retry) -> bytes | awaitable`; never block,
  because that stalls the server. Optional hooks are `on_message`, `rps`, `go_first` and `on_end`.
  `PolicySeat(name, policy)` wraps a callable.
- `SeatView` (`location()`, `card()`, `snapshot()`, `field()`) is the fair view: opponent hidden cards have
  no codes, and your own deck is a count only.
- Observers: a `DuelObserver` gets `on_message(view, msg)`, `on_prompt`, `on_response` and `on_end`
  (`Room.duel_observers`, `duel_observer_factory`). A `RoomObserver` gets join, leave, chat and end events.
- Prompts are dataclasses (`messages.py`) built from `CardRef(code, controller, location, sequence,
  position)`. SELECT_CARD, TRIBUTE and UNSELECT zero the codes of opponent cards, even face-up ones;
  rebuild identity from `SeatView.card()`. Responses use `SelectIdleCmd.respond(IdleAction.X, i)` and
  similar. Queries return `CardQuery` (counters, overlays, current level, scales, equip/target).
- Stacking: `Duel(..., stack={team: [codes]})`, `run_match(stack=...)` or `--stack-hand0`. Custom boards use
  `StartState([Placement(...)])`. In-process games: `run_duel(Engine.load(), DuelConfig(rules="mr3"),
  decks, seats, seed=)`.
- Replays: `.yrpX` files that match EDOPro field by field, and STOC_NEW_REPLAY is sent. Comparisons must use
  `replay.streams_match`, because some hint-message order differs.
- **User GUI check, 2026-10-21: passed.** The user joined by IP (LAN → 127.0.0.1:7911) with Geargia against
  `windbot:Blue-Eyes`. Two full duels, with the lobby, RPS/first, timer, chat and replay (EDOPro auto-saved
  `_LastReplay.yrpX` from our STOC_NEW_REPLAY, and it plays back) all fine. The LAN list didn't show the room:
  EDOPro's own refresh button segfaults in MenuHandler::OnEvent before any reply arrives, an EDOPro bug.
  Still untested: spectator catch-up, and the Bo3 side flow.
- Additions to the planned layout: `arena/{runner,deck,client,policies,gamelog,cli}.py`. CLI:
  `python -m ygo_agent.arena host|bots|selfplay-direct|list-bots|replay-info`.

**Stage 8a (web panel, commit 79ca9ee).**
- Code is in `ygo_agent/web/` (bus, render, server, recorded, pics, demo, static/); the message schema is in
  `docs/web.md`. The only hook is in `GameLog`, so any seat that logs through it appears on the panel.
  Publishing does nothing when the panel is off.
- `play`/`teach`/`copilot --web` use port 7930. `ygo-agent web` browses recorded games, and
  `ygo-agent web --demo games/<dir> --speed 2` replays one live.
- Stage 4 must create each seat's `DuelBrain(..., game_id=G, seat=S)` with one shared `G` per duel; otherwise
  two seats show up as two games. Stage 5 must publish `decision` → `advice` (with `late`) →
  `human_choice` (with `matched`) for the human seat; copilot already sends this sequence.
- Screenshots are in `docs/img/` (1.9 MB; compress them in Stage 9). `tests/web/shoot.mjs` takes them with
  headless Firefox and Node.

**Stage 3.**
- New files in `arena/`:
  - `native_view.py`: the bridge event stream, plus card tracking the way WindBot does it.
  - `native_decide.py`: `build(prompt, view)` → `Decision` with `.fields`, `.encode(choice)` and
    `.decode(response)`.
  - `native_seat.py`: `AgentSeat.create(deck, backend)`, `add_to_room`, `PacedSeat`, `link(a, b,
    match_id=)` (a shared web `game_id`) and `SeatWatcher(team, cards, on_decision=, on_choice=)`. The
    watcher is a DuelObserver for the human seat: it builds the human's own-view decision JSON and decodes
    each response into option indices. Use it in Stage 5.
- Parity with the WindBot bridge over 19 games: kind and option count 100%, option meaning 1,679 of 1,685
  (the rest is a WindBot bug). The known differences are all on WindBot's side.
- Fairness: 0 leaks across 12 games, and all 6 injected leaks were caught. 60 heuristic-vs-heuristic games
  and 11 against WindBot decks ran with 0 crashes.
- Sonnet smoke game: Saffira beat Blue-Eyes in 7 turns, with 0 invalid replies and 2.4 s mean per decision.
- Optional fields: `ctr`, `sc`, `blv`, `own`, `uid`. Optional events: `confirm`, `equip`, `swap`, `counter`,
  `coin`, `dice`, `declared`, and `flip` on summoning.
- Arena CLI: `agent:<deck>[:<backend>]` seats, `--pace`, `--games-dir`, `--chat`.
- Open points (1) a false rollover when rules answered a turn's first decisions, (2) `confirm.cards` texts
  missing from the prompt and (3) identical Xyz-procedure options were all fixed by Stage 4 (checked in the
  2026-10-22 review, each with a test). Brain fallbacks are only `place` (about 16%, as in the bridge). The
  LAN test binds UDP 7920, so deselect it while an arena is running.

**Stage 4.**
- `ygo_agent/match.py` is the API that Stages 5, 6 and 7 build on:
  - `SeatSpec.parse("saffira:opus" | "path.ydk:sonnet" | "heuristic[:deck]" | "random" | "windbot:Blue-Eyes" | "human")`.
  - `run_games(seat_a, seat_b, games, *, rules, seed, best_of, pace, parallel, spectate, web, web_port, out,
    stack, start_state, first, on_game, on_room, quiet, …) -> RunResult`. A `RunResult` holds
    `GameResult`s (winner, reason, turns, seconds, first, seed, replay, retries, lua_errors, plus one
    `SeatResult` per seat with kind, name, deck, backend, log_dir and the meta.json stats); helpers are
    `wins()`, `seat_totals(i)`, `summary_lines()` and `to_dict()`. Setup problems raise `MatchError`.
  - AI-vs-AI games with no spectator run in-process, on threads when `parallel`. Anything with WindBot, a
    human or a spectator goes through an arena room. `on_room(room)` is the hook for the Stage 5 coach.
  - Output: `games/matches/<ts>_<a>-vs-<b>/results.json` plus replays. Seat logs are in `log_dir`.
- CLI: `play` (arena-hosted, `--web`), `play --join` (legacy), `selfplay --a --b [--games --parallel
  --spectate --pace --quiet --web]`, `teach --deck [--opponent]` (waits for a spectator).
- Stats change: native seats' zone placements count as `auto`, not `fallback`.
- Sonnet vs Sonnet (Saffira vs Blackwing): Blackwing won in 15 turns, 16 min, about $4.8, with 1 invalid
  reply out of 351 and 0 fallbacks. The play looked sensible.
- Gaps: WindBot seats can't be paced (they answer over the network). The spectator gate is per match, by
  design (games 2-3 of a Bo3 follow siding). Spectating from the EDOPro GUI was checked by the user.

**User GUI checks after Stage 4 (2026-10-21).**
- `ygo-agent play --deck saffira --backend opus --web`: the user played Geargia against the AI and lost.
  The user: "bot played perfectly".
- `selfplay --spectate --pace 2`: spectating works in EDOPro, and leaving and rejoining mid-duel catches
  the board up correctly.
- Bug found: the web panel's board froze at decision #20 for the rest of the game, while the reasoning list
  kept updating. Suspected cause: native `place` decisions answered with a zone mask, which the panel never
  saw from the WindBot path. The Stage 5 agent is fixing it, together with clearer live/paused state.

**Stage 7 (bench).**
- `ygo_agent/bench/` (spec, runner, metrics, report, chart) and `bench/configs/{readme,smoke}.toml`.
- Pilot run: `bench/results/2026-10-21_212557_readme/`, 268 games, copied to `docs/bench/`.
  - Opus 4/4; Sonnet 7/12; Haiku 7/12; heuristic 26/120; random 2/120.
  - Like-for-like on game 1 of each pairing: Opus 4/4, Sonnet 3/4, Haiku 1/4.
  - 0 invalid replies out of 1,811.
- Extend the pilot after the usage reset: raise the counts in `readme.toml`, then `ygo-agent bench readme --resume`.
- Opponent strength scan: heuristic win rate against Branded 0%, Blue-Eyes 5%, Time Thief 25%, Dragunity 70%.
- Bench and trainer force who goes first through `RoomConfig.first` (`first=` in `run_games`); the old
  `room._ask_first` monkeypatch is gone.

**Stage 6 (trainer).**
- `ygo_agent/trainer/` (dossier, goldfish, lab, games, review, llm, report) and the commands
  `ygo-agent train` / `train-compare`.
- The reviewer is agentic `claude -p` with only Read/Grep/Glob in a sandbox copy, or inline for other
  backends. A lesson is applied only when its quoted evidence checks out against the script or log.
- Geargia: 2 rounds, 2-2 in games, 12 lessons, 7 regression cases, 5 of 8 lines verified in the lab,
  about $14, 50 min. Did not converge: round 2 still found 5 major mistakes.
- Follow-ups for Stage 9:
  1. Condensing must not lose behaviour. The final condense took 21.6 KB to 13.9 KB, but regression cases
     fell from 7/7 to 5/7. Gate every condense on the saved cases, and retry or keep the longer text if
     they drop.
  2. The player "never went to Battle Phase" in both rounds. Consider a general built-in rule or a
     stronger general.md line (enter the Battle Phase when an attack is possible and favourable), and
     have the trainer write proposed rules into `rules.py` behind a flag.
  3. Prune stale open questions.
  4. `describe.py` prints "Opponent Special Summons X" before the negation window (Solemn Strike), so the
     player believed the summon had resolved. Word it as "is being Special Summoned", or move it after the
     window.
  5. Gitignore `decks/*/train/` except `train-report.md`, per the agreed deck-storage layout.
  6. After the usage reset: `ygo-agent train-compare --name geargia --games 2 --opponent windbot:Blue-Eyes --parallel 3`.

**Stage 5 (coach) and the web fix.**
- `ygo_agent/coach/` (live, brain, review, detect, cli); `ygo-agent coach [--deck --backend --opponent --level --web]`
  and `coach --review DIR`. Copilot is removed; old copilot logs still replay.
- Web freeze root cause: clicking the newest decision card pinned the board while the header still said
  LIVE. Now there's a not-live banner, PAUSED AT #N, per-message try/catch with an error chip, and a browser
  regression test on the user's game (anonymised fixture).
- Real check, with a scripted human vs Blue-Eyes: Sonnet advice arrives about 2 s after the decision, Haiku
  about 5 s. The reviews are useful, but they had two hallucinated rulings (Sonnet: SDQ summons Idaten;
  Haiku: Normal-Summoned monsters can't attack). The prompts were tightened, but no game was re-run
  afterwards, so re-check after the usage reset.
- Never played by a real human in EDOPro yet: that's the user test after the reset.

## Remaining work (Stage 9 and follow-ups), as of 2026-10-21 22:40
Usage window nearly exhausted, so this waits for the reset. Then:
1. **Fixes:**
   - trainer condense gated on regression cases;
   - a Battle Phase rule or general.md line;
   - prune stale open questions;
   - describe "is being Special Summoned" before negation windows;
   - a proper first-player option (`RoomConfig.first`) replacing the `_ask_first` patches in bench and
     trainer;
   - user decks dir (`~/.local/share/ygo-agent/decks/`, `train` writes there by default, `--into repo`).
2. **Quality pass:** a code review of the whole repo for bugs, dead code, naming and duplication
   (e.g. `agent/carddb.py` vs `core/cards.py`); keep the tests green.
3. **`ygo-agent doctor`**, plus a first-run `setup` (build the fork, venv hints).
4. **Docs:** `architecture.md` (with a diagram), adding a deck, adding a backend; a README overhaul (pitch,
   GIF, quick start, features, bench table, how it works); compress the images.
5. **CI:** GitHub Actions running the unit tests (no EDOPro), plus a mono build of the fork if feasible.
6. **Real checks:**
   - user coach-mode test in EDOPro;
   - `train-compare --name geargia`;
   - extend the bench (`bench readme --resume` with higher counts);
   - re-run one real coach review.
7. **Publish, with user confirmation:** fork windbot → `mostwanted7/windbot` branch `brain-bridge`;
   `windbot-src` as a submodule; create `mostwanted7/ygo-agent` (visibility per the user) and push.

## 2026-10-22: user feedback and the new sequence
- The folder is renamed to `~/Projects/ygo-agent`. A symlink from `yugioh-claude` keeps old paths working.
  The venv was rebuilt and the fork rebuilt.
- **The user will do the polish (Stage 9 items 2-5) in a separate session.** Tell them when the codebase is
  ready for review. Publishing still needs their confirmation.
- Playbook style, agreed: principle-first and short, overridable by the bot. Specifics and pitfalls go in a
  bottom section; no hard-coded lines. Hard rules are only for the play model's repeated no-judgment
  mistakes, each backed by a regression case, with rule ablation when the model changes. The user's
  Geargia insights go into decks/geargia (Gadget + Armor vs Gigant X, Gigant X with Geargianos in GY,
  Geargiagear at the opponent's end of turn, Limiter Removal ×1–2 + Gagaga Cowboy lethal).
- **Standardise on one Claude play model**, chosen by a proper comparison: equal games for opus, sonnet and
  haiku, with win rate plus a reviewer-counted mistakes-per-game metric. Local models come later, on the
  user's desktop (RX 9070).
- Running now: (a) the playbook-style + rules-policy + Geargia rewrite; (b) functional fixes (describe
  summon wording, `RoomConfig.first`, user decks dir, attack-available line, bench smoke output dir).
  Next: (c) the model comparison, then the Geargia evaluation (new playbook vs none) with the chosen model,
  then the user's coach-mode test with Geargia.

## Status 2026-10-22 (commit 9a68082): feature-complete, ready for the user's review session
- Done since the feedback:
  - principle-first playbooks and the trainer style;
  - the rules policy with `test --ablate-rules`;
  - summon-window wording, the attack note (excludes monsters a face-up card stops from attacking), chain
    target stats, shared-effect-label qualifiers;
  - `RoomConfig.first`; the user decks dir plus `ygo-agent decks`;
  - `bench exam` (a blind Opus judge plus a Sonnet second judge).
- **Opus is the play model** (exam: 3.73 vs Sonnet 3.30 vs Haiku 3.15; 0.2 vs 1.0 vs 2.0 mistakes per game).
  `decks/geargia` is the user's Gadget Geargia list.
- Open:
  - more coached games from the EDOPro GUI (the user played two on 2026-10-22);
  - the attack note still misses non-negating locks (Spellbinding Circle, Swords). An exact fix needs
    card-target links in the decision JSON, i.e. a C# change;
  - ~~`train-compare` for Geargia (now with Opus as the player)~~ done 2026-10-22 (see the end of this file);
  - local models on the desktop: exam → hybrid routing (local model for routine decisions, escalate hard
    ones to Opus) → maybe distillation (fine-tune on logged Opus decisions);
  - publishing (needs confirmation).

## Status 2026-10-22 (polish pass): reviewed, ready to publish after the user's look
- Review pass by six agents in parallel worktrees plus a read-only security scan, squash-merged in logical
  commits (`git log` from c6bb66f): CI; the exam judge transcripts dropped (local paths, session ids, account
  telemetry); the agent core (one card-db reader on `core/`, session cleanup); the exam split into
  `ygo_agent/bench/exam/`; README and docs (architecture, adding a deck, adding a backend, demo GIF, smaller
  images); `ygo-agent doctor`; coach and web (bounded POSTs, stalled streams, a renderer race); the arena
  (leaked log files, a reset timer, LAN discovery scope); the security fixes (notes name their author, http(s)
  only for pictures, rules counted without importing, malformed packets dropped).
- Security verdict: a local tool; the room is bound on every interface without a password by default for
  rooms a human joins (debatable, left as is), everything else is loopback; secrets never reach logs.
- Debatable items were listed for the user rather than changed (the session's final report).
- Publishing (the WindBot fork, the submodule, the public repo) still waits for the user's confirmation.

## Published 2026-10-22
Public at https://github.com/mostwanted7/ygo-agent. `windbot-src` is a submodule pointing at
https://github.com/mostwanted7/windbot (branch `brain-bridge`, a fork of ProjectIgnis/windbot).

## train-compare for Geargia (2026-10-22): training stays
- `train-compare --name geargia --variants trained,none --games 4 --parallel 2` with Opus against WindBot Blue-Eyes,
  stopped by hand after 3 paired games (same seeds, same first player): trained 2-1, no playbook 2-1, each pair
  with the same result (won first, lost second). About $11 in API-price dollars, 15 minutes.
- The win rate can't tell them apart (Blue-Eyes games are decided mostly by who goes first), but the play did:
  in game 1 the trained player found exact lethal on turn 5 (Gear Gigant X searched Gold Gadget before the Normal
  Summon, Gold Gadget brought Geargiarmor, Limiter Removal for 6600 into 4200), where the untrained one spent its
  Normal Summon first and left the opponent on 100 LP; in game 2 the untrained player cleared its own board with
  Limiter Removal and lost two turns earlier. Game 3 was even.
- "Trained" is the playbook as it stands (trainer lessons, the user's Geargia insights, the principle-first
  rewrite); the study draft was left out because it was written for the pre-Gadget list.
- **Decision (user): training stays part of the project.** It is cheap and it works. For firmer numbers later, a
  few pairs against a longer-game deck (Time Thief, Dragunity) say more than more Blue-Eyes games.

## Stage 10: training as the user defined it, the web app, release 0.1.0b1 (2026-10-22) ◐

### What "training" means (the user's definition, agreed)
A **trained deck is a guidebook**: `playbook.md`, the strategy the play model reads on every decision, so it doesn't
spend time on the basics or make basic mistakes. Next to it: `tips.md` (the owner's own advice, verbatim),
`tests/*.json` (regression cases) and, rarely, `rules.py`. No weights, no fine-tuning. The loop:

1. **You give the deck** (`.ydk`).
2. **The bot interviews you.** It reads the deck (the dossier: every card, its script) and asks a few deck-specific
   questions (how the deck wins, the main lines, going first or second, what to avoid, which Extra Deck monsters
   matter), plus "anything else?". Your answers are saved to `<deck>/tips.md`. Skippable.
3. **It writes the guidebook**: the study (one reviewer session) writes `playbook.md` from the dossier and your tips.
   Your tips win over its own reading unless a card script contradicts them; then it follows the script and lists
   the conflict as an open question for you.
4. **It practises**: a few goldfish turns with stacked hands (the lab) and a couple of games against WindBot deck AIs,
   each reviewed, and the guidebook corrected. Defaults are light (6 lab hands, 2 games, 1 round: about $8-10 of
   API-price usage and half an hour with Opus); `--games`, `--max-rounds`, `--lab-hands` go deeper.
5. **You play it**, and type notes about obvious mistakes in the web panel's note box (or `!note` in EDOPro's chat).
6. **`ygo-agent learn --deck NAME`** (or the Learn button): one reviewer session per game with pending notes reads
   the notes, the decision each one follows, the playbook, your tips and the scripts; it fixes the playbook (a
   principle when one is missing or wrong, a Known pitfall for a specific repeatable mistake), saves a regression
   case for the decision, and marks each note learned in that game's `feedback.md` (or says why it disagrees). Tips
   added since the last learn are folded in the same way. Every edit goes through the existing evidence check and
   the case gate. Learn never plays games.

This replaces nothing: CLAUDE.md's manual loop (Claude Code reading the notes) stays for the developer; `learn` is
the same loop for anyone who cloned the repo.

**Seam (in main, written by the orchestrator, with tests in `tests/trainer/test_tips_notes.py`):**
- `ygo_agent/trainer/tips.py`: `read(deck_dir)`, `entries(deck_dir)`, `add(deck_dir, text, title)`,
  `save_answers(deck_dir, [{"question", "answer"}], name)`, `digest(deck_dir)`. Format: `## <question or Tip>
  (date)` sections under a header.
- `ygo_agent/trainer/notes.py`: `Note` (game_dir, game, index, line, context, author, text, decision, turn, mode,
  deck, learned; `.trusted`, `.pending`, `.key`, `.to_dict()`), `read(game_dir)`, `deck_games(deck, games_dir)`,
  `for_deck(...)`, `pending(deck, games_dir, include_untrusted=False)`, `mark(note, outcome)`. A note is learned when
  an indented `  - Learned <date>: …` (or the older `  - Processed …`) line sits under it. Trusted = `from Web panel`,
  or `from Opponent …` in a `play` game; Spectator notes only with `--include-spectators`.
- `<deck>/train/interview.json`: `{"deck", "created", "backend", "questions": [{"id", "question", "why"}]}`. The
  last question is always the fixed "Anything else the agent should know about this deck?".

**CLI (trainer agent):**
- `ygo-agent train <ydk> --name N`: setup → dossier → **interview** (in a terminal: asks each question, Enter
  skips; tips.md saved) → study → lab → games → report. `--tips FILE` uses that text as the tips (no questions);
  `--no-interview` skips it (an existing tips.md is still used); `--interview-only` stops after writing
  `train/interview.json` (prints the path; the web app uses this, then saves the answers itself and runs
  `train --name N --resume --no-interview [options]`). Without a terminal and without those flags the questions are
  written to interview.json and training continues without answers.
- `ygo-agent learn --deck N [--backend opus] [--budget-usd X] [--game DIR] [--include-spectators] [--gate-repeat K]`;
  `learn --deck N --list [--json]` (pending notes and whether tips changed, no model calls); `learn --deck N --tip
  "text"` (append a tip; no model call). Output: `<deck>/train/learn/<time>/` (calls, reply, report) and a line per
  run in `<deck>/train/learn.md`; `state.json` keeps `learn.tips_digest`. Works on any deck folder (repo or user),
  trained or hand-written; it builds the dossier into `train/` if missing. Section edits never touch Known pitfalls
  or the owner's own sections (Saffira's "Coaching lessons").

### The web app (web agent)
`ygo-agent web` becomes the whole app (the terminal commands all stay; the app runs them):
- **Pages** (hash routes, vanilla JS, no build step, nothing from a CDN, same look as the panel): Home (start
  something: duel the agent, watch AI vs AI, watch it teach, get coached; recent games; decks), Decks (list → a deck:
  playbook rendered + edit, tips + add, pending notes with links to the decision, Learn button, train report, its
  games), New deck (train wizard: pick a .ydk from EDOPro's deck folder or a path, name → "Read the deck" =
  `train --interview-only` → the questions as text boxes → Start training with options → progress: trainer.log
  live, the training games live, the report at the end), Games (the existing board/replay viewer), Jobs (running and
  finished commands, their output, Stop), Setup (`doctor --json`, the backend profiles, the config paths).
- **Jobs run the CLI** as subprocesses (`python -m ygo_agent <argv>`, cwd = the repo, stdin closed, own process
  group, output to a log file), argv built server-side from validated parameters only (never free-form argv, never a
  shell). Stop = SIGINT to the group (graceful, like Ctrl+C: the trainer checkpoints), then SIGTERM, then SIGKILL.
  One room-hosting job at a time (play, teach, coach, selfplay --spectate share the room port). The page shows the
  equivalent terminal command for every job.
- **Live games from jobs** reach the app's bus through a **relay**: the job gets `YGO_AGENT_RELAY` (URL) and
  `YGO_AGENT_RELAY_TOKEN`; any command started with them activates its bus with a forwarding sink (batched POSTs,
  dropped silently if the app is gone) instead of serving a panel. The app's `POST /api/relay` (token-checked,
  bigger body limit) injects the already-rendered messages into its bus. Notes on a relayed live game go to that
  game folder's feedback.md (the existing fallback through `seat_info(...)["dir"]`).
- **Safety**: everything stays loopback-only by default (the existing Host/Origin checks); the job, edit and relay
  endpoints also require a loopback client address whatever the bind address. Deck names must resolve through
  `decks.find`; a .ydk path must exist and end in `.ydk`. A panel started by `play/selfplay/teach/coach --web` is
  the old panel (no jobs); only `ygo-agent web` serves the app.

### Release 0.1.0b1 (orchestrator, after both land)
Version `0.1.0b1` (PEP 440) in pyproject and `ygo_agent.__version__` (`ygo-agent --version`), CHANGELOG.md, tag
`v0.1.0-beta.1`, a GitHub pre-release "ygo-agent 0.1.0 beta 1". 1.0 comes after the user has used it for a while and
trained a couple of decks with the new flow.

## Research track (not release work)
Local and open models are the user's own research, run on their desktop (RX 9070) through backend profiles in
`config.local.toml`: no repo change is needed or wanted for that, and none of it gates a release. Notes are kept here
for the user's portfolio: the model exam on local models → hybrid routing (a local model for routine decisions,
escalating hard ones to Opus) → maybe distillation (fine-tune on logged Opus decisions).
