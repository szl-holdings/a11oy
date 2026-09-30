# CPU Evidence Harness — Runbook

Executable half of the research-evidence contracts. One stdlib-only runner,
fail-closed, receipt-emitting. Contracts live in `docs/research-evidence/`;
evidence produced here binds to them.

| Contract | Mode | Merged via |
|---|---|---|
| `szl-specdec-drafter-evidence-contract.v1` (v1.1) | `specdec` | #2047, #2059 |
| `szl-linear-attention-cpu-probe-contract.v1` | `probe` | #2060 |

## Lab bootstrap (once, ~10 min)

```bash
# 1. llama.cpp (specdec mode needs llama-cli with draft-model support)
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build && cmake --build build --config Release -j --target llama-cli
export LLAMA_CPP_BIN="$PWD/build/bin/llama-cli" && cd ..

# 2. Python side
pip install huggingface_hub
```

## Resolving revision pins (contracts refuse unpinned runs)

```python
from huggingface_hub import HfApi
api = HfApi()
print(api.model_info("satgeze/Qwen3.5-0.8B-DSpark").sha)   # drafter pin
print(api.model_info("<estate chaski GGUF repo>").sha)     # target pin
print(api.model_info("gdiamos/amx-reasoning-v1-instruct").sha)  # probe subject pin
```

Record the pins in the receipt fields; never substitute a moving ref for a pin.

## Lane 1 — specdec (DSpark drafter × chaski-line target)

```bash
python harnesses/research-evidence/cpu_evidence_harness.py specdec \
  --target-repo <estate chaski GGUF repo> --target-revision <pin> \
  --drafter-repo satgeze/Qwen3.5-0.8B-DSpark --drafter-revision <pin> \
  --out specdec_receipt.json
```

Reads as: acceptance rate mean, decode uplift ratio, 4-prompt gate parity,
RSS delta. Threshold check (≥1.5× / ≥0.6 / 0 violations) authorizes writing
an integration proposal — nothing more.

## Lane 2 — linear-attention architecture probe (7.5M m2r artifact)

```bash
pip install -r <pinned snapshot>/requirements.txt   # artifact's own runtime
python harnesses/research-evidence/cpu_evidence_harness.py probe \
  --subject-revision <pin> \
  --probe-cmd "python <pinned snapshot>/example.py --ctx {ctx}" \
  --out probe_receipt.json
```

Reads as: RSS across 512→32768 (hypothesis: sub-quadratic — rss@32k < 4×
rss@512), plus a coherence leg marked REQUIRES_HUMAN_REVIEW (read the
`probe_ctx*.log` stdout tails; sanity only, never a quality claim).

## Receipt interpretation

- `MEASURED` — produced on this machine, this run, with the recorded hardware envelope
- `UNVERIFIED` — output unparseable or precondition missing; the harness never upgrades it
- `signing_posture: PLACEHOLDER` — receipts are hash-chained but not non-repudiable until `A11OY_HMAC_KEY` is set (HONEST_DISCLOSURE.md)
- `raw_measurement_artifact_hash` — sha256 over every raw log; any tampering post-run breaks it

## Boundaries

No Hub mutation. No promotion. No production change. The harness produces
evidence; humans and gates decide everything downstream.
