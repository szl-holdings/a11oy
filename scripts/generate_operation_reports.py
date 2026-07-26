#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Generate the complete Operation Verified Throughput report package."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

LICENSE = """<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->"""
VOCABULARY = (
    "Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, "
    "**PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, "
    "**AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable."
)
BASE = "7ccf04fb65f060115fb01392c739bb4e6c2fe5b8"
DIGEST = "sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416"


def document(title: str, status: str, body: str, generated_at: str) -> str:
    return f"""{LICENSE}

# {title}

Primary status: **{status}**

Generated: `{generated_at}`

{VOCABULARY}

{body.strip()}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "reports" / "operation-verified-throughput").resolve()
    output.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    action_data = json.loads((root / "audit" / "workflow-action-pins.json").read_text(encoding="utf-8"))["data"]
    deployment_data = json.loads(
        (root / "audit" / "deployment-identities.json").read_text(encoding="utf-8")
    )["data"]
    a11oy_live = deployment_data["a11oy"]["runtime_build_info"]["build"]["revision"]
    killinchu_live = deployment_data["killinchu"]["runtime_build_info"]["build"]["revision"]
    backup = deployment_data.get("backup_restoration", {"status": "PREPARED IN A PR"})
    backup_status = backup.get("status", "PREPARED IN A PR")
    backup_evidence = (
        "Both immutable Space snapshots were archived, restored into fresh directories, "
        "and matched their original path/size/SHA-256 manifests byte-for-byte."
        if backup_status == "MEASURED"
        else "The secret-backed snapshot and byte-for-byte restoration workflow is prepared "
        "and must complete in GitHub Actions before a destructive live change."
    )
    sha_pins = sum(
        item.get("pin_policy") == "full-sha" for item in action_data["references"]
    )
    local_actions = sum(
        item.get("pin_policy") == "local" for item in action_data["references"]
    )

    reports = {
        "EXECUTIVE_SUMMARY.md": document(
            "Executive summary",
            "PREPARED IN A PR",
            f"""
The branch establishes a deny-by-default agent-action boundary, strict schemas, signed expiring authorization receipts, a public-key-only execution verifier, a pinned Lean 4.18.0 model for T1/T2, a proposed reusable build boundary, warning-mode Sigstore manifests, secret-safe GenAI telemetry, a fail-closed serving benchmark harness, and a generated Phase 0 inventory.

Verified results:

- **MEASURED:** 27 focused Python tests pass, including five strict schemas, 168 exhaustive runtime-refinement cases, adversarial receipt checks, cross-platform manifest determinism, and report-package integrity.
- **MODELED:** Lean T1 default denial and T2 rejected-implies-non-executable compile with positive, negative, mutation, and premise-removal controls.
- **DOWNGRADED:** Putnam is corrected from stale `4/12 GREEN` text to **0/12 PROVED**.
- **MEASURED:** existing GHCR artifact `{DIGEST}` independently verifies to source `{BASE}`, run 30187276319, Rekor 2255395975.
- **DEPLOYED / MEASURED:** A11oy runtime build-info matches protected main `{a11oy_live}`.
- **DEPLOYED / MEASURED:** Killinchu runtime build-info matches protected main `{killinchu_live}`; `/code`, `/chat`, and the honest endpoint return HTTP 200.
- **MEASURED:** the canonical web application builds and typechecks from the immutable `vendor/platform` gitlink without no-op package stubs.
- **{backup_status}:** {backup_evidence}
- **BLOCKED:** cloud identity, an owned staging cluster, admission negative controls, controlled GPU benchmarks, exact new-builder evidence, and an end-to-end staging release.

Owner authorization was received. Production enforcement and traffic cutover are still blocked by unavailable infrastructure and independent evidence gates, not by missing consent.

No GitHub ruleset, branch-protection, review, check-context, bypass, or approval mutation was performed.
The separately owned canonical governance implementation is PR #317 with zero human approvals and App-owned required attestation; this branch does not modify or reinterpret it.
""",
            generated,
        ),
        "ARCHITECTURE.md": document(
            "Architecture",
            "IMPLEMENTED NOT DEPLOYED",
            """
```text
untrusted proposal
  -> strict schema
  -> finite policy evaluation
  -> human approval when high risk
  -> ECDSA receipt issuer (private key)
  -> append-only lifecycle
  -> execution worker (public key only)
  -> reusable build -> SBOM/scan/sign/attest
  -> independent verification
  -> admission -> staging -> observation
```

The authorization plane, execution plane, build plane, admission plane, and observability plane are separate. Telemetry can record a decision but cannot authorize it. Production identity is an exact tuple of source commit, artifact digest, model/tokenizer revisions when applicable, runtime, environment, and observation time.

The repository's operational Hugging Face surface is `pnpm payload:huggingface`; the diligence demo is `pnpm test:doctrine` in `web/packages/a11oy-core`. The canonical web application is the immutable `vendor/platform` gitlink at `6e0dc7b423fbcfb2c165348e60b41cd55a9b9ace`, using its declared `pnpm@10.26.1` toolchain and `@workspace/a11oy` artifact. A clean production build and typecheck are **MEASURED**. The partial root `web/` mirror is **RETIRED** as an application build target and remains only for doctrine, historical, and static sources.
""",
            generated,
        ),
        "THREAT_MODEL.md": document(
            "Threat model",
            "IMPLEMENTED NOT DEPLOYED",
            """
Threats covered locally include unknown actions, mutable targets, missing approval, absent provenance or rollback, forged or replayed receipts, expiry, revocation, cross-principal/environment/artifact reuse, worker self-authorization, invalid lifecycle transitions, secret-bearing telemetry, and sampling away mandatory security events.

Supply-chain and staging threats are **PREPARED IN A PR**: digest-only signing, exact-source provenance, a warning-mode Sigstore identity policy, and an unsigned negative fixture. They are not **DEPLOYED**.

Residual high risks are absent owned-cluster admission evidence, unavailable controlled GPU infrastructure, missing exact artifacts from the proposed reusable builder, unavailable telemetry backends, and the lack of independent formal-statement review. A11oy and Killinchu live source identity and the canonical web build are no longer open mismatch findings.
""",
            generated,
        ),
        "ESTATE_LEDGER.md": document(
            "Estate ledger",
            "MEASURED",
            """
The machine-readable source is `audit/`. `audit/ESTATE_LEDGER.md` records the canonical repository, live protections, open pull requests, GitHub and Hugging Face identities, provenance, formal state, serving state, cloud blockers, and named risk owners.

Protection inventory was read-only. The branch contains no external protection mutation. The separately owned protection task defines PR #317 as canonical with zero human approvals and App-owned required attestation; PRs #312–#319 and all qillqaq resources were left untouched.
""",
            generated,
        ),
        "LEAN_PROOF_LEDGER.md": document(
            "Lean proof ledger",
            "MODELED",
            """
| Theorem | Kernel build | Non-vacuity | Runtime mapping | Public status |
| --- | --- | --- | --- | --- |
| T1 default denial | PASS | positive + negative + mutation + compile-failing premise removal | exhaustive finite evaluator | MODELED; not publicly PROVED |
| T2 rejected implies non-executable | PASS | same executable witness domain; DENY cannot mint | issuer and lifecycle negative tests | MODELED; not publicly PROVED |
| T3-T12 | not implemented | absent | absent | PLANNED |

Toolchain: `leanprover/lean4:v4.18.0`. Mathlib: `git#v4.18.0`, resolved in committed `lake-manifest.json`. Command `lake build` passed locally.

Public count: **0/12 PROVED**. The minimum four-theorem depth gate and independent English-statement review are unsatisfied. No reviewer approval is invented or self-issued.
""",
            generated,
        ),
        "FORMAL_SCOPE_AND_LIMITATIONS.md": document(
            "Formal scope and limitations",
            "MODELED",
            """
Lean covers the finite governance model: supported action kinds, principal, approval, artifact evidence, environment, policy decision, authorization receipt, lifecycle transition, and audit event. It does not cover neural behavior, human correctness, cryptographic implementation, cloud enforcement, or network delivery.

Runtime binding is Option B. The Python evaluator is **MEASURED** against all 168 combinations of the supported action/principal/environment/approval domain plus adversarial receipt tests. This measured refinement is not called formally verified.
""",
            generated,
        ),
        "RUNTIME_CONFORMANCE.md": document(
            "Runtime conformance",
            "MEASURED",
            """
Focused run: `27 passed`. The suite checks strict Draft 2020-12 schemas, default denial, DENY-to-no-receipt, exact signed receipt acceptance, environment/principal/artifact/policy binding, signature tamper, request replay, expiry, revocation, mutable target, unknown field, unsupported action, absent human approval, all 168 finite refinement cases, append-only lifecycle behavior, telemetry redaction, mandatory sampling, telemetry non-authorization, cross-platform manifest determinism, and evidence-package completeness.

The issuer accepts an injected P-256 private key. `WorkerVerifier` rejects private keys by type and holds only the public key. No key material is committed.
""",
            generated,
        ),
        "SLSA_LEVEL_3_AUDIT.md": document(
            "SLSA Build Level 3 audit",
            "BLOCKED",
            f"""
Existing evidence is **MEASURED** at Build L2 scope: GitHub attestation verification succeeded for `{DIGEST}` and binds it to source `{BASE}`. The existing builder is not a protected reusable workflow and signed mutable tags, so Build L3 is not claimed.

`.github/workflows/reusable-build.yml` is **PREPARED IN A PR**. It builds internally, accepts only the canonical image name, produces an immutable digest, SBOM and vulnerability report for that digest, attests and keyless-signs the digest, and fails on missing evidence. It is not protected until independent review and merge.

The SLSA-native secondary path is **FAILED** for the existing digest and **BLOCKED** for the proposed builder. The pinned `slsa-verifier v2.7.1` Windows binary (verified digest `sha256:1d8f61ad747ecc3d375d2a563cebf2991748b7da1a9bda9a500804c3c499e3c0`) returned `no matching attestations`. `slsa-github-generator >= v1.10.0` has not produced an artifact from the proposed reusable builder. Generator `v2.1.0` is the identified candidate, not an executed result.
""",
            generated,
        ),
        "ACTION_PIN_INVENTORY.md": document(
            "Workflow Action pin inventory",
            "MEASURED",
            f"""
The generated inventory contains **{action_data['total']}** `uses:` references: **{len(action_data['unpinned'])} unpinned** under repository policy. Of these, **{sha_pins}** use full 40-character commit SHAs and **{local_actions}** are local checkout actions.

Exact file, line, action, resolved reference, release comment, and pin policy are in `audit/workflow-action-pins.json`. No Action reference or required-check context was mutated during this task.
""",
            generated,
        ),
        "PROVENANCE_VERIFICATION.md": document(
            "Provenance verification",
            "MEASURED",
            f"""
Verified subject: `oci://ghcr.io/szl-holdings/a11oy@{DIGEST}`.

`gh attestation verify` succeeded with expected repository `szl-holdings/a11oy`. The statement names source `{BASE}`, workflow `.github/workflows/ghcr-build-push.yml@refs/heads/main`, run `30187276319/attempts/1`, GitHub-hosted runner, and Rekor log index `2255395975`.

This verifies the existing attestation and identity. It does not prove reproducibility, admission enforcement, SLSA Build L3, the proposed reusable workflow, or the availability of a matching SBOM.

The secondary `slsa-verifier v2.7.1 verify-image` check **FAILED** with `no matching attestations`. This is retained evidence that the existing GitHub/cosign path is not the required SLSA-native cross-verification path.
""",
            generated,
        ),
        "ADMISSION_TESTS.md": document(
            "Admission tests",
            "BLOCKED",
            """
Sigstore policy-controller `v0.15.1` values, a warning-mode `ClusterImagePolicy`, and an unsigned pod negative fixture are **PREPARED IN A PR** under `deploy/staging/sigstore/`.

No owned staging cluster credentials or usable non-local context are available. Therefore no namespace was labeled, chart installed, webhook changed, unsigned image submitted, or server response captured. Rejection and warning behavior remain **BLOCKED**, not MEASURED.
""",
            generated,
        ),
        "SBOM_AND_VULNERABILITY_REPORT.md": document(
            "SBOM and vulnerability report",
            "BLOCKED",
            f"""
No SBOM and vulnerability report were verified for the exact already-attested image `{DIGEST}`. The existing GHCR workflow explicitly disabled build-time SBOM generation.

The reusable workflow is **PREPARED IN A PR** to generate SPDX JSON and scan the exact immutable digest, failing on high-severity findings and missing output. Because that workflow has not executed, this report contains no fabricated package or vulnerability counts.
""",
            generated,
        ),
        "VLLM_SGLANG_METHODOLOGY.md": document(
            "vLLM and SGLang methodology",
            "PREPARED IN A PR",
            """
The paired matrix fixes one GPU node, OS image digest, driver/CUDA versions, model revision, tokenizer revision, workload, prompt/output lengths, concurrency, request pattern, and repetition count. Each engine must run at least five repetitions for ShareGPT, random, long-context, and structured-output workloads. TTFT, TPOT, ITL, request and token throughput, error rate, failures, and environment identity are retained.

The Rust `vllm-bench` client is pinned to `v0.1.0` with x86_64-linux-musl digest `sha256:e2e246dfe34cd603b85e4d763f9aa6d60940be8b9cef48221f8a70d78420716c`. Candidate vLLM `0.26.0` and SGLang `0.5.16` are not compatibility-tested defaults.

Fairness and output validators fail on environment drift, missing paired engines, empty results, or unlabeled failure cells. Routing remains unchanged until all evidence is **MEASURED** and separately approved.
""",
            generated,
        ),
        "VLLM_SGLANG_SUMMARY.md": document(
            "vLLM and SGLang summary",
            "BLOCKED",
            """
No GPU node, immutable model revision, tokenizer revision, or engine endpoints were supplied. The retained raw matrix therefore contains 40 explicit **BLOCKED** cells (two engines, four workloads, five repetitions) and no performance winner.

No latency, throughput, regression threshold, SLO, or routing recommendation is invented.
""",
            generated,
        ),
        "OTEL_SIGNAL_COVERAGE.md": document(
            "OpenTelemetry signal coverage",
            "IMPLEMENTED NOT DEPLOYED",
            """
| Signal | Contract | Status |
| --- | --- | --- |
| Model call attributes | operation, provider, model, input/output tokens, safe options | MEASURED in unit tests |
| SZL correlation | run, agent, request, policy, formal/artifact digest, model, runtime, benchmark, environment | IMPLEMENTED NOT DEPLOYED |
| Content capture | off by default | MEASURED |
| Policy and receipt failures | forced 100 percent sampling | MEASURED |
| Build/deploy/admission traces | contract only | PREPARED IN A PR |
| Collector, mTLS, buffering, retention, RBAC | no environment | BLOCKED |
| Dashboards and alerts on real telemetry | no backend | BLOCKED |

The schema target is `https://opentelemetry.io/schemas/1.42.0` from the dedicated GenAI conventions line. Observability authorizes nothing.
""",
            generated,
        ),
        "REDACTION_TESTS.md": document(
            "Telemetry redaction tests",
            "MEASURED",
            """
Adversarial tests cover nested tool arguments, authorization headers, API keys, inline passwords, and disallowed correlation keys. Sensitive values are replaced before export with a bounded redaction marker and digest fingerprint; inline credentials are scrubbed. Model span construction accepts no prompt, completion, message, system prompt, tool schema, tool result, or retrieval-document body.

Production collector redaction, trace-backend access, and retention are still **BLOCKED**.
""",
            generated,
        ),
        "FAILURE_INJECTION.md": document(
            "Failure injection",
            "MEASURED",
            """
Executed locally: no-rule default denial, DENY receipt mint refusal, altered signature, replay against a changed request, expiry, revoked principal, wrong environment, wrong principal, wrong digest, wrong policy, unknown field, mutable target, unsupported action, missing approval, rejected-to-executing lifecycle attempt, telemetry secret injection, and mandatory-event sampling.

Prepared but not executed: unsigned-image admission fixture and build evidence fail-closed checks.

Blocked without infrastructure: GPU OOM, engine crash, queue overload, model drift, node or region loss, collector outage/backpressure, blue-green failure, live restoration, and live rollback drills. Offline Space archive restoration is reported separately.
""",
            generated,
        ),
        "DEPLOYED_IDENTITIES.md": document(
            "Deployed identities",
            "MEASURED",
            f"""
| Service | Source identity | Runtime identity | Result |
| --- | --- | --- | --- |
| A11oy Hugging Face | protected GitHub main `{a11oy_live}` | `/api/build-info` reported `{a11oy_live}` | DEPLOYED / MEASURED MATCH |
| Killinchu Hugging Face | protected GitHub main `{killinchu_live}` | `/api/build-info` and honest endpoint reported `{killinchu_live}` | DEPLOYED / MEASURED MATCH |
| A11oy GHCR | source `{BASE}` | `{DIGEST}` | MEASURED attestation match |

Killinchu's Dockerfile COPY inventory is complete in protected source, the exact-source reusable deployment is live, and `/code`, `/chat`, and `/api/killinchu/v1/honest` returned HTTP 200. The live platform image digest is not exposed, so digest-level runtime identity remains unavailable.
""",
            generated,
        ),
        "ROLLBACK_EVIDENCE.md": document(
            "Rollback evidence",
            backup_status,
            f"""
{backup_evidence}

This is offline source restoration evidence, not a live platform rollback or recovery-time measurement. A production traffic cutover still requires an owned staging/production target, an immutable deploy digest, a tested service rollback procedure, and independent release gates.
""",
            generated,
        ),
        "CLAIM_DOWNGRADES.md": document(
            "Claim downgrades",
            "DOWNGRADED",
            f"""
| Surface | Prior text | Corrected label | Evidence |
| --- | --- | --- | --- |
| Series A Putnam row | `PROVED — 0 of 12` and older public `4/12 GREEN` surfaces | **0/12 PROVED** | generated diligence row after pinned Putnam build gate |
| Evidence site Putnam lines | `4/12 GREEN` | **0/12 PROVED** | canonical immutable source labels: 0 REAL / 10 DEMO / 2 OPEN |
| SLSA posture | implied L3 target | **MEASURED Build L2; L3 BLOCKED** | independent attestation plus reusable-boundary gap |
| Killinchu identity | earlier source/runtime mismatch | **DEPLOYED / MEASURED MATCH** | protected main and `/api/build-info` both report `{killinchu_live}` |
| Killinchu `/code` and `/chat` | earlier unavailable/generic-route finding | **MEASURED HTTP 200** | live endpoint probes |

No public external surface was mutated from this branch.
""",
            generated,
        ),
        "CLAIM_UPGRADES.md": document(
            "Claim upgrades",
            "BLOCKED",
            """
No public claim label was upgraded. Local evidence supports reporting test and build facts as **MEASURED** or **MODELED**, but no PROVED, SLSA L3, admission, benchmark, deployment, rollback, or production status is promoted.

Any future public upgrade requires its evidence artifact, automated claim compiler, and independent review. Owner authorization does not replace those evidence gates.
""",
            generated,
        ),
        "OPEN_RISKS.md": document(
            "Open risks",
            "BLOCKED",
            """
High-severity blockers:

1. No owned staging cluster is available for admission negative-control evidence — owner `@szl-holdings/security-reviewers`.
2. No exact SBOM, scan, signature, and SLSA-native cross-verification output exists from the proposed reusable builder — owner `@szl-holdings/release-maintainers`.
3. No controlled GPU environment is available for paired vLLM/SGLang measurement — owner `@szl-holdings/performance-maintainers`.

Additional blockers are independent Lean statement review, collector/access-control deployment, and complete staging trace evidence. The former Killinchu runtime and web-build findings are closed. Machine-readable detail is in `audit/risk-register.json`.
""",
            generated,
        ),
        "FINAL_ACCEPTANCE.md": document(
            "Final acceptance",
            "BLOCKED",
            f"""
This execution is accepted as **PREPARED IN A PR** implementation progress, not as a production rollout.

| Definition-of-done group | Result |
| --- | --- |
| Strict schemas, deny-by-default policy, signed bounded receipts, rejected non-execution | MEASURED locally |
| Pinned Lean build and T1/T2 witnesses | MODELED; 0/12 PROVED publicly |
| Doctrine and Hugging Face payload commands | MEASURED PASS; payload tree stable across two consecutive runs |
| Action pin inventory | MEASURED |
| Protected reusable build | PREPARED IN A PR |
| Exact SBOM, scan, signature, dual provenance from new builder | BLOCKED |
| Staging admission and unsigned rejection | BLOCKED |
| Immutable deploy, blue-green, live rollback | BLOCKED on owned staging infrastructure |
| Hugging Face source backup and offline restoration | {backup_status} |
| vLLM/SGLang identical-environment matrix | BLOCKED |
| OTel GenAI redaction and mandatory sampling | MEASURED locally; backend BLOCKED |
| Live A11oy identity | MEASURED MATCH |
| Live Killinchu identity/source completeness | DEPLOYED / MEASURED MATCH |
| Canonical web application build and typecheck | MEASURED PASS |
| Independent reproducibility/review | BLOCKED |

Production enforcement and traffic cutover are stopped. Unresolved high-severity findings block production.
""",
            generated,
        ),
    }
    for name, content in reports.items():
        (output / name).write_text(content, encoding="utf-8")
    print(f"generated {len(reports)} Markdown reports in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
