"""One seat's picture of the duel in the decision-protocol schema (docs/decision-protocol.md).

The WindBot fork rebuilds the duel from its network stream (GameBehavior.cs) and serializes it (BrainBridge.cs).
`NativeView` does the same for an in-process seat, from exactly the two fair sources a seat has:

  * its team's filtered message stream (`on_message`, fed by SeatFeed: what that player's EDOPro client receives),
    which becomes the bridge's events and keeps the card instances, the chain, the targets, the last summon and
    the battling monsters up to date;
  * its SeatView queries at decision time (`state()`), for the exact current stats.

Card instances. Every card the seat can follow is a `Card` that moves between piles and zones with each
MSG_MOVE/DRAW/SWAP, mirroring the core's arrays (piles are lists in core order, deck top last; zones are slots;
Xyz materials hang off their monster). Its `uid` is a per-game counter, so it stays the same while the seat can
follow the card, and a hidden reorder (a Deck shuffle, the opponent's hand or Extra Deck shuffle, a Set-card
shuffle) gives the cards new uids, because the seat can't tell them apart any more. A card's code is what the
stream told the seat, kept the way WindBot keeps it (a move with a hidden code forgets it, a hidden shuffle forgets
it, a confirmation teaches it), and the SeatView query wins whenever it shows the code.
"""

from __future__ import annotations

import itertools

from ..core.constants import (LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE,
                              LOCATION_OVERLAY, LOCATION_REMOVED, LOCATION_SZONE, POS_FACEUP, STATUS_DISABLED,
                              TYPE_LINK, TYPE_PENDULUM, TYPE_XYZ, HINT_SELECTMSG)
from . import messages as M
from .buffer import LocInfo

PILES = (LOCATION_DECK, LOCATION_HAND, LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_EXTRA)
ZONES = {LOCATION_MZONE: 7, LOCATION_SZONE: 8}
STATE_PILES = (("hand", LOCATION_HAND), ("gy", LOCATION_GRAVE), ("ban", LOCATION_REMOVED), ("extra", LOCATION_EXTRA))
HIDDEN_S = (LOCATION_HAND, LOCATION_DECK, LOCATION_EXTRA)  # sequences the bridge reports as -1 outside `state`
# HINT types that tell the other players what someone declared (EDOPro routes them to everyone but that player).
DECLARED = {4: "option", 6: "race", 7: "attribute", 8: "card", 9: "number"}


class Card:
    """One card instance as the seat follows it."""
    __slots__ = ("uid", "code", "pos", "materials", "q", "attacked")

    def __init__(self, uid: int, code: int = 0, pos: int = 0):
        self.uid, self.code, self.pos = uid, code, pos
        self.materials: list[Card] = []
        self.q = None            # the last CardQuery the seat got for it (stats, status, counters, ...)
        self.attacked = False    # declared an attack this turn

    def __repr__(self) -> str:
        return f"<Card {self.uid} {self.code}>"


def empty_state() -> dict:
    side = {"lp": 0, "hand": [], "mz": [], "sz": [], "gy": [], "ban": [], "deck": 0, "extra": []}
    return {"turn": 0, "turn_player": 0, "phase": 0, "me": dict(side), "opp": dict(side), "chain": [],
            "chain_targets": [], "last_summoned": [], "summon_player": -1, "battling": [None, None]}


class NativeView:
    def __init__(self, team: int, cards=None):
        """`team`: the core team this seat plays (0 moves first). `cards`: the arena CardDatabase (printed stats
        for cards the seat has no query for, e.g. Deck cards offered by a search)."""
        self.team = team
        self.cards = cards
        self.view = None   # SeatView of the current game
        self.reset()

    # --- lifecycle --------------------------------------------------------------------------------------------
    def reset(self) -> None:
        self._uids = itertools.count(1)
        self.piles = {(p, loc): [] for p in (0, 1) for loc in PILES}
        self.zones = {(p, loc): [None] * n for p in (0, 1) for loc, n in ZONES.items()}
        self.started = False
        self.first = self.team == 0
        self.turn = 0
        self.turn_player = 0
        self.phase = 0
        self.lp = [0, 0]
        self.hint = 0                      # the last HINT_SELECTMSG for this seat (WindBot's _select_hint)
        self.chain: list[tuple[Card | None, int, int, int]] = []  # (card, local player, desc, code at activation)
        self.chain_targets: list[Card] = []
        self.summoning: list[Card] = []
        self.last_summoned: list[Card] = []
        self.summon_player = -1
        self.battling: list[Card | None] = [None, None]  # [mine, theirs], local
        self.resyncs = 0                   # piles/zones rebuilt from a query because the tracking drifted
        self.misses = 0                    # moves of a card the tracking didn't have

    def bind(self, view) -> None:
        self.view = view
        self.team = view.team

    def local(self, player: int) -> int:
        return 0 if player == self.team else 1

    def _new(self, code: int = 0, pos: int = 0) -> Card:
        return Card(next(self._uids), code, pos)

    # --- positions ----------------------------------------------------------------------------------------------
    def _slots(self, player: int, location: int) -> list | None:
        if location in ZONES:
            return self.zones.get((player, location))
        return self.piles.get((player, location))

    def at(self, player: int, location: int, sequence: int, position: int = 0) -> Card | None:
        if location & LOCATION_OVERLAY:
            host = self.at(player, location & 0x7F, sequence)
            if host is None or not 0 <= position < len(host.materials):
                return None
            return host.materials[position]
        slots = self._slots(player, location)
        if slots is None or not 0 <= sequence < len(slots):
            return None
        return slots[sequence]

    def _take(self, li: LocInfo) -> Card | None:
        if li.location & LOCATION_OVERLAY:
            host = self.at(li.controller, li.location & 0x7F, li.sequence)
            if host is not None and 0 <= li.position < len(host.materials):
                return host.materials.pop(li.position)
            return None
        slots = self._slots(li.controller, li.location)
        if slots is None or not 0 <= li.sequence < len(slots):
            return None
        if li.location in ZONES:
            card, slots[li.sequence] = slots[li.sequence], None
            return card
        return slots.pop(li.sequence)

    def _put(self, card: Card, li: LocInfo) -> None:
        if li.location & LOCATION_OVERLAY:
            host = self.at(li.controller, li.location & 0x7F, li.sequence)
            if host is not None:
                host.materials.insert(min(li.position, len(host.materials)), card)
            return
        slots = self._slots(li.controller, li.location)
        if slots is None:
            return
        if li.location in ZONES:
            if 0 <= li.sequence < len(slots):
                slots[li.sequence] = card
            return
        slots.insert(min(max(li.sequence, 0), len(slots)), card)

    def locate(self, card: Card | None) -> tuple[int, int, int, int] | None:
        """(player, location, sequence, position) of a tracked card right now, or None once it left the game."""
        if card is None:
            return None
        for (p, loc), slots in self.zones.items():
            for seq, c in enumerate(slots):
                if c is card:
                    return p, loc, seq, c.pos
                if c is not None:
                    for k, m in enumerate(c.materials):
                        if m is card:
                            return p, loc | LOCATION_OVERLAY, seq, k
        for (p, loc), slots in self.piles.items():
            for seq, c in enumerate(slots):
                if c is card:
                    return p, loc, seq, c.pos
        return None

    # --- card dicts -----------------------------------------------------------------------------------------------
    def card_dict(self, card: Card | None, player: int, location: int, sequence: int, position: int | None = None,
                  *, ref: bool = True, code: int | None = None) -> dict:
        """The bridge's full card object. `ref`: a card referenced outside the state's piles (options, events, the
        chain), where hand, Deck and Extra Deck sequences are reported as -1, as the bridge does."""
        code = code if code is not None else (card.code if card else 0)
        q = card.q if card else None
        pos = position if position is not None else (card.pos if card else 0)
        if location & LOCATION_OVERLAY:
            d = {"id": code, "c": self.local(player), "l": LOCATION_OVERLAY, "s": -1, "p": pos}
        else:
            s = -1 if ref and location in HIDDEN_S else sequence
            d = {"id": code, "c": self.local(player), "l": location, "s": s, "p": pos}
        if code:
            self._stats(d, code, q, card, player)
        if card is not None:
            d["uid"] = card.uid
        return d

    def _stats(self, d: dict, code: int, q, card: Card | None, player: int) -> None:
        data = self.cards.get(code) if self.cards else None
        printed_lv = data.level if data else 0
        if q is not None and q.attack is not None:
            atk, df, lv, rk, lk = q.attack, q.defense or 0, q.level or 0, q.rank or 0, q.link or 0
        elif data:
            xyz, link = data.type & TYPE_XYZ, data.type & TYPE_LINK
            atk, df = data.attack, data.defense
            lv, rk, lk = (0 if xyz or link else printed_lv), (printed_lv if xyz else 0), (printed_lv if link else 0)
        else:
            atk = df = lv = rk = lk = 0
        d.update(atk=atk, **{"def": df}, lv=lv, rk=rk, lk=lk)
        if q is not None and q.overlay_cards:
            d["ov"] = list(q.overlay_cards)
        elif card is not None and card.materials and any(m.code for m in card.materials):
            d["ov"] = [m.code for m in card.materials]
        if q is not None and q.status is not None and q.status & STATUS_DISABLED:
            d["dis"] = True
        if card is not None and card.attacked:
            d["att"] = True
        if q is not None and q.equip_card is not None:
            target = self.at(q.equip_card.controller, q.equip_card.location, q.equip_card.sequence)
            d["eq"] = self.short(target, q.equip_card.controller, q.equip_card.location, q.equip_card.sequence)
        if q is None:
            return
        # Stage 3 additions (optional fields, see docs/decision-protocol.md).
        if q.counters:
            d["ctr"] = [[t, n] for t, n in sorted(q.counters.items()) if n]
            if not d["ctr"]:
                del d["ctr"]
        if data and data.type & TYPE_PENDULUM and q.lscale is not None and d["l"] == LOCATION_SZONE:
            d["sc"] = [q.lscale, q.rscale]
        if data and data.type & 1 and d["l"] == LOCATION_MZONE:
            if data.type & TYPE_XYZ:
                if rk and rk != printed_lv:
                    d["blv"] = printed_lv
            elif not data.type & TYPE_LINK and lv and lv != printed_lv:
                d["blv"] = printed_lv
        if q.owner is not None and q.owner != player:
            d["own"] = self.local(q.owner)

    def short(self, card: Card | None, player: int, location: int, sequence: int) -> dict:
        """The bridge's short card object ({id, c, l, s})."""
        code = card.code if card else 0
        if location & LOCATION_OVERLAY:
            return {"id": code, "c": self.local(player), "l": LOCATION_OVERLAY, "s": -1}
        return {"id": code, "c": self.local(player), "l": location, "s": -1 if location in HIDDEN_S else sequence}

    def ref(self, card: Card | None, short: bool = False) -> dict | None:
        """A tracked card wherever it is now (None when it's gone)."""
        where = self.locate(card)
        if where is None:
            return None
        p, loc, seq, pos = where
        return self.short(card, p, loc, seq) if short else self.card_dict(card, p, loc, seq, pos)

    def loc_dict(self, li: LocInfo) -> dict:
        return {"c": self.local(li.controller), "l": li.location, "s": li.sequence, "p": li.position}

    # --- the message stream → events --------------------------------------------------------------------------
    def on_message(self, msg: M.Message) -> list[dict]:
        """Update the picture from one message of the seat's stream; returns the bridge events it produces."""
        handler = _HANDLERS.get(type(msg))
        if handler is None:
            return []
        return handler(self, msg) or []

    def _start(self, m: M.Start) -> list[dict]:
        self.reset()
        self.started = True
        self.first = (m.player_type & 0xF) == 0
        for p in (0, 1):
            self.piles[(p, LOCATION_DECK)] = [self._new() for _ in range(m.deck[p])]
            self.piles[(p, LOCATION_EXTRA)] = [self._new() for _ in range(m.extra[p])]
        self.lp = list(m.lp)
        names = self.view.names if self.view is not None else ("", "")
        me = self.team
        return [{"e": "start", "first": self.first, "lp": [self.lp[me], self.lp[1 - me]],
                 "names": [names[me], names[1 - me]]}]

    def _draw(self, m: M.Draw) -> list[dict]:
        deck, hand = self.piles[(m.player, LOCATION_DECK)], self.piles[(m.player, LOCATION_HAND)]
        for code, pos in m.cards:
            card = deck.pop() if deck else self._new()
            card.code, card.pos, card.q = code, pos, None
            hand.append(card)
        return [{"e": "draw", "player": self.local(m.player), "count": len(m.cards)}]

    def _move(self, m: M.Move) -> list[dict]:
        ev = {"e": "move", "id": m.code, "from": self.loc_dict(m.previous), "to": self.loc_dict(m.current),
              "reason": m.reason}
        prev, cur = m.previous, m.current
        card = self._take(prev) if prev.location else None
        if card is None:
            if prev.location:
                self.misses += 1
            card = self._new()
        card.code = m.code
        card.pos = cur.position if not cur.location & LOCATION_OVERLAY else 0
        if prev.location != cur.location or prev.controller != cur.controller:
            card.q = None
            if not cur.location & LOCATION_MZONE:
                card.attacked = False
        if cur.location & LOCATION_OVERLAY:
            # A card that becomes material is a new object in WindBot; its own materials (if any) go with it here.
            card.materials = []
        if cur.location:
            self._put(card, cur)
        return [ev]

    def _swap(self, m: M.Swap) -> list[dict]:
        a, b = self._take(m.location1), self._take(m.location2)
        cards = []
        for card, code, li in ((a, m.code1, m.location2), (b, m.code2, m.location1)):
            card = card or self._new()
            card.code, card.q = code, None
            card.pos = li.position if li.position else card.pos
            self._put(card, LocInfo(li.controller, li.location, li.sequence, card.pos))
            cards.append(self.card_dict(card, li.controller, li.location, li.sequence))
        return [{"e": "swap", "cards": cards}]

    def _pos_change(self, m: M.PosChange) -> list[dict]:
        card = self.at(m.controller, m.location, m.sequence)
        if card is not None:
            card.pos = m.current_position
            if m.code:
                card.code = m.code
        return [{"e": "pos_change", "id": m.code, "c": self.local(m.controller), "l": m.location, "s": m.sequence,
                 "from": m.previous_position, "to": m.current_position}]

    def _shuffle_deck(self, m: M.ShuffleDeck) -> None:
        self.piles[(m.player, LOCATION_DECK)] = [self._new() for _ in self.piles[(m.player, LOCATION_DECK)]]

    def _reshuffle(self, cards: list[Card], codes: list[int]) -> list[Card]:
        """Cards of a pile in a new order: the seat follows each card it can see (by code), hidden ones get new uids."""
        pool = list(cards)
        out = []
        for code in codes:
            match = next((c for c in pool if code and c.code == code), None)
            if match is not None:
                pool.remove(match)
            else:
                match = self._new(code)
            match.code = code
            out.append(match)
        return out

    def _shuffle_hand(self, m: M.ShuffleHand) -> None:
        key = (m.player, LOCATION_HAND)
        hand = self.piles[key]
        if len(m.codes) != len(hand):
            self.resyncs += 1
        new = self._reshuffle(hand, m.codes)
        for old, card in zip(hand, new):
            card.pos = old.pos
        self.piles[key] = new

    def _shuffle_extra(self, m: M.ShuffleExtra) -> None:
        key = (m.player, LOCATION_EXTRA)
        extra = self.piles[key]
        down = [c for c in extra if not c.pos & POS_FACEUP]
        new = iter(self._reshuffle(down, m.codes[:len(down)]))
        self.piles[key] = [c if c.pos & POS_FACEUP else next(new, c) for c in extra]

    def _shuffle_set(self, m: M.ShuffleSetCard) -> None:
        moved = [self.at(li.controller, li.location, li.sequence) for li in m.previous]
        for card in moved:
            if card is not None:
                card.code, card.q = 0, None
        for li, card in zip(m.current, moved):
            if card is None or not li.location:
                continue
            fresh = self._new(0, card.pos)
            fresh.materials = card.materials
            self.zones[(li.controller, li.location)][li.sequence] = fresh

    def _swap_grave_deck(self, m: M.SwapGraveDeck) -> None:
        p = m.player
        grave, deck = self.piles[(p, LOCATION_GRAVE)], self.piles[(p, LOCATION_DECK)]
        bits = int.from_bytes(m.extra_mask, "little")
        to_extra = [c for i, c in enumerate(grave) if bits >> i & 1]
        to_deck = [c for i, c in enumerate(grave) if not bits >> i & 1]
        for c in grave:
            c.code, c.q = 0, None
        self.piles[(p, LOCATION_GRAVE)] = deck
        self.piles[(p, LOCATION_DECK)] = to_deck
        self.piles[(p, LOCATION_EXTRA)] += to_extra

    def _reverse_deck(self, m: M.ReverseDeck) -> None:
        for p in (0, 1):
            self.piles[(p, LOCATION_DECK)].reverse()

    def _deck_top(self, m: M.DeckTop) -> None:
        deck = self.piles[(m.player, LOCATION_DECK)]
        if 0 <= m.sequence < len(deck):
            deck[len(deck) - 1 - m.sequence].code = m.code & 0x7FFFFFFF

    def _confirm(self, m: M._ConfirmBase) -> list[dict]:
        shown = []
        for ref in m.cards:
            card = self.at(ref.controller, ref.location, ref.sequence)
            if card is not None and ref.code:
                card.code = ref.code
            if ref.code:
                shown.append(self.card_dict(card, ref.controller, ref.location, ref.sequence, code=ref.code))
        if not shown:
            return []
        return [{"e": "confirm", "player": self.local(m.player), "cards": shown}]

    def _update_data(self, m: M.UpdateData) -> None:
        """The host's refreshes. They are queried when the host handles the message, which can be a few messages
        after the core's state moved on, so they only fill in what lines up; decision-time queries fix the rest."""
        slots = self._slots(m.player, m.location)
        if slots is None or len(slots) != len(m.cards):
            return
        for card, q in zip(slots, m.cards):
            if card is not None and q is not None:
                self._refresh(card, q)

    def _update_card(self, m: M.UpdateCard) -> None:
        card = self.at(m.player, m.location, m.sequence)
        if card is not None and m.card is not None:
            self._refresh(card, m.card)

    def _refresh(self, card: Card, q) -> None:
        if q.code and card.code and q.code != card.code:
            return  # not the card the seat has there (the refresh is from later): leave it to the next query
        if q.code:
            card.code = q.code
        if q.position is not None:
            card.pos = q.position
        card.q = q

    def _reload(self, m: M.ReloadField) -> None:
        """A custom start state (Debug.ReloadFieldEnd): rebuild every pile and zone from the public field info."""
        fs = m.state
        for p, pf in enumerate(fs.players):
            self.lp[p] = pf.lp
            for loc, row in ((LOCATION_MZONE, pf.mzone), (LOCATION_SZONE, pf.szone)):
                self.zones[(p, loc)] = [None if z is None else self._zone_card(z) for z in row]
            for loc, n in ((LOCATION_DECK, pf.deck), (LOCATION_HAND, pf.hand), (LOCATION_GRAVE, pf.grave),
                           (LOCATION_REMOVED, pf.removed), (LOCATION_EXTRA, pf.extra)):
                self.piles[(p, loc)] = [self._new() for _ in range(n)]

    def _zone_card(self, z) -> Card:
        card = self._new(0, z.position)
        card.materials = [self._new() for _ in range(z.overlay_count)]
        return card

    def _new_turn(self, m: M.NewTurn) -> list[dict]:
        self.turn += 1
        self.turn_player = m.player
        for slots in self.zones.values():
            for c in slots:
                if c is not None:
                    c.attacked = False
        return [{"e": "new_turn", "turn": self.turn, "player": self.local(m.player)}]

    def _new_phase(self, m: M.NewPhase) -> list[dict]:
        self.phase = m.phase
        self.summon_player = -1
        self.summoning, self.last_summoned = [], []
        self.battling = [None, None]
        self.hint = 0
        return [{"e": "new_phase", "phase": m.phase, "player": self.local(self.turn_player)}]

    def _lp_event(self, kind: str, player: int, amount: int) -> list[dict]:
        if kind == "recover":
            self.lp[player] += amount
        else:
            self.lp[player] = max(0, self.lp[player] - amount)
        return [{"e": kind, "player": self.local(player), "amount": amount, "lp": self.lp[player]}]

    def _lp_update(self, m: M.LpUpdate) -> list[dict]:
        self.lp[m.player] = m.amount
        return [{"e": "lp", "player": self.local(m.player), "lp": m.amount}]

    def _summoning(self, m, special: bool, flip: bool = False) -> list[dict]:
        """MSG_SUMMONING, SPSUMMONING and FLIPSUMMONING (WindBot treats a Flip Summon as a Normal Summon here)."""
        self.last_summoned = []
        card = self.at(m.location.controller, m.location.location, m.location.sequence)
        if card is not None:
            if m.code and not card.code:
                card.code = m.code
            self.summoning.append(card)
        self.summon_player = self.local(m.location.controller)
        ev = {"e": "summoning", "id": m.code, "to": self.loc_dict(m.location), "special": special}
        if flip:
            ev["flip"] = True
        return [ev]

    def _summoned(self, m) -> None:
        self.last_summoned += self.summoning
        self.summoning = []

    def _chaining(self, m: M.Chaining) -> list[dict]:
        li = m.location
        card = self.at(li.controller, li.location, li.sequence, li.position)
        if card is not None and not card.code:
            card.code = m.code
        self.summon_player = -1
        player = self.local(m.controller)
        self.chain.append((card, player, m.description, m.code or (card.code if card else 0)))
        return [{"e": "chaining", "id": m.code, "card": self.card_dict(card, li.controller, li.location, li.sequence,
                                                                          li.position, code=m.code or None),
                 "player": player, "desc": m.description, "link": len(self.chain)}]

    def _chain_end(self, m) -> list[dict]:
        self.chain, self.chain_targets, self.summoning = [], [], []
        return [{"e": "chain_end"}]

    def _targets(self, m: M.BecomeTarget) -> list[dict]:
        out = []
        for li in m.cards:
            card = self.at(li.controller, li.location, li.sequence)
            if card is None:
                continue
            out.append({"e": "targeted", "card": self.card_dict(card, li.controller, li.location, li.sequence)})
            self.chain_targets.append(card)
        return out

    def _attack(self, m: M.Attack) -> list[dict]:
        a = m.attacker
        attacker = self.at(a.controller, a.location, a.sequence)
        target = None if m.direct else self.at(m.target.controller, m.target.location, m.target.sequence)
        side = self.local(a.controller)
        self.battling[side], self.battling[1 - side] = attacker, target
        t = m.target
        ev = {"e": "attack", "attacker": self.card_dict(attacker, a.controller, a.location, a.sequence),
              "target": None if m.direct else self.card_dict(target, t.controller, t.location, t.sequence)}
        if attacker is not None:
            attacker.attacked = True
        return [ev]

    def _hint(self, m: M.Hint) -> list[dict]:
        if m.hint_type == HINT_SELECTMSG and m.player == self.team:
            self.hint = m.data
        elif m.hint_type in DECLARED and m.player != self.team:
            return [{"e": "declared", "player": self.local(m.player), "kind": DECLARED[m.hint_type],
                     "value": m.data}]
        return []

    def _equip(self, m: M.Equip) -> list[dict]:
        a, b = m.card, m.target
        card, target = self.at(a.controller, a.location, a.sequence), self.at(b.controller, b.location, b.sequence)
        return [{"e": "equip", "card": self.card_dict(card, a.controller, a.location, a.sequence),
                 "target": self.card_dict(target, b.controller, b.location, b.sequence)}]

    def _counter(self, m, add: bool) -> list[dict]:
        card = self.at(m.controller, m.location, m.sequence)
        return [{"e": "counter", "card": self.card_dict(card, m.controller, m.location, m.sequence),
                 "type": m.counter_type, "count": m.count, "add": add}]

    def _results(self, m, kind: str) -> list[dict]:
        return [{"e": kind, "player": self.local(m.player), "results": list(m.results)}]

    def _win(self, m: M.Win) -> list[dict]:
        result = 2 if m.player > 1 else self.local(m.player)
        return [{"e": "win", "result": result, "reason": m.reason}]

    # --- queries → state -----------------------------------------------------------------------------------------
    def _sync(self, player: int, location: int, queries: list) -> list:
        """Line the tracked cards of one location up with a query of it (stats and codes from the query; a length
        mismatch means the tracking drifted, so the location is rebuilt from the query)."""
        if location in ZONES:
            slots = self.zones[(player, location)]
            for seq in range(min(len(slots), len(queries))):
                q, card = queries[seq], slots[seq]
                if q is None:
                    if card is not None:
                        slots[seq] = None
                        self.resyncs += 1
                    continue
                if card is None:
                    card = slots[seq] = self._new()
                    self.resyncs += 1
                self._apply(card, q)
            return slots
        if location not in PILES:
            return []
        key = (player, location)
        cards = self.piles[key]
        if len(cards) != len(queries):
            self.resyncs += 1
            cards = self.piles[key] = [self._new() for _ in queries]
        for card, q in zip(cards, queries):
            if q is not None:
                self._apply(card, q)
        return cards

    def _apply(self, card: Card, q) -> None:
        if q.code:
            if card.code and card.code != q.code:
                card.uid = next(self._uids)  # it wasn't the card the seat thought it was
            card.code = q.code
        if q.position is not None:
            card.pos = q.position
        card.q = q

    def state(self) -> dict:
        """The bridge's `state` object, from SeatView queries made now (decision time)."""
        if not self.started or self.view is None:
            return empty_state()
        v = self.view
        fs = v.field()
        sides = {}
        for side, p in (("me", self.team), ("opp", 1 - self.team)):
            out = {"lp": fs.players[p].lp}
            for name, loc in STATE_PILES:
                cards = self._sync(p, loc, v.location(p, loc))
                out[name] = [self.card_dict(c, p, loc, i, ref=False) for i, c in enumerate(cards)]
            for name, loc in (("mz", LOCATION_MZONE), ("sz", LOCATION_SZONE)):
                slots = self._sync(p, loc, v.location(p, loc))
                out[name] = [None if c is None else self.card_dict(c, p, loc, i, ref=False)
                             for i, c in enumerate(slots)]
            deck = self.piles[(p, LOCATION_DECK)]
            n = v.count(p, LOCATION_DECK)
            if len(deck) != n:
                self.resyncs += 1
                self.piles[(p, LOCATION_DECK)] = [self._new() for _ in range(n)]
            out["deck"] = n
            out["mz"] = (out["mz"] + [None] * 7)[:7]
            out["sz"] = (out["sz"] + [None] * 8)[:8]
            sides[side] = out
        self.lp = [fs.players[0].lp, fs.players[1].lp]
        chain = []
        for card, player, desc, code in self.chain:
            chain.append({"card": self.ref(card), "id": code, "player": player, "desc": desc})
        return {"turn": self.turn, "turn_player": self.local(self.turn_player), "phase": self.phase,
                "me": sides["me"], "opp": sides["opp"], "chain": chain,
                "chain_targets": [d for d in (self.ref(c, True) for c in self.chain_targets) if d],
                "last_summoned": [d for d in (self.ref(c, True) for c in self.last_summoned) if d],
                "summon_player": self.summon_player,
                "battling": [self.ref(c, True) for c in self.battling]}

    def option_card(self, ref) -> dict:
        """A prompt's CardRef as an option: the tracked card at that position (the host zeroes the codes of the
        opponent's cards in selections, so the seat's own knowledge fills them in), else the prompt's code."""
        loc = ref.location
        if loc & LOCATION_OVERLAY:
            card = self.at(ref.controller, loc, ref.sequence, ref.position)
        elif loc:
            card = self.at(ref.controller, loc, ref.sequence)
        else:
            card = None
        if card is not None and ref.code and not card.code:
            card.code = ref.code  # WindBot's `if (card.Id == 0) card.SetId(id)`
        code = card.code if card is not None and card.code else ref.code
        if card is None and loc and not loc & LOCATION_OVERLAY:
            self.misses += 1
        return self.card_dict(card, ref.controller, loc, ref.sequence,
                              None if card is not None else ref.position, code=code)


_HANDLERS = {
    M.Start: NativeView._start,
    M.Draw: NativeView._draw,
    M.Move: NativeView._move,
    M.Swap: NativeView._swap,
    M.PosChange: NativeView._pos_change,
    M.ShuffleDeck: NativeView._shuffle_deck,
    M.ShuffleHand: NativeView._shuffle_hand,
    M.ShuffleExtra: NativeView._shuffle_extra,
    M.ShuffleSetCard: NativeView._shuffle_set,
    M.SwapGraveDeck: NativeView._swap_grave_deck,
    M.ReverseDeck: NativeView._reverse_deck,
    M.DeckTop: NativeView._deck_top,
    M.ConfirmCards: NativeView._confirm,
    M.ConfirmDecktop: NativeView._confirm,
    M.ConfirmExtratop: NativeView._confirm,
    M.UpdateData: NativeView._update_data,
    M.UpdateCard: NativeView._update_card,
    M.ReloadField: NativeView._reload,
    M.NewTurn: NativeView._new_turn,
    M.NewPhase: NativeView._new_phase,
    M.Damage: lambda v, m: v._lp_event("damage", m.player, m.amount),
    M.PayLpCost: lambda v, m: v._lp_event("pay_lp", m.player, m.amount),
    M.Recover: lambda v, m: v._lp_event("recover", m.player, m.amount),
    M.LpUpdate: NativeView._lp_update,
    M.Summoning: lambda v, m: v._summoning(m, False),
    M.SpSummoning: lambda v, m: v._summoning(m, True),
    M.FlipSummoning: lambda v, m: v._summoning(m, False, flip=True),
    M.Summoned: NativeView._summoned,
    M.FlipSummoned: NativeView._summoned,
    M.SpSummoned: NativeView._summoned,
    M.Chaining: NativeView._chaining,
    M.ChainSolved: lambda v, m: [{"e": "chain_solved", "link": m.chain_count}],
    M.ChainNegated: lambda v, m: [{"e": "chain_negated", "link": m.chain_count}],
    M.ChainDisabled: lambda v, m: [{"e": "chain_disabled", "link": m.chain_count}],
    M.ChainEnd: NativeView._chain_end,
    M.BecomeTarget: NativeView._targets,
    M.Attack: NativeView._attack,
    M.Hint: NativeView._hint,
    M.Equip: NativeView._equip,
    M.AddCounter: lambda v, m: v._counter(m, True),
    M.RemoveCounter: lambda v, m: v._counter(m, False),
    M.TossCoin: lambda v, m: v._results(m, "coin"),
    M.TossDice: lambda v, m: v._results(m, "dice"),
    M.Win: NativeView._win,
    M.Retry: lambda v, m: [{"e": "retry"}],
}
