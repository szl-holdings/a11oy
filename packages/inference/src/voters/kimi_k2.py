# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
kimi_k2.py — Kimi K2 voter (Moonshot AI).

Backend: Moonshot API (primary) or OpenRouter (secondary).
Env vars: MOONSHOT_API_KEY or OPENROUTER_API_KEY.
200k+ context window, top-tier tool calling.
Off by default — activate by listing "kimi-k2" in voters.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class KimiK2Voter(BaseVoter):
    VOTER_ID = "kimi-k2"
    ENV_VARS = ["MOONSHOT_API_KEY", "OPENROUTER_API_KEY"]
    LICENSE = "Open weights"
    PROVIDER = "Moonshot AI / OpenRouter"
    CONTEXT_WINDOW = 200000
    MODEL_ID = "moonshot-ai/kimi-k2"
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

        moonshot_key = os.environ.get("MOONSHOT_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if moonshot_key:
            url = "https://api.moonshot.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {moonshot_key}",
                "Content-Type": "application/json",
            }
            model = "kimi-k2-0711-preview"
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://szlholdings.com",
                "X-Title": "a11oy-ensemble",
            }
            model = "moonshotai/kimi-k2"

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
