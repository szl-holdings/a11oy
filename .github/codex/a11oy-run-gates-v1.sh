#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
set -uo pipefail

OUTPUT_DIR="${CODEX_GATE_OUTPUT_DIR:-.codex-output/gates}"
TIMEOUT_SECONDS="${CODEX_GATE_TIMEOUT:-1800}"
mkdir -p "$OUTPUT_DIR/logs"
RESULTS_TSV="$OUTPUT_DIR/results.tsv"
RESULTS_JSON="$OUTPUT_DIR/results.json"
: > "$RESULTS_TSV"
FAILURES=0
BLOCKED_REQUIRED=0

# Provider, GitHub, model, database, and deployment credentials must not enter
# repository tests after Codex has completed.
unset OPENAI_API_KEY CODEX_API_KEY A11OY_GITHUB_TOKEN GH_TOKEN GITHUB_TOKEN \
  HF_TOKEN HUGGING_FACE_HUB_TOKEN FIREWORKS_API_KEY FIREWORKS_ACCOUNT_ID \
  DATABASE_URL NEON_API_KEY || true

have() { command -v "$1" >/dev/null 2>&1; }

record() {
  local id="$1" required="$2" status="$3" exit_code="$4" command_text="$5" log_path="$6" note="$7"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$id" "$required" "$status" "$exit_code" "$command_text" "$log_path" "$note" >> "$RESULTS_TSV"
}

run_gate() {
  local id="$1" required="$2" command_text="$3"
  local log="$OUTPUT_DIR/logs/${id}.log"
  printf '==> %s\n' "$id"
  set +e
  if have timeout; then
    timeout "$TIMEOUT_SECONDS" bash -lc "$command_text" >"$log" 2>&1
  else
    bash -lc "$command_text" >"$log" 2>&1
  fi
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    record "$id" "$required" "PASS" "$rc" "$command_text" "$log" "command exited zero"
  else
    record "$id" "$required" "FAIL" "$rc" "$command_text" "$log" "command failed; inspect log"
    if [[ "$required" == "true" ]]; then FAILURES=$((FAILURES + 1)); fi
  fi
}

skip_gate() {
  local id="$1" required="$2" command_text="$3" reason="$4"
  record "$id" "$required" "NOT_RUN" "" "$command_text" "" "$reason"
  if [[ "$required" == "true" ]]; then BLOCKED_REQUIRED=$((BLOCKED_REQUIRED + 1)); fi
}

set -e
run_gate "git-diff-check" "true" "git diff --check && git diff --cached --check"

if [[ -f .github/codex/a11oy-secret-diff-scan-v1.py ]] && have python3; then
  run_gate "secret-diff-scan" "true" "python3 .github/codex/a11oy-secret-diff-scan-v1.py"
else
  skip_gate "secret-diff-scan" "true" "python3 .github/codex/a11oy-secret-diff-scan-v1.py" "python3 or scanner unavailable"
fi

if [[ -f .github/codex/a11oy-action-pin-scan-v1.py ]] && have python3; then
  run_gate "action-pin-scan" "true" "python3 .github/codex/a11oy-action-pin-scan-v1.py"
else
  skip_gate "action-pin-scan" "true" "python3 .github/codex/a11oy-action-pin-scan-v1.py" "python3 or scanner unavailable"
fi

if [[ -f scripts/check_banned_tokens.py ]] && have python3; then
  run_gate "doctrine-banned-tokens" "true" "python3 scripts/check_banned_tokens.py --root . --allowlist .doctrine-allowlist"
else
  skip_gate "doctrine-banned-tokens" "false" "python3 scripts/check_banned_tokens.py --root . --allowlist .doctrine-allowlist" "repository checker not present"
fi

if [[ -f scripts/check_manifest_coverage.py ]] && have python3; then
  run_gate "manifest-coverage-selftest" "true" "python3 scripts/check_manifest_coverage.py --selftest"
  run_gate "manifest-coverage-main" "true" "python3 scripts/check_manifest_coverage.py --root . --base-ref origin/main"
else
  skip_gate "manifest-coverage" "false" "python3 scripts/check_manifest_coverage.py" "repository checker not present"
fi

if have python3; then
  mapfile -t changed_python < <({ git diff --name-only --diff-filter=ACMR; git diff --cached --name-only --diff-filter=ACMR; } | sort -u | grep -E '\.py$' || true)
  if [[ ${#changed_python[@]} -gt 0 ]]; then
    quoted=()
    for file in "${changed_python[@]}"; do [[ -f "$file" ]] && quoted+=("$(printf '%q' "$file")"); done
    if [[ ${#quoted[@]} -gt 0 ]]; then run_gate "python-compile-changed" "true" "python3 -m py_compile ${quoted[*]}"; fi
  fi
fi

python_tests=(
  tests/test_series_a_control_plane.py
  tests/test_production_activation.py
  tests/test_live_estate_truth.py
  tests/test_action_assurance.py
  tests/test_hf_source_bound_drift_contract.py
  tests/test_demo_critical_routes.py
  tests/test_holographic_static_route_runtime.py
  tests/test_sovereign_health_alignment.py
)
selected=()
for test_file in "${python_tests[@]}"; do [[ -f "$test_file" ]] && selected+=("$test_file"); done
if [[ ${#selected[@]} -gt 0 ]]; then
  if have python3 && python3 -c 'import pytest' >/dev/null 2>&1; then
    quoted=()
    for test_file in "${selected[@]}"; do quoted+=("$(printf '%q' "$test_file")"); done
    run_gate "pytest-a11oy-priority-contracts" "true" "python3 -m pytest -q ${quoted[*]}"
  else
    skip_gate "pytest-a11oy-priority-contracts" "true" "python3 -m pytest -q <selected>" "pytest unavailable"
  fi
fi

if [[ -f package.json ]]; then
  if have npm; then
    run_gate "npm-test" "true" "npm test -- --runInBand"
  else
    skip_gate "npm-test" "true" "npm test -- --runInBand" "npm unavailable"
  fi
fi

if [[ "${CODEX_ENABLE_CONTAINER_GATES:-0}" == "1" ]]; then
  if [[ -f Dockerfile ]] && have docker; then
    run_gate "docker-build" "true" "docker build --pull=false -t a11oy-codex-finish-build:local ."
  elif [[ -f Dockerfile ]]; then
    skip_gate "docker-build" "true" "docker build --pull=false -t a11oy-codex-finish-build:local ." "docker unavailable"
  fi
else
  skip_gate "docker-build" "false" "docker build" "set CODEX_ENABLE_CONTAINER_GATES=1 on an approved runner to enable"
fi

python3 - "$RESULTS_TSV" "$RESULTS_JSON" "$FAILURES" "$BLOCKED_REQUIRED" <<'PY_GATE_REPORT'
import csv
import json
import sys
import time
from pathlib import Path

tsv_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
failures = int(sys.argv[3])
blocked = int(sys.argv[4])
rows = []
with tsv_path.open(encoding="utf-8") as handle:
    reader = csv.reader(handle, delimiter="\t")
    for row in reader:
        row += [""] * (7 - len(row))
        rows.append({
            "id": row[0],
            "required": row[1] == "true",
            "status": row[2],
            "exit_code": int(row[3]) if row[3].isdigit() else None,
            "command": row[4],
            "log_path": row[5] or None,
            "note": row[6],
        })
status = "PASS" if failures == 0 and blocked == 0 else ("FAIL" if failures else "BLOCKED")
payload = {
    "schema_version": "a11oy.codex.gates.v2",
    "observed_at_epoch": int(time.time()),
    "status": status,
    "required_failures": failures,
    "required_not_run": blocked,
    "results": rows,
}
json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"status": status, "required_failures": failures, "required_not_run": blocked}))
PY_GATE_REPORT

if [[ $FAILURES -gt 0 ]]; then exit 1; fi
if [[ $BLOCKED_REQUIRED -gt 0 ]]; then exit 2; fi
exit 0
