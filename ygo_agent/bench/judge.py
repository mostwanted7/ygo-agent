"""The exam's judge: blind labelling of the candidates' answers, the judge's prompt and reply format, the read-only
sandbox it checks rulings in, and the lighter whole-game review (docs/bench.md, "Decision exam").

The judge never sees which model gave an answer: the distinct answers to a position get the labels A, B, C... in a
per-position random order (seeded, so a run can be re-judged and un-blinded exactly), model names are scrubbed from
the reasons, and identical choices share one label, so they get one grade. It runs through the trainer's reviewer
(trainer/llm.py): agentic `claude -p` with only Read/Grep/Glob in a sandbox, or inline for the other backends.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import string

from ..agent.validate import validate

GRADES = ("best", "good", "acceptable", "mistake", "blunder")
SCORE = {"best": 4, "good": 3, "acceptable": 2, "mistake": 1, "blunder": 0}
CONFIDENCE = ("high", "medium", "low")
SEVERITIES = ("blunder", "major", "minor")
MODEL_WORDS = re.compile(r"\b(opus|sonnet|haiku|claude(?:-code)?)\b", re.I)

RULES_TEXT = {
    "MR3": "Master Rule 3: Extra Deck monsters are summoned to the Main Monster Zones (there is no Extra Monster "
           "Zone), the Pendulum Zones are separate from the Spell & Trap Zones, and Link Monsters don't exist.",
}


def _str(desc=None):
    return {"type": "string", **({"description": desc} if desc else {})}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _arr(item):
    return {"type": "array", "items": item}


JUDGE_SCHEMA = _obj(positions=_arr(_obj(
    position=_str("the position id, e.g. p07"),
    assessment=_str("2-4 sentences: what matters in this position and which options are reasonable"),
    own_choice=_arr({"type": "integer"}),
    equivalent=_arr(_str("a label (A, B, ...) whose answer is as good as your own choice")),
    grades=_arr(_obj(label=_str("A, B, ..."), grade={"type": "string", "enum": list(GRADES)},
                     reason=_str("one or two sentences: the concrete reason for the grade"))),
    confidence={"type": "string", "enum": list(CONFIDENCE)},
)))

GAME_SCHEMA = _obj(
    summary=_str("3-5 sentences: how the game went and why it was won or lost"),
    mistakes=_arr(_obj(
        decision={"type": "integer"}, turn={"type": "integer"},
        severity={"type": "string", "enum": list(SEVERITIES)},
        what=_str("what the player did"), better=_str("what it should have done, and why"),
        evidence=_str("a short verbatim quote from the log or a script that shows it"))),
    significant={"type": "integer", "description": "how many of the mistakes are blunders or major"},
)

SYSTEM = """You are an expert Yu-Gi-Oh! player and judge who also knows the EDOPro engine and its Lua card scripts. \
You grade decisions that AI players made in real duels under {rules}

Each position is one decision from a real game, shown exactly as the player saw it: the duel log so far, the current \
state and the numbered legal options (the engine generated them, so every option is legal; "you" is the player). \
Then come two to four answers labelled A, B, C, ...: the option(s) a player chose and the reason it gave. They come \
from different players, in random order.

Grade every answer:
- best: as good as any legal option here (several answers can be best; passing can be best)
- good: sound, slightly worse than the best, or a reasonable alternative a strong player might pick
- acceptable: playable but clearly worse; it costs a little
- mistake: it costs real resources, damage, tempo or a winning chance; a strong player wouldn't do it
- blunder: it likely loses the game, throws away a key card or effect, or rests on a misread of the cards or rules

Grade the move, not the prose: a right move with a muddled reason is still right (say so in the reason), and a \
well-argued wrong move is still wrong. Judge from what the player could know at that moment (its hand, the public \
state, the log), not from luck or what might happen later. Judge each position on its own. When the decision is one \
step of a longer action (a target, a cost, a material), grade the step in the light of the line it serves.

The deck's playbook is the strategy guide the players were told to follow. Treat it as strong guidance from a coach \
who knows the deck, not as law: when a position clearly calls for something else, grade by the position and say so.

{tools}

For every position return: `assessment` first (what matters, which options are reasonable), then `own_choice` (the \
option indices you would pick, in the decision's reply format: [] to pass, [1] yes / [0] no), `equivalent` (the \
labels whose answers are as good as your own choice; empty if none), one entry in `grades` per label, and your \
`confidence`."""

TOOLS_AGENTIC = """You have read-only tools (Read, Grep, Glob) in a working folder: scripts/c<id>.lua is the Lua \
script of every card in these positions (scripts/lib/ has shared helpers such as utility.lua and proc_xyz.lua), and \
cards.md has every card's text. Open a script when a ruling decides a grade (once-per-turn limits, timing, \
targeting, costs, what a card can summon); skip it when the position is clear. You can't write files: your \
structured reply is your whole output."""

TOOLS_INLINE = """The card texts you need are in the message. When a ruling isn't clear from a text, trust what the \
engine offers and say how sure you are."""


GAME_SYSTEM = """You are an expert Yu-Gi-Oh! player and coach who also knows the EDOPro engine and its Lua card \
scripts. You review whole games that an AI player played under {rules} and count its significant mistakes. What is \
true, in order: what the engine did (the log), the card's Lua script, the card text. Never count a mistake you \
haven't checked against the options the log lists at that decision (and the script, when a ruling decides it).

{tools}"""

GAME_TOOLS_AGENTIC = """You have read-only tools (Read, Grep, Glob) in a working folder: games/<id>/game.md (the full \
log: every decision with all its options and the player's reason), games/<id>/condensed.md (the chosen options only), \
scripts/c<id>.lua (the Lua script of every card in the games; scripts/lib/ has shared helpers) and cards.md (every \
card's text). You can't write files: your structured reply is your whole output."""


def _rules_text(rules: str) -> str:
    return RULES_TEXT.get(str(rules).upper(), f"{rules} rules.")


def system(rules: str, agentic: bool) -> str:
    return SYSTEM.format(rules=_rules_text(rules), tools=TOOLS_AGENTIC if agentic else TOOLS_INLINE)


def game_system(rules: str, agentic: bool) -> str:
    return GAME_SYSTEM.format(rules=_rules_text(rules), tools=GAME_TOOLS_AGENTIC if agentic else TOOLS_INLINE)


# ---- blinding ----

def scrub(text: str | None) -> str:
    """A reason with model and product names taken out, so a label can't be traced back to a model."""
    return MODEL_WORDS.sub("the player", (text or "").strip())


def _rng(salt: str, position: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{salt}:{position}".encode()).hexdigest()[:16], 16))


def blind(position: str, answers: dict[str, dict], salt: str, probe: float = 0.0) -> tuple[list[dict], dict]:
    """Label the distinct answers of one position. `answers`: candidate -> {"key", "answer", "why"} (key: the
    canonical choice, see exam.answer_key). Returns (items for the judge [{"label", "answer", "why"}], mapping
    label -> {"key", "candidates", "why_from", "probe_of"}).

    Candidates with the same key share one label (its reason is one of theirs, picked at random). With probability
    `probe`, a position where two candidates gave the same choice with different reasons also shows the second
    reason under its own label (`probe_of` names the real label): it measures whether the judge grades the same move
    the same way twice, and its grade is never scored."""
    rng = _rng(salt, position)
    groups: dict[str, list[str]] = {}
    for cand in sorted(answers):
        groups.setdefault(answers[cand]["key"], []).append(cand)
    entries = []
    for key, members in groups.items():
        source = rng.choice(members)
        entries.append({"key": key, "candidates": members, "why_from": source, "probe_of": None})
    do_probe = rng.random() < probe
    if do_probe:
        shared = [e for e in entries if len({scrub(answers[c]["why"]) for c in e["candidates"]}) > 1]
        if shared:
            e = rng.choice(shared)
            other = rng.choice([c for c in e["candidates"] if scrub(answers[c]["why"]) !=
                                scrub(answers[e["why_from"]]["why"])])
            entries.append({"key": e["key"], "candidates": [], "why_from": other, "probe_of": e})
    rng.shuffle(entries)
    labels = string.ascii_uppercase
    for i, e in enumerate(entries):
        e["label"] = labels[i]
    mapping, items = {}, []
    for e in entries:
        mapping[e["label"]] = {"key": e["key"], "candidates": e["candidates"], "why_from": e["why_from"],
                               "probe_of": e["probe_of"]["label"] if e["probe_of"] else None}
        src = answers[e["why_from"]]
        items.append({"label": e["label"], "answer": src["answer"], "why": scrub(src["why"])})
    return items, mapping


def unblind(mapping: dict, grades: dict[str, dict]) -> dict[str, dict]:
    """candidate -> {"label", "grade", "reason"}: every candidate gets the grade of its answer's label (probe labels
    are never scored)."""
    out = {}
    for label, m in mapping.items():
        if m.get("probe_of"):
            continue
        g = grades.get(label) or {}
        for cand in m["candidates"]:
            out[cand] = {"label": label, "grade": g.get("grade"), "reason": g.get("reason", "")}
    return out


def answers_sha(answers: dict[str, dict]) -> str:
    """Changes when any candidate's answer or reason changes (then the position is judged again)."""
    blob = json.dumps({c: [a["key"], a.get("why") or ""] for c, a in sorted(answers.items())}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---- the judge's prompt and reply ----

def deck_block(deck: dict) -> str:
    """deck: {"name", "decklist", "general", "playbook"}."""
    parts = [f"# Deck: {deck['name']}", f"## Decklist\n{deck['decklist']}"]
    if deck.get("general"):
        parts.append(f"## General strategy (for every deck)\n{deck['general'].strip()}")
    parts.append(f"## Playbook (the coaching notes the players follow)\n{deck['playbook'].strip()}")
    return "\n\n".join(parts)


def position_block(item: dict) -> str:
    """item: {"id", "deck_name", "kind", "text", "card_texts": [str], "answers": [{"label", "answer", "why"}]}."""
    parts = [f"# Position {item['id']} ({item['deck_name']}, a `{item['kind']}` decision)",
             "## What the player saw", "<<<\n" + item["text"].strip() + "\n>>>"]
    if item.get("card_texts"):
        texts = "\n".join(f"- {t}" for t in item["card_texts"])
        parts.append(f"## Texts of the deck's cards in this position\n{texts}")
    lines = []
    for a in item["answers"]:
        lines.append(f"{a['label']}) {a['answer']}\n   reason given: {a['why'] or '(none)'}")
    parts.append("## Answers\n" + "\n".join(lines))
    return "\n\n".join(parts)


def judge_prompt(items: list[dict], decks: dict[str, dict]) -> str:
    """One batch: the decks' context once each, then the positions."""
    used = list(dict.fromkeys(i["deck"] for i in items))
    head = (f"# Task: grade the answers in {len(items)} position(s): "
            + ", ".join(i["id"] for i in items) + ".\n\nReturn one entry per position, in this order.")
    return "\n\n".join([head] + [deck_block(decks[d]) for d in used] + [position_block(i) for i in items])


def check_reply(out: dict | None, items: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """The usable per-position results of a judge reply (position id -> result) and what was wrong with the rest."""
    problems = []
    results = {}
    by_id = {p.get("position"): p for p in (out or {}).get("positions") or [] if isinstance(p, dict)}
    for item in items:
        p = by_id.get(item["id"])
        if p is None:
            problems.append(f"{item['id']}: missing from the reply")
            continue
        grades = {}
        for g in p.get("grades") or []:
            label = str(g.get("label", "")).strip().upper()[:1]
            if g.get("grade") in GRADES and label:
                grades[label] = {"grade": g["grade"], "reason": (g.get("reason") or "").strip()}
        want = {a["label"] for a in item["answers"]}
        if not want <= set(grades):
            problems.append(f"{item['id']}: no grade for {', '.join(sorted(want - set(grades)))}")
            continue
        try:
            own = [int(x) for x in p.get("own_choice") or []]
        except (TypeError, ValueError):
            own = None
        results[item["id"]] = {
            "assessment": (p.get("assessment") or "").strip(),
            "own_choice": own,
            "equivalent": sorted({str(x).strip().upper()[:1] for x in p.get("equivalent") or []} & want),
            "grades": {k: v for k, v in grades.items() if k in want},
            "confidence": p.get("confidence") if p.get("confidence") in CONFIDENCE else "medium",
        }
    return results, problems


def own_key(result: dict, decision: dict, key_of) -> str | None:
    """The judge's own pick as an answer key (None when it isn't a legal answer to the decision)."""
    own = result.get("own_choice")
    if own is None or validate(decision, own):
        return None
    return key_of(own)


def consistency(mapping: dict, result: dict, own: str | None) -> list[str]:
    """Places where a judge's reply contradicts itself."""
    issues = []
    grades = result["grades"]
    primary = {label: m for label, m in mapping.items() if not m.get("probe_of")}
    for label, m in primary.items():
        g = grades.get(label, {}).get("grade")
        if own is not None and m["key"] == own and g != "best":
            issues.append(f"its own choice is answer {label}, graded {g}")
        if label in result["equivalent"] and g != "best":
            issues.append(f"answer {label} is called equivalent to its own choice but graded {g}")
    if own is not None and any(m["key"] == own for m in primary.values()):
        best = [label for label in primary if grades.get(label, {}).get("grade") == "best"]
        if not best:
            issues.append("no answer is graded best although one matches its own choice")
    return issues


def probe_pairs(mapping: dict, grades: dict) -> list[tuple[str, str]]:
    """(grade of the real label, grade of its probe) for each probe label."""
    return [(grades.get(m["probe_of"], {}).get("grade"), grades.get(label, {}).get("grade"))
            for label, m in mapping.items() if m.get("probe_of")]


# ---- the sandbox ----

def build_sandbox(folder: str, ids, db, script_dirs: list[str]) -> dict:
    """A fresh read-only working folder for the agentic judge: scripts/c<id>.lua for the cards, the shared helper
    libraries, and cards.md with every card's text. Returns {"scripts": n, "missing": [...]}."""
    from ..trainer.dossier import LIBS, PROC_LIBS, find_lib, find_script
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "scripts"))
    copied, missing, texts, types = 0, [], [], 0
    for cid in sorted(set(ids)):
        card = db.get(cid)
        if card is None:
            continue
        types |= card.type
        texts.append(f"- {db.full_text(cid)}")
        src = find_script(cid, script_dirs, card.alias) if script_dirs else None
        if src:
            shutil.copyfile(src, os.path.join(folder, "scripts", f"c{cid}.lua"))
            copied += 1
        elif not card.type & 0x10:  # Normal Monsters have no script
            missing.append(card.name)
    for lib in LIBS + [lib for bit, lib in PROC_LIBS.items() if types & bit]:
        src = find_lib(lib, script_dirs) if script_dirs else None
        if src:
            os.makedirs(os.path.join(folder, "scripts", "lib"), exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, "scripts", "lib", lib))
    with open(os.path.join(folder, "cards.md"), "w", encoding="utf-8") as f:
        f.write("# Card texts\n\n" + "\n".join(texts) + "\n")
    return {"scripts": copied, "missing": missing}


# ---- whole-game review ----

def anonymize(md: str, labels: list[str], names: list[str] = ()) -> str:
    """game.md with the player's backend label, its timing and its seat name taken out (the reviewer stays blind)."""
    def tag(m):
        who = m.group("tag")
        return "> **player**:" if who in labels or MODEL_WORDS.search(who) else f"> **{who}**:"
    md = re.sub(r"> \*\*(?P<tag>[^*\n]+)\*\*(?: \([\d.]+s\))?:", tag, md)
    for name in names:
        if name:
            md = md.replace(name, "the player")
    return MODEL_WORDS.sub("player", md)


def game_prompt(game: dict, deck: dict, log_ref: str, problems: list[str]) -> str:
    """game: {"id", "deck_name", "opponent", "result", "turns", "first", "reason"}."""
    result = {"win": "won", "loss": "lost", "draw": "drew"}.get(game.get("result"), "finished")
    probs = "\n".join(f"- {p}" for p in problems) or "- none"
    return f"""# Task: count the significant mistakes in game {game['id']}

An AI player played {game['deck_name']} against {game.get('opponent') or 'an opponent'} and {result} in \
{game.get('turns', '?')} turns, going {'first' if game.get('first') else 'second'} ({game.get('reason') or ''}). \
{log_ref}

Go through the game turn by turn and list the player's mistakes, the way a coach reviews a student's game. Only the \
player's own decisions count: decisions tagged `rule:...` or `auto` were made by hard-coded rules, and `FALLBACK` ones \
by a fallback policy. Look for missed lethal (add up the damage it could have dealt), unused resources (searches not \
taken, the Normal Summon unused, triggers skipped, a card left in hand that had a use), bad chain timing (negation \
wasted or held too long), attacks into bigger or face-down monsters, wrong Extra Deck choices, misread rulings, and \
lines that deviate from the playbook for the worse. Verify each one against the options listed at that decision \
(and the card's script when a ruling decides it), and drop what you can't verify. Severity: `blunder` = it likely \
cost the game; `major` = it cost a lot of resources or a likely win; `minor` = a small inefficiency. Don't count luck, \
the opponent's strength or a weak draw. Put the number of blunders plus majors in `significant`.

## Problems the engine and the agent flagged

{probs}

{deck_block(deck)}"""


def count_significant(out: dict) -> int:
    mistakes = out.get("mistakes") or []
    return sum(1 for m in mistakes if m.get("severity") in ("blunder", "major"))
