# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
hf_inference_voter.py — Three HF Inference free-tier voters:
  - hf-inference-llama   (Meta-Llama-3.1-70B-Instruct)
  - hf-inference-mistral (Mistral-7B-Instruct-v0.3)
  - hf-inference-qwen    (Qwen2.5-72B-Instruct via HF)

All three use HF_TOKEN.  Off by default; activate by including voter_id in
the `voters` list AND having HF_TOKEN in the env.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .base_voter import BaseVoter

HF_INFERENCE_BASE = "https://api-inference.huggingface.co/models"


class _HFInferenceBaseVoter(BaseVoter):
    ENV_VARS = ["HF_TOKEN"]
    LICENSE = "various-open"
    PROVIDER = "HuggingFace Inference API"
    BFCL_SCORE = None

    async def _call(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        token = os.environ.get("HF_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
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
        url = "https://api-inference.huggingface.co/v1/chat/completions"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class HFInferenceLlamaVoter(_HFInferenceBaseVoter):
    VOTER_ID = "hf-inference-llama"
    LICENSE = "Llama 3 Community"
    PROVIDER = "HuggingFace Inference API (Meta-Llama)"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "meta-llama/Meta-Llama-3.1-70B-Instruct"


class HFInferenceMistralVoter(_HFInferenceBaseVoter):
    VOTER_ID = "hf-inference-mistral"
    LICENSE = "Apache-2.0"
    PROVIDER = "HuggingFace Inference API (Mistral)"
    CONTEXT_WINDOW = 32768
    MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"


class HFInferenceQwenVoter(_HFInferenceBaseVoter):
    VOTER_ID = "hf-inference-qwen"
    LICENSE = "Apache-2.0"
    PROVIDER = "HuggingFace Inference API (Qwen)"
    CONTEXT_WINDOW = 131072
    MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
