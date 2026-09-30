#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. and SZL Holdings
"""SZL Atelier Frontier Workbench.

Taxonomy home: services/ + provenance/ + governance/.

This module is an original clean-room capability synthesis of a bounded public
repository audit. It copies no third-party source, branding, visual assets,
prompts, example outputs, or mascots. The only repository marked
``ADAPT_WITH_NOTICE`` has a verified MIT license; the current implementation
still uses only its abstract capability pattern.

The workbench is GET/HEAD-only. It owns no credential, database, signer,
scheduler, model weights, or effector. Candidate scoring is MODELED from bounded
caller input, hard-zeroed by the safety gate, and capped at the A11oy trust
ceiling. It cannot authorize production work.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

SCHEMA_REGISTRY = "szl.atelier-frontier-registry/v1"
SCHEMA_EVALUATION = "szl.atelier-frontier-evaluation/v1"
FORMULA_VERSION = "atelier-frontier-weighted-geomean/v1"
TRUST_CEILING = 0.97
MAX_SCORE = 100
ALLOWED_ENERGY_STATES = {"REPORTED", "UNAVAILABLE"}
OBSERVED_AT = "2026-09-03"
MIT_NOTICE_SHA256 = "13539d7d18cf3e67acc73a857861591095641f54ef194274638d1f1dcf56b568"
NO_STORE_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
PAGE_HEADERS = {
    **NO_STORE_HEADERS,
    "content-security-policy": (
        "default-src 'none'; script-src 'self'; script-src-attr 'none'; "
        "style-src 'self'; style-src-attr 'none'; connect-src 'self'; "
        "img-src 'self' data:; font-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
    ),
    "permissions-policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
        "accelerometer=(), gyroscope=()"
    ),
}

REFERENCE_REPOSITORIES: tuple[dict[str, Any], ...] = ({'name': 'AI-agents',
  'source': 'https://github.com/meta-success/AI-agents',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'CLEAN_ROOM_ONLY',
  'lanes': ['orchestration',
            'language',
            'multimodal',
            'generation',
            'alignment',
            'training',
            'evaluation',
            'deployment'],
  'note': 'Multi-studio workbench and staged orchestration patterns only; no source, '
          'branding, mascot, prompts, or site assets copied.'},
 {'name': 'multimodal-vision-demo',
  'source': 'https://github.com/meta-success/multimodal-vision-demo',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'CLEAN_ROOM_ONLY',
  'lanes': ['multimodal', 'retrieval', 'identity'],
  'note': 'Independent evidence-envelope design only; no model glue or UI copied.'},
 {'name': 'football-analysis',
  'source': 'https://github.com/meta-success/football-analysis',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['sports_vision', 'evaluation'],
  'note': 'Frame-analysis capability reference; implementation requires independent '
          'design.'},
 {'name': 'AI-Image-PromptGenerator',
  'source': 'https://github.com/meta-success/AI-Image-PromptGenerator',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['generation', 'alignment'],
  'note': 'Prompt-governance reference only.'},
 {'name': 'n8n-automation',
  'source': 'https://github.com/meta-success/n8n-automation',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['automation'],
  'note': 'Workflow ideas only; connector terms and source require separate review.'},
 {'name': 'certification',
  'source': 'https://github.com/meta-success/certification',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['evaluation'],
  'note': 'Evaluation and certification workflow reference only.'},
 {'name': 'mujoco-drone-pong',
  'source': 'https://github.com/meta-success/mujoco-drone-pong',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['simulation'],
  'note': 'Simulation pattern only; no environment or assets copied.'},
 {'name': 'NLP-chatbot',
  'source': 'https://github.com/meta-success/NLP-chatbot',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'CLEAN_ROOM_ONLY',
  'lanes': ['language', 'orchestration'],
  'note': 'Independent conversational pipeline design only.'},
 {'name': 'ai-generate-with-langchain',
  'source': 'https://github.com/meta-success/ai-generate-with-langchain',
  'license_state': 'UPSTREAM_PROVENANCE_REQUIRED',
  'reuse_policy': 'UPSTREAM_REQUIRED',
  'lanes': ['orchestration', 'retrieval', 'generation'],
  'note': 'Documentation appears tied to external instructional material; original '
          'upstream license must be verified.'},
 {'name': 'meta-success',
  'source': 'https://github.com/meta-success/meta-success',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['portfolio'],
  'note': 'Organization profile and navigation reference only.'},
 {'name': 'Table-tennis-anlaysis',
  'source': 'https://github.com/meta-success/Table-tennis-anlaysis',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['sports_vision', 'evaluation'],
  'note': 'Frame-analysis capability reference only.'},
 {'name': 'VICE',
  'source': 'https://github.com/meta-success/VICE',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['multimodal', 'evaluation'],
  'note': 'Vision/evaluation pattern pending provenance review.'},
 {'name': 'AI-chatbot-MERN',
  'source': 'https://github.com/meta-success/AI-chatbot-MERN',
  'license_state': 'UPSTREAM_PROVENANCE_REQUIRED',
  'reuse_policy': 'UPSTREAM_REQUIRED',
  'lanes': ['language', 'deployment'],
  'note': 'Documentation points to an external upstream project; preserve upstream '
          'notices after verification.'},
 {'name': 'Multi-Agent-System',
  'source': 'https://github.com/meta-success/Multi-Agent-System',
  'license_state': 'EMPTY_OR_INSUFFICIENT',
  'reuse_policy': 'EMPTY_REFERENCE',
  'lanes': ['orchestration'],
  'note': 'No implementation was relied upon.'},
 {'name': 'bittensor-auto-register',
  'source': 'https://github.com/meta-success/bittensor-auto-register',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['automation', 'deployment'],
  'note': 'No wallet, credential, or registration automation copied.'},
 {'name': 'Make.com-automation',
  'source': 'https://github.com/meta-success/Make.com-automation',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['automation'],
  'note': 'Workflow ideas only.'},
 {'name': 'astro-project',
  'source': 'https://github.com/meta-success/astro-project',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['deployment'],
  'note': 'Frontend/deployment pattern only.'},
 {'name': 'mujoco-cloth-hooking',
  'source': 'https://github.com/meta-success/mujoco-cloth-hooking',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['simulation'],
  'note': 'Simulation pattern only; no environment or assets copied.'},
 {'name': 'RAG-pipeline-typescript',
  'source': 'https://github.com/meta-success/RAG-pipeline-typescript',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'CLEAN_ROOM_ONLY',
  'lanes': ['retrieval', 'deployment'],
  'note': 'Independent retrieval architecture only.'},
 {'name': 'face-ai-system',
  'source': 'https://github.com/meta-success/face-ai-system',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['identity', 'multimodal'],
  'note': 'Biometric processing remains denied until consent, retention, bias, and '
          'jurisdiction controls are bound.'},
 {'name': 'solana-sniper-trading-mev-bot',
  'source': 'https://github.com/meta-success/solana-sniper-trading-mev-bot',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['markets', 'automation'],
  'note': 'No trading, MEV, key, or execution code copied; effectors remain disabled.'},
 {'name': 'chrome-livecaption',
  'source': 'https://github.com/meta-success/chrome-livecaption',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['language', 'deployment'],
  'note': 'Speech/edge capability reference only.'},
 {'name': 'RAG-SYSTEM-NODE',
  'source': 'https://github.com/meta-success/RAG-SYSTEM-NODE',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['retrieval', 'deployment'],
  'note': 'Documented capability and inspected source shape were not treated as '
          'reusable implementation.'},
 {'name': 'launchstack-custom',
  'source': 'https://github.com/meta-success/launchstack-custom',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['deployment'],
  'note': 'Deployment/frontend reference only.'},
 {'name': 'GPU-Accelerated-ML-Pipeline',
  'source': 'https://github.com/meta-success/GPU-Accelerated-ML-Pipeline',
  'license_state': 'VERIFIED_MIT',
  'reuse_policy': 'ADAPT_WITH_NOTICE',
  'lanes': ['gpu_lab', 'training', 'evaluation', 'deployment'],
  'note': 'Only verified permissive candidate. Current workbench independently '
          'implements the pattern and copies no source.'},
 {'name': 'booking-system',
  'source': 'https://github.com/meta-success/booking-system',
  'license_state': 'LICENSE_NOT_VERIFIED',
  'reuse_policy': 'REFERENCE_ONLY',
  'lanes': ['automation', 'deployment'],
  'note': 'Workflow/frontend reference only.'})

CAPABILITY_DESIGNS: tuple[dict[str, Any], ...] = ({'id': 'orchestration',
  'label': 'Governed orchestration',
  'state': 'REPORTED',
  'bindings': ['/api/a11oy/v1/reason', '/api/a11oy/v1/gates'],
  'improvement': 'Safety and evidence gates precede model use; no fail-open '
                 'moderation.'},
 {'id': 'retrieval',
  'label': 'Evidence retrieval',
  'state': 'REPORTED',
  'bindings': ['/api/a11oy/v1/frontier-now/inventory'],
  'improvement': 'Citation-bearing source envelopes, bounded context, and explicit '
                 'stale or unavailable states.'},
 {'id': 'multimodal',
  'label': 'Multimodal evidence',
  'state': 'MODELED',
  'bindings': [],
  'improvement': 'OCR, captions, detections, and embeddings remain separate claims '
                 'until a governance gate authorizes fusion.'},
 {'id': 'gpu_lab',
  'label': 'GPU compute lab',
  'state': 'REPORTED',
  'bindings': ['/api/a11oy/v1/kernel-estate'],
  'improvement': 'Runtime capability is observed; energy is never labeled MEASURED by '
                 'this workbench.'},
 {'id': 'automation',
  'label': 'Workflow automation',
  'state': 'MODELED',
  'bindings': ['/api/a11oy/v1/series-a/status'],
  'improvement': 'Prospective writes require an explicit action passport, one bounded '
                 'attempt, and a write receipt.'},
 {'id': 'simulation',
  'label': 'Simulation and digital twins',
  'state': 'REPORTED',
  'bindings': ['/api/a11oy/v1/pnt/limits'],
  'improvement': 'Simulation output remains MODELED and cannot silently become sensor '
                 'evidence.'},
 {'id': 'sports_vision',
  'label': 'Sports and video analytics',
  'state': 'MODELED',
  'bindings': [],
  'improvement': 'Frame lineage, confidence calibration, and repeatable evaluation '
                 'replace highlight-only demonstrations.'},
 {'id': 'language',
  'label': 'Language and conversation',
  'state': 'REPORTED',
  'bindings': ['/api/a11oy/v1/reason'],
  'improvement': 'Responses carry status, citations, observation time, and bounded '
                 'confidence.'},
 {'id': 'generation',
  'label': 'Generative media',
  'state': 'ROADMAP',
  'bindings': [],
  'improvement': 'Prompt, model, seed, policy verdict, and output digest travel as one '
                 'evidence bundle.'},
 {'id': 'identity',
  'label': 'Identity and face analysis',
  'state': 'UNAVAILABLE',
  'bindings': [],
  'improvement': 'Denied until consent, retention, bias, and jurisdiction controls are '
                 'bound and verified.'},
 {'id': 'alignment',
  'label': 'Safety and alignment',
  'state': 'MODELED',
  'bindings': ['/api/a11oy/v1/gates'],
  'improvement': 'Safety failure is a hard zero gate rather than an advisory badge.'},
 {'id': 'training',
  'label': 'Training and fine-tuning',
  'state': 'MODELED',
  'bindings': ['/api/a11oy/v1/kernel-estate'],
  'improvement': 'Dataset lineage, deterministic configuration, benchmark evidence, '
                 'and export digest are required.'},
 {'id': 'deployment',
  'label': 'Deployment and edge',
  'state': 'REPORTED',
  'bindings': ['/api/build-info', '/api/a11oy/readyz'],
  'improvement': 'Exact source-to-runtime binding, immutable artifacts, and terminal '
                 'live verification.'},
 {'id': 'evaluation',
  'label': 'Evaluation and certification',
  'state': 'MODELED',
  'bindings': ['/api/a11oy/v1/frontier-now/summary'],
  'improvement': 'Weighted evidence score is capped at 0.97 and cannot override a '
                 'failed safety gate.'})

WEIGHTS: Mapping[str, float] = {
    "evidence": 0.30,
    "repeatability": 0.25,
    "coverage": 0.20,
    "governance": 0.25,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _asset_bytes(name: str) -> bytes:
    path = Path(__file__).resolve().parent / "atelier_frontier_web" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"asset missing: {name}")
    return path.read_bytes()


def _asset_digest(name: str) -> str:
    return hashlib.sha256(_asset_bytes(name)).hexdigest()


def _asset_cache_control(request: Request, content: bytes) -> str:
    if request.query_params.get("v") == hashlib.sha256(content).hexdigest():
        return "public,max-age=31536000,immutable"
    return "no-store"


def _canonical_digest(value: Any) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _single(request: Request, name: str, default: str) -> str:
    values = request.query_params.getlist(name)
    if len(values) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"{name} must be supplied at most once",
        )
    return values[0] if values else default


def _score(request: Request, name: str, default: int) -> int:
    raw = _single(request, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{name} must be an integer",
        ) from exc
    if value < 0 or value > MAX_SCORE:
        raise HTTPException(
            status_code=422,
            detail=f"{name} must be between 0 and {MAX_SCORE}",
        )
    return value


def _binary(request: Request, name: str, default: int) -> int:
    value = _score(request, name, default)
    if value not in {0, 1}:
        raise HTTPException(status_code=422, detail=f"{name} must be 0 or 1")
    return value


def _weighted_geometric_mean(values: Mapping[str, int]) -> float:
    normalized = {key: values[key] / 100.0 for key in WEIGHTS}
    if any(value <= 0.0 for value in normalized.values()):
        return 0.0
    return math.exp(
        sum(WEIGHTS[key] * math.log(normalized[key]) for key in WEIGHTS)
    )


def evaluate_candidate(
    *,
    evidence: int,
    repeatability: int,
    coverage: int,
    governance: int,
    safety: int,
    energy: int,
    energy_state: str,
) -> dict[str, Any]:
    scores = {
        "evidence": evidence,
        "repeatability": repeatability,
        "coverage": coverage,
        "governance": governance,
        "energy": energy,
    }
    for name, value in scores.items():
        if value < 0 or value > MAX_SCORE:
            raise ValueError(f"{name} must be between 0 and {MAX_SCORE}")
    if safety not in {0, 1}:
        raise ValueError("safety must be 0 or 1")
    state = energy_state.upper()
    if state not in ALLOWED_ENERGY_STATES:
        raise ValueError("energy_state is not allowed")

    quality_inputs = {key: scores[key] for key in WEIGHTS}
    quality = _weighted_geometric_mean(quality_inputs)
    energy_factor = 1.0 if state == "UNAVAILABLE" else 0.90 + (energy / 1000.0)
    uncapped = quality * energy_factor * float(safety)
    score = min(TRUST_CEILING, uncapped)

    if safety == 0:
        decision = "DENIED"
        reason = "SAFETY_GATE_FAILED"
    elif score >= 0.78:
        decision = "SANDBOX_CANDIDATE"
        reason = "MODELED_THRESHOLD_MET_NO_EFFECTOR_BOUND"
    elif score >= 0.60:
        decision = "REVIEW"
        reason = "MODELED_THRESHOLD_PARTIAL"
    else:
        decision = "HOLD"
        reason = "MODELED_THRESHOLD_NOT_MET"

    inputs = {
        **quality_inputs,
        "safety": safety,
        "energy": energy if state == "REPORTED" else None,
        "energy_state": state,
    }
    derivation = {
        "formula": FORMULA_VERSION,
        "weights": dict(WEIGHTS),
        "trust_ceiling": TRUST_CEILING,
        "inputs": inputs,
        "quality": round(quality, 8),
        "energy_factor": round(energy_factor, 8),
        "uncapped": round(uncapped, 8),
        "score": round(score, 8),
        "decision": decision,
    }
    return {
        "schema": SCHEMA_EVALUATION,
        "generated_at": _now(),
        "evidence_class": "MODELED",
        "formula": derivation,
        "decision": {
            "state": decision,
            "reason": reason,
            "external_writes": "DISABLED",
            "effectors": [],
            "automatic_retries": 0,
        },
        "derivation_fingerprint": {
            "kind": "DETERMINISTIC_RESPONSE_FINGERPRINT",
            "sha256": _canonical_digest(derivation),
            "signature_status": "UNAVAILABLE",
            "persisted": False,
        },
        "energy": {
            "state": state,
            "score_used": energy if state == "REPORTED" else None,
            "input_provenance": "CALLER_SUPPLIED",
            "joules_claimed": False,
            "measured_claim_permitted": False,
        },
        "private_reasoning_collected": False,
        "claim": "CANDIDATE_SCORE_NOT_PRODUCTION_AUTHORIZATION",
    }


def _capability_lanes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for design in CAPABILITY_DESIGNS:
        lane_id = str(design["id"])
        references = sorted(
            item["name"]
            for item in REFERENCE_REPOSITORIES
            if lane_id in item.get("lanes", [])
        )
        row = dict(design)
        row["reference_count"] = len(references)
        row["references"] = references
        rows.append(row)
    return rows


def build_registry() -> dict[str, Any]:
    policy_counts: dict[str, int] = {}
    license_counts: dict[str, int] = {}
    for item in REFERENCE_REPOSITORIES:
        policy = str(item["reuse_policy"])
        license_state = str(item["license_state"])
        policy_counts[policy] = policy_counts.get(policy, 0) + 1
        license_counts[license_state] = license_counts.get(license_state, 0) + 1

    lanes = _capability_lanes()
    snapshot = {
        "organization": "meta-success",
        "observed_at": OBSERVED_AT,
        "repositories": [dict(item) for item in REFERENCE_REPOSITORIES],
        "capability_lanes": lanes,
    }
    return {
        "schema": SCHEMA_REGISTRY,
        "generated_at": _now(),
        "surface": "SZL Atelier Frontier Workbench",
        "evidence_class": "REPORTED_SNAPSHOT",
        "source_inventory": {
            "organization": "meta-success",
            "observed_at": OBSERVED_AT,
            "observed_public_repository_count": len(REFERENCE_REPOSITORIES),
            "reuse_policy_counts": policy_counts,
            "license_state_counts": license_counts,
            "affiliation": "NONE",
            "clean_room": True,
            "source_copy_used": False,
            "visual_assets_copied": False,
            "brand_identity_reused": False,
            "repositories": [dict(item) for item in REFERENCE_REPOSITORIES],
        },
        "public_site": {
            "source": "https://nexus-ai-multi-agent.vercel.app/",
            "evidence_class": "REPORTED_REFERENCE",
            "embedded": False,
            "assets_copied": False,
            "patterns_abstracted": [
                "multi-studio capability navigation",
                "agent workflow staging",
                "evaluation and telemetry affordances",
            ],
        },
        "capability_lanes": lanes,
        "governance": {
            "trust_ceiling": TRUST_CEILING,
            "formula_version": FORMULA_VERSION,
            "safety_gate": "HARD_ZERO",
            "external_writes": "DISABLED",
            "effectors": [],
            "automatic_retries": 0,
            "license_rule": "UNVERIFIED_LICENSE_MEANS_NO_SOURCE_COPY",
            "attribution_rule": "VERIFIED_LICENSE_NOTICES_ARE_PRESERVED",
            "verified_mit_notice_sha256": MIT_NOTICE_SHA256,
        },
        "snapshot_sha256": _canonical_digest(snapshot),
        "routes": {
            "page": "/atelier/frontier",
            "registry": "/api/a11oy/v1/atelier/frontier/registry",
            "evaluate": "/api/a11oy/v1/atelier/frontier/evaluate",
            "atelier": "/atelier",
        },
        "private_reasoning_collected": False,
    }


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    prefix = f"/api/{ns}/v1/atelier/frontier"
    intended_paths = {
        "/atelier/frontier",
        "/atelier/frontier/",
        "/atelier/frontier/app.js",
        "/atelier/frontier/app.js/",
        "/atelier/frontier/styles.css",
        "/atelier/frontier/styles.css/",
        f"{prefix}/registry",
        f"{prefix}/registry/",
        f"{prefix}/evaluate",
        f"{prefix}/evaluate/",
    }
    existing = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in intended_paths
    ]
    if existing:
        complete = {
            getattr(route, "path", None) for route in existing
        } == intended_paths
        owned = all(
            getattr(getattr(route, "endpoint", None), "__module__", None)
            == __name__
            for route in existing
        )
        methods_complete = all(
            {"GET", "HEAD"}.issubset(getattr(route, "methods", set()))
            for route in existing
        )
        if complete and owned and methods_complete and len(existing) == len(intended_paths):
            return {
                "ok": True,
                "state": "ALREADY_REGISTERED",
                "routes": sorted(intended_paths),
            }
        raise RuntimeError("ATELIER_FRONTIER_ROUTE_COLLISION")

    async def page(request: Request) -> Response:
        html = (
            _asset_bytes("index.html")
            .decode("utf-8")
            .replace("__APP_ASSET_DIGEST__", _asset_digest("app.js"))
            .replace("__STYLE_ASSET_DIGEST__", _asset_digest("styles.css"))
        )
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="text/html",
                headers=PAGE_HEADERS,
            )
        return HTMLResponse(html, headers=PAGE_HEADERS)

    async def js(request: Request) -> Response:
        content = _asset_bytes("app.js")
        headers = {
            **NO_STORE_HEADERS,
            "cache-control": _asset_cache_control(request, content),
        }
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/javascript",
                headers=headers,
            )
        return Response(content, media_type="application/javascript", headers=headers)

    async def css(request: Request) -> Response:
        content = _asset_bytes("styles.css")
        headers = {
            **NO_STORE_HEADERS,
            "cache-control": _asset_cache_control(request, content),
        }
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="text/css",
                headers=headers,
            )
        return Response(content, media_type="text/css", headers=headers)

    async def registry(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers=NO_STORE_HEADERS,
            )
        return JSONResponse(build_registry(), headers=NO_STORE_HEADERS)

    async def evaluate(request: Request) -> Response:
        energy_state = _single(request, "energy_state", "UNAVAILABLE").upper()
        if energy_state not in ALLOWED_ENERGY_STATES:
            raise HTTPException(
                status_code=422,
                detail="energy_state must be REPORTED or UNAVAILABLE",
            )
        result = evaluate_candidate(
            evidence=_score(request, "evidence", 50),
            repeatability=_score(request, "repeatability", 50),
            coverage=_score(request, "coverage", 50),
            governance=_score(request, "governance", 50),
            safety=_binary(request, "safety", 0),
            energy=_score(request, "energy", 50),
            energy_state=energy_state,
        )
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers=NO_STORE_HEADERS,
            )
        return JSONResponse(result, headers=NO_STORE_HEADERS)

    routes: list[tuple[str, Callable[..., Any], list[str]]] = [
        ("/atelier/frontier", page, ["GET", "HEAD"]),
        ("/atelier/frontier/", page, ["GET", "HEAD"]),
        ("/atelier/frontier/app.js", js, ["GET", "HEAD"]),
        ("/atelier/frontier/app.js/", js, ["GET", "HEAD"]),
        ("/atelier/frontier/styles.css", css, ["GET", "HEAD"]),
        ("/atelier/frontier/styles.css/", css, ["GET", "HEAD"]),
        (f"{prefix}/registry", registry, ["GET", "HEAD"]),
        (f"{prefix}/registry/", registry, ["GET", "HEAD"]),
        (f"{prefix}/evaluate", evaluate, ["GET", "HEAD"]),
        (f"{prefix}/evaluate/", evaluate, ["GET", "HEAD"]),
    ]
    added: list[str] = []
    for path, endpoint, methods in routes:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=False)
        added.append(path)

    added_set = set(added)
    selected = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in added_set
    ]
    selected_ids = {id(route) for route in selected}
    app.router.routes[:] = selected + [
        route for route in app.router.routes if id(route) not in selected_ids
    ]

    return {
        "ok": True,
        "state": "REGISTERED",
        "namespace": ns,
        "routes": sorted(added),
        "operating_mode": "READ_ONLY_MODELED_EVALUATION",
        "sign_on_read": False,
        "external_writes": "DISABLED",
        "effectors": [],
        "private_reasoning_collected": False,
    }
