#!/usr/bin/env bash
# test_graph_spans.sh — Validates the a11oy.graph.* OTEL span schema
#
# Tests:
#   1. Schema file exists and is non-empty
#   2. All four span names are present
#   3. All required common SZL attributes are defined
#   4. JSON schema section is present
#   5. Example spans cover all four span types
#
# Usage: bash schemas/spans/test_graph_spans.sh
# Exit code: 0 = all tests passed, 1 = at least one test failed.

set -euo pipefail

SCHEMA_FILE="schemas/spans/a11oy.graph.yaml"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== a11oy.graph.* span schema tests (v17.2) ==="
echo ""
echo "Schema file: $SCHEMA_FILE"
echo ""

# Test 1: file exists and is non-empty
check "Schema file exists" "[ -f '$SCHEMA_FILE' ]"
check "Schema file is non-empty" "[ -s '$SCHEMA_FILE' ]"

# Test 2: all four span names present
check "Span 'a11oy.graph.lambda' defined"        "grep -q 'a11oy.graph.lambda'       '$SCHEMA_FILE'"
check "Span 'a11oy.graph.automorphism' defined"  "grep -q 'a11oy.graph.automorphism' '$SCHEMA_FILE'"
check "Span 'a11oy.graph.position' defined"      "grep -q 'a11oy.graph.position'     '$SCHEMA_FILE'"
check "Span 'a11oy.graph.gcpn_propose' defined"  "grep -q 'a11oy.graph.gcpn_propose' '$SCHEMA_FILE'"

# Test 3: required common SZL attributes defined
check "Attribute 'szl.graph.lambda_value' defined"    "grep -q 'szl.graph.lambda_value'    '$SCHEMA_FILE'"
check "Attribute 'szl.graph.v_count' defined"         "grep -q 'szl.graph.v_count'         '$SCHEMA_FILE'"
check "Attribute 'szl.graph.e_count' defined"         "grep -q 'szl.graph.e_count'         '$SCHEMA_FILE'"
check "Attribute 'szl.graph.receipt_hash' defined"    "grep -q 'szl.graph.receipt_hash'    '$SCHEMA_FILE'"
check "Attribute 'szl.graph.governance_drift' defined" "grep -q 'szl.graph.governance_drift' '$SCHEMA_FILE'"

# Test 4: JSON schema section present
check "JSON schema section present"   "grep -q 'json_schema' '$SCHEMA_FILE'"
check "JSON schema required fields"   "grep -q 'required' '$SCHEMA_FILE'"

# Test 5: example spans cover all four types
check "Example for 'a11oy.graph.lambda' present"       "grep -q 'span: a11oy.graph.lambda'       '$SCHEMA_FILE'"
check "Example for 'a11oy.graph.automorphism' present" "grep -q 'span: a11oy.graph.automorphism' '$SCHEMA_FILE'"
check "Example for 'a11oy.graph.position' present"     "grep -q 'span: a11oy.graph.position'     '$SCHEMA_FILE'"
check "Example for 'a11oy.graph.gcpn_propose' present" "grep -q 'span: a11oy.graph.gcpn_propose' '$SCHEMA_FILE'"

# Test 6: Lean theorem citations present
check "V17.2-T1 citation present" "grep -q 'V17.2-T1' '$SCHEMA_FILE'"
check "V17.2-T2 citation present" "grep -q 'V17.2-T2' '$SCHEMA_FILE'"
check "V17.2-T3 citation present" "grep -q 'V17.2-T3' '$SCHEMA_FILE'"

# Test 7: upstream paper citations present
check "You et al. 2020 citation (graph2nn)"  "grep -q 'arXiv:2007.06559' '$SCHEMA_FILE'"
check "You et al. 2019 citation (P-GNN)"     "grep -q 'arXiv:1906.04817' '$SCHEMA_FILE'"
check "You et al. 2018 citation (GraphRNN)"  "grep -q 'arXiv:1802.08773' '$SCHEMA_FILE'"
check "You et al. 2018 citation (GCPN)"      "grep -q 'arXiv:1806.02473' '$SCHEMA_FILE'"
check "Fey & Lenssen 2019 citation (PyG)"    "grep -q 'pytorch_geometric' '$SCHEMA_FILE'"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
