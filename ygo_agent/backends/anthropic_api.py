"""Backend type "anthropic": the Claude Messages API over HTTPS (stdlib urllib, no SDK needed).

- The API key comes from an environment variable (ANTHROPIC_API_KEY unless `api_key_env` says otherwise).
- The system prompt is cached (cache_control), and so is the turn's conversation so far: the breakpoint moves to
  the newest user message, so each decision only pays full price for its own new text.
- Structured output: `output_config.format` with the reply schema (the default, `structured = "json_schema"`), a
  strict `reply` tool (`structured = "tool"`, for gateways without output_config), or prompt-and-parse ("none").
  The current models reject a forced tool_choice, so the tool mode asks for the tool and parses text if it's
  skipped.
- `effort` goes to output_config.effort (low | medium | high | xhigh | max); the 5.5 models think adaptively.
- 429, 5xx and 529 (overloaded) are retried with backoff, honouring retry-after, within the decision timeout.
- The conversation is append-only (thinking blocks are passed back unchanged), as the API requires.
"""

import copy
import json
import os

from .base import Backend, BackendError, ChatSession, HTTPStatusError, cost, post_json

API_URL = "https://api.anthropic.com"
VERSION = "2023-06-01"
MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# USD per million tokens (5-minute cache writes are 1.25x input). Override per profile with `price = {...}`.
PRICES = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 5.0},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20, "cache_write": 2.5},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
}
STRUCTURED = ("json_schema", "tool", "none")
TOOL_NOTE = "\n\nAlways answer each decision by calling the `reply` tool."
FORMAT_NOTE = ('\n\nAnswer each decision with only a JSON object: {"choice": [option indices], "why": "...", '
               '"plan": "..."}.')


def strict_schema(schema):
    """The reply schema as structured outputs want it: additionalProperties false on every object."""
    out = copy.deepcopy(schema)

    def fix(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for value in node.values():
                fix(value)
        elif isinstance(node, list):
            for value in node:
                fix(value)
    fix(out)
    return out


class AnthropicBackend(Backend):
    TYPE = "anthropic"

    @property
    def model_id(self):
        model = self.profile.get("model") or "opus"
        return MODELS.get(model, model)

    @property
    def key_env(self):
        return self.profile.get("api_key_env") or "ANTHROPIC_API_KEY"

    def check(self):
        if not os.environ.get(self.key_env):
            raise BackendError(f"backend {self.name!r} (anthropic) needs an API key in ${self.key_env}.")
        if self.profile.get("structured", "json_schema") not in STRUCTURED:
            raise BackendError(f"backend {self.name!r}: structured must be one of {', '.join(STRUCTURED)}")

    def open_session(self, system_prompt, schema):
        self.check()
        return AnthropicSession(self, system_prompt, schema)


class AnthropicSession(ChatSession):
    def __init__(self, backend, system_prompt, schema):
        p = backend.profile
        self.mode = p.get("structured", "json_schema")
        super().__init__(system_prompt + {"tool": TOOL_NOTE, "none": FORMAT_NOTE}.get(self.mode, ""), schema)
        self.backend = backend
        self.url = (p.get("base_url") or API_URL).rstrip("/") + "/v1/messages"
        self.model = backend.model_id
        self.price = p.get("price") or PRICES.get(self.model)
        self.pending_tool = None  # id of the reply tool call the next user message must answer

    def _headers(self):
        h = {"x-api-key": os.environ.get(self.backend.key_env, ""), "anthropic-version": VERSION}
        betas = self.backend.profile.get("betas")
        if betas:
            h["anthropic-beta"] = ",".join(betas) if isinstance(betas, list) else str(betas)
        return h

    def _user(self, text):
        content = [{"type": "text", "text": text}]
        if self.pending_tool:
            content.insert(0, {"type": "tool_result", "tool_use_id": self.pending_tool, "content": "received"})
            self.pending_tool = None
        self.history.append({"role": "user", "content": content})

    def _assistant_note(self, text):
        self.history.append({"role": "assistant", "content": [{"type": "text", "text": text}]})

    def _body(self):
        p = self.backend.profile
        messages = copy.deepcopy(self.history)
        messages[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}  # cache the conversation so far
        body = {
            "model": self.model,
            "max_tokens": int(p.get("max_tokens", 16000)),
            "system": [{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }
        output_config = {}
        if p.get("effort"):
            output_config["effort"] = p["effort"]
        if self.mode == "json_schema":
            output_config["format"] = {"type": "json_schema", "schema": strict_schema(self.schema)}
        elif self.mode == "tool":
            body["tools"] = [{"name": "reply", "description": "Your answer to the current decision.",
                              "input_schema": strict_schema(self.schema), "strict": True}]
            body["tool_choice"] = {"type": "auto"}
        if output_config:
            body["output_config"] = output_config
        if p.get("temperature") is not None:
            body["temperature"] = p["temperature"]
        if p.get("fallbacks"):
            body["fallbacks"] = p["fallbacks"]
        body.update(p.get("extra_body") or {})
        return body

    def _complete(self, deadline, info):
        try:
            resp = post_json(self.url, self._body(), self._headers(), deadline, info,
                             max_retries=int(self.backend.profile.get("max_retries", 3)))
        except HTTPStatusError as e:
            raise BackendError(f"Anthropic API error {e.status}: {_error_message(e.body)}") from None
        usage = resp.get("usage") or {}
        call = {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens") or 0,
                "cache_write_tokens": usage.get("cache_creation_input_tokens") or 0}
        for k, v in call.items():
            info[k] += v
        c = cost(call, self.price)
        if c is not None:
            info["cost_usd"] = round((info["cost_usd"] or 0) + c, 6)
        content = resp.get("content") or []
        self.history.append({"role": "assistant", "content": content})  # unchanged, thinking blocks included
        if resp.get("stop_reason") == "refusal":
            details = resp.get("stop_details") or {}
            raise BackendError(f"the model declined ({details.get('category') or 'refusal'})")
        for block in content:
            if block.get("type") == "tool_use":
                self.pending_tool = block.get("id")
                if block.get("name") == "reply" and isinstance(block.get("input"), dict):
                    return None, block["input"]
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        return text, None


def _error_message(body):
    try:
        err = json.loads(body).get("error") or {}
        return f"{err.get('type', 'error')}: {err.get('message', '')}"[:300]
    except (ValueError, AttributeError):
        return body[:300]
