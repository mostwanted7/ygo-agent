"""Backend type "openai": any OpenAI-compatible /v1/chat/completions server (Ollama, vLLM, llama.cpp's
llama-server, LM Studio, OpenRouter, OpenAI itself).

Structured output (`json_mode`):
  "schema"  response_format {"type": "json_schema", ...}: the server constrains the output to the reply schema
  "json"    response_format {"type": "json_object"}: any JSON object
  "none"    no response_format; the prompt asks for JSON
  "auto"    (default) start with "schema" and step down when the server rejects a mode; the working mode is
            remembered for the rest of the run
Whatever the mode, the reply goes through the tolerant parser (code fences, prose, <think> blocks, trailing commas,
bare numbers), with one repair retry when it still can't be read.
"""

import copy
import json
import os
import threading

from .base import Backend, BackendError, ChatSession, HTTPStatusError, cost, post_json
from .parse import strip_reasoning

MODES = ("schema", "json", "none")
JSON_MODES = MODES + ("auto",)
# Words in an error body that mean "this server doesn't do that response_format".
FORMAT_WORDS = ("response_format", "json_schema", "json_object", "schema", "grammar", "format", "unsupported",
                "not supported", "extra inputs", "unrecognized")

FORMAT_NOTE = """

# Reply format
Reply with a single JSON object and nothing else, for example:
{"why": "Normal Summon Kris to enable Bora's Special Summon.", "choice": [2], "plan": ""}
- why: 1-3 short sentences.
- choice: the option indices, in the format the decision asks for ([] to pass, where passing is allowed).
- plan: your plan for the rest of the turn, or "" if it hasn't changed."""

_learned = {}  # (base_url, model) -> the json_mode that worked, shared by every session of this run
_learned_lock = threading.Lock()


def reply_schema(schema):
    """The schema as strict json_schema servers want it: every property required, no extra ones, and "why" first,
    so models that write fields in schema order reason before they choose."""
    props = copy.deepcopy(schema.get("properties", {}))
    order = ["why"] + [k for k in props if k != "why"]
    props = {k: props[k] for k in order if k in props}
    if "plan" in props:
        props["plan"] = {"type": "string", "description": "Your plan for the rest of this turn, or \"\"."}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


class OpenAIBackend(Backend):
    TYPE = "openai"

    @property
    def base_url(self):
        return (self.profile.get("base_url") or "http://localhost:11434/v1").rstrip("/")

    def check(self):
        if not self.profile.get("model"):
            raise BackendError(f"backend {self.name!r} (openai) needs a `model`.")
        if self.profile.get("json_mode", "auto") not in JSON_MODES:
            raise BackendError(f"backend {self.name!r}: json_mode must be one of {', '.join(JSON_MODES)}")
        env = self.profile.get("api_key_env")
        if env and not os.environ.get(env):
            raise BackendError(f"backend {self.name!r} (openai) needs an API key in ${env}.")

    def open_session(self, system_prompt, schema):
        self.check()
        return OpenAISession(self, system_prompt, schema)

    def mode(self):
        """(json_mode to use, whether it may still step down)."""
        wanted = self.profile.get("json_mode", "auto")
        if wanted != "auto":
            return wanted, False
        with _learned_lock:
            learned = _learned.get((self.base_url, self.model))
        return learned or "schema", learned is None

    def learn(self, mode):
        with _learned_lock:
            _learned[(self.base_url, self.model)] = mode


class OpenAISession(ChatSession):
    def __init__(self, backend, system_prompt, schema):
        super().__init__(system_prompt + FORMAT_NOTE, schema)
        self.backend = backend
        self.url = backend.base_url + "/chat/completions"

    def _headers(self):
        p = self.backend.profile
        h = dict(p.get("headers") or {})
        env = p.get("api_key_env")
        if env and os.environ.get(env):
            h["authorization"] = f"Bearer {os.environ[env]}"
        return h

    def _user(self, text):
        self.history.append({"role": "user", "content": text})

    def _assistant_note(self, text):
        self.history.append({"role": "assistant", "content": text})

    def _body(self, mode):
        p = self.backend.profile
        body = {"model": p["model"], "messages": [{"role": "system", "content": self.system_prompt}] + self.history}
        if p.get("max_tokens"):
            body["max_tokens"] = int(p["max_tokens"])
        if p.get("temperature") is not None:
            body["temperature"] = p["temperature"]
        if mode == "schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "decision_reply", "strict": True, "schema": reply_schema(self.schema)}}
        elif mode == "json":
            body["response_format"] = {"type": "json_object"}
        if p.get("num_ctx"):
            # Ollama's native option; its /v1 endpoint may ignore it (then set OLLAMA_CONTEXT_LENGTH or a Modelfile).
            body["options"] = {"num_ctx": int(p["num_ctx"])}
        body.update(copy.deepcopy(p.get("extra_body") or {}))
        return body

    def _complete(self, deadline, info):
        mode, auto = self.backend.mode()  # once a mode has worked, errors are never blamed on response_format
        retries = int(self.backend.profile.get("max_retries", 3))
        while True:
            try:
                resp = post_json(self.url, self._body(mode), self._headers(), deadline, info, max_retries=retries)
                if isinstance(resp, dict) and resp.get("error") and not resp.get("choices"):
                    raise HTTPStatusError(200, json.dumps(resp["error"]))
            except HTTPStatusError as e:
                if auto and mode != "none" and self._format_rejected(e):
                    mode = MODES[MODES.index(mode) + 1]
                    info["retries"] += 1
                    info.setdefault("notes", []).append(f"server rejected response_format; using json_mode={mode}")
                    continue
                raise BackendError(f"{self.backend.base_url} error {e.status}: {e.body[:300]}") from None
            break
        if auto:
            self.backend.learn(mode)
        info["json_mode"] = mode
        self._usage(resp.get("usage") or {}, info)
        choices = resp.get("choices") or []
        if not choices:
            raise BackendError("the server returned no choices")
        msg = choices[0].get("message") or {}
        text = msg.get("content")
        if isinstance(text, list):  # content parts
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        text = text or ""
        if not text.strip():
            # Some reasoning servers put everything in a separate field when the answer budget runs out.
            text = msg.get("reasoning_content") or msg.get("reasoning") or ""
        # History keeps the answer, not the reasoning: re-sending chains of thought wastes a small context.
        self.history.append({"role": "assistant", "content": strip_reasoning(text).strip() or text})
        if choices[0].get("finish_reason") == "length":
            info.setdefault("notes", []).append("the reply hit max_tokens")
        return text, None

    def _format_rejected(self, e):
        body = e.body.lower()
        return e.status in (400, 404, 415, 422, 500, 501) and (
            any(w in body for w in FORMAT_WORDS) or e.status in (400, 422))

    def _usage(self, usage, info):
        prompt = usage.get("prompt_tokens") or 0
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        call = {"input_tokens": max(0, prompt - cached), "output_tokens": usage.get("completion_tokens") or 0,
                "cache_read_tokens": cached, "cache_write_tokens": 0}
        for k, v in call.items():
            info[k] += v
        price = self.backend.profile.get("price")
        c = usage.get("cost") if isinstance(usage.get("cost"), (int, float)) else cost(call, price)  # OpenRouter
        if c is not None:
            info["cost_usd"] = round((info["cost_usd"] or 0) + c, 6)
