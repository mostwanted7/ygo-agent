"""One run of an exam (bench/exams/results/<time>_<name>/): the positions prepared through a scripted brain (the same
text for every candidate), every candidate's answers, each judge's blind grades, the whole-game reviews, then the
report. Every answer and grade is appended to the run's files as it lands, so `--resume` asks only what is missing."""

from __future__ import annotations

import concurrent.futures
import itertools
import json
import os
import random
import time

from ... import paths
from ...agent.brain import DuelBrain, event_ids
from ...agent.describe import Describer
from ...agent.gamelog import GameLog
from .. import judge as J
from ..runner import LLM_TYPES, probe
from . import files
from .files import WRITE_LOCK, ExamError, append_jsonl, file_sha, latest, load_json, load_jsonl, rel, save_json, sha
from .positions import answer_key, fill_extra, read_log, render
from .report import build


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
    from ...backends.heuristic import first_legal
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
        self.exam, self.folder, self.db = exam, folder, db
        self.candidates, self.judges = list(candidates), list(judges)
        self.parallel, self.budget, self.judge_batch = max(1, parallel), budget or None, max(1, judge_batch)
        self.agentic, self.probe, self.games, self.games_from = agentic, probe, games, games_from
        self.judge_effort, self.probe_backends, self.argv, self.say = judge_effort, probe_backends, argv, say
        self.cfg = {**cfg, "chat": "off"}  # the exam never chats; the caller's config stays as it was
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
            from ...match import load_profile
            self.profiles[deck] = load_profile(deck, self.db, self.cfg)
        return self.profiles[deck]

    def backend(self, name: str, effort: str | None = None) -> dict:
        from ...config import ConfigError, backend
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
        from ...agent import replay
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
            with WRITE_LOCK:
                self.spent += record.get("cost_usd") or 0
            n = next(counter)
            what = record.get("answer") or record.get("error") or ""
            cost = f", ${record['cost_usd']:.3f}" if record.get("cost_usd") is not None else ""
            self.say(f"  [{n}/{len(jobs)}] {p['id']} {cand}: {record['status']} {what[:90]} "
                     f"({record.get('seconds') or 0:.1f}s{cost})")

        self._pool(work, jobs)

    def answer_one(self, p: dict, cand: str) -> dict:
        from ...agent import replay
        from ...trainer.review import limited
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
        from ...trainer.llm import Reviewer
        rv = Reviewer(self.backend(judge, self.judge_effort), self.db, self.agentic, name="exam")
        rv.sandbox = sandbox
        return rv

    def script_dirs(self) -> list[str]:
        try:
            from ...core.install import EdoproInstall
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
        with WRITE_LOCK:
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
        from ...trainer import logs
        source = self.games_from or files.default_bench_run()
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
            with WRITE_LOCK:
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
