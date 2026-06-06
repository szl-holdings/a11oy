#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# smoke-test.sh — durability + chain-continuity smoke test for szl-receipts.
#
# What it proves (PhD Systems Scope 6):
#   1. POST 3 receipts into the running server.
#   2. Record the 3rd receipt's chain hash.
#   3. Delete the pod (forces reschedule onto the PVC).
#   4. Wait for the pod to come back and rehydrate the chain from disk.
#   5. POST a 4th receipt and assert its chain.prev_hash == the 3rd's hash.
#
# Prints PASS or FAIL and exits non-zero on FAIL.
#
# Usage: ./scripts/smoke-test.sh [namespace]
#   namespace defaults to "szl-receipts".
#
# Requires: kubectl with access to the target cluster, jq.

set -euo pipefail

NS="${1:-szl-receipts}"
SELECTOR="app.kubernetes.io/name=szl-receipts-server"
PORT="${SZL_PORT:-8080}"
CONTAINER="receipts-server"

fail() { echo "FAIL: $*" >&2; exit 1; }

command -v kubectl >/dev/null || fail "kubectl not found"
command -v jq >/dev/null || fail "jq not found"

pod_name() {
  kubectl -n "$NS" get pods -l "$SELECTOR" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

wait_ready() {
  echo "Waiting for pod readiness (selector: $SELECTOR)…"
  kubectl -n "$NS" wait --for=condition=Ready pod -l "$SELECTOR" --timeout=120s \
    || fail "pod did not become Ready"
}

# POST a receipt from inside the pod (avoids needing ingress / port-forward).
# Echoes the JSON response.
post_receipt() {
  local pod="$1" subject="$2"
  kubectl -n "$NS" exec "$pod" -c "$CONTAINER" -- \
    python3 -c "
import json,urllib.request,sys
body=json.dumps({'subject':'$subject','smoke':True}).encode()
req=urllib.request.Request('http://127.0.0.1:$PORT/receipt',data=body,headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req,timeout=5).read().decode())
"
}

echo "== szl-receipts smoke test (namespace: $NS) =="
wait_ready
POD="$(pod_name)"; [ -n "$POD" ] || fail "no pod found"
echo "Target pod: $POD"

echo "-- POST 3 receipts --"
R1="$(post_receipt "$POD" "smoke/Deployment/one")"
R2="$(post_receipt "$POD" "smoke/Deployment/two")"
R3="$(post_receipt "$POD" "smoke/Deployment/three")"
echo "r1: $R1"
echo "r2: $R2"
echo "r3: $R3"

H3="$(echo "$R3" | jq -r '.chain.hash')"
IDX3="$(echo "$R3" | jq -r '.chain.chain_index')"
[ "$H3" != "null" ] && [ -n "$H3" ] || fail "could not read 3rd receipt chain.hash"
echo "3rd receipt: chain_index=$IDX3 hash=$H3"

echo "-- restart pod (delete; controller reschedules onto the PVC) --"
kubectl -n "$NS" delete pod -l "$SELECTOR" --wait=true
wait_ready
POD2="$(pod_name)"; [ -n "$POD2" ] || fail "no pod after restart"
echo "New pod: $POD2"

echo "-- confirm rehydration log --"
REHYDRATED="$(kubectl -n "$NS" logs "$POD2" -c "$CONTAINER" 2>/dev/null | grep -i 'Rehydrated' | tail -1 || true)"
echo "${REHYDRATED:-<no rehydrate log line found yet>}"

echo "-- POST 4th receipt and check chain continuity --"
R4="$(post_receipt "$POD2" "smoke/Deployment/four")"
echo "r4: $R4"
PREV4="$(echo "$R4" | jq -r '.chain.prev_hash')"
IDX4="$(echo "$R4" | jq -r '.chain.chain_index')"
echo "4th receipt: chain_index=$IDX4 prev_hash=$PREV4"

if [ "$PREV4" = "$H3" ]; then
  echo "Chain continuity: 4th.prev_hash == 3rd.hash ($H3)"
  if [ "$IDX4" = "$((IDX3 + 1))" ]; then
    echo "Index continuity: 4th.chain_index ($IDX4) == 3rd.chain_index+1"
    echo "PASS"
    exit 0
  else
    fail "index discontinuity: expected $((IDX3 + 1)), got $IDX4"
  fi
else
  fail "chain broken across restart: 4th.prev_hash=$PREV4 != 3rd.hash=$H3"
fi
