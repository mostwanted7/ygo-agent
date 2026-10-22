"""The pool of positions and the sample: the decisions of the logged games worth re-asking, the stratified selection
that becomes bench/exams/<name>.json, and a choice as a move (so identical moves share one grade)."""

from __future__ import annotations

import copy
import json
import os
import random
import re
import time
import types

from ... import paths
from ...agent.brain import DuelBrain
from ...agent.describe import HINT_ATTACK_TARGET, OWN_PROCEDURE, Describer
from ..runner import LLM_TYPES
from .files import ExamError, rel, sha, tally

GROUPS = ("idle", "battle", "chain", "select_card", "effect_yn", "other")
WEIGHTS = {"idle": 0.30, "chain": 0.20, "select_card": 0.20, "battle": 0.125, "effect_yn": 0.10, "other": 0.075}
SKIP_KINDS = ("place", "announce_card", "go_first", "game_over", "announce_number", "announce_attrib",
              "announce_race", "rps")
YES_NO = ("effect_yn", "yesno", "go_first")
SET_KINDS = ("select_card", "tribute", "select_sum", "select_unselect")
PHASE_ACTIONS = ("to_battle", "to_main2", "to_end")
SUB_WEIGHT = {"opp-activation": 3.0, "opp-summon": 2.5, "opp-attack": 2.5, "own-chain": 1.5, "opp-turn": 1.2,
              "own-turn": 1.0, "search": 2.5, "target": 2.5, "summon": 2.2, "material": 2.0, "cost": 2.0,
              "option": 1.5, "tribute": 1.5, "select_sum": 1.2, "yesno": 1.0, "position": 0.5}
REPEATS = re.compile(r"\(by its own summoning procedure; entry \d+ of \d+[^)]*\)")


# ---- answers as moves ----

def norm_option(text: str) -> str:
    """An option's text with the "entry n of m" numbering of equivalent summon entries taken out."""
    return REPEATS.sub(OWN_PROCEDURE, text).strip()


def answer_key(d: dict, choice, texts: list[str]) -> str:
    """What a choice does, in words: equal for choices that make the same move (another copy of the same card, the same
    cards in another order where order doesn't matter), so identical moves get one grade."""
    if choice is None:
        return "(no answer)"
    if d["kind"] in YES_NO:
        return "yes" if list(choice) == [1] else "no"
    if not choice:
        return "pass / none"
    parts = [norm_option(texts[i]) if 0 <= i < len(texts) else f"option {i}" for i in choice]
    if d["kind"] in SET_KINDS:
        parts = sorted(parts)
    return " + ".join(parts)


def render(d: dict, choice, texts: list[str]) -> str:
    """A choice as the judge sees it: the indices and the options' text."""
    if choice is None:
        return "(no answer)"
    if d["kind"] in YES_NO:
        return "[1] yes" if list(choice) == [1] else "[0] no"
    if not choice:
        return "[] pass / none" if d["kind"] == "chain" else "[] (cancel / finish the selection)"
    return "; ".join(f"[{i}] {texts[i]}" if 0 <= i < len(texts) else f"[{i}]" for i in choice)


# ---- the pool of positions ----

def find_games(roots: list[str], decks=None) -> list[dict]:
    """Logged games an LLM backend played (game.jsonl + meta.json), each once (symlinks like `latest` skipped)."""
    seen, out = set(), []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(paths.resolve(root)):
            dirnames[:] = sorted(x for x in dirnames if x not in ("exams", "replays", "latest"))
            if "meta.json" not in filenames or "game.jsonl" not in filenames:
                continue
            real = os.path.realpath(dirpath)
            if real in seen:
                continue
            seen.add(real)
            try:
                with open(os.path.join(real, "meta.json"), encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            backend = meta.get("backend")
            if not isinstance(backend, dict) or backend.get("type") not in LLM_TYPES or meta.get("mode") == "coach":
                continue
            if decks and meta.get("deck") not in decks:
                continue
            out.append({"dir": rel(real), "deck": meta.get("deck"), "backend": backend.get("name"),
                        "model": backend.get("model"), "mode": meta.get("mode"),
                        "opponent": meta.get("opponent_info"), "result": meta.get("result")})
    return sorted(out, key=lambda g: g["dir"])


def read_log(game_dir: str) -> list[dict]:
    with open(os.path.join(paths.resolve(game_dir), "game.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fill_extra(d: dict, profile) -> dict:
    """The decision as the agent sees it (DuelBrain.on_decide fills the Extra Deck in from the decklist first)."""
    d = copy.deepcopy(d)
    if (d.get("state") or {}).get("me"):
        DuelBrain.fill_extra(types.SimpleNamespace(profile=profile), d["state"])
    return d


def classify(d: dict, describer: Describer) -> tuple[str, str]:
    """(group, sub-kind) of a decision, for the exam's mix of kinds."""
    kind, st = d["kind"], d.get("state") or {}
    if kind == "idle":
        return "idle", "main2" if st.get("phase") == 0x100 else "main1"
    if kind == "battle":
        opp = any(st.get("opp", {}).get("mz") or [])
        return "battle", "into-monsters" if opp else "direct"
    if kind == "select_card" and d.get("hint") == HINT_ATTACK_TARGET:
        return "battle", "attack-target"
    if kind == "chain":
        chain = st.get("chain") or []
        battling = st.get("battling") or []
        if chain and chain[-1].get("player") == 1:
            return "chain", "opp-activation"
        if st.get("summon_player") == 1:
            return "chain", "opp-summon"
        if st.get("turn_player") == 1 and len(battling) > 1 and battling[1]:
            return "chain", "opp-attack"
        if chain:
            return "chain", "own-chain"
        return "chain", "opp-turn" if st.get("turn_player") == 1 else "own-turn"
    if kind in ("select_card", "select_unselect", "tribute"):
        hint = describer.hint(d).lower()
        if "add to your hand" in hint:
            return "select_card", "search"
        if "special summon" in hint or "place on the field" in hint:
            return "select_card", "summon"
        if "material" in hint or "tribute" in hint:
            return "select_card", "material"
        if any(w in hint for w in ("send to the gy", "discard", "banish", "detach", "return to the deck")):
            return "select_card", "cost"
        return "select_card", "target"
    if kind == "effect_yn":
        return "effect_yn", "optional"
    return "other", kind


def real_options(d: dict, texts: list[str]) -> int:
    return len({norm_option(t) for t, o in zip(texts, d.get("options") or [])
                if isinstance(o, dict) and o.get("a") not in PHASE_ACTIONS})


def choice_count(d: dict, texts: list[str]) -> int:
    """Roughly how many different moves the decision allows (1 = nothing to decide)."""
    kind = d["kind"]
    if kind in YES_NO:
        return 2
    distinct = len({norm_option(t) for t in texts})
    if kind == "chain":
        return distinct + (0 if d.get("forced") else 1)
    if kind in ("select_card", "tribute", "select_sum"):
        cancel = 1 if d.get("cancelable") or d.get("min") == 0 else 0
        return (1 if distinct <= d.get("min", 1) else distinct) + cancel
    if kind == "select_unselect":
        return distinct + (1 if d.get("finishable") or d.get("cancelable") else 0)
    return distinct


def importance(d: dict, group: str, sub: str, count: int, contested: bool) -> float:
    """A sampling weight: decisions where the answer matters (a reply to the opponent, a search, a target, a Main Phase
    with many plays) and where the heuristic policy disagrees with what the model did (so it isn't obvious)."""
    base = {"idle": 2.0, "battle": 1.5, "effect_yn": 1.8}.get(group) or SUB_WEIGHT.get(sub, 1.0)
    if group == "idle":
        base += 0.25 * min(max(count - 3, 0), 4)
    if group == "battle":
        st = d.get("state") or {}
        base += 1.0 if any(st.get("opp", {}).get("mz") or []) else 0.0
        base += 0.5 if sum(1 for o in d.get("options") or [] if o.get("a") == "attack") > 1 else 0.0
    if contested:
        base += 1.5
    return round(base, 2)


def scan_game(game: dict, db, profile, rules) -> list[dict]:
    """The decisions of one logged game that are worth asking: the model answered them (not a rule, the automatic
    answers or a fallback), they offer a real choice, and today's rules wouldn't answer them either."""
    from ...agent.rules import Context
    from ...backends.heuristic import Policy
    describer = Describer(db)
    records = read_log(game["dir"])
    replies = {r["msg"].get("id"): r["msg"] for r in records if r["kind"] == "reply"}
    out, prev = [], None
    for rec in records:
        if rec["kind"] == "event":
            prev = rec["msg"]
            continue
        if rec["kind"] != "decide":
            continue
        raw = rec["msg"]
        after_retry = (prev or {}).get("e") == "retry"
        prev = raw
        reply = replies.get(raw.get("id")) or {}
        if after_retry or reply.get("source") != "backend" or raw["kind"] in SKIP_KINDS:
            continue
        d = fill_extra(raw, profile)
        if rules.decide(Context(d, db, describer, profile))[0] is not None:
            continue
        texts = describer.options(d)
        count = choice_count(d, texts)
        group, sub = classify(d, describer)
        if count < 2 or (group == "idle" and real_options(d, texts) < 2) or (
                d["kind"] == "battle" and not any(o.get("a") == "attack" for o in d.get("options") or [])):
            continue
        original = reply.get("choice")
        try:
            heuristic = Policy(db).choose(copy.deepcopy(d))
        except Exception:  # the heuristic is only a hint here
            heuristic = None
        contested = heuristic is not None and answer_key(d, heuristic, texts) != answer_key(d, original, texts)
        if d["kind"] == "position" and not contested:
            continue  # a summon's battle position rarely matters; keep the ones where the policies disagree
        st = d.get("state") or {}
        out.append({"game": game["dir"], "decision": raw["id"], "deck": game["deck"], "kind": raw["kind"],
                    "group": group, "sub": sub, "turn": st.get("turn"), "my_turn": st.get("turn_player") == 0,
                    "choices": count, "score": importance(d, group, sub, count, contested),
                    "source_backend": game["backend"], "original": original, "heuristic": heuristic,
                    "contested": contested, "sha": sha(raw)})
    return out


def allocate(n: int, targets: dict, available: dict) -> dict:
    """Integer quotas close to `targets` (largest remainders) that never exceed what a stratum has; the shortfall of a
    small stratum goes to the others in proportion."""
    alloc = {k: 0 for k in targets}
    active = {k for k in targets if available.get(k, 0) > 0 and targets[k] > 0}
    while sum(alloc.values()) < n and active:
        remaining = n - sum(alloc.values())
        total = sum(targets[k] for k in active)
        shares = {k: remaining * targets[k] / total for k in active}
        add = {k: int(shares[k]) for k in active}
        for k in sorted(active, key=lambda k: (-(shares[k] - add[k]), str(k)))[:remaining - sum(add.values())]:
            add[k] += 1
        for k in active:
            alloc[k] += min(add[k], available[k] - alloc[k])
        active = {k for k in active if alloc[k] < available[k]}
    return alloc


def select(pool: list[dict], n: int, decks: list[str], seed: int, weights: dict | None = None, per_game: int = 3,
           spacing: int = 3) -> list[dict]:
    """A reproducible, stratified sample: the decks share `n` equally, each deck's share is split over the decision
    groups by `weights`, a stratum's picks rotate over the models whose games they come from, and the weights favour
    important positions. At most `per_game` positions per game, `spacing` decisions apart."""
    weights = weights or WEIGHTS
    rng = random.Random(seed)
    strata: dict[tuple, list[dict]] = {}
    for c in pool:
        if c["deck"] in decks:
            strata.setdefault((c["deck"], c["group"]), []).append(c)
    targets = {(d, g): weights.get(g, 0) / len(decks) for d in decks for g in GROUPS}
    quotas = allocate(n, targets, {k: len(v) for k, v in strata.items()})
    taken: list[dict] = []
    per: dict[str, list[int]] = {}

    def fits(c, limit, gap):
        ids = per.get(c["game"], [])
        return len(ids) < limit and all(abs(c["decision"] - i) >= gap for i in ids) and c not in taken

    def take(c):
        taken.append(c)
        per.setdefault(c["game"], []).append(c["decision"])

    def pick(cands):
        w = [c["score"] ** 2 for c in cands]
        return rng.choices(cands, weights=w, k=1)[0]

    for key in sorted(quotas):
        want = quotas[key]
        by_src: dict[str, list[dict]] = {}
        for c in strata.get(key, []):
            by_src.setdefault(str(c["source_backend"]), []).append(c)
        sources = sorted(by_src)
        rng.shuffle(sources)
        got = 0
        while got < want:
            progressed = False
            for src in sources:
                if got >= want:
                    break
                cands = [c for c in by_src[src] if fits(c, per_game, spacing)]
                if cands:
                    take(pick(cands))
                    got += 1
                    progressed = True
            if not progressed:
                break
    if len(taken) < n:  # the per-game limits left a stratum short: top up anywhere, with looser limits
        rest = [c for c in pool if c["deck"] in decks and fits(c, per_game + 2, 1)]
        while len(taken) < n and rest:
            c = pick(rest)
            take(c)
            rest = [x for x in rest if fits(x, per_game + 2, 1)]
    taken.sort(key=lambda c: (decks.index(c["deck"]), GROUPS.index(c["group"]), c["game"], c["decision"]))
    width = max(2, len(str(len(taken))))
    return [{"id": f"p{i + 1:0{width}d}", **c} for i, c in enumerate(taken)]


def make_exam(name: str, cfg: dict, db, decks: list[str], n: int, seed: int, sources: list[str] | None = None,
              say=print) -> dict:
    from ...agent.rules import Rules
    from ...match import MatchError, load_profile
    sources = sources or [cfg.get("games_dir", "games")]
    games = find_games(sources, decks)
    pool = []
    for deck in decks:
        try:
            profile = load_profile(deck, db, cfg)
        except MatchError as e:
            raise ExamError(str(e)) from None
        rules = Rules(profile.dir)
        for g in (g for g in games if g["deck"] == deck):
            try:
                pool += scan_game(g, db, profile, rules)
            except (OSError, ValueError, KeyError) as e:
                say(f"  skipped {g['dir']}: {e}")
    if not pool:
        raise ExamError(f"no usable decisions in the game logs under {', '.join(sources)} for {', '.join(decks)}")
    positions = select(pool, n, decks, seed)
    strata = {}
    for c in pool:
        strata[f"{c['deck']}/{c['group']}"] = strata.get(f"{c['deck']}/{c['group']}", 0) + 1
    return {"name": name, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "seed": seed, "n": n, "decks": decks,
            "weights": WEIGHTS, "sources": sources,
            "pool": {"games": len(games), "decisions": len(pool), "by_stratum": dict(sorted(strata.items())),
                     "by_backend": tally(g["backend"] for g in games)},
            "positions": positions}
