# =============================================================================
# ATTRIBUTION — this file wraps external MIT-licensed software; it is NOT
# clean-room and does NOT claim to be. We absorb openly with full credit.
#
# llama.cpp
#   URL    : https://github.com/ggml-org/llama.cpp
#   Commit : 253ba110bcd372207ca7b0bb56f1ea10d60d53fd  (HEAD at integration)
#   License: MIT  —  Copyright (c) 2023-2026 The ggml authors
#             Permission is hereby granted, free of charge, to any person
#             obtaining a copy of this software and associated documentation
#             files (the "Software"), to deal in the Software without
#             restriction, including without limitation the rights to use,
#             copy, modify, merge, publish, distribute, sublicense, and/or
#             sell copies of the Software, and to permit persons to whom the
#             Software is furnished to do so, subject to the following
#             conditions: The above copyright notice and this permission notice
#             shall be included in all copies or substantial portions of the
#             Software.
#
# llama-cpp-python  (official Python binding — MIT)
#   URL    : https://github.com/abetlen/llama-cpp-python
#   Version: 0.3.x  (latest release v0.3.23-cu123 at integration)
#   License: MIT  —  Copyright (c) 2023 Andrei Betlen
#
# Wrap strategy: llama-cpp-python (pip install llama-cpp-python).
#   Chosen over raw subprocess because llama-cpp-python exposes logits
#   directly in Python, removing shell-quoting fragility and enabling
#   deterministic argmax without re-parsing text output.
#   Dependency is one pip install; still MIT; still local inference.
#
# Springboard rule: the launchpad is theirs; the landing form is ours.
#   RIMAY kernel signature  (state, world, features, priors, seed) -> int
#   is preserved exactly.  This wrapper translates that contract onto
#   llama.cpp inference.
# =============================================================================

from __future__ import annotations

from typing import Sequence

# ---------------------------------------------------------------------------
# Lazy import: llama-cpp-python is an optional runtime dep.
# Code remains importable for mocking / unit tests without it installed.
# ---------------------------------------------------------------------------
try:
    from llama_cpp import Llama  # type: ignore
    _LLAMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LLAMA_AVAILABLE = False
    Llama = None  # type: ignore


# ---------------------------------------------------------------------------
# Module-level model cache: one Llama handle per model_path.
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict[str, "Llama"] = {}


def _get_model(model_path: str, n_ctx: int = 512) -> "Llama":
    """Load (or return cached) llama.cpp model handle."""
    if not _LLAMA_AVAILABLE:
        raise ImportError(
            "llama-cpp-python is not installed. "
            "Run: pip install llama-cpp-python"
        )
    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            logits_all=False,
            verbose=False,
        )
    return _MODEL_CACHE[model_path]


# ---------------------------------------------------------------------------
# RIMAY kernel — llama.cpp path
# Signature: (state, world, features, priors, seed) -> int
#
# Mapping:
#   state    : ignored by this path (context is encoded in world tokens)
#   world    : list[int] — token-id context fed to llama.cpp as prompt
#   features : Sequence[float] — additive bias over the prior logit vector
#   priors   : Sequence[float] — reference logit vector (same vocab size)
#   seed     : int — passed to llama.cpp for deterministic sampling
#
# Returns:
#   int — argmax( priors + features + llama_logits ) over shared vocab
#         (deterministic; no stochastic sampling — exact replay guaranteed)
# ---------------------------------------------------------------------------

def propose(
    state,
    world: Sequence[int],
    features: Sequence[float],
    priors: Sequence[float],
    seed: int,
    *,
    model_path: str = "",
    _mock_logits: Sequence[float] | None = None,
) -> int:
    """
    RIMAY (state, world, features, priors, seed) -> int  — llama.cpp path.

    Production use:   supply model_path pointing to a .gguf file.
    Test / mock use:  supply _mock_logits to bypass llama.cpp entirely;
                      the wrapper's own deterministic arithmetic is still
                      exercised (features + priors combination, argmax).
    """
    vocab_size = len(priors)
    if vocab_size == 0:
        raise ValueError("priors must be non-empty")
    if len(features) != vocab_size:
        raise ValueError("features and priors must have equal length")

    # --- acquire llama.cpp logits (or mock) --------------------------------
    if _mock_logits is not None:
        llama_logits = list(_mock_logits)
    elif model_path:
        llm = _get_model(model_path)
        # llama-cpp-python: create_completion with logprobs exposes raw logits
        # We call eval directly to extract next-token logit vector.
        # seed is passed at model load time or via context reset; here we
        # reset the sampler seed before the call.
        llm.reset()
        llm.set_seed(seed)
        llm.eval(list(world) if world else [0])
        # scores() returns a flat array of length vocab_size for last token
        raw = llm.scores[-1]  # numpy array or list
        llama_logits = [float(x) for x in raw[:vocab_size]]
    else:
        # No model path and no mock: fall back to zero-bias (test-safe).
        llama_logits = [0.0] * vocab_size

    # --- combine: priors + features + llama_logits -------------------------
    # Deterministic: no sampling, pure argmax.  seed already consumed above
    # for llama.cpp's internal ordering; our combination is seedless-exact.
    combined = [
        priors[i] + features[i] + llama_logits[i]
        for i in range(vocab_size)
    ]
    return int(combined.index(max(combined)))
