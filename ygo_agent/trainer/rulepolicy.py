"""When a reviewer's rule proposal may become a hard rule in rules.py.

Hard rules are calibrated to the play model (the default backend, config agent.backend): one is only for a mistake
with no judgment in it that the play model made even though the playbook already covered it, and a saved regression
case must prove it. Everything else is playbook material. A proposal that qualifies is written into rules.py only
with `ygo-agent train --write-rules`; the others, and those, go to train/rule-proposals.md with the reasons.
"""

from __future__ import annotations

import ast
import os
import re

from . import playbook as pb

HEADER = """# Rule proposals

Hard rules are for mistakes with no judgment in them that the play model ({play_model}) makes even with a playbook \
lesson, each proven by a regression case. A proposal that qualifies is written into rules.py only with \
`ygo-agent train --write-rules`; otherwise copy it yourself. Check a rule with `ygo-agent test --deck {deck} <case>`, \
and later with `ygo-agent test --deck {deck} --ablate-rules`, which finds the rules a model no longer needs.

"""


def assess(proposal: dict, mistakes: list[dict], *, player: str, play_model: str, playbook: str,
           cases: set[str]) -> dict:
    """{"rule", "decisions", "case", "code", "qualifies", "reasons"}. `mistakes`: this game's verified mistakes;
    `playbook`: the text the game was played with; `cases`: the deck's saved case names."""
    decisions = [int(d) for d in proposal.get("decisions") or [] if str(d).lstrip("-").isdigit()]
    found = [m for m in mistakes if m.get("decision") in decisions]
    reasons = []
    if not found:
        reasons.append("no verified mistake at those decisions")
    elif not any(m.get("no_judgment") for m in found):
        reasons.append("the mistake needed judgment: improve the playbook instead")
    if player != play_model:
        reasons.append(f"made by {player}, not by the play model {play_model}: check it with "
                       f"`--backend {play_model}` first")
    if found and not any(m.get("playbook_had") and pb.quote_found(m["playbook_had"], playbook) for m in found):
        reasons.append("the playbook didn't cover it yet: the new pitfall or principle gets the first chance")
    case = (proposal.get("case") or "").strip()
    if case not in cases:
        reasons.append("no saved regression case proves it" + (f" ({case!r} wasn't saved)" if case else ""))
    return {"rule": (proposal.get("rule") or "").strip(), "decisions": decisions, "case": case,
            "code": (proposal.get("code") or "").strip(), "qualifies": not reasons, "reasons": reasons}


def function_name(code: str) -> str | None:
    """The name of the function `code` defines, if it is exactly one function of one argument and nothing else
    (nothing may run when rules.py is imported), else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].decorator_list:
        return None
    fn = tree.body[0]
    return fn.name if len(fn.args.args) == 1 and not fn.args.vararg and not fn.args.kwarg else None


def write_rule(path: str, code: str, case: str) -> str | None:
    """Append the rule to rules.py with @cases(case) and list it in RULES. Returns its name, or None when the code
    isn't one clean function or the file wouldn't load (the file is left as it was)."""
    name = function_name(code)
    if not name:
        return None
    with open(path, encoding="utf-8") as f:
        old = f.read()
    m = re.search(r"(?ms)^RULES\s*=\s*\[(.*?)\]", old)
    if not m or re.search(rf"\bdef {re.escape(name)}\b", old):
        return None
    text = old
    if not re.search(r"(?m)^from ygo_agent\.agent\.rules import [^\n]*\bcases\b", text):
        doc = re.match(r'(?s)\s*""".*?"""\n', text)
        at = doc.end() if doc else 0
        text = text[:at] + "\nfrom ygo_agent.agent.rules import Decide, cases  # noqa: F401\n" + text[at:]
    m = re.search(r"(?ms)^RULES\s*=\s*\[(.*?)\]", text)
    items = [x.strip() for x in m.group(1).split(",") if x.strip()]
    block = f"@cases({case!r})\n{code.strip()}\n\n\n"
    listed = "RULES = [\n" + "".join(f"    {x},\n" for x in items + [name]) + "]"
    text = text[:m.start()] + block + listed + text[m.end():]
    try:
        compile(text, path, "exec")
    except SyntaxError:
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        from ..agent.rules import Rules
        if name not in [r.__name__ for r in Rules(os.path.dirname(path)).deck_rules]:
            raise ValueError(name)
    except Exception:
        with open(path, "w", encoding="utf-8") as f:
            f.write(old)
        return None
    return name


def entry_markdown(entry: dict) -> str:
    where = f"{entry.get('game')} #{', #'.join(map(str, entry['decisions']))}" if entry.get("decisions") else \
        entry.get("game", "")
    status = ("**written to rules.py**" if entry.get("written") else "**qualifies**" if entry["qualifies"] else
              "not a rule (yet)")
    out = f"- {status} ({where}, played by {entry.get('player')}): {entry['rule']}"
    if entry.get("case"):
        out += f" Case: `{entry['case']}`."
    if entry["reasons"]:
        out += " Why not: " + "; ".join(entry["reasons"]) + "."
    if entry.get("code"):
        out += "\n\n  ```python\n" + "\n".join("  " + line for line in entry["code"].splitlines()) + "\n  ```"
    return out + "\n"
