# Hugging Face estate recovery — 2026-09-04

This branch completes the owned-Khipu inference path and enters the canonical `hf-sync.yml` publisher after merge.

Execution invariants:

- `SZLHOLDINGS/a11oy` remains the canonical A11oy Docker Space.
- Six domain flagships are published only through the existing exact-main publisher.
- The Khipu model may be labeled executed only when the exact locked GGUF is loaded in-image and the live proof succeeds.
- Missing provider entitlement, write scope, hardware, source identity, or runtime evidence remains an explicit blocker.
- No direct competing Space writer is introduced.
- No secret bytes, prompts, outputs, or hidden reasoning are persisted in deployment receipts.

Required live proof after protected-main deployment:

```bash
python scripts/prove_hf_owned_cortex_live.py \
  --base-url https://szlholdings-a11oy.hf.space \
  --expected-source-sha "$SOURCE_SHA" \
  --output /tmp/hf-owned-cortex-live.json
```

The merge is not equivalent to deployment. Completion requires exact source SHA readback, Khipu runtime identity, nonempty grounding citations, Nemo allow witnesses, deterministic receipt integrity, and `NO_ACTION_AUTHORITY`.
