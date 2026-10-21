"""Decision backends. A backend profile (a [backends.NAME] table in the config, with a `type`) becomes a Backend,
which opens one session per game turn; a session answers one decision at a time (see base.py and
docs/backends.md):

    backend = create(profile, db=card_db)
    session = backend.open_session(system_prompt, schema)
    reply, info = session.ask(Request(text, decision, schema, timeout))
"""

from .base import Backend, BackendError, Request, Session, estimate_tokens, new_info  # noqa: F401

TYPES = {
    "claude-code": ("claude_code", "ClaudeCodeBackend"),
    "anthropic": ("anthropic_api", "AnthropicBackend"),
    "openai": ("openai_compat", "OpenAIBackend"),
    "heuristic": ("heuristic", "HeuristicBackend"),
    "random": ("random_", "RandomBackend"),
    "scripted": ("scripted", "ScriptedBackend"),
}


def backend_class(kind):
    if kind not in TYPES:
        raise BackendError(f"unknown backend type {kind!r}; supported: {', '.join(TYPES)}")
    import importlib
    module, cls = TYPES[kind]
    return getattr(importlib.import_module(f"{__name__}.{module}"), cls)


def create(profile, db=None):
    """A Backend for a profile dict ({"name": ..., "type": ..., ...}); a Backend passes through unchanged."""
    if isinstance(profile, Backend):
        return profile
    return backend_class(profile.get("type"))(profile, db)


def check(profile):
    """Raise BackendError if this profile can't run on this machine."""
    create(profile).check()


def label(profile):
    """How decisions by this backend are tagged in the terminal and game.md, e.g. "opus (claude-code)"."""
    return create(profile).label


def describe(profile):
    return create(profile).describe()


def open_session(profile, system_prompt, schema, db=None):
    return create(profile, db).open_session(system_prompt, schema)
