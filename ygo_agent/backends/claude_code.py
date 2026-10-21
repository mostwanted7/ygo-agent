"""Backend type "claude-code": a persistent headless Claude Code session (`claude -p`, streaming JSON in and out).

Uses the user's normal Claude Code login, so no API key is needed. The agent keeps one session per game turn:
the model keeps its plan between the decisions of that turn, and each new turn starts fresh with a recap.
"""

import json
import os
import queue
import subprocess
import threading
import time

from ..paths import CACHE

LABEL = "Claude"


class ClaudeCodeSession:
    def __init__(self, system_prompt, schema, model, effort=None, cwd=None):
        # An empty working directory, so the CLI doesn't pick up this repo's CLAUDE.md or settings.
        self.cwd = cwd or os.path.join(CACHE, "claude-code")
        os.makedirs(self.cwd, exist_ok=True)
        cmd = [
            "claude", "-p",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--tools", "", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence",
            "--model", model,
            "--system-prompt", system_prompt,
            "--json-schema", json.dumps(schema),
        ]
        if effort:
            cmd += ["--effort", effort]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, cwd=self.cwd, bufsize=1)
        self.lines = queue.Queue()
        self.messages = 0
        self.stderr_tail = []
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

    def ask(self, text, timeout):
        """Send one user message; returns (structured_output dict or None, info dict)."""
        info = {"started": time.time()}
        if not self.alive:
            info["error"] = "session process exited: " + " | ".join(getattr(self, "stderr_tail", []))
            return None, info
        try:
            self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            info["error"] = f"could not write to session: {e}"
            return None, info
        self.messages += 1
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                info["error"] = f"timed out after {timeout}s"
                self.close()
                return None, info
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                info["error"] = "session ended: " + " | ".join(getattr(self, "stderr_tail", []))
                return None, info
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "result":
                continue
            info["seconds"] = round(time.time() - info["started"], 1)
            info["usage"] = ev.get("usage")
            if ev.get("is_error"):
                info["error"] = ev.get("result") or ev.get("subtype") or "error result"
                return None, info
            out = ev.get("structured_output")
            if out is None:
                try:
                    out = json.loads(ev.get("result") or "")
                except json.JSONDecodeError:
                    info["error"] = f"unparseable reply: {(ev.get('result') or '')[:300]}"
                    return None, info
            return out, info

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
