"""Backend type "heuristic": a no-LLM policy over the decision JSON (docs/decision-protocol.md).

It is a baseline for benchmarks and the fallback for native seats, so it always returns a legal reply for every
decision kind (anything it can't reason about gets the first legal answer). The play is simple but not silly:

- Main Phase: use card effects and non-Quick-Play spells, Special Summon by procedure, Normal Summon the strongest
  monster (Set it instead when the opponent has something stronger), switch positions for attacks, attack when an
  attack wins, then Set traps and Quick-Play spells before ending the turn.
- Battle: attack directly, or into monsters it beats; never into a stronger known monster.
- Chain windows: respond with hand traps, traps and Quick-Plays only to the opponent's plays; use its own
  triggered effects during its own turn; otherwise pass.
- Targets: the opponent's strongest card for removal, its own weakest card for costs and materials, its own best
  card for searches and summons. Optional triggers and "use this effect?" questions get a yes.

Use it directly as `Policy(db).choose(decision)` (a list, the same reply format the agent sends).
"""

import collections

from ..agent.validate import validate
from .base import Backend, Session, new_info

DECK, HAND, MZONE, SZONE, GY, BANISHED, EXTRA = 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40
FU_ATK, FD_ATK, FU_DEF, FD_DEF = 0x1, 0x2, 0x4, 0x8
MONSTER, SPELL, TRAP, TOKEN, QUICKPLAY, COUNTER_TRAP = 0x1, 0x2, 0x4, 0x4000, 0x10000, 0x100000
BATTLE_PHASES = (0x8, 0x10, 0x20, 0x40, 0x80)
MAIN2 = 0x100
ATTACK_TARGET = 549

COST_HINTS = {500, 501, 511, 512, 513, 519, 531, 533, 578}          # tribute, discard, materials, detach
REMOVAL_HINTS = {502, 503, 505, 507, 520, 528, 530, 575, 576}       # destroy, banish, bounce, take control, negate
NO_YESNO = {93, 210}  # "continue choosing materials / selecting cards?": stop at the minimum
MAX_SAME_ACTION = 2   # per turn: the same effect/summon/attack is never chosen more often (loop guard)
MAX_IDLE_ACTIONS = 40


def lowest_bit(mask):
    return mask & -mask


def first_legal(d):
    """A deterministic legal reply to any decision (the safety net under every policy)."""
    kind, opts = d["kind"], d.get("options", [])
    if kind in ("effect_yn", "yesno", "go_first"):
        return [1]
    if kind == "chain":
        return [0] if d.get("forced") and opts else []
    if kind in ("idle", "battle"):
        for want in ("to_end", "to_main2"):
            for i, o in enumerate(opts):
                if o.get("a") == want:
                    return [i]
        return [0]
    if kind in ("select_card", "tribute"):
        return list(range(min(d.get("min", 0), len(opts))))
    if kind == "select_unselect":
        return [] if d.get("finishable") or not opts else [0]
    if kind == "select_sum":
        return sum_pick(d, lambda i: 1) or list(range(len(opts)))
    if kind in ("announce_attrib", "announce_race"):
        return list(range(min(d.get("count", 1), len(opts))))
    if kind == "place":
        return [lowest_bit(d.get("available", 0)) or 1]
    return [0] if opts else []


def sum_pick(d, cost):
    """Cheapest option indices whose values satisfy a select_sum (see agent/validate.py), or None.
    Costs are positive, so the cheapest set never holds a card it could drop (the engine rejects those)."""
    opts, target = d.get("options", []), d.get("sum", 0)
    exact, lo, hi = d.get("exact"), d.get("min", 0), min(d.get("max", 99), len(d.get("options", [])))
    best = None
    for values in ([o.get("v1", 0) for o in opts], [o.get("v2") or o.get("v1", 0) for o in opts]):
        states = {(0, 0): (0, ())}
        for i, v in enumerate(values):
            nxt = dict(states)
            for (k, s), (c, items) in states.items():
                if k >= hi or (exact and s + v > target) or (not exact and s >= target):
                    continue
                cand = (c + max(1, cost(i)), items + (i,))
                if (k + 1, s + v) not in nxt or cand < nxt[(k + 1, s + v)]:
                    nxt[(k + 1, s + v)] = cand
            states = nxt
        for (k, s), (c, items) in states.items():
            if lo <= k <= hi and (s == target if exact else s >= target) and validate(d, list(items)) is None:
                if best is None or (c, k) < best[0]:
                    best = ((c, k), sorted(items))
    return best[1] if best else None


class Policy:
    def __init__(self, db=None):
        self.db = db
        self.turn = None
        self.used = collections.Counter()  # (action key) -> times chosen this turn
        self.idle_actions = 0
        self.attacker = None
        self.why = ""

    # ---- entry point ----

    def choose(self, d):
        """The reply (a list) for decision `d`; self.why says why."""
        state = d.get("state") or {}
        if state.get("turn") != self.turn:
            self.turn, self.used, self.idle_actions = state.get("turn"), collections.Counter(), 0
        self.why = ""
        try:
            choice = getattr(self, "_" + d["kind"], self._default)(d)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            choice = None
        if choice is None or validate(d, choice) is not None:
            choice, self.why = first_legal(d), "first legal option"
        return choice

    def _default(self, d):
        return None

    # ---- card helpers ----

    def data(self, card):
        return self.db.get(card.get("id")) if self.db and card and card.get("id") else None

    def ctype(self, card):
        data = self.data(card)
        if data:
            return data.type
        return MONSTER if card and (card.get("lv") or card.get("rk") or card.get("lk") or card.get("atk")) else 0

    def is_monster(self, card):
        return bool(self.ctype(card) & MONSTER)

    def atk(self, card):
        if card.get("atk") or not self.data(card):
            return card.get("atk") or 0
        return max(0, self.data(card).atk)

    def defense(self, card):
        if card.get("def") or not self.data(card):
            return card.get("def") or 0
        return max(0, self.data(card).defense)

    def worth(self, card):
        """How much the bot values one of its own cards (costs go to the cheapest)."""
        t = self.ctype(card)
        if t & TOKEN:
            return 0
        if t & MONSTER:
            return 100 + self.atk(card) + self.defense(card) // 4 + 50 * (card.get("lv") or card.get("rk") or 0)
        return 1300 if card.get("l") in (HAND, DECK) or card.get("p", 0) & 0xA else 900

    def threat(self, card):
        """How much the bot wants an opponent's card gone."""
        if card.get("l") == MZONE:
            if not card.get("id"):
                return 1500
            return max(self.atk(card), self.defense(card) // 2) + 100
        if card.get("l") == SZONE:
            return 1200 if not card.get("id") or card.get("p", 0) & 0xA else 1000
        return 500 + (self.atk(card) // 2 if self.is_monster(card) else 0)

    @staticmethod
    def key(card, *extra):
        return (card.get("id"), card.get("c"), card.get("l"), card.get("s")) + extra if card else extra

    def fresh(self, key, limit=MAX_SAME_ACTION):
        return self.used[key] < limit

    def mark(self, key):
        self.used[key] += 1

    # ---- the board ----

    @staticmethod
    def monsters(state, side):
        return [c for c in (state.get(side) or {}).get("mz", []) if c]

    def beats(self, atk, target):
        """Attacking `target` with `atk` destroys it without losing ours (face-down: assumed a weak defender)."""
        if not target.get("id"):
            return atk >= 1600
        if target.get("p", 0) & (FU_ATK | FD_ATK):
            return atk > self.atk(target)
        return atk > self.defense(target)

    def opp_best_atk(self, state):
        return max((self.atk(c) for c in self.monsters(state, "opp") if c.get("id") and c.get("p", 0) & FU_ATK),
                   default=0)

    def can_attack_well(self, card, state):
        opp = self.monsters(state, "opp")
        atk = self.atk(card)
        return atk > 0 and (not opp or any(self.beats(atk, t) for t in opp))

    # ---- Main Phase ----

    def activate_now(self, opt):
        card = opt.get("card") or {}
        t, loc = self.ctype(card), card.get("l")
        if loc == HAND:
            if t & SPELL:
                return not t & QUICKPLAY  # Quick-Plays wait for the opponent's plays
            return not t & TRAP
        if loc == SZONE and card.get("p", 0) & 0xA:  # a Set card: Normal Spells yes, traps and Quick-Plays wait
            return bool(t & SPELL) and not t & QUICKPLAY
        return True  # effects of cards already on the field, in the GY or banished

    def summon_score(self, card, state):
        atk, lv = self.atk(card), card.get("lv") or 0
        tributes = 0 if lv <= 4 else 1 if lv <= 6 else 2
        mine = sorted(self.worth(c) for c in self.monsters(state, "me"))
        return atk - sum(mine[:tributes]) if tributes <= len(mine) else atk - 1000 * tributes

    def _idle(self, d):
        s, opts = d["state"], d["options"]
        by = collections.defaultdict(list)
        for i, o in enumerate(opts):
            by[o["a"]].append(i)
        main2 = s.get("phase") == MAIN2
        self.idle_actions += 1
        busy = self.idle_actions <= MAX_IDLE_ACTIONS

        def pick(i, why):
            self.mark(self.key(opts[i].get("card"), opts[i]["a"], opts[i].get("desc")))
            self.why = why
            return [i]

        def ok(i):
            return busy and self.fresh(self.key(opts[i].get("card"), opts[i]["a"], opts[i].get("desc")))

        acts = [i for i in by["activate"] if ok(i) and self.activate_now(opts[i])]
        if acts:
            return pick(acts[0], "use this effect while it's available")
        sps = [i for i in by["spsummon"] if ok(i)]
        if sps:
            return pick(max(sps, key=lambda i: self.atk(opts[i]["card"])), "Special Summon the strongest monster")
        summons = [i for i in by["summon"] if ok(i)]
        if summons:
            best = max(summons, key=lambda i: self.summon_score(opts[i]["card"], s))
            card = opts[best]["card"]
            stronger = self.opp_best_atk(s) > self.atk(card)
            sets = [i for i in by["set_monster"] if ok(i)]
            if self.summon_score(card, s) > 0 and not (stronger and sets):
                return pick(best, "Normal Summon the strongest monster")
            if sets:
                return pick(max(sets, key=lambda i: self.defense(opts[i]["card"])),
                            "Set a monster: the opponent has a stronger one")
        elif by["set_monster"] and not self.monsters(s, "me"):
            sets = [i for i in by["set_monster"] if ok(i)]
            if sets:
                return pick(max(sets, key=lambda i: self.defense(opts[i]["card"])), "Set a monster as a wall")
        for i in by["reposition"]:
            card = opts[i]["card"]
            if not ok(i):
                continue
            in_defense = card.get("p", 0) & (FU_DEF | FD_DEF)
            if in_defense and not main2 and by["to_battle"] and self.can_attack_well(card, s):
                return pick(i, "switch to Attack Position to attack")
            if not in_defense and main2 and self.atk(card) < self.opp_best_atk(s) and self.defense(card) > self.atk(card):
                return pick(i, "switch to Defense Position: the opponent's monster is stronger")
        if by["to_battle"] and not main2:
            if any(self.can_attack_well(c, s) for c in self.monsters(s, "me")
                   if c.get("p", 0) & FU_ATK and not c.get("att")):
                self.why = "go to battle: an attack wins"
                return [by["to_battle"][0]]
        sets = [i for i in by["set_spell"] if ok(i) and self.ctype(opts[i]["card"]) & (TRAP | QUICKPLAY)]
        if sets:
            return pick(sets[0], "Set a trap / Quick-Play for the opponent's turn")
        if by["to_end"]:
            self.why = "nothing useful left: end the turn"
            return [by["to_end"][0]]
        if by["to_battle"]:
            return [by["to_battle"][0]]
        return None

    def _battle(self, d):
        s, opts = d["state"], d["options"]
        opp = self.monsters(s, "opp")
        good = []
        for i, o in enumerate(opts):
            if o.get("a") != "attack":
                continue
            card = o["card"]
            atk = self.atk(card)
            if not self.fresh(self.key(card, "attack")) or atk <= 0:
                continue
            if o.get("direct") or not opp:
                good.append((1, atk, i))
            elif any(self.beats(atk, t) for t in opp):
                good.append((0, atk, i))
        if good:
            direct, _, i = max(good)
            self.attacker = opts[i]["card"]
            self.mark(self.key(self.attacker, "attack"))
            self.why = "attack directly" if direct else "attack: it wins the battle"
            return [i]
        for want in ("to_main2", "to_end"):
            for i, o in enumerate(opts):
                if o.get("a") == want:
                    self.why = "no attack wins: leave the Battle Phase"
                    return [i]
        return None

    # ---- responses ----

    def opponent_acting(self, s):
        chain = s.get("chain") or []
        if chain:
            return chain[-1].get("player") == 1
        battling = s.get("battling") or [None, None]
        attacking = s.get("turn_player") == 1 and s.get("phase") in BATTLE_PHASES and len(battling) > 1 and battling[1]
        return s.get("summon_player") == 1 or bool(attacking)

    def _chain(self, d):
        s, opts = d["state"], d["options"]
        if d.get("forced"):
            self.why = "the activation is mandatory"
            return [0]
        chain = s.get("chain") or []
        opponent = self.opponent_acting(s)
        own_chain = not chain or chain[-1].get("player") == 0
        best = None
        for i, o in enumerate(opts):
            card = o.get("card") or {}
            k = self.key(card, "chain", o.get("desc"))
            if not self.fresh(k):
                continue
            in_play = card.get("l") in (MZONE, GY, BANISHED) or (card.get("l") == SZONE and not card.get("p", 0) & 0xA)
            if opponent:
                prio = 2 if not in_play else 1
            elif in_play and s.get("turn_player") == 0 and own_chain:
                prio = 1  # its own triggered effects, during its own turn
            else:
                continue
            if best is None or prio > best[0]:
                best = (prio, i, k)
        if best is None:
            self.why = "nothing to respond to: pass"
            return []
        self.mark(best[2])
        self.why = "respond to the opponent's play" if opponent else "use this triggered effect"
        return [best[1]]

    def _effect_yn(self, d):
        self.why = "use the optional effect"
        return [1]

    def _yesno(self, d):
        no = d.get("desc") in NO_YESNO
        self.why = "stop at the minimum" if no else "yes"
        return [0] if no else [1]

    def _go_first(self, d):
        self.why = "go first"
        return [1]

    # ---- selections ----

    def category(self, d):
        hint, opts = d.get("hint"), d.get("options", [])
        theirs = any(c.get("c") == 1 for c in opts)
        if d["kind"] == "tribute" or hint in COST_HINTS:
            return "cost"
        if hint in REMOVAL_HINTS or hint == 551:
            return "removal" if theirs else ("cost" if hint in REMOVAL_HINTS else "benefit")
        if hint == 504:  # send to the GY: from the Deck it's a benefit, from the field or hand a cost
            if theirs:
                return "removal"
            return "benefit" if all(c.get("l") in (DECK, EXTRA) for c in opts) else "cost"
        return "removal" if theirs and not any(c.get("c") == 0 for c in opts) else "benefit"

    def ranked(self, d, category):
        opts = d.get("options", [])
        mine = [i for i, c in enumerate(opts) if c.get("c") != 1]
        theirs = sorted((i for i, c in enumerate(opts) if c.get("c") == 1), key=lambda i: -self.threat(opts[i]))
        if category == "cost":
            return sorted(mine, key=lambda i: self.worth(opts[i])) + theirs[::-1], mine
        if category == "removal":
            return theirs + sorted(mine, key=lambda i: self.worth(opts[i])), theirs
        hand = {c.get("id") for c in ((d.get("state") or {}).get("me") or {}).get("hand", []) if c}
        best = sorted(mine, key=lambda i: -(self.worth(opts[i]) - (2000 if opts[i].get("id") in hand else 0)))
        return best + theirs, best

    def attack_target(self, d):
        opts = d["options"]
        atk = self.atk(self.attacker) if self.attacker else max(
            (self.atk(c) for c in self.monsters(d["state"], "me")), default=0)
        wins = [i for i, c in enumerate(opts) if self.beats(atk, c)]
        if wins:
            self.why = "attack the strongest monster this one beats"
            return [max(wins, key=lambda i: self.threat(opts[i]))]
        if d.get("cancelable"):
            self.why = "no target it beats: cancel the attack"
            return []
        self.why = "attack the weakest target"
        return [min(range(len(opts)), key=lambda i: self.threat(opts[i]))]

    def _select_card(self, d):
        if d.get("hint") == ATTACK_TARGET and d.get("min", 1) <= 1:
            return self.attack_target(d)
        cat = self.category(d)
        order, preferred = self.ranked(d, cat)
        lo, hi = d.get("min", 0), d.get("max", 1)
        n = lo if cat == "cost" else max(lo, min(hi, len(preferred)))
        self.why = {"cost": "pay with the least valuable cards", "removal": "hit the opponent's strongest cards",
                    "benefit": "take the best cards"}[cat]
        return sorted(order[:min(n, len(order))])

    _tribute = _select_card

    def _select_unselect(self, d):
        opts = d.get("options", [])
        cat = self.category(d)
        order, preferred = self.ranked(d, cat)
        if d.get("finishable") and (cat != "removal" or not preferred or len(d.get("selected", [])) >= d.get("max", 1)):
            self.why = "the selection is complete"
            return []
        if not opts:
            return []
        self.why = {"cost": "use the least valuable card", "removal": "hit the opponent's strongest card",
                    "benefit": "take the best card"}[cat]
        return [order[0]]

    def _select_sum(self, d):
        opts = d.get("options", [])
        self.why = "the cheapest cards that reach the sum"
        return sum_pick(d, lambda i: self.worth(opts[i]))

    def _position(self, d):
        opts = d.get("options", [])
        card = self.db.get(d.get("card_id")) if self.db else None
        atk, df = (max(0, card.atk), max(0, card.defense)) if card else (0, 0)
        state = d.get("state") or {}
        opp = self.monsters(state, "opp")
        attack = atk > 0 and (atk > self.opp_best_atk(state) if opp else atk >= df)
        for want in ((FU_ATK,) if attack else ()) + (FU_DEF, FD_DEF, FU_ATK):
            if want in opts:
                self.why = "Attack Position" if want == FU_ATK else "Defense Position"
                return [opts.index(want)]
        return [0]

    def _option(self, d):
        self.why = "the first effect"
        return [0]

    def _announce_number(self, d):
        self.why = "the highest number"
        return [len(d.get("options", [])) - 1]

    def _announce_card(self, d):
        s = d.get("state") or {}
        seen = collections.Counter(c.get("id") for zone in ("gy", "ban", "mz", "sz", "hand")
                                   for c in (s.get("opp") or {}).get(zone, []) if c and c.get("id"))
        opts = d.get("options", [])
        known = [i for i, code in enumerate(opts) if seen.get(code)]
        self.why = "a card the opponent has shown" if known else "the first card"
        return [max(known, key=lambda i: seen[opts[i]])] if known else [0]

    def _announce_flags(self, d, field):
        s, opts, count = d.get("state") or {}, d.get("options", []), d.get("count", 1)
        tally = collections.Counter()
        for c in self.monsters(s, "opp"):
            data = self.data(c)
            if data:
                tally[getattr(data, field)] += 1
        order = sorted(range(len(opts)), key=lambda i: -sum(n for v, n in tally.items() if v & opts[i]))
        self.why = "what the opponent's monsters are"
        return sorted(order[:count])

    def _announce_attrib(self, d):
        return self._announce_flags(d, "attribute")

    def _announce_race(self, d):
        return self._announce_flags(d, "race")

    def _place(self, d):
        self.why = "the first free zone"
        return [lowest_bit(d.get("available", 0))] if d.get("available") else None


class HeuristicBackend(Backend):
    TYPE = "heuristic"

    def __init__(self, profile, db=None):
        super().__init__(profile, db)
        self.policy = Policy(db)  # shared by the seat's sessions, so per-turn memory survives a rollover

    def open_session(self, system_prompt, schema):
        return PolicySession(self.policy)


class PolicySession(Session):
    """A session over a policy object with choose(decision) and a `why`."""

    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def ask(self, request):
        info = new_info()
        self.messages += 1
        if not request.decision:
            info["error"] = "this backend needs the decision itself, not only the prompt text"
            return None, info
        choice = self.policy.choose(request.decision)
        info["replies"] = 1
        return {"choice": choice, "why": getattr(self.policy, "why", ""), "plan": None}, info
