"""Applying a reviewer's reply: lessons (Known pitfalls) that pass the evidence check, section rewrites, verified-line
marks, and regression cases saved with the replay machinery (decks/<deck>/tests/<name>.json)."""

from __future__ import annotations

import contextlib
import difflib
import io
import json
import os
import re

from ..agent import replay
from ..agent.validate import validate
from . import logs
from . import playbook as pb

# Errors that mean "you're out of model usage" (the agent then played on with the fallback, so the game isn't the
# backend's): the claude CLI's wordings, HTTP 429s, and the APIs' quota and overload errors.
LIMIT = re.compile(r"usage limit|rate[ _-]?limit|hit your (usage |session |weekly )?limit|limit (reached|exceeded)"
                   r"|quota|credit balance|out of (extra )?usage|too many requests|overloaded|\b429\b", re.I)


class UsageLimited(Exception):
    """The model service refused for usage or rate limits: checkpoint and stop (resume after the reset)."""


def limited(error) -> bool:
    return bool(error) and LIMIT.search(str(error)) is not None


def game_usage_limited(game_dir: str) -> str | None:
    """A usage/rate-limit error the player's backend hit during a game (the fallback then played those decisions)."""
    try:
        with open(os.path.join(game_dir, "prompts.jsonl"), encoding="utf-8") as f:
            for line in f:
                err = (json.loads(line).get("info") or {}).get("error")
                if limited(err):
                    return err
    except (OSError, ValueError):
        return None
    return None


def apply_lessons(text: str, lessons: list[dict], tag: str, evidence: pb.Evidence) -> tuple[str, list, list]:
    """Add the lessons whose evidence checks out as Known pitfalls tagged *(tag)*. Returns (text, accepted, rejected);
    each entry is {"text", "severity", "notes"}."""
    accepted, rejected = [], []
    for lesson in lessons or []:
        body = (lesson.get("text") or "").strip()
        if not body:
            continue
        if already_there(body, text):
            rejected.append({"text": body, "severity": lesson.get("severity"), "decisions": lesson.get("decisions")
                             or [], "notes": ["the playbook already has this lesson"]})
            continue
        ok, notes = evidence.verify(lesson.get("evidence") or [])
        entry = {"text": body, "severity": lesson.get("severity"), "notes": notes,
                 "decisions": lesson.get("decisions") or []}
        (accepted if ok else rejected).append(entry)
    if accepted:
        text = pb.add_lessons(text, tag, [e["text"] for e in accepted])
    return text, accepted, rejected


def already_there(lesson: str, text: str) -> bool:
    """The same lesson (give or take wording) is already in the playbook: the reviewer repeated itself."""
    want = pb.norm(pb.clean_lesson(lesson))
    for line in text.splitlines():
        have = pb.norm(pb.clean_lesson(re.sub(r"\s*\*\(.*\)\*\s*$", "", line)))  # without its *(tag)*
        if have and (have == want or len(want) > 40 and difflib.SequenceMatcher(None, want, have).ratio() > 0.85):
            return True
    return False


def apply_sections(text: str, sections: list[dict]) -> tuple[str, list[str]]:
    return pb.apply_sections(text, sections or [])


def slug_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "case").lower()).strip("-")
    return s[:40] or "case"


def save_cases(profile, game_dir: str, cases: list[dict], prefix: str = "", limit: int = 3
               ) -> tuple[list[dict], list[str]]:
    """Check each proposed case (the first `limit`) against the logged decision (it exists, its choices are legal for
    it, and the choice actually made is rejected or not expected) and save it with replay.save_case. Returns (saved,
    problems)."""
    saved, problems = [], []
    tests_dir = os.path.join(profile.dir, "tests")
    for case in (cases or [])[:limit]:
        did = int(case.get("decision") or 0)
        d = logs.decision_message(game_dir, did)
        if d is None:
            problems.append(f"case {case.get('name')!r}: no decision #{did} in the log")
            continue
        expect = [list(map(int, c)) for c in case.get("expect") or [] if isinstance(c, list)]
        reject = [list(map(int, c)) for c in case.get("reject") or [] if isinstance(c, list)]
        bad = [c for c in expect + reject if c and validate(d, c)]
        if bad or not (expect or reject):
            problems.append(f"case {case.get('name')!r}: " + (f"choices {bad} aren't legal for decision #{did}"
                                                               if bad else "no expect/reject"))
            continue
        reply = logs.reply_for(game_dir, did) or {}
        made = reply.get("choice")
        if made is not None and expect and made in expect:
            problems.append(f"case {case.get('name')!r}: the player already chose {made} at #{did}")
            continue
        name = slug_name(prefix + (case.get("name") or f"decision-{did}"))
        base, n = name, 2
        while os.path.exists(os.path.join(tests_dir, f"{name}.json")):
            name, n = f"{base}-{n}", n + 1
        try:
            msgs = replay.load_messages(game_dir, did)
        except (OSError, LookupError) as e:
            problems.append(f"case {name}: {e}")
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            path = replay.save_case(profile, name, game_dir, did, msgs, expect, reject, case.get("note") or "")
        saved.append({"name": name, "decision": did, "expect": expect, "reject": reject, "note": case.get("note"),
                      "path": path, "made": made})
    return saved, problems
