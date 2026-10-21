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

1. In EDOPro: **LAN Mode → Host**. Use the banlist you normally use with the deck (or tick *Don't check deck*), and
   set the **time limit as high as it goes**: the AI takes a few seconds per decision.
2. In a terminal: `./play.sh` (the same as `ygo-agent play --join`), then press **Enter** once you're in the room.
3. The bot joins the room. Start the duel.

While you play:
- The terminal shows every decision live: the options, what the AI picked, why, and its plan for the turn.
- The duel chat stays quiet apart from a few jokes per duel (`chat = "off"` in the config silences them).
- Type `!` followed by a note in the duel chat (e.g. `!don't Veiler my Stratos, save it`) to bookmark feedback at
  that exact moment. The bot confirms it with "Noted feedback #1." and the note is saved with the game log.

After the game:
- The log is in `games/latest/` (each game gets `games/<time>_<deck>-vs-<opponent>/`): `game.md` to read,
  `feedback.md` with your notes, `game.jsonl` and `prompts.jsonl` with the raw data, and `windbot.log`.
- Open Claude Code in this folder and tell it what the AI got wrong. It updates the deck's playbook and rules (see
  CLAUDE.md), and the next game uses them.

Options: `--backend sonnet` (faster, a bit weaker; also `haiku`, `api-opus`, `local`, `heuristic`, `random` or
your own profile), `--model`/`--effort` to override the profile's, `--deck blackwing` (any folder under `decks/`),
`--host`/`--port`/`--password` for the room, `--chat off`, `--brain-only` (run only the agent and print the bot
command). `ygo-agent play --help` lists them all. At the end of a game the terminal prints the decision stats
(who decided, latency, invalid replies, tokens, cost), which `meta.json` keeps too.

## Learning a deck (e.g. Blackwings)

- **Watch:** host the room, move yourself to the spectator seat, and use EDOPro's *Add AI* to fill the other seat with
  any WindBot deck. Then run `ygo-agent teach --deck blackwing` (or `./play.sh --deck blackwing --teach`) and start
  the duel. The AI explains every play like a coach, and its full plan for the turn appears in the terminal. As a
  spectator you can't see its hand in EDOPro, but the terminal shows it.
- **Copilot:** the same setup with `ygo-agent copilot --deck blackwing`. For every decision the terminal shows the
  board, the options and the AI's recommendation with its reasoning. Press Enter to follow it or type your own
  choice, so you're the one playing and the AI coaches. Set a long time limit, because your thinking time counts too.
- No one coaches the bot on a deck you don't know yet, so after a game ask Claude Code to *review* it. It checks the
  plays against the card scripts and the engine log and updates the playbook (see CLAUDE.md).

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

and `ygo-agent play --join --backend qwen`. [docs/backends.md](docs/backends.md) covers every backend and key.

The rules stated to the AI come from the room's own settings when the bot joins (Master Rule 3 by default). When
EDOPro updates its network protocol, the bot notices, retries with the new version and remembers it in
`~/.cache/ygo-agent/`.

## How it works

```
EDOPro room ⇄ WindBot fork (windbot-src, C#) ⇄ agent (Python, port 7922) ⇄ backend (default: claude -p, your Claude Code login)
```

- `windbot-src/` is a fork of ProjectIgnis WindBot, branch `brain-bridge`. When started with `Brain=host:port`, its
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
- `ygo-agent replay games/latest 14` re-asks decision #14 with the current playbook and rules, and
  `ygo-agent test` re-runs every saved mistake.

## Tests

- `.venv/bin/python -m pytest`: unit tests (no EDOPro or model needed; the tests that read the EDOPro install skip
  without it). The API backends are tested against local mock servers; `pytest --live` adds one real claude-code
  call (and an Anthropic API call when `ANTHROPIC_API_KEY` is set).
- `tests/run_bridge_test.sh`: checks the C# ⇄ agent ⇄ model plumbing without EDOPro (real model calls, about a minute;
  `--model sonnet` makes it quicker).

## License

AGPL-3.0, like WindBot. See `LICENSE`.
