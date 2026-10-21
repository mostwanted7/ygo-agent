"""The coach's side of one game: a DuelBrain that advises instead of playing.

It keeps the duel history, the backend sessions (one per turn) and the deck's rules exactly as a playing seat does,
but it never answers the engine: the human does, and their moves go back into its history so the next advice starts
from what they actually played. live.py drives it from the arena (asynchronously, so it never holds up the duel).
"""

from ..agent import prompts
from ..agent.brain import DuelBrain, chat_source
from ..agent.rules import Context

# Prompts the coach never weighs in on: zone placement, card/chain ordering, counters (the human's client handles
# those), plus whatever only has one way to answer.
TRIVIAL = ("place", "sort_card", "sort_chain", "select_counter", "go_first")
ONE_ANSWER = ("idle", "battle", "option", "position", "announce_number", "announce_attrib", "announce_race",
              "announce_card")


class CoachBrain(DuelBrain):
    """`level`: "beginner" (explain the idea behind each move) or "intermediate" (terse)."""

    def __init__(self, cfg, db, profile, *, level="beginner", **kw):
        kw.setdefault("prewarm", False)  # live.py opens sessions itself, only while no ask is running
        kw.setdefault("fallback", "heuristic")
        super().__init__(cfg, db, profile, mode="coach", **kw)
        self.level = level

    @property
    def system_prompt(self):
        if self._system_prompt is None:
            self._system_prompt = prompts.system_prompt(self.profile, "coach", self.rules_key, self.card_texts,
                                                        self.opponent, level=self.level)
        return self._system_prompt

    # ---- decisions ----

    def begin(self, d):
        """A decision the human faces: logged (the panel shows it at once) and put into words."""
        self.log.record("decide", d)
        if d.get("state", {}).get("me"):
            self.fill_extra(d["state"])
        self.last_decision = d["id"]
        if d["kind"] != "select_unselect" or d.get("hint") != self.plan_hint:
            self.plan = []  # a planned multi-pick only continues within the same selection
        return self.describer.question(d), self.describer.options(d)

    def auto_advice(self, d):
        """(choice, why, source) for a decision the backend isn't asked about: a trivial one (choice None: no advice),
        the next card of a selection the coach planned, or one the deck's rules answer. None: ask the backend."""
        kind, options = d["kind"], d.get("options", [])
        if kind in TRIVIAL:
            return None, "nothing to advise", "auto"
        if kind in ONE_ANSWER and len(options) <= 1:
            return None, "only one choice", "auto"
        if kind == "chain" and d.get("forced") and len(options) == 1:
            return None, "a mandatory activation", "auto"
        if kind in ("select_card", "tribute") and d.get("min") == d.get("max") == len(options):
            return None, "every card has to be picked", "auto"
        if kind == "select_unselect" and self.plan:
            k = self.next_planned(d)
            if k is not None:
                return [k], "the next card of the selection advised above", "auto"
            if d.get("finishable"):
                return [], "the selection advised above is complete", "auto"
        decided, source = self.rules.decide(Context(d, self.db, self.describer, self.profile))
        if decided is None:
            return None
        if source == "auto":
            return None, decided.why, "auto"
        if decided.choice is None:
            return None  # a deck rule that leaves it open: the backend advises
        return decided.choice, decided.why, source

    def check(self, d, out):
        """(choice, error) for a backend reply: error is None when the choice is legal for this decision."""
        try:
            choice = [int(x) for x in out.get("choice", [])]
        except (TypeError, ValueError):
            return None, "choice must be a list of integers"
        return choice, self.validate(d, choice)

    def hindsight_message(self, d, question, options_text, human, first):
        """The prompt for a decision the human answered before the coach got to it: its own state (it's in the past),
        what they chose, and the usual reply asked for, briefly."""
        parts = []
        if first:
            history = self.history[-self.history_lines:] if self.history_lines > 0 else []
            parts.append("A new session started for this turn. Duel log so far:\n" + "\n".join(history))
            carry = self.carry_over()
            if carry:
                parts.append(carry)
        ids = (self.describer.ids_in_state(d["state"]) | self.describer.ids_in_decision(d)) - self.session_seen
        new = sorted(i for i in ids if self.db.get(i))
        if new:
            self.session_seen |= set(new)
            playbook = self.profile.playbook if self.card_texts == "compact" else None
            parts.append("Card texts (not shown to you yet this turn):\n"
                         + "\n".join("- " + self.profile.card_text(i, self.card_texts, playbook) for i in new))
        opts = "\n".join(f"[{i}] {t}" for i, t in enumerate(options_text))
        parts.append(f"LOOKING BACK: the human answered decision #{d['id']} before your advice was ready; they chose "
                     f"{self.picked(options_text, human or [])}. What would you have recommended there? Reply as "
                     "usual, with a one-sentence why (it goes into the review after the game).")
        parts.append("STATE AT THAT DECISION\n" + self.describer.state(d["state"]))
        parts.append(f"DECISION #{d['id']}: {question}" + (f"\n{opts}" if opts else ""))
        return "\n\n".join(parts)

    def human_moved(self, d, question, options_text, choice, advised=None, source=None):
        """The human's move goes into the duel history (and this turn's carry-over), so the coach's next advice
        knows what was actually played, and whether it was what it advised."""
        picked = self.picked(options_text, choice or [])
        line = f"The human chose at #{d['id']} ({self.short_question(d, question)}): {picked}"
        if advised is not None and source not in ("auto",) and list(advised) != list(choice or []):
            line += f" (you had advised: {self.picked(options_text, advised)})"
        self.history.append(line)
        self.pending.append(line)
        self.turn_log.append("- " + line)

    # ---- chat and notes ----

    def note(self, text, who, turn=None, decision=None, ack=True):
        """A note for whoever improves the coach and the playbook: feedback.md, tagged as a coach game."""
        self.feedback += 1
        after = decision or self.last_decision
        context = f"coach game, turn {turn or self.turn}, " + (f"right after decision #{after}" if after else
                                                                  "before the first decision")
        self.log.feedback(text, context, who=who)
        if ack:
            self.say_queue.append(f"Noted feedback #{self.feedback}.")
        return {"n": self.feedback, "context": context}

    def panel_note(self, text, decision=None, turn=None):
        return self.note(text, "Web panel", turn, decision, ack=False)

    def on_chat(self, ev):
        msg = ev.get("message", "").strip()
        source = chat_source(ev)
        if not msg or source == "system":
            return
        own = source == "duelist" and ev.get("player") == ev.get("position")
        if msg.startswith("!"):
            self.note(msg[1:].strip(), "Player" if own else ("Spectator" if source == "spectator" else "Opponent"))
        elif not own:
            line = f'{"A spectator" if source == "spectator" else "The opponent"} says in chat: "{msg}"'
            self.history.append(line)
            self.pending.append(line)
            self.log.event(line)

    def summary(self):
        self.log.write_meta(stats=self.stats.summary())  # live.py prints the coach's own summary
