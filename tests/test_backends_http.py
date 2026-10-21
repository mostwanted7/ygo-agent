"""The anthropic and openai backends against local mock servers: request shapes, structured output, retries,
fallback modes, sloppy JSON, timeouts and usage accounting."""

import json
import time

import pytest

from mockhttp import MockServer, anthropic_message, openai_completion
from ygo_agent import backends
from ygo_agent.agent.prompts import SCHEMA
from ygo_agent.backends import BackendError, Request, openai_compat

KEY = "sk-test-not-a-real-key-123"


def ask(session, text="DECISION #1: pick", timeout=5):
    return session.ask(Request(text, {"kind": "idle"}, SCHEMA, timeout))


@pytest.fixture
def anthropic(monkeypatch):
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", KEY)
    with MockServer() as srv:
        def make(**profile):
            p = {"name": "api", "type": "anthropic", "model": "opus", "effort": "medium", "base_url": srv.url,
                 "api_key_env": "TEST_ANTHROPIC_KEY", **profile}
            return backends.create(p).open_session("SYSTEM PROMPT", SCHEMA)
        srv.make = make
        yield srv


def test_anthropic_request_and_reply(anthropic):
    s = anthropic.make()
    anthropic.queue(anthropic_message('{"choice": [2], "why": "summon", "plan": "attack next"}'))
    reply, info = ask(s)
    assert reply == {"choice": [2], "why": "summon", "plan": "attack next"}
    req = anthropic.requests[0]
    assert req["path"] == "/v1/messages"
    assert req["headers"]["x-api-key"] == KEY and req["headers"]["anthropic-version"] == "2023-06-01"
    body = req["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == [{"type": "text", "text": "SYSTEM PROMPT", "cache_control": {"type": "ephemeral"}}]
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["additionalProperties"] is False
    assert body["output_config"]["effort"] == "medium" and "tool_choice" not in body
    assert body["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert info["input_tokens"] == 12 and info["output_tokens"] == 30
    assert info["cache_read_tokens"] == 5000 and info["cache_write_tokens"] == 100
    # 12*4 + 30*20 + 5000*0.2 + 100*5 per million
    assert info["cost_usd"] == pytest.approx((12 * 4 + 30 * 20 + 5000 * 0.2 + 100 * 5) / 1e6)
    assert info["replies"] == 1 and info["error"] is None and info["seconds"] >= 0
    assert KEY not in json.dumps(info)


def test_anthropic_history_is_append_only(anthropic):
    s = anthropic.make()
    first = anthropic_message('{"choice": [0], "why": "a"}')
    anthropic.queue(first)
    anthropic.queue(anthropic_message('{"choice": [1], "why": "b"}'))
    ask(s, "one")
    ask(s, "two")
    msgs = anthropic.requests[1]["body"]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == first["content"]  # thinking block passed back unchanged
    assert "cache_control" not in msgs[0]["content"][-1]  # only the newest user message carries the breakpoint
    assert msgs[2]["content"][-1]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_tool_mode(anthropic):
    s = anthropic.make(structured="tool")
    anthropic.queue(anthropic_message(tool_input={"choice": [1], "why": "tool"}))
    anthropic.queue(anthropic_message('{"choice": [0], "why": "text instead"}'))
    reply, _ = ask(s)
    assert reply["choice"] == [1]
    body = anthropic.requests[0]["body"]
    assert body["tools"][0]["name"] == "reply" and body["tools"][0]["strict"] is True
    assert body["tool_choice"] == {"type": "auto"} and "format" not in body.get("output_config", {})
    assert "reply` tool" in body["system"][0]["text"]
    reply, _ = ask(s, "next")  # the model skipped the tool: its text is parsed instead
    assert reply["choice"] == [0]
    user = anthropic.requests[1]["body"]["messages"][-1]["content"]
    assert user[0] == {"type": "tool_result", "tool_use_id": "toolu_1", "content": "received"}


@pytest.mark.parametrize("status", [429, 529, 500])
def test_anthropic_retries(anthropic, status):
    s = anthropic.make()
    anthropic.queue({"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}, status=status,
                    headers={"retry-after": "0"})
    anthropic.queue(anthropic_message('{"choice": [1], "why": "ok"}'))
    reply, info = ask(s)
    assert reply["choice"] == [1] and info["retries"] == 1 and len(anthropic.requests) == 2


def test_anthropic_client_error_keeps_the_session(anthropic):
    s = anthropic.make()
    anthropic.queue({"type": "error", "error": {"type": "invalid_request_error", "message": "bad thing"}}, status=400)
    anthropic.queue(anthropic_message('{"choice": [0], "why": "fine"}'))
    reply, info = ask(s)
    assert reply is None and "400" in info["error"] and "bad thing" in info["error"]
    assert info["replies"] == 0 and len(anthropic.requests) == 1 and s.alive
    reply, _ = ask(s, "again")
    assert reply["choice"] == [0]
    roles = [m["role"] for m in anthropic.requests[1]["body"]["messages"]]
    assert roles == ["user", "assistant", "user"]  # a note stands in for the missing answer


def test_anthropic_timeout(anthropic):
    s = anthropic.make()
    anthropic.queue(anthropic_message('{"choice": [0], "why": "late"}'), delay=3)
    start = time.monotonic()
    reply, info = ask(s, timeout=0.5)
    assert reply is None and "timed out" in info["error"]
    assert time.monotonic() - start < 2


def test_anthropic_refusal_and_prompt_mode(anthropic):
    s = anthropic.make(structured="none")
    anthropic.queue(anthropic_message("", stop_reason="refusal"))
    reply, info = ask(s)
    assert reply is None and "declined" in info["error"]
    anthropic.queue(anthropic_message('Here you go:\n```json\n{"choice": [3], "why": "parsed",}\n```'))
    reply, _ = ask(s, "again")
    assert reply["choice"] == [3]
    body = anthropic.requests[1]["body"]
    assert "output_config" in body and "format" not in body["output_config"] and "JSON object" in body["system"][0]["text"]


def test_anthropic_needs_a_key(monkeypatch):
    monkeypatch.delenv("NO_SUCH_KEY_VAR", raising=False)
    with pytest.raises(BackendError, match="NO_SUCH_KEY_VAR"):
        backends.check({"name": "api", "type": "anthropic", "api_key_env": "NO_SUCH_KEY_VAR"})


# ---- openai-compatible ----

@pytest.fixture
def openai(monkeypatch):
    monkeypatch.setattr(openai_compat, "_learned", {})
    with MockServer() as srv:
        def make(**profile):
            p = {"name": "local", "type": "openai", "model": "test-model", "base_url": srv.url + "/v1",
                 "json_mode": "auto", **profile}
            backend = backends.create(p)
            return backend.open_session("SYSTEM PROMPT", SCHEMA)
        srv.make = make
        yield srv


def test_openai_schema_mode(openai, monkeypatch):
    monkeypatch.setenv("TEST_OPENAI_KEY", KEY)
    s = openai.make(api_key_env="TEST_OPENAI_KEY", headers={"X-Title": "ygo-agent"}, temperature=0.2, max_tokens=500,
                    num_ctx=16384, extra_body={"top_k": 20}, price={"input": 1.0, "output": 2.0})
    openai.queue(openai_completion('{"why": "ok", "choice": [1], "plan": ""}',
                                   usage={"prompt_tokens": 1000, "completion_tokens": 50,
                                          "prompt_tokens_details": {"cached_tokens": 600}}))
    reply, info = ask(s)
    assert reply == {"choice": [1], "why": "ok", "plan": None}
    req = openai.requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["authorization"] == f"Bearer {KEY}" and req["headers"]["x-title"] == "ygo-agent"
    body = req["body"]
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    assert list(schema["properties"]) == ["why", "choice", "plan"] and schema["required"] == ["why", "choice", "plan"]
    assert body["messages"][0]["role"] == "system" and body["messages"][0]["content"].startswith("SYSTEM PROMPT")
    assert "Reply format" in body["messages"][0]["content"]
    assert body["temperature"] == 0.2 and body["max_tokens"] == 500 and body["top_k"] == 20
    assert body["options"] == {"num_ctx": 16384}
    assert info["input_tokens"] == 400 and info["cache_read_tokens"] == 600 and info["output_tokens"] == 50
    assert info["cost_usd"] == pytest.approx((400 * 1 + 600 * 1 + 50 * 2) / 1e6)
    assert info["json_mode"] == "schema" and KEY not in json.dumps(info)


def test_openai_steps_down_when_formats_are_rejected(openai):
    s = openai.make()
    openai.queue({"error": {"message": "response_format json_schema is not supported"}}, status=400)
    openai.queue({"error": "'response_format.type' must be 'json_schema' or 'text'"}, status=400)
    openai.queue(openai_completion('{"choice": [0], "why": "plain"}'))
    reply, info = ask(s)
    assert reply["choice"] == [0] and info["json_mode"] == "none"
    kinds = [r["body"].get("response_format", {}).get("type") for r in openai.requests]
    assert kinds == ["json_schema", "json_object", None]
    # The next session starts with the mode that worked, and a later error isn't blamed on the format.
    s2 = openai.make()
    openai.queue({"error": {"message": "context length exceeded, check your request format"}}, status=400)
    reply, info = ask(s2)
    assert reply is None and "400" in info["error"]
    assert "response_format" not in openai.requests[3]["body"] and len(openai.requests) == 4


def test_openai_json_object_mode(openai):
    s = openai.make(json_mode="json")
    openai.queue(openai_completion('{"choice": [2], "why": "json mode"}'))
    reply, _ = ask(s)
    assert reply["choice"] == [2] and openai.requests[0]["body"]["response_format"] == {"type": "json_object"}


def test_openai_sloppy_reply_and_history(openai):
    s = openai.make(json_mode="none")
    openai.queue(openai_completion('<think>\nLots of reasoning here.\n</think>\n\nSure!\n```json\n'
                                   '{"choice": [1, 2,], "why": "sloppy",}\n```'))
    openai.queue(openai_completion('{"choice": [0], "why": "next"}'))
    reply, _ = ask(s)
    assert reply["choice"] == [1, 2] and "response_format" not in openai.requests[0]["body"]
    ask(s, "two")
    history = openai.requests[1]["body"]["messages"]
    assert "<think>" not in history[2]["content"] and "sloppy" in history[2]["content"]


def test_openai_reasoning_field_and_repair(openai):
    s = openai.make(json_mode="none")
    openai.queue(openai_completion("I think the best move is to summon the dragon."))
    openai.queue(openai_completion("", reasoning_content='{"choice": [3], "why": "from reasoning"}'))
    reply, info = ask(s)
    assert reply["choice"] == [3]
    assert info["invalid"] == 1 and info["retries"] == 1 and info["replies"] == 2 and info["error"] is None
    repair = openai.requests[1]["body"]["messages"][-1]
    assert repair["role"] == "user" and "could not be read" in repair["content"]


def test_openai_gives_up_after_one_repair(openai):
    s = openai.make(json_mode="none")
    openai.queue(openai_completion("no json"))
    openai.queue(openai_completion("still no json"))
    reply, info = ask(s)
    assert reply is None and info["invalid"] == 2 and "unparseable" in info["error"] and len(openai.requests) == 2


def test_openai_retry_and_timeout(openai):
    s = openai.make(json_mode="none")
    openai.queue({"error": {"message": "rate limited"}}, status=429, headers={"retry-after": "0"})
    openai.queue(openai_completion('{"choice": [1], "why": "after retry"}'))
    reply, info = ask(s)
    assert reply["choice"] == [1] and info["retries"] == 1
    openai.queue(openai_completion('{"choice": [1], "why": "late"}'), delay=3)
    start = time.monotonic()
    reply, info = ask(s, timeout=0.5)
    assert reply is None and "timed out" in info["error"] and time.monotonic() - start < 2


def test_openai_openrouter_cost_and_unreachable_server(openai):
    s = openai.make(json_mode="none")
    openai.queue(openai_completion('{"choice": [0], "why": "x"}',
                                   usage={"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00042}))
    _, info = ask(s)
    assert info["cost_usd"] == pytest.approx(0.00042)
    dead = backends.create({"name": "x", "type": "openai", "model": "m", "base_url": "http://127.0.0.1:9/v1",
                            "max_retries": 0}).open_session("S", SCHEMA)
    reply, info = ask(dead, timeout=2)
    assert reply is None and "can't reach" in info["error"]


def test_openai_check():
    with pytest.raises(BackendError, match="model"):
        backends.check({"name": "x", "type": "openai"})
    with pytest.raises(BackendError, match="json_mode"):
        backends.check({"name": "x", "type": "openai", "model": "m", "json_mode": "xml"})
    backends.check({"name": "x", "type": "openai", "model": "m"})  # no key needed for local servers
