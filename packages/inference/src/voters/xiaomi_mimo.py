# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
xiaomi_mimo.py — Xiaomi MiMo voter.

Backend: Nous Research Portal (primary) or direct Xiaomi endpoint (secondary).
Env vars: XIAOMI_API_KEY or NOUS_API_KEY.
Strong Chinese model. Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class XiaomiMiMoVoter(BaseVoter):
    VOTER_ID = "xiaomi-mimo"
    ENV_VARS = ["XIAOMI_API_KEY", "NOUS_API_KEY"]
    LICENSE = "Open weights (Apache-2.0)"
    PROVIDER = "Nous Research / Xiaomi direct"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "XiaomiMiMo/MiMo-7B-RL"
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

        xiaomi_key = os.environ.get("XIAOMI_API_KEY")
        nous_key = os.environ.get("NOUS_API_KEY")

        if xiaomi_key:
            # Xiaomi direct API (OpenAI-compat)
            url = "https://api.xiaomi-mimo.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {xiaomi_key}",
                "Content-Type": "application/json",
            }
            model = "mimo-7b-rl"
        else:
            # Nous Portal fallback
            url = "https://inference.nous.systems/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {nous_key}",
                "Content-Type": "application/json",
            }
            model = "xiaomi-mimo-7b"

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
