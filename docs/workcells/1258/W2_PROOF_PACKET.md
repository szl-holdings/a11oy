# Workcell 1258 — W2 proof packet

## Plan

Implement the Prefix Foundry and tokenizer semantic-promotion gate as an independent, network-free package. Do not route interactive traffic until exact semantics and earlier batch stages are verified.

## Patch

- deterministic tokenizer profiles and SHA3-256 identities;
- exact token ID, offset, normalization, special-token, added-token, family, revision, pre-tokenizer, and post-processor comparisons;
- tenant-bound content-addressed prefix-object storage without raw prompt persistence;
- candidate/oracle benchmark records;
- ordered promotion policy;
- tokenizer/cache/CPU/prefill-aware ingress routing heuristic explicitly separated from RVO;
- JSON Schema and pinned CI.

## Measured local verification

```text
Python unit tests: 14/14 passed
Python byte compilation: PASS
JSON Schema syntax: PASS
Raw prefix text persisted: false
Interactive promotion without prior receipts: BLOCKED
Semantic mismatch: BLOCKED
RVO claim: absent; routing_score_v1 is explicitly a heuristic
```

## Limits

The package provides adapter contracts and deterministic test/reference tokenizers. It does not claim that Gigatoken, Hugging Face, or tiktoken won a production benchmark until a separately captured run on representative SZL datasets proves it.
