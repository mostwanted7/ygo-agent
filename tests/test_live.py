"""End-to-end runs of the openai backend against the fake server, and real model calls (`pytest --live`)."""

import json
import os
import shutil
import threading

import pytest

from helpers import CASES, decisions, load_case
from ygo_agent import backends
from ygo_agent.agent.brain import DuelBrain
from ygo_agent.agent.profile import Profile
from ygo_agent.agent.prompts import SCHEMA
from ygo_agent.agent.validate import validate
from ygo_agent.backends import Request, openai_compat

import fake_openai_server


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(openai_compat, "_learned", {})
    httpd = fake_openai_server.server(sloppy=True, reject_schema=True)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()
    httpd.server_close()


@pytest.mark.parametrize("name", ["set-lance-before-ending", "chinook-on-attack"])
def test_a_saved_game_through_the_openai_backend(name, fake, db, cfg):
    path = next(p for p in CASES if p.endswith(f"/{name}.json"))
    cfg["backends"]["fake"] = {"type": "openai", "base_url": fake, "model": "fake-7b", "json_mode": "auto",
                               "card_texts": "compact", "history_lines": 100, "max_session_messages": 6}
    cfg["agent"]["backend"] = "fake"
    brain = DuelBrain(cfg, db, Profile(path.split(os.sep)[-3], db, cfg), prewarm=False)
    replies = []
    for m in load_case(path)["messages"]:
        m = json.loads(json.dumps(m))
        if m.get("t") == "event":
            brain.on_event(m)
        else:
            replies.append((m, brain.on_decide(m)))
    brain.close()
    with open(os.path.join(brain.log.dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    stats = meta["stats"]
    assert meta["backend"]["label"] == "fake (openai, fake-7b)"
    assert stats["by_source"]["backend"] > 0 and stats["errors"] == 0
    assert stats["tokens"]["input"] > 0 and stats["invalid_replies"] <= stats["replies"]
    for d, r in replies:
        if r["choice"] is not None and d["kind"] not in ("announce_card", "select_unselect"):
            assert validate(d, r["choice"]) is None
    with open(os.path.join(brain.log.dir, "prompts.jsonl"), encoding="utf-8") as f:
        infos = [json.loads(line)["info"] for line in f]
    assert {i.get("json_mode") for i in infos if i.get("json_mode")} == {"json"}  # stepped down from schema


@pytest.mark.live
@pytest.mark.skipif(not shutil.which("claude"), reason="no claude CLI")
def test_claude_code_one_real_call(db):
    """One real call through the user's Claude Code login (haiku, cheap)."""
    session = backends.create({"name": "haiku", "type": "claude-code", "model": "haiku", "effort": "low"}
                              ).open_session("You answer Yu-Gi-Oh! decisions as JSON.", SCHEMA)
    d = next(d for d in decisions(load_case(CASES[0])) if d["kind"] == "idle")
    try:
        reply, info = session.ask(Request("DECISION #1: Main Phase. Reply with exactly one option index.\n"
                                          "[0] Normal Summon a monster\n[1] End your turn", d, SCHEMA, 120))
    finally:
        session.close()
    assert reply is not None, info
    assert reply["choice"] in ([0], [1]) and reply["why"]
    assert info["output_tokens"] > 0 and info["seconds"] > 0


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY is not set")
def test_anthropic_one_real_call():
    session = backends.create({"name": "api", "type": "anthropic", "model": "haiku", "max_tokens": 4000}
                              ).open_session("You answer Yu-Gi-Oh! decisions as JSON.", SCHEMA)
    reply, info = session.ask(Request("DECISION #1: Main Phase. Reply with exactly one option index.\n"
                                      "[0] Normal Summon a monster\n[1] End your turn", None, SCHEMA, 120))
    assert reply is not None, info
    assert reply["choice"] in ([0], [1]) and info["output_tokens"] > 0 and info["cost_usd"] is not None
