# Benchmark evolution doctrine

A11oy benchmark claims are evidence artifacts, not slogans. A run is
publishable only when the corpus, route, judge panel, receipts, and raw results
are immutable and replayable.

This doctrine covers Putnam-style goals in `agi-forecast`, theorem/runtime
routes in `lutar-lean` and `a11oy`, and any future Hugging Face
`test-results` mirror.

## Corpus immutability

- Every corpus has a stable `corpusId`, `corpusVersion`, `sourceUri`,
  `license`, `canonicalization`, `sha256` or externally declared digest, and
  problem-count manifest.
- A changed prompt, solution, rubric, split, metadata row, or canonicalization
  rule creates a new `corpusVersion`.
- Old corpora are never overwritten. They may be deprecated by pointer only.
- Putnam problem text may be stored only when license permits. Otherwise store
  official/source pointers, metadata, and content digests.

## Putnam raw-score honesty

- Report Putnam as raw points: `earned_points / possible_points`, with
  year/problem breakdown.
- Do not say “cracked Putnam” unless a sealed, pre-registered corpus reaches a
  declared threshold with receipts, reproducible tooling, and unanimous headline
  judge agreement.
- Separate answer correctness, proof validity, Lean/formal verification,
  runtime formula routing, and provenance compliance.
- Publish failed attempts, retries, time budgets, tool use, and judge
  disagreements.

## Formula routing

Each benchmark item may route to zero or more formulas:

- `FalsePosition`
- `MadhavaBound`
- `LiuHuiPi`
- `SummationInvariant`
- `AdversarialRobustness`
- `QECLineage`
- `ReceiptSubstrate`

A formula route is advisory unless backed by:

1. a theorem-runtime manifest ID;
2. a runtime file;
3. a test file;
4. a validation command;
5. a current claim status.

Ancient or historical lineage never gives benchmark credit by itself.

## Multi-judge panels

Minimum panel:

| Judge | Role |
| --- | --- |
| `raw_grader` | Scores final answer against a rubric. |
| `proof_judge` | Checks reasoning, theorem use, formalization, or runtime verification. |
| `provenance_judge` | Checks receipts, corpus digest, tool budget, and claim wording. |

Two-of-three agreement may publish a raw result. Unanimous agreement is
required for headline claims.

## Receipt requirements

Each run emits JSONL receipts containing:

- `runId`
- `sourceCommit`
- `benchmarkMapSha256`
- `corpusSha256` or `externalCorpusDigest`
- `problemId`
- `promptSha256`
- `modelId` / `solverId`
- `toolPolicy`
- `attemptNumber`
- `answerSha256`
- `judgePanelSha256`
- `rawScore`
- `timestamp`
- `prev_receipt_hash`

Receipts must verify as an append-only chain before a result is mirrored.

## Hugging Face test-results publication

GitHub remains canonical. Hugging Face can mirror benchmark outputs to a
dataset such as `SZLHOLDINGS/a11oy-test-results` with:

- `README.md`
- `benchmark-map.json`
- `results/*.jsonl`
- `receipts/*.jsonl`
- `MANIFEST.json`

The HF dataset must say `mirror-not-canonical` and point back to GitHub commits,
CI runs, receipts, and payload manifests.

## CI gates

Block benchmark PRs unless:

- `benchmarks/benchmark-map.json` validates;
- corpus/result digests match bytes on disk or declared external digests;
- formula routes resolve to `docs/theorem-runtime-manifest.json`;
- Putnam language remains raw-score/staged unless evidence supports more;
- receipt JSONL verifies as append-only;
- HF dry-run includes benchmark/test-results files.

## Current state

The current benchmark map is deliberately staged: it defines the operating
contract and formula routes, but it does not claim a live Putnam score. The
next operational step is a pinned corpus manifest, judge-panel config, and
receipt-emitting runner in `agi-forecast` or a dedicated benchmark package.
