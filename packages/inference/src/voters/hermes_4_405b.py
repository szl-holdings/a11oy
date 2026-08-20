# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
hermes_4_405b.py — Hermes-4-405B voter (Nous Research).

Backend: Nous Research Portal (primary), OpenRouter (secondary), HF (tertiary).
Env vars: NOUS_API_KEY or HF_TOKEN.
Hybrid <think> reasoning + ChatML. Off by default.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class Hermes4405BVoter(BaseVoter):
    VOTER_ID = "hermes-4-405b"
    ENV_VARS = ["NOUS_API_KEY", "HF_TOKEN"]
    LICENSE = "Open weights (Llama 3.1 base)"
    PROVIDER = "Nous Research / OpenRouter / HuggingFace"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "NousResearch/Hermes-4-405B"
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

        nous_key = os.environ.get("NOUS_API_KEY")
        hf_token = os.environ.get("HF_TOKEN")

        if nous_key:
            url = "https://inference.nous.systems/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {nous_key}",
                "Content-Type": "application/json",
            }
            model = "hermes-4-405b"
        else:
            # HF Inference fallback
            url = "https://api-inference.huggingface.co/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json",
            }
            model = self.MODEL_ID

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            # Strip <think>...</think> blocks from hybrid reasoning output
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return text
