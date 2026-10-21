"""Reading a decision reply out of whatever a model wrote.

Models without enforced structured output wrap the JSON in code fences, put prose or <think>…</think> reasoning
around it, leave trailing commas, use single quotes or unquoted keys, get cut off mid-object, or answer with a bare
number. parse_reply() recovers {"choice": [...], "why": ..., "plan": ...} from all of those, or raises ParseError.
"""

import ast
import json
import re


class ParseError(ValueError):
    pass


THINK = re.compile(r"<(think|thinking|reasoning|thought)>.*?</\1>", re.S | re.I)
UNOPENED_THINK = re.compile(r"^.*?</(think|thinking|reasoning|thought)>", re.S | re.I)
FENCE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", re.S)
CHOICE_KEYS = ("choice", "choices", "answer", "option", "options", "index", "indices", "selection", "pick")
WHY_KEYS = ("why", "reason", "reasoning", "explanation", "rationale")
# Words meaning "[]". Not "no"/"yes": in a yes/no prompt those are [0]/[1], in a chain window "no" means pass.
PASS_WORDS = ("pass", "none", "nothing", "skip", "cancel", "finish", "done", "")


def strip_reasoning(text):
    text = THINK.sub("", text)
    if re.search(r"</(think|thinking|reasoning|thought)>", text, re.I):
        text = UNOPENED_THINK.sub("", text)  # the opening tag was part of the chat template
    return re.sub(r"<(think|thinking|reasoning|thought)>.*\Z", "", text, flags=re.S | re.I)  # never closed


def _clean(src):
    """Make near-JSON loadable: drop comments and trailing commas, quote bare keys, swap single-quoted strings.
    Works on the token level, so text inside strings is never touched."""
    out, i, n = [], 0, len(src)
    while i < n:
        ch = src[i]
        if ch in "\"'":
            j, buf = i + 1, []
            while j < n and src[j] != ch:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                buf.append(src[j])
                j += 1
            body = "".join(buf)
            if ch == "'":
                body = body.replace('\\"', '"').replace("\\'", "'").replace('"', '\\"')
            out.append('"' + body + '"')
            i = j + 1
            continue
        if src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == ",":
            k = i + 1
            while k < n and src[k].isspace():
                k += 1
            if k >= n or src[k] in "}]":
                i += 1
                continue
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", src[i:])
        if m:
            word = m.group(0)
            rest = src[i + len(word):].lstrip()
            prev = "".join(out).rstrip()[-1:]
            if rest.startswith(":") and prev in ("{", ",", ""):
                out.append(f'"{word}"')
            else:
                out.append({"True": "true", "False": "false", "None": "null"}.get(word, word))
            i += len(word)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _objects(text):
    """Every top-level {...} span in the text; an object still open at the end is closed (cut-off replies)."""
    spans, depth, start, in_str, esc, stack = [], 0, None, None, False, []
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'" and depth:
            in_str = ch
        elif ch in "{[":
            if ch == "{" and depth == 0:
                start = i
            if depth or ch == "{":
                depth += 1
                stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and depth:
            depth -= 1
            stack.pop()
            if depth == 0:
                spans.append(text[start:i + 1])
    if depth and start is not None:
        tail = text[start:]
        if in_str:
            tail += in_str
        spans.append(tail.rstrip().rstrip(",") + "".join(reversed(stack)))
    return spans


def _load(src):
    for candidate in (src, _clean(src)):
        try:
            return json.loads(candidate, strict=False)
        except ValueError:
            pass
    try:
        return ast.literal_eval(src)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None


def _bare_choice(text):
    """A reply that is only a number or a list of numbers ("2", "[0, 3]", "Choice: 1", "[]")."""
    t = text.strip().strip("`").strip()
    m = re.fullmatch(r"(?:(?:final\s+)?(?:choice|answer|option|pick)s?\s*[:=]?\s*)?(\[[\d,\s]*\]|-?\d+)\.?", t, re.I)
    if not m:
        return None
    value = json.loads(m.group(1))
    return {"choice": value if isinstance(value, list) else [value], "why": ""}


def parse_reply(text):
    """The reply dict in a model's raw output; raises ParseError with a short reason."""
    if isinstance(text, dict):
        return text
    if not isinstance(text, str) or not text.strip():
        raise ParseError("the reply was empty")
    body = strip_reasoning(text).strip()
    if not body:
        raise ParseError("the reply had only reasoning, no answer")
    pieces = FENCE.findall(body) + [body]
    for piece in pieces:
        found = [obj for obj in (_load(s) for s in _objects(piece)) if isinstance(obj, dict)]
        with_choice = [obj for obj in found if any(k in obj for k in CHOICE_KEYS)]
        if with_choice:
            return with_choice[-1]  # after any examples or reasoning, the last answer counts
        bare = _bare_choice(piece)
        if bare:
            return bare
        loaded = _load(piece.strip())
        if isinstance(loaded, list) and all(isinstance(x, int) for x in loaded):
            return {"choice": loaded, "why": ""}
    if any(_objects(body)):
        raise ParseError('no "choice" field in the JSON')
    raise ParseError("no JSON object in the reply")


def _ints(value):
    if value is None or isinstance(value, bool):
        raise ParseError("choice must be a list of integers")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            raise ParseError("choice must be a list of integers")
        return [int(value)]
    if isinstance(value, str):
        if value.strip().lower() in PASS_WORDS:
            return []
        nums = re.findall(r"-?\d+", value)
        if nums and re.fullmatch(r"[\s\[\](),\-\d]*", value):
            return [int(x) for x in nums]
        raise ParseError(f"choice {value!r} is not a list of option indices")
    if isinstance(value, (list, tuple)):
        out = []
        for x in value:
            out += _ints(x) if isinstance(x, (list, tuple, str)) else _ints(x)
        return out
    raise ParseError("choice must be a list of integers")


def normalize(reply):
    """{"choice": [int, ...], "why": str, "plan": str | None} from a loosely shaped reply dict."""
    if not isinstance(reply, dict):
        raise ParseError("the reply is not a JSON object")
    key = next((k for k in CHOICE_KEYS if k in reply), None)
    if key is None:
        raise ParseError('no "choice" field in the JSON')
    why = next((reply[k] for k in WHY_KEYS if k in reply and reply[k] is not None), "")
    plan = reply.get("plan")
    if isinstance(plan, list):
        plan = "\n".join(str(p) for p in plan)
    return {"choice": _ints(reply[key]), "why": str(why).strip(),
            "plan": (str(plan).strip() or None) if plan is not None else None}
