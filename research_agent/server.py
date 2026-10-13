"""Loopback HTTP adapter for the research terminal and its typed Agent API."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlparse

from pydantic import ValidationError
from .data import ROOT
from .models import ResearchRequest
from .workflow import run_research

RUN_SLOTS = BoundedSemaphore(2)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web/dist"), **kwargs)

    def json_response(self, status, value):
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/status":
            return self.json_response(200, {"service": "sarkaz-research", "version": "2.0.0",
                                           "model_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))})
        if self.path.startswith("/api/"):
            return self.json_response(404, {"error": "Unknown endpoint"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/research":
            return self.json_response(404, {"error": "Unknown endpoint"})
        # The server has no CORS grant. Reject cross-origin browser requests even
        # when a browser can reach loopback from an unrelated website.
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self.json_response(403, {"error": "Same-origin requests required"})
        if self.headers.get_content_type() != "application/json":
            return self.json_response(415, {"error": "Expected application/json"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 2 or size > 20000:
                return self.json_response(413, {"error": "Invalid request size"})
            request = ResearchRequest.model_validate_json(self.rfile.read(size))
        except (ValueError, ValidationError):
            return self.json_response(422, {"error": "Invalid research parameters"})
        if request.mode == "openai" and not (os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")):
            return self.json_response(409, {"error": "Configure OPENAI_API_KEY and OPENAI_MODEL on the server"})
        if not RUN_SLOTS.acquire(blocking=False):
            return self.json_response(429, {"error": "Research capacity reached; retry after the active run"})
        try:
            result = run_research(request, output_root=ROOT / "outputs/api-runs")
            result.pop("local_run_dir", None)
            return self.json_response(200, result)
        except Exception as error:
            return self.json_response(500, {"error": "Research failed", "type": type(error).__name__})
        finally:
            RUN_SLOTS.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8507)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    args = parser.parse_args()
    if not (ROOT / "web/dist/index.html").exists():
        raise SystemExit("Build the terminal first: cd web && npm ci && npm run build")
    print(f"SARKAZ Research Terminal · http://127.0.0.1:{args.port}", flush=True)
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
