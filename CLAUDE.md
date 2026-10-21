# ygo-agent — notes for Claude Code

The user plays EDOPro duels against a Claude-driven WindBot, then gives feedback here. Their goal is to have
a good opponent to play against, not to review logs, so turn short feedback into precise fixes yourself.
See README.md for the architecture and `docs/plan.md` for where the project is going.

`ygo-agent` below means `.venv/bin/ygo-agent`; `python3 -m ygo_agent` from the repo folder does the same.

## Turning feedback into improvements

1. Read `games/latest/game.md` (or the game the user names). If it exists, also read `games/latest/feedback.md`:
   notes the user typed as `!...` in duel chat, each tagged with the decision number it followed.
   Decisions are numbered (`Decision #N`). `game.jsonl` has the raw state for each one and the reply that was sent,
   `prompts.jsonl` has the exact prompt Claude saw and its reply, and `meta.json` says which deck and model played.
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
- In copilot games, "The pilot chose …" notes mark the user's own decisions, not Claude's (✅ marks the move actually
  played; the reply in `game.jsonl` has `"source": "pilot"` and the `suggested` choice). You can point out where
  their choice cost them, since they're there to learn.

## Code map

- `ygo_agent/cli.py`: the `ygo-agent` command (`play --join`, `teach`, `copilot`, `replay`, `test`).
  `ygo_agent/join.py`: launches the bot into the user's room. `ygo_agent/config.py`: `config/default.toml`, then
  `config.local.toml`, then CLI flags.
- `ygo_agent/agent/brain.py`: one game (events → history, decisions → rules → model → validation → reply).
  `bridge_server.py`: the TCP server; one `Match` per bot connection, a fresh `DuelBrain` and log for each game.
- `ygo_agent/agent/prompts.py`: the system prompt (mode, rules in force, `playbooks/general.md`, deck, playbook).
- `ygo_agent/agent/describe.py`: all text Claude sees (state, options, events). `carddb.py`: EDOPro cdb + strings.
- `ygo_agent/backends/claude_code.py`: persistent `claude -p` stream-json session, one per game turn. No API key.
- `docs/decision-protocol.md`: the bot ⇄ agent message schema. Keep it in sync with any change to either side.
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
