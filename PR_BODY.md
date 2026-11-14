## What

Unseals the .guarded-import-allowlist [DEAD-STUB] entry for szl_brain_v3: serve.py has mounted the BRAIN v3 block guardedly since Yachay 2026-06-01, but the module never existed — /api/a11oy/v3/brain/* has been ABSENT at runtime. This PR implements it.

## Contract (verbatim from the serve.py block)

- Mounts /api/a11oy/v3/brain/{models,chat,chat/stream,converse,tool-call,usage}; ADDITIVE, no v1/v2 szl_brain changes.
- Anthropic-hosted flagship ladder (claude-opus-5-5 primary, 7-tier fallback on model_not_found ONLY).
- HONEST fail-closed: no ANTHROPIC_API_KEY -> exact-unblock-action 503, never fabricated output (Zero-Bandaid Law).
- Claude Platform user-scoped keys: sends anthropic-workspace-id iff ANTHROPIC_WORKSPACE_ID is set; a 400 "not scoped to a workspace" degrades to a 503 with the exact unblock action.
- Token accounting + bounded metadata-only request ledger; receipts honestly labeled "ledger+log" (DSSE binding NOT claimed).

## Doctrine integration

- szl_boot_preflight._REGISTRY: ANTHROPIC_WORKSPACE_ID registered (VARIABLE, brain, optional) — mirrors docs/RUNTIME_ENV.md 1:1, collision rule honored (Variables tab only; ANTHROPIC_API_KEY stays Secrets-tab-only).
- docs/RUNTIME_ENV.md: new row + collision-rule-safe placement.
- Dockerfile: per-file COPY szl_brain_v3.py (this Dockerfile has no blanket *.py COPY).
- .guarded-import-allowlist: szl_brain_v3 DEAD-STUB entry removed (module now exists; guard passes naturally).

## Tests

tests/test_brain_v3.py — 6 tests: honest 503 w/o key; workspace header wiring; exact unblock on workspace-400; ladder on 404 ONLY; NO ladder walk on 401; models/usage/converse shape. All green locally (6 passed).
