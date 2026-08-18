# Proof Packet — Memory index adapter-generation binding

Date: 2026-08-17  
Branch: `codex/p0-a11oy-stage-20260811`

`routers/memory_index_binding.py` defines the canonical `szl.memory-index-generation/v1` identity envelope over provider, model, revision, dimension, metric, and normalization. The canonical JSON SHA-256 must equal the worker configuration and the active database generation digest before `run_once` can execute.

The binding refuses missing/extra fields, unsupported metrics or normalization modes, invalid dimensions, identity-read failures, and digest mismatches. A mismatch is rejected before a database connection or adapter operation is delegated.

Focused tests cover deterministic canonicalization, exact binding, mismatch refusal, malformed identities, and sanitized identity-provider failure.

Current disposition: `IMPLEMENTED / EXACT_HEAD_CI_PENDING`.

This does not select or call an embedding provider. No model, API key, vector index, database credential, or deployment authority is inferred from the identity contract.
