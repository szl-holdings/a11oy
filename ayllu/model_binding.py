# SPDX-License-Identifier: Apache-2.0
"""Honest runtime binding between the Ayllu council and SZL-Forge.

Ayllu personas are task roles sharing A11oy's routed model backend.  They are
not eleven separately trained models.  This module binds each role to a
declared SZL-Forge profile and a bounded set of *proposal* capabilities while
leaving execution, approval, signing, and verification in independent runtime
organs.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping


SCHEMA = "szl.ayllu.model-family-binding/v1"
FAMILY_ID = "SZL-Forge-1.5B"
COMPUTE_PLANE = "SZL-Yupaq"
BINDING_STATE = "ROUTER_INTEGRATED_FORGE_PROFILE_NOT_PINNED"

_ALL_COMPUTE_OPERATIONS = (
    "formula.org_lambda.weighted_geomean",
    "quant.sample.pipeline",
    "quantum.qubo.exact_baseline",
    "numerics.external.run",
    "numerics.external.compare",
    "proof.lean.inventory",
    "formula.admission.inventory",
    "brain.corpus.inventory",
    "lake.evidence.inventory",
)

_PROFILE_STATES = {
    "ReceiptAgent-v1": "TRAINING_PATH_READY_GPU_BLOCKED",
    "BrainNavigator-v1": "PLANNED_DATASET_ADMISSION_REQUIRED",
    "Operator-v1": "PLANNED_TOOL_CONTRACT_REQUIRED",
    "Sentinel-v1": "PLANNED_SECURITY_ADMISSION_REQUIRED",
    "Anatomy-v1": "PLANNED_ONTOLOGY_ADMISSION_REQUIRED",
}

_PERSONA_BINDINGS: dict[str, dict[str, Any]] = {
    "Amaru": {
        "primary_profile": "Operator-v1",
        "supporting_profiles": ["Anatomy-v1"],
        "proposal_surfaces": ["architecture.review", "anatomy.inspect"],
        "compute_operations": [],
    },
    "Ruwaq": {
        "primary_profile": "Operator-v1",
        "supporting_profiles": [],
        "proposal_surfaces": ["code.plan", "build.review", "compute.submit"],
        "compute_operations": [
            "proof.lean.inventory",
            "formula.admission.inventory",
            "brain.corpus.inventory",
            "lake.evidence.inventory",
        ],
    },
    "Yupaq": {
        "primary_profile": "ReceiptAgent-v1",
        "supporting_profiles": ["BrainNavigator-v1"],
        "proposal_surfaces": ["compute.submit", "receipt.verify", "proof.review"],
        "compute_operations": list(_ALL_COMPUTE_OPERATIONS),
    },
    "Qhaway": {
        "primary_profile": "Sentinel-v1",
        "supporting_profiles": ["Anatomy-v1"],
        "proposal_surfaces": ["simulation.review", "failure.evaluate"],
        "compute_operations": ["quantum.qubo.exact_baseline"],
    },
    "Maskaq": {
        "primary_profile": "BrainNavigator-v1",
        "supporting_profiles": ["ReceiptAgent-v1"],
        "proposal_surfaces": ["brain.query", "evidence.retrieve", "citation.review"],
        "compute_operations": [
            "brain.corpus.inventory",
            "formula.admission.inventory",
            "lake.evidence.inventory",
        ],
    },
    "Hampiq": {
        "primary_profile": "Anatomy-v1",
        "supporting_profiles": ["Sentinel-v1"],
        "proposal_surfaces": ["health.inspect", "remediation.propose"],
        "compute_operations": ["lake.evidence.inventory"],
    },
    "Yanapaq": {
        "primary_profile": "Operator-v1",
        "supporting_profiles": [],
        "proposal_surfaces": ["ops.review", "incident.support"],
        "compute_operations": [],
    },
    "Chaka": {
        "primary_profile": "Operator-v1",
        "supporting_profiles": ["ReceiptAgent-v1"],
        "proposal_surfaces": ["connector.review", "contract.crosswalk"],
        "compute_operations": [],
    },
    "Kamachiq": {
        "primary_profile": "Operator-v1",
        "supporting_profiles": ["ReceiptAgent-v1"],
        "proposal_surfaces": ["route.review", "plan.sequence", "approval.request"],
        "compute_operations": [],
    },
    "Qhatuq": {
        "primary_profile": "ReceiptAgent-v1",
        "supporting_profiles": [],
        "proposal_surfaces": ["risk.review", "quant.compute"],
        "compute_operations": [
            "quant.sample.pipeline",
            "formula.org_lambda.weighted_geomean",
        ],
    },
    "Willakuq": {
        "primary_profile": "ReceiptAgent-v1",
        "supporting_profiles": [],
        "proposal_surfaces": ["receipt.verify", "provenance.review", "archive.propose"],
        "compute_operations": ["lake.evidence.inventory"],
    },
}

_HARD_BOUNDARIES = {
    "personas_are_separate_weights": False,
    "tool_dispatch_active": False,
    "can_execute_external_actions": False,
    "can_approve_own_proposal": False,
    "can_sign_own_evidence": False,
    "can_self_certify_correctness": False,
    "model_output_is_verified_truth": False,
    "automatic_lounge_publish": False,
    "compute_execution_location": "SZL-Yupaq external governed computation plane",
    "binding_rule": "MODEL_PROPOSES; YUPAQ_VALIDATES_SCHEMA; ENGINE_COMPUTES; HONESTY_LABELS; RECEIPT_BINDS",
}


def persona_binding(
    name: str,
    *,
    actual_model: Any = None,
    backend_mode: str | None = None,
) -> dict[str, Any]:
    """Return one role's immutable model/control-plane binding."""
    canonical = next((key for key in _PERSONA_BINDINGS if key.lower() == (name or "").lower()), None)
    if canonical is None:
        raise KeyError(f"unknown Ayllu persona: {name}")
    binding = copy.deepcopy(_PERSONA_BINDINGS[canonical])
    primary = binding["primary_profile"]
    binding.update({
        "schema": SCHEMA,
        "persona": canonical,
        "family_id": FAMILY_ID,
        "binding_state": BINDING_STATE,
        "profile_state": _PROFILE_STATES[primary],
        "actual_model": actual_model,
        "backend_mode": backend_mode or "NOT_OBSERVED",
        "actual_model_authority": "turn receipt and router evidence",
        "compute_plane": COMPUTE_PLANE,
        "authority": "PROPOSAL_ONLY",
        "hard_boundaries": copy.deepcopy(_HARD_BOUNDARIES),
    })
    return binding


def family_binding(
    *,
    namespace: str = "a11oy",
    backend_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the machine-readable Ayllu-to-Forge family contract."""
    status = dict(backend_status or {})
    return {
        "schema": SCHEMA,
        "family_id": FAMILY_ID,
        "binding_state": BINDING_STATE,
        "runtime_backend": status,
        "runtime_backend_is_profile_pinned": False,
        "profile_pin_requirement": (
            "A promoted adapter must be loaded by the local OpenAI-compatible endpoint "
            "and named by A11OY_LOCAL_GENERAL_MODEL; the turn receipt remains authoritative."
        ),
        "personas": [persona_binding(name) for name in _PERSONA_BINDINGS],
        "compute": {
            "plane_id": COMPUTE_PLANE,
            "capabilities_endpoint": f"/api/{namespace}/v1/compute/capabilities",
            "submit_endpoint": f"/api/{namespace}/v1/compute/jobs",
            "allowed_operations": list(_ALL_COMPUTE_OPERATIONS),
            "dispatch_state": "PROPOSAL_ONLY_NOT_ACTIVE_IN_AYLLU_LOOP",
            "stateful_routes_require_auth": True,
        },
        "hard_boundaries": copy.deepcopy(_HARD_BOUNDARIES),
    }


def prompt_contract(binding: Mapping[str, Any]) -> str:
    """Serialize the binding into a compact system-prompt control contract."""
    compact = {
        "schema": binding.get("schema"),
        "family_id": binding.get("family_id"),
        "persona": binding.get("persona"),
        "primary_profile": binding.get("primary_profile"),
        "profile_state": binding.get("profile_state"),
        "authority": binding.get("authority"),
        "proposal_surfaces": binding.get("proposal_surfaces"),
        "compute_operations": binding.get("compute_operations"),
        "binding_rule": (binding.get("hard_boundaries") or {}).get("binding_rule"),
    }
    return (
        "A11OY MODEL-BINDING CONTRACT (machine-readable; binding):\n"
        + json.dumps(compact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\nYou may propose only. Never claim that a proposal was executed, approved, "
          "signed, kernel-verified, or trained unless an independent receipt is present."
    )


__all__ = [
    "BINDING_STATE",
    "COMPUTE_PLANE",
    "FAMILY_ID",
    "SCHEMA",
    "family_binding",
    "persona_binding",
    "prompt_contract",
]
