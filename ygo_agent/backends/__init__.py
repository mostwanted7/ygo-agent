"""Decision backends. A backend profile (a [backends.NAME] table in the config) opens sessions; a session answers
one decision message at a time:

    session = open_session(profile, system_prompt, schema)
    reply, info = session.ask(text, timeout)   # reply: dict matching `schema`, or None (info["error"] says why)
    session.alive, session.messages, session.close()

Only "claude-code" exists so far; other types (API, OpenAI-compatible, heuristic) plug in here.
"""

import shutil

TYPES = ("claude-code",)


class BackendError(Exception):
    pass


def check(profile):
    """Raise BackendError if this profile can't run on this machine."""
    kind = profile.get("type")
    if kind not in TYPES:
        raise BackendError(f"backend {profile.get('name')!r} has type {kind!r}; supported: {', '.join(TYPES)}")
    if kind == "claude-code" and not shutil.which("claude"):
        raise BackendError("The `claude` CLI is not on PATH; the claude-code backend uses it to talk to Claude.")


def label(profile):
    """How decisions by this backend are tagged in the terminal and game.md."""
    if profile.get("type") == "claude-code":
        from .claude_code import LABEL
        return LABEL
    return profile.get("name", "AI")


def describe(profile):
    bits = [f"model: {profile['model']}"] if profile.get("model") else []
    if profile.get("effort"):
        bits.append(f"effort: {profile['effort']}")
    return ", ".join(bits)


def open_session(profile, system_prompt, schema):
    kind = profile.get("type")
    if kind == "claude-code":
        from .claude_code import ClaudeCodeSession
        return ClaudeCodeSession(system_prompt, schema, profile["model"], profile.get("effort") or None)
    raise BackendError(f"unsupported backend type {kind!r}")
