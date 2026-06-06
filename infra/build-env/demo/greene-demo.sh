#!/usr/bin/env bash
# greene-demo.sh — scripted demo for the June 9 meeting.
#
# Golden narrative:
#   1. Bring up the full stack on kind (5 organs + Istio ambient + OTel).
#   2. Run the honest cosign + SLSA gate — show NOTHING is faked.
#   3. Send one test request and watch a single traceparent propagate across organs.
#   4. Show the DSSE receipt chain (stub-honest until COSIGN secret is wired).
#
# Designed to be paused between beats. Set DEMO_AUTO=1 to run start-to-finish.
set -uo pipefail
cd "$(dirname "$0")/.."

NAMESPACE="${NAMESPACE:-szl}"
DEMO_AUTO="${DEMO_AUTO:-0}"

bold(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
pause(){ [ "$DEMO_AUTO" = "1" ] && return; read -rp $'\n[enter to continue] '; }

bold "SZL Build Env demo — Doctrine v11 749/14/163 @ c7c0ba17 (NOT Iron Bank)"
echo "Mesh: Istio ambient (ztunnel + waypoint). Telemetry: OpenTelemetry -> Jaeger."
pause

bold "Beat 1/4 — bring up the whole stack"
echo "\$ make up"
make up
pause

bold "Beat 2/4 — honest supply-chain gate (cosign + slsa-verifier, fail-closed)"
echo "Watch: killinchu shows KNOWN-GAP (private image) — we do not fake it green."
echo "\$ make verify"
make verify || true
pause

bold "Beat 3/4 — one request, one traceparent, across all organs"
echo "\$ make trace"
make trace || true
echo ""
echo "Open the trace tree in Jaeger:  http://localhost:16686"
pause

bold "Beat 4/4 — DSSE receipt chain"
echo "The OTel collector promotes szl.dsse.receipt attributes onto each span so the"
echo "receipt chain is queryable. NOTE (honest): signatures are stub-unverified until"
echo "a real COSIGN_KEY / Sigstore identity is wired — see HONEST_GAPS.md § DSSE."
echo ""
echo "Receipt chain spans for the demo trace:"
kubectl -n "$NAMESPACE" logs deploy/opentelemetry-collector 2>/dev/null \
  | grep -i "szl.dsse" | tail -20 \
  || echo "   (no DSSE attributes emitted yet — organs must set szl.dsse.receipt; stub gap)"
pause

bold "Demo complete"
echo "Verdict matrix above is the honest state. To reset:  make down"
