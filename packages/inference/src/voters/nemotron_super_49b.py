# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
nemotron_super_49b.py — Nemotron-Super-49B voter (NVIDIA NIM).

Backend: NVIDIA NIM API exclusively.
Env var: NVIDIA_API_KEY.
NVIDIA-optimized, "Palantir-class" reasoning. Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class NemotronSuper49BVoter(BaseVoter):
    VOTER_ID = "nemotron-super-49b"
    ENV_VARS = ["NVIDIA_API_KEY"]
    LICENSE = "NVIDIA Open Model License"
    PROVIDER = "NVIDIA NIM"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "nvidia/llama-3.3-nemotron-super-49b-v1"
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

        nvidia_key = os.environ.get("NVIDIA_API_KEY", "")

        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {nvidia_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.MODEL_ID,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
