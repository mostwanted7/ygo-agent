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
    def __init__(self, db):
        self.db = db

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
        """Battle stats and status for a monster on the field."""
        if not card or not card.get("id") or card.get("l") != 0x4:
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
                lines.append("  Targets: " + ", ".join(self.card_line(c, True) for c in s["chain_targets"] if c))
        return "\n".join(lines)

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

    def effect_text(self, desc):
        text = self.db.desc(desc)
        return f' — effect: "{text}"' if text else ""

    def option_line(self, kind, opt):
        if kind in ("idle", "battle", "chain"):
            a = opt["a"]
            card = opt.get("card")
            if a == "activate":
                return f"Activate {self.card_line(card)} from {self.where(card)}{self.effect_text(opt.get('desc'))}"
            if a == "summon":
                return f"Normal Summon {self.name(card)} (from hand)"
            if a == "spsummon":
                return f"Special Summon {self.name(card)} from {self.where(card)} (by its own summoning procedure)"
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
        return [self.option_line(d["kind"], o) for o in d.get("options", [])]

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
                    f"{self.effect_text(d.get('desc'))}? Reply [1] for yes or [0] for no.")
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

    def event(self, ev):
        """One line for the duel log, or None for noise."""
        e = ev["e"]
        db = self.db
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
            to = ev["to"]
            mine = to["c"] == 0
            how = ("Special Summon" if ev.get("special") else "Normal/Flip Summon") + ("" if mine else "s")
            who = "You" if mine else "Opponent"
            return f"{who} {how} \"{db.name(ev['id'])}\" to {zone_label(to['l'], to['s'])} ({POSITIONS.get(to['p'], '?')})."
        if e == "chaining":
            who = "You" if ev["player"] == 0 else "Opponent"
            card = ev.get("card") or {}
            return (f"CL{ev['link']}: {who} activate{'s' if who == 'Opponent' else ''} \"{db.name(ev['id'])}\""
                    f" from {self.where(card) if card else '?'}{self.effect_text(ev.get('desc'))}")
        if e == "chain_solved":
            return f"   CL{ev['link']} resolved."
        if e in ("chain_negated", "chain_disabled"):
            return f"   CL{ev['link']} was NEGATED."
        if e == "chain_end":
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
        return f"{name}: {src} → {dst}" + (f" ({', '.join(why)})" if why else "")
