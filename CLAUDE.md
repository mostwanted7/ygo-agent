# ygo-agent — notes for Claude Code

The user plays EDOPro duels against the agent (`ygo-agent play`: the agent hosts the room; or `play --join`: a
Claude-driven WindBot joins the user's room), watches it play (`selfplay` against itself or a WindBot deck AI,
`teach`), or plays a deck themselves while the agent coaches them (`coach`), then gives feedback here. Their goal is
to have a good opponent to play against, not to review logs, so turn short feedback into precise fixes yourself.
See README.md for the architecture and `docs/plan.md` for where the project is going.

`ygo-agent` below means `.venv/bin/ygo-agent`; `python3 -m ygo_agent` from the repo folder does the same.

## Turning feedback into improvements

1. Read `games/latest/game.md` (or the game the user names). If it exists, also read `games/latest/feedback.md`:
   notes the user typed as `!...` in duel chat (or in the web panel's note box), each tagged with the decision number
   it followed. Every game gets its folder `games/<time>_<deck>-vs-<opponent>/`, whichever command played it. In a
   self-play game each AI seat has its own folder (`games/latest` is seat A's); the run's
   `games/matches/<time>_<a>-vs-<b>/results.json` lists every game with each seat's `log_dir`, and `meta.json`'s
   `match` points back at the run. Both seats' mistakes count: fix the deck the seat played.
   Decisions are numbered (`Decision #N`). `game.jsonl` has the raw state for each one and the reply that was sent,
   `prompts.jsonl` has the exact prompt the model saw and its reply, and `meta.json` says which deck and backend
   played (with the game's stats). The default backend is Claude Code (`claude -p`); `--backend NAME` picks
   another profile from the config (docs/backends.md).
2. For each mistake, find the decision and work out why it happened:
   - Bad strategy or judgment → add a lesson to the **Coaching lessons** section at the top of
     `decks/saffira/playbook.md`. Newest first, dated, and naming the game. State it as a concrete
     instruction ("When X, do Y because Z"). Correct or remove any existing playbook text it contradicts,
     and drop "(untested)" from lines a game has confirmed. Keep the playbook tight: Claude reads all of it on
     every decision. A lesson that holds for every deck (timing rules, general play) goes in
     `playbooks/general.md` instead.
   - The same mistake again after a lesson, or a rule with no judgment in it → add a function to
     `decks/saffira/rules.py` (see `ygo_agent/agent/rules.py` for the Context helpers) and list it in RULES.
   - Claude misread the state or options → the presentation is wrong. Fix `ygo_agent/agent/describe.py`.
   - Wrong card data or engine behaviour → check the card script in `~/Games/ProjectIgnis/script/official/c<id>.lua`.
3. Verify: `ygo-agent replay games/<game> <N>` re-asks decision N with the current playbook/rules (the deck comes
   from the game log; `--deck` overrides it).
   Save important ones as regression cases:
   `ygo-agent replay games/<game> <N> --save <short-name> --expect '[[2]]' --note "..."`
   (`--expect` takes a list of acceptable choices; `'[[]]'` means pass, `--reject` lists the wrong ones).
   `ygo-agent test` runs every case of the deck 3 times (`--deck`, case names, `--repeat N`). Claude isn't
   deterministic, so a case that passes only sometimes needs a stronger playbook line or a rule.
   `.venv/bin/python -m pytest` checks that describe/validate/rules still handle every saved case (no model calls).
4. Tell the user what changed in one or two lines. They'll see it in the next game.

## Decks without a coach (Blackwing)

For `decks/blackwing` the user is learning the deck and can't spot mistakes, so after a game they'll ask you to
*review* it. Be the coach yourself:
- Go through `game.md` turn by turn. Compare the actual line with the playbook's main line, and look for
  `FALLBACK`, "engine rejected" notes, unused resources (searches not taken, Normal Summon unused, Black Feather
  Whirlwind or Shamal triggers skipped), wrong Extra Deck locks, zone clogging, and self-damage taken without
  Black-Winged Dragon on the field.
- Check doubtful rulings in the card script before writing a lesson. Never write a lesson you haven't verified
  against the script or the engine log.
- Promote steps the engine actually allowed from *(unverified)* to verified, and fix steps that failed.
- In coach games (`meta.json` `mode: "coach"`, docs/coach.md) every move is the user's own, not Claude's: game.md
  tags each decision `human` (✅ marks the move they played) and puts the coach's advice under it as a `🎓 Coach`
  line; in `game.jsonl` the replies have `"source": "human"` with `advised`/`matched`, and the coach's advice is in
  `advice` rows. `review.md` is the coach's own review of the game. A mistake in the *advice* (or the review) is
  fixed like any other (playbook, rules, describe.py); the user's own mistakes are theirs to learn from, so you can
  point out where their choice cost them. Old copilot logs mark the user's moves with "The pilot chose …" and
  `"source": "pilot"` (with the `suggested` choice).

## Code map

- `ygo_agent/cli.py`: the `ygo-agent` command (`play`, `selfplay`, `teach`, `coach`, `play --join`, `teach --join`,
  `replay`, `test`, `web`, plus `bench` and `train`). `ygo_agent/match.py`: seat specs and `run_games()`, which every arena-hosted
  command runs on (in-process AI vs AI, or an arena room for WindBot/human/spectators; results, replays, the web
  panel). `ygo_agent/join.py`: launches the bot into the user's room (`--join`). `ygo_agent/config.py`:
  `config/default.toml`, then `config.local.toml`, then CLI flags.
- `ygo_agent/arena/`: the headless EDOPro host on libocgcore (`server.py` rooms, `duel.py`, `native_seat.py`: the
  agent as an in-process seat, `windbot.py`: WindBot deck AIs as opponents); `python -m ygo_agent.arena` for the
  low-level tools.
- `ygo_agent/agent/brain.py`: one game (events → history, decisions → rules → model → validation → reply).
  `bridge_server.py`: the TCP server; one `Match` per bot connection, a fresh `DuelBrain` and log for each game.
- `ygo_agent/agent/prompts.py`: the system prompt (mode, rules in force, `playbooks/general.md`, deck, playbook).
- `ygo_agent/agent/describe.py`: all text Claude sees (state, options, events). `carddb.py`: EDOPro cdb + strings.
- `ygo_agent/backends/`: decision backends, one session per game turn (docs/backends.md): `claude_code.py`
  (persistent `claude -p` stream-json session, no API key), `anthropic_api.py`, `openai_compat.py` (Ollama, vLLM,
  llama.cpp, LM Studio, OpenRouter), `heuristic.py`, `random_.py`, `scripted.py` (tests); `parse.py` reads sloppy
  model output. `ygo_agent/agent/stats.py`: the per-game stats in `meta.json`.
- `docs/decision-protocol.md`: the bot ⇄ agent message schema. Keep it in sync with any change to either side.
- `ygo_agent/web/`: the browser panel (`--web`, `ygo-agent web [--demo games/<dir>]`). `GameLog` publishes everything
  it logs to `web/bus.py` (a no-op unless a panel runs); `server.py` serves it over SSE; `recorded.py` turns a game
  folder into the same messages. Notes typed in the panel land in `feedback.md` like `!notes`. Schema: `docs/web.md`.
- `ygo_agent/coach/`: `ygo-agent coach` (docs/coach.md): `live.py` watches the human's seat through a SeatWatcher
  and advises without ever blocking the duel, `brain.py` is the coach's DuelBrain (prompt mode `coach`), `review.py`
  writes review.md after the game (`coach --review games/<dir>` again), `detect.py` recognises the human's deck.
- `ygo_agent/trainer/`: `ygo-agent train` (docs/training.md): dossier → study → lab (goldfish turns with stacked
  hands) → games → reviews, checkpointed in `decks/<name>/train/state.json`. A trained deck's `train/` folder has the
  scripts, logs and reviewer calls behind every lesson in its playbook.
- `windbot-src/`: WindBot fork, its own git repo, branch `brain-bridge` (`ExecutorBase/Game/BrainBridge.cs`, the
  `Brain` hooks in `ExecutorBase/Game/GameAI.cs` and `Game/GameBehavior.cs`, `Game/AI/Decks/AgentExecutor.cs`).
  Run `./build.sh` after editing C#, then `tests/run_bridge_test.sh` (real Claude calls, ~1 minute).
- `decks/<deck>/deck.ydk` is a copy of the deck list. This machine's `config.local.toml` points Saffira and Blackwing
  at the user's own `~/Games/ProjectIgnis/deck/*.ydk`, so edits they make in EDOPro carry over. Don't change those
  files without asking.

## Gotchas

- Don't use `pkill -f`/`pgrep -f` with a pattern that also appears in your own command line: it kills the
  shell running it. Use PIDs, as `tests/run_bridge_test.sh` does.
- Decision ids restart at 1 for each game, including each game of a Bo3 (they share one bot connection).
- `ygo-agent replay` works on arena games too (native seats send the same decision JSON). For a deck played from a
  loose `.ydk`, `meta.json` has `deck_ydk` and replay finds it there.
