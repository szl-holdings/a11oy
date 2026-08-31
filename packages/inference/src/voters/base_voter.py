# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem; 163 sorries).
# Authored by Yachay (CTO). DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
base_voter.py — Abstract base class for all a11oy v4 multi-LLM ensemble voters.

Every voter MUST:
  - Declare a VOTER_ID (str), ENV_VARS (list[str]), LICENSE, PROVIDER, CONTEXT_WINDOW
  - Implement _call(prompt, **kwargs) -> str  (raw model text completion)
  - Never fabricate a response when unavailable; return {status: "unavailable"} instead.

Voter is OFF by default. Only activates when:
  1. Caller explicitly lists it in the `voters` field of /agent/ask
  2. At least one of its ENV_VARS is present in os.environ

Λ-aggregator: untouched (Conjecture 1, 163 sorries). Provenance entries appended.
"""
from __future__ import annotations

import abc
import asyncio
import os
import time
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# JSON Schema for voter input/output (additionalProperties: false)
# ---------------------------------------------------------------------------

VOTER_INPUT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "title": "VoterInput",
    "required": ["prompt"],
    "additionalProperties": False,
    "properties": {
        "prompt": {"type": "string", "description": "The user prompt to route to this voter."},
        "system": {"type": "string", "description": "Optional system prompt override."},
        "max_tokens": {"type": "integer", "default": 512, "minimum": 1, "maximum": 8192},
        "temperature": {"type": "number", "default": 0.7, "minimum": 0.0, "maximum": 2.0},
    },
}

VOTER_OUTPUT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "title": "VoterOutput",
    "additionalProperties": False,
    "properties": {
        "voter_id": {"type": "string"},
        "status": {"type": "string", "enum": ["ok", "unavailable", "error"]},
        "text": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
        "latency_ms": {"type": ["number", "null"]},
        "provenance": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "provider": {"type": "string"},
                "model_id": {"type": "string"},
                "license": {"type": "string"},
                "env_var_used": {"type": ["string", "null"]},
                "timestamp_utc": {"type": "string"},
            },
        },
    },
}


class BaseVoter(abc.ABC):
    """Abstract base voter for the a11oy v4 multi-LLM ensemble."""

    # Subclasses MUST override:
    VOTER_ID: str = ""
    ENV_VARS: List[str] = []  # First present one is used
    LICENSE: str = ""
    PROVIDER: str = ""
    CONTEXT_WINDOW: int = 4096
    MODEL_ID: str = ""
    BFCL_SCORE: Optional[str] = None  # e.g. "#1" or None

    def is_available(self) -> bool:
        """True iff at least one required env var is present."""
        return any(os.environ.get(v) for v in self.ENV_VARS)

    def _active_env_var(self) -> Optional[str]:
        """Return the first present env var name (not the value)."""
        for v in self.ENV_VARS:
            if os.environ.get(v):
                return v
        return None

    @abc.abstractmethod
    async def _call(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Perform the actual LLM call. Must return a non-empty string.
        Raise any exception on failure; the wrapper handles it.
        """
        ...

    async def vote(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Entry point called by the aggregator. Never raises.

        If the env var is missing → returns {status: "unavailable"}.
        If the call fails    → returns {status: "error"}.
        If success           → returns {status: "ok", text: <str>}.
        """
        import datetime

        env_var_used = self._active_env_var()
        provenance = {
            "provider": self.PROVIDER,
            "model_id": self.MODEL_ID,
            "license": self.LICENSE,
            "env_var_used": env_var_used,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if not self.is_available():
            return {
                "voter_id": self.VOTER_ID,
                "status": "unavailable",
                "text": None,
                "reason": (
                    f"token_not_present — none of {self.ENV_VARS} found in runtime env; "
                    "set the env var to activate this voter."
                ),
                "latency_ms": None,
                "provenance": provenance,
            }

        t0 = time.monotonic()
        try:
            text = await self._call(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            return {
                "voter_id": self.VOTER_ID,
                "status": "ok",
                "text": text,
                "reason": None,
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "provenance": provenance,
            }
        except Exception as exc:
            return {
                "voter_id": self.VOTER_ID,
                "status": "error",
                "text": None,
                "reason": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "provenance": provenance,
            }

    def metadata(self) -> Dict[str, Any]:
        """Return voter metadata for /agent/voters endpoint."""
        avail = self.is_available()
        return {
            "voter_id": self.VOTER_ID,
            "status": "available" if avail else "token_required",
            "provider": self.PROVIDER,
            "license": self.LICENSE,
            "context_window": self.CONTEXT_WINDOW,
            "bfcl_score": self.BFCL_SCORE,
            "env_vars": self.ENV_VARS,
            "model_id": self.MODEL_ID,
        }
