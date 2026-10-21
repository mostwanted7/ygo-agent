"""Live terminal output plus per-game log files (a readable game.md and a machine-readable game.jsonl)."""

import json
import os
import re
import sys
import time

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


class GameLog:
    """One game's folder: game.md (readable), game.jsonl (everything the bot sent and the replies), prompts.jsonl
    (every prompt and model reply), feedback.md (!notes) and meta.json. A fresh timestamped folder is named
    <time>_<deck>, and gets -vs-<opponent> once the duel starts; games/latest points at the newest one."""

    def __init__(self, games_dir, deck_name, name=None, latest=True, quiet=False, deck_key=None):
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
                return

    def write_meta(self, **fields):
        self.meta.update(fields)
        with open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2)
            f.write("\n")

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

    def prompt(self, decision_id, text, reply, info):
        self.prompts.write(json.dumps({"id": decision_id, "prompt": text, "reply": reply, "info": info}) + "\n")
        self._flush()

    def event(self, line):
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
                 label="Claude", echo=True, write=True):
        """source: 'llm' (shown as `label`), 'rule:<name>', 'auto', 'fallback' or 'pilot'.
        echo/write: show it in the terminal / write it to game.md (copilot shows the advice first, and writes the
        decision once the human has made it)."""
        if len(options) > 40:  # e.g. "declare a card name": only show what was picked
            many = len(options)
            options = [t if i in chosen else "" for i, t in enumerate(options)]
        else:
            many = 0
        tag = {"llm": label, "auto": "auto", "fallback": "FALLBACK (built-in AI)"}.get(source, source)
        timing = f" ({seconds}s)" if seconds is not None else ""
        if echo:
            self._echo_decision(decision_id, question, options, chosen, why, plan, source, tag, timing, note, many)
        if write:
            self._write_decision(decision_id, question, options, chosen, why, plan, tag, timing, note)

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
        self.md.write(f"> ✎ {text}\n\n")
        self._flush()

    def feedback(self, text, context, who="Opponent"):
        print(paint(BOLD + ";" + YELLOW, f"\n  ✍ feedback noted: {text}"))
        path = os.path.join(self.dir, "feedback.md")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"- ({context}) {text}\n")
        self.md.write(f"\n> ✍ **{who} feedback** ({context}): {text}\n\n")
        self._flush()

    def close(self):
        for f in (self.md, self.jsonl, self.prompts):
            try:
                f.close()
            except OSError:
                pass
