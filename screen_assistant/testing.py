"""Test-only HTTP server using documented Ollama response shapes."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VISION_MODEL = "test-vision:latest"
TEXT_MODEL = "llama3.2:latest"


@dataclass
class Response:
    payload: object
    status: int = 200
    delay: float = 0
    chunk_size: int = 0
    chunk_delay: float = 0
    headers: dict = field(default_factory=dict)


def answer_response(text="The test image contains a rectangle.", **kwargs):
    return Response({"model": VISION_MODEL,
                     "message": {"role": "assistant", "content": text},
                     "done": True}, **kwargs)


class FakeOllamaServer:
    def __init__(self):
        self.requests = []
        self.routes = {}
        self.stopping = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.handle_request()

            def do_POST(self):
                self.handle_request()

            def handle_request(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                request = {"method": self.command, "path": self.path,
                           "headers": dict(self.headers), "body": json.loads(raw) if raw else None}
                owner.requests.append(request)
                route = owner.routes.get(self.path)
                response = route(request) if callable(route) else route
                if response is None:
                    response = owner.default_response(request)
                if owner.stopping.wait(response.delay):
                    return
                data = (response.payload if isinstance(response.payload, bytes) else
                        json.dumps(response.payload).encode("utf-8"))
                try:
                    self.send_response(response.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    for key, value in response.headers.items():
                        self.send_header(key, value)
                    self.end_headers()
                    chunk_size = response.chunk_size or max(1, len(data))
                    for offset in range(0, len(data), chunk_size):
                        self.wfile.write(data[offset:offset + chunk_size])
                        self.wfile.flush()
                        if response.chunk_delay and owner.stopping.wait(response.chunk_delay):
                            return
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.02), daemon=True)

    def default_response(self, request):
        if request["path"] == "/api/tags":
            return Response({"models": [
                {"name": VISION_MODEL, "model": VISION_MODEL,
                 "size": 123456, "details": {"format": "gguf"}},
                {"name": TEXT_MODEL, "model": TEXT_MODEL,
                 "size": 654321, "details": {"format": "gguf"}},
            ]})
        if request["path"] == "/api/show":
            model = request["body"].get("model")
            if model not in (VISION_MODEL, TEXT_MODEL):
                return Response({"error": "model not found"}, 404)
            capabilities = ["completion"]
            if model == VISION_MODEL:
                capabilities.append("vision")
            return Response({"capabilities": capabilities, "details": {"format": "gguf"},
                             "model_info": {"general.architecture": "test"}})
        if request["path"] == "/api/chat":
            return answer_response()
        return Response({"error": "not found"}, 404)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self.stopping.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def requests_to(self, path):
        return [r for r in self.requests if r["path"] == path]
