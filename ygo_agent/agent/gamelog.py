"""Live terminal output plus per-game log files (a readable game.md and a machine-readable game.jsonl)."""

import json
import os
import re
import sys
import threading
import time

from ..web.bus import Channel

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(code, text):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


DIM, BOLD, GREEN, CYAN, YELLOW, RED, MAGENTA = "2", "1", "32", "36", "33", "31", "35"


def slug(text, limit=24):
    """A short, filesystem-safe piece of a log folder name."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()
    return text[:limit].strip("-") or "unknown"


def unique_dir(parent, name):
    """Create parent/name, or name-2, name-3... if a game already started in the same second."""
    os.makedirs(parent, exist_ok=True)
    for n in range(1, 1000):
        candidate = name if n == 1 else f"{name}-{n}"
        try:
            os.mkdir(os.path.join(parent, candidate))
            return candidate
        except FileExistsError:
            continue
    raise OSError(f"too many game folders named {name} in {parent}")


RESULTS = {0: "win", 1: "loss", 2: "draw"}
USAGE = ("seconds", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cost_usd")


class GameLog:
    """One game's folder: game.md (readable), game.jsonl (everything the bot sent and the replies), prompts.jsonl
    (every prompt and model reply), feedback.md (!notes) and meta.json. A fresh timestamped folder is named
    <time>_<deck>, and gets -vs-<opponent> once the duel starts; games/latest points at the newest one.

    Everything it logs also goes to the web panel's bus (a no-op unless a panel is running; docs/web.md) as seat
    `seat` of game `game_id` (default: this folder's first name). `publish` defaults to `not quiet`."""

    def __init__(self, games_dir, deck_name, name=None, latest=True, quiet=False, deck_key=None, game_id=None,
                 seat=0, publish=None):
        self.quiet = quiet
        self.games_dir = games_dir
        self.latest = latest
        self.timestamped = not name
        if name:
            os.makedirs(os.path.join(games_dir, name), exist_ok=True)
            self.stem = name
        else:
            self.stem = f"{time.strftime('%Y-%m-%d_%H%M%S')}_{slug(deck_key or deck_name)}"
            name = unique_dir(games_dir, self.stem)
        self.name = name
        self.dir = os.path.join(games_dir, name)
        self._link_latest()
        self.md = open(os.path.join(self.dir, "game.md"), "w", encoding="utf-8")
        self.jsonl = open(os.path.join(self.dir, "game.jsonl"), "w", encoding="utf-8")
        self.prompts = open(os.path.join(self.dir, "prompts.jsonl"), "w", encoding="utf-8")
        self.md.write(f"# {deck_name} — game started {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        self.meta = {}
        self._flush()
        self._lock = threading.RLock()  # the panel's feedback box writes from another thread
        self._outcome = None            # the decision logged last, sent to the panel along with its reply
        self._advice = {}               # decision id -> what the agent suggested before the human chose
        self._usage = {}                # decision id -> the backend's time and tokens for it
        self.web = Channel(game_id or self.name, seat, enabled=not quiet if publish is None else publish)
        self.web.send("game_start", deck=deck_key, deck_name=deck_name, dir=self.dir, name=self.name)
        if not quiet:
            print(paint(BOLD, f"\n▶ New game — logging to {self.dir}"))

    def _link_latest(self):
        if not self.latest:
            return
        link = os.path.join(self.games_dir, "latest")
        try:
            if os.path.islink(link) or os.path.exists(link):
                os.remove(link)
            os.symlink(self.name, link)
        except OSError:
            pass

    def add_opponent(self, opponent):
        """Rename the folder to <time>_<deck>-vs-<opponent> (open files keep working across a rename)."""
        if not self.timestamped:
            return
        self.timestamped = False  # named once
        base = f"{self.stem}-vs-{slug(opponent)}"
        for n in range(1, 1000):
            target = base if n == 1 else f"{base}-{n}"
            if not os.path.exists(os.path.join(self.games_dir, target)):
                try:
                    os.rename(self.dir, os.path.join(self.games_dir, target))
                except OSError:
                    return
                self.name, self.dir = target, os.path.join(self.games_dir, target)
                self._link_latest()
                self.web.send("meta", dir=self.dir, name=self.name)
                return

    def write_meta(self, **fields):
        self.meta.update(fields)
        with open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2)
            f.write("\n")
        self.web.send("meta", **fields)

    def link_windbot_log(self, path):
        """Point <game>/windbot.log at the bot output file of the run this game belongs to."""
        try:
            os.symlink(os.path.relpath(path, self.dir), os.path.join(self.dir, "windbot.log"))
        except OSError:
            pass

    def _flush(self):
        self.md.flush()
        self.jsonl.flush()
        self.prompts.flush()

    def record(self, kind, payload):
        self.jsonl.write(json.dumps({"ts": round(time.time(), 3), "kind": kind, "msg": payload}) + "\n")
        self._flush()
        if not self.web.live:
            return
        if kind == "event":
            self.web.send("event", ev=payload)
            if payload.get("e") == "win":
                self.web.send("game_end", result=RESULTS.get(payload.get("result"), "draw"),
                              reason=payload.get("reason"))
        elif kind == "decide" and payload.get("kind") != "game_over":
            self.web.send("decision", decision=payload)
        elif kind == "reply":
            self._publish_reply(payload)

    def _publish_reply(self, record):
        """The panel's view of a reply: what was decided and why (from decision()), the backend's usage (from
        prompt()) and what was actually sent. A human's choice after a suggestion is also a human_choice."""
        did = record.get("id")
        outcome = self._outcome if self._outcome and self._outcome["id"] == did else {"id": did}
        self._outcome = None
        msg = {"choice": record.get("choice"), **outcome, "sent": record.get("choice"),
               "source": record.get("source") or outcome.get("source")}
        for key in ("say", "suggested"):
            if record.get(key) is not None:
                msg[key] = record[key]
        if did in self._usage:
            msg["usage"] = self._usage.pop(did)
        self.web.send("reply", **msg)
        if did in self._advice:
            advised = self._advice.pop(did)
            self.web.send("human_choice", id=did, choice=msg["choice"], advised=advised,
                          matched=msg["choice"] == advised)

    def prompt(self, decision_id, text, reply, info):
        self.prompts.write(json.dumps({"id": decision_id, "prompt": text, "reply": reply, "info": info}) + "\n")
        self._flush()
        if self.web.live:
            usage = self._usage.setdefault(decision_id, {})
            for key in USAGE:
                if isinstance(info.get(key), (int, float)):
                    usage[key] = round(usage.get(key, 0) + info[key], 4)
            if info.get("error"):
                usage["error"] = info["error"]

    def event(self, line):
        with self._lock:
            self._event(line)

    def _event(self, line):
        if self.quiet:
            self.md.write(f"- {line}\n")
            return
        if line.startswith("==="):
            print(paint(BOLD + ";" + MAGENTA, "\n" + line))
            self.md.write(f"\n## {line.strip('= ')}\n\n")
        elif line.startswith("--"):
            print(paint(DIM, line))
            self.md.write(f"*{line[2:].strip()}*\n\n")
        elif line.startswith("***"):
            print(paint(BOLD + ";" + YELLOW, line))
            self.md.write(f"\n**{line}**\n\n")
        else:
            print(paint(DIM, "  " + line))
            self.md.write(f"- {line}\n")
        self._flush()

    def decision(self, decision_id, question, options, chosen, why, plan, source, seconds=None, note=None,
                 label="backend", echo=True, write=True, fallback="the built-in AI"):
        """source: 'backend' (shown as `label`, e.g. "opus (claude-code)"), 'rule:<name>', 'auto', 'fallback' or
        'pilot'. echo/write: show it in the terminal / write it to game.md (copilot shows the advice first, and
        writes the decision once the human has made it)."""
        if len(options) > 40:  # e.g. "declare a card name": only show what was picked
            many = len(options)
            options = [t if i in chosen else "" for i, t in enumerate(options)]
        else:
            many = 0
        tag = {"backend": label, "auto": "auto", "fallback": f"FALLBACK ({fallback.removeprefix('the ')})"}.get(
            source, source)
        timing = f" ({seconds}s)" if seconds is not None else ""
        if echo:
            self._echo_decision(decision_id, question, options, chosen, why, plan, source, tag, timing, note, many)
        if write:
            with self._lock:
                self._write_decision(decision_id, question, options, chosen, why, plan, tag, timing, note)
        if self.web.live:
            outcome = {"id": decision_id, "choice": list(chosen or []), "why": why, "plan": plan, "source": source,
                       "label": label, "seconds": seconds, "note": note}
            if write:
                self._outcome = outcome
            else:  # shown before a human makes the call (copilot): that's advice
                self._advice[decision_id] = outcome["choice"]
                self.web.send("advice", **outcome, late=False)

    def _echo_decision(self, decision_id, question, options, chosen, why, plan, source, tag, timing, note, many):
        print(paint(BOLD + ";" + CYAN, f"\n  ? #{decision_id} {question}"))
        if many:
            print(paint(DIM, f"    ({many} options, showing the chosen one)"))
        for i, text in enumerate(options):
            if not text:
                continue
            mark = "▶" if i in chosen else " "
            line = f"    {mark} [{i}] {text}"
            print(paint(GREEN + ";" + BOLD, line) if i in chosen else paint(DIM, line))
        if not options and chosen in ([0], [1]):
            print(paint(GREEN + ";" + BOLD, f"    ▶ {'YES' if chosen == [1] else 'NO'}"))
        elif not chosen and source != "fallback":
            print(paint(GREEN + ";" + BOLD, "    ▶ (pass / none)"))
        color = RED if source == "fallback" else (YELLOW if source.startswith("rule") else CYAN)
        if why:
            print(paint(color, f"    ↳ {tag}{timing}: {why}"))
        else:
            print(paint(color, f"    ↳ {tag}{timing}"))
        if plan:
            print(paint(YELLOW, "    ✎ plan: " + plan.replace("\n", "\n            ")))
        if note:
            print(paint(RED, f"    ! {note}"))

    def _write_decision(self, decision_id, question, options, chosen, why, plan, tag, timing, note):
        self.md.write(f"\n**Decision #{decision_id}** — {question}\n\n")
        for i, text in enumerate(options):
            if not text:
                continue
            self.md.write(f"{'  - ✅' if i in chosen else '  -'} `[{i}]` {text}\n")
        if not options and chosen in ([0], [1]):
            self.md.write(f"  - ✅ {'YES' if chosen == [1] else 'NO'}\n")
        elif not chosen:
            self.md.write("  - ✅ (pass / none)\n")
        self.md.write(f"\n> **{tag}**{timing}: {why or ''}\n")
        if plan:
            self.md.write(f">\n> *Plan:* {plan}\n")
        if note:
            self.md.write(f">\n> ⚠️ {note}\n")
        self.md.write("\n")
        self._flush()

    def board(self, text):
        """Terminal-only board view for copilot mode (the full state is in game.jsonl anyway)."""
        print(paint(DIM, "\n    " + text.replace("\n", "\n    ")))

    def note(self, text):
        print(paint(YELLOW, f"    ✎ {text}"))
        with self._lock:
            self.md.write(f"> ✎ {text}\n\n")
            self._flush()

    def feedback(self, text, context, who="Opponent"):
        print(paint(BOLD + ";" + YELLOW, f"\n  ✍ feedback noted: {text}"))
        with self._lock:
            path = os.path.join(self.dir, "feedback.md")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"- ({context}) {text}\n")
            if not self.md.closed:  # a note from the panel can come after the game's log was closed
                self.md.write(f"\n> ✍ **{who} feedback** ({context}): {text}\n\n")
                self._flush()
        self.web.send("feedback_ack", text=text, context=context, who=who)

    def close(self):
        for f in (self.md, self.jsonl, self.prompts):
            try:
                f.close()
            except OSError:
                pass
