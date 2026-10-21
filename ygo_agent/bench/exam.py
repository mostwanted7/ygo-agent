"""`ygo-agent bench exam`: compare models on the same decisions instead of on win rates (docs/bench.md).

Win rates need many games before the luck of the draw averages out. The exam takes a fixed set of real decision
points from logged games instead, re-asks each one of every candidate model exactly the way `ygo-agent replay` does
(a fresh session with the duel history, the current playbook and rules), and has a blind judge grade the answers.

    ygo-agent bench exam --select                  # sample the positions into bench/exams/main.json (no LLM)
    ygo-agent bench exam --dry-run                 # the positions, and what a run would cost
    ygo-agent bench exam                           # candidates answer, the judge grades, report.md
    ygo-agent bench exam --resume                  # continue the newest run (finished answers and grades are kept)
    ygo-agent bench exam report DIR                # rebuild report.md and summary.json

A run folder is bench/exams/results/<time>_<name>/: exam.json (the positions), run.json (settings, model ids, prompt
hashes), prepared.json (what each position shows), answers.jsonl, judge.jsonl, games.jsonl (with --games), and
report.md + summary.json. The candidates' replay logs go to games/exams/<run folder>/.
"""

from __future__ import annotations

import concurrent.futures
import copy
import glob
import hashlib
import itertools
import json
import math
import os
import random
import re
import threading
import time
import types

from .. import paths
from ..agent.brain import DuelBrain, event_ids
from ..agent.describe import HINT_ATTACK_TARGET, OWN_PROCEDURE, Describer
from ..agent.gamelog import GameLog
from . import judge as J
from .metrics import mean, percentile, wilson

EXAMS = os.path.join(paths.ROOT, "bench", "exams")
RESULTS = os.path.join(EXAMS, "results")
BENCH_RESULTS = os.path.join(paths.ROOT, "bench", "results")
LLM_TYPES = ("claude-code", "anthropic", "openai")
DEFAULT_CANDIDATES = ["opus", "sonnet", "haiku"]
DEFAULT_DECKS = ["saffira", "blackwing"]
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
# Rough (USD, seconds) per position answered, from the pilot benchmark's first-of-turn decisions (a fresh session,
# like the exam's); per position judged and per whole game reviewed, from the smoke run (sonnet) scaled by API price.
EST_ANSWER = {"opus": (0.10, 12.0), "sonnet": (0.04, 8.0), "haiku": (0.006, 7.0)}
EST_JUDGE = {"opus": (0.20, 30.0), "sonnet": (0.10, 15.0), "haiku": (0.03, 10.0)}
EST_GAME = {"opus": (0.60, 120.0), "sonnet": (0.25, 60.0), "haiku": (0.08, 40.0)}
FILES = ("exam.json", "run.json", "prepared.json", "answers.jsonl", "judge.jsonl", "games.jsonl")
_WRITE = threading.Lock()


class ExamError(Exception):
    pass


def rel(path: str) -> str:
    real, root = os.path.realpath(path), os.path.realpath(paths.ROOT)
    return os.path.relpath(real, root) if real.startswith(root + os.sep) else real


def sha(obj, n: int = 12) -> str:
    blob = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:n]


def file_sha(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError:
        return None


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
    from ..agent.rules import Context
    from ..backends.heuristic import Policy
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
    from ..agent.rules import Rules
    from ..match import MatchError, load_profile
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
                     "by_backend": _count(g["backend"] for g in games)},
            "positions": positions}


def _count(values) -> dict:
    out = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def exam_path(name: str) -> str:
    if name.endswith(".json") or os.sep in name:
        return paths.resolve(name)
    return os.path.join(EXAMS, f"{name}.json")


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_jsonl(path: str) -> list[dict]:
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue  # a line cut off by a crash
    except OSError:
        pass
    return out


def append_jsonl(path: str, record: dict) -> None:
    with _WRITE:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


# ---- asking a position ----

class ExamBrain(DuelBrain):
    """A DuelBrain that keeps what it showed the backend and what came back."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured: dict = {}

    def build_message(self, d, question, options_text, first):
        text = super().build_message(d, question, options_text, first)
        self.captured.setdefault("text", text)
        return text

    def decided(self, d, question, options_text, chosen, why, plan, source, seconds=None, note=None, **kw):
        self.captured.update(question=question, options=list(options_text), chosen=list(chosen or []), why=why,
                             plan=plan, source=source, note=note)
        super().decided(d, question, options_text, chosen, why, plan, source, seconds, note, **kw)


def capture_backend() -> dict:
    from ..backends.heuristic import first_legal
    return {"name": "capture", "type": "scripted", "policy": lambda d: {"choice": first_legal(d), "why": "capture"}}


def ask(msgs: list[dict], cfg: dict, db, profile, backend: dict, log_root: str, label: str, mode=None,
        opponent=None) -> dict:
    """Re-ask the last decision in `msgs` the way `ygo-agent replay` does: a fresh brain replays the events, then gets
    the decision. Returns what the backend was shown and answered, with its time, tokens and cost."""
    log = GameLog(log_root, profile.name, name=label, latest=False, quiet=True)
    brain = ExamBrain(cfg, db, profile, log=log, prewarm=False, backend=backend, fallback="heuristic", mode=mode,
                      opponent=opponent)
    try:
        for msg in msgs[:-1]:
            if msg.get("t") == "event":
                brain.on_event(msg)
        brain.on_decide(json.loads(json.dumps(msgs[-1])))
        system_prompt, rules = brain.system_prompt, brain.rules_key
    finally:
        brain.close()
    c, s = brain.captured, brain.stats.summary()
    return {"text": c.get("text"), "question": c.get("question"), "options": c.get("options") or [],
            "choice": c.get("chosen"), "why": c.get("why"), "plan": c.get("plan"), "source": c.get("source"),
            "note": c.get("note"), "seconds": brain.stats.latencies[-1] if brain.stats.latencies else None,
            "tokens": s["tokens"], "cost_usd": s["cost_usd"], "asks": s["asks"], "invalid": s["invalid_replies"],
            "errors": s["errors"], "system_sha": sha(system_prompt), "rules": rules, "log": rel(log.dir)}


def run_mode(meta_mode) -> str:
    return meta_mode if meta_mode in ("play", "selfplay", "teach") else "selfplay"


# ---- a run ----

class ExamRun:
    """One run of an exam in `folder`: prepare the positions, collect every candidate's answers, have each judge
    grade them, optionally review whole games, and write the report. Every step is resumable."""

    def __init__(self, exam: dict, folder: str, cfg: dict, db, candidates: list[str], judges: list[str], *,
                 parallel: int = 4, budget: float | None = None, judge_batch: int = 3, agentic: bool | None = None,
                 probe: float = 0.15, games: int = 0, games_from: str | None = None, judge_effort: str | None = None,
                 probe_backends: bool = True, argv=None, say=print):
        self.exam, self.folder, self.cfg, self.db = exam, folder, cfg, db
        self.candidates, self.judges = list(candidates), list(judges)
        self.parallel, self.budget, self.judge_batch = max(1, parallel), budget or None, max(1, judge_batch)
        self.agentic, self.probe, self.games, self.games_from = agentic, probe, games, games_from
        self.judge_effort, self.probe_backends, self.argv, self.say = judge_effort, probe_backends, argv, say
        self.cfg["chat"] = "off"
        self.profiles: dict = {}
        self.limited: set[str] = set()
        self.spent = 0.0
        self.stopped: str | None = None
        self.log_root = os.path.join(paths.resolve(cfg.get("games_dir", "games")), "exams",
                                     os.path.basename(os.path.normpath(folder)))

    def path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def profile(self, deck: str):
        if deck not in self.profiles:
            from ..match import load_profile
            self.profiles[deck] = load_profile(deck, self.db, self.cfg)
        return self.profiles[deck]

    def backend(self, name: str, effort: str | None = None) -> dict:
        from ..config import ConfigError, backend
        try:
            profile = backend(self.cfg, name)
        except ConfigError as e:
            raise ExamError(str(e)) from None
        if effort:
            profile["effort"] = effort
        return profile

    # ---- setup ----

    def setup(self) -> None:
        os.makedirs(self.folder, exist_ok=True)
        stored = load_json(self.path("exam.json"))
        if stored is None:
            save_json(self.path("exam.json"), self.exam)
        elif [p["id"] for p in stored["positions"]] != [p["id"] for p in self.exam["positions"]] or any(
                a.get("sha") != b.get("sha") for a, b in zip(stored["positions"], self.exam["positions"])):
            self.say(f"  note: this run keeps its own copy of the positions ({rel(self.path('exam.json'))})")
            self.exam = stored
        decks = list(dict.fromkeys(p["deck"] for p in self.exam["positions"]))
        prompts = {"describe": file_sha(os.path.join(paths.ROOT, "ygo_agent", "agent", "describe.py")),
                   "prompts": file_sha(os.path.join(paths.ROOT, "ygo_agent", "agent", "prompts.py")),
                   "general": file_sha(os.path.join(paths.PLAYBOOKS, "general.md"))}
        for deck in decks:
            p = self.profile(deck)
            prompts[f"{deck}/playbook"] = file_sha(p.playbook_path) if p.playbook_path else None
            prompts[f"{deck}/rules"] = file_sha(os.path.join(p.dir, "rules.py"))
        run = load_json(self.path("run.json")) or {"exam": self.exam["name"], "created": time.strftime(
            "%Y-%m-%d %H:%M:%S"), "prompts": prompts, "invocations": [], "model_ids": {}}
        if run.get("prompts") != prompts:
            changed = [k for k in prompts if run.get("prompts", {}).get(k) != prompts[k]]
            self.say(f"  warning: {', '.join(changed)} changed since this run started; answers from before and after "
                     "the change are mixed (start a new run to compare on one prompt version)")
            run["prompts_now"] = prompts
        run["candidates"] = {c: _public(self.backend(c)) for c in self.candidates}
        run["judges"] = self.judges
        run["judge_profiles"] = {j: _public(self.backend(j, self.judge_effort)) for j in self.judges}
        run["settings"] = {"parallel": self.parallel, "budget_usd": self.budget, "judge_batch": self.judge_batch,
                           "agentic": self.agentic, "probe": self.probe, "games": self.games,
                           "games_from": self.games_from}
        run["invocations"].append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "argv": self.argv})
        if self.probe_backends:
            from .runner import probe
            for name in dict.fromkeys(self.candidates + self.judges):
                profile = self.backend(name)
                if profile.get("type") not in LLM_TYPES:
                    continue
                result = probe(profile)
                if not result.get("ok"):
                    save_json(self.path("run.json"), run)
                    raise ExamError(f"backend {name} can't answer: {result.get('error')}")
                if result.get("model_ids"):
                    run["model_ids"][name] = result["model_ids"]
                    self.say(f"  {name}: {', '.join(result['model_ids'])} ({result.get('seconds')}s)")
        save_json(self.path("run.json"), run)
        self.run_info = run
        self.spent = sum(r.get("cost_usd") or 0 for name in ("answers.jsonl", "judge.jsonl", "games.jsonl")
                         for r in load_jsonl(self.path(name)))

    # ---- the steps ----

    def run(self) -> dict:
        self.setup()
        self.prepare()
        self.answer()
        for judge in self.judges:
            self.judge(judge)
        if self.games:
            self.review_games()
        if self.stopped:
            self.say(f"Stopped early: {self.stopped}. `ygo-agent bench exam --resume {rel(self.folder)}` continues.")
        return build(self.folder)

    def over_budget(self) -> bool:
        if self.budget and self.spent >= self.budget and not self.stopped:
            self.stopped = f"the budget of ${self.budget:.2f} is spent (${self.spent:.2f})"
        return bool(self.budget and self.spent >= self.budget)

    def prepare(self) -> dict:
        """What each position shows the players (the same text for every candidate), via a scripted backend; also
        drops positions today's rules would answer, and positions whose game log has changed or gone."""
        prepared = load_json(self.path("prepared.json"), {})
        changed = False
        for p in self.exam["positions"]:
            old = prepared.get(p["id"])
            if old and old.get("sha") == p["sha"] and old.get("status") in ("ok", "excluded"):
                continue
            prepared[p["id"]] = self.prepare_one(p)
            changed = True
        if changed:
            save_json(self.path("prepared.json"), prepared)
        self.prepared = prepared
        out = [k for k, v in prepared.items() if v["status"] != "ok"]
        self.say(f"Positions: {len(prepared) - len(out)} to ask" + (f", {len(out)} excluded" if out else ""))
        return prepared

    def prepare_one(self, p: dict) -> dict:
        from ..agent import replay
        try:
            msgs = replay.load_messages(paths.resolve(p["game"]), p["decision"])
        except (OSError, LookupError) as e:
            return {"status": "excluded", "sha": p["sha"], "reason": f"game log unavailable: {e}"}
        if sha(msgs[-1]) != p["sha"]:
            return {"status": "excluded", "sha": p["sha"], "reason": "the game log changed since the exam was made"}
        meta = load_json(os.path.join(paths.resolve(p["game"]), "meta.json"), {})
        profile = self.profile(p["deck"])
        mode, opponent = run_mode(meta.get("mode")), meta.get("opponent_info")
        res = ask(msgs, self.cfg, self.db, profile, capture_backend(), self.log_root, f"capture/{p['id']}", mode,
                  opponent)
        entry = {"sha": p["sha"], "mode": mode, "opponent": opponent, "deck": p["deck"], "kind": p["kind"]}
        if res["source"] != "backend":
            return {**entry, "status": "excluded", "reason": f"answered by {res['source']} now"}
        describer = Describer(self.db)
        d = fill_extra(msgs[-1], profile)
        ids = describer.ids_in_state(d["state"]) | describer.ids_in_decision(d)
        for m in msgs:
            if m.get("t") == "event":
                ids |= event_ids(m)
        return {**entry, "status": "ok", "text": res["text"], "question": res["question"], "options": res["options"],
                "decision": d, "rules": res["rules"], "ids": sorted(i for i in ids if self.db.get(i)),
                "prompt_sha": sha(res["text"] or ""), "system_sha": res["system_sha"]}

    def positions(self) -> list[dict]:
        return [p for p in self.exam["positions"] if self.prepared.get(p["id"], {}).get("status") == "ok"]

    def answer(self) -> None:
        done = latest(load_jsonl(self.path("answers.jsonl")), ("position", "candidate"))
        jobs = [(p, c) for p in self.positions() for c in self.candidates
                if (done.get((p["id"], c)) or {}).get("status") not in ("done", "rule")]
        if not jobs:
            return
        self.say(f"Answers: {len(jobs)} to ask ({len(self.candidates)} candidates, {self.parallel} at a time)")
        counter = itertools.count(1)

        def work(job):
            p, cand = job
            if cand in self.limited or self.over_budget():
                return
            record = self.answer_one(p, cand)
            append_jsonl(self.path("answers.jsonl"), record)
            with _WRITE:
                self.spent += record.get("cost_usd") or 0
            n = next(counter)
            what = record.get("answer") or record.get("error") or ""
            cost = f", ${record['cost_usd']:.3f}" if record.get("cost_usd") is not None else ""
            self.say(f"  [{n}/{len(jobs)}] {p['id']} {cand}: {record['status']} {what[:90]} "
                     f"({record.get('seconds') or 0:.1f}s{cost})")

        self._pool(work, jobs)

    def answer_one(self, p: dict, cand: str) -> dict:
        from ..agent import replay
        from ..trainer.review import limited
        prep = self.prepared[p["id"]]
        base = {"position": p["id"], "candidate": cand, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        try:
            msgs = replay.load_messages(paths.resolve(p["game"]), p["decision"])
            res = ask(msgs, self.cfg, self.db, self.profile(p["deck"]), self.backend(cand), self.log_root,
                      f"{p['id']}--{cand}", prep["mode"], prep["opponent"])
        except Exception as e:  # one broken position mustn't stop the run
            return {**base, "status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
        d = prep["decision"]
        status = "done" if res["source"] == "backend" else (
            "rule" if (res["source"] or "").startswith("rule") or res["source"] == "auto" else "error")
        error = None if status == "done" else (res.get("note") or res["source"])
        if status == "error" and limited(error):
            status = "limited"
            self.limited.add(cand)
            if not self.stopped:
                self.stopped = f"{cand} hit a usage limit ({error[:120]})"
        return {**base, "status": status, "choice": res["choice"],
                "key": answer_key(d, res["choice"], res["options"]) if status == "done" else None,
                "answer": render(d, res["choice"], res["options"]) if status == "done" else None,
                "why": res["why"], "plan": res["plan"], "source": res["source"], "error": error,
                "seconds": res["seconds"], "tokens": res["tokens"], "cost_usd": res["cost_usd"], "asks": res["asks"],
                "invalid": res["invalid"], "errors": res["errors"], "prompt_sha": sha(res["text"] or ""),
                "same_prompt": sha(res["text"] or "") == prep.get("prompt_sha"), "log": res["log"]}

    def _pool(self, fn, items, workers: int | None = None) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers or self.parallel) as ex:
            for f in concurrent.futures.as_completed([ex.submit(fn, x) for x in items]):
                f.result()

    # ---- judging ----

    def deck_context(self, deck: str) -> dict:
        p = self.profile(deck)
        return {"name": p.name, "decklist": p.decklist(), "general": p.general_playbook, "playbook": p.playbook}

    def reviewer(self, judge: str, sandbox: str):
        from ..trainer.llm import Reviewer
        rv = Reviewer(self.backend(judge, self.judge_effort), self.db, self.agentic, name="exam")
        rv.sandbox = sandbox
        return rv

    def script_dirs(self) -> list[str]:
        try:
            from ..core.install import EdoproInstall
            return EdoproInstall.find(paths.resolve(self.cfg["edopro_dir"])).script_dirs
        except Exception:  # no EDOPro install (tests): the judge works from the card texts
            return []

    def judge(self, judge: str) -> None:
        answers = latest(load_jsonl(self.path("answers.jsonl")), ("position", "candidate"))
        judged = latest([r for r in load_jsonl(self.path("judge.jsonl")) if r.get("judge") == judge], ("position",))
        todo = []
        for p in self.positions():
            got = {c: answers.get((p["id"], c)) for c in self.candidates}
            if not all(a and a.get("status") == "done" for a in got.values()):
                continue
            mine = {c: {"key": a["key"], "answer": a["answer"], "why": a.get("why")} for c, a in got.items()}
            old = judged.get((p["id"],))
            if old and old.get("status") == "done" and old.get("answers_sha") == J.answers_sha(mine):
                continue
            todo.append((p, mine))
        if not todo:
            return
        if self.over_budget():
            return
        sandbox = os.path.join(paths.CACHE, "exam", os.path.basename(os.path.normpath(self.folder)), judge)
        rv = self.reviewer(judge, sandbox)
        if rv.agentic:
            ids = set()
            for p, _ in todo:
                ids |= set(self.prepared[p["id"]]["ids"])
                ids |= self.profile(p["deck"]).ids
            info = J.build_sandbox(sandbox, ids, self.db, self.script_dirs())
            self.say(f"  judge sandbox: {info['scripts']} scripts" + (f", {len(info['missing'])} missing"
                                                                       if info["missing"] else ""))
        rng = random.Random(f"{self.exam['name']}:{judge}:batches")
        batches = []
        for deck in dict.fromkeys(p["deck"] for p, _ in todo):
            mine = [x for x in todo if x[0]["deck"] == deck]
            rng.shuffle(mine)
            batches += [mine[i:i + self.judge_batch] for i in range(0, len(mine), self.judge_batch)]
        self.say(f"Judge {judge}{' (agentic)' if rv.agentic else ''}: {len(todo)} positions in {len(batches)} "
                 "call(s)")
        os.makedirs(self.path("judge"), exist_ok=True)
        counter = itertools.count(1)

        def work(batch):
            if self.over_budget():
                return
            n = next(counter)
            records = self.judge_batch_call(rv, judge, batch, f"{judge}-{n:03d}")
            failed = [x for x, r in zip(batch, records) if r["status"] != "done"]
            if failed and len(batch) > 1:  # a batch that came back partial: ask the missing ones alone
                retry = {x[0]["id"]: self.judge_batch_call(rv, judge, [x], f"{judge}-{n:03d}-{i + 1}")[0]
                         for i, x in enumerate(failed)}
                records = [retry.get(r["position"], r) for r in records]
            for r in records:
                append_jsonl(self.path("judge.jsonl"), r)
            grades = ", ".join(f"{r['position']} {'/'.join(g['grade'][:4] for g in r['result']['grades'].values())}"
                               if r["status"] == "done" else f"{r['position']} {r['status']}" for r in records)
            self.say(f"  judged {grades}")

        self._pool(work, batches)

    def judge_batch_call(self, rv, judge: str, batch: list, call_id: str) -> list[dict]:
        items, maps = [], {}
        salt = f"{self.exam['name']}:{judge}"
        for p, mine in batch:
            shown, mapping = J.blind(p["id"], mine, salt, self.probe)
            maps[p["id"]] = mapping
            prep = self.prepared[p["id"]]
            profile = self.profile(p["deck"])
            texts = [self.db.full_text(i) for i in prep["ids"] if i in profile.ids]
            items.append({"id": p["id"], "deck": p["deck"], "deck_name": profile.name, "kind": p["kind"],
                          "text": prep["text"], "card_texts": texts, "answers": shown})
        decks = {d: self.deck_context(d) for d in dict.fromkeys(i["deck"] for i in items)}
        prompt = J.judge_prompt(items, decks)
        rules = self.prepared[batch[0][0]["id"]].get("rules") or self.cfg.get("duel", {}).get("rules", "MR3")
        with open(self.path(f"judge/{call_id}.prompt.md"), "w", encoding="utf-8") as f:
            f.write(prompt)
        remaining = (self.budget - self.spent) if self.budget else None
        out, info = rv.ask("exam-judge", J.system(rules, rv.agentic), prompt, J.JUDGE_SCHEMA, timeout=1800,
                           transcript=self.path(f"judge/{call_id}.transcript.jsonl") if rv.agentic else None,
                           max_cost=remaining)
        with _WRITE:
            self.spent += info.get("cost_usd") or 0
        results, problems = J.check_reply(out, items)
        share = (info.get("cost_usd") or 0) / len(batch)
        records = []
        for (p, mine), item in zip(batch, items):
            base = {"position": p["id"], "judge": judge, "answers_sha": J.answers_sha(mine), "mapping": maps[p["id"]],
                    "shown": item["answers"], "call": call_id, "cost_usd": round(share, 4),
                    "seconds": info.get("seconds"), "files_read": info.get("files_read") or [],
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            result = results.get(p["id"])
            if result is None:
                err = info.get("error") or "; ".join(x for x in problems if x.startswith(p["id"])) or "no result"
                records.append({**base, "status": "error", "error": err})
                continue
            d = self.prepared[p["id"]]["decision"]
            options = self.prepared[p["id"]]["options"]
            own = J.own_key(result, d, lambda c: answer_key(d, c, options))
            records.append({**base, "status": "done", "result": result, "own_key": own,
                            "own_answer": render(d, result["own_choice"], options) if own else None,
                            "issues": J.consistency(maps[p["id"]], result, own),
                            "probes": J.probe_pairs(maps[p["id"]], result["grades"])})
        return records

    # ---- whole games ----

    def review_games(self) -> None:
        """A blind "count the significant mistakes" review of K logged games per candidate, on the same deals where
        the benchmark has them (the same deck, opponent and seed for every candidate)."""
        from ..trainer import logs
        source = self.games_from or default_bench_run()
        if not source:
            self.say("No benchmark run to take games from (--games-from DIR).")
            return
        picks = pick_games(source, self.candidates, self.games, seed=self.exam.get("seed", 1))
        done = latest(load_jsonl(self.path("games.jsonl")), ("id",))
        todo = [g for g in picks if (done.get((g["id"],)) or {}).get("status") != "done"]
        if not todo:
            return
        judge = self.judges[0]
        sandbox = os.path.join(paths.CACHE, "exam", os.path.basename(os.path.normpath(self.folder)), "games")
        rv = self.reviewer(judge, sandbox)
        ids, prepared = set(), {}
        for g in todo:
            game_dir = paths.resolve(g["log_dir"])
            meta = load_json(os.path.join(game_dir, "meta.json"), {})
            label = (meta.get("backend") or {}).get("label")
            md = J.anonymize(logs.read(os.path.join(game_dir, "game.md")), [x for x in (label,) if x],
                             [f"({(meta.get('backend') or {}).get('name')})"])
            prepared[g["id"]] = (md, logs.condense(md), meta)
            for r in read_log(g["log_dir"]):
                ids |= _ids(r.get("msg"))
            ids |= self.profile(g["deck"]).ids
        if rv.agentic:
            J.build_sandbox(sandbox, ids, self.db, self.script_dirs())
            for gid, (md, condensed, _) in prepared.items():
                os.makedirs(os.path.join(sandbox, "games", gid), exist_ok=True)
                with open(os.path.join(sandbox, "games", gid, "game.md"), "w", encoding="utf-8") as f:
                    f.write(md)
                with open(os.path.join(sandbox, "games", gid, "condensed.md"), "w", encoding="utf-8") as f:
                    f.write(condensed)
        self.say(f"Whole-game reviews: {len(todo)} game(s) by {judge}")
        os.makedirs(self.path("games"), exist_ok=True)

        def work(g):
            if self.over_budget():
                return
            md, condensed, meta = prepared[g["id"]]
            if rv.agentic:
                ref = (f"The full log is games/{g['id']}/game.md (every decision with all its options; grep it), and "
                       f"a condensed one is games/{g['id']}/condensed.md: start there.")
            else:
                ref = f"The condensed game log follows.\n\n```\n{condensed[:60000]}\n```"
            info_game = {"id": g["id"], "deck_name": self.profile(g["deck"]).name, "opponent": g["opponent"],
                         "result": g["result"], "turns": g.get("turns"), "first": g.get("first") == "player",
                         "reason": g.get("reason")}
            prompt = J.game_prompt(info_game, self.deck_context(g["deck"]), ref, logs.problems(md))
            with open(self.path(f"games/{g['id']}.prompt.md"), "w", encoding="utf-8") as f:
                f.write(prompt)
            transcript = self.path(f"games/{g['id']}.transcript.jsonl") if rv.agentic else None
            out, info = rv.ask("exam-game", J.game_system(meta.get("rules") or "MR3", rv.agentic), prompt,
                               J.GAME_SCHEMA, timeout=2400, transcript=transcript)
            with _WRITE:
                self.spent += info.get("cost_usd") or 0
            record = {**g, "status": "done" if out else "error", "review": out, "error": info.get("error"),
                      "cost_usd": info.get("cost_usd"), "seconds": info.get("seconds"),
                      "files_read": info.get("files_read") or [], "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            if out:
                record["significant"] = J.count_significant(out)
            append_jsonl(self.path("games.jsonl"), record)
            self.say(f"  {g['id']} ({g['candidate']}): " + (f"{len(out.get('mistakes') or [])} mistakes, "
                                                            f"{record['significant']} significant" if out else
                                                            f"error {info.get('error')}"))

        self._pool(work, todo, workers=min(self.parallel, 3))


def _public(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k in ("name", "type", "model", "effort", "base_url", "card_texts",
                                                       "history_lines")}


def _ids(value, key=None) -> set:
    out = set()
    if isinstance(value, dict):
        for k, v in value.items():
            out |= _ids(v, k)
    elif isinstance(value, list):
        for v in value:
            out |= _ids(v, key)
    elif isinstance(value, int) and not isinstance(value, bool) and key == "id" and value:
        out.add(value)
    return out


def latest(records: list[dict], keys: tuple) -> dict:
    """The last record for each key (a later line replaces an earlier one, e.g. a retried answer)."""
    out = {}
    for r in records:
        out[tuple(r.get(k) for k in keys)] = r
    return out


def default_bench_run() -> str | None:
    """The newest benchmark run with LLM games."""
    for folder in sorted(glob.glob(os.path.join(BENCH_RESULTS, "*")), reverse=True):
        if os.path.isfile(os.path.join(folder, "results.jsonl")):
            return folder
    return None


def pick_games(bench_folder: str, candidates: list[str], k: int, seed: int = 1) -> list[dict]:
    """Up to `k` finished games per candidate from a benchmark run: deals every candidate played first (the same deck,
    opponent and game number, so the same seed), then the candidate's other games."""
    rows = [r for r in load_jsonl(os.path.join(bench_folder, "results.jsonl"))
            if r.get("status") == "done" and (r.get("player") or {}).get("log_dir")]
    last = latest(rows, ("deck", "backend", "opponent", "game"))
    by = {}
    for (deck, backend, opponent, game), r in last.items():
        if backend in candidates and os.path.isfile(os.path.join(paths.resolve(r["player"]["log_dir"]), "game.md")):
            by.setdefault((deck, opponent, game), {})[backend] = r
    shared = sorted(key for key, v in by.items() if all(c in v for c in candidates))
    rng = random.Random(seed)
    order = sorted(shared, key=lambda key: (key[2], key[0], key[1]))
    picks = []
    for cand in candidates:
        mine = [(key, True) for key in order[:k]]
        if len(mine) < k:
            others = sorted(key for key, v in by.items() if cand in v and key not in shared)
            rng.shuffle(others)
            mine += [(key, False) for key in others[:k - len(mine)]]
        for key, same in mine:
            r = by[key][cand]
            picks.append({"candidate": cand, "deck": key[0], "opponent": key[1], "index": key[2],
                          "like_for_like": same, "log_dir": r["player"]["log_dir"], "result": r.get("result"),
                          "turns": r.get("turns"), "first": r.get("first"), "reason": r.get("reason")})
    for g in picks:  # anonymous, and stable when a resumed run asks for more games
        g["id"] = "g" + sha(f"{g['candidate']}:{g['log_dir']}", 6)
    return sorted(picks, key=lambda g: g["id"])


# ---- statistics ----

def bootstrap_ci(values: list[float], b: int = 2000, seed: int = 0) -> list[float] | None:
    """A 95% percentile-bootstrap interval for the mean (seeded, so a report rebuilds identically)."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(b))
    return [means[int(0.025 * b)], means[int(0.975 * b) - 1]]


def sign_test(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial p-value for wins vs losses (ties dropped)."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _rate(k: int, n: int):
    return k / n if n else None


def _ci(k: int, n: int):
    ci = wilson(k, n)
    return list(ci) if ci else None


# ---- the report ----

def load_run(folder: str) -> dict:
    data = {name: (load_jsonl if name.endswith(".jsonl") else load_json)(os.path.join(folder, name))
            for name in FILES}
    if not data["exam.json"] or not data["run.json"]:
        raise ExamError(f"{folder} is not an exam run (no exam.json / run.json)")
    return data


def model_of(profile: dict | None) -> str | None:
    return (profile or {}).get("model") or (profile or {}).get("name")


def summarize(data: dict) -> dict:
    exam, run = data["exam.json"], data["run.json"]
    prepared = data["prepared.json"] or {}
    cands = list(run.get("candidates") or {})
    judges = run.get("judges") or []
    primary = judges[0] if judges else None
    positions = {p["id"]: p for p in exam["positions"]}
    answers = latest(data["answers.jsonl"], ("position", "candidate"))
    judged_all = [r for r in data["judge.jsonl"] if r.get("status") == "done"]

    def current(judge):
        """The judge's latest grades for answers that are still the candidates' latest ones."""
        out = {}
        for r in latest([r for r in judged_all if r.get("judge") == judge], ("position",)).values():
            got = {c: answers.get((r["position"], c)) for c in cands}
            if not all(a and a.get("status") == "done" for a in got.values()):
                continue
            mine = {c: {"key": a["key"], "answer": a["answer"], "why": a.get("why")} for c, a in got.items()}
            if J.answers_sha(mine) == r.get("answers_sha"):
                out[r["position"]] = r
        return out

    graded = {j: current(j) for j in judges}
    main = graded.get(primary, {})
    rows = []
    for pid, r in sorted(main.items()):
        p = positions.get(pid)
        if not p:
            continue
        per = J.unblind(r["mapping"], r["result"]["grades"])
        keys = {c: answers[(pid, c)]["key"] for c in cands}
        for c in cands:
            g = per.get(c) or {}
            rows.append({"position": pid, "candidate": c, "deck": p["deck"], "group": p["group"], "sub": p["sub"],
                         "grade": g.get("grade"), "score": J.SCORE.get(g.get("grade")), "label": g.get("label"),
                         "reason": g.get("reason"), "key": keys[c],
                         "agree": keys[c] == r.get("own_key") or g.get("label") in r["result"]["equivalent"],
                         "unique": sum(1 for x in cands if keys[x] == keys[c]) == 1})
    rows = [x for x in rows if x["score"] is not None]
    models = {}
    for c in cands:
        mine = [x for x in rows if x["candidate"] == c]
        done = [a for (pid, cand), a in answers.items() if cand == c and a.get("status") == "done"]
        models[c] = model_stats(c, mine, done, run)
    pairs = []
    by_pos = {}
    for x in rows:
        by_pos.setdefault(x["position"], {})[x["candidate"]] = x["score"]
    for a, b in itertools.combinations(cands, 2):
        common = [v for v in by_pos.values() if a in v and b in v]
        diffs = [v[a] - v[b] for v in common]
        wins, losses = sum(1 for d in diffs if d > 0), sum(1 for d in diffs if d < 0)
        pairs.append({"a": a, "b": b, "n": len(diffs), "diff": mean(diffs), "ci95": bootstrap_ci(diffs, seed=1),
                      "a_better": wins, "ties": len(diffs) - wins - losses, "b_better": losses,
                      "p_sign": sign_test(wins, losses)})
    excluded = {pid: v.get("reason") for pid, v in prepared.items() if v.get("status") != "ok"}
    asked = [pid for pid, v in prepared.items() if v.get("status") == "ok"]
    summary = {
        "name": exam["name"], "folder": rel(data["_folder"]) if data.get("_folder") else None,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "positions": len(exam["positions"]), "asked": len(asked), "graded": len(by_pos), "excluded": excluded,
        "candidates": cands, "judge": primary, "judges": judges, "run": {k: run.get(k) for k in (
            "created", "candidates", "judge_profiles", "model_ids", "prompts", "prompts_now", "settings")},
        "exam": {k: exam.get(k) for k in ("seed", "n", "decks", "sources", "pool", "created")},
        "models": models, "pairs": pairs,
        "judge_checks": judge_checks(rows, main, run, cands, primary),
        "cross_judges": cross_judges(graded, primary, cands, answers),
        "prompt_mismatch": sorted({a["position"] for a in answers.values() if a.get("status") == "done"
                                   and a.get("same_prompt") is False}),
        "incomplete": sorted(pid for pid in asked if any((answers.get((pid, c)) or {}).get("status") != "done"
                                                         for c in cands)),
        "disagreements": disagreements(rows, main, positions, answers, prepared),
        "games": games_summary(data["games.jsonl"], cands),
        "bench": bench_context(run, cands),
        "rows": rows,
    }
    summary["recommendation"] = recommend(summary)
    return summary


def model_stats(c: str, mine: list[dict], done: list[dict], run: dict) -> dict:
    n = len(mine)
    scores = [x["score"] for x in mine]
    count = lambda *gs: sum(1 for x in mine if x["grade"] in gs)  # noqa: E731
    lat = [a["seconds"] for a in done if a.get("seconds") is not None]
    costs = [a["cost_usd"] for a in done if a.get("cost_usd") is not None]
    toks = {k: sum((a.get("tokens") or {}).get(k, 0) for a in done) for k in ("input", "output", "cache_read",
                                                                             "cache_write")}
    unique = [x for x in mine if x["unique"]]

    def split(key):
        out = {}
        for x in mine:
            out.setdefault(x[key], []).append(x)
        return {k: {"n": len(v), "mean_score": mean(y["score"] for y in v),
                    "mistake_rate": _rate(sum(1 for y in v if y["grade"] in ("mistake", "blunder")), len(v))}
                for k, v in sorted(out.items())}
    return {
        "candidate": c, "model": model_of((run.get("candidates") or {}).get(c)),
        "model_ids": (run.get("model_ids") or {}).get(c), "graded": n,
        "mean_score": mean(scores), "ci95": bootstrap_ci(scores),
        "best": _rate(count("best"), n), "best_or_good": _rate(count("best", "good"), n),
        "mistake_rate": _rate(count("mistake", "blunder"), n), "mistake_ci": _ci(count("mistake", "blunder"), n),
        "blunder_rate": _rate(count("blunder"), n), "blunder_ci": _ci(count("blunder"), n),
        "grades": {g: count(g) for g in J.GRADES},
        "agreement": _rate(sum(1 for x in mine if x["agree"]), n),
        "unique": len(unique), "unique_best": _rate(sum(1 for x in unique if x["grade"] == "best"), len(unique)),
        "answered": len(done), "latency_mean_s": mean(lat), "latency_p95_s": percentile(lat, 0.95),
        "cost_per_decision": sum(costs) / len(costs) if costs else None, "cost_usd": sum(costs) if costs else None,
        "tokens_per_decision": {k: v / len(done) for k, v in toks.items()} if done else None,
        "invalid_replies": sum(a.get("invalid") or 0 for a in done),
        "by_group": split("group"), "by_deck": split("deck"),
    }


def judge_checks(rows: list[dict], main: dict, run: dict, cands: list[str], primary: str | None) -> dict:
    """Self-preference (the judge's model among the candidates being "best" far more often when it stands alone),
    the judge's self-contradictions, and its probe agreement (the same move graded twice)."""
    judge_model = model_of((run.get("judge_profiles") or {}).get(primary))
    same = [c for c in cands if model_of((run.get("candidates") or {}).get(c)) == judge_model]
    rates = {}
    for c in cands:
        unique = [x for x in rows if x["candidate"] == c and x["unique"]]
        rates[c] = {"unique": len(unique), "unique_best": _rate(sum(1 for x in unique if x["grade"] == "best"),
                                                                len(unique))}
    flag = None
    for c in same:
        mine, others = rates[c], [rates[o]["unique_best"] for o in cands if o != c and rates[o]["unique"] >= 4
                                  and rates[o]["unique_best"] is not None]
        if mine["unique"] >= 4 and mine["unique_best"] is not None and others and \
                mine["unique_best"] - max(others) >= 0.3:
            flag = (f"{c} (the judge's own model) is graded best in {mine['unique_best']:.0%} of the positions where "
                    f"its answer differs from every other candidate's, against at most {max(others):.0%} for the "
                    "others. That gap may be real skill or self-preference: re-judge with another model "
                    "(--judge sonnet on --resume) and compare.")
    issues = [(pid, i) for pid, r in main.items() for i in r.get("issues") or []]
    probes = [p for r in main.values() for p in r.get("probes") or [] if p[0] and p[1]]
    return {"judge_model": judge_model, "same_model_candidates": same, "unique": rates, "self_preference": flag,
            "positions_with_issues": len({pid for pid, _ in issues}), "issues": issues[:10],
            "probes": len(probes), "probes_same": sum(1 for a, b in probes if a == b),
            "probes_within_one": sum(1 for a, b in probes if abs(J.SCORE[a] - J.SCORE[b]) <= 1),
            "confidence": _count(r["result"].get("confidence") for r in main.values())}


def cross_judges(graded: dict, primary: str | None, cands: list[str], answers: dict) -> list[dict]:
    out = []
    base = graded.get(primary) or {}
    for judge, records in graded.items():
        if judge == primary:
            continue
        same = within = n = 0
        scores = {c: [] for c in cands}
        for pid, r in records.items():
            mine = J.unblind(r["mapping"], r["result"]["grades"])
            theirs = J.unblind(base[pid]["mapping"], base[pid]["result"]["grades"]) if pid in base else {}
            for c in cands:
                g = (mine.get(c) or {}).get("grade")
                if g:
                    scores[c].append(J.SCORE[g])
                h = (theirs.get(c) or {}).get("grade")
                if g and h:
                    n += 1
                    same += g == h
                    within += abs(J.SCORE[g] - J.SCORE[h]) <= 1
        out.append({"judge": judge, "positions": len(records), "compared": n, "same": _rate(same, n),
                    "within_one": _rate(within, n), "mean_score": {c: mean(v) for c, v in scores.items()}})
    return out


def disagreements(rows: list[dict], main: dict, positions: dict, answers: dict, prepared: dict, k: int = 5):
    """The positions where the candidates' grades are furthest apart (most instructive first)."""
    by = {}
    for x in rows:
        by.setdefault(x["position"], []).append(x)
    conf = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(by, key=lambda pid: (-(max(x["score"] for x in by[pid]) - min(x["score"] for x in by[pid])),
                                         conf.get(main[pid]["result"].get("confidence"), 1), pid))
    out, groups = [], []
    for pid in ranked:
        spread = max(x["score"] for x in by[pid]) - min(x["score"] for x in by[pid])
        if spread == 0 or len(out) >= k:
            break
        p = positions[pid]
        if groups.count(p["group"]) >= 2 and len(ranked) > 2 * k:
            continue  # keep the examples varied
        groups.append(p["group"])
        r = main[pid]
        prep = prepared.get(pid) or {}
        out.append({"position": pid, "deck": p["deck"], "kind": p["kind"], "sub": p["sub"], "turn": p.get("turn"),
                    "source": f"{p['game']} #{p['decision']}", "question": prep.get("question"),
                    "spread": spread, "assessment": r["result"].get("assessment"), "own": r.get("own_answer"),
                    "confidence": r["result"].get("confidence"),
                    "answers": [{"candidate": x["candidate"], "grade": x["grade"], "reason": x["reason"],
                                 "answer": answers[(pid, x["candidate"])]["answer"],
                                 "why": answers[(pid, x["candidate"])].get("why")}
                                for x in sorted(by[pid], key=lambda y: -y["score"])]})
    return out


def games_summary(records: list[dict], cands: list[str]) -> dict | None:
    done = [r for r in latest(records, ("id",)).values() if r.get("status") == "done" and r.get("review")]
    if not done:
        return None
    out = {}
    order = {"blunder": 0, "major": 1, "minor": 2}
    for c in cands:
        mine = [r for r in done if r["candidate"] == c]
        mistakes = [{**m, "game": r["id"], "deck": r["deck"], "opponent": r["opponent"], "result": r["result"]}
                    for r in mine for m in r["review"].get("mistakes") or []]
        worst = sorted((m for m in mistakes if m.get("severity") in ("blunder", "major")),
                       key=lambda m: (order.get(m.get("severity"), 3), m["game"], m.get("decision") or 0))
        out[c] = {"games": len(mine), "like_for_like": sum(1 for r in mine if r.get("like_for_like")),
                  "mistakes_per_game": _rate(len(mistakes), len(mine)),
                  "significant_per_game": _rate(sum(r.get("significant") or 0 for r in mine), len(mine)),
                  "blunders_per_game": _rate(sum(1 for m in mistakes if m.get("severity") == "blunder"), len(mine)),
                  "wins": sum(1 for r in mine if r.get("result") == "win"),
                  "per_game": [{"game": r["id"], "deck": r["deck"], "opponent": r["opponent"], "index": r["index"],
                                "result": r["result"], "mistakes": len(r["review"].get("mistakes") or []),
                                "significant": r.get("significant"), "log_dir": r["log_dir"]} for r in mine],
                  "worst": worst[:3]}
    return out


def bench_context(run: dict, cands: list[str]) -> dict:
    """Win rate and cost per game of the candidates in the benchmark run the games came from (or the newest one)."""
    folder = (run.get("settings") or {}).get("games_from") or default_bench_run()
    summary = load_json(os.path.join(folder, "summary.json")) if folder else None
    if not summary:
        return {}
    out = {"folder": rel(folder)}
    for b in summary.get("backends") or []:
        if b.get("backend") in cands:
            out[b["backend"]] = {k: b.get(k) for k in ("games", "wins", "win_rate", "cost_per_game",
                                                       "latency_mean_s", "decisions_per_game")}
    return out


def recommend(s: dict) -> dict:
    """The model to standardise on: the cheapest one that the exam can't tell apart from the best (a paired difference
    whose 95% interval reaches within a quarter grade of zero), with how sure that is."""
    models = {c: m for c, m in s["models"].items() if m["graded"]}
    if not models:
        return {"choice": None, "confidence": "none", "text": "No graded positions yet."}
    best = max(models, key=lambda c: models[c]["mean_score"])
    pair = {(p["a"], p["b"]): p for p in s["pairs"]}

    def versus(a, b):
        """mean score a - b with its CI."""
        if (a, b) in pair:
            p = pair[(a, b)]
            return p["diff"], p["ci95"], p["n"]
        p = pair.get((b, a))
        if not p:
            return None, None, 0
        return -p["diff"] if p["diff"] is not None else None, [-p["ci95"][1], -p["ci95"][0]] if p["ci95"] else None, \
            p["n"]

    def cost(c):
        v = (s["bench"].get(c) or {}).get("cost_per_game")
        return v if v is not None else (models[c]["cost_per_decision"] or 0) * 60

    lines, choice = [], best
    for c in sorted(models, key=cost):
        if c == best:
            choice = best
            break
        diff, ci, n = versus(c, best)
        close_mistakes = (models[c]["mistake_rate"] or 0) <= (models[best]["mistake_rate"] or 0) + 0.10
        if diff is not None and ci and ci[1] >= -0.25 and ci[0] > -0.75 and close_mistakes:
            choice = c
            lines.append(f"{c} is within reach of {best} (mean grade {diff:+.2f}, 95% CI {ci[0]:+.2f} to "
                         f"{ci[1]:+.2f} over {n} positions) and cheaper.")
            break
        if diff is not None:
            lines.append(f"{c} scores below {best}: {diff:+.2f} grade points"
                         + (f" (95% CI {ci[0]:+.2f} to {ci[1]:+.2f})" if ci else "") + f" over {n} positions.")
    others = [c for c in models if c != choice]
    separated = []
    for c in others:
        diff, ci, n = versus(choice, c)
        if ci and (ci[0] > 0 or ci[1] < 0):
            separated.append(c)
    n = models[choice]["graded"]
    checks = s["judge_checks"]
    if n < 20 or checks.get("self_preference"):
        confidence = "low"
    elif len(separated) == len(others) and n >= 30:
        confidence = "high"
    else:
        confidence = "medium"
    why = []
    if n < 20:
        why.append(f"only {n} graded positions")
    if checks.get("self_preference"):
        why.append("a possible self-preference of the judge")
    if checks.get("probes") and checks["probes_same"] / checks["probes"] < 0.6:
        why.append(f"the judge gave the same move the same grade only {checks['probes_same']}/{checks['probes']} "
                   "times")
    close = [c for c in others if c not in separated]
    if choice != best:
        why.append(f"statistically tied with {best}, and cheaper")
        close = [c for c in close if c != best]
    if close:
        why.append(f"not separated from {', '.join(close)} at 95%")
    return {"choice": choice, "best": best, "confidence": confidence, "reasons": why, "lines": lines,
            "separated_from": separated}


def _pct(v) -> str:
    return "–" if v is None else f"{v:.0%}"


def _num(v, fmt="{:.2f}") -> str:
    return "–" if v is None else fmt.format(v)


def _ci_text(ci, fmt="{:.2f}") -> str:
    return "" if not ci else f" ({fmt.format(ci[0])}–{fmt.format(ci[1])})"


def report_md(s: dict) -> str:
    cands = s["candidates"]
    m = s["models"]
    rec = s["recommendation"]
    out = [f"# Decision exam: {s['name']}", ""]
    out.append(f"{s['graded']} positions graded by **{s['judge']}** (blind) out of {s['asked']} asked "
               f"({s['positions']} sampled; {len(s['excluded'])} excluded). Candidates: {', '.join(cands)}. "
               f"Each position is re-asked exactly as `ygo-agent replay` does: a fresh session with the duel history, "
               f"today's playbook and rules. Generated {s['generated']}.")
    out += ["", "## Recommendation", ""]
    if rec.get("choice"):
        bench = s["bench"].get(rec["choice"]) or {}
        out.append(f"**Standardise on {rec['choice']}** (confidence: {rec['confidence']}"
                   + (f"; {', '.join(rec['reasons'])}" if rec.get("reasons") else "") + ").")
        out.append("")
        for line in rec.get("lines") or []:
            out.append(f"- {line}")
        mc = m[rec["choice"]]
        out.append(f"- {rec['choice']}: mean grade {_num(mc['mean_score'])} of 4, mistakes or blunders in "
                   f"{_pct(mc['mistake_rate'])} of decisions, {_num(mc['latency_mean_s'], '{:.1f}')} s and "
                   f"${_num(mc['cost_per_decision'], '{:.3f}')} per exam decision"
                   + (f"; ${bench['cost_per_game']:.2f} per game in the benchmark" if bench.get("cost_per_game")
                      else "") + ".")
        if rec["best"] != rec["choice"]:
            mb = m[rec["best"]]
            out.append(f"- {rec['best']} scored highest ({_num(mb['mean_score'])}), at "
                       f"${_num(mb['cost_per_decision'], '{:.3f}')} per decision.")
    else:
        out.append(rec.get("text") or "No recommendation yet.")
    out += ["", "## Leaderboard", "",
            "Grades: best 4, good 3, acceptable 2, mistake 1, blunder 0. Intervals are 95% (bootstrap for the mean, "
            "Wilson for rates). \"Agrees\" = the judge would have played the same move.", "",
            "| model | graded | mean grade | best | best/good | mistake+blunder | blunder | agrees "
            "| latency (mean / p95) | cost / decision | invalid |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in sorted(cands, key=lambda c: -(m[c]["mean_score"] or -1)):
        x = m[c]
        ids = f" ({', '.join(x['model_ids'])})" if x.get("model_ids") else ""
        out.append(f"| {c}{ids} | {x['graded']} | {_num(x['mean_score'])}{_ci_text(x['ci95'])} | {_pct(x['best'])} | "
                   f"{_pct(x['best_or_good'])} | {_pct(x['mistake_rate'])}{_ci_text(x['mistake_ci'], '{:.0%}')} | "
                   f"{_pct(x['blunder_rate'])} | {_pct(x['agreement'])} | {_num(x['latency_mean_s'], '{:.1f}')} / "
                   f"{_num(x['latency_p95_s'], '{:.1f}')} s | ${_num(x['cost_per_decision'], '{:.3f}')} | "
                   f"{x['invalid_replies']} |")
    out.append("")
    out.append("Latency includes the CLI start-up of a fresh session per position (in games, pre-warming hides it), "
               "and every exam decision is a turn's first message (the whole duel log), so cost per decision is "
               "higher than in a game.")
    if s["pairs"]:
        out += ["", "## Paired comparisons", "", "Every candidate answered the same positions, so the differences are "
                "per position (luck-free).", "",
                "| A vs B | positions | mean grade A − B | A better | tie | B better | sign test p |",
                "|---|---:|---:|---:|---:|---:|---:|"]
        for p in s["pairs"]:
            out.append(f"| {p['a']} vs {p['b']} | {p['n']} | {_num(p['diff'], '{:+.2f}')}"
                       f"{_ci_text(p['ci95'], '{:+.2f}')} | {p['a_better']} | {p['ties']} | {p['b_better']} | "
                       f"{_num(p['p_sign'], '{:.3f}')} |")
    for title, key in (("By decision kind", "by_group"), ("By deck", "by_deck")):
        keys = sorted({k for c in cands for k in m[c][key]})
        if not keys:
            continue
        out += ["", f"## {title}", "", "Mean grade (mistake+blunder rate), n.", "",
                "| | " + " | ".join(cands) + " |", "|---|" + "---:|" * len(cands)]
        for k in keys:
            cells = []
            for c in cands:
                v = m[c][key].get(k)
                cells.append(f"{_num(v['mean_score'])} ({_pct(v['mistake_rate'])}), {v['n']}" if v else "–")
            out.append(f"| {k} | " + " | ".join(cells) + " |")
    jc = s["judge_checks"]
    out += ["", "## Can the judge be trusted?", ""]
    out.append(f"- **Self-preference.** The judge runs on {jc.get('judge_model')}"
               + (f", which is also the candidate {', '.join(jc['same_model_candidates'])}" if
                  jc.get("same_model_candidates") else "") + ". Graded best when its answer was the only one of its "
               "kind: " + ", ".join(f"{c} {_pct(v['unique_best'])} of {v['unique']}" for c, v in jc["unique"].items())
               + ".")
    out.append(f"  - {'⚠️ ' + jc['self_preference'] if jc.get('self_preference') else 'No sign of self-preference.'}")
    out.append(f"- **Self-consistency.** {jc['positions_with_issues']} of {s['graded']} positions have a reply that "
               "contradicts itself (e.g. its own pick not graded best)"
               + ("; e.g. " + "; ".join(f"{pid}: {i}" for pid, i in jc["issues"][:3]) if jc["issues"] else "") + ".")
    if jc["probes"]:
        out.append(f"- **Probes.** The same move shown twice (with two candidates' different reasons) got the same "
                   f"grade {jc['probes_same']}/{jc['probes']} times, within one grade {jc['probes_within_one']}/"
                   f"{jc['probes']}.")
    out.append(f"- **Confidence it reported:** " + ", ".join(f"{k} {v}" for k, v in jc["confidence"].items()) + ".")
    for x in s["cross_judges"]:
        out.append(f"- **Second judge {x['judge']}** ({x['positions']} positions): the same grade as {s['judge']} "
                   f"{_pct(x['same'])}, within one {_pct(x['within_one'])}; mean grades "
                   + ", ".join(f"{c} {_num(v)}" for c, v in x["mean_score"].items()) + ".")
    if s["disagreements"]:
        out += ["", "## The most instructive disagreements", ""]
        for d in s["disagreements"]:
            out.append(f"### {d['position']}: {d['deck']} {d['kind']} ({d['sub']}), turn {d.get('turn')}")
            out.append("")
            out.append(f"From `{d['source']}`. {d.get('question') or ''}")
            out.append("")
            out.append(f"> **Judge** ({d.get('confidence')} confidence): {d.get('assessment')}"
                       + (f" It would play {d['own']}." if d.get("own") else ""))
            out.append("")
            for a in d["answers"]:
                out.append(f"- **{a['candidate']}: {a['grade']}** — {a['answer']}")
                out.append(f"  - its reason: \"{(a.get('why') or '').strip()}\"")
                out.append(f"  - judge: {a.get('reason')}")
            out.append("")
    g = s.get("games")
    if g:
        out += ["", "## Whole-game reviews", "", "A blind review of whole logged games (model names removed) that "
                "counts the significant mistakes. Like-for-like games are the same deal (deck, opponent, seed) for "
                "every candidate.", "",
                "| model | games (like-for-like) | wins | mistakes / game | significant / game | blunders / game |",
                "|---|---:|---:|---:|---:|---:|"]
        for c in cands:
            x = g.get(c)
            if x:
                out.append(f"| {c} | {x['games']} ({x['like_for_like']}) | {x['wins']} | "
                           f"{_num(x['mistakes_per_game'], '{:.1f}')} | {_num(x['significant_per_game'], '{:.1f}')} | "
                           f"{_num(x['blunders_per_game'], '{:.1f}')} |")
        for c in cands:
            x = g.get(c)
            if x and x["worst"]:
                out += ["", f"**{c}, worst mistakes:**"]
                for w in x["worst"]:
                    out.append(f"- {w['severity']}, {w['deck']} vs {w['opponent']} ({w['result']}), decision "
                               f"#{w.get('decision')}: {w.get('what')} Better: {w.get('better')}")
    out += ["", "## Positions", "", "| id | deck | kind | from | " + " | ".join(cands) + " |",
            "|---|---|---|---|" + "---|" * len(cands)]
    by = {}
    for x in s["rows"]:
        by.setdefault(x["position"], {})[x["candidate"]] = x["grade"]
    exam_pos = {r["position"]: r for r in s["rows"]}
    for pid in sorted(by):
        r = exam_pos[pid]
        out.append(f"| {pid} | {r['deck']} | {r['group']}/{r['sub']} | " + s["sources"].get(pid, "") + " | "
                   + " | ".join(by[pid].get(c) or "–" for c in cands) + " |")
    if s["excluded"]:
        out += ["", "Excluded: " + "; ".join(f"{pid} ({why})" for pid, why in sorted(s["excluded"].items())) + "."]
    if s["incomplete"]:
        out += ["", f"Not graded yet (an answer is missing or failed; `--resume` retries): "
                    f"{', '.join(s['incomplete'])}."]
    if s["prompt_mismatch"]:
        out += ["", f"⚠️ Some candidates saw a different prompt than the prepared one (a per-profile prompt budget?): "
                    f"{', '.join(s['prompt_mismatch'])}."]
    prompts = s["run"].get("prompts") or {}
    out += ["", "## Notes", "", f"- Prompt versions (sha256 prefixes): " + ", ".join(f"{k} `{v}`" for k, v in
                                                                                   prompts.items()) + "."]
    if s["run"].get("prompts_now"):
        out.append("- ⚠️ The prompts changed while this run was in progress; answers span two versions.")
    pool = s["exam"].get("pool") or {}
    played = ", ".join(f"{k} {v}" for k, v in (pool.get("by_backend") or {}).items())
    out.append(f"- Sampled with seed {s['exam'].get('seed')} from {pool.get('decisions')} usable decisions in "
               f"{pool.get('games')} logged games ({played}).")
    out.append("- A candidate's answer is graded once per distinct move: copies of the same card and the same cards "
               "in another order count as one move, so identical choices always get the same grade.")
    return "\n".join(out) + "\n"


def short_game(game: str) -> str:
    """A game folder's name in a table: a benchmark game's job folder (deck--backend--opponent--n), else its own."""
    parts = os.path.normpath(game).split(os.sep)
    return parts[-2] if "bench" in parts[:-2] else parts[-1]


def build(folder: str) -> dict:
    data = load_run(folder)
    data["_folder"] = folder
    s = summarize(data)
    s["sources"] = {p["id"]: f"{short_game(p['game'])} #{p['decision']}" for p in data["exam.json"]["positions"]}
    save_json(os.path.join(folder, "summary.json"), s)
    with open(os.path.join(folder, "report.md"), "w", encoding="utf-8") as f:
        f.write(report_md(s))
    return s


def leaderboard_lines(s: dict) -> list[str]:
    out = []
    for c in sorted(s["candidates"], key=lambda c: -(s["models"][c]["mean_score"] or -1)):
        x = s["models"][c]
        out.append(f"  {c:<10} mean grade {_num(x['mean_score'])}{_ci_text(x['ci95'])}  mistakes "
                   f"{_pct(x['mistake_rate'])}  best {_pct(x['best'])}  ${_num(x['cost_per_decision'], '{:.3f}')}"
                   f"/decision  {x['graded']} graded")
    rec = s["recommendation"]
    if rec.get("choice"):
        out.append(f"  → {rec['choice']} (confidence {rec['confidence']})")
    return out


# ---- the command ----

def newest_run(name: str) -> str | None:
    found = sorted(glob.glob(os.path.join(RESULTS, f"*_{name}")))
    return found[-1] if found else None


def estimate(exam: dict, candidates: list[str], judges: list[str], cfg: dict, games: int) -> dict:
    from ..config import ConfigError, backend

    def model(name):
        try:
            return backend(cfg, name).get("model") or name
        except ConfigError:
            return name
    n = len(exam["positions"])
    cost = secs = 0.0
    for c in candidates:
        c_cost, c_secs = EST_ANSWER.get(model(c), (0.0, 0.1) if c in ("heuristic", "random") else EST_ANSWER["sonnet"])
        cost += n * c_cost
        secs += n * c_secs
    jcost = jsecs = 0.0
    for j in judges:
        j_cost, j_secs = EST_JUDGE.get(model(j), EST_JUDGE["sonnet"])
        jcost += n * j_cost
        jsecs += n * j_secs
    gcost = gsecs = 0.0
    if games and judges:
        g_cost, g_secs = EST_GAME.get(model(judges[0]), EST_GAME["sonnet"])
        gcost, gsecs = games * len(candidates) * g_cost, games * len(candidates) * g_secs
    return {"positions": n, "answers_usd": cost, "answers_s": secs, "judge_usd": jcost, "judge_s": jsecs,
            "games_usd": gcost, "games_s": gsecs, "total_usd": cost + jcost + gcost}


def main(args, cfg, what: list[str]) -> int:
    """`ygo-agent bench exam [NAME | report DIR]` (flags from bench/cli.py)."""
    import sys
    from .spec import split_list
    if what and what[0] == "report":
        if len(what) != 2:
            sys.exit("usage: ygo-agent bench exam report <run folder>")
        s = build(what[1])
        print("\n".join(leaderboard_lines(s)))
        print(f"\nWrote {os.path.join(what[1], 'report.md')} and summary.json.")
        return 0
    if len(what) > 1:
        sys.exit("give at most one exam name (bench/exams/<name>.json)")
    name = os.path.splitext(os.path.basename(what[0]))[0] if what else (args.name or "main")
    path = exam_path(what[0] if what else name)
    decks = split_list(args.decks) if args.decks else DEFAULT_DECKS
    candidates = split_list(args.backends) if args.backends else DEFAULT_CANDIDATES
    judges = split_list(args.judge) if args.judge else ["opus"]
    try:
        from ..cli import load_db
        db = load_db(cfg)
        folder = None
        if args.resume:
            folder = args.resume if isinstance(args.resume, str) else newest_run(name)
            if not folder or not os.path.isfile(os.path.join(folder, "run.json")):
                sys.exit(f"nothing to resume{f' in {folder}' if folder else ''} (no run.json)")
            exam = load_json(os.path.join(folder, "exam.json"))
        elif args.select or args.resample or not os.path.isfile(path):
            if os.path.isfile(path) and not args.resample:
                sys.exit(f"{rel(path)} exists; --resample replaces it (runs keep their own copy)")
            exam = make_exam(name, cfg, db, decks, args.positions or 40, args.seed if args.seed is not None else 1,
                             split_list(args.sources) if args.sources else None)
            save_json(path, exam)
            print(f"Selected {len(exam['positions'])} positions from {exam['pool']['decisions']} usable decisions in "
                  f"{exam['pool']['games']} games → {rel(path)}")
            print("  " + ", ".join(f"{k} {v}" for k, v in _count(f"{p['deck']}/{p['group']}"
                                                                for p in exam["positions"]).items()))
            if args.select:
                return 0
        else:
            exam = load_json(path)
        if args.dry_run:
            for p in exam["positions"]:
                print(f"  {p['id']} {p['deck']:<10} {p['group'] + '/' + p['sub']:<26} turn {p.get('turn')!s:<3} "
                      f"{p['choices']:>2} choices  score {p['score']:<4} {p['game']} #{p['decision']}")
            est = estimate(exam, candidates, judges, cfg, args.games or 0)
            par = args.parallel or 4
            minutes = (est["answers_s"] + est["judge_s"] + est["games_s"]) / par / 60
            print(f"\nEstimate: answers ${est['answers_usd']:.2f}, judge ${est['judge_usd']:.2f}"
                  + (f", game reviews ${est['games_usd']:.2f}" if est["games_usd"] else "")
                  + f" → about ${est['total_usd']:.0f} (API prices) and {minutes:.0f} min at --parallel {par}.")
            return 0
        if folder is None:
            folder = os.path.abspath(args.out) if args.out else os.path.join(
                RESULTS, f"{time.strftime('%Y-%m-%d_%H%M%S')}_{name}")
        runner = ExamRun(exam, folder, cfg, db, candidates, judges, parallel=args.parallel or 4,
                         budget=args.budget_usd, judge_batch=args.judge_batch or 3,
                         agentic=False if args.inline_judge else None,
                         probe=args.probe if args.probe is not None else 0.15, games=args.games or 0,
                         games_from=args.games_from, judge_effort=args.judge_effort,
                         probe_backends=not args.no_probe, argv=["ygo-agent", "bench"] + sys.argv[2:])
        print(f"Exam {name}: {len(exam['positions'])} positions, candidates {', '.join(candidates)}, judge "
              f"{', '.join(judges)} → {rel(folder)}")
        s = runner.run()
    except ExamError as e:
        sys.exit(f"error: {e}")
    print()
    print("\n".join(leaderboard_lines(s)))
    print(f"\nReport: {rel(os.path.join(folder, 'report.md'))}")
    return 0
