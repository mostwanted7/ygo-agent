"""Turns the bot's raw JSON (state, options, events) into readable text for the model and for the logs."""

LOC = {0x1: "Deck", 0x2: "hand", 0x4: "Monster Zone", 0x8: "Spell/Trap Zone", 0x10: "GY", 0x20: "banished",
       0x40: "Extra Deck", 0x80: "Xyz material", 0x100: "Field Zone", 0x200: "Pendulum Zone"}
PHASES = {0x1: "Draw Phase", 0x2: "Standby Phase", 0x4: "Main Phase 1", 0x8: "Battle Phase (start step)",
          0x10: "Battle Step", 0x20: "Damage Step", 0x40: "Damage Calculation", 0x80: "Battle Phase (end step)",
          0x100: "Main Phase 2", 0x200: "End Phase"}
POSITIONS = {0x1: "face-up Attack", 0x2: "face-down Attack", 0x4: "face-up Defense", 0x8: "face-down Defense"}
REASONS = [(0x1, "destroyed"), (0x2, "Tributed"), (0x20, "by battle"), (0x40, "by effect"), (0x80, "as cost"),
           (0x4000, "discarded"), (0x8, "as material"), (0x40000, "Fusion"), (0x80000, "Synchro"),
           (0x100000, "Ritual"), (0x200000, "Xyz"), (0x10000000, "Link"), (0x20000, "returned"),
           (0x400, "by rule")]
ATTRIBUTE_FLAGS = {0x1: "EARTH", 0x2: "WATER", 0x4: "FIRE", 0x8: "WIND", 0x10: "LIGHT", 0x20: "DARK", 0x40: "DIVINE"}

HINT_ATTACK_TARGET = 549
CANNOT_ATTACK = {"EFFECT_CANNOT_ATTACK", "EFFECT_CANNOT_ATTACK_ANNOUNCE"}
OWN_PROCEDURE = "(by its own summoning procedure)"


def loc_name(loc):
    if loc & 0x80:
        return "Xyz material"
    return LOC.get(loc, f"location {loc}")


def whose(controller):
    return "your" if controller == 0 else "opponent's"


def zone_label(loc, seq):
    if loc == 0x4:
        return f"M{seq + 1}" if seq < 5 else ("EMZ-left" if seq == 5 else "EMZ-right")
    if loc == 0x8:
        return f"S{seq + 1}" if seq < 5 else ("Field" if seq == 5 else f"P{seq - 5}")
    return loc_name(loc)


class Describer:
    """All text the model sees. Events are described one at a time (event), and for a seat's duel log through lines(),
    which also merges a Summon that went through at once into one line. It remembers a little of the event stream:
    which Summons are still in their negation window, and (for logs that don't say) whether a chain is open.
    `attack_note`: say on the "Go to the Battle Phase" option when an attack could matter (attack_summary)."""

    def __init__(self, db, attack_note=True):
        self.db = db
        self.attack_note = attack_note
        self.chain_open = False   # between a `chaining` and its `chain_end`
        self.summons = {}         # (controller, zone) -> the `summoning` of a Summon still in its negation window
        self.held = None          # lines(): (event, line) of such a Summon, until the next event shows how it went

    # ---- cards ----

    def name(self, card):
        if not card:
            return "nothing"
        if not card.get("id"):
            return "a face-down card" if card.get("l") in (0x4, 0x8) else "an unknown card"
        return f'"{self.db.name(card["id"])}"'

    def where(self, card):
        loc, seq, ctrl = card.get("l", 0), card.get("s", 0), card.get("c", 0)
        if loc in (0x4, 0x8):
            return f"{whose(ctrl)} {zone_label(loc, seq)}"
        return f"{whose(ctrl)} {loc_name(loc)}"

    def stats(self, card):
        """Battle stats and status for a monster on the field (none for a short card object, which has no stats)."""
        if not card or not card.get("id") or card.get("l") != 0x4 or "atk" not in card:
            return ""
        data = self.db.get(card["id"])
        bits = [POSITIONS.get(card.get("p"), "")]
        if data and data.has(0x4000000):
            bits.append(f"ATK {card.get('atk')}")
        else:
            bits.append(f"ATK {card.get('atk')} / DEF {card.get('def')}")
        if card.get("blv") is not None:
            rank = data and data.has(0x800000)
            bits.append(f"{'Rank' if rank else 'Level'} {card.get('rk' if rank else 'lv')} (printed {card['blv']})")
        if card.get("ov"):
            bits.append(f"{len(card['ov'])} material(s): " + ", ".join(self.db.name(i) for i in card["ov"]))
        bits += self.extras(card)
        if card.get("dis"):
            bits.append("effects negated")
        if card.get("att"):
            bits.append("already attacked")
        if card.get("own") is not None:
            bits.append("owned by " + ("you" if card["own"] == 0 else "your opponent"))
        return ", ".join(b for b in bits if b)

    def extras(self, card):
        """Status the native arena seats add (counters, equip target, Pendulum Scales); WindBot never sends these
        fields except `eq`, so decisions without them read as before."""
        bits = []
        for kind, n in card.get("ctr") or []:
            bits.append(f"{n} {self.db.counters.get(kind, f'counter {kind:#x}')}(s)")
        eq = card.get("eq")
        if eq:
            bits.append(f"equipped to {self.name(eq)} ({self.where(eq)})")
        if card.get("sc"):
            left, right = card["sc"]
            bits.append(f"Pendulum Scale {left}" if left == right else f"Pendulum Scales {left}/{right}")
        return bits

    def zone_status(self, card):
        """The status of a card in the Spell & Trap Zone (monsters get theirs from stats())."""
        if not card or not card.get("id") or card.get("l") != 0x8:
            return ""
        bits = self.extras(card)
        if card.get("dis"):
            bits.append("effects negated")
        if card.get("own") is not None:
            bits.append("owned by " + ("you" if card["own"] == 0 else "your opponent"))
        return ", ".join(bits)

    def card_line(self, card, with_where=False):
        text = self.name(card)
        if card and card.get("id") and card.get("l") == 0x8 and card.get("p", 0) & 0xA:
            text += " (set)"
        stats = self.stats(card) or self.zone_status(card)
        if stats:
            text += f" ({stats})"
        if with_where and card:
            text += f" — {self.where(card)}"
        return text

    # ---- state ----

    def _zones(self, cards, loc):
        parts = []
        for seq, card in enumerate(cards):
            if card is None:
                continue
            if card.get("id") == 0:
                desc = "face-down card" if loc == 0x8 else f"face-down monster ({POSITIONS.get(card.get('p'), '?')})"
                parts.append(f"{zone_label(loc, seq)}: {desc}")
            else:
                parts.append(f"{zone_label(loc, seq)}: {self.card_line(card)}")
        return " | ".join(parts) if parts else "none"

    def _pile(self, cards, hidden_label=None):
        known = [f'"{self.db.name(c["id"])}"' for c in cards if c and c.get("id")]
        unknown = sum(1 for c in cards if c and not c.get("id"))
        if not cards:
            return "none"
        text = ", ".join(known)
        if unknown:
            text += (", " if text else "") + f"{unknown} {hidden_label or 'unknown'}"
        return f"({len(cards)}) {text}"

    def state(self, s):
        me, opp = s["me"], s["opp"]
        turn_owner = "YOUR" if s["turn_player"] == 0 else "OPPONENT'S"
        lines = [
            f"TURN {s['turn']} — {turn_owner} turn — {PHASES.get(s['phase'], s['phase'])}",
            f"LP: you {me['lp']} | opponent {opp['lp']}",
            "",
            f"YOUR HAND {self._pile(me['hand'])}",
            f"YOUR MONSTERS: {self._zones(me['mz'], 0x4)}",
            f"YOUR SPELLS/TRAPS: {self._zones(me['sz'], 0x8)}",
            f"YOUR GY {self._pile(me['gy'])}",
            f"YOUR BANISHED {self._pile(me['ban'], 'face-down')}",
            f"YOUR DECK: {me['deck']} cards | YOUR EXTRA DECK {self._pile(me['extra'])}",
            "",
            f"OPPONENT HAND: {len(opp['hand'])} card(s)"
            + (f" (known: {', '.join(repr(self.db.name(c['id'])) for c in opp['hand'] if c and c.get('id'))})"
               if any(c and c.get("id") for c in opp["hand"]) else ""),
            f"OPPONENT MONSTERS: {self._zones(opp['mz'], 0x4)}",
            f"OPPONENT SPELLS/TRAPS: {self._zones(opp['sz'], 0x8)}",
            f"OPPONENT GY {self._pile(opp['gy'])}",
            f"OPPONENT BANISHED {self._pile(opp['ban'], 'face-down')}",
            f"OPPONENT DECK: {opp['deck']} cards | OPPONENT EXTRA DECK: {len(opp['extra'])} card(s)"
            + (f" (face-up: {', '.join(repr(self.db.name(c['id'])) for c in opp['extra'] if c and c.get('id'))})"
               if any(c and c.get("id") for c in opp["extra"]) else ""),
        ]
        if s.get("chain"):
            lines.append("")
            lines.append("CURRENT CHAIN (resolves last-to-first):")
            for i, link in enumerate(s["chain"], 1):
                who = "you" if link["player"] == 0 else "opponent"
                effect = self.db.desc(link.get("desc"))
                lines.append(f"  CL{i}: {who} activated {self.name(link.get('card')) if link.get('card') else self.db.name(link['id'])}"
                             + (f" — {effect}" if effect else ""))
            if s.get("chain_targets"):
                lines.append("  Targets: " + ", ".join(self.card_line(self.on_field(s, c), True)
                                                       for c in s["chain_targets"] if c))
        return "\n".join(lines)

    @staticmethod
    def on_field(s, ref):
        """The state's full card for a short card object (a chain target), if it's on the field there; else `ref`."""
        side = s.get("me" if ref.get("c") == 0 else "opp") or {}
        cards = side.get({0x4: "mz", 0x8: "sz"}.get(ref.get("l"))) or []
        seq = ref.get("s", -1)
        if 0 <= seq < len(cards) and cards[seq] and cards[seq].get("id") == ref.get("id"):
            return cards[seq]
        return ref

    def ids_in_state(self, s):
        ids = set()
        for side in ("me", "opp"):
            f = s[side]
            for key in ("hand", "mz", "sz", "gy", "ban", "extra"):
                for c in f[key]:
                    if c and c.get("id"):
                        ids.add(c["id"])
                        ids.update(c.get("ov", []))
        for link in s.get("chain", []):
            if link.get("id"):
                ids.add(link["id"])
        return ids

    # ---- options ----

    def effect_text(self, desc, card_id=None):
        text = self.db.desc(desc)
        if text and "%ls" in text and card_id:
            text = text.replace("%ls", self.db.name(card_id))  # e.g. 'Use the effect of "%ls" to avoid destruction'
        return f' — effect: "{text}"' if text else ""

    def label_note(self, desc, card):
        """A factual qualifier for an effect label that the card's script makes ambiguous, else "". The label (a
        card string the script's SetDescription picked) can be shared by several of the card's effects, or plainly
        not fit where the card is ("Special Summon this card" for one already in the Monster Zone, as on Blackwing -
        Vata's on-field effect). Then say so, and name the zone the effect works from when the script's SetRange
        tells which effect it is. Clones of one effect (the same effect for another event or zone) don't count."""
        code, loc = (card or {}).get("id"), (card or {}).get("l", 0)
        text = self.db.desc(desc) if desc and desc >= (1 << 20) else None
        if not text or not code or desc >> 20 != code:
            return ""
        effects = self.db.scripts.labelled(code, (code, desc & 0xFFFFF))
        families = {e.family for e in effects}
        misfit = loc == 0x4 and "special summon this card" in text.lower()
        if len(families) < 2 and not misfit:
            return ""
        here = [e for e in effects if e.range is None or (loc and e.range & loc)]
        zone = loc_name(loc) if loc and len({e.family for e in here}) == 1 and all(e.range for e in here) else None
        if len(families) > 1:
            note = f"this label is shared by {len(families)} of this card's effects" + (
                f"; this one works from the {zone}" if zone else "")
        elif zone:
            note = f"the script's label for its {zone} effect, though this card is already on the field"
        else:
            note = "the script's label, though this card is already on the field"
        return f" ({note}; see the card text)"

    def option_line(self, kind, opt):
        if kind in ("idle", "battle", "chain"):
            a = opt["a"]
            card = opt.get("card")
            if a == "activate":
                desc = opt.get("desc")
                return (f"Activate {self.card_line(card)} from {self.where(card)}"
                        f"{self.effect_text(desc, (card or {}).get('id'))}{self.label_note(desc, card)}")
            if a == "summon":
                return f"Normal Summon {self.name(card)} (from hand)"
            if a == "spsummon":
                return f"Special Summon {self.name(card)} from {self.where(card)} {OWN_PROCEDURE}"
            if a == "set_monster":
                return f"Set {self.name(card)} face-down in Defense Position (counts as your Normal Summon)"
            if a == "set_spell":
                return f"Set {self.name(card)} in your Spell/Trap Zone"
            if a == "reposition":
                return f"Change the battle position of {self.card_line(card)}"
            if a == "attack":
                return f"Attack with {self.card_line(card)}" + (" (can attack directly)" if opt.get("direct") else "")
            if a == "to_battle":
                return "Go to the Battle Phase"
            if a == "to_main2":
                return "End the Battle Phase (go to Main Phase 2)"
            if a == "to_end":
                return "End your turn (go to the End Phase)"
            return str(opt)
        if kind in ("select_card", "tribute", "select_unselect"):
            return f"{self.card_line(opt)} — {self.where(opt)}"
        if kind == "select_sum":
            values = f"counts as {opt['v1']}" + (f" or {opt['v2']}" if opt.get("v2") else "")
            return f"{self.card_line(opt)} — {self.where(opt)} ({values})"
        if kind == "option":
            return self.db.desc(opt) or f"option {opt}"
        if kind == "position":
            return POSITIONS.get(opt, str(opt))
        if kind == "announce_card":
            return self.db.name(opt)
        if kind == "announce_attrib":
            return ATTRIBUTE_FLAGS.get(opt, str(opt))
        if kind == "announce_race":
            from .carddb import RACES
            bit = opt.bit_length() - 1
            return RACES[bit] if 0 <= bit < len(RACES) else str(opt)
        return str(opt)

    def options(self, d):
        lines = [self.option_line(d["kind"], o) for o in d.get("options", [])]
        if d["kind"] == "idle":
            self._number_repeats(d["options"], lines)
            note = self.attack_summary(d) if self.attack_note else None
            if note:
                for i, o in enumerate(d["options"]):
                    if o.get("a") == "to_battle":
                        lines[i] += f" ({note})"
        return lines

    def attack_summary(self, d):
        """Facts about a possible attack, or None. Only in your Main Phase 1 with the Battle Phase open to you, when
        you have face-up Attack Position monsters that can attack, and the opponent controls no monster or their
        total ATK reaches the opponent's LP. Their total ATK, the opponent's LP and monster count, no advice. Monsters
        a card stops from attacking (attack_locks) are left out of the total, and named."""
        s = d.get("state") or {}
        if s.get("turn_player") != 0 or s.get("phase") != 0x4 or not any(
                o.get("a") == "to_battle" for o in d.get("options", [])):
            return None
        me, opp = s.get("me") or {}, s.get("opp") or {}
        ready = [c for c in me.get("mz") or [] if c and c.get("id") and c.get("p") == 0x1 and not c.get("att")]
        locks = self.attack_locks(s)
        attackers = [c for c in ready if c.get("s") not in locks]
        total = sum(c.get("atk") or 0 for c in attackers)
        theirs = sum(1 for c in opp.get("mz") or [] if c)
        lp = opp.get("lp")
        if total <= 0 or (theirs and (lp is None or total < lp)):
            return None
        held = "; ".join(f"{self.name(locks[c['s']])} stops {self.name(c)} from attacking"
                         for c in ready if c.get("s") in locks)
        return (f"attack available: your Attack Position monsters total {total} ATK" + (f" ({held})" if held else "")
                + f"; opponent LP {lp}; opponent has "
                + ("no monsters" if not theirs else f"{theirs} monster{'s' if theirs > 1 else ''}"))

    def attack_locks(self, s):
        """{zone: the card} for your monsters that a face-up Spell/Trap stops from attacking, by its script
        (EFFECT_CANNOT_ATTACK). An Equip Card names its monster (`eq`). A card that holds a monster by targeting it,
        like Fiendish Chain, isn't linked to it in the decision; such a card that also negates the monster holds a
        negated one, so while one is face-up every negated monster of yours counts as held. (`att` can't tell: in
        Main Phase 1 it is never set.)"""
        locks, holders = {}, []
        for side in ("me", "opp"):
            for c in (s.get(side) or {}).get("sz") or []:
                if not c or not c.get("id") or c.get("p", 0) & 0xA or c.get("dis"):
                    continue
                codes = self.db.scripts.codes(c["id"])
                if not codes & CANNOT_ATTACK:
                    continue
                eq = c.get("eq")
                if eq:
                    if eq.get("c") == 0 and eq.get("l") == 0x4:
                        locks[eq.get("s")] = c
                elif "EFFECT_DISABLE" in codes:
                    holders.append(c)
        if holders:
            for c in (s.get("me") or {}).get("mz") or []:
                if c and c.get("dis") and c.get("s") not in locks:
                    locks[c.get("s")] = holders[0]
        return locks

    @staticmethod
    def _number_repeats(options, lines):
        """The engine lists a card once per copy and summoning procedure (e.g. an Xyz Monster with an alternative
        procedure), and those entries would read the same: number them, and say they're interchangeable."""
        groups = {}
        for i, o in enumerate(options):
            card = o.get("card") or {}
            if o.get("a") == "spsummon":
                groups.setdefault((card.get("id"), card.get("c"), card.get("l"), card.get("s")), []).append(i)
        for entries in groups.values():
            if len(entries) < 2:
                continue
            for n, i in enumerate(entries, 1):
                lines[i] = lines[i].replace(OWN_PROCEDURE, f"(by its own summoning procedure; entry {n} of "
                                            f"{len(entries)} for this card, which the engine lists once per copy "
                                            "and procedure: the entries are equivalent)")

    def hint(self, d):
        text = self.db.desc(d.get("hint", 0))
        return text or "Select card(s)"

    def question(self, d):
        """The decision prompt: what is being asked and how to answer."""
        kind = d["kind"]
        if kind == "idle":
            return "Main Phase: choose your next action. Reply with exactly one option index."
        if kind == "battle":
            return "Battle Phase: choose your next action. Reply with exactly one option index."
        if kind == "chain":
            q = "Response window: you may activate one of these cards/effects now"
            if d.get("forced"):
                return q + " (an activation is mandatory here). Reply with exactly one option index."
            return q + ". Reply with [] to pass (do nothing), or one option index to activate."
        if kind == "effect_yn":
            return (f"Do you want to activate/use {self.card_line(d['card'])} ({self.where(d['card'])})"
                    f"{self.effect_text(d.get('desc'), d['card'].get('id'))}{self.label_note(d.get('desc'), d['card'])}"
                    "? Reply [1] for yes or [0] for no.")
        if kind == "yesno":
            text = self.db.desc(d.get("desc")) or f"question #{d.get('desc')}"
            return f'Yes/no question from the game: "{text}". Reply [1] for yes or [0] for no.'
        if kind in ("select_card", "tribute"):
            cancel = " You may reply [] to cancel." if d.get("cancelable") or d.get("min") == 0 else ""
            extra = ""
            if d.get("hint") == HINT_ATTACK_TARGET:
                extra = " (this picks the target of the attack you just declared)"
            return (f'The game asks: "{self.hint(d)}"{extra}. Choose between {d["min"]} and {d["max"]} card(s); '
                    f"reply with the list of option indices.{cancel}")
        if kind == "select_unselect":
            # The engine's min/max are sometimes per step (Synchro Materials are asked one step at a time, with the
            # earlier picks shown as already selected) and sometimes for the whole selection, so don't add them up.
            already = ", ".join(self.card_line(c) for c in d.get("selected", [])) or "none"
            if d.get("finishable"):
                stop = " The selection is already valid: reply [] to finish here."
            elif d.get("cancelable"):
                stop = " Replying [] cancels the whole action."
            else:
                stop = " You must pick at least one card."
            return (f'The game asks: "{self.hint(d)}" (cards are picked one at a time; engine limits for this step: '
                    f'{d["min"]}-{d["max"]}). Already picked: {already}. Reply with the indices of the card(s) you want '
                    f"from THIS list, in order.{stop}")
        if kind == "select_sum":
            rule = "exactly" if d.get("exact") else "at least"
            return (f'The game asks: "{self.hint(d)}". Choose cards whose values add up to {rule} {d["sum"]} '
                    f"(between {d['min']} and {d['max']} cards). Reply with the list of option indices.")
        if kind == "go_first":
            return "You won the coin toss/RPS: go first? Reply [1] to go first or [0] to go second."
        if kind == "option":
            return "Choose one of these effects/options. Reply with exactly one option index."
        if kind == "position":
            return f"Choose the battle position for {self.db.name(d.get('card_id'))}. Reply with exactly one option index."
        if kind == "announce_card":
            return "Declare a card name. Reply with exactly one option index."
        if kind == "announce_number":
            return "Declare a number. Reply with exactly one option index."
        if kind in ("announce_attrib", "announce_race"):
            what = "Attribute" if kind == "announce_attrib" else "Type"
            return f"Declare {d.get('count', 1)} {what}(s). Reply with exactly {d.get('count', 1)} option indices."
        return f"Decision of kind {kind}. Reply with option indices."

    def ids_in_decision(self, d):
        ids = set()
        for o in d.get("options", []):
            if isinstance(o, dict):
                c = o.get("card", o)
                if c and c.get("id"):
                    ids.add(c["id"])
        if d.get("card") and d["card"].get("id"):
            ids.add(d["card"]["id"])
        if d.get("card_id"):
            ids.add(d["card_id"])
        for desc in [d.get("desc"), d.get("hint")] + [o.get("desc") for o in d.get("options", []) if isinstance(o, dict)]:
            if desc and desc >= (1 << 20):
                ids.add(desc >> 20)
        return ids

    # ---- events ----

    def lines(self, ev):
        """The duel-log lines for one event, for a history the model reads. Like event(), except that the line of a
        Summon in its negation window waits for the next event: if that is the Summon succeeding, the two read as one
        line ("Opponent Special Summons ..."); if not (a response, a negation), the in-progress line comes first.
        Call flush(decision) before showing the history, so a held line is never lost."""
        out = []
        if self.held is not None:
            held, line = self.held
            self.held = None
            if ev["e"] == "summoned" and self._spot(ev) == self._spot(held):
                self.event(ev)
                return [self._summon_text(held)]
            out.append(line)
        unknown = ev["e"] == "summoning" and "window" not in ev and not self.chain_open
        line = self.event(ev)
        if ev["e"] == "summoning" and (self._spot(ev) in self.summons or unknown):
            self.held = (ev, line)
        elif line:
            out.append(line)
        return out

    def flush(self, decision=None):
        """The line lines() holds back, if any, before `decision` is shown. A log without `window` (older bots) never
        says when a Summon completed: one still held at a response window ("chain") is most likely in its negation
        window, so it reads as in progress there; anywhere else it reads as done, as it always did."""
        if self.held is None:
            return []
        (held, line), self.held = self.held, None
        if "window" not in held and (decision or {}).get("kind") == "chain":
            line = self._summon_text(held, pending=True)
        return [line]

    @staticmethod
    def _spot(ev):
        to = ev.get("to") or {}
        return to.get("c"), to.get("s")

    def _summon_kind(self, ev):
        if ev.get("special"):
            return "Special Summon"
        if ev.get("flip"):
            return "Flip Summon"
        # Bots that report negation windows also mark Flip Summons; older logs don't tell the two apart.
        return "Normal Summon" if "window" in ev else "Normal/Flip Summon"

    def _summon_text(self, ev, pending=False):
        to = ev["to"]
        mine = to["c"] == 0
        what, card = self._summon_kind(ev), f'"{self.db.name(ev["id"])}"'
        zone, pos = zone_label(to["l"], to["s"]), POSITIONS.get(to["p"], "?")
        if pending:
            return (f"{'You are' if mine else 'Opponent is'} {what}ing {card} to {zone}, {pos} (not complete yet: it "
                    "can still be negated).")
        return f"{'You' if mine else 'Opponent'} {what}{'' if mine else 's'} {card} to {zone} ({pos})."

    def _summoning(self, ev):
        """A Summon starts. Outside a chain it has a negation window (Solemn Strike and the like): the core asks for
        responses and only then completes it. Bots that report this mark the event with `window` and send `summoned`
        when it completes (docs/decision-protocol.md); a Summon that a resolving effect performs has no window.
        Without `window` (older logs) nothing says when it completed, so it reads as done (flush() has the one
        exception)."""
        if not ev.get("window"):
            return self._summon_text(ev)
        self.summons[self._spot(ev)] = ev
        return self._summon_text(ev, pending=True)

    def _summoned(self, ev):
        """A Summon completed: worth a line only after a window that showed it in progress."""
        pending = self.summons.pop(self._spot(ev), None)
        if pending is None:
            return None
        who = "Your" if pending["to"]["c"] == 0 else "Opponent's"
        return f'{who} {self._summon_kind(pending)} of "{self.db.name(pending["id"])}" succeeded.'

    def event(self, ev):
        """One line for the duel log, or None for noise."""
        e = ev["e"]
        db = self.db
        if e in ("start", "new_turn", "new_phase"):
            self.chain_open, self.summons = False, {}
        if e == "start":
            return f"DUEL START — you go {'first' if ev['first'] else 'second'}. LP {ev['lp'][0]} vs {ev['lp'][1]}."
        if e == "new_turn":
            return f"=== TURN {ev['turn']} ({'your' if ev['player'] == 0 else 'opponent'}'s turn) ===".replace("your's", "your")
        if e == "new_phase":
            return f"-- {PHASES.get(ev['phase'], ev['phase'])}"
        if e == "draw":
            return f"{'You draw' if ev['player'] == 0 else 'Opponent draws'} {ev['count']} card(s)."
        if e == "move":
            return self._move(ev)
        if e == "summoning":
            return self._summoning(ev)
        if e == "summoned":
            return self._summoned(ev)
        if e == "chaining":
            self.chain_open = True
            who = "You" if ev["player"] == 0 else "Opponent"
            card = ev.get("card") or {}
            return (f"CL{ev['link']}: {who} activate{'s' if who == 'Opponent' else ''} \"{db.name(ev['id'])}\""
                    f" from {self.where(card) if card else '?'}{self.effect_text(ev.get('desc'), ev.get('id'))}"
                    f"{self.label_note(ev.get('desc'), dict(card, id=ev.get('id')))}")
        if e == "chain_solved":
            return f"   CL{ev['link']} resolved."
        if e in ("chain_negated", "chain_disabled"):
            return f"   CL{ev['link']} was NEGATED."
        if e == "chain_end":
            self.chain_open = False
            return None
        if e == "attack":
            target = ev.get("target")
            att = self.card_line(ev["attacker"], True)
            return f"ATTACK: {att} attacks " + (self.card_line(target, True) if target else "directly") + "."
        if e == "damage":
            return f"{'You take' if ev['player'] == 0 else 'Opponent takes'} {ev['amount']} damage (LP now {ev['lp']})."
        if e == "pay_lp":
            return f"{'You pay' if ev['player'] == 0 else 'Opponent pays'} {ev['amount']} LP (LP now {ev['lp']})."
        if e == "recover":
            return f"{'You gain' if ev['player'] == 0 else 'Opponent gains'} {ev['amount']} LP (LP now {ev['lp']})."
        if e == "lp":
            return f"{'Your' if ev['player'] == 0 else 'Opponent'}'s LP set to {ev['lp']}.".replace("Your's", "Your")
        if e == "pos_change":
            if not ev.get("id"):
                return None
            card = f"{whose(ev['c']).capitalize()} \"{db.name(ev['id'])}\""
            if ev["to"] in POSITIONS:
                return f"{card} changes to {POSITIONS[ev['to']]}."
            # A Spell/Trap (or a card without a battle position) only turns face-up or face-down.
            return f"{card} is flipped {'face-up' if ev['to'] & 0x5 else 'face-down'}."
        if e == "targeted":
            return f"   {self.card_line(ev['card'], True)} is targeted."
        if e == "win":
            outcome = {0: "YOU WIN", 1: "YOU LOSE", 2: "DRAW"}.get(ev["result"], "GAME OVER")
            reason = db.victory.get(ev.get("reason"), "")
            return f"*** {outcome} *** {reason}".strip()
        if e == "retry":
            return "!!! The game engine rejected the last response."
        return self._native_event(ev)

    def _native_event(self, ev):
        """Events only the native arena seats send (docs/decision-protocol.md, "Native seats")."""
        e, db = ev["e"], self.db
        you = ev.get("player") == 0
        if e == "confirm":
            cards = ", ".join(f"{self.name(c)} ({self.where(c)})" for c in ev.get("cards", []))
            return f"Revealed to {'you' if you else 'the opponent'}: {cards}." if cards else None
        if e == "equip":
            return f"{self.card_line(ev['card'], True)} is equipped to {self.card_line(ev['target'], True)}."
        if e == "swap":
            a, b = (ev.get("cards") or [None, None])[:2]
            return f"Control swap: {self.name(a)} is now in {self.where(a)}, {self.name(b)} in {self.where(b)}."
        if e == "counter":
            name = db.counters.get(ev["type"], f"counter {ev['type']:#x}")
            how = "placed on" if ev.get("add") else "removed from"
            return f"{ev['count']} {name}(s) {how} {self.card_line(ev['card'], True)}."
        if e in ("coin", "dice"):
            results = ev.get("results") or []
            shown = ", ".join(("heads" if r else "tails") if e == "coin" else str(r) for r in results)
            verb = {("coin", True): "You toss a coin", ("coin", False): "Opponent tosses a coin",
                    ("dice", True): "You roll a die", ("dice", False): "Opponent rolls a die"}[(e, you)]
            return f"{verb}: {shown}."
        if e == "declared":
            who = "You" if you else "Opponent"
            kind, value = ev.get("kind"), ev.get("value", 0)
            if kind == "card":
                return f'{who} declared "{db.name(value)}".'
            if kind == "attribute":
                return f"{who} declared {' and '.join(n for b, n in ATTRIBUTE_FLAGS.items() if value & b)}."
            if kind == "race":
                from .carddb import RACES
                return f"{who} declared {' and '.join(RACES[i] for i in range(len(RACES)) if value >> i & 1)}."
            if kind == "number":
                return f"{who} declared the number {value}."
            text = db.desc(value)
            return f'{who} chose: "{text}".' if text else None
        return None

    def _move(self, ev):
        f, t, reason = ev["from"], ev["to"], ev.get("reason", 0)
        fl, tl = f["l"], t["l"]
        if fl == tl and f["c"] == t["c"] and (fl & 0x7F) in (0x1, 0x2, 0x40):
            return None  # reordering inside a hidden pile
        if fl == 0x1 and tl == 0x2 and reason & 0x2000000:
            return None  # draws are reported separately
        name = f'"{self.db.name(ev["id"])}"' if ev.get("id") else "a hidden card"
        why = [w for bit, w in REASONS if reason & bit]
        src = f"{whose(f['c'])} {zone_label(fl, f['s']) if fl in (0x4, 0x8) else loc_name(fl)}" if fl else "outside the game"
        dst = f"{whose(t['c'])} {zone_label(tl, t['s']) if tl in (0x4, 0x8) else loc_name(tl)}" if tl else "removed from play"
        line = f"{name}: {src} → {dst}" + (f" ({', '.join(why)})" if why else "")
        if fl == 0x4 and self.summons.pop((f["c"], f["s"]), None) is not None:
            line += " — its Summon was negated."  # it left the field inside its window: no `summoned` will come
        return line
