# Proof Packet — budget-native semantic token ingress

Date: 2026-08-18
Repository: `szl-holdings/a11oy`
Pull request: `#1331`
Branch: `feat/budget-token-ingress-20260818`
Protected base: `b51f66add89755642c97deaa8acaeb2cc94a6bf4`

## Disposition

`SOURCE_VERIFIED / REVIEW_AND_PROTECTED_PROMOTION_PENDING`

This packet records source implementation and hosted exact-source qualification. It does not claim
protected merge, deployment, Hugging Face publication, live traffic routing, tokenizer promotion,
measured performance, provider mutation, or production readback.

## Architectural convergence

A first isolated implementation used new `routers/token_ingress*` modules. The protected
Hugging Face candidate guard correctly identified that those files would enlarge the canonical
Dockerfile-managed deployment set before post-merge publication. Rather than weakening that guard
or creating a second runtime writer, this successor converges token ingress into the existing
`szl_budget_router.py` runtime seam.

That module already owns bounded decision-risk, time-budget, and model-tier routing and is already
copied and registered by the production application. Tokenizer throughput, cache locality, prefix
reuse, and verifier reinvestment are resource-budget signals, so this is one coherent controller
rather than a parallel subsystem.

No Dockerfile COPY source, automatic Hugging Face writer, route-registration loop, or managed-file
count is added by this successor.

## Runtime implementation

`szl_budget_router.py` preserves the existing budget-tier routes and operator page, and adds:

- deterministic tokenizer-throughput and cache-locality routing;
- finite-number and bounded-input validation;
- a digest-bound Semantic Token Contract over tokenizer family, vocabulary, normalization,
  special tokens, added tokens, chat template, and document separator;
- exact token-ID and decoded-text representative-case qualification;
- a bounded content-addressed Prefix Foundry bound to the semantic-contract digest;
- deterministic file-native repository ingestion with path containment, symlink refusal,
  file-count and byte budgets, binary classification, per-file SHA-256 rows, and a batch digest;
- verifier-budget reinvestment with explicit `MODELED` or trusted-internal `MEASURED` authority;
- governed pre-catch-all routes:
  - `GET /api/a11oy/v1/token-ingress/status`;
  - `POST /api/a11oy/v1/token-ingress/route`;
  - `POST /api/a11oy/v1/token-ingress/qualify`;
  - `POST /api/a11oy/v1/token-ingress/verification-budget`.

The public routes enforce a 64 KiB request boundary, unique JSON fields, finite JSON numbers,
closed nested contracts, bounded arrays, and non-boolean non-negative integer token IDs.

## Authority boundary

Public callers cannot:

- upgrade caller-supplied routing telemetry to `MEASURED`;
- upgrade estimated savings beyond `MODELED`;
- persist tokenized prefixes;
- read arbitrary repository files;
- invoke a provider or mutate a model;
- sign a record;
- mutate a database, deployment, or Hugging Face resource.

The route surface contains zero provider, network, model, repository-read, persistent-prefix-write,
signing, database, or deployment effectors.

## Semantic admission law

A candidate tokenizer is ineligible unless both conditions pass:

1. every semantic-component digest matches the declared oracle; and
2. every representative case has identical token IDs and identical decoded text.

Throughput, cache warmth, provider identity, and benchmark speed cannot override semantic mismatch.

## Hosted evidence

Exact source/runtime head qualified: `f61e68ece1c1875d91acf28d28fb7db64319fa18`.

Focused workflow:

- workflow: `Budget and token ingress contracts`;
- run: `32089486241`;
- job: `95568722008`;
- exact candidate-head checkout: passed;
- hash-locked dependency installation: passed;
- Python compilation: passed;
- focused core, HTTP, and assembled-app tests: **15 passed** in 5.25 seconds;
- scoped `git diff --check`: passed.

The same source head also completed the repository-wide gates fetched for this PR, including:

- Tests;
- container build and local smoke test;
- CodeQL for Actions and JavaScript/TypeScript;
- Trivy and Grype;
- Gitleaks;
- DCO;
- Doctrine and overclaim checks;
- Dockerfile/COPY completeness and registration invocation;
- canonical Hugging Face source parity and single-writer controls;
- manifest, shared-source, namespace, private-IP, lockfile, and action-pin guards.

All observed jobs above concluded successfully. The proof/workflow update that contains this record is
non-runtime evidence-only and intentionally re-triggers the same exact-head admission before review.

## Verification contracts

- `tests/test_budget_token_ingress.py`
  - preserves existing budget-route registration;
  - covers routing, refusal, semantic-contract drift, decoded-text drift, Prefix Foundry isolation,
    deterministic repository ingestion, symlink/traversal/budget refusal, evidence authority,
    strict JSON, input types, and HTTP outcomes.

- `tests/test_budget_token_ingress_assembled.py`
  - proves the four production routes are owned by `szl_budget_router`;
  - proves they precede the API proxy and SPA catch-all;
  - proves the public token-ingress route set exposes no storage/provider/model/deploy effector.

- `.github/workflows/budget-token-ingress.yml`
  - exact candidate-head checkout;
  - immutable action revisions;
  - hash-locked Python dependency installation;
  - Python compilation;
  - focused core, HTTP, and assembled-app tests;
  - scoped whitespace rejection against current protected main;
  - proof-packet changes included in the exact-head trigger and whitespace scope.

## Honest non-claims

- No alternate tokenizer was promoted.
- No live tokenizer or cache benchmark was run.
- No prefix cache was attached to production traffic.
- No deployment or Hugging Face mutation occurred.
- No provider credential, signing key, model weight, or database credential was accessed.
- No measured latency, throughput, KV hit-rate, energy, or cost claim is made.

## Promotion gates

Before any merge transition:

1. the final exact head must have terminal green hosted checks;
2. independent exact-head review must have no actionable P0/P1 finding;
3. DCO, doctrine, secret, supply-chain, container, route, and Hugging Face parity gates must pass;
4. protected merge remains separate authority;
5. canonical post-merge deployment and immutable live readback remain separate authority.

## Rollback

Close the draft PR without merge, or revert the successor commits changing or adding:

- `szl_budget_router.py`;
- `tests/test_budget_token_ingress.py`;
- `tests/test_budget_token_ingress_assembled.py`;
- `.github/workflows/budget-token-ingress.yml`;
- this proof packet.

Protected main and deployed provider state remain untouched until the normal protected path acts.
