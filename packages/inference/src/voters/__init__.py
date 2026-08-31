# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
voters/__init__.py — Registry of a11oy v4 ensemble voters.

Sovereign-default: khipu-gguf (pinned SZL-Khipu GGUF on the CPU lab) is ALWAYS
first and never removed. Llama / Mistral / Qwen Hugging Face voters remain
optional cloud voters; they are not the sovereign path. qwen-local stays in
the pool as an always-on local floor that stubs when vLLM is unreachable.
"""
from __future__ import annotations

from typing import Dict, List

from .base_voter import BaseVoter, VOTER_INPUT_SCHEMA, VOTER_OUTPUT_SCHEMA

# ── Sovereign default: pinned Khipu GGUF CPU lab ─────────────────────────────
from .khipu_gguf import KhipuGGUFVoter, SOVEREIGN_VOTER_ID

# ── Local floor + optional HF cloud voters (not sovereign) ───────────────────
from .qwen_local import QwenLocalVoter
from .hf_inference_voter import (
    HFInferenceLlamaVoter,
    HFInferenceMistralVoter,
    HFInferenceQwenVoter,
)

# ── 9 additional cloud voters (feat/llm-roster-expansion-9-voters) ───────────
from .deepseek_r1 import DeepSeekR1Voter
from .kimi_k2 import KimiK2Voter
from .glm_4_6 import GLM46Voter
from .hermes_4_405b import Hermes4405BVoter
from .minimax_m2 import MiniMaxM2Voter
from .step_3_7_flash import Step37FlashVoter
from .nomos_1 import Nomos1Voter
from .nemotron_super_49b import NemotronSuper49BVoter
from .xiaomi_mimo import XiaomiMiMoVoter

# Ordered: sovereign-default first, then local floor, then optional HF, then 9
_ALL_VOTER_INSTANCES: List[BaseVoter] = [
    KhipuGGUFVoter(),           # sovereign-default: pinned GGUF CPU lab
    QwenLocalVoter(),           # local floor (stubs if vLLM unreachable)
    HFInferenceLlamaVoter(),    # optional cloud — not sovereign
    HFInferenceMistralVoter(),  # optional cloud — not sovereign
    HFInferenceQwenVoter(),     # optional cloud — not sovereign
    DeepSeekR1Voter(),
    KimiK2Voter(),
    GLM46Voter(),
    Hermes4405BVoter(),
    MiniMaxM2Voter(),
    Step37FlashVoter(),
    Nomos1Voter(),
    NemotronSuper49BVoter(),
    XiaomiMiMoVoter(),
]

_VOTER_MAP: Dict[str, BaseVoter] = {v.VOTER_ID: v for v in _ALL_VOTER_INSTANCES}

VOTER_COUNT = len(_ALL_VOTER_INSTANCES)  # 14


def get_all_voters() -> List[BaseVoter]:
    """Return all registered voter instances (sovereign-default first)."""
    return list(_ALL_VOTER_INSTANCES)


def get_voter(voter_id: str) -> BaseVoter | None:
    """Look up a voter by ID."""
    return _VOTER_MAP.get(voter_id)


def resolve_voters(requested: List[str] | None) -> List[BaseVoter]:
    """Return voters to run for a given request.

    If `requested` is None/empty → only khipu-gguf (sovereign-default).
    Otherwise → intersection of requested IDs with the registry, preserving
    order. khipu-gguf is always prepended as the sovereign floor.
    """
    sovereign = _VOTER_MAP[SOVEREIGN_VOTER_ID]
    if not requested:
        return [sovereign]
    out: List[BaseVoter] = []
    seen = set()
    out.append(sovereign)
    seen.add(SOVEREIGN_VOTER_ID)
    for vid in requested:
        if vid in seen:
            continue
        voter = _VOTER_MAP.get(vid)
        if voter is not None:
            out.append(voter)
            seen.add(vid)
    return out


__all__ = [
    "BaseVoter",
    "VOTER_INPUT_SCHEMA",
    "VOTER_OUTPUT_SCHEMA",
    "VOTER_COUNT",
    "SOVEREIGN_VOTER_ID",
    "get_all_voters",
    "get_voter",
    "resolve_voters",
    # Individual voter classes
    "KhipuGGUFVoter",
    "QwenLocalVoter",
    "HFInferenceLlamaVoter",
    "HFInferenceMistralVoter",
    "HFInferenceQwenVoter",
    "DeepSeekR1Voter",
    "KimiK2Voter",
    "GLM46Voter",
    "Hermes4405BVoter",
    "MiniMaxM2Voter",
    "Step37FlashVoter",
    "Nomos1Voter",
    "NemotronSuper49BVoter",
    "XiaomiMiMoVoter",
]
