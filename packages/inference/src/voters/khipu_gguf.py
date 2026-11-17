# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem).
"""Retired Khipu CPU-lab voter and historical model metadata.

The legacy OpenAI generation contract is retired. This voter cannot infer
operator authentication or public-prompt acknowledgement from ensemble input.
It remains discoverable as unavailable and never forwards a prompt. Explicit
generation belongs to the existing authenticated Atelier CPU-lab turn route.
Historical artifact pins and receipt parsers are compatibility metadata only.
Lambda uniqueness remains Conjecture 1.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse


from .base_voter import BaseVoter

# Public dummy for the CPU lab. Not a credential. Never substitute a real token.
KHIPU_LAB_DUMMY_BEARER = "not-a-secret"

KHIPU_LAB_LOCKED_ORIGIN = "https://szlholdings-szl-model-inference-lab.hf.space"
KHIPU_LAB_LOCKED_HOST = "szlholdings-szl-model-inference-lab.hf.space"
KHIPU_LAB_DEFAULT_BASE = KHIPU_LAB_LOCKED_ORIGIN
KHIPU_LAB_V1 = KHIPU_LAB_LOCKED_ORIGIN + "/v1"
_FORBIDDEN_LAB_NEEDLES = (
    "forge-lab",
    "forge_lab",
    "trainer",
    "serve-studio",
    "serve_studio",
    "servestudio",
)
KHIPU_MODEL_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
KHIPU_MODEL_REV = "67d60ec577730747055491640cfb91fc4a4b5d25"
KHIPU_GGUF_FILE = "SZL-Khipu-1.5B-Q4_K_M.gguf"
KHIPU_GGUF_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
KHIPU_MAX_TOKENS = 32
KHIPU_TEMPERATURE = 0.0

# Past observation of one successful POST. Shown as MEASURED history, never as
# a live tokens/s figure.
KHIPU_MEASURED_PROBE_2026_08_28: Dict[str, Any] = {
    "label": "MEASURED",
    "when": "2026-08-28 ~12:32pm ET",
    "http_status": 200,
    "wall_s": 2.498,
    "usage": {"prompt_tokens": 51, "completion_tokens": 21, "total_tokens": 72},
    "elapsed_ms": 2053,
    "signature": "UNSIGNED",
    "record_sha256": "f19b63a619094d5c13b98f399c7f632862bae571f9f3f72cdcad6110f6e56c8d",
}

SOVEREIGN_VOTER_ID = "khipu-gguf"
KHIPU_SUCCESSOR_PATH = "/api/a11oy/v1/atelier/cpu-lab/turn"
KHIPU_RETIRED_REASON = (
    "RETIRED: legacy CPU-lab generation is disabled. Use the authenticated "
    "Atelier CPU-lab turn with explicit public-prompt acknowledgement."
)


def khipu_successor() -> Dict[str, Any]:
    return {
        "method": "POST",
        "path": KHIPU_SUCCESSOR_PATH,
        "ui": "/command-centre#cpu-work",
        "operator_authentication_required": True,
        "public_share_acknowledged": True,
        "declared": "PUBLIC",
        "max_output_tokens": KHIPU_MAX_TOKENS,
        "grounding_required": True,
        "authority": "PROPOSAL_ONLY",
        "automatic_forwarding": False,
    }


def _is_test_or_loopback_host(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    return h in {"127.0.0.1", "localhost", "::1"} or h.endswith(".test")


def khipu_lab_base() -> str:
    """CPU lab origin (no /v1). Production is locked to szl-model-inference-lab.

    A11OY_KHIPU_LAB_BASE may retarget loopback or RFC 2606 ``*.test`` hosts for
    hermetic tests. Forge-lab, trainer, Serve Studio, and any other production
    host are ignored — the locked inference-lab origin is used instead.
    """
    raw = os.environ.get("A11OY_KHIPU_LAB_BASE", "").strip()
    if not raw:
        return KHIPU_LAB_LOCKED_ORIGIN
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "").lower()
    blob = raw.lower()
    if any(needle in blob for needle in _FORBIDDEN_LAB_NEEDLES):
        return KHIPU_LAB_LOCKED_ORIGIN
    if scheme not in {"http", "https"}:
        return KHIPU_LAB_LOCKED_ORIGIN
    if host == KHIPU_LAB_LOCKED_HOST:
        return KHIPU_LAB_LOCKED_ORIGIN
    if _is_test_or_loopback_host(host):
        return ("%s://%s" % (parsed.scheme, parsed.netloc)).rstrip("/")
    return KHIPU_LAB_LOCKED_ORIGIN


def khipu_lab_v1() -> str:
    """Historical retired OpenAI base; metadata only, never a generation target."""
    return khipu_lab_base() + "/v1"


def khipu_pin() -> Dict[str, Any]:
    return {
        "lab_base": khipu_lab_base(),
        "lab_v1": khipu_lab_v1(),
        "lab_v1_state": "RETIRED",
        "locked_lab_v1": KHIPU_LAB_V1,
        "model_repo": KHIPU_MODEL_REPO,
        "model_rev": KHIPU_MODEL_REV,
        "gguf_file": KHIPU_GGUF_FILE,
        "gguf_sha256": KHIPU_GGUF_SHA256,
        "max_tokens": KHIPU_MAX_TOKENS,
        "temperature": KHIPU_TEMPERATURE,
        "stream": False,
        "auth": "RETIRED ? no inference credential is used by this voter",
        "generation_state": "RETIRED",
        "operational": False,
        "successor": khipu_successor(),
        "gpu_inference_endpoint": "ROADMAP",
        "forge_lab": "SNAPSHOT",
        "forge_lab_role": "not a trainer, not Serve Studio",
        "energy_attested_runs": "UNAVAILABLE",
        "killinchu_detector": "SIMULATED",
        "lambda": "Conjecture 1",
    }


def clamp_max_tokens(max_tokens: Any) -> int:
    try:
        n = int(max_tokens)
    except (TypeError, ValueError):
        n = KHIPU_MAX_TOKENS
    if n < 1:
        n = 1
    if n > KHIPU_MAX_TOKENS:
        n = KHIPU_MAX_TOKENS
    return n


def extract_lab_receipt(data: Dict[str, Any]) -> Dict[str, Any]:
    """Pull UNSIGNED / record_sha256 from the lab JSON without inventing them."""
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    signing = data.get("signing") if isinstance(data.get("signing"), dict) else {}

    sig: Any = (
        data.get("signature")
        or receipt.get("signature")
        or signing.get("signature")
        or signing.get("status")
        or provenance.get("signature")
    )
    if isinstance(sig, dict):
        if sig.get("signed") is False or not sig.get("signatures"):
            sig = "UNSIGNED"
        else:
            sig = sig.get("status") or "UNKNOWN"
    if not sig:
        sig = "UNKNOWN"

    sha = (
        data.get("record_sha256")
        or data.get("record_sha")
        or receipt.get("sha256")
        or receipt.get("record_sha256")
        or provenance.get("record_sha256")
    )
    if not sha:
        sha = "UNKNOWN"

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    text = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
        text = msg.get("content") or choices[0].get("text") or ""
    if not text:
        text = data.get("text") or ""

    elapsed = data.get("elapsed_ms")
    try:
        elapsed_ms = int(elapsed) if elapsed is not None else None
    except (TypeError, ValueError):
        elapsed_ms = None

    return {
        "text": str(text),
        "signature": str(sig),
        "record_sha256": str(sha),
        "usage": usage,
        "elapsed_ms": elapsed_ms,
        "model": data.get("model") or ("%s@%s" % (KHIPU_MODEL_REPO, KHIPU_MODEL_REV)),
    }


class KhipuGGUFVoter(BaseVoter):
    VOTER_ID = SOVEREIGN_VOTER_ID
    ENV_VARS = []
    LICENSE = "Apache-2.0"
    PROVIDER = "SZL CPU inference lab (llama.cpp GGUF)"
    CONTEXT_WINDOW = 32768
    MODEL_ID = "%s@%s" % (KHIPU_MODEL_REPO, KHIPU_MODEL_REV)
    BFCL_SCORE = None

    def is_available(self) -> bool:
        return False

    def _active_env_var(self):
        return None

    def metadata(self) -> Dict[str, Any]:
        return {
            **super().metadata(),
            "status": "unavailable",
            "state": "RETIRED",
            "reason": KHIPU_RETIRED_REASON,
            "successor": khipu_successor(),
        }

    async def vote(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = KHIPU_MAX_TOKENS,
        temperature: float = KHIPU_TEMPERATURE,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        result = await super().vote(
            prompt, system=system, max_tokens=max_tokens,
            temperature=temperature, **kwargs,
        )
        result["reason"] = KHIPU_RETIRED_REASON
        return result

    async def _call(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = KHIPU_MAX_TOKENS,
        temperature: float = KHIPU_TEMPERATURE,
        **kwargs: Any,
    ) -> str:
        raise RuntimeError(KHIPU_RETIRED_REASON)
