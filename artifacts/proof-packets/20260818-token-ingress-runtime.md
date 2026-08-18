# Proof Packet — governed semantic token ingress

Date: 2026-08-18  
Repository: `szl-holdings/a11oy`  
Branch: `feat/token-ingress-semantic-contract-20260818`  
Protected base: `d9bf1fb96f80523b0e6cfc42fd313b3e83b04ce7`

## Disposition

`SOURCE_APPLIED / HOSTED_VERIFICATION_PENDING`

This packet records source-level implementation on an isolated current-main successor. It does
not claim protected merge, deployment, provider mutation, Hugging Face publication, live traffic
routing, tokenizer promotion, measured performance, or production readback.

## Runtime implementation

- `routers/token_ingress_core.py`
  - deterministic tokenizer-throughput and cache-locality routing;
  - finite-number and bounded-input validation;
  - digest-bound Semantic Token Contract over tokenizer family, vocabulary, normalization,
    special tokens, added tokens, chat template, and document separator;
  - exact token-ID and decoded-text representative-case qualification;
  - bounded content-addressed Prefix Foundry bound to the semantic contract digest;
  - deterministic file-native repository ingestion with path containment, symlink refusal,
    file-count and byte budgets, binary classification, SHA-256 file rows, and a batch digest;
  - verifier-budget reinvestment with explicit `MODELED` or trusted-internal `MEASURED` labels.

- `routers/token_ingress.py`
  - `GET /api/a11oy/v1/token-ingress/status`;
  - `POST /api/a11oy/v1/token-ingress/route`;
  - `POST /api/a11oy/v1/token-ingress/qualify`;
  - `POST /api/a11oy/v1/token-ingress/verification-budget`;
  - strict 64 KiB JSON boundary, unique-field enforcement, non-finite-number refusal, closed
    nested contracts, bounded arrays, and token-ID type checks;
  - public caller telemetry is always `SAMPLE` and public savings are always `MODELED`;
  - zero provider, model, network, repository-read, persistent-prefix-write, signing, or
    deployment effectors.

- `routers/frontier_reads.py`
  - registers token ingress through the existing guarded pre-catch-all seam while preserving the
    Series-A and Frontier Now controllers.

- `routers/__init__.py`
  - records the intentional runtime package exports.

## Verification contracts

- `tests/test_token_ingress.py`
  - routing, refusal, semantic-contract, decoded-text, Prefix Foundry, repository-ingestion,
    evidence-authority, strict-JSON, type, and HTTP status coverage.

- `tests/test_token_ingress_assembled.py`
  - proves the four production routes are owned by `routers.token_ingress`, occur before both
    production catchalls, and expose no storage/provider mutation route.

- `.github/workflows/token-ingress.yml`
  - exact candidate-head checkout;
  - immutable action revisions;
  - hash-locked Python dependency installation;
  - Python compilation;
  - focused core, HTTP, and assembled-app tests;
  - scoped whitespace rejection against current protected main.

## Semantic admission law

A candidate tokenizer is ineligible unless both conditions pass:

1. every semantic component digest matches the declared oracle; and
2. every representative case has identical token IDs and identical decoded text.

Throughput, cache warmth, vendor identity, and benchmark speed cannot override semantic mismatch.

## Honest boundaries

- No alternate tokenizer was promoted.
- No live benchmark was run by this branch.
- No tokenized prefix was persisted through a public route.
- No arbitrary repository file can be read through a public route.
- No provider endpoint, model, deployment, database, signing key, or Hugging Face resource was
  mutated.
- Memory Covenant database/runtime work is excluded from this collision-safe successor and must
  use a separate current-main PR.

## Promotion gates

Before any ready or merge transition:

1. exact-head hosted checks must be terminal and green;
2. the branch must remain based on current protected main or be rebuilt without history rewrite;
3. independent exact-head review must have no actionable P0/P1 finding;
4. DCO, signing, doctrine, secret, supply-chain, container, and route ownership gates must pass;
5. protected merge and canonical post-merge publication/readback remain separate authorities.

## Rollback

Close the draft PR without merge, or revert the commit changing or adding:

- `routers/token_ingress_core.py`
- `routers/token_ingress.py`
- `routers/frontier_reads.py`
- `routers/__init__.py`
- `tests/test_token_ingress.py`
- `tests/test_token_ingress_assembled.py`
- `.github/workflows/token-ingress.yml`
- this proof packet

Protected main and deployed provider state remain untouched until the normal protected path acts.
