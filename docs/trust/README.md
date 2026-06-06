# szl-trust

**SZL Holdings Public Trust Portal** · Doctrine v11 LOCKED (749 / 14 / 163) · CC-BY-4.0

[![CI](https://github.com/szl-holdings/szl-trust/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/ci.yml) [![CodeQL](https://github.com/szl-holdings/szl-trust/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/codeql.yml) [![SBOM](https://github.com/szl-holdings/szl-trust/actions/workflows/sbom.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/sbom.yml) [![DCO](https://github.com/szl-holdings/szl-trust/actions/workflows/dco.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-trust/actions/workflows/dco.yml)

[![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-eab308?style=flat-square)](https://slsa.dev/spec/v1.0/levels) [![License: CC-BY-4.0](https://img.shields.io/badge/license-CC--BY--4.0-C8B26A?style=flat-square)](./LICENSE)

[![DOI 10.5281/zenodo.20434276 (v18.0)](https://img.shields.io/badge/DOI-zenodo.20434276_v18.0-805AD5?style=flat-square&logo=doi)](https://doi.org/10.5281/zenodo.20434276)

> **Note (2026-06-03):** Contents are mirrored in
> [`docs-site/trust/`](https://github.com/szl-holdings/docs-site/tree/main/trust).
> This repo is the canonical, version-controlled home for trust run artifacts.

---

A measurable governance operator on the receipt-bus σ-algebra of agentic AI — publishing
Covenant Proof Standard run artifacts from real production executions with `mocked:false`
evidence chains for external auditability.

## What this is

**szl-trust** is the public transparency layer of the SZL Holdings governed AI platform.
It publishes Covenant Proof Standard (CPS) run artifacts — hash-chained, cryptographically
verifiable governance receipts from real production executions. The canonical reference run
is the **E4 Codex Kernel (2026-04-29)**: 12 receipts, all `mocked:false`, 12 proof ledger
steps, 31 span IDs in `trace.jsonl`, with a `deployment_contract.json` anchoring the full
run to a specific `repo_commit`.

External auditors, partners, and regulators can verify every decision without SZL tooling.

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

## E4 Codex Kernel run at a glance

| Metric | Value |
|--------|-------|
| Run ID | `E4-codex-kernel-governed-loop-unified-replit-all-in-one` |
| Date | 2026-04-29 |
| Receipts | 12 (`mocked:false` on all) |
| Proof ledger steps | 12 (hash-chained, covenant-v1) |
| Span IDs in trace | 12 spans (all validators PASS) |
| Policy version | `covenant-v1` |
| Repo commit | `7eb623f8b870128e615ac6be9880e0265204b454` |

## Key files

| Path | Role |
|------|------|
| `runs/E4-codex-kernel-2026-04-29/run_manifest.json` | Run manifest — payload hash, ledger digest, deliverable SHAs |
| `runs/E4-codex-kernel-2026-04-29/proof_ledger.jsonl` | 12-step hash-chained proof ledger |
| `runs/E4-codex-kernel-2026-04-29/trace.jsonl` | 12 execution spans — all `mocked:false` |
| `runs/E4-codex-kernel-2026-04-29/deployment_contract.json` | Deployment contract (platform: replit, repo_commit anchored) |
| `runs/E4-codex-kernel-2026-04-29/decision_receipt.json` | Canonical decision receipt |

## Honesty scope

- **Not a live execution system.** Read-only audit artifact registry — publishes receipts, does not execute AI decisions.
- **Not independently sufficient for trust.** Receipts should be verified against the Ouroboros runtime.
- **Not a general-purpose blockchain ledger.** JSON artifacts anchored by Merkle roots; Cardano anchoring (via amaru) is separate.
- **SLSA L1 honest** — provenance generated; **L2/L3 not claimed**.
- **Λ-uniqueness = Conjecture 1** (not a theorem).
- No FedRAMP / Iron Bank / CMMC claims.

## Related

| Repo | Role |
|------|------|
| [ouroboros](https://github.com/szl-holdings/ouroboros) | Runtime that generates the receipts |
| [lutar-lean](https://github.com/szl-holdings/lutar-lean) | Lean 4 proofs — 749 decls / 14 unique axioms (15 raw, 1 dup) / 163 sorries @ c7c0ba17 |
| [a11oy](https://github.com/szl-holdings/a11oy) | Flagship governance app |
| [docs-site/trust/](https://github.com/szl-holdings/docs-site/tree/main/trust) | Mirror (docs) |

## Citation

See [CITATION.cff](./CITATION.cff). Preferred: [The Ouroboros Substrate (v18.0)](https://doi.org/10.5281/zenodo.20434276), DOI 10.5281/zenodo.20434276.

## License

[CC-BY-4.0](./LICENSE). Artifacts may be used and redistributed with attribution to SZL Holdings.
Security disclosures: [security@szlholdings.com](mailto:security@szlholdings.com) — see [SECURITY.md](./SECURITY.md).

---

*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 · SLSA L1 honest*

Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
