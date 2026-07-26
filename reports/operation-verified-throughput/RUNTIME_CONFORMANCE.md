<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Runtime conformance

Primary status: **MEASURED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Focused run: `27 passed`. The suite checks strict Draft 2020-12 schemas, default denial, DENY-to-no-receipt, exact signed receipt acceptance, environment/principal/artifact/policy binding, signature tamper, request replay, expiry, revocation, mutable target, unknown field, unsupported action, absent human approval, all 168 finite refinement cases, append-only lifecycle behavior, telemetry redaction, mandatory sampling, telemetry non-authorization, cross-platform manifest determinism, and evidence-package completeness.

The issuer accepts an injected P-256 private key. `WorkerVerifier` rejects private keys by type and holds only the public key. No key material is committed.
