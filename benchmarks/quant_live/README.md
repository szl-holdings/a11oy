# A11oy bounded local quant benchmark

This harness replaces the Quant surface's placeholder claim states with an
operator-generated receipt from real local execution. It does **not** reproduce
NVIDIA's published benchmark environment and must not be used to claim vendor
speedups, one-million-token retrieval, cuML acceleration, or Ripser++ GPU
performance.

## Run

Prerequisites:

- Ollama is reachable at `http://127.0.0.1:11434`.
- `szl-nemo:latest` and `qwen2.5:3b` are locally installed.
- NVIDIA device telemetry is available through `nvidia-smi` when GPU identity
  evidence is desired.

```powershell
py -3.12 benchmarks/quant_live/run_bench.py
```

The default operator receipt is written outside the repository to
`%USERPROFILE%\.a11oy\receipts\quant-live-benchmark.json`. To refresh the
versioned public evidence snapshot, pass
`--output benchmarks/quant_live/receipts/latest.json` after reviewing the
inputs, models, and license boundaries.

## Evidence contract

The receipt records:

- exact served model tags and Ollama generation counters;
- bounded exact-match and needle-retrieval tasks;
- wall-clock and model-reported latency;
- observed GPU inventory;
- actual CPU-reference numerical timings;
- dependency availability and explicit unavailable GPU comparisons;
- a canonical SHA-256 content digest;
- DSSE state, which remains `UNSIGNED_CONTENT_ADDRESSED` unless an approved
  local signing key is present.

The `/api/a11oy/v1/quant/verify-claims` route validates the receipt size,
schema, completion state, and digest before surfacing any `MEASURED` row. A
missing or tampered receipt fails closed. `MEASURED` means measured on this
bounded local protocol only; it is not a claim of general accuracy or parity
with a vendor benchmark.
