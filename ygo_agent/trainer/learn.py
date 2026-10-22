"""`ygo-agent learn`: fold the deck owner's feedback into a deck's playbook, without playing a game.

    ygo-agent learn --deck geargia                   # every pending note, and the tips added since the last learn
    ygo-agent learn --deck geargia --list [--json]   # what is pending (no model call)
    ygo-agent learn --deck geargia --tip "..."       # add a tip to tips.md (no model call)

A note is a line the owner typed while a game was played (`!note` in the duel chat, the web panel's note box), saved in
that game's feedback.md right after the decision it follows (notes.py). For each game with pending notes, one reviewer
call gets the notes, the decisions they follow, the game log, the playbook, the owner's tips (tips.py) and the card
scripts. It checks each claim against the log and the scripts (owners are usually right about strategy; rulings get
checked), fixes the playbook (a principle when one is missing or wrong, a Known pitfall for a specific repeatable
mistake), proposes a regression case per decision, and gives each note a verdict: applied, already covered, or
disagree with the reason. The reply goes through the trainer's apply path (Trainer.apply_reply: quotes checked against
the files, section rewrites gated on the saved cases), then a condense if the playbook grew past its budget. Each note
is then marked in feedback.md with a one-line outcome, so it's never used twice. Tips added to tips.md since the
playbook last took them in are folded in by the first call, or by one of their own.

It works on any deck folder (decks/ or the user decks dir), trained or hand-written: the dossier is built into train/
when missing. A run's files are in <deck>/train/learn/<time>/ (prompts, replies, gates, report.md), with one line per
run in <deck>/train/learn.md; its state is under "learn" in train/state.json, apart from a training run's.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import shutil
import sys
import time

from .. import decks, paths
from . import notes as notes_mod
from . import tips as tips_mod
from .workspace import TrainerError

VERDICTS = {"applied": "applied", "already_covered": "already covered", "disagree": "disagree"}
STOPPED = 2
AGAIN = "The notes learned so far are marked; run learn again for the rest."


# ---- what is pending (no model call) ----

def find_deck(cfg: dict, key: str) -> decks.DeckDir:
    try:
        return decks.find(key, cfg)
    except decks.DeckError as e:
        raise TrainerError(str(e)) from None


def games_dir(cfg: dict) -> str:
    return paths.resolve(cfg.get("games_dir") or "games")


def deck_name(deck: decks.DeckDir, cfg: dict) -> str:
    try:
        return decks.deck_settings(deck.dir, deck.key, cfg).get("name", deck.key)
    except (OSError, ValueError):
        return deck.key


def learn_state(deck_dir: str) -> dict:
    """state.json's "learn" (read only; {} without one)."""
    try:
        with open(os.path.join(deck_dir, "train", "state.json"), encoding="utf-8") as f:
            return json.load(f).get("learn") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def tip_key(tip: dict) -> str:
    """A tip's identity (its title and text), to tell the ones a playbook already took in from new or edited ones."""
    return hashlib.sha1(f"{tip['title']}\n{' '.join(tip['text'].split())}".encode()).hexdigest()[:12]


def tips_status(deck_dir: str) -> dict:
    """The tips, and which ones the playbook hasn't taken in yet (added or edited since the study or the last learn
    that folded tips in)."""
    entries = tips_mod.entries(deck_dir)
    seen = set(learn_state(deck_dir).get("tips_seen") or [])
    new = [n for n, t in enumerate(entries, 1) if tip_key(t) not in seen]
    return {"path": tips_mod.path(deck_dir), "count": len(entries), "new": new, "digest": tips_mod.digest(deck_dir),
            "changed": bool(new)}


def game_folder(cfg: dict, name: str) -> str:
    """--game: a game folder, or the name of one in the games dir."""
    for path in (os.path.expanduser(name), os.path.join(games_dir(cfg), name)):
        if os.path.isfile(os.path.join(path, "meta.json")) or os.path.isfile(os.path.join(path, "game.md")):
            return os.path.abspath(path)
    raise TrainerError(f"no game folder {name!r} (neither a folder nor a game in {games_dir(cfg)})")


def pending(cfg: dict, deck: decks.DeckDir, games: list[str] | None = None,
            include_untrusted: bool = False) -> tuple[list[notes_mod.Note], list[notes_mod.Note]]:
    """(every pending note of the deck's games, newest game first; the ones learn uses: the owner's, or all of them
    with include_untrusted). `games` limits it to those game folders, which must be this deck's."""
    if games:
        every = []
        for name in games:
            folder = game_folder(cfg, name)
            played = str(notes_mod.read_meta(folder).get("deck") or "")
            if played.lower() != deck.key.lower():
                raise TrainerError(f"{folder} was played with the deck {played or '?'!r}, not {deck.key!r}")
            every += [n for n in notes_mod.read(folder) if n.pending]
    else:
        every = notes_mod.pending(deck.key, games_dir(cfg), include_untrusted=True)
    return every, [n for n in every if n.trusted or include_untrusted]


def status(cfg: dict, deck_key: str, games: list[str] | None = None, include_untrusted: bool = False) -> dict:
    """`learn --list`: the pending notes and the tips not folded in yet. No model call, nothing written."""
    deck = find_deck(cfg, deck_key)
    every, used = pending(cfg, deck, games, include_untrusted)
    tips = tips_status(deck.dir)
    return {"deck": deck.key, "name": deck_name(deck, cfg), "dir": deck.dir, "games_dir": games_dir(cfg),
            "notes": [{**n.to_dict(), "used": n in used} for n in every], "to_learn": len(used),
            "tips": {k: tips[k] for k in ("path", "count", "changed", "new")},
            "pending": bool(used or tips["new"])}


def add_tip(cfg: dict, deck_key: str, text: str) -> dict:
    deck = find_deck(cfg, deck_key)
    if not tips_mod.add(deck.dir, text, "Tip", deck_name(deck, cfg)):
        raise TrainerError("the tip is empty")
    return {"deck": deck.key, "path": tips_mod.path(deck.dir), "tips": len(tips_mod.entries(deck.dir))}


# ---- a run ----

class Lock:
    """One learn at a time per deck (two would use the same notes twice and overwrite each other's edits)."""

    def __init__(self, deck_dir: str):
        self.path = os.path.join(deck_dir, "train", "learn.lock")

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    with open(self.path, encoding="utf-8") as f:
                        pid = int(f.read().strip() or 0)
                    os.kill(pid, 0)
                except (OSError, ValueError):  # gone: a stale lock
                    os.remove(self.path)
                    continue
                raise TrainerError(f"another `ygo-agent learn` is running on this deck (pid {pid}; {self.path})")
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
            return self
        raise TrainerError(f"can't lock {self.path}")

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass


def run(cfg: dict, deck_key: str, *, games: list[str] | None = None, include_untrusted: bool = False,
        reviewer: str | None = None, player: str | None = None, gate_repeat: int = 2, budget: float | None = None,
        agentic: bool | None = None, quiet: bool = False, db=None) -> dict:
    """Learn the pending notes (and new tips) of a deck. Returns the run's summary (`status`: "done", "nothing to
    learn" or "stopped: <why>")."""
    deck = find_deck(cfg, deck_key)
    every, todo = pending(cfg, deck, games, include_untrusted)
    tips = tips_status(deck.dir)
    base = {"deck": deck.key, "name": deck_name(deck, cfg), "skipped_untrusted": len(every) - len(todo)}
    if not todo and not tips["new"]:
        return {**base, "status": "nothing to learn"}
    if not os.path.isfile(os.path.join(deck.dir, "playbook.md")):
        raise TrainerError(f"{deck.dir} has no playbook.md to learn into: train the deck first (ygo-agent train)")
    with Lock(deck.dir):
        return Learner(cfg, deck, todo, tips, base, reviewer=reviewer, player=player, gate_repeat=gate_repeat,
                       budget=budget, agentic=agentic, quiet=quiet, db=db).run()


class Learner:
    def __init__(self, cfg, deck, todo, tips, base, *, reviewer, player, gate_repeat, budget, agentic, quiet, db):
        from ..backends import BackendError
        from .pipeline import Options, Trainer
        from .workspace import LearnWorkspace
        self.cfg, self.deck, self.todo, self.tips_info, self.summary = cfg, deck, todo, tips, dict(base)
        self.run_id = time.strftime("%Y-%m-%d_%H%M%S")
        self.quiet = quiet
        opts = Options(ydk=None, name=deck.key, backend=reviewer or (cfg.get("trainer") or {}).get("backend", "opus"),
                       player_backend=player or "", out=deck.dir, gate_repeat=gate_repeat, budget=budget,
                       rules=cfg["duel"]["rules"], agentic=agentic, echo="off")
        self.t = Trainer(opts, cfg, db=db, quiet=quiet, interview="skip")
        self.t.backend_profile(opts.player_backend)  # a bad profile name fails here, before anything is written
        try:
            self.t.reviewer.check()
        except BackendError as e:
            raise TrainerError(f"the reviewer can't run: {e}") from None
        self.t.ws = self.ws = LearnWorkspace(deck.dir, self.run_id, budget, quiet=quiet)
        # Case scores depend on the player and on the cases, both of which may differ from the last run.
        self.ws.state["case_scores"] = {}
        self.ws.state.pop("gate_last", None)
        self.calls: list[dict] = []
        self.other_texts: dict[str, str] = {}

    # ---- the run ----

    def run(self) -> dict:
        from .review import UsageLimited
        from .workspace import BudgetExhausted
        t, ws = self.t, self.ws
        started = time.monotonic()
        status = "done"
        size_before = len(t.playbook().encode())
        tips_folded = False
        try:
            self.fresh_dossier()
            by_game = collections.OrderedDict()
            for n in sorted(self.todo, key=lambda n: (n.game, n.index)):  # oldest game first
                by_game.setdefault(n.game_dir, []).append(n)
            new_tips = self.tips_info["new"]
            ws.log(f"Learning {len(self.todo)} note(s) from {len(by_game)} game(s)"
                   + (f" and {len(new_tips)} new tip(s)" if new_tips else "") + f" into {self.summary['name']}'s "
                   f"playbook ({t.reviewer.label} reviews; saved cases replayed with {t.o.player_backend}).")
            jobs = list(by_game.items()) or [(None, [])]  # the new tips go with the first call
            for i, (game_dir, game_notes) in enumerate(jobs):
                self.calls.append(self.learn_call(game_dir, game_notes, new_tips if i == 0 else []))
                tips_folded = tips_folded or bool(new_tips)
            size = len(t.playbook().encode())
            if size > size_before:  # only what learn itself grew: a hand-written playbook's size is the owner's call
                from . import playbook as pb
                if size > pb.LIMIT_BYTES:
                    t.condense(self.run_id, folder=".")
        except BudgetExhausted as e:
            status = "stopped: budget"
            ws.warn(f"Stopping: {e}. {AGAIN}")
        except UsageLimited as e:
            status = "stopped: usage limit"
            ws.warn(f"Stopping: the model service hit a usage/rate limit ({e}). {AGAIN}")
        except TrainerError as e:
            status = "stopped: error"
            ws.error(f"Stopping: {e}. {AGAIN}")
        except KeyboardInterrupt:
            status = "stopped: interrupted"
            ws.warn(f"Interrupted. {AGAIN}")
        except Exception as e:
            status = "stopped: crashed"
            ws.error(f"Crashed: {e!r}. {AGAIN}")
            raise
        finally:
            if tips_folded:
                ws.state.update(tips_digest=self.tips_info["digest"],
                                tips_seen=[tip_key(x) for x in self.tips_entries])
            self.summary.update(self.totals(status, size_before, time.monotonic() - started))
            ws.state["runs"].append({k: self.summary[k] for k in ("run", "status", "notes", "verdicts", "tips",
                                                                  "kb_before", "kb_after", "cases", "cost")})
            ws.save()
            self.summary["report"] = self.write_report()
        return self.summary

    def fresh_dossier(self):
        """The dossier in train/, rebuilt when the deck list changed since it was made."""
        t = self.t
        d = t.dossier()
        profile = t.profile()
        have = {c.id for c in d.cards if c.section in ("main", "extra")}
        if have != set(profile.main) | set(profile.extra):
            self.ws.log("The deck list changed since the dossier was made: rebuilding it.")
            t.dossier(rebuild=True)

    def other_cards(self, md: str, limit: int = 40) -> dict[str, str | None]:
        """The cards a game log names that aren't in the deck (the opponent's, mostly; notes are often about them):
        {name: its script, copied into the run's scripts/ folder, or None}. Their texts go to self.other_texts."""
        from . import dossier as dossier_mod
        t = self.t
        named = set(re.findall(r'"([^"\n]{2,80})"', md)) - {c.name for c in t.dossier().cards}
        ids = {}
        for cid, card in t.db.cards.items():
            if card.name in named and (card.name not in ids or not card.alias):
                ids[card.name] = cid
        install = getattr(t.db, "install", None)
        dirs = install.script_dirs if install else []
        out = {}
        for name in sorted(ids)[:limit]:
            cid = ids[name]
            self.other_texts[name] = t.db.full_text(cid)
            src = dossier_mod.find_script(cid, dirs, t.db.cards[cid].alias) if dirs else None
            out[name] = None
            if src:
                out[name] = os.path.join(self.ws.dir, "scripts", os.path.basename(src))
                os.makedirs(os.path.dirname(out[name]), exist_ok=True)
                shutil.copyfile(src, out[name])
        return out

    @property
    def tips_entries(self) -> list[dict]:
        if not hasattr(self, "_tips"):
            self._tips = self.t.tips()  # read once: a tip added during the run is new next time
        return self._tips

    # ---- one reviewer call ----

    def learn_call(self, game_dir: str | None, game_notes: list, new_tips: list[int]) -> dict:
        from . import dossier as dossier_mod
        from . import logs, prompts, schemas
        from . import playbook as pb
        t, ws = self.t, self.ws
        rv = t.reviewer
        d = t.dossier()
        text = t.playbook()
        files, game, listed, decisions, log_ref, problems, logs_ = {}, None, [], "", "", [], None
        if game_dir:
            name = os.path.basename(game_dir)
            step = name
            md = logs.read(os.path.join(game_dir, "game.md"))
            meta = logs.meta(game_dir)
            condensed = ws.write(f"games/{name}/condensed.md", logs.condense(md))
            game = {"id": name, "mode": meta.get("mode"), "opponent": meta.get("opponent"),
                    "result": meta.get("result"), "first": meta.get("first"), "turns": len(logs.turns(md)),
                    "backend": (meta.get("backend") or {}).get("label")}
            listed = [{"n": i, "context": n.context, "author": n.author, "text": n.text, "trusted": n.trusted}
                      for i, n in enumerate(game_notes, 1)]
            blocks = [logs.decision_text(md, did, before=1) for did in sorted({n.decision for n in game_notes
                                                                              if n.decision})]
            decisions = "\n\n---\n\n".join(b for b in blocks if b)
            problems = logs.problems(md)
            if rv.agentic:
                files = {f"games/{name}/game.md": os.path.join(game_dir, "game.md"),
                         f"games/{name}/condensed.md": condensed}
                log_ref = (f"The full log is games/{name}/game.md (every decision with all its options and the "
                           f"player's reason; grep it), and a condensed version is games/{name}/condensed.md.")
            else:
                log_ref = ("The game log (condensed: the chosen option of each decision, with the reason) is at the "
                           "end of this message.")
            names = {c.name for c in d.cards if f'"{c.name}"' in md}
            others = self.other_cards(md)
            if rv.agentic:
                files.update({f"scripts/{os.path.basename(p)}": p for p in others.values() if p})
            logs_ = {name: os.path.join(game_dir, "game.md")}
            short = name[:17] if name[:4].isdigit() else name
            tag = f"{time.strftime('%Y-%m-%d')}, owner's note on game {short}"
        else:
            step = "tips"
            others = {}
            names = {c.name for c in d.cards if any(c.name in x["text"] for x in self.tips_entries)}
            tag = f"{time.strftime('%Y-%m-%d')}, owner's tip"
        prompt = prompts.learn(self.summary["name"], text, game=game, notes=listed, decisions=decisions,
                               log_ref=log_ref, problems=problems, tips=self.tips_entries, new_tips=new_tips,
                               agentic=rv.agentic, house_style=pb.house_style(text),
                               scripts=None if rv.agentic else dossier_mod.scripts_text(d, names))
        if game_dir and not rv.agentic:
            prompt += f"\n\n## The game log (condensed)\n\n```\n{logs.read(condensed)[:60000]}\n```"
            texts = [f"### {os.path.basename(p)} — {name}\n```lua\n{dossier_mod.strip_lua(logs.read(p))}\n```"
                     for name, p in others.items() if p]
            if texts:
                prompt += "\n\n## Scripts of the other cards in this game (comments stripped)\n\n" + \
                          "\n\n".join(texts)[:40000]
        out = t.ask(step, "learn", prompt, schemas.LEARN, files=files)
        evidence = t.evidence(logs_)
        evidence.more_scripts.append(os.path.join(ws.dir, "scripts"))
        evidence.card_texts.update(self.other_texts)
        applied = t.apply_reply(step, out, evidence, tag, game_dir, f"playbook-after-{step}.md",
                                max_cases=max(3, len(game_notes)))
        verdicts = {v.get("note"): v for v in out.get("notes") or [] if isinstance(v.get("note"), int)}
        marked = []
        for i, n in enumerate(game_notes, 1):
            v = verdicts.get(i)
            if not v:
                ws.warn(f"no verdict for note {i} of {n.game} ({n.text[:60]!r}): it stays pending")
                continue
            outcome = note_outcome(v, n, applied)
            if notes_mod.mark(n, outcome):
                marked.append({"key": n.key, "game": n.game, "decision": v.get("decision") or n.decision,
                               "note": n.text, "author": n.author, "verdict": v.get("verdict"), "outcome": outcome})
            else:
                ws.warn(f"couldn't mark note {n.key} in feedback.md (the file changed?)")
        tip_verdicts = [{"tip": v.get("tip"), "verdict": v.get("verdict"), "outcome": v.get("outcome"),
                         "title": self.tips_entries[v["tip"] - 1]["title"]}
                        for v in out.get("tips") or [] if isinstance(v.get("tip"), int)
                        and 1 <= v["tip"] <= len(self.tips_entries)]
        result = {"step": step, "game": game_dir and os.path.basename(game_dir), "summary": out.get("summary"),
                  "notes": marked, "tips": tip_verdicts, "open_questions": out.get("open_questions") or [],
                  "changes": [c for c in applied["changes"] if not c.startswith("ignored")],
                  "ignored": [c for c in applied["changes"] if c.startswith("ignored")],
                  "pitfalls": [a["text"] for a in applied["accepted"]],
                  "rejected": [{"text": a["text"], "notes": a["notes"]} for a in applied["rejected"]],
                  "cases": [{k: s.get(k) for k in ("name", "decision", "expect", "reject", "note")}
                            for s in applied["saved"]],
                  "case_problems": applied["case_problems"], "gate": applied["gate"]}
        ws.write_json(f"{step}.result.json", result)
        ws.finish(f"{self.run_id}.{step}", {k: result[k] for k in ("game", "changes", "pitfalls", "cases", "gate")})
        counts = collections.Counter(m["verdict"] for m in marked)
        ws.log(f"{step}: {len(marked)} note(s) marked ({', '.join(f'{k} {v}' for k, v in counts.items()) or 'none'})"
               + (f", {len(tip_verdicts)} tip verdict(s)" if tip_verdicts else "")
               + f"; {len(result['changes'])} section edit(s), {len(result['pitfalls'])} pitfall(s), "
               f"{len(result['cases'])} case(s)"
               + (f" (the case check kept the {applied['gate']['kept']} text)" if applied["gate"] else "") + ".")
        return result

    # ---- the summary and the report ----

    def totals(self, status: str, size_before: int, seconds: float) -> dict:
        from . import playbook as pb
        notes_ = [m for c in self.calls for m in c["notes"]]
        return {"run": self.run_id, "status": status, "notes": len(notes_),
                "verdicts": dict(collections.Counter(m["verdict"] for m in notes_)),
                "tips": [v for c in self.calls for v in c["tips"]],
                "kb_before": round(size_before / 1024, 1), "kb_after": pb.size_kb(self.t.playbook()),
                "cases": [s["name"] for c in self.calls for s in c["cases"]], "cost": self.ws.spent,
                "seconds": round(seconds, 1), "games": [c["game"] for c in self.calls if c["game"]],
                "playbook": self.t.playbook_path}

    def write_report(self) -> str:
        s, ws = self.summary, self.ws
        out = [f"# Learn: {s['name']}, {self.run_id.replace('_', ' ')}", "",
               f"Status: **{s['status']}**. Reviewer: {self.t.reviewer.label}; edits checked against the saved cases "
               f"with {self.t.o.player_backend} (x{self.t.o.gate_repeat}). Spent ${s['cost']:.2f} (API-price "
               f"equivalents) in {s['seconds']:.0f} s.",
               f"Playbook: {s['kb_before']} KB → {s['kb_after']} KB (`{decks.short(s['playbook'])}`; the version after "
               "each call is in this folder).", ""]
        if s.get("skipped_untrusted"):
            out += [f"{s['skipped_untrusted']} note(s) from spectators or from games the owner didn't play were left "
                    "pending (`--include-spectators` uses them).", ""]
        for c in self.calls:
            out += [f"## {'Game ' + c['game'] if c['game'] else 'Tips'}", ""]
            if c.get("summary"):
                out += [c["summary"], ""]
            if c["notes"]:
                out += ["| decision | note | verdict | outcome |", "|---|---|---|---|"]
                out += [f"| #{m['decision']} | {cell(m['note'])} | {VERDICTS.get(m['verdict'], m['verdict'])} | "
                        f"{cell(m['outcome'])} |" for m in c["notes"]]
                out.append("")
            if c["tips"]:
                out += ["Tips folded in:", ""] + [f"- {t['tip']}. {t['title']}: {VERDICTS.get(t['verdict'], t['verdict'])}"
                                                  f" — {t['outcome']}" for t in c["tips"]] + [""]
            edits = c["changes"] + [f"Known pitfall added: {p}" for p in c["pitfalls"]]
            if edits:
                out += ["Playbook edits:", ""] + [f"- {e}" for e in edits] + [""]
            if c["gate"]:
                g = c["gate"]
                out += [f"Checked against the saved cases: {g['before']} → {g['after']}"
                        + (f", fix-up {g['revised']}" if g.get("revised") else "") + f"; kept the {g['kept']} text.", ""]
            if c["rejected"]:
                out += ["Pitfalls dropped (their evidence didn't check out):", ""]
                out += [f"- {r['text']} ({'; '.join(r['notes']) or 'no evidence'})" for r in c["rejected"]] + [""]
            if c["cases"]:
                out += ["Regression cases saved:", ""]
                out += [f"- `{x['name']}` (#{x['decision']}): {x.get('note') or ''} expect {x['expect']} reject "
                        f"{x['reject']}" for x in c["cases"]] + [""]
            if c["case_problems"]:
                out += ["Cases not saved:", ""] + [f"- {p}" for p in c["case_problems"]] + [""]
            if c["open_questions"]:
                out += ["For you to settle:", ""] + [f"- {q}" for q in c["open_questions"]] + [""]
        out += ["## Cost", "", "| step | kind | cost | time |", "|---|---|---|---|"]
        out += [f"| {e['step']} | {e['kind']} | ${e.get('cost') or 0:.2f} | {e.get('seconds') or 0:.0f} s |"
                for e in ws.run_ledger()]
        path = ws.write("report.md", "\n".join(out) + "\n")
        index = os.path.join(ws.train_dir, "learn.md")
        new = not os.path.isfile(index)
        with open(index, "a", encoding="utf-8") as f:
            if new:
                f.write(f"# What `ygo-agent learn` changed in {s['name']}'s playbook\n\nOne line per run, newest last; "
                        "each run's report is in learn/<time>/report.md.\n\n")
            f.write(f"- {self.run_id.replace('_', ' ')}: {one_line_summary(s)} "
                    f"([report](learn/{self.run_id}/report.md))\n")
        return path


def note_outcome(v: dict, note: notes_mod.Note, applied: dict) -> str:
    """The line under the note in feedback.md: the verdict, the reviewer's one-liner, and what actually landed."""
    verdict = v.get("verdict") if v.get("verdict") in VERDICTS else "applied"
    said = " ".join(str(v.get("outcome") or "").split())
    decision = v.get("decision") or note.decision
    text = f"{VERDICTS[verdict]}: {said}"
    if verdict == "applied":
        mine = [a for a in applied["accepted"] if decision in (a.get("decisions") or [])]
        gate = applied["gate"] or {}
        kept = gate.get("kept") != "before"
        edited = [m.group(1) for c in applied["changes"] if not c.startswith("ignored")
                  for m in [re.search(r"## (.+?)(?: \(\d|$)", c)] if m] if kept else []
        if not mine and not edited:
            why = (f"the edit made saved cases fail ({gate['before']} → {gate['after']}), so the playbook kept its "
                   "previous text" if not kept else "no playbook edit got through the checks")
            return f"not applied: {why}; {said}"
        text += f" [edited: {', '.join(edited + (['Known pitfalls'] if mine else []))}]"  # what really changed
    cases = [s["name"] for s in applied["saved"] if s["decision"] == decision]
    return text + (f"; case {', '.join(cases)}" if cases else "")


def one_line_summary(s: dict) -> str:
    v = s.get("verdicts") or {}
    parts = [f"{s['notes']} note(s) from {len(s.get('games') or [])} game(s)"
             + (f" ({', '.join(f'{VERDICTS.get(k, k)} {n}' for k, n in v.items())})" if v else "")]
    if s.get("tips"):
        parts.append(f"{len(s['tips'])} tip(s) folded in")
    parts.append(f"playbook {s['kb_before']} → {s['kb_after']} KB")
    if s.get("cases"):
        parts.append(f"{len(s['cases'])} case(s) saved ({', '.join(s['cases'])})")
    parts.append(f"${s['cost']:.2f}")
    if s["status"] != "done":
        parts.append(s["status"])
    return "; ".join(parts)


def cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "/")


# ---- the command ----

def main(args, cfg) -> int:
    cfg["chat"] = "off"
    try:
        if args.tip is not None:
            info = add_tip(cfg, args.deck_key, args.tip)
            print(json.dumps(info) if args.json else f"Added a tip to {info['path']} ({info['tips']} tip(s)). "
                  f"`ygo-agent learn --deck {info['deck']}` folds it into the playbook.")
            return 0
        if args.list:
            info = status(cfg, args.deck_key, args.game, args.include_spectators)
            print(json.dumps(info, indent=1, ensure_ascii=False) if args.json else listing_text(info))
            return 0
        result = run(cfg, args.deck_key, games=args.game, include_untrusted=args.include_spectators,
                     reviewer=args.reviewer, player=args.player_backend, gate_repeat=args.gate_repeat,
                     budget=args.budget_usd, agentic=False if args.inline else None, quiet=args.quiet)
    except TrainerError as e:
        sys.exit(f"error: {e}")
    if result["status"] == "nothing to learn":
        print(f"Nothing to learn for {result['name']}: no pending notes from you and no new tips."
              + (f" ({result['skipped_untrusted']} note(s) from others: --include-spectators uses them.)"
                 if result.get("skipped_untrusted") else ""))
        return 0
    print(f"Learn {result['status']}: {one_line_summary(result)}.\nPlaybook: {result['playbook']}\n"
          f"Report: {result['report']}")
    return 0 if result["status"] == "done" else STOPPED


def listing_text(info: dict) -> str:
    out = [f"{info['name']} ({decks.short(info['dir'])}), notes from the games in {decks.short(info['games_dir'])}:"]
    if not info["notes"]:
        out.append("  no pending notes.")
    for n in info["notes"]:
        who = "" if n["trusted"] else f"  [not yours: {n['author']}; only with --include-spectators]"
        at = f"#{n['decision']}" if n.get("decision") else "?"
        out.append(f"  {n['game']} {at}: {n['text']}{who}")
    t = info["tips"]
    out.append(f"Tips: {t['count']} in {decks.short(t['path'])}, {len(t['new'])} not in the playbook yet."
               if t["count"] else "Tips: none (ygo-agent learn --deck NAME --tip \"...\" adds one).")
    out.append(f"`ygo-agent learn --deck {info['deck']}` learns {info['to_learn']} note(s)"
               + (" and the new tips." if t["new"] else ".") if info["pending"] else "Nothing to learn.")
    return "\n".join(out)
