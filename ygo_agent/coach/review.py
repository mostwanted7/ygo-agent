"""The review after a coach game (review.md in the game's folder): one LLM pass over the game log, the moments the
human did something else than the coach advised, and the deck's playbook.

    path, markdown = write_review("games/<dir>", cfg, db, backend_profile)     # also `ygo-agent coach --review DIR`

Everything comes from the game folder (game.jsonl, meta.json, feedback.md), so a finished game can be reviewed again
later with another backend or after the playbook changed.
"""

import json
import os
import time

from .. import backends
from ..agent import prompts
from ..agent.brain import event_ids
from ..agent.describe import Describer
from ..agent.gamelog import same_pick

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "array", "items": {"type": "integer"}, "description": "Always []."},
        "why": {"type": "string", "description": "The whole review, in Markdown, with the sections asked for."},
    },
    "required": ["choice", "why"],
}
SELECTS = ("select_card", "tribute", "select_sum", "select_unselect", "position", "option", "effect_yn", "yesno",
           "announce_card", "announce_number", "announce_attrib", "announce_race", "chain")
KEY_KINDS = ("idle", "battle", "chain", "effect_yn")
MAX_DIVERGENCES = 18
RESULT_WORDS = {"win": "won", "loss": "lost", "draw": "drew"}

SYSTEM = """You are an expert Yu-Gi-Oh! coach. A human who is learning {deck} played a duel under {rules} in EDOPro;
their opponent was {opponent}. You coached them live: at most decisions you recommended a move, and they made every
move themselves. Now you write their review of the game.{rules_line}

# General strategy
{general}

# The deck they play: {deck}
{decklist}

## Card texts
{card_texts}

# Playbook (what they are learning)
{playbook}
"""

ASK = """Write the review of this game for the human, addressing them as "you".
{level}

{facts}

DUEL LOG: the events from your side of the table, and at each decision what you (the human) did and what the coach
advised (✓ followed, ✗ did something else; "no advice" = they answered before the coach could).
{log}

DECISIONS WHERE YOU DID SOMETHING ELSE THAN THE COACH ADVISED, with the state at that moment:
{divergences}
{opponent_cards}{notes}
Write the review in Markdown with exactly these sections:

## Summary
2-4 sentences: how the game went and what decided it.

## Key moments
The 3-6 moments that mattered most, the most costly first. For each, a heading "### Turn T, decision #N: <what
happened>" and then:
- **You:** what they did.
- **Better:** the better play: the exact cards and the line.
- **Why:** the concrete reason: what the cards do, the board and LP it leads to, what the opponent could do about it.
- **Playbook:** the playbook rule it is about (quote it briefly), or "No rule yet:" and the rule worth adding.
A moment can be one where the coach was wrong and the human right: say so. Decisions where they followed good advice
don't belong here. When the same mistake happens more than once, report it at its FIRST occurrence and list the later
decisions that repeat it.

Judge every decision only by what the human could know at that moment: their hand, the public board, the cards
revealed so far. Never use information revealed later (what a face-down card turned out to be, the opponent's hand)
or how things worked out. A risky play that happened to work is still risky, and safe advice that was not followed
was still right. Yu-Gi-Oh is a game of incomplete information and several lines are often equally good: call a play a
mistake only if it was clearly worse with what was known, and leave out choices that were reasonable alternatives
(you can mention one briefly under "What you did well" if the reasoning was sound).

## What you did well
2-4 bullets, each tied to a specific decision of this game.

## Practise next
2-3 concrete things to practise in the next games, each tied to this deck's cards.

Be specific and correct about the cards: every effect you mention must match its card text above, restrictions
included (Attribute, Type, Level, once per turn, what a card can summon or search). Keep to the basic rules: a
monster can attack the turn it is summoned, however it was summoned (no one attacks on the duel's first turn); a
Ritual Monster can't be Normal Summoned or Set. Don't invent effects or rulings, and say so when the log doesn't show
something. The coach's live
advice can be wrong too: check it against the texts before you endorse it. No generic advice that isn't tied to a
moment of this game. Keep the whole review under about 900 words. Put it in "why" and reply with choice []."""

LEVELS = {"beginner": "They are new to the deck: explain each point so that the idea behind it is clear.",
          "intermediate": "They know the basics of the deck: be brief and technical."}


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def read_meta(game_dir):
    try:
        with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def picked(options, choice):
    if choice is None:
        return "?"
    if options:
        text = ", ".join(options[k] for k in choice if 0 <= k < len(options))
    else:
        text = {(1,): "yes", (0,): "no"}.get(tuple(choice), str(choice))
    return text or "pass / none"


def digest(game_dir, db, profile=None):
    """The game as the reviewer reads it: the log text, the divergences (with their states), the stats."""
    words = Describer(db)
    rows = read_jsonl(os.path.join(game_dir, "game.jsonl"))
    decisions, advice, replies = {}, {}, {}
    for r in rows:
        m = r.get("msg") or {}
        if r.get("kind") == "decide":
            decisions[m.get("id")] = m
        elif r.get("kind") == "advice":
            advice[m.get("id")] = m
        elif r.get("kind") == "reply":
            replies[m.get("id")] = m
    lines, divergences, seen_ids = [], [], set()
    stats = {"advised": 0, "followed": 0, "diverged": 0, "late": 0, "no_advice": 0, "turns": 0, "result": None}
    own = set(profile.ids) if profile is not None else set()
    for r in rows:
        kind, m = r.get("kind"), r.get("msg") or {}
        if kind == "event":
            if m.get("e") == "room":
                continue
            seen_ids |= event_ids(m)
            if m.get("e") == "new_turn":
                stats["turns"] = max(stats["turns"], m.get("turn") or 0)
            if m.get("e") == "win":
                stats["result"] = {0: "win", 1: "loss"}.get(m.get("result"), "draw")
            try:
                text = words.event(m)
            except (KeyError, TypeError, ValueError):
                text = None
            if text:
                lines.append(text if text.startswith("===") else "- " + text)
        elif kind == "reply" and m.get("source") == "human":
            d = decisions.get(m.get("id"))
            if not d or d.get("kind") in ("place", "game_over"):
                continue
            a = advice.get(d["id"]) or {}
            line = decision_line(words, d, m, a)
            if line:
                lines.append(line)
            if a.get("choice") is not None and a.get("source") == "backend":
                stats["advised"] += 1
                stats["late"] += bool(a.get("late"))
                if same_pick(m.get("choice"), a["choice"], d.get("kind")):
                    stats["followed"] += 1
                else:
                    stats["diverged"] += 1
                    divergences.append((d, m, a))
            elif a.get("source") in ("skipped", None) and d.get("kind") in KEY_KINDS:
                stats["no_advice"] += 1
    if len(divergences) > MAX_DIVERGENCES:  # the key decisions first, then the rest in game order
        key = [x for x in divergences if x[0]["kind"] in KEY_KINDS]
        rest = [x for x in divergences if x[0]["kind"] not in KEY_KINDS]
        keep = {id(x) for x in (key + rest)[:MAX_DIVERGENCES]}
        divergences = [x for x in divergences if id(x) in keep]
    blocks = [divergence_block(words, d, m, a) for d, m, a in divergences]
    opponent_ids = sorted(i for i in seen_ids - own if db.get(i))
    return {"log": "\n".join(lines), "divergences": "\n\n".join(blocks) or "(none)", "blocks": blocks,
            "stats": stats, "opponent_ids": opponent_ids, "count": len(divergences)}


def decision_line(words, d, reply, a):
    kind = d.get("kind")
    options = words.options(d)
    you = picked(options, reply.get("choice"))
    turn = (d.get("state") or {}).get("turn")
    head = f"#{d['id']} (turn {turn}, {kind})"
    if a.get("choice") is not None and a.get("source") == "backend":
        if same_pick(reply.get("choice"), a["choice"], kind):
            return f"{head} you: {you} ✓ as the coach advised" + (f" — coach: {a['why']}" if a.get("why") else "")
        when = " (late)" if a.get("late") and not a.get("hindsight") else (" (looking back)" if a.get("hindsight") else "")
        return f"{head} you: {you} ✗ the coach advised{when}: {picked(options, a['choice'])} — {a.get('why') or ''}"
    if a.get("source", "").startswith("rule") and a.get("choice") is not None:
        mark = "✓" if same_pick(reply.get("choice"), a["choice"], kind) else "✗"
        return f"{head} you: {you} {mark} deck rule: {picked(options, a['choice'])} ({a.get('why')})"
    if kind in KEY_KINDS and a.get("source") not in ("auto",):
        return f"{head} you: {you} (no advice)"
    if kind in SELECTS:
        return f"{head} you: {you}"
    return None


def divergence_block(words, d, reply, a):
    options = words.options(d)
    shown = options if len(options) <= 25 else [t if i in (reply.get("choice") or []) + a["choice"] else "" for i, t
                                                in enumerate(options)]
    opts = "\n".join(f"  [{i}] {t}" for i, t in enumerate(shown) if t)
    return (f"### #{d['id']} (turn {(d.get('state') or {}).get('turn')}) {words.question(d).split(' Reply')[0]}\n"
            f"{words.state(d['state'])}\nOptions:\n{opts}\n"
            f"You chose: {picked(options, reply.get('choice'))}\n"
            f"The coach advised{' (after you had answered)' if a.get('late') else ''}: {picked(options, a['choice'])}"
            f" — {a.get('why') or ''}")


def system_prompt(profile, meta):
    rules = prompts.ruleset(meta.get("rules") or "MR3")
    detail = f" The rules: {rules[0]}: {rules[1]}." if rules[1] else ""
    return SYSTEM.format(deck=profile.name, rules=rules[0], opponent=prompts.opponent_text(meta.get("opponent_info")),
                         rules_line=detail, general=profile.general_playbook.strip() or "(none)",
                         decklist=profile.decklist(), card_texts=profile.card_texts("full"),
                         playbook=profile.playbook)


def review_text(game_dir, db, profile, meta, level=None):
    """The user message of the review ask, and the digest it was made from."""
    dig = digest(game_dir, db, profile)
    s = dig["stats"]
    result = s["result"] or meta.get("result")
    facts = [f"The game: you {RESULT_WORDS.get(result, 'did not finish')} it"
             + (f" on turn {s['turns']}" if s["turns"] else "")
             + (f" against {meta['opponent']}" if meta.get("opponent") else "") + "."]
    if s["advised"]:
        facts.append(f"The coach advised {s['advised']} decisions live or right after; you followed {s['followed']} "
                     f"and did something else {s['diverged']} times" + (f" ({s['late']} of its pieces of advice came "
                                                                       "after you had already answered)" if s["late"]
                                                                       else "") + ".")
    if s["no_advice"]:
        facts.append(f"{s['no_advice']} key decisions got no advice (you were faster than the coach): judge them from "
                     "the log.")
    opp = ""
    if dig["opponent_ids"]:
        opp = "\nTHE OPPONENT'S CARDS SEEN THIS GAME:\n" + "\n".join("- " + db.full_text(i) for i in dig["opponent_ids"]) \
              + "\n"
    notes = ""
    try:
        with open(os.path.join(game_dir, "feedback.md"), encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            notes = "\nNOTES TYPED DURING THE GAME (by the human or a spectator):\n" + text + "\n"
    except OSError:
        pass
    level = level or (meta.get("coach") or {}).get("level") or "beginner"
    text = ASK.format(level=LEVELS.get(level, LEVELS["beginner"]), facts="\n".join(facts), log=dig["log"],
                      divergences=dig["divergences"], opponent_cards=opp, notes=notes)
    return text, dig


def header(meta, dig, label):
    s = dig["stats"]
    bits = [f"{meta.get('deck_name') or meta.get('deck') or 'Your deck'} vs {meta.get('opponent') or 'the opponent'}"]
    if s["result"] or meta.get("result"):
        bits.append({"win": "won", "loss": "lost", "draw": "draw"}.get(s["result"] or meta.get("result"), ""))
    if s["turns"]:
        bits.append(f"{s['turns']} turns")
    lines = [f"# Coach review: {' · '.join(b for b in bits if b)}", ""]
    stats = []
    if s["advised"]:
        stats.append(f"followed the coach {s['followed']}/{s['advised']} times")
    if s["late"]:
        stats.append(f"{s['late']} advice late")
    stats.append(f"reviewed by {label}, {time.strftime('%Y-%m-%d %H:%M')}")
    lines += [f"*{'; '.join(stats)}. The game log: game.md; the decisions are numbered as there.*", ""]
    return "\n".join(lines)


def plain_review(dig):
    """Without an LLM (heuristic/random backends): the divergences, for a human or a coding agent to go through."""
    out = ["## Summary", "", "No LLM backend wrote this review (the coach backend has no language model). Below are the "
           "decisions where you did something else than the coach advised.", "", "## Key moments", ""]
    if not dig["count"]:
        out.append("(none)")
    for block in dig["blocks"]:
        head, _, rest = block.partition("\n")
        out += [head, "", "```", rest, "```", ""]
    return "\n".join(out)


def write_review(game_dir, cfg, db, backend_profile, profile=None, level=None, timeout=None):
    """Ask the backend for the review and write review.md. Returns (path, markdown, info)."""
    from ..match import load_profile
    meta = read_meta(game_dir)
    if profile is None:
        key = meta.get("deck_ydk") if meta.get("deck_ydk") and os.path.isfile(meta.get("deck_ydk")) else meta.get("deck")
        profile = load_profile(key, db, cfg)
    text, dig = review_text(game_dir, db, profile, meta, level)
    backend = backends.create(backend_profile, db=db)
    info = {}
    if backend.TYPE in ("heuristic", "random"):
        body = plain_review(dig)
    else:
        session = backend.open_session(system_prompt(profile, meta), REVIEW_SCHEMA)
        try:
            limit = float(timeout or cfg.get("coach", {}).get("review_timeout_seconds", 600))
            out, info = session.ask(backends.Request(text, None, REVIEW_SCHEMA, limit))
        finally:
            session.close()
        body = (out or {}).get("why") or ""
        if not body.strip():
            body = plain_review(dig) + f"\n\n*(The review backend gave no answer: {info.get('error') or 'empty'}.)*"
    markdown = header(meta, dig, backend.label) + body.strip() + "\n"
    path = os.path.join(game_dir, "review.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(os.path.join(game_dir, "review-prompt.md"), "w", encoding="utf-8") as f:
        f.write(text)  # what the reviewer saw, for checking its claims
    return path, markdown, info
