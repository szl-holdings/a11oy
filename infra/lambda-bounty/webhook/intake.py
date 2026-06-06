#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SZL Holdings — Λ-Bounty webhook intake receiver.
# Sign: Yachay <yachay@szlholdings.dev>
#
# A WORKING webhook surface for Conjecture 1 (Λ-aggregator uniqueness) bounty
# submissions. Validates the payload against submission.schema.json, emits a
# hash-chained Khipu intake receipt, and (when GITHUB_TOKEN is present) opens a
# tracking issue on szl-holdings/lambda-bounty.
#
# HONESTY: a webhook receipt acknowledges INTAKE only. Eligibility for the
# founder-set award is decided SOLELY by the verify-proof CI on the linked PR.
# This receiver never declares a winner and never moves money.
#
# Run standalone:        python intake.py            # tiny stdlib HTTP server on :8099
# Run as FastAPI app:    uvicorn intake:app          # if fastapi/uvicorn installed
# Mount under a11oy at:  POST /api/lambda-bounty/submit
#
# Endpoints:
#   GET  /healthz                       -> liveness + conjecture status
#   POST /api/lambda-bounty/submit      -> validate + receipt
#   GET  /api/lambda-bounty/receipts    -> intake receipt ledger (append-only)

import json, os, re, hashlib, hmac, datetime, pathlib, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "submission.schema.json").read_text())
LEDGER = HERE.parent / "submissions" / "receipts" / "intake_ledger.jsonl"
SIGN_KEY = os.environ.get("LAMBDA_BOUNTY_HMAC_KEY", "dev-key-not-for-prod").encode()
PR_RE = re.compile(r"^https://github\.com/szl-holdings/lambda-bounty/pull/\d+$")
ALLOWED_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}

CONJECTURE = {
    "id": "Conjecture 1",
    "formula": "F23",
    "status": "OPEN — NOT a theorem",
    "statement": "Any two 9-axis aggregators satisfying A1 idempotence, A2 monotonicity, "
                 "A3 symmetry, A4 zero-absorption agree on every input.",
    "arbiter": "verify-proof CI on a PR to szl-holdings/lambda-bounty (sole, no-bypass)",
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate(payload: dict) -> list[str]:
    """Minimal stdlib JSON-Schema check for the fields we enforce. Returns error list."""
    errs = []
    req = SCHEMA["required"]
    for k in req:
        if k not in payload:
            errs.append(f"missing required field: {k}")
    if "pr_url" in payload and not PR_RE.match(str(payload["pr_url"])):
        errs.append("pr_url must be https://github.com/szl-holdings/lambda-bounty/pull/<n>")
    if payload.get("lean_toolchain") not in (None, "leanprover/lean4:v4.13.0"):
        errs.append("lean_toolchain must be leanprover/lean4:v4.13.0")
    if payload.get("sorry_free_claim") is not True:
        errs.append("sorry_free_claim must be true (CI verifies independently)")
    sub = payload.get("submitter")
    if not isinstance(sub, dict) or not sub.get("name"):
        errs.append("submitter.name is required")
    # informational axiom pre-check (CI is authoritative)
    ap = payload.get("axiom_print", "")
    if ap:
        found = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", ap))
        extra = {a for a in found if a in {"sorryAx"}} or (found & {"Lean.ofReduceBool"})
        if "sorryAx" in found:
            errs.append("axiom_print contains sorryAx — proof is incomplete")
    return errs


def _prev_hash() -> str:
    if not LEDGER.exists():
        return "genesis"
    last = None
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            last = line
    if not last:
        return "genesis"
    return json.loads(last).get("hash", "genesis")


def make_receipt(payload: dict, accepted: bool, errors: list[str]) -> dict:
    prev = _prev_hash()
    body = {
        "receipt_type": "lambda_bounty_intake",
        "conjecture": "Conjecture 1 (F23 Λ-aggregator uniqueness)",
        "ts": _now(),
        "submitter": payload.get("submitter", {}).get("name", "?"),
        "pr_url": payload.get("pr_url"),
        "accepted_intake": accepted,
        "errors": errors,
        "eligibility_note": "Intake acknowledgement only. Award eligibility = verify-proof CI green on the PR.",
        "prev": prev,
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    sig = hmac.new(SIGN_KEY, digest.encode(), hashlib.sha256).hexdigest()
    body["hash"] = digest
    body["hmac_sha256"] = sig
    return body


def append_ledger(receipt: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(receipt) + "\n")


def maybe_open_issue(payload: dict, receipt: dict):
    """If a GITHUB_TOKEN is present, open a tracking issue. Best-effort, never fatal."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    url = "https://api.github.com/repos/szl-holdings/lambda-bounty/issues"
    data = json.dumps({
        "title": f"[Λ-bounty intake] {payload.get('submitter',{}).get('name','?')} · {payload.get('pr_url','')}",
        "body": f"Automated intake receipt `{receipt['hash'][:12]}`.\n\n"
                f"PR: {payload.get('pr_url')}\n"
                f"Eligibility is decided by `verify-proof` CI on the PR (sole arbiter).\n\n"
                f"```json\n{json.dumps(receipt, indent=2)}\n```",
        "labels": ["lambda-bounty", "conjecture-1", "intake"],
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "lambda-bounty-intake",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("html_url")
    except Exception as e:  # noqa: BLE001 — best-effort
        return f"issue-open-failed: {e}"


def handle_submit(payload: dict) -> tuple[int, dict]:
    errors = validate(payload)
    accepted = len(errors) == 0
    receipt = make_receipt(payload, accepted, errors)
    append_ledger(receipt)
    issue = maybe_open_issue(payload, receipt) if accepted else None
    return (200 if accepted else 422), {"accepted_intake": accepted, "errors": errors,
                                        "receipt": receipt, "tracking_issue": issue}


# ----------------------------- FastAPI (optional) ----------------------------
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, PlainTextResponse

    app = FastAPI(title="Λ-Bounty Intake", version="1.0.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "lambda-bounty-intake", "conjecture": CONJECTURE}

    @app.post("/api/lambda-bounty/submit")
    async def submit(req: Request):
        payload = await req.json()
        code, body = handle_submit(payload)
        return JSONResponse(status_code=code, content=body)

    @app.get("/api/lambda-bounty/receipts")
    def receipts():
        if not LEDGER.exists():
            return PlainTextResponse("", media_type="application/x-ndjson")
        return PlainTextResponse(LEDGER.read_text(), media_type="application/x-ndjson")
except Exception:  # noqa: BLE001 — FastAPI not installed; stdlib server below still works
    app = None


# --------------------------- stdlib fallback server --------------------------
def _serve(port=8099):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj, ctype="application/json"):
            body = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/healthz":
                self._send(200, {"status": "ok", "service": "lambda-bounty-intake", "conjecture": CONJECTURE})
            elif self.path == "/api/lambda-bounty/receipts":
                self._send(200, LEDGER.read_text() if LEDGER.exists() else "", "application/x-ndjson")
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/lambda-bounty/submit":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
            code, body = handle_submit(payload)
            self._send(code, body)

        def log_message(self, *a):  # quiet
            pass

    print(f"Λ-bounty intake on :{port} — POST /api/lambda-bounty/submit")
    HTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    _serve(int(os.environ.get("PORT", "8099")))
