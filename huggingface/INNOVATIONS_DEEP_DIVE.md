# Innovations deep dive — evidence-backed edition

This file intentionally replaces older speculative model-wrapper copy. A11oy is
not presented here as a Python package, a text-generation model, or a hosted LLM
endpoint. It is a governed execution substrate with source, tests, payload
manifests, UDS/Zarf handoff documentation, and a public claim contract.

## 1. Receipt-backed execution

**Problem.** Agentic systems often produce tool calls without a durable,
verifiable audit trail.

**A11oy mechanism.** `packages/receipt-substrate` canonicalizes tool envelopes,
hashes payloads, links receipts through `prev_receipt_hash`, checks quorum
signatures, and verifies replay/tamper failures.

**Evidence.** `EVAL_TRACE_SAMPLE.jsonl` shows two generated receipts using the
current receipt shape. GitHub contains the implementation and tests under
`packages/receipt-substrate`.

## 2. Payload integrity as a first-class product surface

**Problem.** A demo can look polished while the deploy artifact remains
unverifiable.

**A11oy mechanism.** `deploy/MANIFEST.json` records every deploy payload file
with size and SHA-256. The operational bundle builder emits a deterministic
tarball and checksum sidecar.

**Evidence.** `payloads/deploy/MANIFEST.json`, `payloads/deploy/zarf.yaml`,
`payloads/deploy/manifests/*`, and `a11oy-metadata.json`.

## 3. UDS/Zarf-aware operator handoff

**Problem.** Defense and air-gapped operators need inspectable packages, not
SaaS-only demos.

**A11oy mechanism.** The A11oy UDS lane documents build, inspect, verify,
rollback, and attestation flows. The Warhacker proof-point plan ties those
steps to receipt-chain smoke tests and tamper checks.

**Evidence.** `source/docs/WARHACKER_UDS_PROOF_POINT.md`,
`source/docs/INVESTOR_DEMO.md`, and GitHub `artifacts/a11oy-uds/README.md`.

## 4. Proof-aware claim discipline

**Problem.** Research-heavy AI companies often overstate formal proof coverage.

**A11oy mechanism.** `source/docs/PROVENANCE.md` defines allowed public-claim
statuses: runtime-verified, release-payload, thesis-anchor,
lean-backed-current-green, lean-backed-needs-upstream-ci, roadmap, historical.

**Evidence.** Every high-level claim in this packet points back to GitHub files,
releases, CI workflows, DOI records, or a guarded roadmap status.

## 5. Ecosystem readiness graph

**Problem.** Multi-repo systems become impossible to diligence without a single
map.

**A11oy mechanism.** `source/docs/ecosystem-readiness-report.json` classifies all
visible repos by demo status, evidence, guardrails, and active-showcase scope.

**Evidence.** The generator is `scripts/build_ecosystem_readiness.py` in GitHub;
the report is checked by `pnpm ecosystem:readiness`.

## 6. Active vertical wedge

**Problem.** Infrastructure is easier to understand when tied to a concrete
vertical.

**A11oy mechanism.** Vessels is the active vertical demo wedge. Counsel, Terra,
and Carlota Jo are deliberately excluded from active-demo claims until funded.

**Evidence.** `source/docs/ecosystem-readiness-report.json` and
`source/docs/INVESTOR_DEMO.md`.

