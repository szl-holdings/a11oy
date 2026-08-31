<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operation Verified Throughput threat model

## Scope and status

**IMPLEMENTED NOT DEPLOYED:** this document covers the governed authorization slice in
`packages/policy/src/verified`, its JSON schemas, the pinned `formal/LutarPolicy` model, and
the evidence emitted by the verification scripts. It does not claim production admission,
cloud identity, GPU serving, or collector enforcement.

## Assets

| Asset | Integrity requirement | Status |
|---|---|---|
| Action request | Immutable principal, action, source, artifact, environment, expiry, and approvals | IMPLEMENTED NOT DEPLOYED |
| Authorization receipt | Ed25519 signature plus request, principal, target, environment, policy, formal artifact, and expiry binding | IMPLEMENTED NOT DEPLOYED |
| Formal policy artifact | Exact Lean toolchain and dependency lock; source digest retained | IMPLEMENTED NOT DEPLOYED |
| Deployment identity | Exact source, workflow, image, attestation, SBOM, policy, model, runtime, hardware, and trace identity | SCHEMA IMPLEMENTED; LIVE KILLINCHU ENDPOINT BLOCKED |
| Production credentials | Short-lived, least privilege, isolated from pull-request code | BLOCKED: production identity inventory unavailable |

## Trust boundaries

1. The untrusted caller may propose an action request but cannot mint an authorization receipt.
2. The policy evaluator rejects malformed policy state and malformed, oversized, expired,
   mutable or mismatched targets, illegal transitions, revoked, unmatched, or insufficiently
   approved requests.
3. The receipt issuer accepts only an `ALLOW` decision and signs a bounded receipt.
4. An execution worker resolves the receipt `key_id` through the policy-trusted issuer-key
   registry using own-property lookups only and independently validates every receipt binding
   and signature. Plain or null-prototype registries are required; inherited entries reject.
5. Telemetry observes decisions but has no authority to change them.
6. Human approvals require an Ed25519 signature from a policy-trusted public key whose
   configured owner exactly matches the declared approver.
7. Every action requires provenance whose source, subject, verifier, repository, timestamp,
   and digest match policy-controlled records. Test, security, and rollback receipts likewise
   require semantic bindings; caller-supplied booleans and bare digest reuse are insufficient.
8. The transition origin must equal the target's current environment in trusted policy state;
   the caller-provided `from` value is never sufficient on its own.
9. Production admission and traffic control remain external gates.

## Threats and current controls

| Threat | Current control | Evidence | Residual status |
|---|---|---|---|
| Unknown field injects an allow flag | Strict top-level and nested field validation | Policy negative suite | IMPLEMENTED NOT DEPLOYED |
| Mutable image tag is authorized | Immutable target validation requires a digest or immutable revision | Policy negative suite | IMPLEMENTED NOT DEPLOYED |
| Target, source, or transition is relabeled | Exact target/artifact, all-action source/provenance, legal-transition, and policy-current-environment bindings | Policy negative suite | IMPLEMENTED NOT DEPLOYED |
| No rule matches but action executes | Default denial in TypeScript and Lean T1 | Runtime and formal receipts | IMPLEMENTED NOT DEPLOYED |
| Rejected request mints a receipt | Issuer throws; Lean T2 returns `none` | Negative, differential, and Lean evidence | IMPLEMENTED NOT DEPLOYED |
| Receipt replayed for another artifact, principal, or environment | Exact binding checks plus Ed25519 verification | Mutation suite | IMPLEMENTED NOT DEPLOYED |
| Expired or revoked receipt executes | Time and revocation checks at verification | Mutation suite | IMPLEMENTED NOT DEPLOYED |
| Caller forges or misattributes a human approval | Ed25519 verification plus policy-bound key ownership | Negative suite | IMPLEMENTED NOT DEPLOYED |
| Caller self-asserts or relabels passing evidence | Policy-controlled receipt semantic bindings and required controls | Negative suite | IMPLEMENTED NOT DEPLOYED |
| Receipt key confusion selects an attacker key | Policy-controlled issuer-key resolution, key binding, and revocation | Mutation suite | IMPLEMENTED NOT DEPLOYED |
| Prototype pollution injects an approval or receipt key | Plain/null-prototype registry validation plus own-property-only resolution | Negative and mutation suites | IMPLEMENTED NOT DEPLOYED |
| Oversized, cyclic, or deeply nested input exhausts the worker | Pre-canonicalization JSON shape, depth, node, array, value-string, object-key, and cumulative string bounds | Negative suite | IMPLEMENTED NOT DEPLOYED |
| Published schema admits a mutable target or illegal transition | Immutable-target pattern and action-specific transition constraints mirror runtime validation | Contract suite | IMPLEMENTED NOT DEPLOYED |
| Production deploy lacks trusted provenance, tests, or rollback | Fail-closed production prerequisites | Negative suite | IMPLEMENTED NOT DEPLOYED |
| Prompt injection bypasses policy | No runtime path in this slice can override `REJECT` | Finite-domain checks only | MODELED; end-to-end agent path not yet connected |
| Wrong or unsigned image reaches staging | No live admission test in this run | None | BLOCKED |
| Telemetry leaks prompt, tool, or secret content | Capture-off design requirement only | No adversarial collector receipt | BLOCKED |

## Explicit limitations

- **MODELED:** the TypeScript implementation is compared with an independent reference model
  over a finite test domain. A machine-checked refinement theorem between TypeScript and Lean
  does not exist.
- **AWAITING AUTHORIZATION:** the English statements for T1 and T2 have no second-human sign-off.
- **BLOCKED:** no authorized cluster was available for admission, rollback, collector, or
  identical-hardware serving tests.
- **BLOCKED:** production cloud identities and backup restoration were not available. The
  source-archive restore receipt is intentionally narrower than a production backup.
- **PLANNED:** T3 through T12, signed workload identity, end-to-end trace continuity, and
  production enforcement remain outside this change.
