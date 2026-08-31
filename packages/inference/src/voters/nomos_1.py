# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
nomos_1.py — Nomos-1 voter (Nous Research).

Backend: Nous Research Portal (primary) or HF Inference (secondary).
Env vars: NOUS_API_KEY or HF_TOKEN.
30B SOTA mathematician — critical for Lean kernel work.
Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class Nomos1Voter(BaseVoter):
    VOTER_ID = "nomos-1"
    ENV_VARS = ["NOUS_API_KEY", "HF_TOKEN"]
    LICENSE = "Open weights"
    PROVIDER = "Nous Research / HuggingFace"
    CONTEXT_WINDOW = 32768
    MODEL_ID = "NousResearch/Nomos-1-30B"
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
            model = "nomos-1"
        else:
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
            return data["choices"][0]["message"]["content"]
