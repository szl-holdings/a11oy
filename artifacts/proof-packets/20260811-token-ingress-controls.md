# Proof Packet — Token ingress controls

Date: 2026-08-11  
Branch: `codex/p0-a11oy-work-20260811`

## Scope

Runtime-integrated implementation of the current P0 task's state/ingress-efficiency requirements. The production runtime taxonomy home is the existing `routers/` package, which the canonical Dockerfile copies as one governed unit.

## Implemented

- `routers/token_ingress_core.py`
  - bounded tokenizer-throughput/cache-warmth node routing;
  - finite-value validation for throughput, cache, and saved-latency inputs;
  - explicit `MEASURED` vs `SAMPLE` routing evidence labels for trusted internal callers;
  - fail-closed semantic parity gate over token IDs, special tokens, and normalized text;
  - bounded content-addressed Prefix Foundry;
  - file-native repository batch ingestion with path containment, file/total byte budgets, binary classification, and stable SHA-256 manifest entries;
  - verifier-budget reinvestment with `MODELED` default and `MEASURED` only when trusted internal evidence is explicitly supplied.
- `routers/token_ingress.py`
  - `GET /api/a11oy/v1/token-ingress/status`;
  - `POST /api/a11oy/v1/token-ingress/route`;
  - `POST /api/a11oy/v1/token-ingress/qualify`;
  - `POST /api/a11oy/v1/token-ingress/verification-budget`;
  - strict 64 KiB JSON boundary with duplicate-field and non-finite-number rejection;
  - public routing evidence is always `SAMPLE`, even if a caller sends a measured flag;
  - public verification-savings evidence is always `MODELED`;
  - no provider call, arbitrary repository-file read endpoint, persistent-prefix write endpoint, model action, or network effector.
- `routers/frontier_reads.py`
  - invokes the token-ingress controller through the established guarded pre-catch-all registration seam.
- `routers/__init__.py`
  - exports the intentional runtime modules.
- `tests/test_token_ingress.py`
  - core routing/refusal/parity/cache/ingestion/evidence tests;
  - HTTP truth-boundary tests;
  - strict JSON, non-finite telemetry, and token-ID type rejection tests.
- `tests/test_demo_critical_routes.py`
  - assembled-app regression coverage for the status, route, and semantic-qualification paths so a future refactor cannot silently leave the handlers in-image but unwired.
- `.github/workflows/token-ingress.yml`
  - exact hashed Python dependency install;
  - Python compile gate over runtime and route tests;
  - focused token-ingress plus assembled-route pytest gate;
  - scoped `git diff --check` gate.

## Evidence

The earlier source-only contract completed its hosted gate successfully after the workflow checkout was corrected; that run proved the original nine focused tests and whitespace gate. The implementation has since been moved into the actual container-copied runtime package, registered into the assembled application, expanded with HTTP and parser hardening, and therefore requires a fresh terminal exact-head run before this packet labels the runtime-integrated state `APPLIED_AND_VERIFIED`.

Current runtime-integrated disposition: `APPLIED / VERIFICATION_PENDING`.

## Truth boundary

`PASS` means only that the source/runtime contract and stated hosted tests pass on the exact PR head. It does **not** mean an alternate tokenizer has been promoted, a live tokenizer benchmark has been run, production traffic has been rerouted, Hugging Face has been mutated, or a provider/deployment action occurred.

Tokenizer promotion remains `BLOCKED` until representative oracle/candidate token sequences, normalization, special-token behavior, separators, and applicable chat-template behavior match exactly. Performance claims remain `SAMPLE` or `MODELED` unless fresh measurements originate from a trusted internal telemetry path.

## Rollback

Revert the commits changing or adding:

- `routers/token_ingress_core.py`
- `routers/token_ingress.py`
- `routers/frontier_reads.py`
- `routers/__init__.py`
- `tests/test_token_ingress.py`
- `tests/test_demo_critical_routes.py`
- `.github/workflows/token-ingress.yml`
- this proof packet

No database state migration, provider mutation, deployment, key change, Hugging Face publication, or model promotion is part of this token-ingress change.
