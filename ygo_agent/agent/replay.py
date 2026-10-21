"""Re-ask a logged decision with the current playbook and rules, and keep fixed mistakes as test cases.

    ygo-agent replay games/latest 14                    # what would the agent do now at decision #14?
    ygo-agent replay games/latest 14 --save veiler-timing --expect '[[]]' --note "keep Veiler for ..."
    ygo-agent test                                      # run every saved case of the deck 3 times (--repeat N)
    ygo-agent test veiler-timing                        # run some of them (searched in every deck)

A saved case is <deck folder>/tests/<name>.json (decks/<deck>/ or the user decks dir) holding everything the bot sent up to that decision, so it
keeps working after old game logs are deleted. --expect lists acceptable choices, --reject forbidden ones.
"""

import glob
import json
import os
import sys

from .. import decks, paths
from .brain import DuelBrain
from .gamelog import GameLog, paint, BOLD, GREEN, RED, DIM


def load_messages(game_dir, decision_id):
    """Everything the bot sent in that game up to and including the given decision (replies left out)."""
    msgs = []
    with open(os.path.join(game_dir, "game.jsonl"), encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record.get("kind") not in ("event", "decide"):
                continue
            msg = record["msg"]
            msgs.append(msg)
            if msg.get("t") == "decide" and msg.get("id") == decision_id:
                return msgs
    raise LookupError(f"decision #{decision_id} not found in {game_dir}")


def game_deck(game_dir, cfg=None):
    """The deck a logged game was played with: meta.json's deck key (or its .ydk, for a deck played from a loose
    file), or for older logs the deck name in game.md's title."""
    try:
        with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("deck_ydk") and not decks.matches(meta.get("deck") or "", cfg):
            return meta["deck_ydk"]
        return meta.get("deck")
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(game_dir, "game.md"), encoding="utf-8") as f:
            title = f.readline()
    except OSError:
        return None
    for d in decks.scan(cfg):
        try:
            name = decks.deck_settings(d.dir, d.key, cfg).get("name", d.key)
        except (OSError, ValueError):
            continue
        if title.startswith(f"# {name} — "):
            return d.key
    return None


def case_source(game_dir, decision_id):
    """A machine-independent pointer to where a case came from, e.g. "games/2026-10-21_140420 #105"."""
    real = os.path.realpath(game_dir)
    rel = os.path.relpath(real, paths.ROOT)
    where = rel if not rel.startswith("..") else os.path.join("games", os.path.basename(real))
    return f"{where} #{decision_id}"


def replay(msgs, cfg, db, profile, label, disabled=()):
    """The reply the agent gives now to the last decision in `msgs`; `disabled` names deck rules to leave out (rule
    ablation)."""
    games = os.path.join(paths.resolve(cfg.get("games_dir", "games")), "replays")
    log = GameLog(games, profile.name, name=label, latest=False, quiet=True)
    brain = DuelBrain(cfg, db, profile, log=log, prewarm=False)
    if disabled:
        brain.rules.deck_rules = [r for r in brain.rules.deck_rules if r.__name__ not in disabled]
    try:
        for msg in msgs[:-1]:
            if msg.get("t") == "event":
                brain.on_event(msg)
        decision = json.loads(json.dumps(msgs[-1]))
        return brain.on_decide(decision)
    finally:
        brain.close()


def case_paths(deck_keys, names=None, cfg=None):
    """The saved cases of these decks (by name: decks.find), optionally only the named ones."""
    paths_ = []
    for key in deck_keys:
        paths_ += sorted(glob.glob(os.path.join(decks.find(key, cfg).dir, "tests", "*.json")))
    if names:
        paths_ = [p for p in paths_ if os.path.splitext(os.path.basename(p))[0] in names]
    return paths_


def load_case(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Multi-card picks whose order means nothing: [5, 0, 1] is the same reply as [0, 1, 5].
UNORDERED = ("select_card", "tribute", "select_sum", "announce_attrib", "announce_race")


def choice_ok(case, choice):
    """Is `choice` one of the case's `expect` (when it has any) and none of its `reject`?"""
    kind = case["messages"][-1].get("kind")

    def norm(c):
        return sorted(c) if kind in UNORDERED and isinstance(c, list) else c
    expect = [norm(c) for c in case.get("expect") or []]
    return (not expect or norm(choice) in expect) and norm(choice) not in [norm(c) for c in case.get("reject") or []]


def run_case(path, cfg, db, profile, repeat=1, disabled=(), case=None, on_run=None):
    """Replay one saved case `repeat` times: {"name", "deck", "note", "choices", "good", "repeat", "passed"}.
    `case` gives the case dict directly (path is then only its name); on_run(run, choice, ok) sees each run."""
    name = os.path.splitext(os.path.basename(path))[0]
    case = case or load_case(path)
    choices, good = [], 0
    for run in range(repeat):
        choice = replay(case["messages"], cfg, db, profile, f"test-{name}-{run + 1}", disabled)["choice"]
        ok = choice_ok(case, choice)
        choices.append(choice)
        good += ok
        if on_run:
            on_run(run, choice, ok)
    return {"name": name, "deck": os.path.basename(os.path.dirname(os.path.dirname(path))), "note": case.get("note"),
            "choices": choices, "good": good, "repeat": repeat, "passed": good == repeat}


def run_tests(cases, cfg, db, profile_for, repeat=1, disabled=(), results=None):
    """cases: case file paths; profile_for(deck_key) gives the Profile to replay each one with. Prints each run;
    returns the exit code (1 if a case failed a run). `results`, a list, collects run_case()'s dicts."""
    if not cases:
        print("No saved cases.")
        return 0
    failed = 0
    for path in cases:
        name = os.path.splitext(os.path.basename(path))[0]
        deck = os.path.basename(os.path.dirname(os.path.dirname(path)))
        case = load_case(path)
        print(paint(BOLD, f"\n=== {name} ({deck}): {case.get('note', '')}"))
        res = run_case(path, cfg, db, profile_for(deck), repeat, disabled, case, on_run=lambda run, choice, ok: print(
            paint(GREEN if ok else RED, f"  run {run + 1}: chose {choice}")))
        failed += not res["passed"]
        if results is not None:
            results.append(res)
        print(paint(GREEN if res["passed"] else RED, f"{'PASS' if res['passed'] else 'FAIL'} {name}: "
                    f"{res['good']}/{repeat} runs correct"
                    + (f" (expected one of {case['expect']})" if case.get("expect") else "")
                    + (f" (must not be {case['reject']})" if case.get("reject") else "")))
    print(paint(BOLD, f"\n{len(cases) - failed}/{len(cases)} cases passed every run"))
    return 1 if failed else 0


def save_case(profile, name, game_dir, decision_id, msgs, expect=None, reject=None, note=""):
    os.makedirs(os.path.join(profile.dir, "tests"), exist_ok=True)
    case = {"note": note, "source": case_source(game_dir, decision_id),
            "expect": expect or [], "reject": reject or [], "messages": msgs}
    path = os.path.join(profile.dir, "tests", f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f)
    print(paint(DIM, f"saved {path}"))
    return path


def replay_one(game_dir, decision_id, cfg, db, profile, save=None, expect=None, reject=None, note=""):
    try:
        msgs = load_messages(game_dir, decision_id)
    except (OSError, LookupError) as e:
        sys.exit(str(e))
    if save:
        save_case(profile, save, game_dir, decision_id, msgs, expect, reject, note)
    reply = replay(msgs, cfg, db, profile, f"{os.path.basename(os.path.realpath(game_dir))}-{decision_id}")
    print(paint(BOLD, f"\nReplayed decision #{decision_id}: choice {reply['choice']}"))
    return reply
