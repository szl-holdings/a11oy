# ORO operational status

ORO means **Obligation-Ranked Orbits**. This document records only evidence carried by the current source branch. It is not a deployment receipt.

## Current source slice

The current branch contains:

- a frozen four-component rank over unresolved obligations, evidence deficits, integer budget units, and turn allowance;
- strict rejection of booleans, floats, negative values, overflow, unknown fields, and rank-schema drift;
- structural lexicographic decrease separated from objective convergence;
- parent-turn consumption and conserved child allocation receipts;
- canonical, domain-separated semantic hashing;
- barrier membership, generation, TTL, bounded-payload, and conflicting-duplicate validation;
- semantic-cycle refusal;
- invariant manifests bound to stable identity, version, source digest, implementation digest, input schema, and golden vectors;
- strict SQLite evidence tables for runs, barriers, allocations, invariant results, semantic hashes, negative results, approvals, and certificates;
- independent candidate, evaluator, and approver authority checks;
- a production fail-closed requirement for a governed signer;
- committed Draft 2020-12 schemas and a path-scoped protected CI gate.

## Honest labels

| Claim | Current label |
|---|---|
| Rank and barrier source contract | IMPLEMENTED, exact-head CI pending |
| Focused regression suite | COMMITTED, hosted result pending |
| Runtime route registration | NOT IMPLEMENTED on this slice |
| Durable production volume | NOT VERIFIED |
| Governed production signer | NOT VERIFIED |
| Live A11oy readback | NOT VERIFIED |
| Well-founded termination | MODELED |
| Machine-checked termination | NOT PROVED |
| Global action optimality | NOT CLAIMED |

## Promotion blockers

The PR remains draft until all of the following are carried on an exact current-main successor and independently qualified:

1. API and zero-CDN dashboard registration before the SPA catch-all.
2. Plan create/list/read/execute and orbit/barrier/invariant/negative-result readback.
3. Exact Dockerfile delivery for every runtime file.
4. Real Uvicorn loopback HTTP smoke tests.
5. Persistent-volume readiness and governed-signer readiness that fail closed in production.
6. One bounded demonstration against a real failing or historically failing workflow.
7. Current-head protected CI, independent review, protected merge, Hugging Face deployment, and exact-revision live readback.
8. Separate Lean witnesses and a later data-only theorem binding.

No direct production write, self-approval, self-certification, protection bypass, secret readback, or Hugging Face overwrite is authorized by this document.
