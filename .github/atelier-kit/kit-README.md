# SZL Atelier kit

GitHub-aligned Python for the SZLHOLDINGS Hugging Face estate. Forty Hub model ids. Canonical source: [szl-holdings/szl-khipu](https://github.com/szl-holdings/szl-khipu), [szl-holdings/szl-forge](https://github.com/szl-holdings/szl-forge), [szl-holdings/szl-nemo](https://github.com/szl-holdings/szl-nemo).

## Train

- `train_nano.py` — NumPy silhouettes (moons, mini-embed, tiny-khipu, 4-way gate, lambda). MEASURED.
- `train_cohort.py` — CPU NumPy silhouettes for WILLAY (tell/silence) and the chaski courier lineage. Seed 20260721. `--kernels-only` re-measures organs without refitting MLPs. Does **not** GPU-retrain 0.5B / 0.8B / 1.5B.
- `receipted_unsloth.py` — Unsloth QLoRA, unique profile per organ. TAKE fused kernels / 4bit / adamw_8bit / rsLoRA. LEAVE packing=True, LoftQ, GGUF-as-model. CUT: every knob in the receipt, house seed 20260721. `--receipt-only` mints the recipe without GPU. `--list` shows the silhouettes. Owner-metal path for Hub adapters. Does **not** run here.

Holdout 1.00 is SYNTHETIC (separable by design). Non-perfect holdout is MEASURED.

## Infer

- `infer_khipu.py` — handles-only navigator decode.

## Bench

- `bench_governed.py` — false-open, abstain recall, hallucinated citations. Never invents joules.

## Kernel smokes (live `szl_khipu`)

- `yarqa_smoke.py` — canal-local softmax, leaked ~0.
- `maskmod_smoke.py` — causal future_mass ~0.
- `ouroboros_smoke.py` — loop-tax MEASURED ms / DERIVED overhead.
- `yuyay_smoke.py` — WGM fail-closed, Conjecture 1 OPEN.
- `kernel_smoke.py` — fail-closed assertions.
- `forge_nemo.py` — doctrine R1–R5 triage. NOT NVIDIA NeMo. NOT Nemotron.

## `kernels/` — fail-closed organs (SOFTWARE, not SGD)

Vendored from GitHub. These are the load path. Not Hub joblib. Not a 1.5B retrain.

| file | organ | cut |
| --- | --- | --- |
| `chain.py` | receipt chain | SHA-256 silhouette of SHA3-256 metal. Labeled, not faked. |
| `doctrine.py` | frozen v11 | 749/14/163. Conjecture 1 OPEN. proven_trust false. |
| `yarqa.py` | YARQA-ATTN | canal-local softmax; leak is a hard zero, not a mask |
| `maskmod.py` | MASKMOD | causal future_mass ≈ 0 |
| `receipt_attn.py` | receipt attention | tiled residual vs naive is the honesty metric |
| `ouroboros.py` | ouroboros | loop-tax on self-referential decode |
| `block_kv.py` | block KV | paged gather + BlockWitness on swap |
| `lambda_gate.py` | λ-gate | WGM fail-closed; Λ uniqueness is Conjecture 1 OPEN |
| `governed_norm.py` | RMSNorm | unit residual + integrity digest |
| `formulas.py` | formulas | numeric CHECKED, locked-8 STRUCTURAL. CHECKED ≠ PROVEN |
| `blocked.py` | blocked | HARD_DENY > λ veto > HARD_ALLOW; output is None on BLOCK |
| `nemo_rules.py` | szl-nemo | `rule_check()` R1–R5. Stdlib only. Joblib is quarantined. |

```python
from kernels.nemo_rules import rule_check
ok, violated = rule_check(prompt, answer)
```

## Cards

`hf/*.md` / Space `cards/*.md` — one polished Hub card per model id.

Doctrine v11 LOCKED · 749/14/163 · Λ uniqueness Conjecture 1 OPEN. Apache-2.0. Sign receipts before you call a merge a model.
