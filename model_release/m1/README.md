# A11oy M1 experimental operational gate

This directory contains machine-readable evidence for the local 1.5B PEFT
candidate. It does not contain model weights. The candidate is permanently
reported as `NOT_PROMOTED`, `NOT_ESTABLISHED`, and
`EXPERIMENTAL_LOCAL_ONLY` by this gate.

## Evidence boundary

- Exact base, tokenizer, adapter, training-receipt, and offline-reload hashes
  must match `operational-manifest.json`.
- The provider must be the exact in-process identity
  `a11oy.m1.local-peft/v1`; remote URLs and provider fallbacks are forbidden.
- Live GPU identity, free memory, utilization, and temperature must pass the
  fixed admission policy immediately before inference.
- `brain-ingest-ledger.jsonl` contains one decision for every one of the 9,462
  current Brain nodes: 4,227 non-person artifacts and 5,235 person-attribution
  nodes.
- `formula-curriculum-ledger.jsonl` contains the 123 records found in current
  versioned sources: 23 canonical PURIQ records and 100 thesis records. The
  requested count of 200 is explicitly `NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES`.
- Eight formulas are `KERNEL_ACCEPTED`; 115 are `OPEN`; no current record has
  evidence sufficient for `CONDITIONAL` or `REFUTED`.
- External rows without item-level license evidence and all person metadata are
  quarantined. They are never silently used as training text.
- Formula families are holdout-only. Open and conditional formulas become
  abstention examples; refuted formulas would become negative examples.

The existing adapter was **not** trained from these new ledgers. Their relation
is `PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER`, and training remains `NOT_RUN`.

## Regenerate locally

From the repository root, with the existing local Python dependencies:

```powershell
python szl_m1_corpus_manifest.py
```

Generation is deterministic and local-only. It fails unless the Brain graph is
exactly 9,462 nodes / 4,227 distinct artifacts. It performs no web requests,
downloads, training, publishing, signing, or promotion.

## Runtime configuration

The status endpoint is `GET /api/a11oy/v1/models/m1`; bounded inference is
`POST /api/a11oy/v1/models/m1/infer`; the operator view is `/models/m1`.

Required operator bindings:

```text
A11OY_M1_RUN_ROOT=<exact local training-run root>
A11OY_M1_BASE_SNAPSHOT=<exact local cached base snapshot>
A11OY_M1_PROVIDER_ID=a11oy.m1.local-peft/v1
A11OY_M1_GPU_INDEX=0                    # optional; defaults to 0
```

`A11OY_M1_BASE_URL` is forbidden. If any artifact, receipt, row binding,
runtime dependency, provider identity, or GPU measurement is absent or
mismatched, inference returns structured `BLOCKED` or `UNAVAILABLE` with no
fabricated model output.
