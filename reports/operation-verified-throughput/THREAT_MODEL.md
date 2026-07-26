<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Threat model

Primary status: **IMPLEMENTED NOT DEPLOYED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Threats covered locally include unknown actions, mutable targets, missing approval, absent provenance or rollback, forged or replayed receipts, expiry, revocation, cross-principal/environment/artifact reuse, worker self-authorization, invalid lifecycle transitions, secret-bearing telemetry, and sampling away mandatory security events.

Supply-chain and staging threats are **PREPARED IN A PR**: digest-only signing, exact-source provenance, a warning-mode Sigstore identity policy, and an unsigned negative fixture. They are not **DEPLOYED**.

Residual high risks are absent owned-cluster admission evidence, unavailable controlled GPU infrastructure, missing exact artifacts from the proposed reusable builder, unavailable telemetry backends, and the lack of independent formal-statement review. A11oy and Killinchu live source identity and the canonical web build are no longer open mismatch findings.
