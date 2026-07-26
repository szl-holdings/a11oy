<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Formal scope and limitations

Primary status: **MODELED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Lean covers the finite governance model: supported action kinds, principal, approval, artifact evidence, environment, policy decision, authorization receipt, lifecycle transition, and audit event. It does not cover neural behavior, human correctness, cryptographic implementation, cloud enforcement, or network delivery.

Runtime binding is Option B. The Python evaluator is **MEASURED** against all 168 combinations of the supported action/principal/environment/approval domain plus adversarial receipt tests. This measured refinement is not called formally verified.
