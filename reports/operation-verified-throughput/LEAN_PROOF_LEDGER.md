<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Lean proof ledger

Primary status: **MODELED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

| Theorem | Kernel build | Non-vacuity | Runtime mapping | Public status |
| --- | --- | --- | --- | --- |
| T1 default denial | PASS | positive + negative + mutation + compile-failing premise removal | exhaustive finite evaluator | MODELED; not publicly PROVED |
| T2 rejected implies non-executable | PASS | same executable witness domain; DENY cannot mint | issuer and lifecycle negative tests | MODELED; not publicly PROVED |
| T3-T12 | not implemented | absent | absent | PLANNED |

Toolchain: `leanprover/lean4:v4.18.0`. Mathlib: `git#v4.18.0`, resolved in committed `lake-manifest.json`. Command `lake build` passed locally.

Public count: **0/12 PROVED**. The minimum four-theorem depth gate and independent English-statement review are unsatisfied. No reviewer approval is invented or self-issued.
