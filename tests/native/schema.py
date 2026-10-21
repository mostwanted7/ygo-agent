"""The decision protocol (docs/decision-protocol.md) as checks: every field, its type, and the options per kind.

`decision_errors(d)` / `event_errors(ev)` return a list of problems (empty = conforms). The saved bridge
fixtures must pass, so this is the bridge's schema; the native seats' additions are the optional fields and
events the document lists for them.
"""

from __future__ import annotations

INT = int
LOCATIONS = {0, 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x80, 0x100, 0x200}
CARD_OPTIONAL = {"ov", "dis", "att", "eq", "ctr", "sc", "blv", "own", "uid", "v1", "v2"}


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class Checker:
    def __init__(self):
        self.errors: list[str] = []

    def err(self, where: str, what: str) -> None:
        self.errors.append(f"{where}: {what}")

    def ints(self, obj: dict, where: str, *keys: str) -> None:
        for k in keys:
            if k not in obj:
                self.err(where, f"missing {k}")
            elif not _int(obj[k]):
                self.err(where, f"{k} is not an int ({obj[k]!r})")

    def short(self, c, where: str, nullable: bool = False) -> None:
        if c is None:
            if not nullable:
                self.err(where, "null card")
            return
        if not isinstance(c, dict):
            return self.err(where, f"not a card: {c!r}")
        self.ints(c, where, "id", "c", "l", "s")
        if c.get("c") not in (0, 1):
            self.err(where, f"controller {c.get('c')}")
        if c.get("l") not in LOCATIONS and not (_int(c.get("l")) and c["l"] & 0x80):
            self.err(where, f"location {c.get('l')}")

    def card(self, c, where: str, nullable: bool = False) -> None:
        if c is None:
            if not nullable:
                self.err(where, "null card")
            return
        self.short(c, where)
        if not isinstance(c, dict):
            return
        self.ints(c, where, "p")
        if c.get("id"):
            self.ints(c, where, "atk", "def", "lv", "rk", "lk")
        extra = set(c) - {"id", "c", "l", "s", "p", "atk", "def", "lv", "rk", "lk"} - CARD_OPTIONAL
        if extra:
            self.err(where, f"unknown fields {sorted(extra)}")
        if "ov" in c and not (isinstance(c["ov"], list) and all(_int(x) for x in c["ov"])):
            self.err(where, "ov must be a list of codes")
        for flag in ("dis", "att"):
            if flag in c and c[flag] is not True:
                self.err(where, f"{flag} must be true when present")
        if "eq" in c:
            self.short(c["eq"], where + ".eq")
        if "ctr" in c and not (isinstance(c["ctr"], list) and all(
                isinstance(x, list) and len(x) == 2 and all(_int(y) for y in x) for x in c["ctr"])):
            self.err(where, "ctr must be [[type, count], ...]")
        if "sc" in c and not (isinstance(c["sc"], list) and len(c["sc"]) == 2 and all(_int(y) for y in c["sc"])):
            self.err(where, "sc must be [left, right]")
        if "own" in c and c["own"] not in (0, 1):
            self.err(where, "own must be 0 or 1")
        for k in ("blv", "uid"):
            if k in c and not _int(c[k]):
                self.err(where, f"{k} must be an int")

    def side(self, f, where: str) -> None:
        if not isinstance(f, dict):
            return self.err(where, "not an object")
        self.ints(f, where, "lp", "deck")
        for key in ("hand", "gy", "ban", "extra"):
            for i, c in enumerate(f.get(key, [])):
                self.card(c, f"{where}.{key}[{i}]")
            if key not in f:
                self.err(where, f"missing {key}")
        for key, n in (("mz", 7), ("sz", 8)):
            zone = f.get(key)
            if not isinstance(zone, list) or len(zone) not in (0, n):
                self.err(where, f"{key} must have {n} slots")
                continue
            for i, c in enumerate(zone):
                self.card(c, f"{where}.{key}[{i}]", nullable=True)

    def state(self, s) -> None:
        if not isinstance(s, dict):
            return self.err("state", "missing")
        self.ints(s, "state", "turn", "turn_player", "phase", "summon_player")
        if s.get("turn_player") not in (0, 1):
            self.err("state", "turn_player must be 0 or 1")
        self.side(s.get("me"), "state.me")
        self.side(s.get("opp"), "state.opp")
        for i, link in enumerate(s.get("chain", [])):
            self.ints(link, f"chain[{i}]", "id", "player", "desc")
            self.card(link.get("card"), f"chain[{i}].card", nullable=True)
        for key in ("chain_targets", "last_summoned"):
            if not isinstance(s.get(key), list):
                self.err("state", f"{key} must be a list")
            for i, c in enumerate(s.get(key) or []):
                self.short(c, f"{key}[{i}]")
        battling = s.get("battling")
        if not (isinstance(battling, list) and len(battling) == 2):
            self.err("state", "battling must be [mine, theirs]")
        else:
            for i, c in enumerate(battling):
                self.short(c, f"battling[{i}]", nullable=True)


ACTIONS = {"idle": ("activate", "summon", "spsummon", "set_monster", "set_spell", "reposition", "to_battle", "to_end"),
           "battle": ("activate", "attack", "to_main2", "to_end"), "chain": ("activate",)}
KIND_FIELDS = {
    "idle": {}, "battle": {}, "chain": {"forced": bool},
    "effect_yn": {"card": dict, "desc": int}, "yesno": {"desc": int}, "go_first": {},
    "select_card": {"min": int, "max": int, "hint": int, "cancelable": bool},
    "tribute": {"min": int, "max": int, "hint": int, "cancelable": bool},
    "select_unselect": {"selected": list, "min": int, "max": int, "hint": int, "finishable": bool, "cancelable": bool},
    "select_sum": {"sum": int, "min": int, "max": int, "hint": int, "exact": bool},
    "option": {}, "position": {"card_id": int},
    "place": {"card_id": int, "player": int, "location": int, "available": int},
    "announce_card": {}, "announce_number": {}, "announce_attrib": {"count": int}, "announce_race": {"count": int},
    "game_over": {"result": int, "reason": int},
}
NO_OPTIONS = ("effect_yn", "yesno", "go_first", "place", "game_over")


def decision_errors(d: dict) -> list[str]:
    ck = Checker()
    kind = d.get("kind")
    if d.get("t") != "decide" or not _int(d.get("id")) or d["id"] < 1:
        ck.err("decision", "needs t=decide and an id >= 1")
    if kind not in KIND_FIELDS:
        return [f"unknown kind {kind!r}"]
    for key, typ in KIND_FIELDS[kind].items():
        v = d.get(key)
        ok = isinstance(v, typ) and (typ is not int or not isinstance(v, bool))
        if not ok:
            ck.err(kind, f"{key} must be {typ.__name__} ({v!r})")
    ck.state(d.get("state"))
    opts = d.get("options")
    if kind in NO_OPTIONS:
        if opts:
            ck.err(kind, "has options")
    elif not isinstance(opts, list) or (not opts and kind != "announce_card"):
        ck.err(kind, "needs a non-empty options list")
    else:
        for i, o in enumerate(opts):
            where = f"{kind}.options[{i}]"
            if kind in ACTIONS:
                if o.get("a") not in ACTIONS[kind]:
                    ck.err(where, f"action {o.get('a')!r}")
                if o.get("a") in ("to_battle", "to_end", "to_main2"):
                    if "card" in o:
                        ck.err(where, "phase actions have no card")
                else:
                    ck.card(o.get("card"), where + ".card")
                if (o.get("a") == "activate") != ("desc" in o):
                    ck.err(where, "desc goes with activate (only)")
                if (o.get("a") == "attack") != ("direct" in o):
                    ck.err(where, "direct goes with attack (only)")
            elif kind in ("select_card", "tribute", "select_unselect", "select_sum"):
                ck.card(o, where)
                if kind == "select_sum":
                    ck.ints(o, where, "v1", "v2")
            elif not _int(o):
                ck.err(where, "must be an int")
        order = [ACTIONS[kind].index(o.get("a")) for o in opts if kind in ACTIONS and o.get("a") in ACTIONS[kind]]
        if order != sorted(order):
            ck.err(kind, "options out of order")
    if kind == "select_unselect":
        for i, c in enumerate(d.get("selected", [])):
            ck.card(c, f"selected[{i}]")
    if kind == "effect_yn":
        ck.card(d.get("card"), "effect_yn.card")
    if kind == "place" and d.get("location") not in (0x4, 0x8, 0x100, 0x200):
        ck.err("place", f"location {d.get('location')}")
    return ck.errors


EVENTS = {
    "room": {"duel_flags": int, "forbidden_types": int, "best_of": int, "teams": list, "start_lp": int,
             "start_hand": int, "draw_count": int, "time_limit": int},
    "start": {"first": bool, "lp": list, "names": list},
    "draw": {"player": int, "count": int}, "new_turn": {"turn": int, "player": int},
    "new_phase": {"phase": int, "player": int},
    "move": {"id": int, "from": dict, "to": dict, "reason": int},
    "summoning": {"id": int, "to": dict, "special": bool},
    "summoned": {"id": int, "to": dict, "special": bool},
    "chaining": {"id": int, "card": dict, "player": int, "desc": int, "link": int},
    "chain_solved": {"link": int}, "chain_negated": {"link": int}, "chain_disabled": {"link": int},
    "chain_end": {}, "attack": {"attacker": dict},
    "damage": {"player": int, "amount": int, "lp": int}, "pay_lp": {"player": int, "amount": int, "lp": int},
    "recover": {"player": int, "amount": int, "lp": int}, "lp": {"player": int, "lp": int},
    "pos_change": {"id": int, "c": int, "l": int, "s": int, "from": int, "to": int},
    "targeted": {"card": dict},
    "chat": {"player": int, "position": int, "message": str},
    "win": {"result": int, "reason": int}, "retry": {},
    # native seats only (optional events)
    "confirm": {"player": int, "cards": list}, "equip": {"card": dict, "target": dict}, "swap": {"cards": list},
    "counter": {"card": dict, "type": int, "count": int, "add": bool},
    "coin": {"player": int, "results": list}, "dice": {"player": int, "results": list},
    "declared": {"player": int, "kind": str, "value": int},
}


def event_errors(ev: dict) -> list[str]:
    ck = Checker()
    e = ev.get("e")
    if ev.get("t") != "event" or e not in EVENTS:
        return [f"unknown event {e!r}"]
    for key, typ in EVENTS[e].items():
        v = ev.get(key)
        if not isinstance(v, typ) or (typ is int and isinstance(v, bool)):
            ck.err(e, f"{key} must be {typ.__name__} ({v!r})")
    for key in ("card", "attacker", "target"):
        if key in ev and (ev[key] is not None or key != "target"):
            ck.card(ev[key], f"{e}.{key}")
    for i, c in enumerate(ev.get("cards", []) if e in ("confirm", "swap") else []):
        ck.card(c, f"{e}.cards[{i}]")
    for key in ("from", "to"):
        if key in ev and isinstance(ev[key], dict):
            ck.ints(ev[key], f"{e}.{key}", "c", "l", "s", "p")
    if e == "attack" and "target" not in ev:
        ck.err(e, "missing target (null for a direct attack)")
    for key in ("window", "flip"):  # optional flags of summoning/summoned
        if key in ev and not isinstance(ev[key], bool):
            ck.err(e, f"{key} must be bool ({ev[key]!r})")
    return ck.errors
