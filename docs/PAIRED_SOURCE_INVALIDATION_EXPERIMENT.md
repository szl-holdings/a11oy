# Paired source invalidation: synthetic contract experiment

**State: SIMULATED.** This is an offline, deterministic check of a proposed
literal evidence boundary. It does not run Khipu, a retriever, a semantic
entailment model, a signer, or a production service. It cannot qualify the
published Khipu abstention result (2/6) or authorize an action. The code lives
under `scripts/` as a governance research harness; it is not copied into the
serving image or registered as a route.

## Question and method

Can the same proposal be retained when its selected source span supports a
literal structured assertion, yet refused when the evidence changes? For each
of 120 synthetic pairs, the proposal is byte-identical. One member contains a
selected assertion in a source whose SHA-256 agrees with a supplied expected
hash. The other member makes exactly one of four changes: removes the selected
support span, revises the source so the proposal's hash is stale, adds a
conflicting assertion, or selects context that mentions the claim but asserts
no answer. There are 30 pairs per mutation. The seed is
`szl-paired-source-invalidation-20261014-v1`; the generated fixture digest is
`de177b7289856e2e1f8a22ad6755d0a50b8691f657ddedd2f52480f7ff1555d9`.
The fixture is not trainable, and no model training or provider calls occur.

The proposal-only baseline deliberately answers without inspecting evidence.
The gate checks the supplied expected hashes, the proposal's cited hash,
literal selected-line membership in the source, a structured claim/value
match, and conflicting assertions anywhere in the anchored source content,
including spans the selector omitted. Ambiguous JSON with duplicate keys is
rejected at every object depth, even when its byte hashes match. It returns only `ANSWER` or
`ABSTAIN`; neither value is a runtime authorization. The expected-hash map is
an unauthenticated input in this experiment. A real deployment would need
independently admitted sources, a protected source snapshot, authenticated
bindings, and semantic validation.

The original construction here is the **paired evidence inversion**: hold a
proposal fixed, vary its source support in four independently constructed ways,
and report both invalidated denial and supported retention with the same
denominator. That makes the safety/utility tradeoff visible without calling a
blanket refusal a success. This is an implementation choice for this repo,
not a claim that no one has studied paired counterfactual evaluation before.

## Fresh local run

Run `python -X utf8 -B scripts/paired_source_invalidation.py` from the repo
root. A local run on 2026-10-14 returned:

| Synthetic count | Proposal-only | Literal source-bound gate |
| --- | ---: | ---: |
| Supported cases answered / 120 | 120 | 120 |
| Invalidated cases answered / 120 | 120 | 0 |
| Invalidated cases abstained / 120 | 0 | 120 |
| Supported-to-invalidated reversals / 120 pairs | 0 | 120 |

Each mutation contributed 30/30 retained supported cases and 30/30 denied
invalidated cases. These are results of a constructed fixture and a
deterministic gate, not sampled model performance or an estimate of real-world
risk. No statistical confidence interval, leaderboard rank, model promotion,
joule measurement, signed receipt, or independent replay is claimed. The
fixture's symbolic assertions do not establish the truth of a natural-language
answer; a hash proves byte identity only against the supplied anchor.

Focused test command: `python -X utf8 -B -m pytest -q
tests/test_paired_source_invalidation.py -p no:cacheprovider` with
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the environment. The test suite checks
pair identity, refusal outcomes for all four mutations, retained supported cases,
source tampering, fabricated spans, a hidden contradiction, duplicate JSON
keys, duplicate sources, and explicit
denominators. This harness is intentionally separate from the existing
15-query `szl_brain_evidence_eval` pilot and from all Forge held-out model
release gates.

## Prior art studied

- [AbstentionBench](https://arxiv.org/abs/2506.09038) studies many forms of
  unanswerable questions and motivates testing refusal rather than only
  answer accuracy. We use no benchmark rows or model scores from it.
- [Sufficient Context](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems/)
  separates answer failure caused by insufficient retrieved material from
  failure to use sufficient material. Our synthetic relevant-but-insufficient
  mutation is a narrower, literal contract test, not its context classifier.
- [Tele-AI/TELEVAL at `780ac38e`](https://github.com/Tele-AI/TELEVAL/tree/780ac38e833d14221eee3c7cd50a9b29e7067f64)
  (Apache-2.0) separates inference and evaluation stages for spoken-language
  models. We studied that separation, but neither use its data nor copy its
  code; this experiment has no inference stage at all.

The next scientifically meaningful step is a separately frozen, rights-admitted
set of real source/question pairs and an exact-revision Khipu proposal run,
with proposal outputs recorded before gate evaluation. Until that exists,
model and release outcomes remain **UNKNOWN**.
