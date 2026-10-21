"""One game as the agent sees it: events become the duel history; each decision goes through the rules first,
then to the model, and the validated answer goes back to the bot (see docs/decision-protocol.md)."""

import collections
import time

from .. import backends, paths
from ..backends import Request
from ..config import backend as backend_profile
from .banter import Banter
from .describe import Describer
from .gamelog import GameLog, paint, BOLD, YELLOW
from .prompts import SCHEMA, rules_from_flags
from .rules import Context, Rules
from .stats import GameStats
from .validate import validate

BOSS_TYPES = 0x40 | 0x80 | 0x2000 | 0x800000 | 0x4000000  # Fusion, Ritual, Synchro, Xyz, Link
BOSS_ATK = 2500
FIELD = (0x4, 0x8)
KEY_ACTIONS = ("activate", "summon", "spsummon", "set_monster", "set_spell", "attack", "reposition")
FALLBACKS = ("bot", "heuristic")
# Backend profile keys meta.json records (never headers or keys).
META_KEYS = ("name", "type", "model", "effort", "base_url", "json_mode", "structured", "api_key_env", "temperature",
             "max_tokens", "num_ctx", "history_lines", "card_texts", "max_session_messages", "seed")


def card_key(c):
    return (c.get("id"), c.get("c"), c.get("l"), c.get("s"))


def event_ids(ev):
    """The card codes an event names (their texts go into the next prompt if the session hasn't seen them)."""
    ids = set()
    if isinstance(ev.get("id"), int) and ev["id"]:
        ids.add(ev["id"])
    cards = [ev.get(key) for key in ("card", "attacker", "target")] + list(ev.get("cards") or [])  # confirm, swap
    for c in cards:
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
    """One game for one seat. `backend` (a profile dict or a Backend) overrides the config's agent.backend;
    `fallback` is who answers when the backend can't: "bot" (choice null, WindBot's own AI) or "heuristic".
    `mode` overrides the config's (play, selfplay, teach, coach); `opponent` describes who it plays against
    (prompts.opponent_text); `log_options` go to its GameLog (terminal tag and verbosity, see GameLog)."""

    def __init__(self, cfg, db, profile, log=None, prewarm=True, runtime=None, room=None, backend=None,
                 fallback=None, game_id=None, seat=0, mode=None, opponent=None, log_options=None):
        self.cfg = cfg
        self.db = db
        self.profile = profile
        self.rules = Rules(profile.dir)
        self.describer = Describer(db)
        self._log = log
        self.game_id = game_id  # the web panel's ids for this game and seat (several seats can share a game)
        self.seat = seat
        if getattr(log, "web", None):
            log.web.on_feedback(self.panel_note)
        self.prewarm = prewarm
        self.runtime = runtime
        self.mode = mode or cfg.get("mode", "play")
        self.opponent = opponent
        self.log_options = dict(log_options or {})
        if backend is None:
            backend = backend_profile(cfg)
        self.backend = backends.create(backend, db=db)
        self.backend_cfg = self.backend.profile
        self.label = self.backend.label
        agent = cfg["agent"]
        # The prompt budget: a profile's own keys win over [agent] (small-context models need smaller prompts).
        self.history_lines = int(self.backend_cfg.get("history_lines", agent.get("history_lines", 500)))
        self.card_texts = self.backend_cfg.get("card_texts", agent.get("card_texts", "full"))
        self.session_limit = int(self.backend_cfg.get("max_session_messages", agent["max_messages_per_session"]))
        self.fallback = fallback or agent.get("fallback", "bot")
        self._fallback_policies = {}
        self.room = room
        self._system_prompt = None
        # A coach's moves are the human's, so no jokes in coach mode.
        self.banter = Banter(enabled=cfg.get("chat") == "banter" and self.mode != "coach")
        self.history = []
        self.pending = []
        self.pending_ids = set()
        self.session = None
        self.session_turn = None
        self.session_seen = set()
        self.opened_turn = None  # the turn the last session was opened for
        self.rolled_over = False  # the current session replaces one of the same turn
        self.turn = 0
        self.retry = False
        self.plan = []
        self.plan_hint = None
        self.say_queue = []
        self.last_decision = None
        self.feedback = 0
        self.stats = GameStats()
        self.turn_log = []     # this turn's decisions, replayed to a session that starts mid-turn
        self.turn_plan = None  # the last plan the backend gave this turn
        self.memory_turn = None
        self.started = False  # got this game's `start` event
        self.over = False     # got its `win` event
        self.chain_players = {}
        self.wiped = 0

    @property
    def log(self):
        # Created on first use, so a bot that never got into a duel leaves no empty log behind.
        if self._log is None:
            self._log = GameLog(paths.resolve(self.cfg.get("games_dir", "games")), self.profile.name,
                                deck_key=self.profile.key, game_id=self.game_id, seat=self.seat,
                                **self.log_options)
            self._log.web.on_feedback(self.panel_note)
            extra = {"deck_ydk": self.profile.ydk} if getattr(self.profile, "adhoc", False) else {}
            if self.opponent:
                extra["opponent_info"] = self.opponent
            self._log.write_meta(deck=self.profile.key, deck_name=self.profile.name, mode=self.mode,
                                 backend=self.backend_meta(), rules=self.rules_key,
                                 started=time.strftime("%Y-%m-%d %H:%M:%S"), **extra)
            if self.room:
                self._log.record("event", self.room)
            if self.runtime and self.runtime.windbot_log:
                self._log.link_windbot_log(self.runtime.windbot_log)
        return self._log

    @property
    def rules_key(self):
        """The room's real rules when the bot reported them, else the configured ones."""
        return rules_from_flags((self.room or {}).get("duel_flags")) or self.cfg["duel"]["rules"]

    def backend_meta(self):
        meta = {k: self.backend_cfg[k] for k in META_KEYS if self.backend_cfg.get(k) not in (None, "")}
        return {**meta, "label": self.label, "fallback": self.fallback}

    @property
    def system_prompt(self):
        if self._system_prompt is None:
            self._system_prompt = self.profile.system_prompt(self.mode, self.rules_key, self.card_texts,
                                                             self.opponent)
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
            self.new_turn_memory(ev["turn"])
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

    def panel_note(self, text, decision=None, turn=None):
        """A note typed in the web panel, saved like a `!note` from the duel chat. `decision`/`turn`: the decision
        the panel was showing, when the viewer had scrolled back to an earlier one."""
        self.feedback += 1
        context = f"turn {turn or self.turn}, right after decision #{decision or self.last_decision}"
        self.log.feedback(text, context, who="Web panel")
        return {"n": self.feedback, "context": context}

    # ---- sessions ----

    def new_turn_memory(self, turn):
        if turn != self.memory_turn:
            self.memory_turn, self.turn_log, self.turn_plan = turn, [], None

    def ensure_session(self, turn):
        s = self.session
        if s and (self.session_turn != turn or not s.alive or s.messages >= self.session_limit):
            s.close()
            self.session = None
        if self.session is None:
            self.new_turn_memory(turn)
            self.session = self.backend.open_session(self.system_prompt, SCHEMA)
            self.session_turn = turn
            self.session_seen = set(self.profile.ids)
            self.stats.sessions += 1
            # A rollover replaces a session of the same turn. The turn's first session is none, even when rules
            # already answered some of its decisions.
            self.rolled_over = self.opened_turn == turn
            self.opened_turn = turn
        return self.session

    def carry_over(self):
        """For a session that starts mid-turn: the plan and the decisions so far, so the backend keeps its line.
        A turn's first session gets the decisions the rules already made this turn, if any."""
        if not self.turn_log and not self.turn_plan:
            return None
        lines = []
        if self.rolled_over:
            lines.append("Your previous session for this turn ended (message limit, crash or timeout). Where you were:")
            if self.turn_plan:
                lines.append("Your plan for this turn: " + self.turn_plan)
        if self.turn_log:
            lines.append("Decisions already made this turn:\n" + "\n".join(self.turn_log[-30:]))
        return "\n".join(lines) or None

    def build_message(self, d, question, options_text, first):
        parts = []
        if first:
            history = self.history[-self.history_lines:] if self.history_lines > 0 else []
            parts.append("A new session started for this turn. Duel log so far:\n" + "\n".join(history))
            carry = self.carry_over()
            if carry:
                parts.append(carry)
            if self.rolled_over:
                self.stats.rollovers += 1
        elif self.pending:
            parts.append("What happened since your last decision:\n" + "\n".join(self.pending))
        self.pending = []
        ids = self.describer.ids_in_state(d["state"]) | self.describer.ids_in_decision(d) | self.pending_ids
        self.pending_ids = set()
        new = sorted(i for i in ids - self.session_seen if self.db.get(i))
        if new:
            self.session_seen |= set(new)
            playbook = self.profile.playbook if self.card_texts == "compact" else None
            parts.append("Card texts (not shown to you yet this turn):\n"
                         + "\n".join("- " + self.profile.card_text(i, self.card_texts, playbook) for i in new))
        parts.append("CURRENT STATE\n" + self.describer.state(d["state"]))
        opts = "\n".join(f"[{i}] {t}" for i, t in enumerate(options_text))
        parts.append(f"DECISION #{d['id']}: {question}" + (f"\n{opts}" if opts else ""))
        return "\n\n".join(parts)

    def ask_model(self, d, question, options_text):
        """(choice, why, plan, info): choice None when the backend gave no usable answer."""
        session = self.ensure_session(d["state"]["turn"])
        text = self.build_message(d, question, options_text, first=session.messages == 0)
        timeout = self.cfg["agent"]["decision_timeout_seconds"]
        info, error, seconds = {}, None, 0.0
        try:
            for _ in range(2):
                out, info = session.ask(Request(text, d, SCHEMA, timeout, error))
                seconds += info.get("seconds") or 0
                if out is not None:
                    try:
                        choice = [int(x) for x in out.get("choice", [])]
                    except (TypeError, ValueError):
                        choice = None
                    error = "choice must be a list of integers" if choice is None else self.validate(d, choice)
                    if error:
                        info["invalid"] = info.get("invalid", 0) + 1
                        info["error"] = f"invalid reply {out.get('choice')}: {error}"
                self.stats.ask(info)
                self.log.prompt(d["id"], text, out, info)
                if out is None:
                    if not session.alive:
                        self.session = None
                    return None, None, None, info
                if not error:
                    if out.get("plan"):
                        self.turn_plan = out["plan"]
                    return choice, out.get("why", ""), out.get("plan"), info
                text = f"That reply is invalid: {error}. Answer DECISION #{d['id']} again with a valid choice."
            return None, None, None, info
        finally:
            self.stats.latencies.append(round(seconds, 2))

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

        if self.retry:
            self.retry = False
            # The engine refused the last answer: don't repeat that policy; a random legal answer gets unstuck.
            choice = self.fallback_choice(d, "random")
            self.decided(d, question, options_text, choice or [], None, None, "fallback",
                         note="the engine rejected the previous answer, so "
                              f"{self.fallback_label('random')} answers this prompt")
            return self.reply(d, choice, "fallback")

        if kind == "select_unselect" and self.plan:
            k = self.next_planned(d)
            if k is not None:
                self.decided(d, question, options_text, [k], "continuing the selection planned above", None, "auto")
                return self.reply(d, [k], "auto")
            if d.get("finishable") or d.get("cancelable"):
                self.decided(d, question, options_text, [], "planned selection complete", None, "auto")
                return self.reply(d, [], "auto")

        decided, source = self.rules.decide(Context(d, self.db, self.describer, self.profile))
        if decided is not None:
            choice = decided.choice
            if choice is None and self.fallback != "bot":
                # A built-in rule leaving the prompt to the default (zone placement, a huge card-name list) is still
                # "auto", as with WindBot; a deck rule that gives up is a fallback.
                choice = self.fallback_choice(d)
                source = "auto" if source == "auto" else "fallback"
            if kind != "place":
                if source.startswith("rule"):
                    choice = self.conclude(d, question, options_text, choice, decided.why, None, source)
                else:
                    self.decided(d, question, options_text, choice or [], decided.why, None, source)
            return self.finish(d, choice, source)

        choice, why, plan, info = self.ask_model(d, question, options_text)
        seconds = self.stats.latencies[-1] if self.stats.latencies else None
        if choice is None:
            note = f"{self.label} gave no usable answer ({info.get('error') or 'unknown error'})"
            fallback = self.fallback_choice(d)
            if fallback is not None:
                note += f"; {self.fallback_label()} answered"
            choice = self.conclude(d, question, options_text, fallback, None, None, "fallback", seconds, note=note)
            return self.finish(d, choice, "fallback")
        choice = self.conclude(d, question, options_text, choice, why, plan, "backend", seconds,
                               note=info.get("error"))
        return self.finish(d, choice, "backend")

    def fallback_choice(self, d, policy="heuristic"):
        """What the fallback answers: None (WindBot's own AI) with fallback = "bot", else a policy's legal choice."""
        if self.fallback == "bot":
            return None
        if policy not in self._fallback_policies:
            self._fallback_policies[policy] = backends.create({"name": policy, "type": policy}, db=self.db).policy
        return self._fallback_policies[policy].choose(d)

    def fallback_label(self, policy="heuristic"):
        return "the built-in AI" if self.fallback == "bot" else f"the {policy} policy"

    def decided(self, d, question, options_text, chosen, why, plan, source, seconds=None, note=None, **kw):
        """Log a decision (terminal + game.md) and remember it for this turn's carry-over."""
        self.log.decision(d["id"], question, options_text, chosen, why, plan, source, seconds, note,
                          label=self.label, fallback=self.fallback_label(), key=self.key_play(d, chosen),
                          turn=(d.get("state") or {}).get("turn"), **kw)
        self.turn_log.append(f"- #{d['id']} {self.short_question(d, question)}: {self.picked(options_text, chosen)} "
                             f"[{self.tag(source)}]" + (f" — {why}" if why else ""))

    @staticmethod
    def picked(options_text, chosen):
        """The chosen options in words ("pass / none" when nothing was picked)."""
        text = ", ".join(options_text[k] for k in chosen if 0 <= k < len(options_text)) if options_text else (
            {(1,): "yes", (0,): "no"}.get(tuple(chosen), str(chosen)))
        return text or "pass / none"

    @staticmethod
    def key_play(d, chosen):
        """A play worth a line in the compact terminal view: an action taken in the Main or Battle Phase or a
        chain (not a phase change or a pass), or a yes to an optional effect."""
        if d["kind"] == "effect_yn":
            return chosen == [1]
        if d["kind"] not in ("idle", "battle", "chain") or not chosen:
            return False
        options = d.get("options", [])
        return any(0 <= k < len(options) and options[k].get("a") in KEY_ACTIONS for k in chosen)

    def short_question(self, d, question):
        if d["kind"] in ("select_card", "tribute", "select_unselect", "select_sum"):
            return self.describer.hint(d)
        return question.split(":")[0].split(". ")[0][:80]

    def tag(self, source):
        return {"backend": self.label, "fallback": "fallback"}.get(source, source)

    def conclude(self, d, question, options_text, choice, why, plan, source, seconds=None, note=None):
        """Log the decision and return the choice to send."""
        self.decided(d, question, options_text, choice or [], why, plan, source, seconds, note)
        return choice

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
        if source != "game_over":
            self.stats.decision(source or "fallback")
        if say:
            record["say"] = say
        self.log.record("reply", record)
        return {"id": d["id"], "choice": choice, "say": say}

    def summary(self):
        self.log.write_meta(stats=self.stats.summary())
        echo = self.log.echo
        if echo in ("key", "off") or self.log.quiet:
            return  # the match prints the result
        lines = [paint(BOLD, "\n  " + self.stats.line(self.label)),
                 paint(BOLD + ";" + YELLOW, f"  Game log: {self.log.dir}/game.md")]
        if echo == "all" and not self.log.tag:
            lines.append(paint(YELLOW, "  Give your feedback to your coding agent (e.g. Claude Code) in this repo's "
                                       "folder to update the playbook/rules.\n"))
        self.log.say(*lines)

    def close(self):
        if self.session:
            self.session.close()
            self.session = None
        if self._log:
            if not self.over:
                self._log.write_meta(stats=self.stats.summary())  # a game cut short still records its numbers
            self._log.close()
