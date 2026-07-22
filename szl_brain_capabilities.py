# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings
# Signed-off-by: Codex <codex@openai.com>
"""Honest brain-capabilities manifest for the holographic brain surface.

This module is intentionally a capability ledger, not a model runtime. It exposes
what is currently evidenced, what is modeled, what is simulated, and what is
unavailable so UI surfaces cannot silently promote a stub into a live claim.
"""

import datetime as _dt
from typing import Any


ALLOWED_STATUSES = (
    "OPERATIONAL",
    "PARTIALLY OPERATIONAL",
    "MODELED",
    "SIMULATED",
    "EXPERIMENTAL",
    "UNAVAILABLE",
)


_RETRIEVAL_PILOT = {
    "status": "MEASURED_LOCAL_PILOT",
    "protocol_id": "brain-canonical-retrieval-pilot-v1",
    "artifacts": [
        "research/brain-evidence-admission/preregistration.json",
        "research/brain-evidence-admission/qrels.json",
        "research/brain-evidence-admission/canonical-index.json",
        "research/brain-evidence-admission/evaluation-results.json",
        "research/brain-evidence-admission/evidence-manifest.json",
    ],
    "claims_boundary": {
        "external_validity": "NOT_ESTABLISHED",
        "proof_credit": 0,
        "model_trust_delta": 0,
        "model_promotion_allowed": False,
        "training_triggered": False,
    },
    "limits": [
        "five unique canonical documents and fifteen manually judged queries",
        "lexical BM25 only; no learned reranker or independent external corpus",
        "canonical source timestamp coverage is zero",
        "9,464 raw graph nodes were observed and excluded from the index",
    ],
}


_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "holographic_brain_surface",
        "title": "3D holographic brain surface",
        "status": "PARTIALLY OPERATIONAL",
        "route": "/static/3d/brain.html",
        "evidence": [
            "static/3d/brain.html reads /api/a11oy/v1/holographic/brain/evidence",
            "szl3d_holographic.py serves the bounded evidence route",
            "WebGPU/WebGL is display-only and degrades to unavailable rather than fabricating data",
        ],
        "blockers": [
            "visual sculpting is local display state",
            "not a training runtime or autonomous brain",
        ],
        "next_step": "Bind each lobe to this capabilities manifest so display labels stay provenance-backed.",
    },
    {
        "id": "estate_brain_graph",
        "title": "Estate brain graph",
        "status": "PARTIALLY OPERATIONAL",
        "route": "/api/a11oy/v1/brain/graph",
        "evidence": [
            "a11oy_brain_graph builds deterministic nodes and links from committed estate metadata",
            "serve.py registers the route before catch-all handlers",
        ],
        "blockers": [
            "source inventory is snapshot/harvest based",
            "not a continuously learned external knowledge base",
        ],
        "next_step": "Add durable ingestion receipts for GitHub, Hugging Face, and site deployment events.",
    },
    {
        "id": "brain_retrieval",
        "title": "Graph retrieval and query grounding",
        "status": "PARTIALLY OPERATIONAL",
        "route": "/api/a11oy/v1/brain/search",
        "evidence": [
            "szl_brain_api exposes search, neighbors, community, subgraph, salience, stats, and ask routes",
            "retrieval returns grounding graph evidence even when generated prose is unavailable",
            "szl_brain_evidence_eval.py deterministically replays the committed canonical retrieval pilot",
            "research/brain-evidence-admission/evidence-manifest.json binds pilot artifacts and honesty boundaries",
        ],
        "blockers": [
            "hash embeddings and graph similarity are modeled",
            "no external vector database is evidenced",
            "the measured pilot is small, local, lexical-only, and has no established external validity",
        ],
        "evaluation": _RETRIEVAL_PILOT,
        "next_step": "Run the locked lexical/vector/graph/hybrid benchmark on an independent admitted corpus; do not generalize the local pilot.",
    },
    {
        "id": "brain_memory",
        "title": "Brain memory freshness",
        "status": "PARTIALLY OPERATIONAL",
        "route": "/api/a11oy/v1/brain/memory",
        "evidence": [
            "szl_brainmemory ranks freshness over the same graph",
            "it degrades to STRUCTURAL-ONLY when no real recency timestamp exists",
        ],
        "blockers": [
            "memory is not yet a durable event store",
            "many nodes have structural rather than measured recency",
        ],
        "next_step": "Back memory with append-only event receipts and source-specific retention policy.",
    },
    {
        "id": "provenance_lineage",
        "title": "Provenance and lineage lenses",
        "status": "PARTIALLY OPERATIONAL",
        "route": "/api/a11oy/v1/brain/lineage",
        "evidence": [
            "brain provenance and lineage routes read origin fields verbatim",
            "absent origin is labeled unknown/unavailable rather than filled in",
        ],
        "blockers": [
            "does not yet provide full build/model SLSA attestation",
            "source chains are only as complete as harvested fields",
        ],
        "next_step": "Attach model, dataset, Space, and GitHub commit attestations to every surfaced node.",
    },
    {
        "id": "query_audit_receipts",
        "title": "Query audit and receipts",
        "status": "SIMULATED",
        "route": "/api/a11oy/v1/brain/audit",
        "evidence": [
            "query audit exists as an in-process hash-linked log",
            "receipt endpoints emit unsigned SHA-256 content digests",
        ],
        "blockers": [
            "audit state is restart-ephemeral",
            "digests are not independent signatures",
        ],
        "next_step": "Move audit entries to durable storage and sign receipts with an approved key path.",
    },
    {
        "id": "llm_router",
        "title": "LLM/router answer generation",
        "status": "SIMULATED",
        "route": "/api/a11oy/v1/brain",
        "evidence": [
            "szl_brain.py emits an honest stub when no model key/backend is available",
            "routing receipts are deterministic but not proof of live inference",
        ],
        "blockers": [
            "no verified live model invocation is evidenced by this manifest",
            "no loaded-weight manifest is bound to the route",
        ],
        "next_step": "Add a model-availability endpoint with weight SHA, license, backend, and smoke-test receipt.",
    },
    {
        "id": "training_and_weights",
        "title": "Training runs and weighted models",
        "status": "UNAVAILABLE",
        "route": None,
        "evidence": [
            "no verified training run, eval artifact, or loaded-weight manifest is in this contract",
        ],
        "blockers": [
            "cannot claim fully trained or fully weighted models without reproducible receipts",
        ],
        "next_step": "Publish a training/eval ledger before promoting any model to OPERATIONAL.",
    },
)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def build_manifest(
    ns: str = "a11oy",
    runtime_status: dict[str, bool] | None = None,
) -> dict[str, Any]:
    capabilities = [
        dict(item, blockers=list(item.get("blockers", [])))
        for item in _CAPABILITIES
    ]
    observed_runtime = dict(runtime_status or {})
    for item in capabilities:
        capability_id = item["id"]
        if capability_id not in observed_runtime:
            continue
        registered = observed_runtime[capability_id]
        item["runtime_registration"] = (
            "REGISTERED" if registered else "FAILED_OR_ABSENT"
        )
        if not registered:
            item["status"] = "UNAVAILABLE"
            item["blockers"].append(
                "required route registration failed or is absent from the assembled app"
            )

    counts = {status: 0 for status in ALLOWED_STATUSES}
    for item in capabilities:
        status = item["status"]
        if status not in counts:
            raise ValueError(f"unknown capability status: {status}")
        counts[status] += 1

    route_failure = any(registered is False for registered in observed_runtime.values())
    contract = {
        "schema": "szl.brain-capabilities.v1",
        "namespace": ns,
        "generated_at": _now_iso(),
        "overall_status": "UNAVAILABLE" if route_failure else "PARTIALLY OPERATIONAL",
        "allowed_statuses": list(ALLOWED_STATUSES),
        "claim_policy": {
            "no_sentience_claim": True,
            "no_agi_or_asi_claim": True,
            "no_training_claim_without_receipt": True,
            "no_operational_claim_without_live_or_replayable_evidence": True,
        },
        "summary": {
            "capabilities_total": len(capabilities),
            "status_counts": counts,
            "ready_for_showcase": not route_failure,
            "ready_for_autonomous_claims": False,
            "ready_for_training_claims": False,
        },
        "capabilities": capabilities,
        "next_vertical_slice": [
            "GitHub event ingestion with source commit and actor provenance",
            "durable memory write with replayable receipt",
            "authorized retrieval over graph and memory",
            "improvement proposal with sandbox evaluation result",
            "human-governed pull request",
            "verified deployment and outcome memory",
            "signed receipt and independent replay",
        ],
        "brain_contract_artifacts": [
            "execution/brain/MEMORY_SCHEMA.json",
            "execution/brain/MEMORY_SCOPE_POLICY.md",
            "execution/brain/KNOWLEDGE_GRAPH_SCHEMA.md",
            "execution/brain/RETRIEVAL_ARCHITECTURE.md",
            "execution/brain/MEMORY_ADMISSION_POLICY.md",
            "execution/brain/CONTRADICTION_ENGINE.md",
            "execution/brain/FORGETTING_SPECIFICATION.md",
            "execution/brain/MEMORY_SECURITY_THREAT_MODEL.md",
            "execution/brain/CONTINUOUS_LEARNING_PROTOCOL.md",
            "execution/brain/ECOSYSTEM_PROPAGATION.md",
            "execution/brain/QUANTUM_EVIDENCE_PLANE.md",
            "execution/brain/research/TRANSACTIONAL_ENERGY_PAPER_SYNTHESIS.md",
            "execution/brain/research/QUANTUM_FRONTIER_LEADERS.csv",
            "research/brain-evidence-admission/preregistration.json",
            "research/brain-evidence-admission/qrels.json",
            "research/brain-evidence-admission/canonical-index.json",
            "research/brain-evidence-admission/evaluation-results.json",
            "research/brain-evidence-admission/evidence-manifest.json",
        ],
    }
    return contract


def build_info(ns: str = "a11oy") -> dict[str, Any]:
    return {
        "schema": "szl.brain-capabilities-info.v1",
        "namespace": ns,
        "route": f"/api/{ns}/v1/brain/capabilities",
        "purpose": "Expose an honest capability ledger for the holographic brain surface.",
        "allowed_statuses": list(ALLOWED_STATUSES),
        "pure_read": True,
        "mints_receipts": False,
    }


def register(
    app,
    ns: str = "a11oy",
    runtime_status: dict[str, bool] | None = None,
) -> str:
    from fastapi import Response
    from fastapi.responses import JSONResponse

    base = f"/api/{ns}/v1/brain/capabilities"
    runtime_snapshot = dict(runtime_status or {})

    @app.api_route(f"{base}/info", methods=["GET", "HEAD"])
    def _brain_capabilities_info():
        return JSONResponse(build_info(ns))

    @app.api_route(base, methods=["GET", "HEAD"])
    def _brain_capabilities():
        return JSONResponse(build_manifest(ns, runtime_snapshot))

    # FastAPI does not synthesize HEAD for GET routes. These explicit, bodyless
    # operational contracts let load balancers and independent verifiers probe
    # the existing read-only surfaces without invoking mutation or duplicating
    # their GET implementations.
    @app.head("/api/livez", include_in_schema=False)
    def _livez_head():
        return Response(status_code=200, headers={"Cache-Control": "no-store"})

    @app.head("/api/build-info", include_in_schema=False)
    def _build_info_head():
        return Response(status_code=200, headers={"Cache-Control": "no-store"})

    @app.head(f"/api/{ns}/v1/readiness/tab-matrix", include_in_schema=False)
    def _readiness_head():
        return Response(status_code=200, headers={"Cache-Control": "no-store"})

    return "brain-capabilities-wired:4"
