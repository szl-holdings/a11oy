# A11oy numerical evaluator dataset

This directory contains the frozen input design and strict ingestion contract
for the A11oy numerical evaluator. The service is implemented in
`szl_numerics_dataset.py` and is registered by `serve.py`.

## Evidence boundary

- The preregistration expands to 1,328 deterministic cases: 1,320
  confirmatory inputs and 8 exploratory Hilbert sentinels.
- Frozen inputs are not measurements. With no authenticated result rows, the
  result ledger truthfully reports zero evidence.
- A result row is accepted only through the bounded, authenticated append
  endpoint and becomes `MEASURED` only when engine/version, executable,
  operator license review, resource, and fixed network-denial evidence pass.
- `MATCH` is agreement between two engines on one frozen case. It is not a
  proof of general correctness and it never changes proof or trust state.
- MATLAB and Octave are external runtime boundaries. Neither engine, a MATLAB
  license, nor network-isolation evidence is bundled here.

## Routes

- `GET /api/a11oy/v1/numerics/dataset/status`
- `GET /api/a11oy/v1/numerics/dataset/cases`
- `GET /api/a11oy/v1/numerics/dataset/cases/{case_id}`
- `GET /api/a11oy/v1/numerics/dataset/results`
- `POST /api/a11oy/v1/numerics/dataset/results`
- `GET /api/a11oy/v1/numerics/dataset/curriculum/formulas`

The formula-curriculum route accounts for F1-F23 using the canonical local
registry, repository-license hashes, and source-family-separated splits.
Missing per-formula proof/refutation receipts stay null; conflicting claims are
quarantined; F23 remains `CONJECTURE_1`; proof/trust uplift is always zero.

## Local configuration

`A11OY_NUMERICS_DATASET_LEDGER` optionally selects the append-only NDJSON
ledger path. `A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256` must contain the
lowercase SHA-256 digest of an operator-held token before POST ingestion is
available. The clear-text token is sent only as
`x-a11oy-numerics-ingest-key`; no default credential exists.
