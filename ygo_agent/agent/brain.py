"""One game as the agent sees it: events become the duel history; each decision goes through the rules first,
then to the model, and the validated answer goes back to the bot (see docs/decision-protocol.md)."""

import collections
import time

from .. import backends, paths
from ..config import backend as backend_profile
from .banter import Banter
from .describe import Describer
from .gamelog import GameLog, paint, BOLD, YELLOW, RED
from .prompts import SCHEMA, rules_from_flags
from .rules import Context, Rules
from .validate import validate

BOSS_TYPES = 0x40 | 0x80 | 0x2000 | 0x800000 | 0x4000000  # Fusion, Ritual, Synchro, Xyz, Link
BOSS_ATK = 2500
FIELD = (0x4, 0x8)


def card_key(c):
    return (c.get("id"), c.get("c"), c.get("l"), c.get("s"))


def event_ids(ev):
    ids = set()
    for key in ("id",):
        if isinstance(ev.get(key), int) and ev[key]:
            ids.add(ev[key])
    for key in ("card", "attacker", "target"):
        c = ev.get(key)
        if isinstance(c, dict) and c.get("id"):
            ids.add(c["id"])
    return ids


def chat_source(ev):
    """'duelist', 'spectator' or 'system'. STOC_CHAT events only carry the sender's player type (7 = observer)."""
    if ev.get("source"):
        return ev["source"]
    player = ev.get("player", 0)
    return "duelist" if player < 4 else "spectator" if player == 7 else "system"


class DuelBrain:
    def __init__(self, cfg, db, profile, log=None, prewarm=True, runtime=None, room=None):
        self.cfg = cfg
        self.db = db
        self.profile = profile
        self.rules = Rules(profile.dir)
        self.describer = Describer(db)
        self._log = log
        self.prewarm = prewarm
        self.runtime = runtime
        self.mode = cfg.get("mode", "play")
        self.copilot = self.mode == "copilot"
        self.backend = backend_profile(cfg)
        self.label = backends.label(self.backend)
        self.room = room
        self._system_prompt = None
        # The pilot's moves aren't the bot's, so no jokes in copilot mode.
        self.banter = Banter(enabled=cfg.get("chat") == "banter" and not self.copilot)
        self.history = []
        self.pending = []
        self.pending_ids = set()
        self.session = None
        self.session_turn = None
        self.session_seen = set()
        self.turn = 0
        self.retry = False
        self.plan = []
        self.plan_hint = None
        self.say_queue = []
        self.last_decision = None
        self.suggested = None
        self.feedback = 0
        self.stats = collections.Counter()
        self.seconds = 0.0
        self.started = False  # got this game's `start` event
        self.over = False     # got its `win` event
        self.chain_players = {}
        self.wiped = 0

    @property
    def log(self):
        # Created on first use, so a bot that never got into a duel leaves no empty log behind.
        if self._log is None:
            self._log = GameLog(paths.resolve(self.cfg.get("games_dir", "games")), self.profile.name,
                                deck_key=self.profile.key)
            self._log.write_meta(deck=self.profile.key, deck_name=self.profile.name, mode=self.mode,
                                 backend={k: self.backend.get(k) for k in ("name", "type", "model", "effort")},
                                 rules=self.rules_key, started=time.strftime("%Y-%m-%d %H:%M:%S"))
            if self.room:
                self._log.record("event", self.room)
            if self.runtime and self.runtime.windbot_log:
                self._log.link_windbot_log(self.runtime.windbot_log)
        return self._log

    @property
    def rules_key(self):
        """The room's real rules when the bot reported them, else the configured ones."""
        return rules_from_flags((self.room or {}).get("duel_flags")) or self.cfg["duel"]["rules"]

    @property
    def system_prompt(self):
        if self._system_prompt is None:
            self._system_prompt = self.profile.system_prompt(self.mode, self.rules_key)
        return self._system_prompt

    def say(self, line):
        if line:
            self.say_queue.append(line)

    # ---- events ----

    def on_event(self, ev):
        e = ev["e"]
        if e == "room":
            self.room = ev
            if self.session is None:
                self._system_prompt = None
            if self._log:
                self._log.record("event", ev)
            return
        self.log.record("event", ev)
        if e == "start":
            self.started = True
            names = ev.get("names") or []
            if len(names) > 1 and names[1]:
                self.log.add_opponent(names[1])
            self.log.write_meta(opponent=names[1] if len(names) > 1 else None, first=ev.get("first"))
            if self.runtime:
                self.runtime.duel_started.set()
            self.say(self.banter.line("start"))
        if e == "chat":
            return self.on_chat(ev)
        if e == "new_turn":
            self.turn = ev["turn"]
        if e == "retry":
            self.retry = True
        self.watch_for_big_plays(ev)
        self.pending_ids |= event_ids(ev)
        line = self.describer.event(ev)
        if line:
            self.history.append(line)
            self.pending.append(line)
            self.log.event(line)
        if e == "new_turn" and self.prewarm:
            self.ensure_session(ev["turn"])  # start the next turn's session while the engine keeps going
        if e == "win":
            self.over = True
            self.log.write_meta(result={0: "win", 1: "loss"}.get(ev.get("result"), "draw"),
                                ended=time.strftime("%Y-%m-%d %H:%M:%S"))
            self.say(self.banter.result(ev.get("result")))
            self.summary()

    def watch_for_big_plays(self, ev):
        """Banter cues: our boss monster hits the field, or our chain link clears 3+ of the opponent's cards."""
        e = ev["e"]
        if e == "summoning" and ev.get("special") and ev.get("to", {}).get("c") == 0:
            card = self.db.get(ev.get("id"))
            if card and card.type & BOSS_TYPES and card.atk >= BOSS_ATK:
                self.say(self.banter.line("boss"))
        elif e == "chaining":
            self.chain_players[ev.get("link")] = ev.get("player")
        elif e == "chain_solved":
            self.chain_players.pop(ev.get("link"), None)
        elif e == "chain_end":
            self.chain_players, self.wiped = {}, 0
        elif e == "move" and self.chain_players:
            src, dst = ev.get("from", {}), ev.get("to", {})
            resolving = self.chain_players[max(self.chain_players)]
            if resolving == 0 and src.get("c") == 1 and src.get("l") in FIELD and dst.get("l") not in FIELD:
                self.wiped += 1
                if self.wiped == 3:
                    self.say(self.banter.line("wipe"))

    def on_chat(self, ev):
        msg = ev.get("message", "").strip()
        source = chat_source(ev)
        if not msg or source == "system" or (source == "duelist" and ev.get("player") == ev.get("position")):
            return
        who = "A spectator" if source == "spectator" else "Opponent"
        if msg.startswith("!"):
            self.feedback += 1
            context = f"turn {self.turn}, right after decision #{self.last_decision}"
            self.log.feedback(msg[1:].strip(), context, who="Spectator" if source == "spectator" else "Opponent")
            self.say_queue.append(f"Noted feedback #{self.feedback}.")
        else:
            line = f'{who} says in chat: "{msg}"'
            self.history.append(line)
            self.pending.append(line)
            self.log.event(line)

    # ---- sessions ----

    def ensure_session(self, turn):
        s = self.session
        limit = self.cfg["agent"]["max_messages_per_session"]
        if s and (self.session_turn != turn or not s.alive or s.messages >= limit):
            s.close()
            self.session = None
        if self.session is None:
            self.session = backends.open_session(self.backend, self.system_prompt, SCHEMA)
            self.session_turn = turn
            self.session_seen = set(self.profile.ids)
        return self.session

    def build_message(self, d, question, options_text, first):
        parts = []
        if first:
            history = self.history[-500:]
            parts.append("A new session started for this turn. Duel log so far:\n" + "\n".join(history))
        elif self.pending:
            parts.append("What happened since your last decision:\n" + "\n".join(self.pending))
        self.pending = []
        ids = self.describer.ids_in_state(d["state"]) | self.describer.ids_in_decision(d) | self.pending_ids
        self.pending_ids = set()
        new = sorted(i for i in ids - self.session_seen if self.db.get(i))
        if new:
            self.session_seen |= set(new)
            parts.append("Card texts (not shown to you yet this turn):\n" + "\n".join("- " + self.db.full_text(i) for i in new))
        parts.append("CURRENT STATE\n" + self.describer.state(d["state"]))
        opts = "\n".join(f"[{i}] {t}" for i, t in enumerate(options_text))
        parts.append(f"DECISION #{d['id']}: {question}" + (f"\n{opts}" if opts else ""))
        return "\n\n".join(parts)

    def ask_model(self, d, question, options_text):
        session = self.ensure_session(d["state"]["turn"])
        text = self.build_message(d, question, options_text, first=session.messages == 0)
        timeout = self.cfg["agent"]["decision_timeout_seconds"]
        info = {}
        for _ in range(2):
            out, info = session.ask(text, timeout)
            self.log.prompt(d["id"], text, out, info)
            if out is None:
                if not session.alive:
                    self.session = None
                return None, None, None, info
            try:
                choice = [int(x) for x in out.get("choice", [])]
            except (TypeError, ValueError):
                choice = None
            err = "choice must be a list of integers" if choice is None else self.validate(d, choice)
            if not err:
                return choice, out.get("why", ""), out.get("plan"), info
            info["error"] = f"invalid reply {out.get('choice')}: {err}"
            text = f"That reply is invalid: {err}. Answer DECISION #{d['id']} again with a valid choice."
        return None, None, None, info

    # ---- decisions ----

    def validate(self, d, choice):
        return validate(d, choice)

    def next_planned(self, d):
        options = d.get("options", [])
        while self.plan:
            key = self.plan.pop(0)
            for i, o in enumerate(options):
                if card_key(o) == key:
                    return i
        return None

    def fill_extra(self, state):
        extra = state["me"]["extra"]
        if not extra or all(c and c.get("id") for c in extra):
            return
        remaining = collections.Counter(self.profile.extra)
        for zone in ("mz", "gy", "ban"):
            for c in state["me"][zone]:
                if c and remaining.get(c.get("id"), 0) > 0:
                    remaining[c["id"]] -= 1
        ids = list(remaining.elements())[:len(extra)]
        state["me"]["extra"] = [{"id": i, "c": 0, "l": 0x40, "s": k} for k, i in enumerate(ids)]

    def on_decide(self, d):
        self.log.record("decide", d)
        self.suggested = None
        kind = d["kind"]
        if kind == "game_over":
            return self.reply(d, None, "game_over")  # only a chance to send the end-of-duel chat line
        if d.get("state", {}).get("me"):
            self.fill_extra(d["state"])
        self.last_decision = d["id"]
        question = self.describer.question(d)
        options_text = self.describer.options(d)
        if kind != "select_unselect" or d.get("hint") != self.plan_hint:
            self.plan = []  # a planned multi-pick only continues within the same selection
        if self.copilot and kind in ("idle", "battle", "chain"):
            self.log.board(self.describer.state(d["state"]))

        if self.retry:
            self.retry = False
            self.stats["fallback"] += 1
            self.log.decision(d["id"], question, options_text, [], None, None, "fallback", label=self.label,
                              note="the engine rejected the previous answer, so the built-in AI answers this prompt")
            return self.reply(d, None, "fallback")

        if kind == "select_unselect" and self.plan:
            k = self.next_planned(d)
            if k is not None:
                self.log.decision(d["id"], question, options_text, [k], "continuing the selection planned above",
                                  None, "auto", label=self.label)
                return self.reply(d, [k], "auto")
            if d.get("finishable") or d.get("cancelable"):
                self.log.decision(d["id"], question, options_text, [], "planned selection complete", None, "auto",
                                  label=self.label)
                return self.reply(d, [], "auto")

        decided, source = self.rules.decide(Context(d, self.db, self.describer, self.profile))
        if decided is not None:
            self.stats["rule" if source.startswith("rule") else "auto"] += 1
            choice = decided.choice
            if decided.choice is not None or kind != "place":
                if source.startswith("rule"):
                    choice = self.conclude(d, question, options_text, choice, decided.why, None, source)
                else:
                    self.log.decision(d["id"], question, options_text, choice or [], decided.why, None, source,
                                      label=self.label)
            return self.finish(d, choice, source)

        choice, why, plan, info = self.ask_model(d, question, options_text)
        if choice is None:
            self.stats["fallback"] += 1
            note = f"{self.label} gave no usable answer ({info.get('error', 'unknown error')})"
            choice = self.conclude(d, question, options_text, None, None, None, "fallback", note=note)
            return self.finish(d, choice, "fallback" if choice is None else "pilot")
        self.stats["llm"] += 1
        self.seconds += info.get("seconds", 0)
        choice = self.conclude(d, question, options_text, choice, why, plan, "llm", info.get("seconds"),
                               note=info.get("error"))
        return self.finish(d, choice, "llm" if self.suggested is None else "pilot")

    def conclude(self, d, question, options_text, suggested, why, plan, source, seconds=None, note=None):
        """Log the decision and return the choice to send. In copilot mode the human makes the call first, with the
        suggestion as the default, and game.md records what they actually did."""
        args = (d["id"], question, options_text)
        if not self.copilot or d["kind"] in ("place", "go_first"):
            self.log.decision(*args, suggested or [], why, plan, source, seconds, note, label=self.label)
            return suggested
        self.log.decision(*args, suggested or [], why, plan, source, seconds, note, label=self.label, write=False)
        taken = self.pilot(d, options_text, suggested)
        if taken != suggested:
            self.suggested = suggested
            chose = f"The pilot chose {taken}" + (f" instead of the suggestion {suggested}." if suggested is not None
                                                  else " (there was no suggestion).")
            note = f"{note}; {chose}" if note else chose
        self.log.decision(*args, taken or [], why, plan, source, seconds, note, label=self.label, echo=False)
        return taken

    def pilot(self, d, options_text, suggested):
        """Copilot mode: the human makes the call, with the suggestion as the default."""
        kind = d["kind"]
        if not self.copilot or kind in ("place", "go_first"):
            return suggested
        yes_no = kind in ("effect_yn", "yesno")
        default = f"Enter = follow {self.label}" if suggested is not None else "Enter = let the built-in AI decide"
        how = "y/n" if yes_no else "option number(s), e.g. 2 or 0 3, '-' for none/pass"
        while True:
            raw = input(paint(BOLD, f"    ▷ your move ({default}; or type {how}): ")).strip().lower()
            if not raw:
                return suggested
            if yes_no:
                if raw not in ("y", "yes", "n", "no", "1", "0"):
                    continue
                pick = [1] if raw in ("y", "yes", "1") else [0]
            elif raw in ("-", "pass", "none"):
                pick = []
            else:
                try:
                    pick = [int(x) for x in raw.replace(",", " ").split()]
                except ValueError:
                    print(paint(RED, "    type option numbers from the list above"))
                    continue
            err = self.validate(d, pick)
            if err:
                print(paint(RED, f"    {err}"))
                continue
            if pick != suggested:
                self.stats["overridden"] += 1
                chosen = ", ".join(options_text[k] for k in pick) if options_text else ("yes" if pick == [1] else "no")
                text = f"The pilot chose {chosen or 'to pass'} instead of your suggestion."
                self.history.append(text)
                self.pending.append(text)
            return pick

    def finish(self, d, choice, source):
        if d["kind"] == "select_unselect" and choice:
            self.plan = [card_key(d["options"][k]) for k in choice[1:]]
            self.plan_hint = d.get("hint")
            choice = choice[:1]
        return self.reply(d, choice, source)

    def reply(self, d, choice, source=None):
        if choice is not None and d["kind"] == "announce_card":
            choice = [d["options"][choice[0]]]
        say = "\n".join(self.say_queue) or None
        self.say_queue = []
        record = {"id": d["id"], "choice": choice, "source": source}
        if self.suggested is not None:
            record["suggested"] = self.suggested
        if say:
            record["say"] = say
        self.log.record("reply", record)
        return {"id": d["id"], "choice": choice, "say": say}

    def summary(self):
        n = self.stats["llm"]
        avg = f", avg {self.seconds / n:.1f}s" if n else ""
        print(paint(BOLD, f"\n  Decisions: {n} by {self.label}{avg}, {self.stats['rule']} by rules, "
                          f"{self.stats['auto']} automatic, {self.stats['fallback']} fallbacks."
                          + (f" You overrode {self.label} {self.stats['overridden']} time(s)." if self.copilot else "")))
        print(paint(BOLD + ";" + YELLOW, f"  Game log: {self.log.dir}/game.md"))
        print(paint(YELLOW, "  Give your feedback to Claude Code in this repo's folder to update the playbook/rules.\n"))

    def close(self):
        if self.session:
            self.session.close()
            self.session = None
        if self._log:
            self._log.close()
