"""The claude-code backend against a fake `claude` executable that speaks the stream-json protocol."""

import json
import os
import stat
import sys
import textwrap

import pytest

from ygo_agent import backends
from ygo_agent.agent.prompts import SCHEMA
from ygo_agent.backends import Request

FAKE = textwrap.dedent("""\
    import json, os, sys, time
    args = sys.argv[1:]
    log = open(os.environ["FAKE_CLAUDE_LOG"], "a")
    prompt_file = args[args.index("--system-prompt-file") + 1]
    system = open(prompt_file).read()
    log.write(json.dumps({"argv": args, "system": system}) + "\\n"); log.flush()
    total = 0.0
    for line in sys.stdin:
        text = json.loads(line)["message"]["content"]
        if "SLEEP" in text:
            time.sleep(5)
        total += 0.01
        print(json.dumps({"type": "assistant", "message": {}}), flush=True)
        if "GARBAGE" in text:
            out = {"type": "result", "is_error": False, "result": "not json", "usage": {}, "total_cost_usd": total}
        else:
            out = {"type": "result", "is_error": False, "structured_output": {"choice": [1], "why": "fake"},
                   "usage": {"input_tokens": 3, "output_tokens": 20, "cache_read_input_tokens": 4000,
                             "cache_creation_input_tokens": 50}, "total_cost_usd": total}
        print(json.dumps(out), flush=True)
    """)


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    script = tmp_path / "claude"
    script.write_text(f"#!{sys.executable}\n" + FAKE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setattr("ygo_agent.backends.claude_code.WORKDIR", str(tmp_path / "work"))
    profile = {"name": "opus", "type": "claude-code", "model": "opus", "effort": "medium", "command": str(script)}
    return profile, log


def test_session_passes_the_system_prompt_by_file(fake_claude):
    profile, log = fake_claude
    backend = backends.create(profile)
    assert backend.label == "opus (claude-code)"
    backend.check()
    system = "You are an expert duelist. " * 2000  # ~54 kB: far too long for a comfortable argv
    session = backend.open_session(system, SCHEMA)
    reply, info = session.ask(Request("DECISION #1", {"kind": "idle"}, SCHEMA, 10))
    assert reply == {"choice": [1], "why": "fake", "plan": None}
    assert info["cache_read_tokens"] == 4000 and info["output_tokens"] == 20 and info["cost_usd"] == 0.01
    reply, info = session.ask(Request("DECISION #2", {"kind": "idle"}, SCHEMA, 10))
    assert info["cost_usd"] == 0.01  # the CLI's running total, turned into a per-call cost
    call = json.loads(log.read_text().splitlines()[0])
    assert call["system"] == system
    assert "--system-prompt" not in call["argv"] and system not in " ".join(call["argv"])
    assert call["argv"][call["argv"].index("--model") + 1] == "opus"
    assert call["argv"][call["argv"].index("--effort") + 1] == "medium"
    assert json.loads(call["argv"][call["argv"].index("--json-schema") + 1]) == SCHEMA
    prompt_file = call["argv"][call["argv"].index("--system-prompt-file") + 1]
    assert os.path.exists(prompt_file) and session.messages == 2
    session.close()
    assert not os.path.exists(prompt_file) and not session.alive


def test_unparseable_result_and_timeout(fake_claude):
    profile, _ = fake_claude
    session = backends.create(profile).open_session("S", SCHEMA)
    reply, info = session.ask(Request("GARBAGE please", None, SCHEMA, 10))
    assert reply is None and info["invalid"] == 1 and "unparseable" in info["error"]
    reply, info = session.ask(Request("SLEEP now", None, SCHEMA, 0.5))
    assert reply is None and "timed out" in info["error"] and not session.alive


def test_missing_cli():
    with pytest.raises(backends.BackendError, match="claude"):
        backends.check({"name": "x", "type": "claude-code", "command": "/nonexistent/claude"})
