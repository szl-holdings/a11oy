# CANONICAL — this repository is the home of the UDS mesh

**`szl-holdings/uds-mesh` is the single canonical home of the UDS mesh.**

This is the authoritative source of record per **ADR-0001 (Canonical Home for the
UDS Mesh, ACCEPTED 2026-06-03)**.

## Why this is canonical

- It is a **real repository with real history** — multi-commit lineage, the mesh
  SDKs (`mesh/sdk/`), the 33-test conformance suite, the 5-organ span schemas, and
  the DSSE receipt layers (`formula_receipts.py`, `pinn_dsse.py`).
- It carries a **green Tests Gate + DCO** on `main`.
- Folding it into another repo mid-flight would be a **destructive merge**; keeping
  it canonical is the lowest-blast-radius, most honest choice.

## What this supersedes

A copy of these files exists at `szl-holdings/uds-bundles/mesh/`. That copy is
**non-canonical** and is being demoted to a thin pointer back to this repository.
A prior `uds-bundles/mesh/README.md` claimed the mesh was "absorbed into
szl-fleet-overlay / ARCHIVED" — **that claim was false** and is corrected by the
companion PR `chore/uds-mesh-pointer` on `uds-bundles`.

## Work landed under this decision

| Work Unit | Path | Status |
|-----------|------|--------|
| WU-1 Byzantine quorum (n ≥ 3f+1) + FLP/CAP guard | `src/mesh/quorum.py`, `tests/test_quorum.py`, `docs/FLP_CAP_CAVEAT.md` | feat/byzantine-quorum |
| WU-2 Istio STRICT mTLS + OTel collector | `manifests/istio/*.yaml`, `manifests/otel/collector.yaml`, `manifests/README.md` | feat/istio-mtls-otlp-broker |
| WU-3 OTLP bridge (in-proc spans → OTLP → vsp-otel) | `src/mesh/otlp_bridge.py`, `tests/test_otlp_bridge.py` | feat/otlp-bridge |

---

*License: Apache-2.0 · © 2026 Lutar, Stephen P. — SZL Holdings*

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem) · SLSA L1+L2 · HONESTY OVER CHECKLIST

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
