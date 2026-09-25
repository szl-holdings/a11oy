<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Anatomy Ledger implementation audit

The Anatomy Ledger is A11oy's portable evidence inspection and policy evaluation
surface. It belongs to provenance, supply-chain, and governance. It is not a
replacement for GPU infrastructure, an enterprise data platform, or fleet lifecycle
management.

The September 24 repair continues draft PR #2216. The original branch lacked its
operator dashboard, accepted caller verification flags as proof, treated evidence
REVIEW or absent evidence as executable, and used workflow action tags prohibited
by the repository's immutable-action policy. Its Makefile passed an unsupported
ledger CLI argument. Those behaviors are corrected in the current implementation.

## Implemented boundary

- A loopback-default HTTP server and a same-service FastAPI registrar in `serve.py`.
- Static assets and API route registration before the application's SPA catch-all,
  plus explicit Dockerfile copies.
- Bounded JSON ingestion, typed policy inspection, explicit BLOCK/REVIEW outcomes,
  caller-proof rejection, and synthetic regression cases labelled as such.
- A real artifact verifier adapter with subject-digest and workflow/repository/ref
  constraints. Stored report fields cannot authorize future requests.
- Internal snapshot-chain validation on ledger read. No signing or writes on GET.
- Pinned policy-engine toolchains, portable validation, deterministic packaging,
  read-only PR checks, and a separate main-push-only attestation job.
- Bounded independent counterfactual analysis using the actual advisory evaluator,
  exact reason traces, explicit intent/evidence distinctions, and unsigned replay.
  Replay checks input, result, and policy digests; it rejects runtime source drift.
  Source hashes describe executed Python dependencies and separately labelled
  reference policies. Matching hashes do not authenticate a capsule's author.

## Evidence that remains separate

Local tests establish local software behavior. Hosted checks apply only to their
exact commit. Existing PR history contains unsigned commits; signing a repair does
not retroactively sign ancestors. A draft update is not a protected merge. A local
package has no GitHub release attestation. Container inclusion is not deployed-route
proof. Production deployment must continue through A11oy's canonical publisher and
retain source, provider, and live runtime evidence.

The inspection API does not authenticate caller assertions as real identities,
approvals, MFA, trusted network location, or execution authority. `executable` stays
false. No new production execution or signing path is created by this feature.
