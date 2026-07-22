# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Codex <codex@openai.com>
"""Fail-closed quantum evidence rollup for the a11oy brain.

This module unifies existing in-process quantum-related evidence. It does not
execute a QPU, promote simulations into measurements, or claim quantum advantage.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable


SCHEMA = "szl.brain-quantum-evidence.v1"
CAPABILITY_KINDS = (
    "classical-computation",
    "simulation",
    "formal-witness",
    "instrument-fed-model",
    "hardware-measurement",
    "evidence-policy",
    "research-inspiration",
)
STATUSES = ("OPERATIONAL", "PARTIALLY OPERATIONAL", "MODELED", "UNAVAILABLE")


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _entry(
    source_id: str,
    capability_kind: str,
    status: str,
    summary: str,
    source: str,
    evidence: dict[str, Any],
    *,
    hardware_used: bool = False,
) -> dict[str, Any]:
    if capability_kind not in CAPABILITY_KINDS:
        raise ValueError(f"unsupported capability kind: {capability_kind}")
    if status not in STATUSES:
        raise ValueError(f"unsupported status: {status}")
    item = {
        "id": source_id,
        "capability_kind": capability_kind,
        "status": status,
        "summary": summary,
        "source": source,
        "hardware_used": hardware_used,
        "evidence": evidence,
    }
    item["source_digest"] = _digest(item)
    return item


def _safe_source(source_id: str, loader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return loader()
    except Exception as exc:  # pragma: no cover - exercised through injected failures
        return _entry(
            source_id,
            "evidence-policy",
            "UNAVAILABLE",
            "Backing source failed closed; no capability was promoted.",
            source_id,
            {"error_type": type(exc).__name__, "error": str(exc)[:180]},
        )


def _quantum_utility() -> dict[str, Any]:
    from szl_quantum_utility import info

    payload = info()
    return _entry(
        "quantum-utility-gate",
        "classical-computation",
        "OPERATIONAL" if payload.get("ready") else "UNAVAILABLE",
        "Bounded classical baselines, proposal plans, and a fail-closed advantage evidence gate.",
        "szl_quantum_utility.py:info",
        {
            "label": payload.get("label"),
            "mode": payload.get("mode"),
            "qpu_calls": payload.get("qpu_calls", 0),
            "provider_calls": payload.get("provider_calls"),
            "capabilities": payload.get("capabilities", {}),
        },
        hardware_used=bool(payload.get("qpu_calls")),
    )


def _vqc() -> dict[str, Any]:
    from szl_vqc import vqc_manifest

    payload = vqc_manifest("a11oy")
    return _entry(
        "governed-vqc",
        "simulation",
        "MODELED",
        "Deterministic state-vector VQC with parameter-shift gradients; not a trained hardware model.",
        "szl_vqc.py:vqc_manifest",
        {
            "label": payload.get("label"),
            "sim_kind": payload.get("sim_kind"),
            "caps": payload.get("caps"),
            "honesty_invariants": payload.get("honesty_invariants"),
        },
    )


def _qbio() -> dict[str, Any]:
    from szl_quant_qbio_holo import _qbio_status

    payload = _qbio_status()
    return _entry(
        "quantum-bio-models",
        "simulation",
        "PARTIALLY OPERATIONAL" if payload.get("backing") == "LIVE" else "UNAVAILABLE",
        "Reproducible deterministic model outputs; not biological or physical experimental validation.",
        "szl_quant_qbio_holo.py:_qbio_status",
        {
            "backing": payload.get("backing"),
            "models_total": payload.get("models_total"),
            "verified_models": payload.get("verified_models"),
            "proposed_models": payload.get("proposed_models"),
            "verification_scope": payload.get("verification_scope"),
            "verification_boundary": payload.get("verification_boundary"),
        },
    )


def _formal_witnesses() -> dict[str, Any]:
    from szl_quant_qbio_holo import _quant_status

    payload = _quant_status()
    return _entry(
        "quantum-formal-witnesses",
        "formal-witness",
        "PARTIALLY OPERATIONAL" if payload.get("formulas_backing") == "LIVE" else "UNAVAILABLE",
        "Formal and computational witnesses with conjectures and axioms kept separate from proven results.",
        "szl_quant_qbio_holo.py:_quant_status",
        {
            "formulas_backing": payload.get("formulas_backing"),
            "quant_formulas_examined": payload.get("quant_formulas_examined"),
            "proven_count": payload.get("proven_count"),
            "conjecture_or_axiom_count": payload.get("conjecture_or_axiom_count"),
            "pnt_mesh": payload.get("pnt_mesh"),
        },
    )


def _sensing_posture() -> dict[str, Any]:
    import quantum_sensing_limits as sensing

    return _entry(
        "quantum-sensing-certifier",
        "instrument-fed-model",
        "PARTIALLY OPERATIONAL",
        "Certifies supplied instrument records and models physical limits; it is not connected to live hardware.",
        "quantum_sensing_limits.py",
        {
            "module": sensing.__name__,
            "endpoint": "/api/a11oy/v1/pnt/limits",
            "input_boundary": "caller-supplied instrument fields",
            "live_instrument_connection": False,
            "derived_outputs_are_modeled": True,
        },
    )


def _claim_gate() -> dict[str, Any]:
    from szl_quant_claims import resolved_claims

    claims = resolved_claims()
    promoted = [row for row in claims if row.get("measurement_gate", {}).get("promoted")]
    return _entry(
        "claim-promotion-gate",
        "evidence-policy",
        "OPERATIONAL",
        "Claim registry presence never promotes a measurement; promotion requires a binding receipt.",
        "szl_quant_claims.py:resolved_claims",
        {
            "claims_total": len(claims),
            "promoted_measurements": len(promoted),
            "promotion_requires_receipt": True,
        },
    )


def _transactional_paper() -> dict[str, Any]:
    return _entry(
        "watts-mead-transactional-energy-paper",
        "research-inspiration",
        "MODELED",
        "Conceptual inspiration for two-sided proposal/acceptance receipts and overlap scoring only.",
        "https://doi.org/10.3390/e28070813",
        {
            "title": "A Wave-Particle Model of Energy Transfer Between Two Atoms in a Transactional Interpretation of Quantum Mechanics",
            "authors": ["Lloyd Watts", "Carver Mead"],
            "journal": "Entropy 2026, 28, 813",
            "license": "CC BY 4.0",
            "adopted_as_physics": False,
            "used_as_quantum_computing_evidence": False,
            "no_ftl_claim": True,
            "no_quantum_advantage_claim": True,
        },
    )


def build_manifest(ns: str = "a11oy") -> dict[str, Any]:
    loaders: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
        ("quantum-utility-gate", _quantum_utility),
        ("governed-vqc", _vqc),
        ("quantum-bio-models", _qbio),
        ("quantum-formal-witnesses", _formal_witnesses),
        ("quantum-sensing-certifier", _sensing_posture),
        ("claim-promotion-gate", _claim_gate),
        ("watts-mead-transactional-energy-paper", _transactional_paper),
    )
    sources = [_safe_source(source_id, loader) for source_id, loader in loaders]
    hardware = [row for row in sources if row["capability_kind"] == "hardware-measurement" and row["hardware_used"]]
    unavailable = [row["id"] for row in sources if row["status"] == "UNAVAILABLE"]
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "namespace": ns,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PARTIALLY OPERATIONAL",
        "allowed_capability_kinds": list(CAPABILITY_KINDS),
        "allowed_statuses": list(STATUSES),
        "sources": sources,
        "summary": {
            "sources_total": len(sources),
            "unavailable_sources": unavailable,
            "hardware_measurements": len(hardware),
            "qpu_execution_verified": False,
            "quantum_advantage_verified": False,
            "full_operational_brain": False,
        },
        "proposal_acceptance_protocol": {
            "status": "MODELED",
            "inspiration": "general two-sided transaction pattern; no physics equivalence claimed",
            "offer": ["task_digest", "classical_baseline", "budget", "backend_plan", "source_provenance"],
            "confirmation": ["authorized_acceptor", "measured_output", "uncertainty", "raw_artifact_digest", "receipt"],
            "commit_rule": "Commit only when offer and confirmation bind to the same task digest and every policy gate passes.",
            "conservation_invariant": "submitted + accepted + rejected + failed counts reconcile to the signed run ledger",
        },
        "next_frontier": [
            "backend-neutral sampler and estimator contract",
            "locked classical versus simulator versus QPU benchmark",
            "calibration, cost, energy, and uncertainty ledger",
            "independent replay before any quantum-advantage claim",
        ],
    }
    manifest["content_sha256"] = _digest(
        {key: value for key, value in manifest.items() if key not in {"generated_at", "content_sha256"}}
    )
    return manifest


def build_info(ns: str = "a11oy") -> dict[str, Any]:
    return {
        "schema": "szl.brain-quantum-evidence-info.v1",
        "route": f"/api/{ns}/v1/brain/quantum-evidence",
        "pure_read": True,
        "executes_qpu": False,
        "claims_quantum_advantage": False,
    }


def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/quantum-evidence"

    @app.get(f"{base}/info")
    def _quantum_evidence_info():
        return JSONResponse(build_info(ns))

    @app.get(base)
    def _quantum_evidence():
        return JSONResponse(build_manifest(ns))

    return "brain-quantum-evidence-wired:1"
