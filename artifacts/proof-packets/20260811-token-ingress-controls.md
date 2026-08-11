# Proof Packet — Token ingress controls

Date: 2026-08-11  
Branch: `codex/p0-a11oy-work-20260811`

## Scope

Source-level implementation of the current P0 task's state/ingress-efficiency requirements. Taxonomy home is `services/` in the flat-rooted repository map.

## Implemented

- `szl_token_ingress.py`
  - bounded tokenizer-throughput/cache-warmth node routing;
  - explicit `MEASURED` vs `SAMPLE` routing evidence labels;
  - fail-closed semantic parity gate over token IDs, special tokens, and normalized text;
  - bounded content-addressed Prefix Foundry;
  - file-native repository batch ingestion with path containment, file/total byte budgets, binary classification, and stable SHA-256 manifest entries;
  - verifier-budget reinvestment with `MODELED` default and `MEASURED` only when the caller explicitly supplies measured evidence.
- `tests/test_token_ingress.py`
  - routing, no-node refusal, parity mismatch/no-cases refusal, prefix eviction, binary-safe ingestion, traversal rejection, total-budget refusal, and evidence-label regression coverage.
- `.github/workflows/token-ingress.yml`
  - exact hashed Python dependency install;
  - Python compile gate;
  - focused pytest gate;
  - `git diff --check` gate.

## Truth boundary

`PASS` here means the source contract and focused hosted tests pass on the exact PR head. It does **not** mean an alternate tokenizer has been promoted, a live tokenizer benchmark has been run, production traffic has been rerouted, Hugging Face has been mutated, or a provider/deployment action occurred.

Tokenizer promotion remains `BLOCKED` until representative oracle/candidate token sequences are supplied and exact parity passes. Performance claims remain `SAMPLE` or `MODELED` unless fresh measured observations are supplied.

## Rollback

Revert the commits adding:

- `szl_token_ingress.py`
- `tests/test_token_ingress.py`
- `.github/workflows/token-ingress.yml`
- this proof packet

No persistent state migration, provider mutation, deployment, key change, or route registration is part of this change.
