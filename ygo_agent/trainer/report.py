"""train-report.md: what a training run did and what a human should look at."""

from __future__ import annotations

import collections
import os
import re

from . import playbook as pb


def money(x) -> str:
    return f"${x:.2f}" if isinstance(x, (int, float)) else "?"


def minutes(s) -> str:
    s = float(s or 0)
    return f"{s / 60:.0f} min" if s >= 60 else f"{s:.0f} s"


def write(trainer) -> str:
    ws = trainer.ws
    st = ws.state
    steps = st.get("steps", {})
    deck = st.get("deck", {})
    opts = st.get("options", {})
    out = [f"# Training report: {deck.get('name', trainer.o.name)}", ""]
    out.append(f"Status: **{st.get('status')}**. Reviewer: {opts.get('backend')}; player: "
               f"{opts.get('player_backend')}; rules {opts.get('rules')}; opponents: "
               f"{', '.join(st.get('pool') or opts.get('opponents') or [])}.")
    text = trainer.playbook()
    out.append(f"Playbook: `{os.path.relpath(trainer.playbook_path, os.path.dirname(trainer.deck_dir))}`, "
               f"{pb.size_kb(text)} KB" + (f" ({'; '.join(pb.problems(text))})" if pb.problems(text) else "") + ".")
    out.append(f"Spent {money(ws.spent)}" + (f" of a {money(ws.budget)} budget" if ws.budget is not None else "") +
               f" (API-price equivalents; a Claude Code subscription isn't billed per call) in "
               f"{minutes(st.get('elapsed_s'))} of running time.")
    out.append("")

    study = steps.get("study", {}).get("result")
    if study:
        checks = study.get("card_checks") or {}
        out += ["## Study", "",
                f"- Draft playbook: {study.get('size_kb')} KB (`train/study/playbook-draft.md`), {study.get('lines')} "
                f"lines to test, {checks.get('verified', 0)}/{checks.get('total', 0)} script citations verified "
                "(`train/study/card-checks.md`).",
                f"- Go first: {study.get('go_first')} — {study.get('go_first_reason') or ''}"]
        if study.get("problems"):
            out.append(f"- Problems: {', '.join(study['problems'])}")
        out.append("")

    out += ["## Rounds", "", "| round | lab hands | lines verified | games | W-L-D | major mistakes | lessons | "
            "playbook |", "|---|---|---|---|---|---|---|---|"]
    r = 1
    while f"r{r}.summary" in steps or f"r{r}.lab.plan" in steps:
        summary = steps.get(f"r{r}.summary", {}).get("result") or {}
        hands = len(steps.get(f"r{r}.lab.plan", {}).get("result") or [])
        verified = [v for v in ((summary.get("lab") or {}).get("verification") or []) if v.get("status") == "verified"]
        games = [steps[k]["result"] for k in steps if k.startswith(f"r{r}.game.")]
        c = collections.Counter(g.get("result") for g in games)
        out.append(f"| {r}{'' if summary else ' (unfinished)'} | {hands} | {len(verified)} | {len(games)} | "
                   f"{c['win']}-{c['loss']}-{c['draw']} | {summary.get('significant', '–')} | "
                   f"{summary.get('lessons', '–')} | {summary.get('playbook_kb', '–')} KB |")
        r += 1
    out.append("")

    games = sorted(((k, v["result"]) for k, v in steps.items() if ".game." in k),
                   key=lambda kv: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", kv[0])])
    if games:
        out += ["## Games", "", "| game | opponent | went | result | turns | invalid | fallback | cost | log |",
                "|---|---|---|---|---|---|---|---|---|"]
        for _, g in games:
            s = g.get("stats") or {}
            out.append(f"| {g.get('id')} | {g.get('opponent')} | {'first' if g.get('first') else 'second'} | "
                       f"{g.get('result')} | {g.get('turns')} | "
                       f"{s.get('invalid_replies', '?')}/{s.get('replies', '?')} "
                       f"| {s.get('fallback_rate', '?')} | {money(g.get('cost'))} | `train/{g.get('log')}` |")
        out.append("")

    verification = st.get("verification") or {}
    lines = st.get("lines") or []
    if lines:
        out += ["## Lines (lab verification)", "", "| id | line | going | status | round | why |",
                "|---|---|---|---|---|---|"]
        for line in lines:
            v = verification.get(line["id"], {})
            why = (v.get("reason") or "").replace("|", "/").replace("\n", " ")
            out.append(f"| {line['id']} | {line['name']} | {line.get('going')} | {v.get('status', 'untested')} | "
                       f"{v.get('round', '')} | {why[:220]} |")
        out.append("")

    errors = [(k.split(".")[0], e) for k, v in steps.items() if k.endswith(".lab.review")
              for e in (v.get("result") or {}).get("player_errors") or []]
    if errors:
        out += ["## Where the player didn't follow a correct line (lab)", "",
                "The same error in two rounds, after a wording fix, is a case for a hard rule in rules.py.", ""]
        out += [f"- ({r}) {e}" for r, e in errors]
        out.append("")

    lessons = st.get("lessons") or []
    if lessons:
        out += ["## Pitfalls added", ""]
        for x in lessons:
            out.append(f"- ({x.get('source')}, {x.get('severity') or ''}) {x['text']}")
        out.append("")
    rejected = st.get("rejected_lessons") or []
    if rejected:
        out += ["## Pitfalls rejected (their evidence didn't check out against the scripts or logs)", ""]
        for x in rejected:
            out.append(f"- ({x.get('source')}) {x['text']}  \n  evidence: {'; '.join(x.get('notes') or ['none'])}")
        out.append("")
    tests = st.get("tests_saved") or []
    final = steps.get("final.tests", {}).get("result")
    if tests or final:
        out += ["## Regression cases", ""]
        for t in tests:
            out.append(f"- `{t['name']}` ({t['game']} #{t['decision']}): {t.get('note') or ''} expect {t['expect']} "
                       f"reject {t['reject']}")
        if final:
            out.append(f"\nFinal run against the trained playbook: {final.get('passed', 0)}/{final.get('cases', 0)} "
                       f"cases passed every one of {final.get('repeat', 0)} runs (`train/tests-final.txt`)"
                       + (f"; failed: {', '.join(final['failed'])}" if final.get("failed") else "") + ".")
        out.append("")

    gates = [(k, v["result"]["gate"]) for k, v in steps.items() if isinstance(v.get("result"), dict)
             and v["result"].get("gate")]
    if gates:
        out += ["## Edits checked against the regression cases", "",
                "Each condense and section rewrite was replayed against the saved cases with the player's backend "
                "(runs passed, before → after); a rewrite that made them fail more often got one fix-up try, else the "
                "previous text was kept.", "", "| step | edit | before | after | fix-up | kept |", "|---|---|---|---|---|---|"]
        for k, gt in gates:
            out.append(f"| {k} | {gt.get('what')} | {gt.get('before')} | {gt.get('after')} | {gt.get('revised', '–')} | "
                       f"{gt.get('kept')}{' (' + ', '.join(gt['failures']) + ')' if gt.get('failures') else ''} |")
        out.append("")

    mistakes = st.get("mistakes") or []
    if mistakes:
        out += ["## Mistakes by model", "", "| player | mistakes | major | no judgment | already covered by the playbook |",
                "|---|---|---|---|---|"]
        for player in sorted({m.get("player") for m in mistakes}):
            ms = [m for m in mistakes if m.get("player") == player]
            out.append(f"| {player} | {len(ms)} | {sum(m.get('severity') == 'major' for m in ms)} | "
                       f"{sum(bool(m.get('no_judgment')) for m in ms)} | {sum(bool(m.get('covered')) for m in ms)} |")
        out.append("")
    proposals = st.get("rule_proposals") or []
    if proposals:
        written = [p for p in proposals if p.get("written")]
        good = [p for p in proposals if p.get("qualifies")]
        out += ["## Rule proposals", "",
                f"{len(proposals)} proposed, {len(good)} qualify (no judgment, made by the play model "
                f"{trainer.play_model()} although the playbook covered it, proven by a saved case), {len(written)} "
                "written to rules.py. Details and the code: `train/rule-proposals.md`.", ""]
        out += [f"- {'written' if p.get('written') else 'qualifies' if p.get('qualifies') else 'not a rule'}: "
                f"{p.get('rule')}" + (f" — {'; '.join(p['reasons'])}" if p.get("reasons") else "") for p in proposals]
        out.append("")

    out += ["## Cost and time by phase", "", "| kind | calls | cost | time |", "|---|---|---|---|"]
    by = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for e in st.get("ledger") or []:
        b = by[e["kind"]]
        b[0] += 1
        b[1] += e.get("cost") or 0
        b[2] += e.get("seconds") or 0
    for kind, (n, cost, secs) in by.items():
        out.append(f"| {kind} | {n} | {money(cost)} | {minutes(secs)} |")
    out.append("")

    settled = {x["question"] for x in st.get("settled_questions") or []}
    questions = [q for q in dict.fromkeys((study or {}).get("open_questions", []) + (st.get("open_questions") or []))
                 if q not in settled]
    out += ["## For a human to check", ""]
    if settled:
        out.append(f"- {len(settled)} open question(s) were settled by later labs and games (`state.json`, "
                   "settled_questions).")
    out.append("- Read the playbook against the card scripts; the lines still marked *(unverified)* haven't been "
               "seen working in the engine.")
    if os.path.isfile(os.path.join(ws.dir, "general-proposals.md")):
        out.append("- `train/general-proposals.md`: proposed lessons for every deck (not applied).")
    if os.path.isfile(os.path.join(ws.dir, "rule-proposals.md")):
        out.append("- `train/rule-proposals.md`: proposed hard rules and whether they qualify.")
    out += [f"- {q}" for q in questions[-15:]]
    out.append("")
    path = os.path.join(ws.dir, "train-report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path
