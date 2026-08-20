# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
step_3_7_flash.py — Step-3.7-Flash voter (StepFun / 阶跃星辰).

Backend: StepFun API (primary) or OpenRouter (secondary).
Env vars: STEPFUN_API_KEY or OPENROUTER_API_KEY.
198B MoE vision-language model. Off by default.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter


class Step37FlashVoter(BaseVoter):
    VOTER_ID = "step-3.7-flash"
    ENV_VARS = ["STEPFUN_API_KEY", "OPENROUTER_API_KEY"]
    LICENSE = "Open weights"
    PROVIDER = "StepFun / OpenRouter"
    CONTEXT_WINDOW = 32768
    MODEL_ID = "stepfun-ai/step-3.7-flash"
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

        stepfun_key = os.environ.get("STEPFUN_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if stepfun_key:
            url = "https://api.stepfun.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {stepfun_key}",
                "Content-Type": "application/json",
            }
            model = "step-3-7b-flash"
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://szlholdings.com",
                "X-Title": "a11oy-ensemble",
            }
            model = "stepfun-ai/step-3-7b-flash"

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
