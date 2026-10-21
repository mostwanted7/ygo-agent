"""The prompt budget (card_texts, history_lines, max_session_messages), plan carry-over across a session rollover,
the per-game stats, backend labels and the heuristic fallback."""

import json
import os

import pytest

from helpers import CASES, EDOPRO, load_case
from ygo_agent.agent.brain import DuelBrain
from ygo_agent.agent.carddb import CardDB
from ygo_agent.agent.profile import Profile
from ygo_agent.agent.validate import validate
from ygo_agent.backends import estimate_tokens
from ygo_agent.backends.heuristic import Policy

LONG = ("When this card is Normal Summoned: You can add 1 Ritual Monster from your Deck to your hand. "
        "During your opponent's Main Phase (Quick Effect): You can Tribute this card; Special Summon 1 Ritual "
        "Monster from your hand, ignoring its summoning conditions. You can only use each effect of "
        '"Test Card" once per turn.\n\n* The above text is unofficial and describes the card\'s functionality '
        "in the OCG.")


def synthetic_db(db):
    """The fixture card data, plus a long effect text on every card (the fixture has no texts)."""
    data = {"cards": {}, "system": db.system, "victory": db.victory}
    for cid, c in db.cards.items():
        data["cards"][cid] = [c.name, LONG.replace("Test Card", c.name), c.strings, c.type, c.level, c.atk,
                              c.defense, c.race, c.attribute, c.alias, c.setcode]
    return CardDB.from_dict(data)


def test_card_text_modes(db, cfg):
    tdb = synthetic_db(db)
    p = Profile("saffira", tdb, cfg)
    full, compact, none = (p.system_prompt("play", "MR3", mode) for mode in ("full", "compact", "none"))
    assert len(none) < len(compact) < len(full)
    for text in (full, compact, none):
        assert all(tdb.name(i) in text for i in p.main + p.extra)
        assert p.playbook in text and "# General strategy" in text
    assert "## Card texts" in compact and "## Card texts" not in none
    assert "unofficial" in full and "unofficial" not in compact
    assert "(Each effect: once per turn.)" in compact
    covered = next(i for i in p.main if tdb.name(i) in p.playbook)
    assert len(p.card_text(covered, "compact")) < len(p.card_text(covered, "full"))
    assert p.card_text(covered, "none") == tdb.type_text(covered) and ":" not in p.card_text(covered, "none")[-3:]
    assert "LIGHT Dragon Lv6" in none  # the decklist carries the type lines when there are no texts


def run_case(brain, case, upto=None):
    replies = []
    for m in case["messages"][:upto]:
        m = json.loads(json.dumps(m))
        if m.get("t") == "event":
            brain.on_event(m)
        else:
            replies.append((m, brain.on_decide(m)))
    return replies


def case(name):
    return load_case(next(p for p in CASES if p.endswith(f"/{name}.json")))


def test_history_lines_and_card_texts_per_profile(db, cfg, scripted):
    cfg["backends"]["test"].update(history_lines=5, card_texts="none")
    brain = DuelBrain(cfg, db, Profile("blackwing", db, cfg), prewarm=False)
    run_case(brain, case("chinook-on-attack"))
    brain.close()
    first = scripted["sessions"][-1].prompts[0]
    log = first.split("Duel log so far:\n", 1)[1].split("\n\n", 1)[0]
    assert len(log.splitlines()) <= 5
    texts = [p for s in scripted["sessions"] for p in s.prompts if "Card texts (not shown" in p]
    assert texts and all("]: " not in t.split("Card texts (not shown", 1)[1].split("\n\n")[0] for t in texts)


def test_rollover_carries_the_plan_and_the_turns_decisions(db, cfg, scripted):
    cfg["backends"]["test"]["max_session_messages"] = 2
    calls = {"n": 0}
    legal = Policy(db)

    def policy(d):
        calls["n"] += 1
        return {"choice": legal.choose(d), "why": f"reason {calls['n']}", "plan": f"PLAN-{calls['n']}"}
    scripted["policy"] = policy
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False)
    run_case(brain, case("set-lance-before-ending"))
    brain.close()
    carried = [s.prompts[0] for s in scripted["sessions"] if "previous session for this turn ended" in s.prompts[0]]
    assert carried, "a mid-turn rollover must carry the plan over"
    text = carried[0]
    assert "Your plan for this turn: PLAN-" in text and "Decisions already made this turn:" in text
    assert "[test (scripted)]" in text and "reason " in text
    with open(os.path.join(brain.log.dir, "meta.json"), encoding="utf-8") as f:
        stats = json.load(f)["stats"]
    assert stats["rollovers"] >= 1 and stats["sessions"] > stats["rollovers"]


def test_stats_labels_and_invalid_replies(db, cfg, scripted):
    seen = set()
    legal = Policy(db)

    def policy(d):
        if d["kind"] == "idle" and d["id"] not in seen:
            seen.add(d["id"])
            return [99]  # illegal: the agent re-asks once
        return legal.choose(d)
    scripted["policy"] = policy
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False)
    c = case("set-lance-before-ending")
    replies = run_case(brain, c)
    brain.on_event({"t": "event", "e": "win", "result": 0, "reason": 1})
    brain.close()
    with open(os.path.join(brain.log.dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    s = meta["stats"]
    assert meta["backend"]["label"] == "test (scripted)" and meta["backend"]["type"] == "scripted"
    assert "policy" not in meta["backend"]
    assert s["decisions"] == len(replies) == sum(s["by_source"].values()) and s["by_source"]["fallback"] == 0
    assert set(s["by_source"]) == {"backend", "rule", "auto", "fallback", "pilot"}
    assert s["invalid_replies"] == len(seen) and s["asks"] == s["replies"] == s["by_source"]["backend"] + len(seen)
    assert s["invalid_rate"] == round(len(seen) / s["replies"], 4)
    assert s["latency_mean_s"] is not None and s["latency_p95_s"] is not None and s["cost_usd"] is None
    assert set(s["tokens"]) == {"input", "output", "cache_read", "cache_write"}
    with open(os.path.join(brain.log.dir, "game.md"), encoding="utf-8") as f:
        md = f.read()
    assert "**test (scripted)**" in md and "Claude" not in md
    sources = {json.loads(line)["msg"]["source"] for line in open(os.path.join(brain.log.dir, "game.jsonl"))
               if json.loads(line)["kind"] == "reply"}
    assert "backend" in sources and "llm" not in sources


def test_heuristic_fallback_answers_what_the_backend_cant(db, cfg, scripted):
    scripted["policy"] = lambda d: None  # the backend never answers
    cfg["agent"]["fallback"] = "heuristic"
    brain = DuelBrain(cfg, db, Profile("saffira", db, cfg), prewarm=False)
    c = case("set-lance-before-ending")
    replies = run_case(brain, c)
    brain.close()
    assert replies
    for d, r in replies:
        assert r["choice"] is not None, d["kind"]
        if d["kind"] == "announce_card":
            assert r["choice"][0] in d["options"]
        elif d["kind"] != "select_unselect":
            assert validate(d, r["choice"]) is None, (d["kind"], r["choice"])
    places = [r for d, r in replies if d["kind"] == "place"]
    assert places and all(r["choice"][0] & d["available"] for d, r in replies if d["kind"] == "place")
    with open(os.path.join(brain.log.dir, "game.md"), encoding="utf-8") as f:
        assert "FALLBACK (heuristic policy)" in f.read()


def test_heuristic_backend_plays_a_case(db, cfg):
    cfg["agent"]["backend"] = "heuristic"
    brain = DuelBrain(cfg, db, Profile("blackwing", db, cfg), prewarm=False)
    replies = run_case(brain, case("nuke-when-overcommitted"))
    brain.close()
    assert brain.label == "heuristic"
    for d, r in replies:
        if r["choice"] is not None and d["kind"] not in ("announce_card", "select_unselect"):
            assert validate(d, r["choice"]) is None


@pytest.mark.integration
@pytest.mark.parametrize("key", ["saffira", "blackwing"])
def test_real_prompt_sizes(key, cfg, capsys):
    real = CardDB(EDOPRO)
    p = Profile(key, real, cfg)
    sizes = {mode: len(p.system_prompt("play", "MR3", mode)) for mode in ("full", "compact", "none")}
    assert sizes["none"] < sizes["compact"] < sizes["full"]
    with capsys.disabled():
        print(f"\n  {key} system prompt: " + ", ".join(f"{m} {n} chars ~{estimate_tokens('x' * n)} tokens"
                                                    for m, n in sizes.items()))
