# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
voters/__init__.py — Registry of all 13 a11oy v4 ensemble voters.

Sovereign-default: qwen-local is ALWAYS first and never removed.
Cloud voters: off by default, activate via env var + explicit voters list.
"""
from __future__ import annotations

from typing import Dict, List

from .base_voter import BaseVoter, VOTER_INPUT_SCHEMA, VOTER_OUTPUT_SCHEMA

# ── Existing 4 voters ─────────────────────────────────────────────────────────
from .qwen_local import QwenLocalVoter
from .hf_inference_voter import (
    HFInferenceLlamaVoter,
    HFInferenceMistralVoter,
    HFInferenceQwenVoter,
)

# ── 9 new voters (feat/llm-roster-expansion-9-voters) ────────────────────────
from .deepseek_r1 import DeepSeekR1Voter
from .kimi_k2 import KimiK2Voter
from .glm_4_6 import GLM46Voter
from .hermes_4_405b import Hermes4405BVoter
from .minimax_m2 import MiniMaxM2Voter
from .step_3_7_flash import Step37FlashVoter
from .nomos_1 import Nomos1Voter
from .nemotron_super_49b import NemotronSuper49BVoter
from .xiaomi_mimo import XiaomiMiMoVoter

# Ordered: sovereign-default first, then existing HF voters, then 9 new voters
_ALL_VOTER_INSTANCES: List[BaseVoter] = [
    QwenLocalVoter(),           # sovereign-default: always in pool
    HFInferenceLlamaVoter(),
    HFInferenceMistralVoter(),
    HFInferenceQwenVoter(),
    # --- 9 new voters ---
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

VOTER_COUNT = len(_ALL_VOTER_INSTANCES)  # 13


def get_all_voters() -> List[BaseVoter]:
    """Return all 13 registered voter instances."""
    return list(_ALL_VOTER_INSTANCES)


def get_voter(voter_id: str) -> BaseVoter | None:
    """Look up a voter by ID."""
    return _VOTER_MAP.get(voter_id)


def resolve_voters(requested: List[str] | None) -> List[BaseVoter]:
    """Return voters to run for a given request.

    If `requested` is None/empty → only qwen-local (sovereign-default).
    Otherwise → intersection of requested IDs with the registry, preserving order.
    qwen-local is always prepended as the sovereign floor.
    """
    sovereign = _VOTER_MAP["qwen-local"]
    if not requested:
        return [sovereign]
    out: List[BaseVoter] = []
    seen = set()
    # sovereign-default always first
    out.append(sovereign)
    seen.add("qwen-local")
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
    "get_all_voters",
    "get_voter",
    "resolve_voters",
    # Individual voter classes
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
