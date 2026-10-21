"""Display text for bus messages, in the words describe.py uses, so the panel reads like game.md and like the prompt
the model saw. The bus runs every live message through a Renderer; the recorded-game loader uses one too."""

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
    def __init__(self, db):
        self.db = db
        self.describer = Describer(db)
        self._seen = {}  # game_id -> card ids whose brief was already sent with that game

    def __call__(self, msg):
        kind = msg.get("type")
        ids = set()
        if kind == "event":
            ev = msg.get("ev") or {}
            if "text" not in msg:
                msg["text"] = self.event_text(ev)
            ids = event_ids(ev)
            if ev.get("e") == "chaining" and "desc_text" not in msg:
                msg["desc_text"] = self.db.desc(ev.get("desc"))
        elif kind == "decision":
            d = msg.get("decision") or {}
            if "question" not in msg:
                msg["question"] = self.describer.question(d)
                msg["options"] = self.describer.options(d)
            if d.get("kind") in ("select_card", "tribute", "select_unselect", "select_sum"):
                msg.setdefault("hint_text", self.describer.hint(d))
            state = d.get("state") or {}
            if state.get("me"):
                ids = self.describer.ids_in_state(state)
                for link in state.get("chain") or []:
                    link.setdefault("desc_text", self.db.desc(link.get("desc")))
            ids |= {i for i in self.describer.ids_in_decision(d) if self.db.get(i)}
        elif kind == "game_end" and "reason_text" not in msg:
            msg["reason_text"] = self.db.victory.get(msg.get("reason"), "")
        if ids:
            seen = self._seen.setdefault(msg.get("game_id"), set())
            new = sorted(i for i in ids if i and i not in seen)
            if new:
                seen.update(new)
                msg["cards"] = {str(i): card_brief(self.db, i) for i in new}
        return msg

    def event_text(self, ev):
        if ev.get("e") == "chat":
            return chat_line(ev)
        try:
            return self.describer.event(ev)
        except (KeyError, TypeError, ValueError):
            return None
