"""Rule ablation: does the play model still need each of a deck's hard rules?

    ygo-agent test --deck saffira --ablate-rules [--backend sonnet] [--repeat 2]

Rules are calibrated to the play model, so re-run this when the model changes. For each rule in the deck's rules.py
the probes are the saved cases that prove it (its @cases), the saved cases it answers itself, and, when that leaves
none, the latest decisions it answered in the game logs (expected: what the rule chose). Each probe is replayed with
that one rule disabled. A rule the model gets right on every run without it is no longer needed; a @shortcut rule
(it only skips prompts that never matter) is reported but kept.
"""

import copy
import glob
import json
import os

from .. import paths
from . import replay
from .describe import Describer
from .gamelog import BOLD, DIM, GREEN, RED, YELLOW, paint
from .rules import Context, Rules

MAX_LOGGED = 3  # logged decisions per rule, from different games, when no saved case covers it


def fires(rule, decision, db, profile):
    """Does `rule` answer this decision by itself?"""
    try:
        out = rule(Context(copy.deepcopy(decision), db, Describer(db), profile))
    except Exception:
        return False
    return out is not None and out.choice is not None


def logged_firings(rule_name, deck_key, folders, limit=MAX_LOGGED):
    """[(game_dir, decision id, choice)]: the newest decisions `rule_name` answered in games of this deck, at most
    one per game."""
    logs = []
    for folder in folders:
        logs += glob.glob(os.path.join(folder, "*", "game.jsonl"))
        logs += glob.glob(os.path.join(folder, "**", "games", "*", "game.jsonl"), recursive=True)
    out = []
    for path in sorted({p for p in logs if not os.path.islink(os.path.dirname(p))},
                       key=lambda p: os.path.basename(os.path.dirname(p)), reverse=True):
        game_dir = os.path.dirname(path)
        try:
            with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
                if json.load(f).get("deck") != deck_key:
                    continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    msg = rec.get("msg") or {}
                    if rec.get("kind") == "reply" and msg.get("source") == f"rule:{rule_name}":
                        out.append((game_dir, msg["id"], msg.get("choice")))
                        break
        except (OSError, ValueError, KeyError):
            continue
        if len(out) >= limit:
            break
    return out


def probes(rule, profile, db, case_files, folders, limit=MAX_LOGGED):
    """The cases to replay without `rule`: [{"name", "source": "case" | "log", "path", "case"}]."""
    named = set(getattr(rule, "cases", ()))
    out = []
    for path in case_files:
        name = os.path.splitext(os.path.basename(path))[0]
        case = replay.load_case(path)
        if name in named or fires(rule, case["messages"][-1], db, profile):
            out.append({"name": name, "source": "case", "path": path, "case": case})
    if out:
        return out
    for game_dir, did, choice in logged_firings(rule.__name__, profile.key, folders, limit):
        try:
            msgs = replay.load_messages(game_dir, did)
        except (OSError, LookupError):
            continue
        name = f"{os.path.basename(game_dir)}-{did}"
        out.append({"name": name, "source": "log", "path": name + ".json", "case": {
            "note": f"logged: the rule answered {choice}", "expect": [choice], "reject": [], "messages": msgs}})
    return out


def verdict(rule, runs):
    if not runs:
        return "untested", "no saved case proves it and it never answered a logged decision: give it a case (@cases)"
    good, total = sum(r["good"] for r in runs), sum(r["repeat"] for r in runs)
    if good < total:
        return "needed", f"without it the model got {good}/{total} runs right"
    if getattr(rule, "shortcut", False):
        return "shortcut", f"the model agrees without it ({good}/{total}); it only saves model calls"
    return "not needed", f"the model got all {total} runs right without it: a candidate for deletion"


def ablate(profile, cfg, db, repeat=2, folders=None, limit=MAX_LOGGED, out=print):
    """Replay each rule's probes with that rule disabled; returns [{"rule", "cases", "shortcut", "probes", "verdict",
    "detail"}]."""
    rules = Rules(profile.dir).deck_rules
    case_files = sorted(glob.glob(os.path.join(profile.dir, "tests", "*.json")))
    if folders is None:  # the game logs: the games dir (--games-dir), the default one, and the deck's training games
        folders = list(dict.fromkeys([paths.resolve(cfg.get("games_dir", "games")), paths.resolve("games"),
                                      os.path.join(profile.dir, "train")]))
    results = []
    if not rules:
        out(paint(DIM, f"{profile.name}: no deck rules to ablate."))
    for rule in rules:
        name = rule.__name__
        out(paint(BOLD, f"\n=== {profile.name}: {name}" + (" (shortcut)" if getattr(rule, "shortcut", False) else "")))
        runs = []
        for p in probes(rule, profile, db, case_files, folders, limit):
            res = replay.run_case(p["path"], cfg, db, profile, repeat, disabled=(name,), case=p["case"])
            runs.append({**res, "name": p["name"], "source": p["source"]})
            out(paint(GREEN if res["passed"] else RED, f"  {p['source']} {p['name']}: {res['good']}/{repeat} right "
                      f"without the rule (chose {res['choices']}; expected {p['case'].get('expect') or 'anything'}"
                      + (f", not {p['case']['reject']}" if p["case"].get("reject") else "") + ")"))
        kind, detail = verdict(rule, runs)
        color = {"needed": GREEN, "untested": YELLOW}.get(kind, YELLOW if kind == "shortcut" else RED)
        out(paint(color, f"{kind.upper()}: {name}: {detail}"))
        results.append({"rule": name, "cases": list(getattr(rule, "cases", ())), "shortcut": bool(
            getattr(rule, "shortcut", False)), "probes": [{k: r[k] for k in ("name", "source", "good", "repeat",
                                                                               "choices")} for r in runs],
            "verdict": kind, "detail": detail})
    return results
