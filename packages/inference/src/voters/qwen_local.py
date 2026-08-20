# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
qwen_local.py — SOVEREIGN DEFAULT voter.

Qwen-local is the floor: it ALWAYS participates regardless of any env var.
When the local vLLM endpoint is unreachable it degrades to a clearly-labelled
deterministic stub — never a hallucinated completion.

Sovereign-default: qwen-local is ALWAYS in the voter pool. The aggregator may
receive a stub response, but it never gets silence from the sovereign floor.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class QwenLocalVoter(BaseVoter):
    VOTER_ID = "qwen-local"
    ENV_VARS = []           # No env var required — sovereign default
    LICENSE = "Apache-2.0"
    PROVIDER = "local-vLLM"
    CONTEXT_WINDOW = 32768
    MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
    BFCL_SCORE = None

    # Sovereign-default: always available
    def is_available(self) -> bool:
        return True

    def _active_env_var(self):
        return None  # No env var needed

    async def _call(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        vllm_url = os.environ.get("QWEN_LOCAL_URL", "http://127.0.0.1:8000/v1/chat/completions")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.MODEL_ID,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(vllm_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            # Sovereign-default stub — clearly labelled, never fabricated
            return (
                f"[qwen-local · STUB · local vLLM unreachable] "
                f"Deterministic stub response for: {prompt[:80]!r}. "
                f"Deploy a local vLLM serving {self.MODEL_ID} at QWEN_LOCAL_URL to enable real inference."
            )
