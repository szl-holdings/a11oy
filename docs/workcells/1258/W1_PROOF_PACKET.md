# Workcell 1258 — W1 proof packet

## Plan

Establish the executable public truth and terminal-state contracts before changing production UI or deploying a new portal.

## Patch

- dependency-free public observation state machine;
- release/readiness and honesty assessors;
- fail-closed source-of-truth generator;
- JSON Schema;
- Python and Node regression tests;
- immutable-action CI workflow.

## Local verification

Commands:

```bash
python -m json.tool schemas/v1/public-source-of-truth.schema.json >/dev/null
python -m unittest -v tests/test_public_source_of_truth.py
node --test packages/public-evidence-ui/tests/*.test.mjs
python scripts/build_public_source_of_truth.py \
  --output /tmp/SOURCE_OF_TRUTH.json \
  --source-revision aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --generated-at 2026-08-11T00:00:00Z \
  --contract-verified
python scripts/build_public_source_of_truth.py --check --output /tmp/SOURCE_OF_TRUTH.json
```

Measured locally before publication:

- Python: **9/9 passed**
- Node: **9/9 passed**
- JSON Schema syntax: **PASS**
- Generated snapshot state: **DEGRADED** (fresh external observations intentionally absent)
- Generated digest verification: **PASS**

## Scope boundary

This wave does not claim a production frontend or Hugging Face deployment changed. It creates the source-backed contract that subsequent UI and rollout PRs must consume.
