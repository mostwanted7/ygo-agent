"""Re-ask a logged decision with the current playbook and rules, and keep fixed mistakes as test cases.

    ygo-agent replay games/latest 14                    # what would the agent do now at decision #14?
    ygo-agent replay games/latest 14 --save veiler-timing --expect '[[]]' --note "keep Veiler for ..."
    ygo-agent test                                      # run every saved case of the deck 3 times (--repeat N)
    ygo-agent test veiler-timing                        # run some of them (searched in every deck)

A saved case is decks/<deck>/tests/<name>.json holding everything the bot sent up to that decision, so it
keeps working after old game logs are deleted. --expect lists acceptable choices, --reject forbidden ones.
"""

import glob
import json
import os
import sys

from .. import paths
from .brain import DuelBrain
from .gamelog import GameLog, paint, BOLD, GREEN, RED, DIM
from .profile import deck_keys


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


def game_deck(game_dir):
    """The deck a logged game was played with: meta.json's deck key (or its .ydk, for a deck played from a loose
    file), or for older logs the deck name in game.md's title."""
    try:
        with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("deck_ydk") and meta.get("deck") not in deck_keys():
            return meta["deck_ydk"]
        return meta.get("deck")
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(game_dir, "game.md"), encoding="utf-8") as f:
            title = f.readline()
    except OSError:
        return None
    for key in deck_keys():
        with open(os.path.join(paths.DECKS, key, "deck.json"), encoding="utf-8") as f:
            name = json.load(f).get("name", key)
        if title.startswith(f"# {name} — "):
            return key
    return None


def case_source(game_dir, decision_id):
    """A machine-independent pointer to where a case came from, e.g. "games/2026-10-21_140420 #105"."""
    real = os.path.realpath(game_dir)
    rel = os.path.relpath(real, paths.ROOT)
    where = rel if not rel.startswith("..") else os.path.join("games", os.path.basename(real))
    return f"{where} #{decision_id}"


def replay(msgs, cfg, db, profile, label):
    games = os.path.join(paths.resolve(cfg.get("games_dir", "games")), "replays")
    log = GameLog(games, profile.name, name=label, latest=False, quiet=True)
    brain = DuelBrain(cfg, db, profile, log=log, prewarm=False)
    try:
        for msg in msgs[:-1]:
            if msg.get("t") == "event":
                brain.on_event(msg)
        decision = json.loads(json.dumps(msgs[-1]))
        return brain.on_decide(decision)
    finally:
        brain.close()


def case_paths(deck_keys, names=None):
    paths_ = []
    for key in deck_keys:
        paths_ += sorted(glob.glob(os.path.join(paths.DECKS, key, "tests", "*.json")))
    if names:
        paths_ = [p for p in paths_ if os.path.splitext(os.path.basename(p))[0] in names]
    return paths_


def load_case(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_tests(cases, cfg, db, profile_for, repeat=1):
    """cases: case file paths; profile_for(deck_key) gives the Profile to replay each one with."""
    if not cases:
        print("No saved cases.")
        return 0
    failed = 0
    for path in cases:
        name = os.path.splitext(os.path.basename(path))[0]
        deck = os.path.basename(os.path.dirname(os.path.dirname(path)))
        case = load_case(path)
        print(paint(BOLD, f"\n=== {name} ({deck}): {case.get('note', '')}"))
        good = 0
        for run in range(repeat):
            reply = replay(case["messages"], cfg, db, profile_for(deck), f"test-{name}-{run + 1}")
            choice = reply["choice"]
            ok = (not case.get("expect") or choice in case["expect"]) and choice not in case.get("reject", [])
            good += ok
            print(paint(GREEN if ok else RED, f"  run {run + 1}: chose {choice}"))
        passed = good == repeat
        failed += not passed
        print(paint(GREEN if passed else RED, f"{'PASS' if passed else 'FAIL'} {name}: {good}/{repeat} runs correct"
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
