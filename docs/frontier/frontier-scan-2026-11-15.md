# Frontier scan — 2026-11-15 (MEASURED)

Measured via the live Hugging Face API on 2026-11-15T02:10-02:25Z by the owner-delegated DC audit lane. Every row carries an estate truth label; no claim exceeds its evidence. Full scrape: hf_frontier_scrape_20261115.json, frontier_deep_scrape_20261115.json, frontier_bases_20261115.json (owner machine, C:\SZL\estate-audit).

## 1 · Open-source leaders (MEASURED unless labeled otherwise)

| Leader | Class | License | Downloads | Likes | Arch |
|---|---|---|---|---|---|
| deepseek-ai/DeepSeek-V4.1-Flash-1017 | frontier, multimodal | MIT | 434,013 | 5,710 | deepseek_v41 |
| Qwen/Qwen3.8-27B | frontier, multimodal | Apache-2.0 | 6,757,964 | 20,016 | qwen3_5 |
| Qwen/Qwen3.8-Flash-Next | fast lane; params UNKNOWN (verify at adoption) | Apache-2.0 (REPORTED, family) | 3,031,222 | 7,131 | qwen4_exp (MEASURED 2026-11-15T02:40Z — corrects the initial REPORTED qwen3_5) |
| NousResearch/Arete-27B | open post-training | Apache-2.0 | 6,191 | 595 | qwen3_5 |
| LiquidAI/LFM3-1.7B | edge class, 24 layers | other (verify) | 100,643 | 1,793 | lfm3 |
| taobao-mnn/MNN-Pocket-0.3B | ultra-tiny edge | UNKNOWN | trending | — | UNKNOWN |
| Edge0/Edge0-145B-NVFP4 | quantized frontier | UNKNOWN | trending | — | UNKNOWN |
| moonshotai/Kimi-K3.1-Pro, meituan-longcat/LongCat-2.5 | frontier | UNKNOWN | trending | — | UNKNOWN |

Community signals (MEASURED): the DeepSeek-V4.1-Flash GGUF ecosystem is exploding (ISTA-DASLab 3,983,957 dl; unsloth 1,388,600; antirez 808,948) — local-first inference is where the estate's edge doctrine already lives. Qwen small fleet remains the download backbone (Qwen3-0.6B 18,515,687 dl; Qwen3-1.7B 3,019,503).

Data leaders (MEASURED): NousResearch/arete-data-pairs — open post-training pairs, 10K<n<100K, text-gen QA, 1,521 dl. google/physical-engineerings-last-exam — official hard-physics benchmark, CC-BY-4.0, 43,834 dl.

Toolchain (MEASURED): transformers latest = 5.23.0. The Qwen3.8 line runs the qwen3_5 architecture — the same model_type that errored 33 estate battery models on 2026-11-14 (ValueError: Transformers does not recognize qwen3_5). Adoption of transformers >= 5.23.0 in the battery lane is the direct fix (torch compatibility must be verified on the battery host).

## 2 · The estate's unmatched lane (PROVED by live receipts)

No scanned leader ships any of these, all MEASURED on the live estate:

- **Per-answer cryptographic provenance** — DSSE/ECDSA-P256 signer live with a measured sign+verify self-test (2026-11-15, key agreement MATCH); governed-RAG answers signed for the operator only.
- **Energy provenance ledger** — tamper-evident, bounded, rotating append-only JSONL storage (MEASURED writable, 0 dropped segments).
- **Measured honesty** — the estate battery records abstention/refusal per probe; 6 models measured 0/6 abstains with published receipts (2026-11-15); thin cards carry explicit "no benchmark recorded" statements instead of invented claims.
- **Governed deployment** — hf-sync pipeline proven green end-to-end (run 43654575730): execution handoff, readiness probe ingestion, evidence verification, byte parity, protected main.
- **Sovereign edge gateway** — llm-router-live: per-answer receipts at the edge; x402 payment challenges live on the pricing paths.

The frontier leaders publish benchmarks. The estate publishes receipts. That asymmetry is the frontier lane nobody else is standing in.

## 3 · Proposal — szl-provenance-native-v1 (ROADMAP, owner-gated)

The first provenance-native model family: a model whose every answer carries (a) a provenance channel — trained, not bolted on — pointing at the receipts that ground it, (b) calibrated abstention measured by the estate battery, and (c) per-answer DSSE + energy provenance verified at the sovereign gateway. Full stack, receipt-bound at every layer:

1. **Base** (owner decision): Qwen3.8-27B is the qwen3_5-arch option that matches the estate fleet's SFT/tooling exactly; Qwen3.8-Flash-Next is the fast-lane candidate but runs the newer qwen4_exp arch (MEASURED) — adopting it requires verifying transformers qwen4_exp support (5.23.0 is the current latest; support status UNKNOWN) and license re-check. Alternative edge-class base: LFM3-1.7B (license review required).
2. **Data**: arete-data-pairs (open pairs) x the estate governed-sft-mix + a provenance-channel synthetic corpus derived from frontier-54-runs receipts (answers paired with the receipts that prove them).
3. **Evaluation**: physical-engineerings-last-exam (CC-BY-4.0 official bench, receipt-bound results) + estate battery abstention measurement + the readiness tiles.
4. **Deployment**: sovereign gateway with per-answer DSSE receipts and energy provenance; honest 8-tile readiness gating (READY only when the tiles are READY).
5. **Doctrine**: every card claim bound to a receipt sha256; errors recorded as errors; no quality claims beyond measurement.

No open-source leader trains provenance emission or measures abstention with published receipts. This is the lane.

## 4 · Immediate operational consequences (MEASURED where stated)

**2026-11-15T02:45Z update (MEASURED):** the v4 pinned-pip battery rerun has landed 12 model receipts (all abstained_or_refused 0 of 6, including six models that errored in the v3 attempt — the qwen3_5 loader fix is confirmed working). All 12 model cards are bound to their receipts with sha256 + readback verification (battery_card_bind_log.jsonl, owner machine). Remaining v3-error models continue landing as v4 progresses.

**2026-11-15T03:00Z addendum (MEASURED):** v4 receipts now carry measured energy per model run (joules_measured, avg_watts, gpu, wall_hours) — energy provenance is now receipt-bound at the per-run level. The provenance-pair corpus builder v1.1 is built and sha256-logged on the owner machine (provenance_sft_corpus_v1.jsonl; build log provenance_corpus_build_log.json): every pair carries its receipt pointer, receipt sha256, measured behavior label (text / echo_question / abstained), and the measured energy envelope. Responses are labeled as measured outputs, not verified content — usable for provenance-emission and abstention-calibration lanes only.

- The 33 qwen3_5-errored battery models: fix = transformers >= 5.23.0 on the battery host (torch compat verify). bitsandbytes and LoraConfig alora_invocation_tokens errors need the pinned-pip pass already in flight (v4).
- Receipt-to-card binding is automated (watch_batteries.py live on the owner machine; battery_card_bind_log.jsonl pattern).
- GPU + 14 secrets remain the only blockers on 5 of 8 readiness tiles (owner-only).

Machine-authored under standing CTO delegation; signed as Lutar, Stephen P.
