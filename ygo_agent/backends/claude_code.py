"""Backend type "claude-code": a persistent headless Claude Code session (`claude -p`, streaming JSON in and out).

Uses the user's normal Claude Code login, so no API key is needed. The agent keeps one session per game turn:
the model keeps its plan between the decisions of that turn, and each new turn starts fresh with a recap. The
agent opens the next turn's session as soon as the turn starts (pre-warming), so the CLI's start-up is hidden.
"""

import glob
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time

from ..paths import CACHE
from .base import Backend, BackendError, Session, new_info
from .parse import ParseError, normalize, parse_reply

WORKDIR = os.path.join(CACHE, "claude-code")


class ClaudeCodeBackend(Backend):
    TYPE = "claude-code"

    def check(self):
        if not shutil.which(self.profile.get("command", "claude")):
            raise BackendError("The `claude` CLI is not on PATH; the claude-code backend runs it (your Claude Code "
                               "login, no API key needed).")

    def open_session(self, system_prompt, schema):
        return ClaudeCodeSession(system_prompt, schema, self.profile.get("model") or "opus",
                                 self.profile.get("effort") or None, command=self.profile.get("command", "claude"))


def _clean_old_prompt_files(folder, age=86400):
    for path in glob.glob(os.path.join(folder, "system-*.md")):
        try:
            if time.time() - os.path.getmtime(path) > age:
                os.remove(path)
        except OSError:
            pass


class ClaudeCodeSession(Session):
    def __init__(self, system_prompt, schema, model, effort=None, cwd=None, command="claude"):
        self.messages = 0  # not Session.__init__(): `alive` is the process's state here, not a flag
        # An empty working directory, so the CLI doesn't pick up this repo's CLAUDE.md or settings.
        self.cwd = cwd or WORKDIR
        os.makedirs(self.cwd, exist_ok=True)
        _clean_old_prompt_files(self.cwd)  # left behind by sessions that crashed
        # The system prompt goes through a file: it's tens of kB, too big to show in `ps` and close to argv limits.
        fd, self.prompt_file = tempfile.mkstemp(prefix="system-", suffix=".md", dir=self.cwd)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(system_prompt)
        cmd = [
            command, "-p",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence",
            "--model", model,
            "--system-prompt-file", self.prompt_file,
            "--json-schema", json.dumps(schema),
        ]
        if effort:
            cmd += ["--effort", effort]
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, cwd=self.cwd, bufsize=1)
        except OSError:
            os.remove(self.prompt_file)
            raise
        self.lines = queue.Queue()
        self.stderr_tail = []
        self.total_cost = 0.0  # the CLI reports the session's running total; per-call cost is the difference
        threading.Thread(target=self._pump, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _drain_stderr(self):
        for line in self.proc.stderr:
            self.stderr_tail = (self.stderr_tail + [line.rstrip()])[-20:]

    @property
    def alive(self):
        return self.proc.poll() is None

    def ask(self, request):
        info = new_info()
        start = time.monotonic()
        try:
            return self._ask(request, info, start)
        finally:
            info["seconds"] = round(time.monotonic() - start, 2)

    def _ask(self, request, info, start):
        if not self.alive:
            info["error"] = "session process exited: " + " | ".join(self.stderr_tail)
            return None, info
        try:
            self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": request.text}})
                                  + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            info["error"] = f"could not write to session: {e}"
            return None, info
        self.messages += 1
        deadline = start + request.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                info["error"] = f"timed out after {request.timeout}s"
                self.close()
                return None, info
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                info["error"] = "session ended: " + " | ".join(self.stderr_tail)
                return None, info
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "result":
                continue
            self._usage(ev, info)
            if ev.get("is_error"):
                info["error"] = ev.get("result") or ev.get("subtype") or "error result"
                return None, info
            info["replies"] += 1
            try:
                out = ev.get("structured_output")
                return normalize(out if isinstance(out, dict) else parse_reply(ev.get("result") or "")), info
            except ParseError as e:
                info["invalid"] += 1
                info["error"] = f"unparseable reply ({e}): {(ev.get('result') or '')[:200]!r}"
                return None, info

    def _usage(self, ev, info):
        usage = ev.get("usage") or {}
        info["input_tokens"] = usage.get("input_tokens", 0)
        info["output_tokens"] = usage.get("output_tokens", 0)
        info["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0)
        info["cache_write_tokens"] = usage.get("cache_creation_input_tokens", 0)
        total = ev.get("total_cost_usd")
        if isinstance(total, (int, float)):
            # What the CLI says these tokens would cost at API prices (a subscription login isn't billed per call).
            info["cost_usd"] = round(max(0.0, total - self.total_cost), 6)
            self.total_cost = total

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()  # reap it, or it stays a zombie until this object is collected
        try:
            os.remove(self.prompt_file)
        except OSError:
            pass
