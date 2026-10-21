# Backends

A **backend** makes the decisions the deck rules leave open. Every seat chooses its own backend profile: a
`[backends.NAME]` table in the config with a `type`. Pick one with `--backend NAME`; `--model` and `--effort`
override that profile's model and effort for the run.

```sh
ygo-agent play --join --backend sonnet         # Claude Code CLI, Sonnet
ygo-agent test --backend local                 # a local model through Ollama
ygo-agent test set-lance-before-ending --backend heuristic --repeat 1
```

| type | what it is | needs |
|---|---|---|
| `claude-code` | the `claude -p` CLI, your Claude Code login | `claude` on PATH |
| `anthropic` | the Claude Messages API | an API key |
| `openai` | any OpenAI-compatible `/v1/chat/completions` server | a server (and a key for hosted ones) |
| `heuristic` | a rule-based player, no model | nothing |
| `random` | uniformly random legal moves | nothing |
| `scripted` | canned replies (tests only) | nothing |

`config/default.toml` defines `opus`, `sonnet`, `haiku` (claude-code), `api-opus` (anthropic), `local` (openai,
Ollama), `heuristic` and `random`, with every key commented. Add your own profiles in `config.local.toml`.

## claude-code

```toml
[backends.opus]
type = "claude-code"
model = "opus"      # any name or alias the CLI accepts
effort = "medium"   # low | medium | high | xhigh | max; "" = the CLI default
```

One `claude -p --input-format stream-json` process per game turn, started as soon as the turn begins
(pre-warming), with no tools, settings, MCP servers or slash commands, in an empty working directory. The system
prompt goes in a temporary file (`--system-prompt-file`), the reply schema through `--json-schema`. Usage comes from
the CLI's `result` events; `cost_usd` is the CLI's API-price figure, which a subscription login isn't billed.

## anthropic

```toml
[backends.api-opus]
type = "anthropic"
model = "opus"                    # opus | sonnet | haiku → claude-opus-5-5 / claude-sonnet-5-5 / claude-haiku-5-5
effort = "medium"                 # output_config.effort
api_key_env = "ANTHROPIC_API_KEY" # never logged
max_tokens = 16000                # thinking included
structured = "json_schema"        # json_schema | tool | none
# base_url, max_retries = 3, price = {...}, betas = [...], temperature, extra_body = {...}
```

Plain HTTPS with the standard library (`POST /v1/messages`, `anthropic-version: 2023-06-01`).

- **Caching**: the system prompt carries a `cache_control` breakpoint, and so does the newest user message, so
  each decision of a turn reads the turn so far from the cache.
- **Structured output**: `json_schema` sends `output_config.format` with the reply schema (objects get
  `additionalProperties: false`). `tool` offers a strict `reply` tool instead, for gateways without
  `output_config`. The 5.5 models reject a forced `tool_choice`, so this mode uses `auto` plus a system-prompt
  instruction and parses the text when the tool is skipped. `none` asks for JSON in the prompt and parses it.
- **Thinking**: the 5.5 models think adaptively; `effort` is the control. The conversation is append-only and the
  assistant's content, thinking blocks included, is sent back unchanged.
- **Retries**: 408, 409, 429, 5xx and 529 (overloaded), up to `max_retries`, with jittered exponential backoff or
  the server's `retry-after`, all inside the decision timeout. A refusal (`stop_reason: "refusal"`) counts as no
  answer.
- **Cost**: from the built-in price table (USD per million tokens; 5-minute cache writes at 1.25x input), or the
  profile's `price = { input, output, cache_read, cache_write }`.

## openai (OpenAI-compatible servers)

```toml
[backends.local]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
api_key_env = ""          # name of the env var holding the key; empty = no key
json_mode = "auto"        # schema | json | none | auto
temperature = 0.2
max_tokens = 4096
num_ctx = 32768           # Ollama only, see below
headers = {}              # extra HTTP headers (OpenRouter's HTTP-Referer / X-Title)
extra_body = {}           # merged into every request body
price = { input = 0, output = 0 }
card_texts = "compact"    # prompt budget, see below
history_lines = 150
max_session_messages = 20
```

### Structured output modes

| `json_mode` | request | what the server must support |
|---|---|---|
| `schema` | `response_format: {"type": "json_schema", "json_schema": {"name", "strict": true, "schema"}}` | constrained decoding to the reply schema |
| `json` | `response_format: {"type": "json_object"}` | JSON mode |
| `none` | no `response_format` | nothing |
| `auto` (default) | `schema` first; when the server rejects a mode, the next one down | nothing |

In `auto`, a rejected `response_format` (an HTTP 400/404/415/422/5xx before any mode has worked) steps down to
the next mode and retries at once. The mode that works is remembered for the rest of the run, and from then on an
error is never blamed on the format. The schema sent to servers lists `why` first, so models that write fields in
schema order reason before they choose. Every property is required (`plan` may be `""`), which satisfies OpenAI's
strict mode.

Whatever the mode, the reply goes through a tolerant parser (`ygo_agent/backends/parse.py`). It handles code
fences, prose before or after the JSON, `<think>…</think>` blocks (also unclosed ones, or a missing opening tag),
trailing commas, comments, single quotes, bare keys, Python literals, a cut-off object, a bare number or list
(`2`, `[0, 3]`, `Choice: 1`), `"choice": 2` or `"2"`, and aliases such as `answer`/`reason`. When nothing can be
read, the session asks once more ("Your last reply could not be read…") before giving up. Reasoning text is left
out of the stored history, so it doesn't fill a small context. If `content` is empty, `reasoning_content` /
`reasoning` is parsed instead.

### Servers

**Ollama**

```sh
OLLAMA_CONTEXT_LENGTH=32768 ollama serve      # Ollama's default context is small and truncates silently
ollama pull qwen3:14b
```
```toml
[backends.local]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
num_ctx = 32768
```
`num_ctx` is sent as `options.num_ctx`, Ollama's native option. Ollama's OpenAI endpoint documents no way to set the
context size, so set it on the server too (`OLLAMA_CONTEXT_LENGTH`, or a Modelfile with `PARAMETER num_ctx 32768`
and `ollama create`).

**vLLM**

```sh
vllm serve Qwen/Qwen2.5-14B-Instruct --max-model-len 32768
```
```toml
[backends.vllm]
type = "openai"
base_url = "http://localhost:8000/v1"
model = "Qwen/Qwen2.5-14B-Instruct"
json_mode = "schema"      # guided decoding
```

**llama.cpp `llama-server`**

```sh
llama-server -m qwen2.5-14b-instruct-q4_k_m.gguf -c 32768 --port 8080 --jinja
```
```toml
[backends.llamacpp]
type = "openai"
base_url = "http://localhost:8080/v1"
model = "local"           # llama-server serves the one model it loaded
json_mode = "auto"        # json_schema is grammar-constrained on recent builds; older ones step down
```

**LM Studio** (Developer tab → Start Server)

```toml
[backends.lmstudio]
type = "openai"
base_url = "http://localhost:1234/v1"
model = "qwen2.5-14b-instruct"
json_mode = "auto"        # LM Studio takes json_schema but not json_object; auto copes either way
```

**OpenRouter**

```toml
[backends.openrouter]
type = "openai"
base_url = "https://openrouter.ai/api/v1"
model = "qwen/qwen-2.5-72b-instruct"
api_key_env = "OPENROUTER_API_KEY"
headers = { "HTTP-Referer" = "https://github.com/mostwanted7/ygo-agent", "X-Title" = "ygo-agent" }
extra_body = { usage = { include = true } }   # OpenRouter then reports usage.cost, recorded as cost_usd
json_mode = "auto"
```

`usage.prompt_tokens_details.cached_tokens` becomes `cache_read_tokens`, and `usage.cost` (OpenRouter) becomes
`cost_usd`. Otherwise the cost comes from `price` if the profile sets one; without it the cost is unknown (`null`).

## heuristic and random

```toml
[backends.heuristic]
type = "heuristic"

[backends.random]
type = "random"
seed = 1        # optional: reproducible runs
```

Both decide from the raw decision (`docs/decision-protocol.md`), not from the prompt, and always return a legal
reply for every decision kind, `place` included. The tests check this on every saved decision. The heuristic:

- **Main Phase**: uses card effects and non-Quick-Play spells, Special Summons by procedure, and Normal Summons the
  strongest monster (it Sets one instead when the opponent has something stronger). It switches positions for an
  attack, goes to battle when an attack wins, and Sets traps and Quick-Plays before ending the turn. The same
  action is never chosen more than twice a turn, which guards against loops.
- **Battle**: attacks directly, or into monsters it beats. It never attacks into a stronger known monster.
- **Chain windows**: it uses hand traps, traps and Quick-Plays only on the opponent's plays (their chain link, their
  summon, their attack), and uses its own triggered effects during its own turn. Otherwise it passes.
- **Targets**: the opponent's strongest card for removal, its own weakest for costs and materials, its own best for
  searches and summons. A `select_sum` gets the cheapest set that reaches the sum.
- **Questions**: yes to optional effects, no to "continue choosing materials?".

`Policy(db).choose(decision)` in `ygo_agent/backends/heuristic.py` is the same logic without a session.

## Fallback

`agent.fallback` decides who answers when the backend can't: a timeout, an error, no legal reply after the
corrective re-ask, or a prompt the agent leaves alone (zone placement, `announce_card` with more than 150 names).

- `"bot"` (default): `choice: null`, and WindBot's built-in AI answers.
- `"heuristic"`: the heuristic policy answers. After an engine `retry`, a random legal answer is sent instead, so
  the rejected answer isn't repeated. Native arena seats use this mode.

Either way, the prompts the agent leaves alone on purpose (zone placement, a card-name list over 150) count as
`auto` in the stats, not as fallbacks.

## Prompt budget (small-context models)

Each profile may set these keys; otherwise `[agent]` applies.

| key | default | effect |
|---|---|---|
| `history_lines` | 500 | duel-log lines replayed in a new session's first message (0 = none) |
| `card_texts` | `"full"` | `full`: complete card texts. `compact`: one line each, no "unofficial text" notes, short once-per-turn clauses, and effects cut at a sentence boundary near 160 characters for cards the playbook names (it explains them) and 300 for the rest. `none`: no card-text section; the decklist carries each card's type/stats line, and cards seen during the game get only that line |
| `max_session_messages` | 40 (`agent.max_messages_per_session`) | decisions per session before a fresh one starts (a new session also starts every turn) |

System prompt size, play mode (characters; tokens measured with Claude's tokenizer on haiku through the CLI, which
counts about 2.4 characters per token here; `estimate_tokens()` uses that ratio):

| deck | full | compact | none |
|---|---|---|---|
| Saffira | 24.7k chars, 10.2k tokens | 19.7k chars, 8.4k tokens (-18%) | 13.7k chars, 6.1k tokens (-40%) |
| Blackwing | 33.6k chars, 13.9k tokens | 26.7k chars, 11.5k tokens (-18%) | 18.2k chars, 8.0k tokens (-42%) |

The playbook stays whole in every mode, because it holds what the AI has learned about the deck (9k and 13k
characters). On top of that, each session's first message (the duel log, plus the carry-over) is typically 7k
characters, and every later decision about 1.8k characters plus the reply.

### Plan carry-over

When a session ends mid-turn (message limit, crash, timeout), the next session's first message carries the last
`plan` the backend gave this turn and a list of this turn's decisions (what was chosen, by whom, and why), so the
backend keeps its line. `stats.rollovers` counts these sessions.

## Stats

At the end of a game the terminal prints a summary, and `meta.json` gets `"stats"`. The benchmark aggregates
these, so the names are stable:

| field | meaning |
|---|---|
| `decisions` | decisions answered (not counting the `game_over` round trip) |
| `by_source` | `{backend, rule, auto, fallback, human}`: who made each decision (`auto` covers built-in rules such as single options, zone placements and planned multi-picks; `human` is the coached human's own move in a coach game; logs from before Stage 5 have `pilot`, the old copilot's human) |
| `asks` | `session.ask()` calls, the corrective re-asks included |
| `replies` | model outputs received (a session's own repair retry is a second one) |
| `invalid_replies` | outputs that couldn't be read, or named an illegal choice |
| `invalid_rate` | `invalid_replies / replies` (`null` without replies) |
| `errors` | asks that got no output at all (timeout, HTTP error, crashed session) |
| `fallback_rate` | `by_source.fallback / decisions` |
| `latency_mean_s`, `latency_p95_s` | seconds the backend spent per decision it was asked (all its asks together) |
| `tokens` | `{input, output, cache_read, cache_write}`; `input` excludes cached tokens |
| `cost_usd` | summed cost, `null` when unknown |
| `sessions`, `rollovers` | sessions opened, and how many of them started mid-turn |

`meta.json` also has `"backend"`: the profile's non-secret settings (`name`, `type`, `model`, `effort`, `base_url`,
`json_mode`, the budget keys, ...) plus `label`, e.g. `"opus (claude-code)"`, which the terminal and `game.md` use
to tag decisions, and `fallback`.

Each ask's `info` is written to `prompts.jsonl` and always has `seconds`, `input_tokens`, `output_tokens`,
`cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `retries` (HTTP retries, format step-downs and repair asks),
`replies`, `invalid` and `error`. It may also have `json_mode` (openai) and `notes`.

## Adding a backend

1. Subclass `Backend` (`ygo_agent/backends/base.py`), set `TYPE`, and implement `open_session(system_prompt,
   schema)` and, optionally, `check()` (raise `BackendError` when it can't run here) and `describe()`.
2. The session (a `Session` subclass) implements `ask(request) → (reply | None, info)`, with `info = new_info()`
   filled in, and `close()`. `request` is a `Request`: `text` (the full message an LLM sees), `decision` (the raw
   decision dict), `schema`, `timeout` (seconds, retries included) and `error` (set on the agent's corrective
   re-ask). The reply is `{"choice": [int...], "why": str, "plan": str | None}`; `parse.normalize()` makes one
   from a loose dict, and `parse.parse_reply()` from raw text. Keep the conversation per session: the agent opens
   one per game turn, and its "That reply is invalid" re-ask is the next `ask()`.
3. For a chat-style HTTP API, subclass `ChatSession`, which does the repair retry, timing and error handling, and
   use `post_json()` for retries and backoff.
4. Register the type in `TYPES` in `ygo_agent/backends/__init__.py`, document its keys in `config/default.toml`
   and here, and test it against a mock server (`tests/mockhttp.py`, `tests/test_backends_http.py`).

## Tests

- `tests/test_backends_http.py`: anthropic and openai against local mock servers (request shapes, tool mode, format
  step-down, sloppy JSON, repair, timeouts, 429/529 retries, usage and cost).
- `tests/test_parse.py`: the parser on a corpus of bad model output.
- `tests/test_policies.py`: heuristic and random are legal on every saved decision, and the heuristic's choices
  on hand-made boards.
- `tests/test_budget.py`: card-text modes, history and session limits, carry-over, stats, the heuristic fallback.
- `tests/test_claude_code.py`: the claude-code session against a fake `claude` executable.
- `tests/test_live.py` (`pytest --live` or `YGO_AGENT_LIVE=1`): one real claude-code call (haiku), and one real
  Anthropic API call if `ANTHROPIC_API_KEY` is set.
- `tests/fake_openai_server.py`: a standalone fake OpenAI-compatible model that answers from the prompt text, with
  sloppy formatting on purpose. Use it to run the bridge test or `ygo-agent test` through the openai backend
  without a GPU.
