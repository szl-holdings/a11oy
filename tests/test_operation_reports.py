# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "operation-verified-throughput"
REQUIRED = {
    "EXECUTIVE_SUMMARY.md",
    "ARCHITECTURE.md",
    "THREAT_MODEL.md",
    "ESTATE_LEDGER.md",
    "LEAN_PROOF_LEDGER.md",
    "FORMAL_SCOPE_AND_LIMITATIONS.md",
    "RUNTIME_CONFORMANCE.md",
    "SLSA_LEVEL_3_AUDIT.md",
    "ACTION_PIN_INVENTORY.md",
    "PROVENANCE_VERIFICATION.md",
    "ADMISSION_TESTS.md",
    "SBOM_AND_VULNERABILITY_REPORT.md",
    "VLLM_SGLANG_METHODOLOGY.md",
    "VLLM_SGLANG_RAW_RESULTS.json",
    "VLLM_SGLANG_SUMMARY.md",
    "OTEL_SIGNAL_COVERAGE.md",
    "REDACTION_TESTS.md",
    "FAILURE_INJECTION.md",
    "DEPLOYED_IDENTITIES.md",
    "ROLLBACK_EVIDENCE.md",
    "CLAIM_DOWNGRADES.md",
    "CLAIM_UPGRADES.md",
    "OPEN_RISKS.md",
    "FINAL_ACCEPTANCE.md",
}
STATUSES = {
    "DEPLOYED",
    "IMPLEMENTED NOT DEPLOYED",
    "PREPARED IN A PR",
    "PROVED",
    "MEASURED",
    "MODELED",
    "FAILED",
    "BLOCKED",
    "AWAITING AUTHORIZATION",
    "DOWNGRADED",
    "RETIRED",
}


def test_complete_report_package_and_status_vocabulary():
    assert {path.name for path in REPORTS.iterdir() if path.is_file()} == REQUIRED
    for path in REPORTS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "SPDX-License-Identifier: Apache-2.0" in text[:240]
        assert STATUSES <= {status for status in STATUSES if f"**{status}**" in text}


def test_raw_matrix_retains_every_blocked_cell_without_a_winner():
    data = json.loads((REPORTS / "VLLM_SGLANG_RAW_RESULTS.json").read_text(encoding="utf-8"))
    assert data["label"] == "BLOCKED"
    assert len(data["results"]) == 40
    assert {cell["status"] for cell in data["results"]} == {"BLOCKED"}
    assert all(cell["failure"] for cell in data["results"])


def test_audit_inventory_has_every_required_phase_zero_artifact():
    required = {
        "github-estate.json",
        "repository-rulesets.json",
        "workflow-action-pins.json",
        "cloud-estate.json",
        "identity-and-oidc-estate.json",
        "secrets-inventory-redacted.json",
        "provenance-baseline.json",
        "lean-baseline.json",
        "serving-baseline.json",
        "observability-baseline.json",
        "deployment-identities.json",
        "claim-inventory.json",
        "risk-register.json",
        "ESTATE_LEDGER.md",
    }
    assert required <= {path.name for path in (ROOT / "audit").iterdir() if path.is_file()}
