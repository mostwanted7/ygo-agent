"""A fake OpenAI-compatible chat server that "plays" from the prompt text alone, for end-to-end runs of the openai
backend without a model:

    python tests/fake_openai_server.py --port 8765 --sloppy --reject-schema

then point a profile at it (`type = "openai"`, `base_url = "http://127.0.0.1:8765/v1"`, any `model`).

It reads the last DECISION in the newest user message and answers with a legal-looking choice: yes to yes/no
questions, pass in response windows, the minimum number of cards for selections (a sum is reached from the
"counts as N" values), and option 0 otherwise. --sloppy wraps answers the way weak models do (think blocks, code
fences, prose, trailing commas). --reject-schema answers json_schema requests with HTTP 400, as servers without
structured output do, so the backend's json_mode "auto" has to step down.
"""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STYLES = [
    lambda j: j,
    lambda j: f"<think>\nLet me look at the options carefully.\n</think>\n{j}",
    lambda j: f"Sure! Here's my move:\n```json\n{j}\n```",
    lambda j: j[:-1] + ",}",
    lambda j: f"I'll go with this.\n{j}\nGood luck!",
]


def decide(text):
    """A choice list for the last decision in `text`."""
    if "That reply is invalid" in text or "could not be read" in text:
        return [0]
    m = list(re.finditer(r"DECISION #\d+: (.*)", text))
    if not m:
        return [0]
    question = m[-1].group(1)
    options = re.findall(r"^\[(\d+)\] (.*)$", text[m[-1].start():], re.M)
    if "Reply [1] for yes" in question or "Reply [1] to go first" in question:
        return [1]
    if "Reply with [] to pass" in question:
        return []
    if "reply [] to finish here" in question:
        return []
    count = re.search(r"Choose between (\d+) and (\d+) card", question)
    if count:
        return list(range(int(count.group(1))))
    total = re.search(r"add up to (exactly|at least) (\d+)", question)
    if total:
        need, pick, got = int(total.group(2)), [], 0
        for k, line in options:
            if got >= need:
                break
            v = re.search(r"counts as (\d+)", line)
            if v:
                pick.append(int(k))
                got += int(v.group(1))
        return pick
    flags = re.search(r"Reply with exactly (\d+) option indices", question)
    if flags:
        return list(range(int(flags.group(1))))
    return [0]


def make_handler(sloppy=False, reject_schema=False):
    state = {"n": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
            if reject_schema and (body.get("response_format") or {}).get("type") == "json_schema":
                return self.send(400, {"error": {"message": "response_format json_schema is not supported"}})
            last = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "user")
            choice = decide(last)
            reply = json.dumps({"why": "fake model: first legal-looking option", "choice": choice, "plan": ""})
            if sloppy:
                state["n"] += 1
                reply = STYLES[state["n"] % len(STYLES)](reply)
            prompt = sum(len(m["content"]) for m in body["messages"]) // 4
            self.send(200, {"id": "fake", "object": "chat.completion", "model": body.get("model"),
                            "choices": [{"index": 0, "finish_reason": "stop",
                                         "message": {"role": "assistant", "content": reply}}],
                            "usage": {"prompt_tokens": prompt, "completion_tokens": len(reply) // 4}})

        def send(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def server(port=0, sloppy=False, reject_schema=False):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(sloppy, reject_schema))
    httpd.daemon_threads = True
    return httpd


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--sloppy", action="store_true")
    ap.add_argument("--reject-schema", action="store_true")
    a = ap.parse_args()
    httpd = server(a.port, a.sloppy, a.reject_schema)
    print(f"fake OpenAI-compatible server on http://127.0.0.1:{httpd.server_address[1]}/v1", flush=True)
    httpd.serve_forever()
