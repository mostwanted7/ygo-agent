"""The training run: setup, study, then rounds of lab + games + reviews until it converges, then the regression
cases and the report. Every step is checkpointed in the workspace (workspace.py), so `--resume` picks up where a run
stopped (Ctrl+C, the budget, a usage limit, a crash)."""

from __future__ import annotations

import concurrent.futures
import contextlib
import copy
import glob
import hashlib
import io
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field

from .. import decks, paths
from ..agent.gamelog import GREEN, slug
from ..match import MatchError, SeatSpec
from . import dossier as dossier_mod
from . import games as games_mod
from . import goldfish, lab, logs, prompts, report, review, rulepolicy, schemas
from . import playbook as pb
from .llm import Reviewer
from .workspace import BudgetExhausted, TrainerError, Workspace

EXAMPLE_DECKS = ("geargia", "saffira", "blackwing")  # the first is in the current house style
MAX_EXAMPLES = 2
RULES_TEMPLATE = '''"""Hard rules for the {name} deck, checked before the model is asked.

A rule is only for a mistake with no judgment in it that the play model keeps making even with a playbook lesson.
Mark it with the regression cases that prove it (@cases("case-name")); `ygo-agent test --deck <deck> --ablate-rules`
replays them without the rule to find the rules a model no longer needs. Each rule gets a
ygo_agent.agent.rules.Context and returns None (let the model decide) or Decide(choice, why).
"""

from ygo_agent.agent.rules import Decide, cases  # noqa: F401

RULES = []
'''


@dataclass
class Options:
    ydk: str | None
    name: str
    backend: str = "opus"              # the reviewer
    player_backend: str = "sonnet"     # lab and games
    opponents: list[str] = field(default_factory=lambda: ["windbot:Blue-Eyes", "windbot:Dragunity"])
    lab_hands: int = 10
    second_hands: int | None = None
    games: int = 4                     # per round
    max_rounds: int = 3
    budget: float | None = None
    seed: int = 1
    rules: str = "MR3"
    phases: tuple = ("study", "lab", "games")
    parallel: int = 2                  # games at a time
    lab_parallel: int = 3
    test_repeat: int = 3
    out: str | None = None             # the deck folder (default <user decks dir>/<name>; ygo_agent/decks.py)
    echo: str = "key"
    agentic: bool | None = None
    deck_name: str | None = None       # the display name (default: the .ydk's name)
    gate_repeat: int = 2               # runs per saved case when an edit is checked against them (0: no gate)
    write_rules: bool = False          # write qualifying rule proposals into rules.py (else train/rule-proposals.md)
    play_model: str | None = None      # the backend rules are calibrated to (default: config agent.backend)


class Trainer:
    def __init__(self, opts: Options, cfg: dict, db=None, engine=None, resume: bool = False, quiet: bool = False):
        self.o = opts
        self.cfg = cfg
        self._db, self._engine = db, engine
        self.resume = resume
        self.deck_dir = os.path.abspath(opts.out or os.path.join(decks.user_dir(cfg), opts.name))
        self.quiet = quiet
        self.ws: Workspace | None = None
        self.started = time.monotonic()

    # ---- shared resources ----

    @property
    def db(self):
        if self._db is None:
            from ..agent.carddb import CardDB
            self._db = CardDB(self.cfg["edopro_dir"])
            if not self._db.cards:
                raise TrainerError(f"no EDOPro card databases in {self._db.root}")
        return self._db

    @property
    def engine(self):
        if self._engine is None:
            from ..core import Engine
            self._engine = Engine.load(paths.resolve(self.cfg["edopro_dir"]))
        return self._engine

    def backend_profile(self, name: str) -> dict:
        from ..config import ConfigError, backend
        try:
            return backend(self.cfg, name)
        except ConfigError as e:
            raise TrainerError(str(e)) from None

    @property
    def reviewer(self) -> Reviewer:
        if not hasattr(self, "_reviewer"):
            self._reviewer = Reviewer(self.backend_profile(self.o.backend), self.db, self.o.agentic, self.o.name)
        return self._reviewer

    def profile(self):
        from ..agent.profile import Profile
        if decks.location_of(self.deck_dir, self.cfg):  # decks/<name> or the user decks dir
            return Profile(self.o.name, self.db, self.cfg, folder=self.deck_dir)
        return Profile(self.o.name, self.db, self.cfg, ydk=os.path.join(self.deck_dir, "deck.ydk"),
                       playbook=self.playbook_path)

    @property
    def playbook_path(self) -> str:
        return os.path.join(self.deck_dir, "playbook.md")

    def playbook(self) -> str:
        try:
            with open(self.playbook_path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def write_playbook(self, text: str, snapshot: str | None = None) -> None:
        with open(self.playbook_path, "w", encoding="utf-8") as f:
            f.write(text)
        if snapshot:
            self.ws.write(snapshot, text)

    # ---- the run ----

    def run(self) -> str:
        self.setup()
        ws = self.ws
        ws.set("status", "running")
        status = "done"
        try:
            if "study" in self.o.phases:
                self.study()
            rounds = self.o.max_rounds if {"lab", "games"} & set(self.o.phases) else 0
            for r in range(1, rounds + 1):
                if ws.result(f"r{r}.summary") is None and self.converged_before(r):
                    break
                self.round(r)
                if ws.result(f"r{r}.summary", {}).get("converged"):
                    ws.log(f"Round {r} found no significant mistakes: converged.", GREEN)
                    break
            if {"lab", "games"} & set(self.o.phases):
                self.condense("final")
                self.final_tests()
        except BudgetExhausted as e:
            status = "stopped: budget"
            ws.warn(f"Stopping: {e}.")
        except review.UsageLimited as e:
            status = "stopped: usage limit"
            ws.warn(f"Stopping: the model service hit a usage/rate limit ({e}). Run again with --resume after the "
                    "reset.")
        except KeyboardInterrupt:
            status = "stopped: interrupted"
            ws.warn("Interrupted. Run again with --resume to continue.")
        except TrainerError as e:
            status = "stopped: error"
            ws.error(f"Stopping: {e}. Fix it and run again with --resume.")
        except Exception as e:
            status = "stopped: crashed"
            ws.error(f"Crashed: {e!r}. The finished steps are saved; --resume continues.")
            raise
        finally:
            ws.set("status", status)
            ws.set("elapsed_s", round((ws.state.get("elapsed_s") or 0) + time.monotonic() - self.started, 1))
            path = report.write(self)
            ws.log(f"Report: {path}")
        return status

    def converged_before(self, r: int) -> bool:
        return any(self.ws.result(f"r{k}.summary", {}).get("converged") for k in range(1, r))

    # ---- setup ----

    def setup(self):
        o = self.o
        state_file = os.path.join(self.deck_dir, "train", "state.json")
        if os.path.isdir(self.deck_dir) and not self.resume:
            if os.path.isfile(state_file):
                raise TrainerError(f"{self.deck_dir} already has a training run: add --resume to continue it, or "
                                   "remove its train/ folder to start over")
            if os.path.isfile(os.path.join(self.deck_dir, "playbook.md")):
                raise TrainerError(f"{self.deck_dir} is an existing deck with a playbook; train into a new --name")
        if self.resume and not os.path.isfile(state_file):
            raise TrainerError(f"nothing to resume in {self.deck_dir}")
        if o.out and not decks.location_of(self.deck_dir, self.cfg) and set(o.phases) - {"study"}:
            raise TrainerError("--out (a deck folder outside decks/ and the user decks dir) only works with --phases "
                               "study")
        os.makedirs(os.path.join(self.deck_dir, "tests"), exist_ok=True)
        self.ws = ws = Workspace(self.deck_dir, o.budget, quiet=self.quiet)
        if self.resume:
            saved = ws.state.get("options") or {}
            ws.log(f"Resuming the training of {o.name} ({ws.spent:.2f} USD spent so far).")
            o.ydk = o.ydk or saved.get("ydk")
        ydk_copy = os.path.join(self.deck_dir, "deck.ydk")
        if not os.path.isfile(ydk_copy):
            if not o.ydk or not os.path.isfile(os.path.expanduser(o.ydk)):
                raise TrainerError(f"deck file not found: {o.ydk}")
            shutil.copyfile(os.path.expanduser(o.ydk), ydk_copy)
        deck_json = os.path.join(self.deck_dir, "deck.json")
        if not os.path.isfile(deck_json):
            name = o.deck_name or os.path.splitext(os.path.basename(o.ydk or "deck"))[0]
            with open(deck_json, "w", encoding="utf-8") as f:
                json.dump({"name": name, "ydk": "deck.ydk", "go_first": True}, f, indent=2)
                f.write("\n")
        rules_py = os.path.join(self.deck_dir, "rules.py")
        if not os.path.isfile(rules_py):
            with open(rules_py, "w", encoding="utf-8") as f:
                f.write(RULES_TEMPLATE.format(name=self.deck_display()))
        self.check_deck(ydk_copy)
        ws.set("options", {**asdict(o), "phases": list(o.phases)})
        ws.set("deck", {"name": self.deck_display(), "key": o.name, "dir": self.deck_dir})
        self.reviewer.check()

    def deck_display(self) -> str:
        try:
            with open(os.path.join(self.deck_dir, "deck.json"), encoding="utf-8") as f:
                return json.load(f).get("name", self.o.name)
        except (OSError, ValueError):
            return self.o.deck_name or self.o.name

    def check_deck(self, ydk: str) -> None:
        from ..arena.deck import DeckRules, check_deck, load_ydk
        from ..core.constants import rule_set
        try:
            loaded = load_ydk(ydk, self.engine.cards)
            err = check_deck(loaded.deck, self.engine.cards, DeckRules(forbidden_types=rule_set(
                self.o.rules.lower()).forbidden_types), loaded.unknown)
        except Exception as e:  # the install is missing: study can still run from the card database
            if set(self.o.phases) - {"study"}:
                raise TrainerError(f"can't check the deck: {e}") from None
            return
        if err:
            raise TrainerError(f"{ydk} is not legal under {self.o.rules}: {err}")

    # ---- reviewer calls ----

    def ask(self, step: str, kind: str, prompt: str, schema: dict, sync: list[str] | None = None) -> dict:
        """One reviewer call, with the budget check, the sandbox, the transcript and one retry."""
        ws = self.ws
        ws.check_budget(kind)
        rv = self.reviewer
        ws.write(f"calls/{step}.prompt.md", prompt)
        if rv.agentic:
            rv.sync(ws.dir, ["scripts", "dossier.md", "examples"] + (sync or []))
            with open(os.path.join(rv.sandbox, "playbook.md"), "w", encoding="utf-8") as f:
                f.write(self.playbook())
        system = prompts.system(self.o.rules, rv.agentic)
        for attempt in (1, 2):
            ws.log(f"{step}: asking the reviewer ({rv.label}{', agentic' if rv.agentic else ''})…")
            remaining = ws.remaining()
            out, info = rv.ask(kind, system, prompt, schema, transcript=ws.path(f"calls/{step}.transcript.jsonl"),
                               max_cost=remaining if remaining is not None else None)
            ws.spend(step, kind, info.get("cost_usd"), info.get("seconds"), backend=rv.label,
                     files_read=len(info.get("files_read") or []), error=info.get("error"))
            if info.get("files_read"):
                ws.write(f"calls/{step}.files.txt", "\n".join(info["files_read"]) + "\n")
            if out is not None:
                ws.write_json(f"calls/{step}.reply.json", out)
                ws.note(f"{step}: done in {info['seconds']:.0f}s, ${info.get('cost_usd') or 0:.2f}, "
                        f"{len(info.get('files_read') or [])} file reads")
                return out
            if review.limited(info.get("error")):
                raise review.UsageLimited(info.get("error"))
            ws.warn(f"{step}: the reviewer gave no usable reply ({info.get('error')})"
                    + ("; retrying" if attempt == 1 else ""))
            ws.check_budget(kind)
        raise TrainerError(f"{step}: the reviewer failed twice")

    # ---- study ----

    def examples(self) -> dict[str, str]:
        """Gold playbooks of other decks (never of this deck, or one that shares most of its cards)."""
        from ..agent.profile import parse_ydk
        mine = set(parse_ydk(os.path.join(self.deck_dir, "deck.ydk"))[0])
        out = {}
        for key in EXAMPLE_DECKS:
            folder = os.path.join(paths.DECKS, key)
            if os.path.abspath(folder) == self.deck_dir or not os.path.isfile(os.path.join(folder, "playbook.md")):
                continue
            try:
                theirs = set(parse_ydk(os.path.join(folder, "deck.ydk"))[0])
            except OSError:
                theirs = set()
            if theirs and len(mine & theirs) > 0.4 * len(mine):
                continue
            with open(os.path.join(folder, "playbook.md"), encoding="utf-8") as f:
                out[key] = f.read()
            if len(out) == MAX_EXAMPLES:
                break
        return out

    def dossier(self):
        if not hasattr(self, "_dossier"):
            if os.path.isfile(os.path.join(self.ws.dir, "cards.json")):
                self._dossier = dossier_mod.load(self.ws.dir, self.deck_display(), self.db)
            else:
                from ..core.install import EdoproInstall
                dirs = EdoproInstall.find(paths.resolve(self.cfg["edopro_dir"])).script_dirs
                self._dossier = dossier_mod.build(os.path.join(self.deck_dir, "deck.ydk"), self.db, dirs,
                                                  self.ws.dir, self.deck_display())
        return self._dossier

    def evidence(self, log_files: dict[str, str] | None = None) -> pb.Evidence:
        d = self.dossier()
        return pb.Evidence(os.path.join(self.ws.dir, "scripts"), log_files,
                           {c.name: c.text for c in d.cards})

    def study(self):
        ws = self.ws
        if ws.done("study"):
            return
        d = self.dossier()
        ws.log(f"Study: dossier of {len(d.cards)} cards ({len(d.text) // 1024} KB), "
               f"{len(d.missing_scripts)} missing scripts.")
        examples = self.examples()
        for key, text in examples.items():
            ws.write(f"examples/{key}.md", text)
        rv = self.reviewer
        general = self.profile().general_playbook
        prompt = prompts.study(self.deck_display(), d.text, general, examples, rv.agentic,
                               None if rv.agentic else dossier_mod.scripts_text(d))
        out = self.ask("study", "study", prompt, schemas.STUDY)
        text = pb.ensure_lessons((out.get("playbook") or "").strip() + "\n")
        problems = pb.problems(text)
        checks = self.check_card_facts(out.get("card_checks") or [])
        lines = [normal_line(x, i) for i, x in enumerate(out.get("lines") or [], 1)]
        self.write_playbook(text, "study/playbook-draft.md")
        self.set_go_first(out.get("go_first"), out.get("go_first_reason"))
        ws.set("lines", lines)
        self.add_questions(out.get("open_questions") or [], "study")
        ws.finish("study", {"size_kb": pb.size_kb(text), "problems": problems, "lines": len(lines),
                            "card_checks": checks, "open_questions": out.get("open_questions") or [],
                            "go_first": out.get("go_first"), "go_first_reason": out.get("go_first_reason")})
        ws.log(f"Study: draft playbook {pb.size_kb(text)} KB, {len(lines)} lines to test, "
               f"{checks['verified']}/{checks['total']} script citations verified"
               + (f"; problems: {', '.join(problems)}" if problems else ""))
        self.condense("study")

    def check_card_facts(self, checks: list[dict]) -> dict:
        ev = self.evidence()
        rows, good = [], 0
        for c in checks:
            ok, note = ev.check({"source": "script", "file": c.get("file"), "quote": c.get("quote")})
            good += ok
            rows.append(f"| {'✓' if ok else '✗'} | {c.get('card', '')} | {c.get('fact', '')} | `{c.get('file', '')}`: "
                        f"`{(c.get('quote') or '').replace('|', '/')[:90]}` |")
        self.ws.write("study/card-checks.md", "# Script citations from the study\n\n| ok | card | fact | quote |\n"
                                              "|---|---|---|---|\n" + "\n".join(rows) + "\n")
        return {"total": len(checks), "verified": good}

    def set_go_first(self, value, reason):
        if value is None:
            return
        path = os.path.join(self.deck_dir, "deck.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["go_first"] = bool(value)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    # ---- a round ----

    def round(self, r: int):
        ws = self.ws
        if ws.done(f"r{r}.summary"):
            return
        ws.log(f"=== Round {r} ===")
        summary = {"round": r}
        if "lab" in self.o.phases:
            results = self.lab(r)
            summary["lab"] = self.lab_review(r, results) if results else None
        if "games" in self.o.phases:
            records = self.games(r)
            summary["games"] = [{k: g.get(k) for k in ("id", "opponent", "result", "first", "turns", "reason")}
                                for g in records]
            reviews = self.reviews(r, records)
            summary["significant"] = sum(x.get("significant", 0) for x in reviews)
            summary["lessons"] = sum(len(x.get("accepted", [])) for x in reviews)
            summary["converged"] = bool(records) and summary["significant"] == 0
        self.condense(f"r{r}")
        summary["playbook_kb"] = pb.size_kb(self.playbook())
        self.write_playbook(self.playbook(), f"round-{r}/playbook.md")
        ws.finish(f"r{r}.summary", summary)

    # ---- lab ----

    def lines_to_test(self, r: int) -> list[dict]:
        lines = self.ws.state.get("lines") or []
        if r == 1:
            return lines
        status = self.ws.state.get("verification") or {}
        return [x for x in lines if status.get(x["id"], {}).get("status") not in ("verified",)]

    def lab(self, r: int) -> list[dict]:
        ws = self.ws
        step = f"r{r}.lab.plan"
        if ws.done(step):
            hands = [lab.LabHand.from_dict(h) for h in ws.result(step)]
        else:
            lines = self.lines_to_test(r)
            if r == 1:
                hands = lab.plan_hands(self.dossier(), lines, self.o.lab_hands, self.o.seed * 100 + r,
                                       self.o.second_hands)
            else:  # re-test what isn't verified yet, plus one random hand
                count = min(self.o.lab_hands, len(lines) + 1) if lines else 0
                hands = lab.plan_hands(self.dossier(), lines, count, self.o.seed * 100 + r,
                                       sum(1 for x in lines if x.get("going") == "second"), random_hands=1)
            ws.finish(step, [h.to_dict() for h in hands])
        if not hands:
            ws.log(f"Lab round {r}: every line is verified; no lab this round.")
            return []
        folder = ws.folder(f"round-{r}", "lab")
        todo = [h for h in hands if not ws.done(f"r{r}.lab.{h.id}")]
        ws.log(f"Lab round {r}: {len(hands)} hands ({len(todo)} to play) with {self.o.player_backend}.")
        backend = self.backend_profile(self.o.player_backend)
        profile = self.profile()

        def play(hand):
            ws.check_budget("lab-hand")
            t0 = time.monotonic()
            res = lab.run_hand(hand, self.engine, self.cfg, self.db, profile, backend, folder, rules=self.o.rules,
                               echo=self.o.echo if self.o.lab_parallel <= 1 else "off", tag=f"[lab {hand.id}]")
            res["log"] = ws.rel(res["log"]) if res.get("log") else None
            limited = review.game_usage_limited(os.path.join(ws.dir, res["log"])) if res.get("log") else None
            ws.spend(f"r{r}.lab.{hand.id}", "lab-hand", res.get("cost"), time.monotonic() - t0)
            if limited:
                raise review.UsageLimited(limited)
            ws.write_json(f"round-{r}/lab/{hand.id}.json", res)
            ws.finish(f"r{r}.lab.{hand.id}", {"file": f"round-{r}/lab/{hand.id}.json",
                                               "board": res.get("board_text"), "problems": len(res["problems"])})
            ws.note(f"lab {hand.id} ({hand.kind}{' ' + hand.line if hand.line else ''}): "
                    f"{res['decisions']} decisions, {len(res['problems'])} problems, ${res.get('cost') or 0:.2f}")
            return res
        self.parallel(play, todo, self.o.lab_parallel)
        results = []
        for h in hands:
            data = ws.read(f"round-{r}/lab/{h.id}.json")
            if data:
                results.append(json.loads(data))
        ws.write(f"round-{r}/lab/lab-results.md", lab.results_markdown(results, ws.state.get("lines") or [],
                                                                        goldfish.COMMON_BOARD_TEXT))
        return results

    def parallel(self, fn, items, workers: int):
        """Run fn over items, `workers` at a time; a budget/usage stop in one stops the rest from starting."""
        if not items:
            return []
        stop = []

        def guarded(item):
            if stop:
                return None
            try:
                return fn(item)
            except (BudgetExhausted, review.UsageLimited) as e:
                stop.append(e)
                return None
        if workers <= 1:
            out = [guarded(i) for i in items]
        else:
            with concurrent.futures.ThreadPoolExecutor(workers) as pool:
                out = list(pool.map(guarded, items))
        if stop:
            raise stop[0]
        return out

    def lab_review(self, r: int, results: list[dict]) -> dict:
        ws = self.ws
        step = f"r{r}.lab.review"
        if ws.done(step):
            return ws.result(step)
        rv = self.reviewer
        lines = ws.state.get("lines") or []
        tested = {x["line"] for x in results if x.get("line")}
        under_test = [x for x in lines if x["id"] in tested] or lines
        results_md = ws.read(f"round-{r}/lab/lab-results.md") or ""
        names = set()
        for x in results:
            for line in (x.get("condensed") or "").splitlines():
                for c in self.dossier().cards:
                    if f'"{c.name}"' in line:
                        names.add(c.name)
        questions = self.questions()
        prompt = prompts.lab_review(self.deck_display(), self.playbook(), results_md, under_test, r,
                                    self.o.player_backend, goldfish.COMMON_BOARD_TEXT, rv.agentic,
                                    None if rv.agentic else dossier_mod.scripts_text(self.dossier(), names),
                                    hands_dir=f"round-{r}/lab/", open_questions=questions)
        out = self.ask(step, "lab-review", prompt, schemas.LAB_REVIEW, sync=[f"round-{r}/lab"])
        status = dict(ws.state.get("verification") or {})
        by_key = {x["id"]: x for x in lines} | {x["name"].lower(): x for x in lines}
        verified_names = []
        for v in out.get("verification") or []:
            line = by_key.get(v.get("line")) or by_key.get((v.get("line") or "").lower())
            lid = line["id"] if line else v.get("line")
            status[lid] = {"status": v.get("status"), "round": r, "hands": v.get("hands") or [],
                           "reason": v.get("reason"), "name": line["name"] if line else v.get("line")}
            if v.get("status") == "verified" and line:
                verified_names.append(line["name"])
        logs_ = {x["id"]: os.path.join(ws.dir, x["log"], "game.md") for x in results if x.get("log")}
        evidence = self.evidence(logs_)

        def finish_text(t):
            t, acc, rej = review.apply_lessons(t, out.get("lessons"), f"{time.strftime('%Y-%m-%d')}, lab round {r}",
                                               evidence)
            t, mk = pb.mark_verified(t, verified_names, "verified in lab")
            return t, acc, rej, mk
        before = self.playbook()
        base, accepted, rejected, marked = finish_text(before)
        edited, changes = review.apply_sections(before, out.get("sections"))
        edited = finish_text(edited)[0]
        text, gate = self.gate(step, base, edited, "section edits") if changes else (base, None)
        new = [normal_line(x, len(lines) + i) for i, x in enumerate(out.get("new_lines") or [], 1)]
        merged = {x["id"]: x for x in lines}
        for x in new:
            if x["id"] in merged and status.get(x["id"], {}).get("status") != "verified":
                status.pop(x["id"], None)  # changed: test it again
            merged[x["id"]] = x
        ws.set("lines", list(merged.values()))
        ws.set("verification", status)
        self.write_playbook(text, f"round-{r}/playbook-after-lab.md")
        ws.state.setdefault("lessons", []).extend({"round": r, "source": "lab", **a} for a in accepted)
        ws.state.setdefault("rejected_lessons", []).extend({"round": r, "source": "lab", **a} for a in rejected)
        self.settle(out.get("settled_questions"), questions, f"lab round {r}")
        self.add_questions(out.get("open_questions") or [], f"lab round {r}")
        result = {"verification": out.get("verification") or [], "changes": changes, "marked": marked,
                  "new_lines": [x["id"] for x in new], "player_errors": out.get("player_errors") or [],
                  "accepted": len(accepted), "rejected": len(rejected), "gate": gate}
        ws.finish(step, result)
        counts = {}
        for v in out.get("verification") or []:
            counts[v.get("status")] = counts.get(v.get("status"), 0) + 1
        ws.log(f"Lab review {r}: {counts}; {len(changes)} section edit(s), {len(new)} new/changed line(s).")
        return result

    # ---- games ----

    def schedule(self, r: int) -> list[dict]:
        pool = self.ws.state.get("pool") or self.o.opponents
        n = self.o.games
        start = (r - 1) * n
        return [{"id": f"r{r}-g{i + 1}", "opponent": pool[(start + i) % len(pool)], "first": (start + i) % 2 == 0,
                 "seed": self.o.seed * 1000 + r * 100 + i + 1} for i in range(n)]

    def games(self, r: int) -> list[dict]:
        ws = self.ws
        if "pool" not in ws.state:
            ok, problems = games_mod.check_pool(self.o.opponents, self.engine, self.db, self.o.rules)
            for p in problems:
                ws.warn(f"opponent pool: {p}")
            if not ok:
                raise TrainerError("no usable opponent in the pool: " + "; ".join(problems))
            ws.set("pool", ok)
        slots = self.schedule(r)
        todo = [s for s in slots if not ws.done(f"r{r}.game.{s['id']}")]
        if ws.read(f"round-{r}/playbook-before-games.md") is None:  # what the games are played with
            ws.write(f"round-{r}/playbook-before-games.md", self.playbook())
        ws.log(f"Games round {r}: {len(slots)} ({len(todo)} to play) with {self.o.player_backend} against "
               f"{', '.join(sorted({s['opponent'] for s in slots}))}.")
        cfg = copy.deepcopy(self.cfg)
        cfg["games_dir"] = ws.folder(f"round-{r}", "games")
        cfg["chat"] = "off"
        spec = SeatSpec("agent", deck=self.o.name, backend=self.o.player_backend)

        def play(slot):
            ws.check_budget("game")
            t0 = time.monotonic()
            try:
                rec = games_mod.play_game(spec, slot["opponent"], seed=slot["seed"], first=slot["first"], cfg=cfg,
                                          db=self.db, engine=self.engine,
                                          out=ws.folder(f"round-{r}", "games", "runs", slot["id"]),
                                          rules=self.o.rules.lower(), echo=self.o.echo if self.o.parallel <= 1
                                          else "off")
            except MatchError as e:
                ws.error(f"game {slot['id']} failed: {e}")
                return None
            rec.update(id=slot["id"], want_first=slot["first"], opponent_text=games_mod.opponent_text(
                slot["opponent"]), log=ws.rel(rec["log"]) if rec.get("log") else None)
            ws.spend(f"r{r}.game.{slot['id']}", "game", rec.get("cost"), time.monotonic() - t0)
            limited = review.game_usage_limited(os.path.join(ws.dir, rec["log"])) if rec.get("log") else None
            if limited:
                raise review.UsageLimited(limited)
            ws.finish(f"r{r}.game.{slot['id']}", rec)
            ws.log(f"game {slot['id']} vs {slot['opponent']}: {rec['result']} in {rec['turns']} turns "
                   f"({'first' if rec['first'] else 'second'}), ${rec.get('cost') or 0:.2f}")
            return rec
        self.parallel(play, todo, self.o.parallel)
        return [ws.result(f"r{r}.game.{s['id']}") for s in slots if ws.done(f"r{r}.game.{s['id']}")]

    def reviews(self, r: int, records: list[dict]) -> list[dict]:
        out = []
        for g in records:
            out.append(self.review_game(r, g))
        return out

    def review_game(self, r: int, g: dict) -> dict:
        ws = self.ws
        step = f"r{r}.review.{g['id']}"
        if ws.done(step):
            return ws.result(step)
        rv = self.reviewer
        game_dir = os.path.join(ws.dir, g["log"])
        md = logs.read(os.path.join(game_dir, "game.md"))
        condensed = logs.condense(md)
        cond_rel = f"round-{r}/reviews/{g['id']}.condensed.md"
        ws.write(cond_rel, condensed)
        if rv.agentic:
            log_ref = (f"The full log is {g['log']}/game.md (every decision with all its options; grep it), and a "
                       f"condensed version is {cond_rel}: start there.")
        else:
            log_ref = "The game log (condensed: the chosen option of each decision, with the reason) follows.\n\n" \
                      f"```\n{condensed[:60000]}\n```"
        names = {c.name for c in self.dossier().cards if f'"{c.name}"' in md}
        recent = [x["text"] for x in (ws.state.get("lessons") or [])[-8:]]
        questions = self.questions()
        prompt = prompts.game_review(self.deck_display(), self.playbook(), {**g, "backend": self.o.player_backend},
                                     log_ref, logs.problems(md), rv.agentic,
                                     None if rv.agentic else dossier_mod.scripts_text(self.dossier(), names),
                                     recent, questions)
        out = self.ask(step, "review", prompt, schemas.GAME_REVIEW, sync=[g["log"], cond_rel])
        evidence = self.evidence({g["id"]: os.path.join(game_dir, "game.md"), g["log"]: os.path.join(game_dir,
                                                                                                   "game.md")})
        before = self.playbook()
        tag = f"{time.strftime('%Y-%m-%d')}, {g['id']} vs {g.get('opponent_text') or g.get('opponent')}"
        base, accepted, rejected = review.apply_lessons(before, out.get("lessons"), tag, evidence)
        base, marked = pb.mark_verified(base, out.get("confirmed_lines") or [], "verified in game")
        edited, changes = review.apply_sections(base, out.get("sections"))
        saved, case_problems = review.save_cases(self.profile(), game_dir, out.get("test_cases"))
        for p in case_problems:
            ws.warn(p)
        text, gate = self.gate(step, base, edited, "section edits") if changes else (base, None)
        self.write_playbook(text, f"round-{r}/playbook-after-{g['id']}.md")
        mistakes = out.get("mistakes") or []
        majors = [m for m in mistakes if m.get("severity") == "major"]
        major_ok = sum(1 for m in majors if m.get("verified") and evidence.verify(m.get("evidence") or [])[0])
        significant = min(int(out.get("significant_mistakes") or 0), len(majors)) if majors else 0
        if major_ok < significant:
            ws.note(f"{g['id']}: {significant - major_ok} major mistake(s) without checkable evidence")
        played_with = ws.read(f"round-{r}/playbook-before-games.md") or before
        ws.state.setdefault("mistakes", []).extend(
            {"round": r, "game": g["id"], "decision": m.get("decision"), "player": self.o.player_backend,
             "severity": m.get("severity"), "kind": m.get("kind"), "what": m.get("what"),
             "no_judgment": bool(m.get("no_judgment")),
             "covered": bool(m.get("playbook_had")) and pb.quote_found(m["playbook_had"], played_with)}
            for m in mistakes if m.get("verified"))
        self.rule_proposals(g, out.get("rule_proposals") or [], [m for m in mistakes if m.get("verified")],
                            played_with)
        general = []
        for item in out.get("general") or []:
            ok, notes = evidence.verify(item.get("evidence") or [])
            general.append({"text": item.get("text"), "verified": ok, "notes": notes, "game": g["id"]})
        self.append_general(general)
        ws.state.setdefault("lessons", []).extend({"round": r, "source": g["id"], **a} for a in accepted)
        ws.state.setdefault("rejected_lessons", []).extend({"round": r, "source": g["id"], **a} for a in rejected)
        ws.state.setdefault("tests_saved", []).extend({"round": r, "game": g["id"], **s} for s in saved)
        self.settle(out.get("settled_questions"), questions, g["id"])
        ws.save()
        ws.write_json(f"round-{r}/reviews/{g['id']}.json", out)
        result = {"significant": significant, "major_with_evidence": major_ok, "mistakes": len(mistakes),
                  "accepted": accepted, "rejected": len(rejected), "changes": changes, "marked": marked,
                  "tests": [s["name"] for s in saved], "summary": out.get("summary"), "gate": gate}
        ws.finish(step, result)
        ws.log(f"Review {g['id']}: {len(mistakes)} mistake(s), {significant} major; {len(accepted)} pitfall(s) added, "
               f"{len(rejected)} rejected for evidence; {len(saved)} test case(s); {len(changes)} section edit(s)"
               + (f" ({gate['kept']} kept after the case check)" if gate else "") + ".")
        return result

    def rule_proposals(self, g: dict, proposals: list[dict], mistakes: list[dict], played_with: str) -> None:
        """Assess each proposal against the rules policy (rulepolicy.py); write the ones that qualify into rules.py
        with --write-rules, and log every one in train/rule-proposals.md."""
        if not proposals:
            return
        names = {os.path.splitext(os.path.basename(p))[0] for p in self.case_files()}
        entries = []
        for p in proposals:
            e = rulepolicy.assess(p, mistakes, player=self.o.player_backend, play_model=self.play_model(),
                                  playbook=played_with, cases=names)
            e.update(game=g["id"], player=self.o.player_backend)
            if e["qualifies"] and self.o.write_rules and e["code"]:
                e["written"] = rulepolicy.write_rule(os.path.join(self.deck_dir, "rules.py"), e["code"], e["case"])
                if e["written"]:
                    self.ws.log(f"Rule {e['written']} written to rules.py (case {e['case']}).", GREEN)
            entries.append(e)
        path = self.ws.path("rule-proposals.md")
        new = not os.path.isfile(path)
        with open(path, "a", encoding="utf-8") as f:
            if new:
                f.write(rulepolicy.HEADER.format(play_model=self.play_model(), deck=self.o.name))
            for e in entries:
                f.write(rulepolicy.entry_markdown(e))
        self.ws.state.setdefault("rule_proposals", []).extend(entries)

    def append_general(self, items: list[dict]) -> None:
        if not items:
            return
        path = self.ws.path("general-proposals.md")
        new = not os.path.isfile(path)
        with open(path, "a", encoding="utf-8") as f:
            if new:
                f.write("# Proposed additions to playbooks/general.md\n\nLessons the reviewer thinks hold for every "
                        "deck. Not applied: copy the ones you agree with into playbooks/general.md.\n\n")
            for x in items:
                f.write(f"- ({x['game']}, evidence {'checked' if x['verified'] else 'NOT checked'}) {x['text']}\n")

    # ---- open questions ----

    def questions(self) -> list[str]:
        """The open questions still unanswered (the study's, the lab's, the reviews'), oldest first."""
        settled = {x["question"] for x in self.ws.state.get("settled_questions") or []}
        return [q for q in dict.fromkeys(self.ws.state.get("open_questions") or []) if q not in settled]

    def add_questions(self, items: list[str], source: str) -> None:
        have = set(self.ws.state.get("open_questions") or [])
        self.ws.state.setdefault("open_questions", []).extend(q for q in items if q and q not in have)
        self.ws.save()

    def settle(self, answers: list[dict] | None, asked: list[str], source: str) -> None:
        """Drop the open questions a review answered ({"question": its number in `asked`, "answer"})."""
        for a in answers or []:
            n = a.get("question")
            if isinstance(n, int) and 1 <= n <= len(asked):
                self.ws.state.setdefault("settled_questions", []).append(
                    {"question": asked[n - 1], "answer": a.get("answer") or "", "source": source})
        self.ws.save()

    # ---- the regression-case gate ----

    def play_model(self) -> str:
        return self.o.play_model or self.cfg["agent"]["backend"]

    def case_files(self) -> list[str]:
        return sorted(glob.glob(os.path.join(self.deck_dir, "tests", "*.json")))

    def case_score(self, text: str, label: str, allow_last: bool = False) -> dict | None:
        """Replay every saved case with `text` as the playbook (the player's backend, gate_repeat runs each):
        {"hash", "cases": {name: {"good", "repeat", "choices"}}, "good", "total"}; None without cases or with the
        gate off. Cached by text. allow_last: an unmeasured text may use the last accepted score instead (the text
        it grew from), which saves a measurement per gate."""
        files = self.case_files()
        if not files or self.o.gate_repeat <= 0:
            return None
        ws = self.ws
        h = hashlib.sha1(text.encode()).hexdigest()[:12]
        cache = ws.state.setdefault("case_scores", {})
        names = {os.path.splitext(os.path.basename(f))[0] for f in files}
        if h in cache and names <= set(cache[h]["cases"]):
            return cache[h]
        if allow_last and ws.state.get("gate_last"):
            return ws.state["gate_last"]
        from ..agent import replay
        repeat = self.o.gate_repeat
        ws.check_budget("test", len(files) * repeat)
        path = ws.write(f"gates/{label}.md", text)
        profile = self.profile()
        profile.playbook_path = path
        cfg = copy.deepcopy(self.cfg)
        cfg["agent"]["backend"] = self.o.player_backend
        cfg["chat"] = "off"
        cfg["games_dir"] = ws.folder("gates", label)
        results, t0 = [], time.monotonic()
        with contextlib.redirect_stdout(io.StringIO()):
            replay.run_tests(files, cfg, self.db, lambda key: profile, repeat, results=results)
        ws.spend(f"{label}.cases", "test", replay_cost(cfg["games_dir"]), time.monotonic() - t0,
                 runs=len(files) * repeat)
        score = {"hash": h, "label": label, "good": sum(x["good"] for x in results),
                 "total": sum(x["repeat"] for x in results),
                 "cases": {x["name"]: {"good": x["good"], "repeat": x["repeat"], "choices": x["choices"]}
                           for x in results}}
        cache[h] = score
        ws.save()
        return score

    def gate(self, step: str, before: str, after: str, what: str) -> tuple[str, dict | None]:
        """(the text to keep, a record). `after` is kept unless the saved cases pass less often with it than with
        `before`; then the reviewer gets one retry with the failing cases as feedback, and if that doesn't hold
        either, `before` is kept."""
        if after == before:
            return after, None
        ws = self.ws
        base = self.case_score(before, f"{step}.before", allow_last=True)
        if base is None:
            return after, None
        new = self.case_score(after, f"{step}.after")
        record = {"what": what, "before": score_text(base), "after": score_text(new)}
        lost = case_losses(base, new)
        if not lost:
            ws.set("gate_last", new)
            return after, {**record, "kept": "after"}
        ws.warn(f"{step}: the {what} made saved cases fail more often ({score_text(base)} → {score_text(new)}: "
                f"{', '.join(lost)}); asking the reviewer to fix it")
        failures = self.failure_details(lost, base, new)
        out = self.ask(f"{step}.revise", "condense", prompts.revise(before, after, failures, pb.TARGET_KB[1], what),
                       schemas.CONDENSE)
        revised = pb.ensure_lessons((out.get("playbook") or "").strip() + "\n")
        if out.get("playbook") and not [p for p in pb.problems(revised) if "KB" not in p]:
            again = self.case_score(revised, f"{step}.revised")
            record["revised"] = score_text(again)
            if not case_losses(base, again):
                ws.set("gate_last", again)
                return revised, {**record, "kept": "revised"}
        ws.warn(f"{step}: keeping the previous text")
        return before, {**record, "kept": "before", "failures": lost}

    def failure_details(self, names: list[str], base: dict, new: dict) -> list[dict]:
        """What the revise prompt shows for each case that got worse: the decision, the right and wrong options,
        and what the player chose."""
        from ..agent import replay
        from ..agent.describe import Describer
        describer = Describer(self.db)
        out = []
        for name in names:
            case = replay.load_case(os.path.join(self.deck_dir, "tests", f"{name}.json"))
            d = case["messages"][-1]
            options = describer.options(d)

            def say(choice):
                return " + ".join(options[i] for i in choice if 0 <= i < len(options)) or "pass"
            b, n = base["cases"].get(name, {}), new["cases"][name]
            out.append({"name": name, "note": case.get("note"), "question": describer.question(d)[:300],
                        "expected": [say(c) for c in case.get("expect") or []][:6],
                        "rejected": [say(c) for c in case.get("reject") or []][:4],
                        "chose": [say(c) for c in n["choices"] if isinstance(c, list)],
                        "before": f"{b.get('good', '?')}/{b.get('repeat', '?')}", "after": f"{n['good']}/{n['repeat']}"})
        return out

    def condense(self, tag: str):
        """Tighten the playbook when it's over the limit (after the study, each round, and at the end). Two tries;
        the smaller result is kept as long as it lost no section and the saved cases still pass as often (gate)."""
        ws = self.ws
        step = f"{tag}.condense"
        text = self.playbook()
        if len(text.encode()) <= pb.LIMIT_BYTES or ws.done(step):
            return
        best, tries, removed = text, [], []
        for attempt in (1, 2):
            out = self.ask(step if attempt == 1 else f"{step}-2", "condense",
                           prompts.condense(best, pb.TARGET_KB[1], previous_kb=tries[-1]["kb"] if tries else None),
                           schemas.CONDENSE)
            new = pb.ensure_lessons((out.get("playbook") or "").strip() + "\n")
            problems = [p for p in pb.problems(new) if "KB" not in p]
            tries.append({"kb": pb.size_kb(new), "problems": problems})
            if not problems and len(new) < len(best):
                best, removed = new, removed + (out.get("removed") or [])
            if len(best.encode()) <= pb.LIMIT_BYTES:
                break
        if best is text:
            ws.warn(f"condense rejected ({tries}); keeping the longer playbook")
            ws.finish(step, {"accepted": False, "tries": tries})
            return
        kept, gate = self.gate(step, text, best, "condense")
        if kept is text:
            ws.finish(step, {"accepted": False, "tries": tries, "gate": gate})
            return
        folder = {"study": "study", "final": "final"}.get(tag, f"round-{tag.lstrip('r')}")
        self.write_playbook(kept, f"{folder}/playbook-condensed.md")
        ws.finish(step, {"accepted": True, "from_kb": pb.size_kb(text), "to_kb": pb.size_kb(kept), "tries": tries,
                         "removed": removed, "gate": gate})
        ws.log(f"Condensed the playbook from {pb.size_kb(text)} to {pb.size_kb(kept)} KB"
               + (f" (cases {gate['before']} → {gate.get('revised') or gate['after']})" if gate else "") + ".")

    # ---- final ----

    def final_tests(self):
        """Re-run every saved case of the deck against the final playbook with the player's backend."""
        ws = self.ws
        if ws.done("final.tests"):
            return
        from ..agent import replay
        cases = self.case_files()
        if not cases:
            ws.finish("final.tests", {"cases": 0})
            return
        repeat = self.o.test_repeat
        n = ws.affordable("test", len(cases) * repeat)
        if n < len(cases) * repeat:
            repeat = max(1, n // len(cases))
            ws.check_budget("test", len(cases) * repeat)
        cfg = copy.deepcopy(self.cfg)
        cfg["agent"]["backend"] = self.o.player_backend
        cfg["chat"] = "off"
        cfg["games_dir"] = ws.folder("final-tests")
        profile = self.profile()
        ws.log(f"Re-running {len(cases)} saved case(s) x{repeat} with {self.o.player_backend}…")
        buf, results = io.StringIO(), []
        t0 = time.monotonic()
        with contextlib.redirect_stdout(buf):
            code = replay.run_tests(cases, cfg, self.db, lambda key: profile, repeat, results=results)
        ws.write("tests-final.txt", strip_ansi(buf.getvalue()))
        cost = replay_cost(cfg["games_dir"])
        ws.spend("final.tests", "tests", cost, time.monotonic() - t0, runs=len(cases) * repeat)
        passed = sum(x["passed"] for x in results)
        ws.finish("final.tests", {"cases": len(cases), "repeat": repeat, "passed": passed, "exit": code,
                                  "cost": round(cost, 4), "failed": [x["name"] for x in results if not x["passed"]]})
        ws.log(f"Regression cases: {passed}/{len(cases)} passed every run.")


def score_text(score: dict | None) -> str:
    return f"{score['good']}/{score['total']}" if score else "–"


def case_losses(base: dict, new: dict) -> list[str]:
    """The cases that pass less often in `new`, if the pass count over the cases both measured dropped; else []."""
    common = [k for k in new["cases"] if k in base["cases"]]
    if sum(new["cases"][k]["good"] for k in common) >= sum(base["cases"][k]["good"] for k in common):
        return []
    return [k for k in common if new["cases"][k]["good"] < base["cases"][k]["good"]]


def replay_cost(folder: str) -> float:
    """What the replayed decisions under `folder` cost (prompts.jsonl of each replay)."""
    cost = 0.0
    for path in glob.glob(os.path.join(folder, "replays", "*", "prompts.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                cost += (json.loads(line).get("info") or {}).get("cost_usd") or 0
    return cost


def normal_line(x: dict, n: int) -> dict:
    return {"id": (x.get("id") or f"L{n}").strip(), "name": (x.get("name") or f"line {n}").strip(),
            "going": x.get("going") if x.get("going") in ("first", "second") else "first",
            "key_cards": [c for c in x.get("key_cards") or [] if c][:4],
            "expected_board": x.get("expected_board") or [], "steps": x.get("steps") or ""}


def strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def deck_key(name: str) -> str:
    return slug(name, 40)
