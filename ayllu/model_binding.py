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
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "szl.ayllu.model-family-binding/v1"
SECOND_BRAIN_SCHEMA = "szl.khipu.compound-second-brain.v1"
FAMILY_ID = "SZL-Forge-1.5B"
COMPUTE_PLANE = "SZL-Yupaq"
BINDING_STATE = "PROFILE_AWARE_LOCAL_ROUTING_ARTIFACT_BINDING_PARTIAL"
CANONICAL_RAW_BRAIN_NODES_SOURCE = (
    "model_release/szl-khipu-second-brain.json"
    "#brain_training_policy.raw_nodes_observed"
)
_INVENTORY_ROOT = Path(__file__).resolve().parents[1]
_INVENTORY_PATHS = {
    "source_admission_manifest": "research/formula-training-admission/admission-manifest.json",
    "m1_brain_ingest_ledger": "model_release/m1/brain-ingest-ledger.jsonl",
    "m1_corpus_manifest": "model_release/m1/corpus-ingestion-manifest.json",
}


def _bounded_inventory_read(relative: str, limit: int) -> bytes:
    path = _INVENTORY_ROOT / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("inventory file unavailable")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("inventory byte limit exceeded")
    return raw


def current_brain_inventory() -> dict[str, Any]:
    """Observe the fixed local release inventory without granting authority.

    Mutable runtime index counts and retained historical pilot counts cannot
    replace this binding. Reads are bounded and perform no network or writes.
    """
    try:
        policy_bytes = _bounded_inventory_read(
            "model_release/szl-khipu-second-brain.json", 256 * 1024,
        )
        document = json.loads(policy_bytes)
        if document["schema_version"] != SECOND_BRAIN_SCHEMA:
            raise ValueError("inventory policy schema mismatch")
        policy = document["brain_training_policy"]
        evidence = policy["current_inventory_evidence"]
        if set(evidence) != set(_INVENTORY_PATHS):
            raise ValueError("inventory evidence set mismatch")
        data = {}
        for name, relative in _INVENTORY_PATHS.items():
            item = evidence[name]
            if item["path"] != relative:
                raise ValueError("inventory evidence path mismatch")
            raw = _bounded_inventory_read(
                relative, 32 * 1024 * 1024 if name == "m1_brain_ingest_ledger" else 1024 * 1024,
            )
            if hashlib.sha256(raw).hexdigest() != item["file_sha256"]:
                raise ValueError("inventory evidence digest mismatch")
            data[name] = raw
        ledger = data["m1_brain_ingest_ledger"]
        observed_rows = 0
        for line in ledger.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (row["training_eligible"] is not False
                    or row["training_decision"] != "QUARANTINE"):
                raise ValueError("inventory ledger quarantine mismatch")
            observed_rows += 1
        manifest = json.loads(data["m1_corpus_manifest"])
        entry = manifest["ledgers"]["brain_nodes"]
        counts = (policy["raw_nodes_observed"],
                  evidence["m1_brain_ingest_ledger"]["rows"], entry["rows"])
        if any(type(count) is not int or count != observed_rows for count in counts):
            raise ValueError("inventory row count mismatch")
        if (entry["path"] != "brain-ingest-ledger.jsonl"
                or entry["sha256"] != evidence["m1_brain_ingest_ledger"]["file_sha256"]
                or type(entry["bytes"]) is not int or entry["bytes"] != len(ledger)):
            raise ValueError("inventory manifest binding mismatch")
        admission = json.loads(data["source_admission_manifest"])
        admission_receipt = admission.pop("manifest_receipt_sha256")
        if _canonical_sha256(admission) != admission_receipt:
            raise ValueError("inventory admission receipt mismatch")
        alignment = admission["source_snapshot"]["m1_alignment"]
        if (alignment["aligned"] is not True
                or alignment["brain_ledger_path"] != _INVENTORY_PATHS["m1_brain_ingest_ledger"]
                or alignment["manifest_path"] != _INVENTORY_PATHS["m1_corpus_manifest"]
                or alignment["brain_ledger_sha256"] != entry["sha256"]
                or alignment["manifest_sha256"] != evidence["m1_corpus_manifest"]["file_sha256"]
                or type(alignment["brain_ledger_rows"]) is not int
                or alignment["brain_ledger_rows"] != observed_rows
                or type(alignment["current_raw_nodes"]) is not int
                or alignment["current_raw_nodes"] != observed_rows):
            raise ValueError("inventory admission source mismatch")
        coverage = manifest["coverage"]
        brain = admission["source_snapshot"]["brain"]
        decision = admission["decision_summary"]
        zero_counts = (
            policy["raw_nodes_admitted_to_gradients"],
            alignment["raw_training_eligible_rows"],
            coverage["training_eligible_nodes"],
            brain["training_text_rows_emitted"],
            decision["train_rows"], decision["raw_brain_rows_emitted"],
        )
        if any(type(count) is not int or count != 0 for count in zero_counts):
            raise ValueError("inventory zero admission boundary mismatch")
        quarantined_counts = (
            manifest["source_snapshot"]["raw_node_count"],
            coverage["node_decisions_total"], coverage["node_decisions_expected"],
            coverage["raw_nodes_training_quarantined"],
            coverage["quarantined_or_excluded_nodes"],
            brain["raw_node_count"], brain["quarantined_node_count"],
            decision["raw_brain_nodes_quarantined"],
        )
        if any(type(count) is not int or count != observed_rows for count in quarantined_counts):
            raise ValueError("inventory quarantine coverage mismatch")
        decisions = coverage["node_decisions"]
        if (set(decisions) != {"QUARANTINE"}
                or type(decisions["QUARANTINE"]) is not int
                or decisions["QUARANTINE"] != observed_rows
                or alignment["current_only_node_ids"] != []
                or alignment["m1_only_node_ids"] != []):
            raise ValueError("inventory quarantine alignment mismatch")
        if (manifest["release_state"] != "NOT_PROMOTED"
                or manifest["training_state"] != "NOT_RUN"
                or manifest["training_relation"] != "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER"
                or alignment["training_state"] != "NOT_RUN"
                or alignment["admission"] != "CURRENT_INVENTORY_ONLY_ALL_ROWS_QUARANTINED"
                or admission["status"] != "COMPLETE_FAIL_CLOSED_HOLDOUT_ONLY"
                or policy["current_state"] != (
                    "ROW_LEVEL_ADMISSION_ENGINE_IMPLEMENTED_CURRENT_RAW_ROWS_QUARANTINED")
                or any(admission["claims_boundary"][key] is not False for key in (
                    "training_triggered", "model_promoted", "raw_node_text_emitted"))):
            raise ValueError("inventory proposal state mismatch")
        return {
            "state": "OBSERVED", "raw_nodes_observed": observed_rows,
            "source": CANONICAL_RAW_BRAIN_NODES_SOURCE,
            "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
            "ledger_sha256": entry["sha256"],
            "scope": "LOCAL_RELEASE_INVENTORY_NOT_RUNTIME_INDEX_OR_TRAINING_ADMISSION",
            "execution_authority": False,
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return {
            "state": "UNAVAILABLE", "raw_nodes_observed": None,
            "source": CANONICAL_RAW_BRAIN_NODES_SOURCE,
            "reason": "CURRENT_INVENTORY_EVIDENCE_UNAVAILABLE",
            "scope": "LOCAL_RELEASE_INVENTORY_NOT_RUNTIME_INDEX_OR_TRAINING_ADMISSION",
            "execution_authority": False,
        }

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
    "ReceiptAgent-v1": "ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED",
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
    inventory = current_brain_inventory()
    runtime_indexed_handle_count = rag.get("brain_handle_count") or 0
    profile_runtime = (
        (backend.get("forge_profiles") or {}).get("profiles") or {}
    ).get("BrainNavigator-v1") or {}
    exact_tag_observed = profile_runtime.get("available") is True
    unavailable_states = {
        "MODEL_TAG_MISSING": "UNAVAILABLE_MODEL_TAG_MISSING",
        "MODEL_CATALOG_UNAUTHORIZED": "UNAVAILABLE_MODEL_CATALOG_UNAUTHORIZED",
        "MODEL_CATALOG_MALFORMED": "UNAVAILABLE_MODEL_CATALOG_MALFORMED",
        "MODEL_CATALOG_UNAVAILABLE": "UNAVAILABLE_MODEL_CATALOG_UNAVAILABLE",
        "LOCAL_ENDPOINT_UNAVAILABLE": "UNAVAILABLE_LOCAL_MODEL_ENDPOINT",
    }
    observed_state = profile_runtime.get("state")
    availability_state = (
        "EXACT_TAG_OBSERVED_ARTIFACT_UNBOUND" if exact_tag_observed
        else observed_state if isinstance(observed_state, str)
        and observed_state in unavailable_states else "MODEL_CATALOG_UNAVAILABLE"
    )
    index_ready = bool(rag.get("built"))
    ready = exact_tag_observed and index_ready
    if ready:
        state = "READY_FOR_GROUNDED_NAVIGATION_ARTIFACT_UNBOUND"
    elif not exact_tag_observed and not index_ready:
        state = "UNAVAILABLE_MODEL_AND_INDEX"
    elif not exact_tag_observed:
        state = unavailable_states[availability_state]
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
            "availability_state": availability_state,
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
            "brain_handle_count": runtime_indexed_handle_count,
            "brain_handle_count_source": "RUNTIME_RAG_STATUS",
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
                "Corpus chunks, the evidence-validated current release inventory, and "
                "the current runtime Brain handle plane are separate, independently "
                "counted planes. Handles preserve source and quarantine metadata and "
                "grant no gradient authority."
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
            "raw_brain_nodes_observed": inventory["raw_nodes_observed"],
            "raw_brain_nodes_observation_state": inventory["state"],
            "current_inventory_evidence": inventory,
            "raw_brain_nodes_observation_source": CANONICAL_RAW_BRAIN_NODES_SOURCE,
            "raw_brain_nodes_observed_is_runtime_index_count": False,
            "raw_brain_nodes_admitted_to_gradients": (
                0 if inventory["state"] == "OBSERVED" else None
            ),
            "training_admission_authorized": False,
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
                if inventory["state"] == "OBSERVED" else "CURRENT_INVENTORY_UNAVAILABLE"
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
    "CANONICAL_RAW_BRAIN_NODES_SOURCE",
    "COMPUTE_PLANE",
    "FAMILY_ID",
    "SCHEMA",
    "SECOND_BRAIN_SCHEMA",
    "family_binding",
    "persona_binding",
    "prompt_contract",
    "second_brain_binding",
    "current_brain_inventory",
]
