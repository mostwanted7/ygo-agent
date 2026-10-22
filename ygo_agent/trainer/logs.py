"""Reading game logs (game.md / meta.json / game.jsonl) for reviews: a condensed log, the problems the engine and
the agent flagged, and the decision messages a regression case needs."""

from __future__ import annotations

import json
import os
import re

DECISION = re.compile(r"^\*\*Decision #(\d+)\*\* — (.*)$")
TAG = re.compile(r"^> \*\*(.+?)\*\*(?: \(([\d.]+)s\))?: ?(.*)$")
PROBLEM_WORDS = ("FALLBACK", "engine can't take", "engine rejected", "gave no usable answer", "invalid reply",
                 "took over", "heuristic answered", "the heuristic answers")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def meta(game_dir: str) -> dict:
    try:
        with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def blocks(md: str):
    """Yield ("event", line) and ("decision", {id, question, options, chosen, tag, why, plan, notes}) in order."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = DECISION.match(line)
        if not m:
            yield "event", line
            i += 1
            continue
        d = {"id": int(m.group(1)), "question": m.group(2), "options": [], "chosen": [], "tag": "", "why": "",
             "plan": "", "notes": []}
        i += 1
        in_plan = False
        while i < len(lines):
            text = lines[i]
            if DECISION.match(text) or text.startswith("## "):
                break
            if in_plan and text.strip() and not text.startswith((">", "- ", "*")):
                d["plan"] += "\n" + text.strip()  # a multi-line plan's continuation lines carry no ">"
                i += 1
                continue
            in_plan = False
            if text.strip() and not text.startswith(">") and (d["tag"] or not text.startswith("  - ")):
                break  # the events after the decision
            if text.startswith("  - "):
                opt = text[4:]
                chosen = opt.startswith("✅")
                opt = opt.removeprefix("✅").strip()
                d["options"].append(opt)
                if chosen:
                    d["chosen"].append(opt)
            elif TAG.match(text):
                t = TAG.match(text)
                d["tag"], d["why"] = t.group(1), t.group(3).strip()
            elif text.startswith("> *Plan:*"):
                d["plan"] = text.removeprefix("> *Plan:*").strip()
                in_plan = True
            elif text.startswith("> ⚠️") or text.startswith("> ✎"):
                d["notes"].append(text[2:].lstrip("⚠️✎ ").strip())
            i += 1
        yield "decision", d


def condense(md: str, why_chars: int = 160) -> str:
    """game.md without the options that weren't chosen: events, then one line per decision with the choice, the
    reason (cut short), the plan when it changes, and any warning. About half the size."""
    out = []
    last_plan = None
    for kind, item in blocks(md):
        if kind == "event":
            line = item.rstrip()
            if not line or line.startswith("# ") or "draws" in line and "card(s)" in line and "Opponent" in line:
                continue
            if line.startswith("> ✎") or line.startswith("> ✍"):
                out.append("  NOTE: " + line[2:].lstrip("✎✍ ").strip())
            elif line.startswith("## "):
                out.append("\n" + line)
            else:
                out.append(line)
            continue
        d = item
        q = re.sub(r"\s+Reply .*$", "", d["question"]).strip()
        q = q[:110] + "…" if len(q) > 110 else q
        chosen = "; ".join(c.split("` ", 1)[-1] if c.startswith("`[") else c for c in d["chosen"]) or "(pass / none)"
        why = d["why"][:why_chars] + ("…" if len(d["why"]) > why_chars else "")
        tag = "" if d["tag"] and not any(w in d["tag"] for w in ("FALLBACK", "rule", "auto")) else f" [{d['tag']}]"
        out.append(f"  #{d['id']} {q} → {chosen}{tag}" + (f" — {why}" if why else ""))
        if d["plan"] and d["plan"] != last_plan:
            last_plan = d["plan"]
            plan = re.sub(r"\s*\n\s*", " / ", d["plan"])
            out.append(f"    plan: {plan[:400]}" + ("…" if len(plan) > 400 else ""))
        for n in d["notes"]:
            out.append(f"    ⚠ {n}")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def problems(md: str) -> list[str]:
    """Decisions the fallback answered or that carry a warning (invalid replies, engine rejections, timeouts)."""
    out = []
    for kind, item in blocks(md):
        if kind == "event":
            if item.startswith("> ✎") and any(w in item for w in PROBLEM_WORDS):
                out.append(item[2:].lstrip("✎ ").strip())
            continue
        if "FALLBACK" in item["tag"] or item["notes"]:
            what = "; ".join(item["notes"]) or item["tag"]
            out.append(f"Decision #{item['id']}: {what}")
    return out


def decision_text(md: str, decision_id: int, before: int = 0) -> str:
    """The raw game.md text of a decision (its question, every option, the reason), and of the `before` decisions
    before it with the events in between; "" when it isn't in the log."""
    lines = md.splitlines()
    starts = [(int(m.group(1)), i) for i, line in enumerate(lines) if (m := DECISION.match(line))]
    at = next((k for k, (did, _) in enumerate(starts) if did == decision_id), None)
    if at is None:
        return ""
    first = starts[max(0, at - before)][1]
    end = starts[at + 1][1] if at + 1 < len(starts) else len(lines)
    for i in range(starts[at][1] + 1, end):  # stop at the next turn heading too
        if lines[i].startswith("## "):
            end = i
            break
    return "\n".join(lines[first:end]).strip()


def decision_count(md: str) -> int:
    return sum(1 for kind, _ in blocks(md) if kind == "decision")


def turns(md: str) -> list[str]:
    return re.findall(r"(?m)^## (TURN \d+.*)$", md)


def decision_message(game_dir: str, decision_id: int) -> dict | None:
    """The raw decision message (game.jsonl) with that id, for checking a test case's choices."""
    try:
        with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                msg = rec.get("msg") or {}
                if rec.get("kind") == "decide" and msg.get("id") == decision_id:
                    return msg
    except (OSError, ValueError):
        return None
    return None


def reply_for(game_dir: str, decision_id: int) -> dict | None:
    try:
        with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("kind") == "reply" and (rec.get("msg") or {}).get("id") == decision_id:
                    return rec["msg"]
    except (OSError, ValueError):
        return None
    return None
