"""Backend type "scripted": canned replies, for tests.

The profile gives either `policy`, a callable (decision dict -> reply dict, or a choice list), or `replies`, a list
of reply dicts / choice lists used in order (a None entry, or running out, gives a failed ask). Every session
records the system prompt and the prompts it was asked in `backend.sessions`.
"""

from .base import Backend, Session, new_info
from .parse import ParseError, normalize


class ScriptedBackend(Backend):
    TYPE = "scripted"

    def __init__(self, profile, db=None):
        super().__init__(profile, db)
        self.replies = list(profile.get("replies") or [])
        self.sessions = profile.get("sessions", [])  # a list the test can hold on to

    def open_session(self, system_prompt, schema):
        session = ScriptedSession(self, system_prompt)
        self.sessions.append(session)
        return session

    def next_reply(self, request):
        policy = self.profile.get("policy")
        if policy:
            return policy(request.decision)
        return self.replies.pop(0) if self.replies else None


class ScriptedSession(Session):
    def __init__(self, backend, system_prompt):
        super().__init__()
        self.backend = backend
        self.system_prompt = system_prompt
        self.prompts = []
        self.requests = []

    def ask(self, request):
        info = new_info()
        self.messages += 1
        self.prompts.append(request.text)
        self.requests.append(request)
        out = self.backend.next_reply(request)
        if out is None:
            info["error"] = "no scripted reply"
            return None, info
        info["replies"] = 1
        if isinstance(out, list):
            out = {"choice": out, "why": "scripted"}
        try:
            return normalize(out), info
        except ParseError as e:
            info["invalid"] = 1
            info["error"] = str(e)
            return None, info
