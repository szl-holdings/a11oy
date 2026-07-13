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

## Preregistered comparison runner

`szl_numerics_experiment.py` is the only supported batch runner for the frozen
comparison. It refuses to invoke either engine unless every mandatory gate is
present: POSIX resource limits, a fresh deny-by-default `unshare --net`
namespace, both external engines, an explicit operator license review for each
engine, and a 100-decimal-place `mpmath` reference implementation. A blocked
preflight writes a receipt with zero engine invocations and zero result rows.

The external engine interface is deliberately fixed. Octave must support its
normal `--version` CLI plus the adapter's bounded script execution. The MATLAB
boundary is an operator-provided offline service executable that must support
`--version` and the adapter's `--json-input PATH --json-output PATH` contract.
Neither boundary may accept a caller-supplied command, shell fragment, network
target, or arbitrary source file. Every actual invocation is launched in a
new network namespace with POSIX CPU, address-space, file-size, and open-file
limits.

Example preflight/execution command (it remains blocked when any gate is
missing):

```text
python szl_numerics_experiment.py --execute-all --output numerics-run.json
```

The two license-review environment flags are affirmative operator attestations,
not runtime discovery: `A11OY_OCTAVE_LICENSE_REVIEWED=1` and
`A11OY_MATLAB_LICENSE_REVIEWED=1`. They must be set only after the applicable
licenses and the external-process boundary have actually been reviewed.

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
