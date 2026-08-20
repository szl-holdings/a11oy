# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
minimax_m2.py — MiniMax-M2 voter.

Backend: MiniMax API (primary) or OpenRouter (secondary).
Env vars: MINIMAX_API_KEY or OPENROUTER_API_KEY.
1M context window. Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class MiniMaxM2Voter(BaseVoter):
    VOTER_ID = "minimax-m2"
    ENV_VARS = ["MINIMAX_API_KEY", "OPENROUTER_API_KEY"]
    LICENSE = "Open weights"
    PROVIDER = "MiniMax / OpenRouter"
    CONTEXT_WINDOW = 1000000
    MODEL_ID = "MiniMaxAI/MiniMax-M2"
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

        minimax_key = os.environ.get("MINIMAX_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if minimax_key:
            url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
            headers = {
                "Authorization": f"Bearer {minimax_key}",
                "Content-Type": "application/json",
            }
            model = "MiniMax-M2"
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://szlholdings.com",
                "X-Title": "a11oy-ensemble",
            }
            model = "minimax/minimax-m2"

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
