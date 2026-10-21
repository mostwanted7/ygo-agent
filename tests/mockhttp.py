"""A local HTTP server with scripted responses, for the API backends' tests (no network, no keys).

    with MockServer() as srv:
        srv.queue(status=429, body={...}, headers={"retry-after": "0"})
        srv.queue(body={...})               # or srv.handler = lambda request: response dict
        ... point a backend at srv.url ...
        srv.requests                         # [{"path", "headers", "body"}, ...]
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockServer:
    def __init__(self):
        self.responses = []
        self.requests = []
        self.handler = None  # callable(request) -> response dict, used when the queue is empty
        self.lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("content-length", 0)))
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = raw.decode()
                request = {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                           "body": body}
                with server.lock:
                    server.requests.append(request)
                    resp = server.responses.pop(0) if server.responses else None
                if resp is None:
                    resp = server.handler(request) if server.handler else {"status": 500, "body": "no response"}
                if resp.get("delay"):
                    time.sleep(resp["delay"])
                payload = resp.get("body", {})
                data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                try:
                    self.send_response(resp.get("status", 200))
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(data)))
                    for k, v in (resp.get("headers") or {}).items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client gave up (timeout tests)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def queue(self, body=None, status=200, headers=None, delay=0):
        self.responses.append({"body": {} if body is None else body, "status": status, "headers": headers,
                               "delay": delay})

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def anthropic_message(text=None, tool_input=None, usage=None, stop_reason="end_turn", thinking=True):
    """A Messages API response body."""
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}] if thinking else []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool_input is not None:
        content.append({"type": "tool_use", "id": "toolu_1", "name": "reply", "input": tool_input})
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": content,
            "stop_reason": "tool_use" if tool_input is not None else stop_reason,
            "usage": usage or {"input_tokens": 12, "output_tokens": 30, "cache_read_input_tokens": 5000,
                               "cache_creation_input_tokens": 100}}


def openai_completion(content, usage=None, finish_reason="stop", **message):
    return {"id": "cmpl-1", "object": "chat.completion", "model": "test",
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": {"role": "assistant", "content": content, **message}}],
            "usage": usage or {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940}}
