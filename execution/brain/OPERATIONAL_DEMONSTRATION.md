# Operational demonstration

Status: PARTIALLY OPERATIONAL

The executable slice is deliberately small and replayable:

1. `build_example_memory()` creates a public, non-training evidence record.
2. `canonical_digest()` generates its deterministic SHA-256 content digest.
3. `validate_memory_record()` enforces scope, provenance, epistemic, governance,
   propagation, and integrity invariants.
4. Tests demonstrate valid admission and rejection of unsafe training and restricted
   records.
5. `/api/a11oy/v1/brain/capabilities` exposes the honest capability and evidence ledger.

Durable storage, authorized hybrid retrieval, contradiction persistence, signed receipts,
connectors, and verified deployment remain the next vertical slice.
