"""The backend interface, plus what the HTTP backends share (retries, cost, the conversation loop).

A backend is created once per seat from its profile (a [backends.NAME] table) and opens one session per game turn:

    backend = backends.create(profile, db=card_db)
    session = backend.open_session(system_prompt, schema)
    reply, info = session.ask(Request(text, decision, schema, timeout))
    session.alive, session.messages, session.close()

`reply` is a dict matching the schema ({"choice": [...], "why": ..., "plan": ...}) or None; `info` always has the
INFO fields below (docs/backends.md). Sessions keep the conversation, so the agent's corrective re-ask
("That reply is invalid: ...") is just the next ask().
"""

import json
import random
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .parse import ParseError, normalize, parse_reply


class BackendError(Exception):
    pass


class HTTPStatusError(BackendError):
    def __init__(self, status, body):
        self.status, self.body = status, body
        super().__init__(f"HTTP {status}: {body[:300]}")


@dataclass
class Request:
    text: str                  # the message an LLM sees (history, card texts, state, the decision)
    decision: dict = None      # the raw decision (docs/decision-protocol.md), for non-LLM backends
    schema: dict = None        # the reply schema (agent/prompts.py SCHEMA)
    timeout: float = 120       # seconds for this ask, retries included
    error: str = None          # on a corrective re-ask: why the previous reply was rejected


def new_info():
    """Every ask() returns these fields (docs/backends.md); `replies` and `invalid` feed the invalid-reply rate."""
    return {"seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0,
            "cost_usd": None, "retries": 0, "replies": 0, "invalid": 0, "error": None}


class Session:
    def __init__(self):
        self.messages = 0  # decisions asked so far (the agent rolls the session over after a limit)
        self.alive = True

    def ask(self, request):
        raise NotImplementedError

    def close(self):
        self.alive = False


class Backend:
    """One configured profile. Subclasses set TYPE and implement open_session()."""
    TYPE = None

    def __init__(self, profile, db=None):
        self.profile = profile
        self.db = db
        self.name = profile.get("name") or self.TYPE

    @property
    def model(self):
        return self.profile.get("model") or ""

    @property
    def label(self):
        """How this backend's decisions are tagged in the terminal, game.md and meta.json."""
        detail = self.TYPE if not self.model or self.model == self.name else f"{self.TYPE}, {self.model}"
        return self.name if self.name == self.TYPE else f"{self.name} ({detail})"

    def check(self):
        """Raise BackendError if this profile can't run on this machine."""

    def describe(self):
        bits = [f"model: {self.model}"] if self.model else []
        for key in ("effort", "base_url", "json_mode"):
            if self.profile.get(key):
                bits.append(f"{key}: {self.profile[key]}")
        return ", ".join(bits)

    def open_session(self, system_prompt, schema):
        raise NotImplementedError


# ---- cost ----

def cost(usage, price):
    """USD for one call. price: {input, output, cache_read, cache_write} in USD per million tokens, or None."""
    if not price:
        return None
    return round((usage["input_tokens"] * price.get("input", 0) + usage["output_tokens"] * price.get("output", 0)
                  + usage["cache_read_tokens"] * price.get("cache_read", price.get("input", 0))
                  + usage["cache_write_tokens"] * price.get("cache_write", price.get("input", 0))) / 1e6, 6)


def estimate_tokens(text):
    """Rough token count of prompt text. Measured on the system prompts: 2.3-2.4 characters per token with
    Claude's tokenizer (card names and quotes are token-dense). Llama/Qwen-style tokenizers usually fit more
    characters per token, so for them this errs high, the safe side for a context budget."""
    return round(len(text) / 2.4)


# ---- HTTP ----

RETRY_STATUS = (408, 409, 429, 500, 502, 503, 504, 529)


def retry_delay(attempt, headers=None):
    """Seconds before retry `attempt` (0-based): the server's retry-after if it gives one, else jittered backoff."""
    try:
        value = float((headers or {}).get("retry-after"))
        return max(0.0, value)
    except (TypeError, ValueError):
        return min(30.0, 0.5 * 2 ** attempt) * (0.75 + random.random() / 2)


def post_json(url, body, headers, deadline, info, max_retries=3):
    """POST `body` as JSON and return the decoded response, retrying 429/5xx/overloaded and connection errors
    within `deadline` (a time.monotonic() value). Raises BackendError. The headers (API keys) are never logged."""
    data = json.dumps(body).encode()
    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.05:
            raise BackendError("timed out")
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=remaining) as resp:
                raw = resp.read()
            try:
                return json.loads(raw)
            except ValueError:
                raise BackendError(f"the server sent invalid JSON: {raw[:200]!r}") from None
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            if e.code in RETRY_STATUS and attempt < max_retries:
                delay = retry_delay(attempt, e.headers)
                if time.monotonic() + delay < deadline:
                    attempt += 1
                    info["retries"] += 1
                    time.sleep(delay)
                    continue
            raise HTTPStatusError(e.code, text) from None
        except (TimeoutError, socket.timeout):
            raise BackendError("timed out") from None
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise BackendError("timed out") from None
            if attempt < min(max_retries, 2):
                delay = retry_delay(attempt)
                if time.monotonic() + delay < deadline:
                    attempt += 1
                    info["retries"] += 1
                    time.sleep(delay)
                    continue
            raise BackendError(f"can't reach {url}: {reason}") from None


# ---- the conversation loop of the HTTP backends ----

REPAIR = ('Your last reply could not be read ({error}). Reply again to the same decision with only a JSON object, '
          'for example: {{"why": "short reason", "choice": [0], "plan": ""}}')


class ChatSession(Session):
    """A conversation over an HTTP chat API. Subclasses implement:
      _user(text)          append a user message to self.history
      _assistant_note(t)   append a plain assistant message (keeps roles alternating after a failed call)
      _complete(deadline, info) -> (text, parsed dict or None): one model call; appends the assistant message
    """

    def __init__(self, system_prompt, schema, repair=True):
        super().__init__()
        self.system_prompt = system_prompt
        self.schema = schema
        self.history = []
        self.repair = repair

    def ask(self, request):
        info = new_info()
        start = time.monotonic()
        deadline = start + request.timeout
        self.messages += 1
        text = request.text
        try:
            for attempt in range(2 if self.repair else 1):
                self._user(text)
                try:
                    raw, parsed = self._complete(deadline, info)
                except BackendError as e:
                    info["error"] = str(e)
                    if self.history and self.history[-1]["role"] == "user":  # keep user/assistant alternating
                        self._assistant_note(f"(no answer: {e}; the game's fallback answered this decision)")
                    return None, info
                info["replies"] += 1
                try:
                    reply = normalize(parsed if parsed is not None else parse_reply(raw))
                    info["error"] = None
                    return reply, info
                except ParseError as e:
                    info["invalid"] += 1
                    info["error"] = f"unparseable reply ({e}): {str(raw)[:200]!r}"
                    if deadline - time.monotonic() < 1:
                        break
                    info["retries"] += 1
                    text = REPAIR.format(error=e)
            return None, info
        finally:
            info["seconds"] = round(time.monotonic() - start, 2)
