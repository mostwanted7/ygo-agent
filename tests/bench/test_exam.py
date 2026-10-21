"""The decision exam (bench/exam.py, bench/judge.py) without EDOPro or an LLM: position sampling and filtering, blind
labels, identical-choice grades, the judge's reply checks, aggregation, and a scripted run of the whole pipeline with
resume. The logged games are built from the saved regression cases."""

import argparse
import glob
import json
import os
import re

import pytest

from helpers import ROOT, first_valid
from ygo_agent.agent.profile import Profile
from ygo_agent.agent.rules import Decide, Rules
from ygo_agent.bench import cli as bench_cli
from ygo_agent.bench import exam as E
from ygo_agent.bench import judge as J

CASES = {deck: sorted(glob.glob(os.path.join(ROOT, "decks", deck, "tests", "*.json")))
         for deck in ("saffira", "blackwing")}


def make_game(folder, case_path, deck, backend="sonnet", btype="claude-code", source=None):
    """A logged game from a saved case: its messages, a reply after every decision (first_valid), and meta.json."""
    with open(case_path, encoding="utf-8") as f:
        case = json.load(f)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "game.jsonl"), "w", encoding="utf-8") as f:
        for m in case["messages"]:
            kind = "decide" if m.get("t") == "decide" else "event"
            f.write(json.dumps({"ts": 0, "kind": kind, "msg": m}) + "\n")
            if kind == "decide":
                src = source(m) if source else "backend"
                f.write(json.dumps({"ts": 0, "kind": "reply", "msg": {"id": m["id"], "choice": first_valid(m),
                                                                      "source": src}}) + "\n")
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"deck": deck, "mode": "selfplay", "rules": "MR3", "result": "win", "first": True,
                   "backend": {"name": backend, "type": btype, "model": backend, "label": f"{backend} ({btype})"},
                   "opponent_info": {"kind": "windbot", "deck": "Blue-Eyes"}}, f)
    with open(os.path.join(folder, "game.md"), "w", encoding="utf-8") as f:
        f.write(f"# {deck}\n\n## TURN 1 (your turn)\n\n**Decision #1** — Main Phase.\n\n  - ✅ `[0]` x\n\n"
                f"> **{backend} ({btype})** (1.2s): because {backend} said so\n")
    return folder


@pytest.fixture
def games(tmp_path):
    root = tmp_path / "games"
    backends = ["opus", "sonnet", "haiku"]
    n = 0
    for deck, cases in CASES.items():
        for i, case in enumerate(cases):
            n += 1
            make_game(str(root / "bench" / "run" / f"{deck}--g{i}" / "log"), case, deck, backends[n % 3],
                      source=lambda m: "auto" if m["id"] % 7 == 0 else "backend")
    make_game(str(root / "heur"), CASES["saffira"][0], "saffira", "heuristic", "heuristic")
    os.symlink("bench", str(root / "latest"))
    return str(root)


@pytest.fixture
def pool(games, db, cfg):
    out = []
    for g in E.find_games([games], ["saffira", "blackwing"]):
        profile = Profile(g["deck"], db, cfg)
        out += E.scan_game(g, db, profile, Rules(profile.dir))
    return out


# ---- sampling and filtering ----

def test_find_games_takes_llm_games_once(games):
    found = E.find_games([games], ["saffira", "blackwing"])
    assert len(found) == sum(len(c) for c in CASES.values())  # the heuristic game is left out
    assert len({g["dir"] for g in found}) == len(found)
    assert all(g["backend"] in ("opus", "sonnet", "haiku") for g in found)
    saffira = E.find_games([games], ["saffira"])
    assert saffira and all(g["deck"] == "saffira" for g in saffira)


def test_scan_keeps_only_real_model_choices(pool, games, db, cfg):
    assert pool
    for c in pool:
        assert c["kind"] not in E.SKIP_KINDS and c["choices"] >= 2
        assert c["decision"] % 7 != 0  # the replies tagged "auto" are never asked
        assert c["group"] in E.GROUPS and c["score"] > 0 and len(c["sha"]) == 12
    assert {c["group"] for c in pool} >= {"idle", "chain", "select_card"}
    # a deck rule that answers every Main Phase takes those decisions out
    g = E.find_games([games], ["saffira"])[0]
    profile = Profile("saffira", db, cfg)
    rules = Rules(profile.dir)
    rules.deck_rules = [lambda ctx: Decide([0], "always") if ctx.kind == "idle" else None]
    assert not [c for c in E.scan_game(g, db, profile, rules) if c["kind"] == "idle"]


def test_selection_is_reproducible_and_stratified(pool):
    a = E.select(pool, 12, ["saffira", "blackwing"], seed=3)
    b = E.select(pool, 12, ["saffira", "blackwing"], seed=3)
    assert a == b and len(a) == 12
    assert [p["id"] for p in a] == [f"p{i:02d}" for i in range(1, 13)]
    assert {p["deck"] for p in a} == {"saffira", "blackwing"}
    assert len({p["group"] for p in a}) >= 3
    per = {}
    for p in a:
        per.setdefault(p["game"], []).append(p["decision"])
    assert all(len(v) <= 5 for v in per.values())
    assert E.select(pool, 12, ["saffira", "blackwing"], seed=4) != a


def test_allocate_respects_targets_and_supply():
    q = E.allocate(10, {"a": 0.5, "b": 0.3, "c": 0.2}, {"a": 100, "b": 100, "c": 100})
    assert q == {"a": 5, "b": 3, "c": 2}
    q = E.allocate(10, {"a": 0.5, "b": 0.3, "c": 0.2}, {"a": 100, "b": 1, "c": 0})
    assert q == {"a": 9, "b": 1, "c": 0}
    assert sum(E.allocate(7, {"a": 1, "b": 1}, {"a": 3, "b": 3}).values()) == 6


def test_make_exam_and_select_command(games, db, cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(E, "EXAMS", str(tmp_path / "exams"))
    monkeypatch.setattr("ygo_agent.cli.load_db", lambda cfg: db)
    ap = argparse.ArgumentParser()
    bench_cli.register(ap.add_subparsers())
    args = ap.parse_args(["bench", "exam", "t", "--select", "--positions", "8", "--sources", games, "--seed", "5"])
    assert E.main(args, cfg, args.what[1:]) == 0
    exam = E.load_json(str(tmp_path / "exams" / "t.json"))
    assert len(exam["positions"]) == 8 and exam["seed"] == 5 and exam["pool"]["games"] == 5
    args = ap.parse_args(["bench", "exam", "t", "--dry-run", "--backends", "opus,haiku"])
    assert E.main(args, cfg, args.what[1:]) == 0


# ---- identical moves, blind labels ----

def test_identical_moves_share_a_key():
    d = {"kind": "select_card", "options": [{}, {}, {}], "min": 1, "max": 2}
    texts = ['"Saffira" — your Deck', '"Saffira" — your Deck', '"Hymn" — your Deck']
    assert E.answer_key(d, [0], texts) == E.answer_key(d, [1], texts) != E.answer_key(d, [2], texts)
    assert E.answer_key(d, [0, 2], texts) == E.answer_key(d, [2, 1], texts)
    idle = {"kind": "idle", "options": [{}, {}]}
    entry = 'Special Summon "X" from your Extra Deck (by its own summoning procedure; entry {} of 2 for this card, ' \
            'which the engine lists once per copy and procedure: the entries are equivalent)'
    assert E.answer_key(idle, [0], [entry.format(1), entry.format(2)]) == E.answer_key(
        idle, [1], [entry.format(1), entry.format(2)])
    assert E.answer_key({"kind": "effect_yn"}, [1], []) == "yes" != E.answer_key({"kind": "effect_yn"}, [0], [])
    assert E.answer_key({"kind": "chain"}, [], ["a"]) == "pass / none"


ANSWERS = {"opus": {"key": "x", "answer": "[0] Activate X", "why": "Opus thinks X is best"},
           "sonnet": {"key": "y", "answer": "[1] Pass", "why": "y because"},
           "haiku": {"key": "x", "answer": "[2] Activate X", "why": "same move, other reason"}}


def test_blind_labels_are_reproducible_and_anonymous():
    items, mapping = J.blind("p01", ANSWERS, "exam:opus")
    again = J.blind("p01", ANSWERS, "exam:opus")
    assert (items, mapping) == again
    assert len(items) == 2 and {i["label"] for i in items} == {"A", "B"}  # opus and haiku share a label
    text = json.dumps(items).lower()
    assert "opus" not in text and "sonnet" not in text and "haiku" not in text
    shared = next(m for m in mapping.values() if m["key"] == "x")
    assert sorted(shared["candidates"]) == ["haiku", "opus"]
    orders = {tuple(m["key"] for _, m in sorted(J.blind(f"p{i}", ANSWERS, "s")[1].items())) for i in range(30)}
    assert len(orders) == 2  # the order changes from position to position


def test_unblind_gives_identical_choices_one_grade():
    items, mapping = J.blind("p01", ANSWERS, "s")
    grades = {label: {"grade": "best" if m["key"] == "x" else "blunder", "reason": "r"}
              for label, m in mapping.items()}
    per = J.unblind(mapping, grades)
    assert per["opus"]["grade"] == per["haiku"]["grade"] == "best" and per["sonnet"]["grade"] == "blunder"
    assert per["opus"]["label"] == per["haiku"]["label"] != per["sonnet"]["label"]


def test_probe_shows_a_move_twice_without_scoring_it():
    items, mapping = J.blind("p01", ANSWERS, "s", probe=1.0)
    assert len(items) == 3
    probe = next(label for label, m in mapping.items() if m["probe_of"])
    real = mapping[probe]["probe_of"]
    assert mapping[probe]["key"] == mapping[real]["key"] == "x" and mapping[probe]["candidates"] == []
    grades = {label: {"grade": "good", "reason": ""} for label in mapping}
    grades[probe] = {"grade": "mistake", "reason": ""}
    assert J.probe_pairs(mapping, grades) == [("good", "mistake")]
    assert J.unblind(mapping, grades)["opus"]["grade"] == "good"


def test_check_reply_and_consistency():
    items = [{"id": "p01", "answers": [{"label": "A"}, {"label": "B"}]},
             {"id": "p02", "answers": [{"label": "A"}]}]
    out = {"positions": [
        {"position": "p01", "assessment": "a", "own_choice": [0], "equivalent": ["b", "Z"], "confidence": "high",
         "grades": [{"label": "A", "grade": "mistake", "reason": "r"}, {"label": "B", "grade": "best", "reason": ""}]},
        {"position": "p02", "assessment": "a", "own_choice": [], "equivalent": [], "confidence": "odd",
         "grades": [{"label": "A", "grade": "terrible", "reason": "r"}]}]}
    results, problems = J.check_reply(out, items)
    assert list(results) == ["p01"] and problems == ["p02: no grade for A"]
    assert results["p01"]["equivalent"] == ["B"]
    mapping = {"A": {"key": "x", "candidates": ["a"], "probe_of": None},
               "B": {"key": "y", "candidates": ["b"], "probe_of": None}}
    assert J.consistency(mapping, results["p01"], "x") == ["its own choice is answer A, graded mistake"]
    assert J.consistency(mapping, results["p01"], "y") == []
    d = {"kind": "idle", "options": [{}, {}]}
    assert J.own_key({"own_choice": [5]}, d, lambda c: "k") is None
    assert J.own_key({"own_choice": [1]}, d, lambda c: "k") == "k"


def test_anonymize_hides_the_player():
    md = '> **opus (claude-code)** (9.28s): I, Opus, attack.\n- DUEL START — "Saffira (opus)" vs Blue-Eyes AI\n' \
         '> **rule:keep_lance**: rule why\n'
    out = J.anonymize(md, ["opus (claude-code)"], ["(opus)"])
    assert "opus" not in out.lower() and "9.28" not in out
    assert "> **player**:" in out and "> **rule:keep_lance**:" in out


# ---- aggregation ----

def synthetic_run(scores_by_pos, judge_model="opus"):
    """exam/run/answers/judge records where scores_by_pos[pid] = {candidate: (key, grade)}."""
    cands = ["opus", "sonnet", "haiku"]
    positions, answers, judged, prepared = [], [], [], {}
    for i, (pid, per) in enumerate(scores_by_pos.items()):
        positions.append({"id": pid, "game": "games/x", "decision": i + 1, "deck": "saffira" if i % 2 else "blackwing",
                          "kind": "idle", "group": "idle" if i % 3 else "chain", "sub": "main1", "turn": 1})
        prepared[pid] = {"status": "ok", "question": "q"}
        mine = {}
        for c in cands:
            key, _ = per[c]
            answers.append({"position": pid, "candidate": c, "status": "done", "key": key, "answer": key,
                            "why": f"{c} why", "seconds": {"opus": 4, "sonnet": 2, "haiku": 1}[c],
                            "cost_usd": {"opus": 0.1, "sonnet": 0.04, "haiku": 0.005}[c], "tokens": {"output": 10}})
            mine[c] = {"key": key, "answer": key, "why": f"{c} why"}
        items, mapping = J.blind(pid, mine, "s")
        grades = {}
        for label, m in mapping.items():
            grades[label] = {"grade": per[m["candidates"][0]][1], "reason": "r"}
        best_key = max(per.values(), key=lambda kg: J.SCORE[kg[1]])[0]
        judged.append({"position": pid, "judge": "opus", "status": "done", "answers_sha": J.answers_sha(mine),
                       "mapping": mapping, "own_key": best_key, "issues": [], "probes": [],
                       "result": {"grades": grades, "equivalent": [], "assessment": "a", "confidence": "high"}})
    run = {"candidates": {c: {"name": c, "type": "claude-code", "model": c} for c in cands}, "judges": ["opus"],
           "judge_profiles": {"opus": {"model": judge_model}}, "settings": {"games_from": "/nonexistent"}}
    return {"exam.json": {"name": "t", "positions": positions}, "run.json": run, "prepared.json": prepared,
            "answers.jsonl": answers, "judge.jsonl": judged, "games.jsonl": []}


def test_aggregation_scores_rates_and_pairs():
    per = {}
    for i in range(10):
        per[f"p{i:02d}"] = {"opus": ("a", "best"), "sonnet": ("a", "best") if i < 8 else ("b", "mistake"),
                            "haiku": ("c", "blunder") if i < 5 else ("a", "best")}
    s = E.summarize(synthetic_run(per))
    m = s["models"]
    assert m["opus"]["mean_score"] == 4 and m["opus"]["best"] == 1.0 and m["opus"]["mistake_rate"] == 0
    assert m["sonnet"]["mean_score"] == pytest.approx((8 * 4 + 2 * 1) / 10)
    assert m["haiku"]["blunder_rate"] == 0.5 and m["haiku"]["mistake_rate"] == 0.5
    assert m["opus"]["agreement"] == 1.0 and m["haiku"]["agreement"] == 0.5
    assert m["opus"]["cost_per_decision"] == pytest.approx(0.1) and m["haiku"]["latency_mean_s"] == 1
    pair = next(p for p in s["pairs"] if (p["a"], p["b"]) == ("opus", "haiku"))
    assert pair["diff"] == pytest.approx(2.0) and pair["a_better"] == 5 and pair["ties"] == 5
    assert pair["p_sign"] == pytest.approx(2 / 32)
    assert set(m["opus"]["by_group"]) == {"idle", "chain"} and set(m["opus"]["by_deck"]) == {"saffira", "blackwing"}
    assert s["recommendation"]["choice"] in ("sonnet", "opus")
    assert "opus" in E.report_md({**s, "sources": {}})


def test_self_preference_is_flagged():
    per = {}
    for i in range(8):  # opus alone and graded best every time; the others alone are never best
        per[f"p{i:02d}"] = {"opus": ("a", "best"), "sonnet": ("b", "mistake"), "haiku": ("c", "acceptable")}
    s = E.summarize(synthetic_run(per, judge_model="opus"))
    assert s["judge_checks"]["self_preference"] and "opus" in s["judge_checks"]["self_preference"]
    assert s["recommendation"]["confidence"] == "low"
    s = E.summarize(synthetic_run(per, judge_model="other"))
    assert not s["judge_checks"]["self_preference"]


def test_stats_helpers():
    assert E.sign_test(5, 0) == pytest.approx(2 / 32) and E.sign_test(0, 0) is None
    ci = E.bootstrap_ci([1, 2, 3, 4, 5] * 4)
    assert ci[0] < 3 < ci[1] and E.bootstrap_ci([1]) is None


# ---- the whole pipeline, scripted ----

def judge_policy(calls):
    def policy(req):
        calls.append(req["task"])
        if req["task"] == "exam-game":
            return {"summary": "s", "significant": 1, "mistakes": [
                {"decision": 1, "turn": 1, "severity": "major", "what": "w", "better": "b", "evidence": "e"}]}
        out = []
        for block in re.split(r"(?m)^# Position ", req["prompt"])[1:]:
            pid = block.split()[0]
            labels = re.findall(r"(?m)^([A-Z])\) ", block)
            out.append({"position": pid, "assessment": "scripted", "own_choice": [], "equivalent": [],
                        "confidence": "high", "grades": [{"label": x, "grade": "best" if x == "A" else "mistake",
                                                          "reason": "scripted"} for x in labels]})
        return {"positions": out}
    return policy


def test_scripted_run_end_to_end_with_resume(games, db, cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(E, "default_bench_run", lambda: None)
    exam = E.make_exam("t", cfg, db, ["saffira", "blackwing"], 6, seed=2, sources=[games])
    first_pos = exam["positions"][0]
    broken = {first_pos["id"]}
    calls = []

    def flaky(d):  # b can't answer the first position until it is "fixed"
        if broken and d["id"] == first_pos["decision"]:
            return None
        return {"choice": first_valid(d), "why": "b's reason"}

    cfg["backends"].update({
        "a": {"type": "scripted", "policy": lambda d: {"choice": first_valid(d), "why": "a's reason"}},
        "b": {"type": "scripted", "policy": flaky},
        "j": {"type": "scripted", "policy": judge_policy(calls)}})
    bench = tmp_path / "bench"
    rows = []
    for g in E.find_games([games], ["saffira", "blackwing"])[:2]:
        for c in ("a", "b"):
            rows.append({"status": "done", "deck": g["deck"], "backend": c, "opponent": "windbot:Blue-Eyes",
                         "game": 1, "result": "win", "turns": 3, "first": "player",
                         "player": {"log_dir": g["dir"]}})
    os.makedirs(bench)
    with open(bench / "results.jsonl", "w") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    folder = str(tmp_path / "run")
    run = E.ExamRun(exam, folder, cfg, db, ["a", "b"], ["j"], parallel=3, probe=0.0, games=1, games_from=str(bench),
                    probe_backends=False, say=lambda *a: None)
    s = run.run()
    answers = E.latest(E.load_jsonl(os.path.join(folder, "answers.jsonl")), ("position", "candidate"))
    asked_positions = [p["id"] for p in exam["positions"] if run.prepared[p["id"]]["status"] == "ok"]
    assert len(answers) == 2 * len(asked_positions)
    if first_pos["id"] in asked_positions:
        assert answers[(first_pos["id"], "b")]["status"] == "error"
        assert first_pos["id"] in s["incomplete"]
    assert s["graded"] == len(asked_positions) - (first_pos["id"] in asked_positions)
    assert os.path.isfile(os.path.join(folder, "report.md")) and os.path.isfile(os.path.join(folder, "summary.json"))
    judged_before = len(E.load_jsonl(os.path.join(folder, "judge.jsonl")))
    games_before = len(E.load_jsonl(os.path.join(folder, "games.jsonl")))
    assert games_before == 2 and s["games"]["a"]["games"] == 1 and s["games"]["a"]["significant_per_game"] == 1
    lines_before = len(E.load_jsonl(os.path.join(folder, "answers.jsonl")))

    broken.clear()  # resume: only the failed answer is asked again, and only its position is judged
    run = E.ExamRun(E.load_json(os.path.join(folder, "exam.json")), folder, cfg, db, ["a", "b"], ["j"], parallel=2,
                    probe=0.0, games=1, games_from=str(bench), probe_backends=False, say=lambda *a: None)
    s = run.run()
    lines = E.load_jsonl(os.path.join(folder, "answers.jsonl"))
    assert len(lines) == lines_before + (first_pos["id"] in asked_positions)
    redo = first_pos["id"] in asked_positions
    assert len(E.load_jsonl(os.path.join(folder, "judge.jsonl"))) == judged_before + redo
    assert len(E.load_jsonl(os.path.join(folder, "games.jsonl"))) == games_before
    assert s["graded"] == len(asked_positions) and not s["incomplete"]
    assert set(s["models"]) == {"a", "b"} and all(m["graded"] == len(asked_positions) for m in s["models"].values())
    # a and b always choose the same move, so every position shows one answer and both get the same grade
    rows = s["rows"]
    for pid in asked_positions:
        assert len({r["grade"] for r in rows if r["position"] == pid}) == 1
    run_info = E.load_json(os.path.join(folder, "run.json"))
    assert len(run_info["invocations"]) == 2 and run_info["prompts"]["saffira/playbook"]
    # the judge never saw a candidate's name
    for path in glob.glob(os.path.join(folder, "judge", "*.prompt.md")):
        with open(path) as f:
            text = f.read()
        assert "a's reason" in text or "b's reason" in text
    assert E.build(folder)["graded"] == s["graded"]


def test_prepare_excludes_what_rules_answer_now(games, db, cfg, tmp_path):
    exam = E.make_exam("t", cfg, db, ["saffira"], 4, seed=2, sources=[games])
    run = E.ExamRun(exam, str(tmp_path / "run"), cfg, db, ["random"], ["random"], probe_backends=False,
                    say=lambda *a: None)
    run.setup()
    first = exam["positions"][0]
    profile = run.profile("saffira")
    original = Rules.decide

    def decide(self, ctx):
        if ctx.d.get("id") == first["decision"] and ctx.kind == first["kind"]:
            return Decide([0], "new rule"), "rule:new_rule"
        return original(self, ctx)
    Rules.decide = decide
    try:
        prepared = run.prepare()
    finally:
        Rules.decide = original
    assert prepared[first["id"]]["status"] == "excluded" and "rule:new_rule" in prepared[first["id"]]["reason"]
    ok = [p for p in exam["positions"] if prepared[p["id"]]["status"] == "ok"]
    assert ok and all(prepared[p["id"]]["text"].startswith("A new session started") for p in ok)
    assert all("DECISION #" in prepared[p["id"]]["text"] for p in ok) and profile.name
