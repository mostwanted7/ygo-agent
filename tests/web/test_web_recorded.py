"""Recorded games as bus messages: game.md parsing, current and old log formats, the real games/ folder, and demo
mode replaying a game through the bus."""

import glob
import json
import os
import shutil

import pytest

from helpers import ROOT
from ygo_agent.web import recorded
from ygo_agent.web.demo import Demo, pace

MD = """# Saffira — game started 2026-10-21 13:36

**Decision #1** — You won the coin toss/RPS: go first? Reply [1] to go first or [0] to go second.

  - ✅ YES

> **auto**: deck setting: go first

- DUEL START — you go first. LP 8000 vs 8000.

**Decision #2** — Main Phase: choose your next action. Reply with exactly one option index.

  - `[0]` Activate "Saffira" from your hand
  - ✅ `[1]` Normal Summon "Tour Guide From the Underworld" (from hand)

> **opus (claude-code)** (9.5s): Tour Guide first.
It brings a Fiend.
>
> *Plan:* 1. Tour Guide.
- 2. Xyz into Lavalval.
>
> ⚠️ engine rejected nothing

- "Tour Guide From the Underworld": your hand → your M1

**Decision #3** — The game asks: "Select". Choose between 1 and 2 card(s); reply with the list of option indices.

  - ✅ `[0]` "A" — your Deck
  - `[1]` "B" — your Deck
  - ✅ `[2]` "C" — your Deck

> **rule:search_first**: always the first

**Decision #4** — Response window: you may activate one of these cards/effects now. Reply with [] to pass.

  - `[0]` Activate "X" from your hand
  - ✅ (pass / none)

> **FALLBACK (built-in AI)**
"""


def test_parse_game_md(tmp_path):
    path = tmp_path / "game.md"
    path.write_text(MD, encoding="utf-8")
    blocks = recorded.parse_md(str(path))
    assert sorted(blocks) == [1, 2, 3, 4]
    assert blocks[1]["chosen"] == [1] and blocks[1]["tag"] == "auto" and blocks[1]["why"] == "deck setting: go first"
    b = blocks[2]
    assert b["chosen"] == [1] and b["tag"] == "opus (claude-code)" and b["seconds"] == 9.5
    assert b["why"] == "Tour Guide first.\nIt brings a Fiend."
    assert b["plan"] == "1. Tour Guide.\n- 2. Xyz into Lavalval." and b["note"] == "engine rejected nothing"
    assert b["options"][0] == 'Activate "Saffira" from your hand'
    assert blocks[3]["chosen"] == [0, 2] and blocks[3]["tag"] == "rule:search_first"
    assert blocks[4]["chosen"] == [] and blocks[4]["tag"].startswith("FALLBACK") and not blocks[4]["why"]


def check_messages(msgs, game_dir):
    rows = [json.loads(line) for line in open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8")]
    decides = [r["msg"] for r in rows if r["kind"] == "decide" and r["msg"]["kind"] != "game_over"]
    decisions = [m for m in msgs if m["type"] == "decision"]
    replies = {m["id"]: m for m in msgs if m["type"] == "reply"}
    assert [m["decision"]["id"] for m in decisions] == [d["id"] for d in decides]
    assert set(replies) == {d["id"] for d in decides}
    assert all(m["question"] and len(m["options"]) == len(m["decision"].get("options", [])) for m in decisions)
    assert sum(1 for m in msgs if m["type"] == "event") == sum(1 for r in rows if r["kind"] == "event")
    assert msgs[0]["type"] == "game_start" and all(m["game_id"] == msgs[0]["game_id"] for m in msgs)
    order = [m["type"] for m in msgs]
    for d in decisions:  # each reply follows its decision
        k = msgs.index(d)
        assert order[k + 1] in ("reply", "advice") and msgs[k + 1]["id"] == d["decision"]["id"]
    return decisions, replies


def test_a_current_format_log(played, db):
    game_dir, case = played
    msgs = recorded.load_game(game_dir, db)
    decisions, replies = check_messages(msgs, game_dir)
    rows = [json.loads(line) for line in open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8")]
    logged = {r["msg"]["id"]: r["msg"] for r in rows if r["kind"] == "reply"}
    for did, r in replies.items():
        assert r["source"] == logged[did]["source"]
        if r["source"] == "backend":
            assert r["why"] == "scripted" and r["label"] and r["usage"]
        if logged[did]["choice"] and len(logged[did]["choice"]) == 1:
            assert r["choice"][:1] == logged[did]["choice"] or r["sent"] == logged[did]["choice"]
    meta = next(m for m in msgs if m["type"] == "meta")
    assert meta["deck"] == "blackwing" and meta["backend"]["label"]
    assert next(m for m in msgs if m["type"] == "game_end")["result"] == "win"


def test_an_old_format_log_without_replies_or_meta(played, db, tmp_path):
    """Logs from before Stage 0 have no reply records and no meta.json: game.md tells what was chosen and why."""
    game_dir, _ = played
    old = tmp_path / "games" / "2026-01-01_000000"
    old.mkdir(parents=True)
    with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f, open(old / "game.jsonl", "w") as out:
        for line in f:
            if json.loads(line)["kind"] != "reply":
                out.write(line)
    shutil.copy(os.path.join(game_dir, "game.md"), old / "game.md")
    msgs = recorded.load_game(str(old), db)
    _, replies = check_messages(msgs, str(old))
    new = {m["id"]: m for m in recorded.load_game(game_dir, db) if m["type"] == "reply"}
    for did, r in replies.items():
        if new[did]["source"] in ("backend", "auto", "fallback") or new[did]["source"].startswith("rule"):
            assert r["source"] == new[did]["source"], did
        if r["source"] != "auto" or new[did]["why"]:
            assert r["why"] == new[did]["why"], did
    meta = next(m for m in msgs if m["type"] == "meta")
    assert meta["started"] and next(m for m in msgs if m["type"] == "game_start")["deck_name"] == "Blackwing"


def test_an_old_copilot_log_still_shows_the_pilots_moves(played, db, tmp_path):
    """Copilot mode is gone (coach mode replaced it), but its logs still replay: a reply with source "pilot" and the
    agent's `suggested` choice becomes the advice, the pilot's move and the human_choice."""
    from ygo_agent.agent.replay import load_messages
    game_dir, _ = played
    old = tmp_path / "games" / "2026-02-02_000000_copilot"
    old.mkdir(parents=True)
    rows = [json.loads(line) for line in open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8")]
    target = next(r["msg"] for r in rows if r["kind"] == "decide" and r["msg"]["kind"] == "idle"
                  and len(r["msg"]["options"]) > 1)
    taken = recorded.parse_md(os.path.join(game_dir, "game.md"))[target["id"]]["chosen"]  # ✅: what was played
    suggested = [1 if taken != [1] else 0]
    with open(old / "game.jsonl", "w", encoding="utf-8") as out:
        for r in rows:
            if r["kind"] == "reply" and r["msg"]["id"] == target["id"]:
                r = {**r, "msg": {"id": target["id"], "choice": taken, "source": "pilot", "suggested": suggested}}
            out.write(json.dumps(r) + "\n")
    shutil.copy(os.path.join(game_dir, "game.md"), old / "game.md")
    meta = json.load(open(os.path.join(game_dir, "meta.json"), encoding="utf-8"))
    json.dump({**meta, "mode": "copilot"}, open(old / "meta.json", "w"))
    msgs = [m for m in recorded.load_game(str(old), db) if m.get("id") == target["id"]]
    kinds = [m["type"] for m in msgs]
    assert kinds == ["advice", "reply", "human_choice"]
    advice, reply, human = msgs
    assert advice["choice"] == suggested and reply["source"] == "pilot" and reply["choice"] == taken
    assert human["advised"] == suggested and human["matched"] is False
    assert load_messages(str(old), target["id"])[-1]["id"] == target["id"]  # `ygo-agent replay` reads it too


def test_feedback_notes_land_after_their_decision(played, db):
    game_dir, _ = played
    ack = recorded.append_feedback(game_dir, "Chinook should wait", decision=5)
    assert ack["context"].endswith("right after decision #5") and ack["context"].startswith("turn ")
    with open(os.path.join(game_dir, "feedback.md"), encoding="utf-8") as f:
        assert f.read().endswith(f"- ({ack['context']}; from Web panel) Chinook should wait\n")
    msgs = recorded.load_game(game_dir, db)
    k = next(i for i, m in enumerate(msgs) if m["type"] == "feedback_ack")
    assert msgs[k - 1]["type"] == "reply" and msgs[k - 1]["id"] == 5 and msgs[k]["text"] == "Chinook should wait"


def test_the_library_lists_games_and_refuses_odd_names(played, db):
    game_dir, _ = played
    lib = recorded.Library(os.path.dirname(game_dir))
    (s,) = lib.list()
    assert s["name"] == os.path.basename(game_dir) and s["deck_name"] == "Blackwing" and s["result"] == "win"
    assert s["decisions"] > 0 and s["latest"] and s["backend"]
    for bad in ("..", "../games", "latest/../x", "", "a b"):
        assert lib.path(bad) is None and lib.summary(bad) is None
    assert lib.load(s["name"], db)[0]["type"] == "game_start"


REAL = sorted(p for p in glob.glob(os.path.join(ROOT, "games", "*", "game.jsonl")) if "/latest/" not in p)


@pytest.mark.skipif(not REAL, reason="no recorded games in games/")
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.split(os.sep)[-2])
def test_real_recorded_games_load(path, db):
    game_dir = os.path.dirname(path)
    msgs = recorded.load_game(game_dir, db)
    decisions, replies = check_messages(msgs, game_dir)
    md = recorded.parse_md(os.path.join(game_dir, "game.md"))
    for d in decisions:
        r = replies[d["decision"]["id"]]
        if d["decision"]["id"] in md:
            assert r["choice"] == md[d["decision"]["id"]]["chosen"] or not md[d["decision"]["id"]]["chosen"]


def test_demo_replays_a_game_through_the_bus(played, db, bus):
    game_dir, _ = played
    demo = Demo(game_dir, db, speed=10000)
    demo.play_once()
    msgs = bus.backlog(demo.game_id)
    assert demo.game_id.startswith("demo:") and len(msgs) == len(demo.messages) + 1
    assert msgs[0]["type"] == "game_start" and msgs[0]["demo"] and msgs[0]["dir"] == os.path.abspath(game_dir)
    assert [m["type"] for m in msgs[:-1]] == [m["type"] for m in demo.messages]
    # A finished game's result comes at its end, so the demo is a live game until then.
    metas = [m for m in msgs if m["type"] == "meta"]
    assert all("result" not in m for m in metas[:-1]) and metas[-1] is msgs[-1] and msgs[-1]["result"] == "win"
    assert bus.games()[0]["game_id"] == demo.game_id and not bus.games()[0]["live"]
    # Thinking time follows the backend's latency, within limits; quiet events go by quickly.
    assert pace(None, {"type": "reply", "source": "backend", "seconds": 30, "why": "x"}) == 7.2
    assert pace(None, {"type": "event", "ev": {"e": "chain_end"}}) < 0.1
