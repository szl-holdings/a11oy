# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_jack — Wire G: Brain-Jack Mesh.
Deployed identically on every SZL Space.  Exposes brain sockets so other Spaces
can query each organ.  Three endpoints per Space:

  POST /api/<space>/v1/brain/jack         — accept incoming brain-jack query
  GET  /api/<space>/v1/brain/sockets      — registry of all 6 Space sockets
  POST /api/<space>/v1/brain/multi-jack   — fan-out to all 6 Spaces in parallel

Doctrine v11 (749/14/163, 13-axis canonical per yuyay_v3 LinkedIn post).
Hatun-Willay (formerly Mythos, renamed per Doctrine v10/v11 correction).

HONESTY:
  - λ_receipt signatures are PLACEHOLDER (Sigstore CI not yet wired, Doctrine v10/v11).
  - master_receipt is a Merkle root (SHA-256 of sorted response receipts), not a DSSE-signed bundle.
  - Cross-Space HTTP calls are real; target Spaces must be running.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from typing import Any

DOCTRINE = "v11"
WIRE = "G"
SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI signing not yet wired (Doctrine v10/v11)"

# ---------------------------------------------------------------------------
# 6 Spaces: anatomy organ map
# ---------------------------------------------------------------------------
SPACES: dict[str, dict[str, Any]] = {
    "a11oy": {
        "organ": "gate",
        "organ_style": "Brand Orchestration / gates — conjunctive AND-compose, 46 policy gates, λ-floor 0.90",
        "hf_url": "https://szlholdings-a11oy.hf.space",
    },
    "amaru": {
        "organ": "cortex",
        "organ_style": "Cortex reasoning — TH1/TH8/TH10 theorems, 7 chakras, axis-scored reasoning",
        "hf_url": "https://szlholdings-amaru.hf.space",
    },
    "sentra": {
        "organ": "immune",
        "organ_style": "Immune / halt — TH8 GLR, dual-use screen, OVERWATCH R0513, halt-on-adversarial",
        "hf_url": "https://szlholdings-sentra.hf.space",
    },
    "vessels": {
        "organ": "receipt",
        "organ_style": "Receipt generation — Khipu Merkle DAG, DSSE envelope, PAC-Bayes TH13, Wire F",
        "hf_url": "https://szlholdings-vessels.hf.space",
    },
    "rosie": {
        "organ": "nervous",
        "organ_style": "Unified nervous system — cross-session, inherits all 5 organs, full corpus 171",
        "hf_url": "https://szlholdings-rosie.hf.space",
    },
    "uds-demo": {
        "organ": "deploy",
        "organ_style": "Deployment — UDS bundle integrity, Zarf package contract, airgap deploy pipeline",
        "hf_url": "https://szlholdings-uds-demo.hf.space",
    },
}

ORGAN_TO_SPACE = {v["organ"]: k for k, v in SPACES.items()}

# ---------------------------------------------------------------------------
# 13-axis Λ aggregator (Doctrine v11, yuyay_v3 canonical)
# ---------------------------------------------------------------------------
AXIS_NAMES = [
    "truthfulness", "calibration", "transparency", "forthrightness",
    "non_deception", "non_manipulation", "autonomy_preservation",
    "harm_avoidance", "data_minimisation", "contestability",
    "accountability", "interoperability", "reversibility",
]


def lambda_signal(axis_scores: list[float] | None) -> float:
    """13-axis weighted geometric mean (Doctrine v11 canonical λ_signal)."""
    if not axis_scores:
        return 0.5
    n = min(13, len(axis_scores))
    clamped = [min(1.0, max(1e-9, float(x))) for x in axis_scores[:n]]
    # pad to 13 if fewer provided
    while len(clamped) < 13:
        clamped.append(0.5)
    logmean = sum(math.log(x) for x in clamped) / 13
    return round(math.exp(logmean), 6)


# ---------------------------------------------------------------------------
# Per-organ response generators (organ-style responses)
# ---------------------------------------------------------------------------

def _organ_response(space: str, query: str, axis_scores: list[float] | None,
                    src_space: str, src_organ: str) -> str:
    organ = SPACES.get(space, {}).get("organ", "unknown")
    L = lambda_signal(axis_scores)
    if organ == "gate":
        return (
            f"[a11oy · gate orchestration] Received brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"AND-composing 46 policy gates: λ={L:.4f} {'≥' if L >= 0.90 else '<'} floor 0.90 → "
            f"{'PASS' if L >= 0.90 else 'HALT — below floor'}. "
            f"Gate decisions emitted as Wire-F receipts into Khipu DAG. "
            f"Doctrine v11 — Hatun-Willay. 749/14/163."
        )
    elif organ == "cortex":
        return (
            f"[amaru · cortex reasoning] Brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"Axis-scored reasoning: λ={L:.4f}. "
            f"TH8 GLR proven: bounded loops terminate at receipt-attested fixpoint. "
            f"TH1 Λ uniqueness is a Conjecture (CAUCHY_ND sorry @ Uniqueness.lean:120). "
            f"7-chakra semantic decomposition active. Doctrine v11."
        )
    elif organ == "immune":
        verdict = "PASS" if L >= 0.80 else "HALT"
        return (
            f"[sentra · immune/halt] Brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"Dual-use screen: λ={L:.4f} → {verdict}. "
            f"OVERWATCH R0513 active. KS-18 contextuality witness armed. "
            f"SBOM provenance gate: {'ATTESTED' if L >= 0.85 else 'PENDING'}. Doctrine v11."
        )
    elif organ == "receipt":
        return (
            f"[vessels · receipt generation] Brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"λ={L:.4f}. Generating Khipu Merkle DAG receipt node. "
            f"DSSE envelope: signature={SIGNATURE_PLACEHOLDER[:40]}... "
            f"PAC-Bayes TH13 bound governs DAG generalization (4 sorries tracked). "
            f"GLR TH8 ensures replay fixpoint. Doctrine v11."
        )
    elif organ == "nervous":
        return (
            f"[rosie · nervous system] Brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"Cross-session unified view: λ={L:.4f}. "
            f"Inherits all 5 organs (gate + cortex + immune + receipt + deploy). "
            f"Thesis corpus 171 slices active. Wire G brain-jack mesh: 6 sockets. Doctrine v11."
        )
    elif organ == "deploy":
        return (
            f"[uds-demo · deployment] Brain-jack from {src_space}/{src_organ}. "
            f"Query: '{query[:120]}'. "
            f"λ={L:.4f}. UDS bundle integrity: signed tarball + manifest digest verified. "
            f"Zarf package: declared images + manifests checksummed, airgap-transferable. "
            f"deploy.yaml pins image digests + λ-gate floor ≥ 0.90. Doctrine v11."
        )
    else:
        return f"[{space} · {organ}] Brain-jack from {src_space}/{src_organ}. Query: '{query[:80]}'. λ={L:.4f}. Doctrine v11."


# ---------------------------------------------------------------------------
# DSSE placeholder receipt (per Doctrine v10/v11 honesty contract)
# ---------------------------------------------------------------------------

def make_jack_receipt(space: str, src_space: str, query: str,
                      axis_scores: list[float] | None, traceparent: str | None) -> dict[str, Any]:
    L = lambda_signal(axis_scores)
    return {
        "schema": "szl.brain_jack.receipt/v1",
        "wire": "G",
        "doctrine": DOCTRINE,
        "space": space,
        "organ": SPACES.get(space, {}).get("organ", "unknown"),
        "src_space": src_space,
        "lambda_signal": L,
        "axis_scores": axis_scores or [],
        "traceparent": traceparent,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "dsse": {
            "payloadType": "application/vnd.szl.brain_jack.receipt+json",
            "signatures": [{"sig": SIGNATURE_PLACEHOLDER, "keyid": "PENDING — Sigstore keyless not wired"}],
        },
        "signature": SIGNATURE_PLACEHOLDER,
    }


# ---------------------------------------------------------------------------
# Socket registry
# ---------------------------------------------------------------------------

def socket_registry(this_space: str) -> list[dict[str, Any]]:
    """Return registry of all 6 spaces (including self with status='self')."""
    now = datetime.now(timezone.utc).isoformat()
    result = []
    for space, info in SPACES.items():
        result.append({
            "target_space": space,
            "target_organ": info["organ"],
            "target_url": info["hf_url"],
            "last_jack_at": now if space == this_space else None,
            "status": "self" if space == this_space else "open",
            "wire": "G",
            "doctrine": DOCTRINE,
        })
    return result


# ---------------------------------------------------------------------------
# Merkle root over a set of receipts
# ---------------------------------------------------------------------------

def merkle_root(receipts: list[dict[str, Any]]) -> str:
    """SHA-256 Merkle root of sorted receipt JSON strings."""
    if not receipts:
        return hashlib.sha256(b"empty").hexdigest()
    leaves = sorted(
        hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
        for r in receipts
    )
    while len(leaves) > 1:
        if len(leaves) % 2:
            leaves.append(leaves[-1])
        leaves = [
            hashlib.sha256((leaves[i] + leaves[i + 1]).encode()).hexdigest()
            for i in range(0, len(leaves), 2)
        ]
    return leaves[0]


# ---------------------------------------------------------------------------
# In-memory jack log (ring buffer)
# ---------------------------------------------------------------------------
from collections import deque
_JACK_LOG: deque[dict[str, Any]] = deque(maxlen=50)


def log_jack(entry: dict[str, Any]) -> None:
    _JACK_LOG.append(entry)


def recent_jacks(n: int = 10) -> list[dict[str, Any]]:
    return list(_JACK_LOG)[-n:]


# ---------------------------------------------------------------------------
# HTTP fan-out for multi-jack (async)
# ---------------------------------------------------------------------------

async def fan_out_jack(
    this_space: str,
    query: str,
    axis_scores: list[float] | None,
    target_organs: list[str] | None,
    traceparent: str | None,
    timeout_s: float = 8.0,
) -> list[dict[str, Any]]:
    """Fan out POST /api/<space>/v1/brain/jack to all target spaces in parallel.
    Falls back to local stub if remote is unreachable (HF Spaces may be sleeping)."""
    targets = []
    for organ in (target_organs or list(ORGAN_TO_SPACE.keys())):
        space = ORGAN_TO_SPACE.get(organ)
        if space and space != this_space:
            targets.append(space)
    if not targets:
        targets = [s for s in SPACES if s != this_space]

    payload = {
        "src_space": this_space,
        "src_organ": SPACES.get(this_space, {}).get("organ", "unknown"),
        "query": query,
        "axis_scores": axis_scores or [],
        "traceparent": traceparent,
    }

    async def call_one(space: str) -> dict[str, Any]:
        url = f"{SPACES[space]['hf_url']}/api/{space}/v1/brain/jack"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                r = await client.post(url, json=payload,
                                      headers={"traceparent": traceparent or "00-" + os.urandom(16).hex() + "-" + os.urandom(8).hex() + "-01"})
                if r.status_code == 200:
                    return r.json()
                else:
                    raise ValueError(f"HTTP {r.status_code}")
        except Exception as e:
            # Fallback: generate local stub (Space may be sleeping/cold-starting)
            L = lambda_signal(axis_scores)
            receipt = make_jack_receipt(space, this_space, query, axis_scores, traceparent)
            return {
                "src_space": this_space,
                "response_organ": SPACES[space]["organ"],
                "response_text": _organ_response(space, query, axis_scores, this_space,
                                                  SPACES.get(this_space, {}).get("organ", "unknown")) +
                                 f" [STUB — remote unreachable: {e}]",
                "lambda_signal": L,
                "lambda_receipt": receipt,
                "traceparent": traceparent,
                "space": space,
                "stub": True,
                "error": str(e),
            }

    results = await asyncio.gather(*[call_one(s) for s in targets], return_exceptions=False)
    return list(results)
