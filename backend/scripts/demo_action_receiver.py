#!/usr/bin/env python3
"""Minimal local webhook target for RoomOS automation demos.

Listens on http://127.0.0.1:9999/roomos and prints JSON POST bodies.
Run alongside RoomOS with configs/actions.demo-local.yaml.

From repo root::

    npm run demo:receiver
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple

HOST = "127.0.0.1"
PORT = 9999


class RoomOSHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {"raw": raw.decode("utf-8", errors="replace")}
        print(f"\n>>> POST {self.path}")
        print(json.dumps(body, indent=2))
        sys.stdout.flush()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"RoomOS demo webhook receiver OK\n")
            return
        self.send_response(404)
        self.end_headers()


def main() -> None:
    addr: Tuple[str, int] = (HOST, PORT)
    print(f"RoomOS demo receiver listening on http://{HOST}:{PORT}/roomos")
    print("Press Ctrl+C to stop.\n")
    HTTPServer(addr, RoomOSHandler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
