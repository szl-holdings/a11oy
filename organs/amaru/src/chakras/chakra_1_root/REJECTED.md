# REJECTED LEADERS

## microsoft/BitNet

**URL:** https://github.com/microsoft/BitNet  
**License:** MIT — VALID  
**Reason rejected:** The 1.58-bit kernel dispatch lives in C++/CUDA infrastructure (`src/ggml-bitnet.cpp`, `src/ggml-bitnet-lut-kernels.h`). The Python-facing layer is a thin subprocess wrapper around a compiled binary (`run_inference.py`). There is no clean Python dispatch loop that can be honestly absorbed to ≤10 lines without either (a) hallucinating function signatures or (b) copying C++ semantics verbatim. The doctrine's "No hallucinated function signatures" rule prohibits reconstruction from documentation. **REJECTED.**

---

## vllm-project/vllm (MoE expert routing)

**URL:** https://github.com/vllm-project/vllm  
**License:** Apache-2.0 — VALID  
**Reason rejected:** The MoE expert routing dispatch spans at minimum three files: `vllm/model_executor/layers/fused_moe/fused_moe.py` (topk softmax + expert selection), `csrc/moe/moe_align_block_size.cu` (CUDA kernel), and `vllm/model_executor/layers/fused_moe/layer.py` (forward dispatch). The minimal honest absorption requires importing vllm's fused_moe module — which is not a ≤10 line standalone kernel. The doctrine's "if can't be honestly minimized, write WHY in REJECTED.md and stop" rule applies. **REJECTED.**

---

## Summary

Both non-chosen candidates have valid open-source licenses (MIT and Apache-2.0). Rejection is solely on minimization grounds, not license grounds.
