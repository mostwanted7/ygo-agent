"""The reviewer: the LLM that writes and corrects the playbook. One call per task, a JSON reply (schemas.py).

* claude-code, agentic (the default): `claude -p` with only Read/Grep/Glob, in a sandbox folder outside the repo that
  holds copies of the workspace files the task needs (scripts, dossier, playbook, logs). `--restricted` confines the
  tools to that folder and nothing can write, so the reviewer reads what it wants and the trainer applies its JSON.
  The tool calls are kept in <step>.transcript.jsonl, so a report can say which scripts it actually opened.
* claude-code without tools, anthropic and openai: inline. The prompt carries the excerpts (pipeline.py decides).
* scripted (tests): the profile's `policy({"task", "prompt", "schema", "system"})` returns the reply dict.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time

from .. import backends
from ..backends.parse import _load, _objects, strip_reasoning
from ..paths import CACHE
from .workspace import TrainerError

TOOLS = "Read,Grep,Glob"
SANDBOX = os.path.join(CACHE, "trainer")
REVIEW_TYPES = ("claude-code", "anthropic", "openai", "scripted")


class Reviewer:
    def __init__(self, profile: dict, db=None, agentic: bool | None = None, name: str = "deck"):
        if profile.get("type") not in REVIEW_TYPES:
            raise TrainerError(f"the reviewer needs an LLM backend (claude-code, anthropic or openai); "
                               f"{profile.get('name')!r} is {profile.get('type')!r}")
        self.profile = profile
        self.db = db
        self.type = profile["type"]
        self.agentic = (self.type == "claude-code") if agentic is None else (agentic and self.type == "claude-code")
        self.sandbox = os.path.join(SANDBOX, name)
        self.label = backends.label(profile) if self.type != "scripted" else "scripted"

    def check(self):
        if self.type != "scripted":
            backends.check(self.profile)

    # ---- the sandbox (agentic) ----

    def sync(self, workspace_dir: str, items: list[str]) -> str:
        """Copy workspace files/folders (relative paths) into a fresh sandbox; returns its path."""
        if os.path.isdir(self.sandbox):
            shutil.rmtree(self.sandbox)
        os.makedirs(self.sandbox)
        for item in items:
            src = os.path.join(workspace_dir, item)
            dst = os.path.join(self.sandbox, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("*.yrpX", "latest"),
                                dirs_exist_ok=True)
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        return self.sandbox

    # ---- asking ----

    def ask(self, task: str, system: str, prompt: str, schema: dict, *, timeout: float = 2400,
            transcript: str | None = None, max_cost: float | None = None) -> tuple[dict | None, dict]:
        """(reply dict or None, info with seconds, cost_usd, error, files_read, turns)."""
        info = {"seconds": 0.0, "cost_usd": None, "error": None, "files_read": [], "turns": 0}
        start = time.monotonic()
        try:
            if self.type == "scripted":
                out = self._scripted(task, system, prompt, schema, info)
            elif self.type == "claude-code":
                out = self._claude(system, prompt, schema, timeout, transcript, max_cost, info)
            else:
                out = self._http(system, prompt, schema, timeout, info)
        except (OSError, backends.BackendError, subprocess.SubprocessError) as e:
            info["error"] = f"{type(e).__name__}: {e}"
            out = None
        info["seconds"] = round(time.monotonic() - start, 1)
        if out is not None and not isinstance(out, dict):
            info["error"] = f"the reply is not a JSON object: {str(out)[:200]}"
            out = None
        return out, info

    def _scripted(self, task, system, prompt, schema, info):
        out = self.profile["policy"]({"task": task, "prompt": prompt, "schema": schema, "system": system})
        info["cost_usd"] = self.profile.get("cost_per_call", 0.0)
        return out

    def _claude(self, system, prompt, schema, timeout, transcript, max_cost, info):
        p = self.profile
        cwd = self.sandbox if self.agentic else os.path.join(CACHE, "claude-code")
        os.makedirs(cwd, exist_ok=True)
        os.makedirs(CACHE, exist_ok=True)
        fd, system_file = tempfile.mkstemp(prefix="reviewer-", suffix=".md", dir=os.path.join(CACHE))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [p.get("command", "claude"), "-p", "--output-format", "stream-json", "--verbose",
               "--model", p.get("model") or "opus", "--system-prompt-file", system_file,
               "--json-schema", json.dumps(schema), "--setting-sources", "", "--strict-mcp-config",
               "--disable-slash-commands", "--no-session-persistence"]
        if self.agentic:
            cmd += ["--tools", TOOLS, "--allowedTools", TOOLS, "--permission-mode", "dontAsk", "--restricted"]
        else:
            cmd += ["--tools", ""]
        if p.get("effort"):
            cmd += ["--effort", p["effort"]]
        if max_cost is not None and max_cost > 0:
            cmd += ["--max-budget-usd", f"{max_cost:.2f}"]
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        except subprocess.TimeoutExpired:
            info["error"] = f"timed out after {timeout:.0f}s"
            return None
        finally:
            try:
                os.remove(system_file)
            except OSError:
                pass
        result = None
        events = []
        for line in proc.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            events.append(ev)
            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if block.get("type") == "tool_use":
                        args = block.get("input") or {}
                        path = args.get("file_path") or args.get("pattern") or args.get("path")
                        if path:
                            shown = os.path.relpath(path, cwd) if os.path.isabs(path) else path
                            info["files_read"].append(f"{block.get('name')}: {shown}")
            if ev.get("type") == "result":
                result = ev
        if transcript:
            with open(transcript, "w", encoding="utf-8") as f:
                for ev in events:
                    f.write(json.dumps(ev) + "\n")
        if result is None:
            info["error"] = f"no result (exit {proc.returncode}): {proc.stderr.strip()[-400:]}"
            return None
        info["cost_usd"] = result.get("total_cost_usd")
        info["turns"] = result.get("num_turns") or 0
        if result.get("is_error"):
            info["error"] = str(result.get("result") or result.get("subtype") or "error")[:400]
            return None
        out = result.get("structured_output")
        if isinstance(out, dict):
            return out
        return extract_json(result.get("result") or "")

    def _http(self, system, prompt, schema, timeout, info):
        profile = dict(self.profile)
        if self.type == "anthropic":
            profile["max_tokens"] = max(int(profile.get("max_tokens", 16000)), 32000)
        backend = backends.create(profile, self.db)
        session = backend.open_session(system, schema)
        session.system_prompt = system + ("" if self.type == "anthropic" and profile.get("structured", "json_schema")
                                          == "json_schema" else JSON_NOTE)
        deadline = time.monotonic() + timeout
        call = backends.new_info()
        text = prompt
        out = None
        for attempt in range(2):
            session._user(text)
            raw, parsed = session._complete(deadline, call)
            out = parsed if isinstance(parsed, dict) else extract_json(raw or "")
            if isinstance(out, dict):
                break
            text = "Your reply could not be read as JSON. Reply again with only the JSON object the task asks for."
        info["cost_usd"] = call.get("cost_usd")
        info["tokens"] = {k: call[k] for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                                               "cache_write_tokens")}
        if out is None:
            info["error"] = "no JSON object in the reply"
        return out


JSON_NOTE = "\n\nReply with a single JSON object that matches the requested schema, and nothing else."


def extract_json(text: str):
    """The last top-level JSON object in a model's text (code fences, prose and reasoning around it are fine)."""
    if not isinstance(text, str):
        return None
    body = strip_reasoning(text)
    for span in reversed(_objects(body)):
        obj = _load(span)
        if isinstance(obj, dict):
            return obj
    return None
