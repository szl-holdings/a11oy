#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Generate the Operation Verified Throughput diligence reports from receipts."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
REPORTS = ROOT / "reports" / "operation-verified-throughput"
HEADER = """<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
"""


def load(name: str) -> dict[str, Any]:
    return json.loads((AUDIT / name).read_text(encoding="utf-8"))


def generated_at() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write(name: str, title: str, body: str, timestamp: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    text = (
        HEADER
        + f"\n# {title}\n\n"
        + f"Generated at `{timestamp}` from tracked audit receipts.\n\n"
        + body.rstrip()
        + "\n"
    )
    (REPORTS / name).write_text(text, encoding="utf-8")


def code(value: Any) -> str:
    return f"`{value}`"


def main() -> int:
    timestamp = generated_at()
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    github = load("github-estate.json")
    pins = load("workflow-action-pins.json")
    formal = load("formal-verification-receipt.json")
    runtime = load("policy-runtime-verification.json")
    deployments = load("deployment-identities.json")
    restore = load("source-restore-evidence.json")
    risks = load("risk-register.json")
    provenance = load("provenance-baseline.json")
    observability = load("observability-baseline.json")
    serving = load("serving-baseline.json")
    release = load("release-command-verification.json")
    web_gap = load("web-workspace-dependency-gap.json")
    receipt_source_commits = {
        "workflow action pins": pins.get("source_commit"),
        "formal verification": formal.get("source_commit"),
        "runtime verification": runtime.get("implementation_source_commit"),
        "source restore": restore.get("source_commit"),
        "release command verification": release.get("source_commit"),
    }
    stale_receipts = [
        name
        for name, receipt_commit in receipt_source_commits.items()
        if receipt_commit != source_commit
    ]
    if stale_receipts:
        raise RuntimeError(
            "refusing to generate reports from receipts not bound to current HEAD: "
            + ", ".join(stale_receipts)
        )
    if not formal.get("paths_match_source_commit"):
        raise RuntimeError("formal verification paths do not match current HEAD")
    if not runtime.get("implementation_paths_match_source_commit"):
        raise RuntimeError("runtime implementation paths do not match current HEAD")
    if restore.get("mismatch_count") != 0:
        raise RuntimeError("source restore receipt contains mismatches")
    if (
        runtime.get("runtime_binding", {}).get("formal_artifact_digest")
        != formal.get("formal_artifact_digest")
    ):
        raise RuntimeError("runtime and formal receipts bind different formal artifacts")
    formal_commands = formal.get("commands", [])
    formal_gate = (
        "PASS"
        if formal.get("kernel_check") == "PASS"
        and formal_commands
        and all(item.get("status") == "PASS" for item in formal_commands)
        else "FAILED"
    )
    runtime_gate = "PASS" if runtime.get("status") == "PASS" else "FAILED"

    noncompliant = [item for item in pins["entries"] if not item["pin_compliant"]]
    deployed_rows = []
    for name, item in deployments["surfaces"].items():
        deployed_rows.append(
            f"| {name} | {item['label']} | {item.get('http_status', '')} |"
        )
    risk_rows = [
        f"| {item['id']} | {item['severity']} | {item['owner']} | {item['label']} | {item['risk']} |"
        for item in risks["risks"]
    ]
    risk_rows.append(
        "| OVT-R6 | P1 | Platform engineering | FAILED | "
        f"The broader web package has {web_gap['missing']} missing workspace manifests. |"
    )

    write(
        "EXECUTIVE_SUMMARY.md",
        "Operation Verified Throughput executive summary",
        f"""## Outcome

| Workstream | Status | Evidence |
|---|---|---|
| Live Phase 0 inventory | MEASURED | {github['summary']['repositories']} visible repositories; canonical detail captured in `audit/` |
| Critical-path source restore | {restore['label']} | {restore['regular_files']} files; {restore['mismatch_count']} mismatches; archive {code(restore['archive_sha256'])} |
| Policy schemas and Ed25519 receipt boundary | IMPLEMENTED NOT DEPLOYED | `schemas/` and `packages/policy/src/verified/` |
| Runtime conformance | {runtime_gate} | {runtime['assertions']} assertions; receipt `audit/policy-runtime-verification.json` |
| Lean T1/T2 | {formal_gate} | Kernel check {formal['kernel_check']}; artifact {code(formal['formal_artifact_digest'])} |
| Declared doctrine/HF delivery path | IMPLEMENTED NOT DEPLOYED | {release['declared_delivery_path']}; deterministic payload {code(release['payload_determinism']['first']['digest'])} |
| Broader SPA build | FAILED | {web_gap['missing']} requested workspace packages have no tracked manifest |
| Public proof-count change | RETIRED | No change; independent statement review and four-theorem gate are unmet |
| Production enforcement or traffic cutover | AWAITING AUTHORIZATION | Not attempted |

## Gate decision

**FAILED:** the operation is not operational. Cloud/cluster inventory, production backup
restore, independently verified staging provenance, admission rejection, identical-hardware
serving results, end-to-end telemetry, rollback, and independent review remain open.

Source baseline: {code(source_commit)}. This report describes branch work, not a deployment.
""",
        timestamp,
    )

    write(
        "ARCHITECTURE.md",
        "Operation Verified Throughput architecture",
        """## Five-plane status

| Plane | Implemented slice | Status |
|---|---|---|
| Control | Strict action schema and deterministic policy evaluator | IMPLEMENTED NOT DEPLOYED |
| Verification | Pinned Lean T1/T2 plus non-vacuity and mutation evidence | IMPLEMENTED NOT DEPLOYED |
| Execution | Independent receipt verification API only | IMPLEMENTED NOT DEPLOYED |
| Supply chain | Read-only pin/provenance inventory | BLOCKED: no new staging artifact |
| Evidence | Script-emitted audit and report bundle | IMPLEMENTED NOT DEPLOYED |

The execution worker, build worker, verifier, and admission controller remain separate trust
roles by contract. No production worker was changed or deployed.
""",
        timestamp,
    )

    write(
        "THREAT_MODEL.md",
        "Operation Verified Throughput threat model",
        """The normative threat model is `docs/THREAT_MODEL.md`.

**IMPLEMENTED NOT DEPLOYED:** strict unknown-field rejection, immutable targets, default
denial, Ed25519 human approvals, policy-resolved receipt issuers, semantic evidence bindings,
resource bounds, expiry, revocation, and replay resistance are covered by retained tests.

**BLOCKED:** live admission, cloud identity, collector redaction, production rollback, and
end-to-end agent-path tests were not available.
""",
        timestamp,
    )

    write(
        "ESTATE_LEDGER.md",
        "Operation Verified Throughput estate ledger",
        f"""| Estate surface | Status | Receipt |
|---|---|---|
| GitHub repositories | MEASURED | {github['summary']['repositories']} visible |
| Canonical branches | MEASURED | {github['summary']['canonical_branches']} |
| Canonical open pull requests | MEASURED | {github['summary']['canonical_open_pull_requests']} |
| Workflow references | MEASURED | {pins['summary']['references']} |
| Noncompliant workflow pins | FAILED | {pins['summary']['noncompliant']} |
| Cloud/cluster estate | BLOCKED | `audit/cloud-estate.json` |
| Serving hardware | BLOCKED | `audit/serving-baseline.json` |
| Production collectors | BLOCKED | `audit/observability-baseline.json` |
""",
        timestamp,
    )

    theorem_rows = "\n".join(
        f"| {name} | {formal_gate} | {'IMPLEMENTED NOT DEPLOYED' if formal_gate == 'PASS' else 'FAILED'} |"
        for name in formal["theorem_declarations"]
    )
    write(
        "LEAN_PROOF_LEDGER.md",
        "Lean proof ledger",
        f"""Toolchain: {code(formal['toolchain']['lean_toolchain'])}. Mathlib input:
{code(formal['toolchain']['mathlib_input'])}. Manifest:
{code(formal['toolchain']['lake_manifest_sha256'])}.

| Declaration | Kernel check | Claim status |
|---|---|---|
{theorem_rows}

Positive witness: {code(formal['non_vacuity']['positive_witness'])}. Negative witness:
{code(formal['non_vacuity']['negative_witness'])}. The critical-premise-removal fixture
failed to compile as required.

**AWAITING AUTHORIZATION:** independent English-statement review is absent.
**RETIRED:** no public `PROVED` count change is made by this branch.
""",
        timestamp,
    )

    write(
        "FORMAL_SCOPE_AND_LIMITATIONS.md",
        "Formal scope and limitations",
        """`docs/FORMAL_SCOPE_AND_LIMITATIONS.md` is the normative disclosure.

**MODELED:** runtime-to-Lean alignment is finite-domain differential evidence, not a
machine-checked refinement. T3 through T12, production call-path integration, cryptographic
implementation correctness, and infrastructure behavior are not proved.
""",
        timestamp,
    )

    runtime_rows = "\n".join(
        f"| {item['name']} | {item['status']} | {item.get('result', {}).get('assertions', '') if isinstance(item.get('result'), dict) else ''} |"
        for item in runtime["commands"]
    )
    write(
        "RUNTIME_CONFORMANCE.md",
        "Runtime conformance",
        f"""| Suite | Status | Assertions |
|---|---|---|
{runtime_rows}

Total assertions emitted by the harness: {runtime['assertions']}.

**MODELED:** the independent TypeScript reference model covers a finite test domain. It does
not establish complete refinement to Lean or prove a production worker calls the boundary.
""",
        timestamp,
    )

    pin_rows = "\n".join(
        f"| {item['workflow']} | {item['action']} | {item['ref']} | {item['pin_policy']} |"
        for item in noncompliant
    ) or "| none | none | none | none |"
    write(
        "SLSA_LEVEL_3_AUDIT.md",
        "SLSA Build Level 3 audit",
        f"""**FAILED:** no SLSA Build Level 3 certification is claimed.

| Blocking finding | Status |
|---|---|
| Selected SLSA reusable-workflow ref policy has {pins['summary']['noncompliant']} violation(s) | FAILED |
| Independently verified staging artifact | BLOCKED |
| Provenance distribution and admission enforcement | BLOCKED |
| Independent SLSA review | AWAITING AUTHORIZATION |

The protected workflow finding is report-only under the active coordination lock.
""",
        timestamp,
    )

    write(
        "ACTION_PIN_INVENTORY.md",
        "Workflow action pin inventory",
        f"""The machine inventory resolved {pins['summary']['references']} references:
{pins['summary']['compliant']} compliant, {pins['summary']['noncompliant']} noncompliant, and
{pins['summary']['unresolved']} unresolved.

| Workflow | Action | Current ref | Required policy |
|---|---|---|---|
{pin_rows}

Evidence: `audit/workflow-action-pins.json`. No workflow was mutated.
""",
        timestamp,
    )

    write(
        "PROVENANCE_VERIFICATION.md",
        "Provenance verification",
        f"""**BLOCKED:** this run did not produce an immutable staging artifact.

Tracked workflow provenance signals: {len(provenance['workflow_signals'])}. Matching release
assets: {len(provenance['release_assets'])}. Neither count is proof that a new artifact was
independently verified. `gh attestation verify` and `slsa-verifier` receipts are absent.
""",
        timestamp,
    )

    write(
        "ADMISSION_TESTS.md",
        "Admission tests",
        """**BLOCKED:** no authorized staging cluster was connected. Sigstore policy-controller
was not installed, warning mode was not activated, and no unsigned, wrong-signer,
wrong-repository, altered, mutable-tag, or missing-provenance image was tested.
""",
        timestamp,
    )

    write(
        "SBOM_AND_VULNERABILITY_REPORT.md",
        "SBOM and vulnerability report",
        """**BLOCKED:** no new staging artifact exists, so there is no artifact-bound SBOM or
vulnerability receipt to report. Historical filenames are inventory signals only and are not
promoted to current verification evidence.
""",
        timestamp,
    )

    write(
        "VLLM_SGLANG_METHODOLOGY.md",
        "vLLM and SGLang methodology",
        """**PLANNED:** hold node, GPU, driver, CUDA, image, model/tokenizer revision, precision,
parallelism, context, dataset revision, lengths, concurrency, request rate, warmup,
repetitions, timeout, network, telemetry, power, and isolation constant. Randomize engine
order, retain raw request events and failures, run at least five measured repetitions, and
validate output correctness before any routing decision.
""",
        timestamp,
    )
    raw = {
        "$comment": "SPDX-License-Identifier: Apache-2.0; generated by build_operation_verified_throughput_reports.py",
        "generated_at": timestamp,
        "status": "BLOCKED",
        "claim_label": "PLANNED",
        "reason": serving["hardware"]["reason"],
        "environment": None,
        "cells": [],
        "failed_cells": [],
    }
    (REPORTS / "VLLM_SGLANG_RAW_RESULTS.json").write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write(
        "VLLM_SGLANG_SUMMARY.md",
        "vLLM and SGLang summary",
        """**BLOCKED:** no identical-hardware results exist. No performance default, latency
target, throughput target, winner, or routing promotion is published.
""",
        timestamp,
    )

    write(
        "OTEL_SIGNAL_COVERAGE.md",
        "OpenTelemetry signal coverage",
        f"""Tracked observability surfaces: {len(observability['tracked_surfaces'])}.

**BLOCKED:** no production collector, exporter, sampling, retention, redaction, or access
configuration was available. End-to-end trace continuity and mandatory-event preservation
were not measured.
""",
        timestamp,
    )

    write(
        "REDACTION_TESTS.md",
        "Telemetry redaction tests",
        """**BLOCKED:** no live collector was available. Prompt, completion, system prompt,
tool schema, tool argument, tool result, retrieval-document, secret, and PII redaction were
not adversarially exercised.
""",
        timestamp,
    )

    write(
        "FAILURE_INJECTION.md",
        "Failure injection",
        f"""**IMPLEMENTED NOT DEPLOYED:** policy inputs cover unknown fields, mutable targets,
unsupported actions, expiry, missing rules, failed security receipts, missing approval,
missing provenance, missing rollback, receipt tampering, replay, revocation, and policy drift.
The retained runtime harness emitted {runtime['assertions']} assertions.

**BLOCKED:** GPU, node, region, admission, collector, backend, queue, and production rollback
failures were not exercised.
""",
        timestamp,
    )

    write(
        "DEPLOYED_IDENTITIES.md",
        "Deployed identities",
        """| Surface | Label | HTTP |
|---|---|---|
"""
        + "\n".join(deployed_rows)
        + "\n\nA successful HTTP response is endpoint evidence, not proof of every required identity field.",
        timestamp,
    )

    write(
        "ROLLBACK_EVIDENCE.md",
        "Rollback evidence",
        f"""**MEASURED:** the governed release critical-path source archive restored
{restore['restored_regular_files']} files with {restore['mismatch_count']} mismatches.

**BLOCKED:** this is not a production rollback. No previously verified image digest was
deployed, shifted, rolled back, and observed in staging or production.
""",
        timestamp,
    )

    write(
        "CLAIM_DOWNGRADES.md",
        "Claim downgrades",
        """**RETIRED:** no new public performance, SLSA, admission, telemetry, deployment, or
formal-integration claim was introduced. Unavailable evidence remains `BLOCKED`, finite
runtime alignment remains `MODELED`, and branch code remains `IMPLEMENTED NOT DEPLOYED`.
""",
        timestamp,
    )

    write(
        "CLAIM_UPGRADES.md",
        "Claim upgrades",
        """**RETIRED:** no material public claim was upgraded to `PROVED` or `MEASURED`.
The branch adds retained implementation evidence without crossing the independent-review,
deployment, hardware, or production-authorization gates.
""",
        timestamp,
    )

    write(
        "OPEN_RISKS.md",
        "Open risks",
        """| ID | Severity | Owner | Label | Risk |
|---|---|---|---|---|
"""
        + "\n".join(risk_rows),
        timestamp,
    )

    acceptance = [
        ("Pinned Lean build and T1/T2 checks", formal_gate),
        ("Runtime policy conformance receipt", runtime["status"]),
        ("Critical-path source restore", restore["label"]),
        ("Clean-checkout doctrine and payload commands", release["declared_delivery_path"]),
        ("Broader web workspace build", release["broader_web_build"]),
        ("Production cloud and cluster inventory", "BLOCKED"),
        ("Independent theorem statement review", "AWAITING AUTHORIZATION"),
        ("SLSA artifact generation and independent verification", "BLOCKED"),
        ("Unsigned-image admission rejection", "BLOCKED"),
        ("Identical-hardware vLLM/SGLang results", "BLOCKED"),
        ("End-to-end OpenTelemetry trace and redaction", "BLOCKED"),
        ("Staging rollback", "BLOCKED"),
        ("Production enforcement and traffic cutover", "AWAITING AUTHORIZATION"),
    ]
    acceptance_rows = "\n".join(
        f"| {gate} | {status} |" for gate, status in acceptance
    )
    write(
        "FINAL_ACCEPTANCE.md",
        "Final acceptance",
        f"""| Gate | Status |
|---|---|
{acceptance_rows}

## Decision

**FAILED:** Operation Verified Throughput is not accepted as operational. This branch is a
reviewable implementation slice and evidence package. It stops before production enforcement,
traffic cutover, paid hardware, destructive infrastructure, or public claim upgrades.
""",
        timestamp,
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "claim_label": "IMPLEMENTED NOT DEPLOYED",
                "generated_at": timestamp,
                "reports": len(list(REPORTS.iterdir())),
                "source_commit": source_commit,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
