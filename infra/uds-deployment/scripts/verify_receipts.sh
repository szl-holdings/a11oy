#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# verify_receipts.sh — Post-demo receipt chain verification
#
# Usage:
#   bash scripts/verify_receipts.sh
#   # or:
#   uds run demo:verify
#
# What this does:
#   1. Port-forwards the receipts server to localhost:9999
#   2. Fetches all stored receipts via GET /receipts
#   3. For each receipt:
#      a. Decodes the DSSE payload
#      b. Recomputes the HMAC-SHA-256 and compares to the stored signature
#      c. Prints PASS/FAIL per receipt
#   4. Shows the Kubernetes annotations on the demo workload
#
# Exit codes:
#   0 — all receipts verified
#   1 — at least one verification failed or server unreachable

set -euo pipefail

NAMESPACE="szl-receipts"
SVC="szl-receipts-server"
LOCAL_PORT="9999"
HMAC_KEY_B64="${SZL_HMAC_KEY:-c3psLWRldi1kZW1vLWtleS0yMDI2LXdhcmhhY2tlcg==}"

# ── Step 1: Port-forward ──────────────────────────────────────────────────────
echo "── SZL Receipt Verification ────────────────────────────────────────"
echo "Port-forwarding ${SVC}:8080 → localhost:${LOCAL_PORT}…"
kubectl port-forward "svc/${SVC}" "${LOCAL_PORT}:8080" -n "${NAMESPACE}" &
PF_PID=$!
# Preserve the script's intended exit status across cleanup: capture $? on
# entry to the trap and re-exit with it, so a failed `kill` (e.g. the
# port-forward already gone) cannot flip a PASS into a non-zero exit or vice
# versa.
cleanup() {
  rc=$?
  kill "$PF_PID" 2>/dev/null || true
  echo "Port-forward stopped."
  exit "$rc"
}
trap cleanup EXIT
sleep 2

# ── Step 2: Fetch receipts ────────────────────────────────────────────────────
echo "Fetching receipts from http://localhost:${LOCAL_PORT}/receipts…"
RECEIPTS_JSON=$(curl -sf "http://localhost:${LOCAL_PORT}/receipts") || {
  echo "ERROR: Could not reach receipts server. Is the bundle deployed?"
  exit 1
}

RECEIPT_COUNT=$(echo "${RECEIPTS_JSON}" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "Found ${RECEIPT_COUNT} receipt(s)."
echo ""

# ── Step 3: Verify each receipt ───────────────────────────────────────────────
PASS=0; FAIL=0

# The receipts JSON is passed via the environment, not stdin: a here-doc-fed
# `python3 - <<'PYEOF'` already binds stdin to the script body, so piping the
# receipts into the same process made sys.stdin.read() return the Python source
# instead of the data. We capture the verifier's exit status, then still run
# Step 4, and finally exit with the captured status so the documented exit-code
# contract (1 = a verification failed) is honoured rather than masked.
VERIFY_RC=0
RECEIPTS_JSON="${RECEIPTS_JSON}" python3 - "${HMAC_KEY_B64}" << 'PYEOF' || VERIFY_RC=$?
import os, sys, json, base64, hmac, hashlib

receipts_json = os.environ["RECEIPTS_JSON"]
hmac_key_b64  = sys.argv[1]

try:
    key_bytes = base64.b64decode(hmac_key_b64)
except Exception:
    print("WARN: Could not decode HMAC key — skipping signature verification")
    key_bytes = b""

receipts = json.loads(receipts_json)
pass_count = 0
fail_count = 0

for r in receipts:
    rid      = r.get("id", "?")[:16]
    envelope = r.get("envelope", {})
    ts       = r.get("timestamp", "?")
    is_valid = r.get("valid", False)

    # Decode payload
    payload_b64 = envelope.get("payload", "")
    try:
        payload = json.loads(base64.b64decode(payload_b64))
    except Exception:
        payload = {}

    subject  = payload.get("subject", "(unknown)")
    spec_hash = payload.get("specHash", "")[:16] + "…"
    op       = payload.get("admissionOp", "?")

    # Re-verify HMAC
    sigs = envelope.get("signatures", [])
    if sigs and key_bytes:
        sig_b64 = sigs[0].get("sig", "")
        expected = hmac.new(key_bytes, base64.b64decode(payload_b64), hashlib.sha256).digest()
        actual   = base64.b64decode(sig_b64) if sig_b64 else b""
        local_verify = hmac.compare_digest(expected, actual)
    else:
        local_verify = False

    status = "PASS" if local_verify else "UNVERIFIED (demo key mismatch or unsigned)"
    icon   = "✓" if local_verify else "○"
    if local_verify:
        pass_count += 1
    else:
        fail_count += 1

    print(f"  {icon} {rid}…  {ts}  op={op}  subject={subject}")
    print(f"       specHash={spec_hash}  status={status}")
    print()

print(f"── Summary: {pass_count} VERIFIED, {fail_count} UNVERIFIED out of {len(receipts)} receipts")
if fail_count > 0:
    print("   NOTE: Unverified receipts may indicate a key mismatch or demo mode (unsigned).")
    print("   In production, replace SZL_HMAC_KEY with the live key and use Ed25519.")
sys.exit(0 if fail_count == 0 else 1)
PYEOF

# ── Step 4: Show K8s annotations ─────────────────────────────────────────────
echo ""
echo "── K8s annotations on demo Deployment ─────────────────────────────"
kubectl get deployment szl-demo-agent -n szl-demo-workload \
  -o jsonpath='{range .metadata.annotations}{@}{"\n"}{end}' 2>/dev/null | \
  grep "szl\." || echo "(szl-demo-workload/szl-demo-agent not found — run demo:workload first)"

echo ""
echo "── K8s annotations on demo Job ─────────────────────────────────────"
kubectl get job szl-demo-job -n szl-demo-workload \
  -o jsonpath='{range .metadata.annotations}{@}{"\n"}{end}' 2>/dev/null | \
  grep "szl\." || echo "(szl-demo-workload/szl-demo-job not found — run demo:workload first)"

echo ""
if [ "${VERIFY_RC}" -eq 0 ]; then
  echo "Verification complete — all receipts verified."
else
  echo "Verification complete — one or more receipts did not verify (exit ${VERIFY_RC})."
fi

# Propagate the verification result so callers and pre-flight scripts see a
# non-zero exit when a receipt failed, rather than the exit code of Step 4.
exit "${VERIFY_RC}"
