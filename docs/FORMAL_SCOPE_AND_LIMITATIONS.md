<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Formal scope and limitations

The Lean project models the discrete governance boundary: action kinds, principals, environments, decisions, receipts, policy evaluation, execution eligibility, transitions, and audit events. It does not formalize a neural model, cloud implementation, cryptography, network transport, or the correctness of human approval.

T1 (default denial) and T2 (rejected implies non-executable) are kernel-checked locally. Positive and negative witnesses prevent a vacuous all-denied model, and a compile-failing negative control shows that removing the authorization premise invalidates the claimed positive witness. They remain **0/12 PROVED** publicly because the required four-theorem minimum and independent English-statement review have not been met.

Runtime binding uses Option B. The Python policy evaluator is compared exhaustively over its finite action, principal, environment, and approval domain and tested adversarially for receipt tampering. The Lean statement may be kernel-checked; the runtime refinement is **MEASURED**, not formally verified. No `lake build` claim by itself establishes runtime integration.
