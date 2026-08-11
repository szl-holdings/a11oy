# Changelog

## 0.5.0rc1 — 2026-08-03

Initial source-complete Council Kernel release candidate.

### Added

- Fourfold Authority/Sentinel/Verifier/Value signed commit-reveal settlement.
- Correlation-aware epistemic diversity compiler and effective council size.
- Capability attenuation, exact-target authorization, budgets, expiry, and revocation.
- SQLite content-addressed state bus with append-only hash-chained events.
- Atomic sandbox executor with idempotency and compensating rollback.
- Signed DSSE-style receipts plus a local Merkle transparency reference log.
- Proof-Carrying Deliberation Graph, Minority Truth Vault, Negative Capability Ledger.
- Empirical ACT/ESCALATE/BLOCK gate and bounded counterfactual branch market.
- Delayed outcome contracts and outcome settlement records.
- Research Foundry quarantine and lineage workflow.
- MCP, A2A, OPA, Temporal, and SPIFFE adapter boundaries.
- Local API/console, deterministic canary, 24-scenario adversarial benchmark, evidence export, 18 strict protocol schemas, and tests.
- Portable Council Settlement v2 schema conformance with strict DSSE, registry, commitment, assessment, diversity, and gate records.
- Accessible DOM-safe console rendering without `innerHTML`, security headers, read-token gates, and mobile layout contracts.
- Deterministic manifest-bound source archive builder with symlink rejection, generated-state exclusion, normalized modes, and archive read-back.
- SHA-pinned release-candidate workflow with repeatable wheel/source builds, CycloneDX SBOM generation, GitHub artifact provenance/SBOM attestations, and bounded artifact retention.
- Release-tool regression tests covering byte repeatability, private/generated-state exclusion, symlink refusal, and deterministic SBOM output.

### Assurance boundary

This release candidate verifies local deterministic and cryptographic mechanics. It does not claim independently administered production operators, production KMS/HSM custody, live SPIFFE federation, external transparency monitors, authenticated GitHub/Hugging Face mutation, or production deployment.
