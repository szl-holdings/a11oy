# szl-trust

<!-- series-a-badges (Doctrine v11) -->
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?style=flat-square&logo=dependabot&logoColor=white)](https://github.com/szl-holdings/szl-trust/security/dependabot)  
[![SLSA](https://img.shields.io/badge/SLSA-L1_honest-eab308?style=flat-square)](https://slsa.dev/spec/v1.0/levels)


**Trust runtime with hash-chained proof ledgers from real production runs.**

[![Doctrine v11](https://img.shields.io/badge/Doctrine-v11-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![License: CC-BY-4.0](https://img.shields.io/badge/license-CC--BY--4.0-C8B26A?style=flat-square)](./LICENSE)

[![DOI 10.5281/zenodo.20434276 (v18.0)](https://img.shields.io/badge/DOI-zenodo.20434276_v18.0-805AD5?style=flat-square&logo=doi)](https://doi.org/10.5281/zenodo.20434276)

[![CI](https://github.com/szl-holdings/szl-trust/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/ci.yml) [![CodeQL](https://github.com/szl-holdings/szl-trust/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/codeql.yml) [![SBOM](https://github.com/szl-holdings/szl-trust/actions/workflows/sbom.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/sbom.yml) [![DCO](https://github.com/szl-holdings/szl-trust/actions/workflows/dco.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/dco.yml) [![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/szl-trust/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/szl-trust) [![GHAS](https://img.shields.io/badge/GHAS-Code_Security-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/szl-trust/security/code-scanning) [![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

---

> A measurable governance operator on the receipt-bus σ-algebra of agentic AI — publishing Covenant Proof Standard run artifacts from real production executions with `mocked:false` evidence chains for external auditability.

---

## What this is

**szl-trust** is the public transparency layer of the SZL Holdings governed AI platform. It publishes Covenant Proof Standard (CPS) run artifacts — hash-chained, cryptographically verifiable governance receipts from real production executions. The canonical reference run is the E4 Codex Kernel (2026-04-29): 12 receipts, all `mocked:false`, 12 proof ledger steps, 31 span IDs in `trace.jsonl`, with a `deployment_contract.json` anchoring the full run to a specific `repo_commit`. External auditors, partners, and regulators can verify every decision without SZL tooling.

## Why it matters

Regulated AI must demonstrate that decisions were made within approved policy bounds — and that evidence is not fabricated post-hoc. szl-trust provides the artifact layer: every receipt is deterministic (given the same inputs and policy, the same byte-string is produced), hash-chained (no receipt can be inserted without breaking the chain), and published at rest (no live system to query). This is what Article 12 of the EU AI Act and NIST AI RMF traceability requirements look like in practice.

## Quickstart

Receipts are plain JSON, verifiable without any SZL tooling:

```bash
git clone https://github.com/szl-holdings/szl-trust
cd szl-trust

# Inspect the E4 Codex Kernel run
cat runs/E4-codex-kernel-2026-04-29/run_manifest.json | jq '.deliverables'
cat runs/E4-codex-kernel-2026-04-29/proof_ledger.jsonl | head -3 | jq '.'

# Verify mocked:false on all receipts
cat runs/E4-codex-kernel-2026-04-29/trace.jsonl | jq '[.decision_receipt.mocked] | unique'
# → [false]
```

## Key files

| Path | Role |
|------|------|
| `runs/E4-codex-kernel-2026-04-29/run_manifest.json` | Run manifest — payload hash, ledger digest, deliverable SHAs |
| `runs/E4-codex-kernel-2026-04-29/proof_ledger.jsonl` | 12-step hash-chained proof ledger (covenant-v1 policy) |
| `runs/E4-codex-kernel-2026-04-29/trace.jsonl` | 12 execution spans — all `mocked:false` with validator results |
| `runs/E4-codex-kernel-2026-04-29/deployment_contract.json` | Deployment contract (platform: replit, repo_commit anchored) |
| `runs/E4-codex-kernel-2026-04-29/decision_receipt.json` | Canonical decision receipt |
| `runs/E4-codex-kernel-2026-04-29/run_summary.json` | Human-readable run summary |

## E4 Codex Kernel run at a glance

| Metric | Value |
|--------|-------|
| Run ID | `E4-codex-kernel-governed-loop-unified-replit-all-in-one` |
| Date | 2026-04-29 |
| Receipts | 12 (`mocked:false` on all) |
| Proof ledger steps | 12 (hash-chained, covenant-v1) |
| Span IDs in trace | 12 spans (validator: `state_transition_rule`, `drift_bounds`, `human_gate`, `evidence_provenance` — all PASS) |
| Policy version | `covenant-v1` |
| Repo commit | `7eb623f8b870128e615ac6be9880e0265204b454` |

## Related

| Repo | Role |
|------|------|
| [ouroboros](https://github.com/szl-holdings/ouroboros) | Runtime that generates the receipts |
| [ouroboros-thesis](https://github.com/szl-holdings/ouroboros-thesis) | Formal research paper (DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)) |
| [lutar-lean](https://github.com/szl-holdings/lutar-lean) | Lean 4 proofs — 749 decls / 14 unique axioms (15 raw, 1 dup) / 163 sorries @ HEAD c7c0ba17 |
| [uds-mesh](https://github.com/szl-holdings/uds-mesh) | UDS service mesh integration |
| [vsp-otel](https://github.com/szl-holdings/vsp-otel) | OTel + DSSE exporter |
| [a11oy](https://github.com/szl-holdings/a11oy) | Flagship governance app |
| [amaru](https://github.com/szl-holdings/amaru) | Cardano anchoring layer |
| [sentra](https://github.com/szl-holdings/sentra) | Policy enforcement engine |
| Hatun Doctrine Specification | [szl-holdings/platform/docs/a11oy/spec/hatun-doctrine-spec/](https://github.com/szl-holdings/platform/tree/main/docs/a11oy/spec/hatun-doctrine-spec/) |

## Citation

See [CITATION.cff](./CITATION.cff) for machine-readable metadata. Quick reference:

```
S. P. Lutar Jr., "szl-trust — Trust runtime with hash-chained proof ledgers from real production runs,"
SZL Holdings, 2026. https://github.com/szl-holdings/szl-trust
```

Preferred citation: [The Ouroboros Substrate (v18.0)](https://doi.org/10.5281/zenodo.20434276), DOI 10.5281/zenodo.20434276.

## Scope

Doctrine v11 honest scoping:

- **Not a live execution system.** szl-trust is a read-only audit artifact registry — it publishes receipts, it does not execute AI decisions.
- **Not independently sufficient for trust.** Receipts should be verified against the Ouroboros runtime and Covenant Policy Engine; this repo does not ship the verifier.
- **Not a general-purpose blockchain ledger.** Receipts are JSON artifacts anchored by Merkle roots; Cardano anchoring (via amaru) is separate.
- **Not accepting external contributions.** This is a founder-governed transparency artifact — no external PRs.

## License · Trust · Security

[CC-BY-4.0](./LICENSE). Artifacts may be used and redistributed with attribution to SZL Holdings. No credentials or sensitive data are included. Security disclosures: [security@szlholdings.com](mailto:security@szlholdings.com) — see [SECURITY.md](./SECURITY.md).
