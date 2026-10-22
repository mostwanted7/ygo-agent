# Adding a backend

A backend makes the decisions the deck rules leave open. Most of the time you don't need code: a new profile of an
existing type covers any Claude model, the Anthropic API and every OpenAI-compatible server. A new *type* is a
small Python class.

## A profile of an existing type

Profiles are `[backends.NAME]` tables; `config/default.toml` defines `opus`, `sonnet`, `haiku` (type `claude-code`),
`api-opus` (`anthropic`), `local` (`openai`, pointed at Ollama), `heuristic` and `random`. Add yours to
`config.local.toml`, for example a local model through Ollama:

```toml
[backends.qwen]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
num_ctx = 32768             # Ollama's context size (also set it on the server: OLLAMA_CONTEXT_LENGTH=32768)
json_mode = "auto"          # schema, then json, then none: whatever the server accepts
card_texts = "compact"      # a smaller prompt for a small context
history_lines = 150
max_session_messages = 20
price = { input = 0, output = 0 }   # local = free; a hosted model's USD per million tokens
```

Then `ygo-agent play --backend qwen`, or any other command with `--backend qwen`. [backends.md](backends.md) lists
every key of every type, with ready-made profiles for vLLM, llama.cpp, LM Studio and OpenRouter, and explains the
prompt-budget keys (`card_texts`, `history_lines`, `max_session_messages`), which any profile may set.

Try it before a game: `ygo-agent test --backend qwen --repeat 1` replays the deck's saved regression cases through
it and shows each reply, and `ygo-agent selfplay --a saffira:qwen --b heuristic --quiet` plays a whole game in a
minute or two. Watch the invalid-reply and fallback counts at the end: a model that can't follow the reply format
ends up playing the heuristic's game.

## A new type

### The interface

`ygo_agent/backends/base.py` defines it. A `Backend` is created once per seat from its profile and opens one
session per game turn; a `Session` answers one decision at a time:

```python
backend = backends.create(profile, db=card_db)          # profile: {"name": ..., "type": ..., ...}
session = backend.open_session(system_prompt, schema)   # once per game turn
reply, info = session.ask(Request(text, decision, schema, timeout))
session.close()
```

- `Backend(profile, db)`: set `TYPE` (the `type` key a profile uses) and implement `open_session(system_prompt,
  schema)`. Optionally `check()`, which raises `BackendError` when the profile can't run here (a missing executable
  or key), so a command fails before the room opens; and `describe()`, the one-line summary the terminal prints.
  `name`, `model` and `label` (how the backend's decisions are tagged in the terminal, `game.md` and `meta.json`)
  come from the base class.
- `Session.ask(request)` returns `(reply, info)`. `request` is a `Request`: `text`, the full message an LLM sees
  (history, card texts, the state, the question and options); `decision`, the raw decision dict
  ([decision-protocol.md](decision-protocol.md)) for backends that don't read text; `schema`, the reply's JSON
  schema; `timeout`, seconds for this ask, retries included; and `error`, set on the agent's corrective re-ask with
  the reason the previous reply was rejected. The reply is `{"choice": [int, ...], "why": str, "plan": str | None}`,
  or `None` when there is no usable answer (the agent then falls back).
- **Keep the conversation per session.** The agent opens one session per game turn, and its re-ask ("That reply is
  invalid: ...") is just the next `ask()` on the same session; it rolls the session over after
  `max_session_messages` decisions, carrying the plan into the new one. Set `self.alive = False` when the session
  can't continue, and count asks in `self.messages`.
- **Usage reporting.** `info` starts as `new_info()` and must keep its fields: `seconds`, `input_tokens`,
  `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd` (`None` when unknown), `retries`,
  `replies` (model outputs received), `invalid` (outputs that couldn't be read) and `error`. The game's stats, the
  benchmark's tables and `prompts.jsonl` are built from these, so their meaning is fixed (backends.md, "Stats").
  `cost(usage, price)` computes a cost from the profile's `price` table.
- **Reading replies.** `parse.parse_reply(text)` recovers the reply dict from whatever a model wrote (code fences,
  prose, `<think>` blocks, trailing commas, a bare number) and `parse.normalize(dict)` turns a loosely shaped dict
  into the exact reply shape; both raise `ParseError`. Put the schema's `why` before `choice` if the model writes
  fields in schema order, so it reasons before it picks.
- **HTTP chat APIs** can subclass `ChatSession` instead of `Session`: it runs the conversation loop, the repair
  retry when a reply can't be read, the timing and the error handling, and leaves three methods to implement:
  `_user(text)` and `_assistant_note(text)` append to the history, and `_complete(deadline, info)` makes one model
  call and returns `(raw_text, parsed_dict_or_None)`. `post_json(url, body, headers, deadline, info)` does the POST
  with retries on 429/5xx/overloaded and connection errors, inside the deadline, without ever logging headers.
  `ygo_agent/backends/openai_compat.py` is the model to copy.
- **The prompt-shrinking keys** `card_texts`, `history_lines` and `max_session_messages` are read by the agent, not
  the backend: a profile that sets them gets a smaller prompt without any code. `estimate_tokens(text)` gives a
  rough count for a context budget.
- **Non-LLM backends** decide from `request.decision`; `heuristic.py` and `random_.py` wrap a policy object with
  `choose(decision)` in a `PolicySession`. A policy must return a legal reply for every decision kind, `place`
  included. The agent builds its fallback policies the same way (`backends.create({"type": ...}).policy`), so a
  type that should serve as `agent.fallback` must expose `.policy`.

### Registering the type

`TYPES` in `ygo_agent/backends/__init__.py` maps a type name to `(module, class)`; the module is imported only when
a profile uses the type, so an optional SDK can be imported lazily inside it with a clear error when missing. Add a
line there, a commented profile to `config/default.toml`, and a section to [backends.md](backends.md). `config.
backend()` then accepts the type in any `[backends.NAME]` table, and `meta.json` records the profile's non-secret
keys (the list is `META_KEYS` in `ygo_agent/agent/brain.py`; extend it for keys worth keeping in the logs; API keys
are never written).

### Testing it

- `tests/test_backends_http.py` tests the anthropic and openai types against `tests/mockhttp.py`, a local HTTP
  server with scripted responses: request shapes, structured-output modes, retries and backoff, sloppy JSON, the
  repair ask, timeouts, usage and cost. Add the same for a new HTTP type. `tests/fake_openai_server.py` is a
  standalone fake model that answers from the prompt text; `tests/test_live.py` runs saved games through it.
- `tests/test_policies.py` checks that `heuristic` and `random` return a legal reply for every saved decision; a
  new non-LLM type belongs there.
- `ygo-agent test --backend NAME --repeat 1` replays the deck's regression cases through the real thing;
  `pytest --live` (or `YGO_AGENT_LIVE=1`) runs the tests that make real model calls.
- `python -m pytest tests/test_backends_http.py tests/test_parse.py tests/test_budget.py` is the quick loop while
  you work.

### Benchmarking it

```sh
ygo-agent bench --name NAME --decks saffira,blackwing --backends NAME,haiku,heuristic \
    --opponents "windbot:Blue-Eyes,windbot:Time Thief" --games 6 --parallel 1
```

Every backend plays the same seeds, so the report compares your type with a reference model and the no-LLM baseline
on the same deals; `--parallel 1` suits one local GPU. `ygo-agent bench exam --backends NAME,opus` grades it on the
same logged decisions as the Claude models, judged blind. See [bench.md](bench.md).
