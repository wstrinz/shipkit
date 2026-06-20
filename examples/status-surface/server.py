#!/usr/bin/env python3
"""Minimal reference status surface for a Loop-Mode Ship.

Zero dependencies (Python stdlib only). Serves a single self-contained page
that renders the loop's state/status.json and lets the Captain drop a steer.

  GET  /              -> index.html
  GET  /status.json   -> the loop's state/status.json (read fresh each request)
  POST /steer         -> writes a `type: steer` drop into inbox/drops/ so it
                         rides the classify_input -> wake path like any steer.

Run:  python3 server.py        (then open http://localhost:8000)

Paths default to the shipkit checkout this file lives in (../../ from here).
Override with env vars if your state/inbox live elsewhere:
  SHIP_ROOT   ship root (default: two dirs up from this file)
  PORT        listen port (default: 8000)
"""

import json
import os
import re
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Default ship root = the shipkit checkout (examples/status-surface/ -> ../../).
SHIP_ROOT = Path(os.environ.get("SHIP_ROOT", HERE.parent.parent)).resolve()
STATUS_PATH = SHIP_ROOT / "state" / "status.json"
DROPS_DIR = SHIP_ROOT / "inbox" / "drops"
PORT = int(os.environ.get("PORT", "8000"))
# Bind localhost only: POST /steer is an unauthenticated write surface — a
# reference dev UI has no business listening on all interfaces. Override HOST
# deliberately if you front it with auth.
HOST = os.environ.get("HOST", "127.0.0.1")

INDEX_HTML = (HERE / "index.html").read_bytes()

# A conservative slug: lowercase, alnum + dashes, capped — keeps drop filenames sane.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text, limit=40):
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return (s[:limit].rstrip("-")) or "steer"


def write_steer(text):
    """Write a well-formed `type: steer` drop. Returns the filename written."""
    DROPS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().astimezone()
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    title = text.strip().splitlines()[0][:72] if text.strip() else "steer"
    name = f"captain-ui-{stamp}-{_slug(title)}.md"
    # YAML-escape: double-quote, backslash-escape inner quotes.
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    doc = (
        "---\n"
        "type: steer\n"
        "source: status-surface\n"
        f'title: "{safe_title}"\n'
        f"created: {now.isoformat()}\n"
        "tags:\n"
        "  - captain-steer\n"
        "---\n\n"
        f"{text.strip()}\n"
    )
    (DROPS_DIR / name).write_text(doc, encoding="utf-8")
    return name


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        elif self.path.startswith("/status.json"):
            try:
                self._send(200, STATUS_PATH.read_bytes())
            except FileNotFoundError:
                self._send(404, json.dumps({"error": f"no status at {STATUS_PATH}"}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/steer":
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            text = json.loads(raw or b"{}").get("text", "")
        except json.JSONDecodeError:
            self._send(400, json.dumps({"error": "bad json"}))
            return
        if not text.strip():
            self._send(400, json.dumps({"error": "empty steer"}))
            return
        name = write_steer(text)
        self._send(200, json.dumps({"ok": True, "drop": name}))

    def log_message(self, *args):
        pass  # quiet by default


if __name__ == "__main__":
    print(f"status-surface: serving http://{HOST}:{PORT}")
    print(f"  status: {STATUS_PATH}")
    print(f"  drops:  {DROPS_DIR}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
