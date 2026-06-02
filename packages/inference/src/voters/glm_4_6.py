# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
glm_4_6.py — GLM-4.6 voter (Zhipu AI / z.ai).

Backend: z.ai (primary) or OpenRouter (secondary).
Env vars: ZAI_API_KEY or OPENROUTER_API_KEY.
BFCL #1 function caller. Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class GLM46Voter(BaseVoter):
    VOTER_ID = "glm-4.6"
    ENV_VARS = ["ZAI_API_KEY", "OPENROUTER_API_KEY"]
    LICENSE = "Open weights"
    PROVIDER = "Zhipu AI (z.ai) / OpenRouter"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "THUDM/GLM-4.6-9B-Chat"
    BFCL_SCORE = "#1"

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

        zai_key = os.environ.get("ZAI_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if zai_key:
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {
                "Authorization": f"Bearer {zai_key}",
                "Content-Type": "application/json",
            }
            model = "glm-4"
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://szlholdings.com",
                "X-Title": "a11oy-ensemble",
            }
            model = "thudm/glm-4.6-9b"

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
