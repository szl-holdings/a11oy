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
SECOND_BRAIN_SCHEMA = "szl.khipu.compound-second-brain.v1"
FAMILY_ID = "SZL-Forge-1.5B"
COMPUTE_PLANE = "SZL-Yupaq"
BINDING_STATE = "PROFILE_AWARE_LOCAL_ROUTING_ARTIFACT_BINDING_PARTIAL"

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
    "ReceiptAgent-v1": "SIGNED_RECEIPTS_VALID_ARTIFACT_BINDING_CONFLICT",
    "BrainNavigator-v1": "SIGNED_RECEIPTS_VALID_ARTIFACT_BINDING_CONFLICT",
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
    model_attestation: Mapping[str, Any] | None = None,
    grounding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one role's immutable model/control-plane binding."""
    canonical = next((key for key in _PERSONA_BINDINGS if key.lower() == (name or "").lower()), None)
    if canonical is None:
        raise KeyError(f"unknown Ayllu persona: {name}")
    binding = copy.deepcopy(_PERSONA_BINDINGS[canonical])
    primary = binding["primary_profile"]
    attestation = copy.deepcopy(dict(model_attestation or {})) or None
    grounding_summary = None
    if grounding:
        grounding_summary = {
            "schema": grounding.get("schema"),
            "state": grounding.get("state"),
            "content_access": grounding.get("content_access"),
            "query_sha256": grounding.get("query_sha256"),
            "evidence_set_sha256": grounding.get("evidence_set_sha256"),
            "handles_sha256": grounding.get("handles_sha256"),
            "augmented_prompt_sha256": grounding.get("augmented_prompt_sha256"),
            "handle_evidence_set_equivalent": grounding.get(
                "handle_evidence_set_equivalent"),
            "citation_validation": copy.deepcopy(
                grounding.get("citation_validation")),
            "rejected_model_output_sha256": grounding.get(
                "rejected_model_output_sha256"),
            "grounded_count": grounding.get("grounded_count"),
        }
    attested_served_model = (
        attestation.get("served_model") if attestation is not None else None)
    model_identity_reconciled = (
        actual_model == attested_served_model
        if isinstance(attested_served_model, str) and attested_served_model
        else None
    )
    binding.update({
        "schema": SCHEMA,
        "persona": canonical,
        "family_id": FAMILY_ID,
        "binding_state": BINDING_STATE,
        "profile_state": _PROFILE_STATES[primary],
        "actual_model": actual_model,
        "backend_mode": backend_mode or "NOT_OBSERVED",
        "actual_model_authority": "turn receipt and router evidence",
        "attested_served_model": attested_served_model,
        "model_identity_reconciled": model_identity_reconciled,
        "model_attestation": attestation,
        "model_attestation_sha256": (
            _canonical_sha256(attestation) if attestation is not None else None
        ),
        "grounding": grounding_summary,
        "grounding_sha256": (
            _canonical_sha256(grounding_summary) if grounding_summary is not None else None
        ),
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
    profile_runtime = status.get("forge_profiles")
    return {
        "schema": SCHEMA,
        "family_id": FAMILY_ID,
        "binding_state": BINDING_STATE,
        "runtime_backend": status,
        "runtime_backend_is_profile_pinned": False,
        "runtime_profile_status": profile_runtime,
        "profile_pin_requirement": (
            "The exact profile tag must be observed, its immutable weight/blob digest must "
            "match a signed release manifest, and the turn receipt must bind that attestation."
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


def second_brain_binding(
    *,
    namespace: str = "a11oy",
    backend_status: Mapping[str, Any] | None = None,
    rag_status: Mapping[str, Any] | None = None,
    signer_ready: bool = False,
) -> dict[str, Any]:
    """Describe the Khipu Second Brain as an evidence-bound compound model.

    The generator tag, persistent retrieval index, controller, and receipt
    verifier are independent components.  Keeping that separation explicit
    prevents an index row count from being mislabeled as parameters or trained
    weights while still exposing one operational system contract.
    """
    backend = copy.deepcopy(dict(backend_status or {}))
    rag = copy.deepcopy(dict(rag_status or {}))
    profile_runtime = (
        (backend.get("forge_profiles") or {}).get("profiles") or {}
    ).get("BrainNavigator-v1") or {}
    exact_tag_observed = bool(profile_runtime.get("available"))
    index_ready = bool(rag.get("built"))
    ready = exact_tag_observed and index_ready
    if ready:
        state = "READY_FOR_GROUNDED_NAVIGATION_ARTIFACT_UNBOUND"
    elif not exact_tag_observed and not index_ready:
        state = "UNAVAILABLE_MODEL_AND_INDEX"
    elif not exact_tag_observed:
        state = "UNAVAILABLE_MODEL_TAG_MISSING"
    else:
        state = "UNAVAILABLE_INDEX_NOT_BUILT"
    return {
        "schema": SECOND_BRAIN_SCHEMA,
        "system_id": "SZL-Khipu-Second-Brain-v1",
        "system_type": "COMPOUND_MODEL_WITH_EXTERNAL_EVIDENCE_MEMORY",
        "state": state,
        "ready_for_grounded_navigation": ready,
        "live_grounded_turn_verified_this_request": False,
        "signer_ready_this_request": bool(signer_ready),
        "promotion_state": "BLOCKED_ARTIFACT_AND_EVAL_GATES",
        "profile": {
            "profile_id": "BrainNavigator-v1",
            "expected_model": profile_runtime.get("expected_model", "khipu:latest"),
            "served_model": profile_runtime.get("served_model"),
            "exact_tag_observed": exact_tag_observed,
            "artifact_binding": "UNBOUND",
            "turn_level_attestation_required": True,
        },
        "memory": {
            "kind": "PERSISTENT_SQLITE_HYBRID_RETRIEVAL_GRAPH",
            "built": index_ready,
            "document_count": rag.get("document_count", rag.get("files")),
            "chunk_count": rag.get("chunk_count", rag.get("chunks")),
            "corpus_chunk_count": rag.get(
                "corpus_chunk_count", rag.get("chunk_count", rag.get("chunks"))
            ),
            "brain_handle_count": rag.get("brain_handle_count", 0),
            "brain_handle_plane": rag.get("brain_handle_plane"),
            "training_authority_rows": rag.get("training_authority_rows", 0),
            "node_count": rag.get("node_count"),
            "edge_count": rag.get("edge_count"),
            "generation_id": rag.get("generation_id"),
            "generation_digest_sha256": rag.get("generation_digest_sha256"),
            "integrity_state": rag.get("integrity_state"),
            "rehydration_state": rag.get("rehydration_state"),
            "corpus": rag.get("corpus"),
            "index_mode": rag.get("mode"),
            "scope_boundary": (
                "Corpus chunks and the canonical 9,464-node Brain handle plane are "
                "separate, independently counted retrieval planes. Handles preserve "
                "source and quarantine metadata and grant no gradient authority."
            ),
            "evidence_access": "HANDLES_ONLY_TO_MODEL; CONTENT_STAYS_IN_CONTROLLER",
        },
        "grounding": {
            "ask_endpoint": f"/api/{namespace}/v1/ayllu/ask",
            "persona": "Maskaq",
            "query_endpoint": f"/api/{namespace}/code/rag/query",
            "required_receipt_fields": [
                "evidence_set_sha256",
                "handles_sha256",
                "augmented_prompt_sha256",
                "grounding_sha256",
                "model_attestation_sha256",
                "turn_output_sha256",
            ],
            "abstain_when_ungrounded": True,
        },
        "training_boundary": {
            "raw_brain_nodes_observed": 9464,
            "raw_brain_nodes_admitted_to_gradients": 0,
            "admission_is_row_level": True,
            "admission_engine": "szl_brain_training_admission.py",
            "admission_contract": "szl.brain-training-admission-report.v2",
            "evidence_security": (
                "ED25519_ROOT_SIGNED_PURPOSE_SCOPED_ISSUER_TOOL_KEY"
            ),
            "required_signed_inputs": [
                "protected_eval_content_sha256_list",
                "purpose_scoped_evidence_trust_store",
                "policy_root_signer",
                "root_signed_policy_bundle",
                "signed_prior_split_ledger_descriptor",
                "exact_split_ledger_head_sha256",
                "reviewer_allowlist",
                "artifact_signing_key",
                "explicit_train_admission_switch",
            ],
            "current_state": (
                "ROW_LEVEL_ADMISSION_ENGINE_IMPLEMENTED_CURRENT_RAW_ROWS_QUARANTINED"
            ),
            "required": [
                "stable_node_id",
                "content_sha256",
                "stable_source_identity",
                "immutable_source_revision",
                "author_and_rightsholder",
                "rights_basis_license_and_permission_scope",
                "privacy_classification_and_signed_pii_clearance",
                "source_timestamp_and_freshness",
                "canonical_state",
                "dedup_group",
                "contamination_result",
                "allowlisted_signed_review",
                "immutable_split",
                "cross_run_split_ledger_binding",
            ],
            "honesty": (
                "All graph nodes may participate in retrieval and evaluation; only "
                "independently admitted rows may enter gradients."
            ),
        },
        "hard_boundaries": {
            "index_is_model_weights": False,
            "retrieval_is_training": False,
            "model_can_read_raw_node_content": False,
            "model_can_write_canonical_memory": False,
            "model_can_self_certify_grounding": False,
        },
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


def _canonical_sha256(value: Any) -> str:
    return __import__("hashlib").sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


__all__ = [
    "BINDING_STATE",
    "COMPUTE_PLANE",
    "FAMILY_ID",
    "SCHEMA",
    "SECOND_BRAIN_SCHEMA",
    "family_binding",
    "persona_binding",
    "prompt_contract",
    "second_brain_binding",
]
