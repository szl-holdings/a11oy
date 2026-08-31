---
license: apache-2.0
tags:
  - benchmark
  - receipts
  - governance
  - mathcomp
  - mirror-not-canonical
pretty_name: A11oy staged test-results schema
---

# A11oy test-results — staged dataset schema

This directory defines the future `SZLHOLDINGS/a11oy-test-results` dataset
layout. It is a **schema and manifest only** in this revision.

GitHub remains canonical. Hugging Face is a generated mirror for review.

The schema, manifest, and receipt examples in this directory are Apache-2.0.
That license does not grant redistribution rights for any future third-party
benchmark corpus. External problem text remains excluded unless its own
row-level license and redistribution rights are admitted.

## Current claim status

- No live benchmark score is claimed.
- No leaderboard metric is claimed.
- No benchmark corpus is redistributed here.
- No model-index metrics are published.

Competition-math benchmark scoring remains staged until corpus digest, receipts, reproducible
tooling, and judge agreement are present.

## Future dataset layout

```text
README.md
MANIFEST.json
benchmark-map.json
schemas/manifest.schema.json
schemas/result-row.schema.json
schemas/receipt-envelope.schema.json
samples/staged/*.jsonl
results/*.jsonl
receipts/*.jsonl
```

Only schema examples or receipt-backed staged dry-run artifacts may appear
before a sealed run exists. Real results require:

1. immutable corpus digest;
2. raw-score reporting;
3. three-judge panel;
4. append-only receipt chain;
5. unsupported-claim rejection;
6. GitHub CI validation.

Validate the current staged manifest with:

```bash
npm run hf:test-results:audit
npm run benchmark:audit
```
