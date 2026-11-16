<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Formula evidence across the product

## Decision

The formal registry and the historical PURIQ numerical demonstrations are
different namespaces. Matching `F` numbers do not establish semantic identity,
implementation correctness, runtime applicability, or execution authority.

`szl_formula_registry.py` validates the existing pinned authority record.
`szl_puriq_formulas.formal_registry_snapshot()` projects that record for the
formula page, JSON API, Brain graph, and numerical curriculum. It exposes the
eight locked records and the F23 Lambda boundary with their scopes, caveats,
theorem references, immutable source pins, and registry digest. Missing or invalid
authority is `UNAVAILABLE`; historical metadata is never a fallback.

The registry remains `UNSIGNED`. Its digest and Git pins establish integrity
and lineage, not signer identity. No formula independently authorizes an action;
runtime applicability is `NOT_ESTABLISHED` on these read surfaces. F23 is
`CONJECTURE_1_ADVISORY` and cannot constrain or authorize execution.

## Why the boundary matters

Before this repair, the public formula API paired numerical examples with
formal-looking proof labels selected by matching short IDs. Examples included
an Euler characteristic calculation under F1, a frustum calculation under F11,
and a CRT schedule under F12. Their canonical formal meanings are Replay-Hash
Determinism, Ayni Reciprocity Conservation, and the Kuramoto Additive Fragment.
The Brain graph and curriculum consumers inherited the same associations.

The old page also generated synthetic hash-linked samples on GET and described
them as live Khipu receipts. Those samples were not signed operational receipts.
The repaired reads expose fixed-seed `SAMPLE` evaluations, no receipt history,
`chain_verified=false`, and `receipt_minted=false`.

## Consumer contract

| Projection | Identity and evidence |
|---|---|
| Formal records | `lutar-lean.formal-f-id.v2:F1` and corresponding covered IDs; validated authority only. |
| Numerical demonstrations | `puriq.numeric-demo.v1:F1` through F23; `UNVERIFIED`, no formal binding, no action authority. |
| Brain graph | Historical numerical node IDs remain stable; separate `formal_formula` nodes carry canonical proof metadata. No implicit mapping edges. |
| Numerical curriculum | Valid demonstration metadata is an unverified holdout, with the formal registry in a separate field. |
| M1 proposal generator | Raw or historical declarations do not become `KERNEL_ACCEPTED` or `REFUTED` from status strings. Receipt association requires the same namespace. |

The raw `FORMULA_META` and `EXPERIMENTAL_WAVES` constants are retained historical
inputs for reconciliation. Public projections use `numeric_demo_metadata()`.
Historical corpus artifacts are source snapshots, not live proof authorities.

The M1 producer refreshes only the untrained proposal ledgers and their dependent
counts and digests. It refuses promoted candidates, trained proposals, or evidence
paths outside that contract. Existing adapter, base model, training dataset,
training receipt, evaluation and reload identities are preserved. The admission
reader requires the explicit numerical or historical namespace and rejects
unsupported proof credit. The frozen proof-obligation package verifies and
reproduces its retained historical inputs; current source drift is reported
separately without rewriting its source commits or release manifest.

Sample checks use `PASS`, `FAIL`, or `NOT_EVALUATED`. The F10 approximation uses
the same threshold it displays, including a failing fixed-seed example. F16
checks pure saddle points before feasible mixed strategies. F12, F14 and F23
leave missing premises or observations unevaluated. These are numerical checks,
not formal proof or operational evidence.

### Routes

- `GET /formulas`: shared HTML projection, with proof limits and sample details.
- `GET /api/a11oy/v1/puriq/formulas`: combined v2 projection. The historical
  `formulas` key remains a compatibility alias for `numeric_demos`.
- `GET /api/a11oy/v1/puriq/formulas/{fid}`: the historical numerical sample;
  matching a canonical identifier does not make it a theorem.
- `GET /api/a11oy/v1/puriq/formal-registry`: canonical formal metadata.
- `GET /api/a11oy/v1/puriq/formal-registry/{fid}`: a covered formal record.

Combined and formal routes return HTTP 503 when formal evidence is unavailable.
Independently labeled numerical samples remain readable with no authority.
Unknown sample IDs and formal IDs outside the declared coverage return JSON 404.
Reads perform no signing, ledger append, model inference, or provider calls.

## Verification

The regression suites check real FastAPI responses, HTML/API agreement, exact
locked-eight membership, Lambda limits, namespace separation, source pins,
tampered and missing authority, cache invalidation, reproducible samples,
negative fuel-bound observations, and downstream holdout status. The rendered
page uses the existing KANCHAY styles. These source tests do not establish
deployment, current image parity, or production readiness.

## Prior art and next research step

Palantir's [OSDK React integration](https://www.palantir.com/docs/foundry/ontology-sdk-react-applications/osdk-react)
provides a useful architectural pattern: shared typed state and action contracts
across application components. This repair applies that principle to the
existing A11oy metadata producers; it does not add a second controller.

AWS's [formal-methods paper](https://cdn.amazon.science/67/f9/92733d574c11ba1a11bd08bfb8ae/how-amazon-web-services-uses-formal-methods.pdf)
distinguishes model-checked designs from proof that executable code implements
the design. That distinction motivates the explicit applicability boundary.
These ideas are prior art, not claims of novel invention.

The proposed next experiment is an evidence-bound applicability record for
one F4 graph append: bind the pinned theorem, its backward-edge assumptions,
the implementation contract, and exact input evidence. Negative controls must
reject an edge that violates those assumptions. This remains a research
proposal until implemented and independently checked.
