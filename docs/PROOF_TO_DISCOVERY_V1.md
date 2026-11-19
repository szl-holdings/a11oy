<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings -->
# Proof-to-Discovery v1: read-only gap and experiment analysis

Status: SOURCE CANDIDATE, NOT DEPLOYED OR PRODUCTION QUALIFIED.
Owner: A11oy provenance/observation API; canonical source is the existing
szl_evidence_graph.py graph and reviewed evidence_graph_receipts.json bundle.
There is no new ledger, daemon, scheduler, credential, database or writer.

## Implemented boundary

The GET route /api/a11oy/v1/evidence/discovery projects the same fixed
CEG bundle used by /graph and /openlineage. It validates the content-addressed
edge list, graph digest, ordering, uniqueness and parent coverage before
returning any candidate. A truncated graph, a missing/invalid receipt bundle,
or missing parents returns HTTP 503/UNAVAILABLE instead of a partial assurance.
Response headers disallow caching. Reading does not append or sign.

Training, evaluation, and model subjects are separate, even if their displayed
IDs coincide. Each eligible subject reports the five independent release gates:
TRAINING, ARTIFACT_VERIFIED, EVALUATED, DEPLOYED and QUALIFIED. No existing
unattested CEG verdict can mark a release gate satisfied. The surface shows
the first missing independent source/model/dataset/config binding, followed
by artifact byte verification, recoverable backup, held-out version-bound
evaluation, production servicing checks and witnessed policy/owner approval.
The output carries its input graph digest and a deterministic content digest;
these are integrity references, not signatures.

The optional pure Python function binary_evsi computes expected value of
sample information for a finite two-state decision, using explicitly supplied
hypothetical priors, USD utilities, sensitivity, specificity, experiment
cost and expected loss from risk. It does not accept unpinned model, dataset
or evaluation harness digests. Its output is always MODELED, non-authorizing,
and cannot be used by the HTTP route to authorize execution. No posterior
probabilities, values of experiments, or training gains are manufactured
from a model's language output.

For two latent states pass/fail and actions release/hold, let V0 be the
maximum expected utility without a test. The value after a test is
V1 = sum over test observations o of max over actions a of
sum over states s of P(o given s) P(s) U(a,s).
EVSI = V1 - V0. The candidate's modeled net value is
EVSI - test_cost_usd - risk_expected_loss_usd.
If no candidate has positive modeled net value, the planner selects none.
The sensitivity/specificity, utilities and prior are assumptions supplied
by a planning process, not empirically validated model performance.

## Regression and adversarial acceptance

Run in a clean source checkout:
    python -m pytest -q tests/test_evidence_discovery.py tests/test_evidence_graph.py tests/test_evidence_receipt_routes.py

Tests cover graph and edge tamper, missing/bounded parent coverage,
subject-type separation, conflicting declarations, false VERIFIED labels,
source binding refusal, non-finite and invalid assumptions, unexpected
authority fields, 121 finite sensitivity/specificity combinations, stable
tie-breaking, no-write repeated HTTP access, 503 on missing bundle, and
Dockerfile COPY inclusion. Fixture tests do not constitute live evaluation.
No external model weights are loaded or executed.

## Remaining gates before a genuine discovery demonstration

1. Reconcile the current owned training snapshots with immutable trainer,
   model, dataset, source, tokenizer and harness identities; measure coverage
   over all accessible providers, not just this public historical bundle.
2. Verify final adapter bytes, independently recoverable backup and durable
   trainer state with the existing GPU bridge; no pickle deserialization.
3. Preregister a held-out experiment with an untouched dataset, frozen
   benchmark/version and quality/safety criteria. Preserve negative cases.
4. Have the existing source-owned evaluation worker run the experiment only
   after proper approval. Record the actual execution receipt separately.
5. Bind a verified witness and outcome into existing CEG/Mesh/Platform
   authorities; prove crash replay and no duplicate effects.
6. Demonstrate live deployment identity and performance and compare to a
   simple rule-based baseline before making novelty or improvement claims.
7. Integrate an accessible operator UI only after the API is admitted in
   protected main, HF release source is synchronized, and independent live
   route/readback is available.

No extra GPU spend, training restart, automatic promotion or publication is
authorized by this implementation. Do not transfer older evaluation scores
to newer model weights. Model assertions, hash identities, signatures,
evidence quality, runtime reachability and policy authority remain distinct.

## External prior art

- Palantir Ontology object, action, and permissions model:
  https://www.palantir.com/docs/foundry/object-backend/overview
- OpenLineage 2.0.2 static JobEvent and dataset lineage:
  https://openlineage.io/docs/spec/
- Temporal workflow replay and idempotency obligations:
  https://docs.temporal.io/
- DeepMind AlphaEvolve evaluator-backed candidate search:
  https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- Expected value of sample information is standard Bayesian decision theory;
  this source change makes no mathematical priority or novelty claim.
