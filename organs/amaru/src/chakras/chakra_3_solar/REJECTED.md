# REJECTED CANDIDATES

## 1. ggml-org/llama.cpp — MIT ✓ license, REJECTED for complexity

- License: MIT — permissive, passes check.
- Commit SHA: `253ba110bc` d372207ca7b0bb56f1ea10d60d53fd
- `llama_decode` is a C/C++ function; no pure Python kernel can faithfully distil it within 10 lines without wrapping the compiled binary (which would be a bandaid, violating doctrine).
- The Python bindings (`llama-cpp-python`) add a third-party wrapper layer that obscures the true source lineage.
- Decision: skip. vllm's pure-PyTorch path is cleaner for a Python kernel.

## 2. huggingface/text-generation-inference — LICENSE CHECKED

- License at HEAD SHA `b4adbf2f6e`: Apache-2.0 confirmed (returned to Apache-2.0 after HFOIL period).
- NOT rejected on license.
- Rejected as **secondary** because vllm's `Sampler.sample()` is more directly minimizable: TGI's sampling is spread across Rust + Python layers, making a ≤10 line pure-Python distillation impractical without stub code.
- If vllm were unavailable, TGI would be the backup leader.
