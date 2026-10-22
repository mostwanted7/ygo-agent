"""What did training buy? The same games (opponent, seeds, who goes first) with three playbooks: the trained one, the
study-only draft, and none (the general playbook only). Writes decks/<name>/train/compare/compare.md."""

from __future__ import annotations

import collections
import copy
import os
import shutil
import time

from .. import paths
from ..match import MatchError, SeatSpec
from . import games as games_mod
from . import review
from .workspace import BudgetExhausted, TrainerError, Workspace, has_run

NO_PLAYBOOK = "(no playbook yet)\n"


def variant_folder(ws: Workspace, deck_dir: str, variant: str, display: str) -> str:
    """A loose-.ydk deck for the variant: <Display>.ydk + its playbook (+ the trained rules.py, so only the playbook
    differs)."""
    folder = ws.folder("compare", variant)
    ydk = os.path.join(folder, f"{display}.ydk")
    shutil.copyfile(os.path.join(deck_dir, "deck.ydk"), ydk)
    rules = os.path.join(deck_dir, "rules.py")
    if os.path.isfile(rules):
        shutil.copyfile(rules, os.path.join(folder, "rules.py"))
    if variant == "trained":
        src = os.path.join(deck_dir, "playbook.md")
    elif variant == "draft":
        src = os.path.join(ws.dir, "study", "playbook-condensed.md")
        if not os.path.isfile(src):
            src = os.path.join(ws.dir, "study", "playbook-draft.md")
    else:
        src = None
    with open(os.path.join(folder, f"{display}.md"), "w", encoding="utf-8") as f:
        if src and os.path.isfile(src):
            with open(src, encoding="utf-8") as s:
                f.write(s.read())
        elif variant == "none":
            f.write(NO_PLAYBOOK)
        else:
            raise TrainerError(f"no {variant} playbook ({src})")
    return ydk


def compare(cfg: dict, name: str, *, backend: str | None = None, opponent: str = "windbot:Blue-Eyes", games: int = 3,
            variants=("trained", "draft", "none"), seed: int = 7, parallel: int = 2, budget: float | None = None,
            db=None, engine=None) -> str:
    from .. import decks
    backend = backend or cfg["agent"]["backend"]  # the play model
    try:
        deck_dir = decks.find(name, cfg).dir
    except decks.DeckError as e:
        raise TrainerError(str(e)) from None
    if not has_run(deck_dir):
        raise TrainerError(f"{deck_dir} has no training run to compare")
    ws = Workspace(deck_dir)
    ws.budget = None if budget is None else ws.spent + budget  # the ledger already holds the training's costs
    from ..agent.carddb import CardDB
    from ..core import Engine
    db = db or CardDB(cfg["edopro_dir"])
    engine = engine or Engine.load(paths.resolve(cfg["edopro_dir"]))
    display = (ws.state.get("deck") or {}).get("name") or name
    ok, problems = games_mod.check_pool([opponent], engine, db, cfg["duel"]["rules"])
    if not ok:
        raise TrainerError("; ".join(problems))
    results = ws.state.setdefault("compare", {})
    jobs = []
    for variant in variants:
        ydk = variant_folder(ws, deck_dir, variant, display)
        for i in range(games):
            jobs.append((variant, i, ydk))
    run_cfg = copy.deepcopy(cfg)
    run_cfg["chat"] = "off"

    def play(job):
        variant, i, ydk = job
        key = f"{variant}-{i + 1}"
        if key in results:
            return
        ws.check_budget("game")
        c = copy.deepcopy(run_cfg)
        c["games_dir"] = ws.folder("compare", variant, "games")
        spec = SeatSpec("agent", deck=ydk, backend=backend, playbook=os.path.splitext(ydk)[0] + ".md")
        t0 = time.monotonic()
        try:
            rec = games_mod.play_game(spec, opponent, seed=seed * 1000 + i + 1, first=i % 2 == 0, cfg=c, db=db,
                                      engine=engine, out=ws.folder("compare", variant, "runs", key),
                                      rules=cfg["duel"]["rules"].lower(), echo="off")
        except MatchError as e:
            ws.error(f"compare {key} failed: {e}")
            return
        ws.spend(f"compare.{key}", "game", rec.get("cost"), time.monotonic() - t0)
        limited = review.game_usage_limited(rec["log"]) if rec.get("log") else None
        if limited:
            raise review.UsageLimited(limited)
        rec["log"] = ws.rel(rec["log"]) if rec.get("log") else None
        with ws._lock:
            results[key] = {"variant": variant, **{k: rec.get(k) for k in ("result", "first", "turns", "reason",
                                                                           "cost", "log")}}
            ws.save()
        ws.log(f"compare {key}: {rec['result']} in {rec['turns']} turns ({'first' if rec['first'] else 'second'})")
    stopped = None
    order = sorted(jobs, key=lambda j: (j[1], variants.index(j[0])))  # interleave, so a stop leaves fair counts
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max(1, parallel)) as pool:
            for f in [pool.submit(play, j) for j in order]:
                try:
                    f.result()
                except (BudgetExhausted, review.UsageLimited) as e:
                    stopped = stopped or str(e)
    finally:
        ws.save()
    return write_report(ws, results, variants, games, opponent, backend, stopped)


def write_report(ws, results, variants, games, opponent, backend, stopped) -> str:
    out = ["# Playbook comparison", "",
           f"{games} game(s) per playbook with {backend} against {opponent}; the same seeds and the same "
           "who-goes-first schedule for each playbook.", ""]
    if stopped:
        out += [f"Stopped early: {stopped}", ""]
    out += ["| playbook | games | W-L-D | win rate | mean turns | cost |", "|---|---|---|---|---|---|"]
    for v in variants:
        rs = [r for r in results.values() if r["variant"] == v]
        c = collections.Counter(r["result"] for r in rs)
        rate = f"{c['win'] / len(rs):.0%}" if rs else "–"
        turns = f"{sum(r['turns'] or 0 for r in rs) / len(rs):.1f}" if rs else "–"
        cost = sum(r.get("cost") or 0 for r in rs)
        out.append(f"| {v} | {len(rs)} | {c['win']}-{c['loss']}-{c['draw']} | {rate} | {turns} | ${cost:.2f} |")
    out += ["", "| game | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
    for i in range(games):
        cells = []
        for v in variants:
            r = results.get(f"{v}-{i + 1}")
            cells.append(f"{r['result']} ({'1st' if r['first'] else '2nd'}, {r['turns']}t)" if r else "–")
        out.append(f"| {i + 1} | " + " | ".join(cells) + " |")
    out.append("")
    return ws.write("compare/compare.md", "\n".join(out))
