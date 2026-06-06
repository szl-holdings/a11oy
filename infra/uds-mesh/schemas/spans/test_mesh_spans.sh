#!/usr/bin/env bash
# test_mesh_spans.sh — Validates the cross-organ UDS mesh span schemas.
#
# Covers all 5 flagship organs:
#   a11oy.graph.yaml      sentra.gate.yaml     amaru.sync.yaml
#   killinchu.courier.yaml  rosie.decision.yaml
#
# Tests per organ:
#   1. Schema file exists and is non-empty
#   2. Every declared span name appears
#   3. Shared cross-organ DSSE attributes are present (szl.mesh.*)
#   4. JSON schema section present
#   5. Example spans present
#
# Usage: bash schemas/spans/test_mesh_spans.sh
# Exit code: 0 = all passed, 1 = at least one failed.

set -euo pipefail
DIR="schemas/spans"
PASS=0; FAIL=0

check() {
  if eval "$2" > /dev/null 2>&1; then echo "  PASS: $1"; PASS=$((PASS+1));
  else echo "  FAIL: $1"; FAIL=$((FAIL+1)); fi
}

# organ : schema file : space-separated span names
declare -A SCHEMA=(
  [a11oy]="a11oy.graph.yaml"
  [sentra]="sentra.gate.yaml"
  [amaru]="amaru.sync.yaml"
  [killinchu]="killinchu.courier.yaml"
  [rosie]="rosie.decision.yaml"
)
declare -A SPANS=(
  [a11oy]="a11oy.graph.lambda a11oy.graph.automorphism a11oy.graph.position a11oy.graph.gcpn_propose"
  [sentra]="sentra.gate.evaluate sentra.gate.fail_closed sentra.gate.attest"
  [amaru]="amaru.sync.merge amaru.sync.drift_alert amaru.sync.receipt"
  [killinchu]="killinchu.courier.dispatch killinchu.courier.verify killinchu.courier.deliver"
  [rosie]="rosie.decision.evaluate rosie.decision.witness rosie.decision.replay"
)

echo "=== UDS mesh cross-organ span schema tests (5 organs) ==="
for organ in a11oy sentra amaru killinchu rosie; do
  f="$DIR/${SCHEMA[$organ]}"
  echo ""
  echo "── $organ ($f) ──"
  check "schema file exists"     "[ -f '$f' ]"
  check "schema file non-empty"  "[ -s '$f' ]"
  for span in ${SPANS[$organ]}; do
    check "span '$span' defined" "grep -q '$span' '$f'"
  done
  # a11oy uses its original szl.graph.* attribute prefix; the other 4 use the
  # shared cross-organ szl.mesh.* DSSE receipt attributes.
  if [ "$organ" = "a11oy" ]; then
    check "receipt_hash attribute present" "grep -q 'receipt_hash' '$f'"
  else
    check "szl.mesh.organ present"        "grep -q 'szl.mesh.organ' '$f'"
    check "szl.mesh.receipt_hash present" "grep -q 'szl.mesh.receipt_hash' '$f'"
    check "szl.mesh.image_digest present" "grep -q 'szl.mesh.image_digest' '$f'"
    check "szl.mesh.lambda_value present" "grep -q 'szl.mesh.lambda_value' '$f'"
  fi
  check "json_schema section present" "grep -q 'json_schema' '$f'"
  check "examples section present"    "grep -q 'examples' '$f'"
done

echo ""
echo "=== RESULT: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
