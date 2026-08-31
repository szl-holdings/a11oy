<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Formal policy scope and limitations

## Exact checked scope

**IMPLEMENTED NOT DEPLOYED:** `formal/LutarPolicy` defines principals, action types, artifact
digests, environments, approvals, provenance results, policy versions, rules, revocation
lists, decisions, authorization receipts, transitions, and audit events.

The pinned Lean kernel checks these statements:

- T1: if no rule matches the request's principal, action, artifact digest, and environment,
  the evaluator returns `REJECT`; the request is therefore not executable.
- T2: if the evaluator returns `REJECT`, the modeled receipt function returns `none`.

The model includes an authorized positive witness, a denied negative witness, principal and
artifact mutation checks, and an expected compile failure when T1's no-match premise is
removed.

## Runtime binding

**MODELED:** the TypeScript gateway implements the corresponding deny-by-default behavior
and is checked against an independent reference model over a finite domain. This is not a
machine-checked refinement theorem, and it is not labeled verified integration.

## What this does not prove

- The neural model, agent planner, tool adapters, operating system, container runtime, cloud,
  cluster, identity provider, telemetry backend, or human reviewer is safe.
- Ed25519, SHA-256, JSON canonicalization, Node.js, Lean's compiler, Git, or hardware is free
  from implementation defects.
- A production worker actually calls this boundary; no production deployment occurred.
- Provenance or admission is active; no live unsigned-image rejection was executed.
- T3 through T12 hold. Their names remain planned requirements, not checked claims.

## Claim gate

The public Putnam count remains 0/12. The operation-specific T1/T2 statements do not change
that ledger, and no operation-specific `PROVED` claim is published until at least four deep
theorems satisfy the full non-vacuity protocol and a second human signs the English statements.
