#!/usr/bin/env python3
"""
check_a11oy_api_health.py — standing health check for a11oy's live demo API.

a11oy auto-syncs its serve.py from GitHub main to the Hugging Face Space
(hf-sync-backend.yml) and an OID-diff guard (hf-module-drift-check) confirms the
files match. But a sync can succeed yet a LIVE endpoint still 500 or drop its
governed envelope — and the front-door smoke monitor only checks HTTP 200 on the
Space shell, so it would stay green while every /api/a11oy/* path quietly served
the SPA HTML with a 200.

This script probes the governed operator/reason capability surface (marker
``a11oy-operator-reason-envelope-task516`` in serve.py) on one or more live
targets and FAILS (non-zero exit) if any endpoint regresses: non-200, a
content-type that is not application/json (the SPA-HTML fallback), an
unparseable / non-object body, or a missing contract key. Transient
rebuild/restart states are tolerated via bounded retries.

The governed reasoning/operator endpoints carry the full Doctrine envelope
{status, citations, fetchedAt, doctrine}. operator/recommend and operator/ledger
have their OWN contract shapes (no governed envelope), so each endpoint declares
exactly the keys it must carry — requiring keys an endpoint never emits would
make the check uselessly red.

Stdlib only (urllib) so it runs on a clean ubuntu-latest with no `pip install`
and no third-party GitHub Action (org policy: github-owned/verified actions only).

Usage:
  check_a11oy_api_health.py \
      --target hf=https://szlholdings-a11oy.hf.space \
      [--target box=https://a11oy.net] \
      [--summary-file out.json] [--attempts 5] [--sleep 15] [--timeout 20]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# Each check: HTTP method, path, optional JSON body, and the contract key(s) the
# response MUST carry. The governed reasoning/operator surfaces carry the full
# Doctrine envelope {status, citations, fetchedAt, doctrine}; /healthz is the
# lightweight liveness probe (carries `status`); operator/recommend and
# operator/ledger have their own contract shapes (no governed envelope).
ENVELOPE = ["status", "citations", "fetchedAt", "doctrine"]
CHECKS = [
    {"method": "GET", "path": "/healthz", "required": ["status"]},
    {"method": "GET", "path": "/api/a11oy/v1/operator/ask", "required": ENVELOPE},
    {"method": "GET", "path": "/api/a11oy/v1/reason", "required": ENVELOPE},
    {"method": "GET", "path": "/api/a11oy/v1/reason/readiness", "required": ENVELOPE},
    {"method": "GET", "path": "/api/a11oy/v1/operator/recommend", "required": ["citations", "recommendations"]},
    {"method": "GET", "path": "/api/a11oy/v1/operator/ledger", "required": ["receipts", "root_hash"]},
    {
        "method": "POST",
        "path": "/api/a11oy/v2/operator/command",
        # approved:false -> the governed loop WITHHOLDS execution (safe to probe).
        "body": {"command": "acknowledge alert", "target": "demo", "approved": False},
        "required": ENVELOPE + ["outcome"],
    },
    # --- console DATA tabs ------------------------------------------------------
    # These back the live /console tabs. They do NOT carry the governed reasoning
    # envelope; each has its own JSON contract. Several carry an ``honest`` flag
    # (the doctrine honesty marker) — requiring it here means a tab that quietly
    # drops its honesty disclosure also turns the check red, not just a 500.
    {"method": "GET", "path": "/api/a11oy/v1/formulas", "required": ["count", "formulas"]},
    {"method": "GET", "path": "/api/a11oy/v1/bounties", "required": ["count", "bounties", "honest"]},
    {"method": "GET", "path": "/api/a11oy/v1/contracting", "required": ["areas", "summary", "honest"]},
    {"method": "GET", "path": "/api/a11oy/v1/readiness", "required": ["sections", "summary", "honest"]},
    {"method": "GET", "path": "/api/a11oy/v1/evidence", "required": ["claims", "total_assertions", "status_counts"]},
    # --- HITL (human-in-the-loop) action ring -----------------------------------
    # operator/act is the SHA-256 hash-chained HITL action ring. "acknowledge" is
    # a safe, enumerated action — it records ONLY into the in-process audit ring
    # (resets on restart, bounded), executes no real action; this is the same
    # probe the in-process CI test uses. It carries the governed envelope PLUS the
    # action-ring record, so require the envelope AND ok/entry/audit_depth.
    {
        "method": "POST",
        "path": "/api/a11oy/v1/operator/act",
        "body": {"action": "acknowledge", "target": "health-probe", "note": "scheduled health check"},
        "required": ENVELOPE + ["ok", "entry", "audit_depth"],
    },
    # --- MCP tools surface ------------------------------------------------------
    # /v1/mcp/tools is the MCP manifest. It does NOT carry the governed envelope —
    # it declares {count, tools, flagship, ...}. Do NOT pin the count: it grows as
    # the canonical-formula tools register and live sibling-flagship MCP surfaces
    # merge in (observed 11 live; older docs say "4 real" host tools). Requiring
    # key presence still catches the SPA-HTML-200 / dropped-contract regression.
    {"method": "GET", "path": "/api/a11oy/v1/mcp/tools", "required": ["count", "tools", "flagship"]},
    # The 3 canonical-formula MCP tools GENUINELY execute via /v1/mcp/call (not a
    # stub) — backed by szl_anatomy_routes -> szl_formulas. Each call response has
    # its OWN {tool, status, ...} contract (no governed envelope). All three share
    # the same path, so a per-check ``label`` keeps the output unambiguous. If the
    # formula registry ever stops importing in-process the call 503s -> red, which
    # is the regression we want surfaced.
    {"method": "POST", "path": "/api/a11oy/v1/mcp/call", "label": "list_formulas",
     "body": {"name": "list_formulas"}, "required": ["tool", "status", "formulas"]},
    {"method": "POST", "path": "/api/a11oy/v1/mcp/call", "label": "run_formula",
     "body": {"name": "run_formula", "arguments": {"name": "lambda_aggregate", "args": [[0.9, 0.92, 0.95]]}},
     "required": ["tool", "status", "result"]},
    {"method": "POST", "path": "/api/a11oy/v1/mcp/call", "label": "formula_proof_status",
     "body": {"name": "formula_proof_status", "arguments": {"name": "lambda_aggregate"}},
     "required": ["tool", "status", "proof_status"]},
]


def evaluate(status_code, content_type, body_bytes, required):
    """Pure check of one HTTP response. Returns (ok: bool, reason: str).

    A regression is: not 200, content-type not application/json (the SPA-HTML
    fallback returning 200), an unparseable / non-object body, or a missing
    contract key.
    """
    if status_code != 200:
        return False, f"HTTP {status_code} (want 200)"
    ct = (content_type or "").lower()
    if "application/json" not in ct:
        return False, (
            f"content-type '{content_type or 'none'}' is not application/json "
            "(likely SPA HTML)"
        )
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any decode/parse error is a regression
        return False, f"body is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return False, "JSON payload is not an object"
    missing = [f for f in required if f not in data]
    if missing:
        return False, f"missing contract key(s): {', '.join(missing)}"
    return True, "ok"


def probe_once(url, method, body, timeout):
    """Single HTTP request. Returns (status_code, content_type, body_bytes, err)."""
    headers = {
        "User-Agent": "a11oy-api-health/1.0",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.headers.get("Content-Type", ""), resp.read(), None
    except urllib.error.HTTPError as exc:
        rbody = b""
        try:
            rbody = exc.read()
        except Exception:  # noqa: BLE001
            pass
        ct = exc.headers.get("Content-Type", "") if exc.headers else ""
        return exc.code, ct, rbody, None
    except Exception as exc:  # noqa: BLE001 - URLError / timeout / DNS / TLS
        return 0, "", b"", str(exc)


def check_endpoint(base, chk, attempts, sleep_s, timeout):
    """Probe one endpoint with bounded retries. Returns (ok, reason, url)."""
    url = base.rstrip("/") + chk["path"]
    method = chk.get("method", "GET")
    body = chk.get("body")
    required = chk["required"]
    last = "no attempt made"
    for attempt in range(1, attempts + 1):
        code, ct, rbody, err = probe_once(url, method, body, timeout)
        if err is not None:
            last = f"request error: {err}"
        else:
            ok, reason = evaluate(code, ct, rbody, required)
            if ok:
                return True, f"200 application/json, contract OK (attempt {attempt})", url
            last = reason
        if attempt < attempts:
            time.sleep(sleep_s)
    return False, f"{last} (sustained over {attempts} attempts)", url


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="a11oy live demo API health check (governed envelope / contract keys)."
    )
    ap.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="LABEL=BASE_URL",
        help="Target to probe, e.g. hf=https://szlholdings-a11oy.hf.space (repeatable).",
    )
    ap.add_argument("--attempts", type=int, default=5, help="Retry attempts per endpoint (default 5).")
    ap.add_argument("--sleep", type=float, default=15.0, help="Seconds between retries (default 15).")
    ap.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout seconds (default 20).")
    ap.add_argument("--summary-file", default="", help="Optional path to write a JSON result summary.")
    args = ap.parse_args(argv)

    if not args.target:
        print("ERROR: at least one --target LABEL=BASE_URL is required", file=sys.stderr)
        return 2

    targets = []
    for t in args.target:
        if "=" not in t:
            print(f"ERROR: bad --target '{t}', expected LABEL=BASE_URL", file=sys.stderr)
            return 2
        label, base = t.split("=", 1)
        label, base = label.strip(), base.strip()
        if not label or not base:
            print(f"ERROR: bad --target '{t}', expected non-empty LABEL=BASE_URL", file=sys.stderr)
            return 2
        targets.append((label, base))

    checked = 0
    passed = 0
    failures = []
    print(
        f"a11oy live API health check — {len(targets)} target(s) x "
        f"{len(CHECKS)} endpoint(s) (attempts={args.attempts}, sleep={args.sleep}s)"
    )
    for label, base in targets:
        print(f"\n== target: {label} ({base}) ==")
        for chk in CHECKS:
            checked += 1
            ok, reason, url = check_endpoint(base, chk, args.attempts, args.sleep, args.timeout)
            tag = f"{chk.get('method', 'GET')} {chk['path']}"
            if chk.get("label"):
                # Several checks (the MCP tool calls) share one path; the label
                # keeps PASS/FAIL lines and the summary unambiguous.
                tag += f" [{chk['label']}]"
            if ok:
                passed += 1
                print(f"  PASS {tag:<54} {reason}")
            else:
                print(f"  FAIL {tag:<54} {reason}")
                failures.append(
                    {"target": label, "url": url, "method": chk.get("method", "GET"),
                     "path": chk["path"], "label": chk.get("label", ""), "reason": reason}
                )

    failed = len(failures)
    print(f"\nRESULT: checked={checked} passed={passed} failed={failed}")

    summary = {"checked": checked, "passed": passed, "failed": failed, "failures": failures}
    if args.summary_file:
        with open(args.summary_file, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"Wrote summary -> {args.summary_file}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
