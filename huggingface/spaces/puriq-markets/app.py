#!/usr/bin/env python3
"""Thin Hugging Face Space adapter for an A11oy Decision Assurance vertical.

Product logic lives in szl-holdings/a11oy/verticals/. This image evaluates
frozen demonstration cases through the Decision Integrity Kernel. Formulas
have authority NONE. Models and market signals never authorize.

Stdlib only. Listens on PORT (default 7860).
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import a11oy_kernel as kernel  # noqa: E402

SPACE_ID = os.environ.get("SPACE_ID", "SZLHOLDINGS/unknown")
VERTICAL_ID = os.environ.get("VERTICAL_ID", "unknown")
PORT = int(os.environ.get("PORT", "7860"))
GIT_SHA = os.environ.get("SZL_GIT_SHA") or os.environ.get("A11OY_GIT_SHA") or "UNKNOWN"
STATUS = "ROADMAP"

POLICY = json.loads((HERE / "policy_bundle.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((HERE / "vertical_manifest.json").read_text(encoding="utf-8"))
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def build_info() -> dict:
    return {
        "schema": "szl.space-adapter-build-info/v8",
        "space_id": SPACE_ID,
        "vertical_id": VERTICAL_ID,
        "kernel_version": kernel.VERSION,
        "kernel_schema": kernel.SCHEMA,
        "formula_authority": "NONE",
        "status": STATUS,
        "visibility": "private",
        "source_sha": GIT_SHA,
        "canonical_source": f"szl-holdings/a11oy/verticals/{VERTICAL_ID}",
        "adapter": f"szl-holdings/a11oy/huggingface/spaces/{Path(SPACE_ID).name}",
        "limitations": [
            "Demonstration kernel. Does not prove production readiness.",
            "Formulas do not grant authority.",
            "This Space is initially private. Do not claim RUNNING until Hub readback.",
        ],
    }


def html_page() -> bytes:
    cases_js = json.dumps(CASES, ensure_ascii=False)
    title = MANIFEST.get("display_name", VERTICAL_ID)
    wedge = MANIFEST.get("wedge", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} — Decision Assurance</title>
<style>
  :root {{ color-scheme: dark; --bg:#0b0d10; --panel:#14181e; --ink:#e8edf2; --mute:#8b97a4; --line:#2a323c; --deny:#ff6b4a; --ok:#7dffb3; --wait:#ffd36b; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--ink); }}
  main {{ max-width: 980px; margin: 0 auto; padding: 28px 18px 64px; }}
  h1 {{ font-size: 1.6rem; letter-spacing: -0.03em; margin: 0 0 6px; }}
  p {{ color: var(--mute); line-height: 1.5; }}
  .row {{ display:flex; flex-wrap:wrap; gap:8px; margin: 16px 0 22px; }}
  button {{ cursor:pointer; background:#1c232c; color:var(--ink); border:1px solid var(--line); border-radius:999px; padding:8px 14px; }}
  button:hover, button:focus-visible {{ border-color:#6d8cff; outline: none; }}
  pre {{ background: var(--panel); border:1px solid var(--line); border-radius: 12px; padding: 16px; overflow:auto; white-space:pre-wrap; word-break:break-word; }}
  .chip {{ display:inline-block; font-size: 12px; padding: 3px 8px; border-radius: 999px; border:1px solid var(--line); color:var(--mute); margin-right:6px; }}
  .DENIED {{ color: var(--deny); border-color: var(--deny); }}
  .APPROVED {{ color: var(--ok); border-color: var(--ok); }}
  .AWAITING_APPROVAL, .ABSTAINED, .ESCALATED {{ color: var(--wait); border-color: var(--wait); }}
</style>
</head>
<body>
<main>
  <div class="chip">{SPACE_ID}</div>
  <div class="chip">kernel {kernel.VERSION}</div>
  <div class="chip">formula authority NONE</div>
  <div class="chip">{STATUS}</div>
  <h1>{title}</h1>
  <p>{wedge}</p>
  <p>Evaluate a frozen demonstration case. The kernel is fail-closed. Models, formulas and market signals never authorize. This adapter does not own product logic.</p>
  <div class="row" id="cases"></div>
  <div id="status"></div>
  <pre id="out">Select a frozen case.</pre>
</main>
<script>
const CASES = {cases_js};
const root = document.getElementById('cases');
const out = document.getElementById('out');
const status = document.getElementById('status');
for (const item of CASES) {{
  const b = document.createElement('button');
  b.textContent = item.eval_id + ' · ' + item.expected_state;
  b.addEventListener('click', () => run(item));
  root.appendChild(b);
}}
async function run(item) {{
  out.textContent = 'Evaluating ' + item.eval_id + '…';
  const res = await fetch('/api/evaluate', {{
    method: 'POST',
    headers: {{ 'content-type': 'application/json' }},
    body: JSON.stringify(item.payload),
  }});
  const data = await res.json();
  const state = data.state || 'UNKNOWN';
  status.innerHTML = '<span class="chip ' + state + '">' + state + '</span>'
    + '<span class="chip">' + (data.reason_codes || []).join(', ') + '</span>'
    + '<span class="chip">digest ' + ((data.receipt && data.receipt.digest) || '').slice(0,12) + '</span>';
  out.textContent = JSON.stringify(data, null, 2);
}}
</script>
</body>
</html>
""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "a11oy-packet8-adapter/8.0.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        raw = json.dumps(obj, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self):
        length = int(self.headers.get("content-length") or "0")
        if length <= 0 or length > 1_000_000:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, html_page(), "text/html; charset=utf-8")
            return
        if path in {"/api/livez", "/healthz", "/health"}:
            self._json(200, {"ok": True, "status": STATUS, "space_id": SPACE_ID})
            return
        if path == "/api/build-info":
            self._json(200, build_info())
            return
        if path == "/api/policy":
            self._json(200, POLICY)
            return
        if path == "/api/manifest":
            self._json(200, MANIFEST)
            return
        if path == "/api/cases":
            self._json(200, CASES)
            return
        self._json(404, {"error": "not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()
        if payload is None:
            self._json(400, {"error": "expected JSON body"})
            return
        if path == "/api/evaluate":
            self._json(200, kernel.evaluate(payload))
            return
        if path == "/api/scan":
            self._json(200, kernel.scan_memo(str(payload.get("text") or "")))
            return
        if path == "/api/replay":
            self._json(200, kernel.replay_receipt(payload if isinstance(payload, dict) else {}))
            return
        self._json(404, {"error": "not found", "path": path})


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sys.stderr.write(
        "packet8 adapter %s vertical=%s kernel=%s port=%s status=%s\n"
        % (SPACE_ID, VERTICAL_ID, kernel.VERSION, PORT, STATUS)
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
