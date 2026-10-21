"""The fairness check: nothing a native seat sends its agent may contain a card code hidden from that seat.

`FairnessChecker(duel_getter, team)` is a DuelObserver on the seat's own filtered stream (it sees each message just
before the seat does) and a `trace` for the AgentSeat (each event and decision is checked the moment it is sent).
Ground truth is the core itself (unfiltered queries at decision time). Three kinds of checks:

  1. Never-seen codes: every code in an event or decision must have reached the seat, through its filtered message
     stream or its fair SeatView queries. Catches any code taken from the full view.
  2. Positions: every card in the state (and every option on the field or in a GY / banished pile) with a code must
     be that card for real, and a card hidden from the seat right now may only carry a code the seat was shown at
     that very spot (a zone) or in that pile (hand, Extra Deck, banished) since it was last shuffled.
  3. No ordering leaks: Deck cards never carry a sequence, and the opponent's cards get new uids after a hidden
     shuffle (their hand, their Set cards), so a uid can't say which hidden card is which.
"""

from __future__ import annotations

import collections
import dataclasses

from ygo_agent.arena import messages as M
from ygo_agent.arena.duel import VIEW_TEAM0, DuelObserver
from ygo_agent.arena.query import CardQuery, parse_location
from ygo_agent.arena.seats import SeatView
from ygo_agent.core.constants import (HINT_CARD, HINT_CODE, HINT_SELECTMSG, LOCATION_DECK, LOCATION_EXTRA,
                                      LOCATION_GRAVE, LOCATION_HAND, LOCATION_MZONE, LOCATION_OVERLAY,
                                      LOCATION_REMOVED, LOCATION_SZONE, QUERY_ALL)

PILES = {"hand": LOCATION_HAND, "gy": LOCATION_GRAVE, "ban": LOCATION_REMOVED, "extra": LOCATION_EXTRA}
ZONES = {"mz": LOCATION_MZONE, "sz": LOCATION_SZONE}


class Leak(AssertionError):
    pass


def message_codes(msg) -> set[int]:
    """Every card code a (filtered) message carries."""
    out: set[int] = set()

    def walk(v, name=""):
        if isinstance(v, (M.CardRef,)):
            if v.code:
                out.add(v.code)
        elif isinstance(v, CardQuery):
            if v.code:
                out.add(v.code)
            out.update(c for c in v.overlay_cards if c)
        elif dataclasses.is_dataclass(v) and not isinstance(v, type):
            for f in dataclasses.fields(v):
                if f.name != "raw":
                    walk(getattr(v, f.name), f.name)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x, name)
        elif isinstance(v, int) and name in ("code", "code1", "code2", "codes") and v:
            out.add(v & 0x7FFFFFFF)
    walk(msg)
    if isinstance(msg, M.Draw):
        out.update(c for c, _ in msg.cards if c)
    if isinstance(msg, M.Hint) and msg.hint_type in (HINT_SELECTMSG, HINT_CODE, HINT_CARD):
        out.add(msg.data)
    return out


def card_codes(d) -> set[int]:
    """Codes in a card dict (and its materials / equip target)."""
    out = set()
    if not isinstance(d, dict):
        return out
    if d.get("id"):
        out.add(d["id"])
    out.update(c for c in d.get("ov", []) if c)
    if isinstance(d.get("eq"), dict) and d["eq"].get("id"):
        out.add(d["eq"]["id"])
    return out


def event_codes(ev) -> set[int]:
    out = set()
    if isinstance(ev.get("id"), int) and ev.get("id"):
        out.add(ev["id"])
    for key in ("card", "attacker", "target"):
        out |= card_codes(ev.get(key))
    for c in ev.get("cards", []) or []:
        out |= card_codes(c)
    if ev.get("e") == "declared" and ev.get("kind") == "card":
        out.add(ev["value"])
    return out


def decision_codes(d) -> set[int]:
    out = set()
    s = d.get("state") or {}
    for side in ("me", "opp"):
        f = s.get(side) or {}
        for key in list(PILES) + list(ZONES):
            for c in f.get(key, []):
                out |= card_codes(c)
    for link in s.get("chain", []):
        out |= card_codes(link.get("card"))
        if link.get("id"):
            out.add(link["id"])
    for key in ("chain_targets", "last_summoned", "battling"):
        for c in s.get(key, []) or []:
            out |= card_codes(c)
    if d["kind"] != "announce_card":
        for o in d.get("options", []):
            if isinstance(o, dict):
                out |= card_codes(o.get("card", o))
    for c in d.get("selected", []):
        out |= card_codes(c)
    out |= card_codes(d.get("card"))
    if d.get("card_id"):
        out.add(d["card_id"])
    return out


class FairnessChecker(DuelObserver, list):
    """Use as the seat's `trace` (a list) and as a DuelObserver of the same duel."""

    def __init__(self, team: int, seat=None):
        list.__init__(self)
        self.team = team
        self.views = frozenset({VIEW_TEAM0 + team})
        self.seat = seat
        self.duel = None
        self.known: set[int] = set()
        self.zone_seen: dict[tuple[int, int, int], int] = {}
        self.pile_seen: dict[tuple[int, int], collections.Counter] = collections.defaultdict(collections.Counter)
        self.opp_hand_uids: list = []         # the opponent's hand uids, in order, as of the last decision
        self.opp_zone_uids: dict[tuple[int, int], int] = {}  # (location, sequence) -> uid, same
        self.stale: set[int] = set()          # uids that must not come back (hidden shuffle since)
        self.checked = collections.Counter()
        self.leaks: list[str] = []

    # --- the seat's stream ----------------------------------------------------------------------------------------
    def on_start(self, duel) -> None:
        self.duel = duel

    def on_message(self, view: int, msg) -> None:
        self.known |= message_codes(msg)
        opp = 1 - self.team
        if isinstance(msg, M.Move):
            prev, cur = msg.previous, msg.current
            self._follow_uids(prev, cur)
            if prev.location in ZONES.values():
                self.zone_seen.pop((prev.controller, prev.location, prev.sequence), None)
            elif prev.location and not prev.location & LOCATION_OVERLAY and msg.code:
                self.pile_seen[(prev.controller, prev.location)][msg.code] -= 1
            if cur.location in ZONES.values():
                key = (cur.controller, cur.location, cur.sequence)
                if msg.code:
                    self.zone_seen[key] = msg.code
                else:
                    self.zone_seen.pop(key, None)
            elif cur.location and not cur.location & LOCATION_OVERLAY and msg.code:
                self.pile_seen[(cur.controller, cur.location)][msg.code] += 1
        elif isinstance(msg, M.Draw):
            if msg.player == opp:
                self.opp_hand_uids += [None] * len(msg.cards)
            for code, _ in msg.cards:
                if code:
                    self.pile_seen[(msg.player, LOCATION_HAND)][code] += 1
        elif isinstance(msg, M.PosChange):
            if msg.code:
                self.zone_seen[(msg.controller, msg.location, msg.sequence)] = msg.code
        elif isinstance(msg, M.Swap):
            for code, li in ((msg.code1, msg.location2), (msg.code2, msg.location1)):
                key = (li.controller, li.location, li.sequence)
                if code:
                    self.zone_seen[key] = code
                else:
                    self.zone_seen.pop(key, None)
        elif isinstance(msg, (M.ConfirmCards, M.ConfirmDecktop, M.ConfirmExtratop)):
            for ref in msg.cards:
                if not ref.code:
                    continue
                if ref.location in ZONES.values():
                    self.zone_seen[(ref.controller, ref.location, ref.sequence)] = ref.code
                else:
                    self.pile_seen[(ref.controller, ref.location)][ref.code] += 1
        elif isinstance(msg, (M.ShuffleHand, M.ShuffleExtra)):
            loc = LOCATION_HAND if isinstance(msg, M.ShuffleHand) else LOCATION_EXTRA
            self.pile_seen[(msg.player, loc)] = collections.Counter(c for c in msg.codes if c)
            if msg.player == opp and loc == LOCATION_HAND:
                self.stale |= {u for u in self.opp_hand_uids if u is not None}
                self.opp_hand_uids = [None] * len(self.opp_hand_uids)
        elif isinstance(msg, M.ShuffleSetCard):
            for li in list(msg.previous) + list(msg.current):
                self.zone_seen.pop((li.controller, li.location, li.sequence), None)
            for li in msg.previous:
                if li.controller == opp and (li.location, li.sequence) in self.opp_zone_uids:
                    self.stale.add(self.opp_zone_uids[(li.location, li.sequence)])
        elif isinstance(msg, M.UpdateCard):
            if msg.card is not None and msg.card.code and msg.location in ZONES.values():
                self.zone_seen[(msg.player, msg.location, msg.sequence)] = msg.card.code
        elif isinstance(msg, M.UpdateData):
            if msg.location in ZONES.values():
                for seq, q in enumerate(msg.cards):
                    if q is not None and q.code:
                        self.zone_seen[(msg.player, msg.location, seq)] = q.code

    def _follow_uids(self, prev, cur) -> None:
        """Keep the opponent's hand/zone uids (as of the last decision) at the right positions as cards move."""
        opp, uid = 1 - self.team, None
        if prev.controller == opp and prev.location == LOCATION_HAND:
            if 0 <= prev.sequence < len(self.opp_hand_uids):
                uid = self.opp_hand_uids.pop(prev.sequence)
        elif prev.controller == opp and prev.location in ZONES.values():
            uid = self.opp_zone_uids.pop((prev.location, prev.sequence), None)
        if cur.controller == opp and cur.location == LOCATION_HAND:
            self.opp_hand_uids.insert(min(cur.sequence, len(self.opp_hand_uids)), uid)
        elif cur.controller == opp and cur.location in ZONES.values() and uid is not None:
            self.opp_zone_uids[(cur.location, cur.sequence)] = uid

    # --- the seat's output (it calls append) ---------------------------------------------------------------------
    def append(self, item) -> None:
        list.append(self, item)
        try:
            if item.get("t") == "event":
                self.check_event(item)
            elif item.get("t") == "decide" and item.get("kind") not in ("go_first", "game_over"):
                self.check_decision(item)
        except Leak as e:
            self.leaks.append(str(e))

    def check_event(self, ev) -> None:
        self.checked["events"] += 1
        unseen = event_codes(ev) - self.known
        if unseen:
            raise Leak(f"event {ev['e']} carries codes the seat never saw: {sorted(unseen)} ({ev})")

    def _fair(self) -> SeatView:
        return SeatView(self.duel, self.team)

    def _truth(self, p: int, loc: int) -> list:
        raw = self.duel.core.query_location(p, loc, QUERY_ALL)
        return parse_location(raw) if raw else []

    def check_decision(self, d) -> None:
        self.checked["decisions"] += 1
        fair = self._fair()
        for q in (q for qs in fair.snapshot().values() for q in qs if q is not None):
            if q.code:
                self.known.add(q.code)
            self.known.update(c for c in q.overlay_cards if c)
        unseen = decision_codes(d) - self.known
        if unseen:
            raise Leak(f"decision #{d['id']} ({d['kind']}) carries codes the seat never saw: {sorted(unseen)}")
        s = d["state"]
        hand_uids, zone_uids = [], {}
        for side, p in (("me", self.team), ("opp", 1 - self.team)):
            for key, loc in list(PILES.items()) + list(ZONES.items()):
                truth, view = self._truth(p, loc), fair.location(p, loc)
                for i, c in enumerate(s[side][key]):
                    if c is None:
                        continue
                    if side == "opp" and c.get("uid") is not None:
                        if key == "hand":
                            hand_uids.append(c["uid"])
                        elif key in ZONES:
                            zone_uids[(loc, i)] = c["uid"]
                    if c.get("id"):
                        self._check_card(d, f"{side}.{key}[{i}]", c, p, loc, i, truth, view)
        for o in d.get("options", []):
            card = o.get("card", o) if isinstance(o, dict) else None
            if not isinstance(card, dict) or "l" not in card:
                continue
            if card["l"] == LOCATION_DECK and card.get("s", -1) != -1:
                raise Leak(f"decision #{d['id']}: a Deck card carries its Deck sequence {card['s']}")
            loc = card["l"]
            if card.get("id") and loc in (LOCATION_MZONE, LOCATION_SZONE, LOCATION_GRAVE, LOCATION_REMOVED) \
                    and card.get("s", -1) >= 0:
                p = self.team if card["c"] == 0 else 1 - self.team
                self._check_card(d, f"option {card}", card, p, loc, card["s"], self._truth(p, loc),
                                 fair.location(p, loc))
        back = (set(hand_uids) | set(zone_uids.values())) & self.stale
        self.stale = set()
        self.opp_hand_uids, self.opp_zone_uids = hand_uids, zone_uids
        if back:
            raise Leak(f"decision #{d['id']}: opponent uids {sorted(back)} survived a hidden shuffle")

    def _check_card(self, d, where, c, p, loc, i, truth, view) -> None:
        if i >= len(truth) or truth[i] is None:
            raise Leak(f"decision #{d['id']}: {where} has {c['id']} but there is no card there")
        real = truth[i].code
        if c["id"] != real:
            raise Leak(f"decision #{d['id']}: {where} says {c['id']}, the card there is {real}")
        if i < len(view) and view[i] is not None and view[i].code:
            self.checked["visible"] += 1
            return
        self.checked["hidden"] += 1
        if loc in ZONES.values():
            ok = self.zone_seen.get((p, loc, i)) == real
        else:
            ok = self.pile_seen[(p, loc)][real] > 0
        if not ok:
            raise Leak(f"decision #{d['id']}: {where} reveals hidden card {real}, never shown to the seat there")
