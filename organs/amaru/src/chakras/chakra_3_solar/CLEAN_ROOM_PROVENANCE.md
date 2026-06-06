# CLEAN_ROOM_PROVENANCE

## Status: Attribution-Based Absorption — NOT Clean-Room

This file documents the provenance of `rimay_llamacpp_path.py`.

---

### What "clean-room" would mean

A clean-room implementation is written without reference to the original
source, by engineers who have never read it, to avoid copyright entanglement.
Clean-room is a legal strategy for copyleft or proprietary situations.

### Why clean-room does not apply here

llama.cpp is MIT-licensed.  
MIT grants unrestricted use, modification, and redistribution provided the
copyright notice and permission notice are preserved.  
There is no copyleft; there is no patent clause.  
Clean-room engineering is unnecessary and would be dishonest theatre.

### What we actually do: attribution-based absorption

| Item | Value |
|------|-------|
| Source repo | https://github.com/ggml-org/llama.cpp |
| License | MIT — Copyright (c) 2023-2026 The ggml authors |
| HEAD commit at integration | `253ba110bcd372207ca7b0bb56f1ea10d60d53fd` |
| Python binding | https://github.com/abetlen/llama-cpp-python |
| Python binding license | MIT — Copyright (c) 2023 Andrei Betlen |
| Python binding version | 0.3.x (latest: v0.3.23-cu123 at integration) |

We wrap llama.cpp via llama-cpp-python.  
We do not fork it.  
We do not strip or obscure its copyright.  
The attribution comment block at the top of `rimay_llamacpp_path.py`
reproduces the MIT permission notice verbatim, as required by the license.

### What is ours

The RIMAY kernel signature `(state, world, features, priors, seed) -> int`
and the combination layer `priors + features + llama_logits -> argmax` are
our interface design.  The launchpad (llama.cpp inference) is theirs.
The landing form (RIMAY contract) is ours.

### Obligations satisfied

- [x] Copyright notice preserved in source file header
- [x] Permission notice preserved in source file header
- [x] Repository URL and commit SHA recorded
- [x] License type stated in every relevant file
- [x] No claim of authorship over llama.cpp code
