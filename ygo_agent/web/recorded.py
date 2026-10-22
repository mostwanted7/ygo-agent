"""Recorded games (games/<name>/) for the panel's game browser, replays and demo mode.

A recorded game becomes the same bus messages a live one publishes. They are rebuilt from game.jsonl (events,
decisions, and the replies in newer logs), game.md (every decision's choice, source, reasoning and plan, in old and
new logs alike), prompts.jsonl (the backend's own reply, time and tokens) and feedback.md.
"""

import json
import os
import re
import threading

from ..agent.gamelog import one_line, same_pick
from .render import Renderer

DECISION = re.compile(r"^\*\*Decision #(\d+)\*\* — (.*)$")
OPTION = re.compile(r"^  - (✅ )?`\[(\d+)\]` (.*)$")
YES_NO = re.compile(r"^  - ✅ (YES|NO)$")
TAG = re.compile(r"^> \*\*(.+?)\*\*(?: \(([\d.]+)s\))?(?::\s?(.*))?$")
PLAN = re.compile(r"^> \*Plan:\*\s?(.*)$")
NOTE = re.compile(r"^> ⚠️\s?(.*)$")
TITLE = re.compile(r"^# (.+?) — game started (.+)$")
FEEDBACK = re.compile(r"^- \((.*?)\) (.*)$")
AFTER = re.compile(r"decision #(\d+)")
SAFE_NAME = re.compile(r"^[\w.+-]+$")
RESULTS = {0: "win", 1: "loss", 2: "draw"}


def game_id(name):
    return f"rec:{name}"


def parse_md(path):
    """{decision id: {question, options {i: text}, chosen, tag, seconds, why, plan, note}} from a game.md."""
    blocks, cur, field = {}, None, None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return blocks
    for line in lines:
        m = DECISION.match(line)
        if m:
            cur = {"question": m.group(2), "options": {}, "chosen": [], "tag": None}
            blocks[int(m.group(1))] = cur
            field = None
            continue
        if cur is None:
            continue
        if cur["tag"] is None:  # the question and options, up to the "> **source**: why" line
            m = OPTION.match(line)
            if m:
                cur["options"][int(m.group(2))] = m.group(3)
                if m.group(1):
                    cur["chosen"].append(int(m.group(2)))
            elif YES_NO.match(line):
                cur["chosen"] = [1] if line.endswith("YES") else [0]
            elif (m := TAG.match(line)):
                cur["tag"], cur["why"] = m.group(1), (m.group(3) or "").strip()
                cur["seconds"] = float(m.group(2)) if m.group(2) else None
                field = "why"
            elif line and not line.startswith("  - "):
                cur = None  # not a decision block after all
            continue
        if not line:
            cur = None
        elif line == ">":
            field = None
        elif (m := PLAN.match(line)):
            cur["plan"], field = m.group(1), "plan"
        elif (m := NOTE.match(line)):
            cur["note"], field = m.group(1), "note"
        elif field:
            cur[field] = (cur.get(field) or "") + "\n" + line
    return blocks


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def read_title(game_dir):
    """{deck_name, started} from game.md's title line: where logs from before meta.json keep them."""
    try:
        with open(os.path.join(game_dir, "game.md"), encoding="utf-8") as f:
            m = TITLE.match(f.readline().strip())
    except OSError:
        return {}
    return {"deck_name": m.group(1), "started": m.group(2)} if m else {}


def usage(info):
    """prompts.jsonl info in the normalized form (logs from before the backends refactor have Claude's raw usage)."""
    if not info:
        return None
    out = {k: info[k] for k in ("seconds", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
                                "cost_usd", "error") if info.get(k) is not None}
    raw = info.get("usage")
    if isinstance(raw, dict):
        out.setdefault("input_tokens", raw.get("input_tokens") or 0)
        out.setdefault("output_tokens", raw.get("output_tokens") or 0)
        out.setdefault("cache_read_tokens", raw.get("cache_read_input_tokens") or 0)
        out.setdefault("cache_write_tokens", raw.get("cache_creation_input_tokens") or 0)
    return out or None


def source_of(tag, record):
    if record and record.get("source"):
        return "backend" if record["source"] == "llm" else record["source"]
    if not tag:
        return "fallback" if record and record.get("choice") is None else "auto"
    if tag == "auto" or tag.startswith("rule"):
        return tag
    if tag.startswith("FALLBACK"):
        return "fallback"
    return "backend"


def read_feedback(game_dir):
    notes = []
    try:
        with open(os.path.join(game_dir, "feedback.md"), encoding="utf-8") as f:
            for line in f:
                m = FEEDBACK.match(line.rstrip("\n"))
                if m:
                    after = AFTER.search(m.group(1))
                    notes.append({"context": m.group(1), "text": m.group(2),
                                  "after": int(after.group(1)) if after else None})
    except OSError:
        pass
    return notes


def load_game(game_dir, db, name=None):
    """The bus messages of a recorded game, in order, rendered like live ones."""
    name = name or os.path.basename(os.path.realpath(game_dir))
    gid = game_id(name)
    rows = read_jsonl(os.path.join(game_dir, "game.jsonl"))
    md = parse_md(os.path.join(game_dir, "game.md"))
    meta = read_json(os.path.join(game_dir, "meta.json"))
    prompts = {}
    for p in read_jsonl(os.path.join(game_dir, "prompts.jsonl")):
        prev = prompts.get(p.get("id"))
        # A corrective re-ask is a second line for the same decision: keep its answer, add up the time.
        info = usage(p.get("info")) or {}
        if prev and prev["usage"]:
            for k, v in prev["usage"].items():
                if isinstance(v, (int, float)) and isinstance(info.get(k), (int, float)):
                    info[k] = round(info[k] + v, 4)
        prompts[p.get("id")] = {"reply": p.get("reply") or {}, "usage": info}
    replies = {r["msg"].get("id"): r["msg"] for r in rows if r.get("kind") == "reply"}
    advices = {r["msg"].get("id"): r["msg"] for r in rows if r.get("kind") == "advice"}  # coach games
    title = read_title(game_dir)
    label = (meta.get("backend") or {}).get("label")
    mode = meta.get("mode", "play")
    t0 = rows[0]["ts"] if rows else 0
    base = {"game_id": gid, "seat": 0}
    out = [{**base, "type": "game_start", "ts": t0, "deck": meta.get("deck"), "name": name, "dir": os.path.abspath(game_dir),
            "deck_name": meta.get("deck_name") or title.get("deck_name"), "recorded": True}]
    start = next((r["msg"] for r in rows if r.get("kind") == "event" and r["msg"].get("e") == "start"), {})
    names = start.get("names") or []
    known = {"opponent": names[1] if len(names) > 1 else None, "first": start.get("first"),
             "started": title.get("started"), "mode": "play"}
    meta_msg = {**{k: v for k, v in known.items() if v is not None}, **meta}
    if meta_msg:
        out.append({**base, "type": "meta", "ts": t0, **meta_msg})
    notes = read_feedback(game_dir)

    def reply_for(d, ts):
        did = d["id"]
        block, record, prompt = md.get(did) or {}, replies.get(did), prompts.get(did) or {}
        answer = prompt.get("reply") or {}
        source = source_of(block.get("tag"), record)
        choice = block.get("chosen") if block else None
        if not choice:
            choice = (record or {}).get("choice")
            if choice is None and source == "backend":
                choice = answer.get("choice")
            if d.get("kind") == "announce_card" and choice:  # replies carry the code itself
                choice = [d["options"].index(choice[0])] if choice[0] in d.get("options", []) else choice
        backend = source in ("backend", "pilot")
        msg = {**base, "type": "reply", "ts": ts, "id": did, "choice": choice or [], "source": source,
               "sent": (record or {}).get("choice", choice),
               "why": (answer.get("why") if backend and answer.get("why") else block.get("why")) or "",
               "plan": (answer.get("plan") if backend and answer.get("plan") else block.get("plan")) or None,
               "label": (block.get("tag") if source == "backend" else None) or label,
               "seconds": block.get("seconds") or (prompt.get("usage") or {}).get("seconds"),
               "note": block.get("note")}
        if prompt.get("usage") and source != "human":
            msg["usage"] = prompt["usage"]
        for key in ("say", "suggested", "trivial", "advised"):
            if record and record.get(key) is not None:
                msg[key] = record[key]
        advice = advices.get(did)
        if advice is not None:  # a coach game: the coach's advice, before or after the human's own move
            note = {**base, "type": "advice", "ts": ts, **advice, **({"usage": prompt["usage"]} if prompt.get("usage") else {})}
            human = []
            if advice.get("choice") is not None:
                human = [{**base, "type": "human_choice", "ts": ts, "id": did, "choice": msg["choice"],
                          "advised": advice["choice"],
                          "matched": same_pick(msg["choice"], advice["choice"], advice.get("kind"))}]
            return [msg, note, *human] if advice.get("late") else [note, msg, *human]
        extra = []
        suggested = (record or {}).get("suggested")  # old copilot logs: the agent's suggestion the pilot overrode
        if suggested is not None or (mode == "copilot" and d.get("kind") not in ("place", "go_first")):
            advised = suggested if suggested is not None else msg["choice"]
            extra.append({**base, "type": "advice", "ts": ts, "id": did, "choice": advised, "why": msg["why"],
                          "plan": msg["plan"], "label": label, "source": "backend", "late": False})
            extra.append({**base, "type": "human_choice", "ts": ts, "id": did, "choice": msg["choice"],
                          "advised": advised, "matched": msg["choice"] == advised})
        return [*extra[:1], msg, *extra[1:]]

    pending = None
    for i, row in enumerate(rows):
        kind, msg, ts = row.get("kind"), row.get("msg") or {}, row.get("ts", t0)
        if kind == "reply" or (pending and kind != "reply"):
            if pending:
                out += reply_for(pending, ts)
                out += [{**base, "type": "feedback_ack", "ts": ts, "who": "Note", **n}
                        for n in notes if n["after"] == pending["id"]]
                pending = None
            if kind == "reply":
                continue
        if kind == "event":
            out.append({**base, "type": "event", "ts": ts, "ev": msg})
            if msg.get("e") == "win" and not any(m["type"] == "game_end" for m in out):
                out.append({**base, "type": "game_end", "ts": ts, "result": RESULTS.get(msg.get("result"), "draw"),
                            "reason": msg.get("reason")})
        elif kind == "decide" and msg.get("kind") != "game_over":
            block = md.get(msg.get("id")) or {}
            d = {**base, "type": "decision", "ts": ts, "decision": msg}
            opts = msg.get("options") or []
            if block.get("question") and len(block["options"]) == len(opts):
                d["question"] = block["question"]
                d["options"] = [block["options"][k] for k in range(len(opts))]
            out.append(d)
            pending = msg
    if pending:
        out += reply_for(pending, rows[-1].get("ts", t0) if rows else t0)
    review = os.path.join(game_dir, "review.md")
    if os.path.isfile(review):  # coach games: the review written after the game
        with open(review, encoding="utf-8") as f:
            out.append({**base, "type": "review", "ts": rows[-1].get("ts", t0) if rows else t0, "markdown": f.read(),
                        "path": os.path.abspath(review)})
    renderer = Renderer(db)
    return [renderer(m) for m in out]


class Library:
    """The games under a games folder, with summaries cached by file size and time."""

    def __init__(self, games_dir):
        self.games_dir = games_dir
        self._cache = {}
        self._lock = threading.Lock()

    def path(self, name):
        """The folder of a recorded game, or None (names come from URLs, so nothing outside games_dir)."""
        if not name or not SAFE_NAME.match(name) or name in (".", ".."):
            return None
        path = os.path.join(self.games_dir, name)
        return path if os.path.isfile(os.path.join(path, "game.jsonl")) else None

    def names(self):
        try:
            entries = sorted(os.listdir(self.games_dir), reverse=True)
        except OSError:
            return []
        return [n for n in entries if n != "latest" and self.path(n)]

    def latest(self):
        try:
            return os.readlink(os.path.join(self.games_dir, "latest"))
        except OSError:
            return None

    def list(self):
        latest = self.latest()
        out = []
        for name in self.names():
            s = self.summary(name)
            if s:
                out.append({**s, "latest": name == latest})
        return out

    def summary(self, name):
        path = self.path(name)
        if path is None:
            return None
        try:
            st = os.stat(os.path.join(path, "game.jsonl"))
        except OSError:
            return None
        key = (st.st_size, st.st_mtime)
        with self._lock:
            hit = self._cache.get(name)
            if hit and hit[0] == key:
                return hit[1]
        summary = self._summarize(name, path, st)
        with self._lock:
            self._cache[name] = (key, summary)
        return summary

    def _summarize(self, name, path, st):
        meta = read_json(os.path.join(path, "meta.json"))
        s = {"name": name, "game_id": game_id(name), "deck": meta.get("deck"), "deck_name": meta.get("deck_name"),
             "opponent": meta.get("opponent"), "result": meta.get("result"), "mode": meta.get("mode", "play"),
             "backend": (meta.get("backend") or {}).get("label"), "started": meta.get("started"),
             "first": meta.get("first"), "size": st.st_size, "mtime": st.st_mtime}
        decisions = turns = 0
        with open(os.path.join(path, "game.jsonl"), encoding="utf-8") as f:
            for line in f:
                if '"kind": "decide"' in line and '"kind": "place"' not in line and '"game_over"' not in line:
                    decisions += 1
                if '"e": "new_turn"' in line or '"e": "start"' in line or '"e": "win"' in line:
                    try:
                        ev = json.loads(line)["msg"]
                    except (ValueError, KeyError):
                        continue
                    if ev.get("e") == "new_turn":
                        turns = max(turns, ev.get("turn") or 0)
                    elif ev.get("e") == "start" and not s["opponent"]:
                        names = ev.get("names") or []
                        s["opponent"] = names[1] if len(names) > 1 else None
                        s["first"] = ev.get("first")
                    elif ev.get("e") == "win" and not s["result"]:
                        s["result"] = RESULTS.get(ev.get("result"), "draw")
        s["decisions"], s["turns"] = decisions, turns
        if not s["deck_name"] or not s["started"]:
            title = read_title(path)
            s["deck_name"] = s["deck_name"] or title.get("deck_name")
            s["started"] = s["started"] or title.get("started")
        s["notes"] = len(read_feedback(path))
        return s

    def load(self, name, db):
        path = self.path(name)
        return load_game(path, db, name) if path else None


def decision_turn(game_dir, decision_id):
    """The turn a logged decision was made in (for tagging a note added afterwards)."""
    for row in read_jsonl(os.path.join(game_dir, "game.jsonl")):
        msg = row.get("msg") or {}
        if row.get("kind") == "decide" and msg.get("id") == decision_id:
            return (msg.get("state") or {}).get("turn")
    return None


def append_feedback(game_dir, text, decision=None, turn=None):
    """A note about a recorded game, in the same feedback.md format as a `!note` typed during the duel."""
    if decision is not None and turn is None:
        turn = decision_turn(game_dir, decision)
    context = f"turn {turn if turn is not None else '?'}, right after decision #{decision if decision else '?'}"
    path = os.path.join(game_dir, "feedback.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- ({context}; from Web panel) {one_line(text)}\n")
    return {"n": len(read_feedback(game_dir)), "context": context}
