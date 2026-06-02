# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
deepseek_r1.py — DeepSeek-R1 voter.

Backend: DeepSeek API (primary) or HF Inference (secondary).
Env vars: DEEPSEEK_API_KEY or HF_TOKEN.
Off by default — activate by listing "deepseek-r1" in voters and having the env var.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class DeepSeekR1Voter(BaseVoter):
    VOTER_ID = "deepseek-r1"
    ENV_VARS = ["DEEPSEEK_API_KEY", "HF_TOKEN"]
    LICENSE = "MIT (open weights)"
    PROVIDER = "DeepSeek API / HuggingFace Inference"
    CONTEXT_WINDOW = 65536
    MODEL_ID = "deepseek-ai/DeepSeek-R1"
    BFCL_SCORE = None

    async def _call(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key:
            # DeepSeek API (OpenAI-compat)
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "deepseek-reasoner",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        else:
            # Fallback: HF Inference API
            hf_token = os.environ.get("HF_TOKEN", "")
            url = "https://api-inference.huggingface.co/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.MODEL_ID,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            # Strip <think>...</think> blocks from reasoning output if present
            text = data["choices"][0]["message"]["content"]
            return text
