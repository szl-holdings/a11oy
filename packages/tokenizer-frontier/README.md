# SZL Tokenizer Frontier

Exact semantic promotion gates and immutable Prefix Foundry objects for a11oy.

## What it does

- binds tokenizer identity, source revision, family, normalization, special tokens, added tokens, pre-tokenizer, and post-processor;
- requires exact token IDs and offsets on representative corpora before promotion;
- stores tenant-bound, content-addressed tokenized prefixes without persisting raw prompt text;
- benchmarks candidate throughput without allowing speed to override semantic mismatch;
- moves corpus preparation, retrieval indexing, and batch prefill before interactive traffic;
- uses tokenizer throughput, cache warmth, CPU ingress, and prefill capacity as routing signals;
- labels `routing_score_v1` as an operational heuristic, not the owner-authored RVO.

## Verification

```bash
PYTHONPATH=packages/tokenizer-frontier \
  python -m unittest -v \
  packages/tokenizer-frontier/tests/test_tokenizer_frontier.py
```

## Promotion order

```text
corpus_prep -> retrieval_indexing -> batch_prefill -> interactive
```

Interactive promotion requires verified receipts for every earlier stage. A semantic mismatch, absent measured benchmark, workload mismatch, or sub-baseline result returns `BLOCKED`.
