"""Display text for bus messages, in the words describe.py uses, so the panel reads like game.md and like the prompt
the model saw. The bus runs every live message through a Renderer; the recorded-game loader uses one too."""

import collections
import threading

from ..agent.brain import chat_source, event_ids
from ..agent.describe import Describer


def card_brief(db, cid):
    """What the board needs to draw a card it only knows the code of (full text: /cardinfo/<code>)."""
    card = db.get(cid)
    if not card:
        return {"n": db.name(cid), "t": 0}
    return {"n": card.name, "t": card.type, "atk": card.atk, "def": card.defense, "lv": card.level & 0xFF}


def chat_line(ev):
    """A chat event the way the agent's duel log words it (None for echoes, system lines and !notes)."""
    msg = (ev.get("message") or "").strip()
    source = chat_source(ev)
    if not msg or msg.startswith("!") or source == "system" or (source == "duelist"
                                                                and ev.get("player") == ev.get("position")):
        return None
    who = "A spectator" if source == "spectator" else "Opponent"
    return f'{who} says in chat: "{msg}"'


class Renderer:
    """Seats publish from their own threads, and a Describer keeps state between events (a Summon in its negation
    window, an open chain), so each (game, seat) gets its own, and the card briefs are tracked per game."""

    MAX_GAMES = 32  # the state of older games is forgotten (a looping demo makes a new game id each time)

    def __init__(self, db):
        self.db = db
        self._lock = threading.Lock()
        self._describers = collections.OrderedDict()  # (game_id, seat) -> Describer
        self._seen = collections.OrderedDict()        # game_id -> card ids whose brief was already sent

    def describer(self, msg):
        key = (msg.get("game_id"), msg.get("seat", 0))
        with self._lock:
            if key not in self._describers:
                if len(self._describers) >= 2 * self.MAX_GAMES:
                    self._describers.popitem(last=False)
                self._describers[key] = Describer(self.db)
            return self._describers[key]

    def __call__(self, msg):
        kind = msg.get("type")
        words = self.describer(msg)
        ids = set()
        if kind == "event":
            ev = msg.get("ev") or {}
            if "text" not in msg:
                msg["text"] = self.event_text(words, ev)
            ids = event_ids(ev)
            if ev.get("e") == "chaining" and "desc_text" not in msg:
                msg["desc_text"] = self.db.desc(ev.get("desc"))
        elif kind == "decision":
            d = msg.get("decision") or {}
            if "question" not in msg:
                msg["question"] = words.question(d)
                msg["options"] = words.options(d)
            if d.get("kind") in ("select_card", "tribute", "select_unselect", "select_sum"):
                msg.setdefault("hint_text", words.hint(d))
            state = d.get("state") or {}
            if state.get("me"):
                ids = words.ids_in_state(state)
                for link in state.get("chain") or []:
                    link.setdefault("desc_text", self.db.desc(link.get("desc")))
            ids |= {i for i in words.ids_in_decision(d) if self.db.get(i)}
        elif kind == "spectator_state":
            ids = words.ids_in_state(msg.get("state") or {})
        elif kind == "game_end" and "reason_text" not in msg:
            msg["reason_text"] = self.db.victory.get(msg.get("reason"), "")
        if ids:
            with self._lock:
                if msg.get("game_id") not in self._seen and len(self._seen) >= self.MAX_GAMES:
                    self._seen.popitem(last=False)
                seen = self._seen.setdefault(msg.get("game_id"), set())
                new = sorted(i for i in ids if i and i not in seen)
                seen.update(new)
            if new:
                msg["cards"] = {str(i): card_brief(self.db, i) for i in new}
        return msg

    def event_text(self, words, ev):
        if ev.get("e") == "chat":
            return chat_line(ev)
        try:
            return words.event(ev)
        except (KeyError, TypeError, ValueError):
            return None
