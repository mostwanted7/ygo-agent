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


DIM, BOLD, GREEN, CYAN, YELLOW, RED, MAGENTA, BLUE = "2", "1", "32", "36", "33", "31", "35", "34"
ECHO = ("all", "decisions", "key", "off")
_PRINT = threading.Lock()  # several seats (and parallel games) print from their own threads


def emit(lines, tag=None):
    """Print lines as one block (no other seat's output in between), each prefixed with `tag` when given."""
    text = "\n".join(lines)
    if tag:
        text = "\n".join(f"{tag} {line}" if line.strip() else line for line in text.split("\n"))
    with _PRINT:
        print(text, flush=True)


def slug(text, limit=24):
    """A short, filesystem-safe piece of a log folder name."""
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()
    return text[:limit].strip("-") or "unknown"



def one_line(text, limit=4000):
    """A note or a name as one line of at most `limit` characters (newlines and control characters collapsed)."""
    return " ".join(str(text).split())[:limit]

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


def same_pick(choice, advised, kind=None):
    """Did the human play what the coach advised? A select_unselect prompt takes one pick at a time, so its advice
    (the whole selection) is followed when the human's pick is the first one advised."""
    if choice is None or advised is None:
        return False
    if kind == "select_unselect" and advised:
        return list(choice)[:1] == list(advised)[:1]
    return list(choice) == list(advised)


USAGE = ("seconds", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cost_usd")


class GameLog:
    """One game's folder: game.md (readable), game.jsonl (everything the bot sent and the replies), prompts.jsonl
    (every prompt and model reply), feedback.md (!notes) and meta.json. A fresh timestamped folder is named
    <time>_<deck>, and gets -vs-<opponent> once the duel starts; games/latest points at the newest one.

    Everything it logs also goes to the web panel's bus (a no-op unless a panel is running; docs/web.md) as seat
    `seat` of game `game_id` (default: this folder's first name). `publish` defaults to `not quiet`.

    Terminal output: `tag` (e.g. a coloured "[A Saffira·opus]") prefixes every line, for several seats in one
    terminal; `echo` is how much this seat prints: "all" (events and decisions, the default), "decisions" (the
    second seat of a self-play game: the first one already prints the events), "key" (one line per key play) or
    "off". `quiet` prints nothing and writes a plain game.md (replays, tests)."""

    def __init__(self, games_dir, deck_name, name=None, latest=True, quiet=False, deck_key=None, game_id=None,
                 seat=0, publish=None, tag=None, echo="all"):
        if echo not in ECHO:
            raise ValueError(f"echo must be one of {', '.join(ECHO)}")
        self.quiet = quiet
        self.tag = tag
        self.echo = "off" if quiet else echo
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
        self._advice = {}               # decision id -> (advised choice, kind): coach advice the human hasn't answered
        self._human = {}                # decision id -> the human's choice, logged before the advice came (late)
        self._usage = {}                # decision id -> the backend's time and tokens for it
        self.web = Channel(game_id or self.name, seat, enabled=not quiet if publish is None else publish)
        self.web.send("game_start", deck=deck_key, deck_name=deck_name, dir=self.dir, name=self.name)
        if self.echo in ("all", "decisions"):
            self.say("", paint(BOLD, f"▶ New game — logging to {self.dir}"))

    def say(self, *lines):
        """Terminal lines from this seat (tagged)."""
        emit(lines, self.tag)

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
        elif kind == "spectator_state":
            self.web.send("spectator_state", **payload)
        elif kind == "advice":
            usage = self._usage.pop(payload.get("id"), None)
            self.web.send("advice", **payload, **({"usage": usage} if usage else {}))
            did, advised = payload.get("id"), payload.get("choice")
            if advised is None:
                return
            if did in self._human:
                self._human_choice(did, self._human.pop(did), advised, payload.get("kind"))
            else:
                self._advice[did] = (advised, payload.get("kind"))

    def advice(self, decision_id, choice, **fields):
        """A recommendation for a human seat (coach mode): an `advice` row in game.jsonl and an `advice` message on
        the panel (fields: why, plan, source, label, seconds, late, kind...). The human's own move is logged as a
        reply with source "human", before or after it; whichever of the two comes second also publishes their
        `human_choice`. A choice of None marks a decision the coach doesn't weigh in on."""
        self.record("advice", {"id": decision_id, "choice": choice, **fields})

    def _human_choice(self, did, choice, advised, kind=None):
        self.web.send("human_choice", id=did, choice=choice, advised=advised, matched=same_pick(choice, advised, kind))

    def _publish_reply(self, record):
        """The panel's view of a reply: what was decided and why (from decision()), the backend's usage (from
        prompt()) and what was actually sent. A human's choice after a suggestion is also a human_choice."""
        did = record.get("id")
        outcome = self._outcome if self._outcome and self._outcome["id"] == did else {"id": did}
        self._outcome = None
        msg = {"choice": record.get("choice"), **outcome, "sent": record.get("choice"),
               "source": record.get("source") or outcome.get("source")}
        for key in ("say", "suggested", "trivial", "advised"):  # suggested: old copilot logs; the rest: coach games
            if record.get(key) is not None:
                msg[key] = record[key]
        if did in self._usage and msg["source"] != "human":  # a coach's usage goes with its advice
            msg["usage"] = self._usage.pop(did)
        self.web.send("reply", **msg)
        if did in self._advice:
            advised, kind = self._advice.pop(did)
            self._human_choice(did, msg["choice"], advised, kind)
        elif msg["source"] == "human":
            self._human[did] = msg["choice"]

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
        show = self.echo == "all"
        if line.startswith("==="):
            if show:
                self.say("", paint(BOLD + ";" + MAGENTA, line))
            self.md.write(f"\n## {line.strip('= ')}\n\n")
        elif line.startswith("--"):
            if show:
                self.say(paint(DIM, line))
            self.md.write(f"*{line[2:].strip()}*\n\n")
        elif line.startswith("***"):
            if show:
                self.say(paint(BOLD + ";" + YELLOW, line))
            self.md.write(f"\n**{line}**\n\n")
        else:
            if show:
                self.say(paint(DIM, "  " + line))
            self.md.write(f"- {line}\n")
        self._flush()

    def decision(self, decision_id, question, options, chosen, why, plan, source, seconds=None, note=None,
                 label="backend", echo=True, fallback="the built-in AI", key=False, turn=None):
        """source: 'backend' (shown as `label`, e.g. "opus (claude-code)"), 'rule:<name>', 'auto', 'fallback' or
        'human' (a coached human's own move; old copilot logs say 'pilot'). echo: show it in the terminal too.
        `key`: a key play, the only decisions the compact terminal view (echo "key") shows, with `turn`."""
        if len(options) > 40:  # e.g. "declare a card name": only show what was picked
            many = len(options)
            options = [t if i in chosen else "" for i, t in enumerate(options)]
        else:
            many = 0
        tag = {"backend": label, "auto": "auto", "fallback": f"FALLBACK ({fallback.removeprefix('the ')})"}.get(
            source, source)
        timing = f" ({seconds}s)" if seconds is not None else ""
        if echo and self.echo in ("all", "decisions"):
            self._echo_decision(decision_id, question, options, chosen, why, plan, source, tag, timing, note, many)
        elif echo and self.echo == "key" and key:
            self._echo_key(decision_id, options, chosen, why, source, tag, turn)
        with self._lock:
            self._write_decision(decision_id, question, options, chosen, why, plan, tag, timing, note)
        if self.web.live:
            self._outcome = {"id": decision_id, "choice": list(chosen or []), "why": why, "plan": plan,
                             "source": source, "label": label, "seconds": seconds, "note": note}

    def _echo_decision(self, decision_id, question, options, chosen, why, plan, source, tag, timing, note, many):
        out = ["", paint(BOLD + ";" + CYAN, f"  ? #{decision_id} {question}")]
        if many:
            out.append(paint(DIM, f"    ({many} options, showing the chosen one)"))
        for i, text in enumerate(options):
            if not text:
                continue
            mark = "▶" if i in chosen else " "
            line = f"    {mark} [{i}] {text}"
            out.append(paint(GREEN + ";" + BOLD, line) if i in chosen else paint(DIM, line))
        if not options and chosen in ([0], [1]):
            out.append(paint(GREEN + ";" + BOLD, f"    ▶ {'YES' if chosen == [1] else 'NO'}"))
        elif not chosen and source != "fallback":
            out.append(paint(GREEN + ";" + BOLD, "    ▶ (pass / none)"))
        color = RED if source == "fallback" else (YELLOW if source.startswith("rule") else CYAN)
        if why:
            out.append(paint(color, f"    ↳ {tag}{timing}: {why}"))
        else:
            out.append(paint(color, f"    ↳ {tag}{timing}"))
        if plan:
            out.append(paint(YELLOW, "    ✎ plan: " + plan.replace("\n", "\n            ")))
        if note:
            out.append(paint(RED, f"    ! {note}"))
        self.say(*out)

    def _echo_key(self, decision_id, options, chosen, why, source, tag, turn):
        """One line: "T3 #12 Normal Summon "X" (from hand) — why"."""
        picked = "; ".join(options[k] for k in chosen if 0 <= k < len(options) and options[k]) or (
            "YES" if chosen == [1] else "")
        why = (why or "").replace("\n", " ")
        if len(why) > 140:
            why = why[:137].rstrip() + "..."
        head = f"T{turn} #{decision_id}" if turn is not None else f"#{decision_id}"
        source_note = f" [{tag}]" if source != "backend" else ""
        self.say(paint(CYAN, f"{head} {picked}{source_note}") + (paint(DIM, f" — {why}") if why else ""))

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

    def append_md(self, text):
        """Raw Markdown appended to game.md (e.g. coach advice that arrived after the decision was written)."""
        with self._lock:
            if not self.md.closed:
                self.md.write(text.rstrip("\n") + "\n\n")
                self._flush()

    def note(self, text):
        if self.echo in ("all", "decisions"):
            self.say(paint(YELLOW, f"    ✎ {text}"))
        with self._lock:
            self.md.write(f"> ✎ {text}\n\n")
            self._flush()

    def feedback(self, text, context, who="Opponent"):
        """A note for whoever improves the deck. The file line names its author, because anyone in the room
        (the opponent, a spectator) can type one; and it is one line, so a note can't forge another entry."""
        text = one_line(text)
        who = one_line(who)[:80] or "Opponent"
        if self.echo != "off":
            self.say("", paint(BOLD + ";" + YELLOW, f"  ✍ feedback noted: {text}"))
        with self._lock:
            path = os.path.join(self.dir, "feedback.md")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"- ({context}; from {who}) {text}\n")
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
