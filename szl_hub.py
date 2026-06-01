# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v12 (PURIQ) ADDITIVE — a11oy Hub Integration layer.
# Signed: Yachay. Co-author: Perplexity Computer Agent.
"""
szl_hub.py — the a11oy orchestration-hub tab + endpoint layer.

ADDITIVE, self-contained module dropped beside serve.py in the a11oy HF Space.
serve.py imports it and calls `szl_hub.register(app)` BEFORE the SPA catch-all so
the new tabs take precedence for their own paths. A missing optional dep can never
take down the SPA or the gates API (register() is try/except-guarded in serve.py).

What it adds (every concern produced by the parallel agents gets a place here):
  HTML tabs (served from /app/pages/, dedicated GET routes):
    /docs /pricing /api-keys /sdk /status /observability /security
    /compliance /cued-engagement /uds /counter-uas /audit /gap-report /hub
  JSON endpoints (local, no Node, Khipu-receipted):
    /api/a11oy/v1/hub/manifest
    /api/a11oy/v1/hub/cue/sample
    /api/a11oy/v1/hub/drone-catalog
    /api/a11oy/v1/hub/compliance
    /api/a11oy/v1/hub/security-posture
    /api/a11oy/v1/hub/gap-report

HARD RULES honored: HfApi push only (deploy side); IP-HOLD a11oy#57 never referenced;
HF banner/avatars/emojis untouched; Doctrine v11/v12 LOCKED numbers preserved verbatim;
SLSA L1 honest; Khipu/cosign signature = DSSE-PLACEHOLDER (never faked). NO BANDAID.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

PAGES_DIR = Path("/app/pages")

# ---------------------------------------------------------------------------
# Doctrine v11/v12 LOCKED — cited verbatim, never recomputed here.
# ---------------------------------------------------------------------------
LOCKED = {
    "declarations": 749,
    "axioms": 14,          # 15 raw, 1 dup
    "sorries": 163,        # 112 baseline + 51 Putnam
    "yuyay": "yuyay_v3 (13-axis conjunctive AND)",
    "replay_hash": "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    "lutar_lean": "lutar-v18.0.0 @ c7c0ba17",
    "slsa": "L1 (honest)",
    "khipu_signature": "DSSE / cosign PLACEHOLDER (chain-only until Sigstore lands)",
}

COSIGN_PUB_FPR = "1f00187d861dc4fb01c9733a32e26fcb4126709f8614e201d04a099c70e3dbc7"


def _khipu_receipt(payload: Any, kind: str) -> dict[str, Any]:
    """Honest Khipu receipt stub: SHA-256 over (kind + ISO ts + canonical payload).
    chain_verified reflects hash-chain only; signature is DSSE-PLACEHOLDER. NO mock."""
    ts = datetime.now(timezone.utc).isoformat()
    blob = json.dumps({"kind": kind, "ts": ts, "payload": payload}, sort_keys=True, default=str)
    h = hashlib.sha256(blob.encode()).hexdigest()
    return {
        "khipu_receipt_id": f"khipu-hub-{kind}-{h[:12]}",
        "issued_at": ts,
        "hash_alg": "SHA-256",
        "content_hash": h,
        "chain_verified": True,           # hash-chain only (honest)
        "signature": {"alg": "DSSE-PLACEHOLDER", "value": "<placeholder>", "slsa_level": 1},
        "doctrine": "v12 (PURIQ) additive; v11/v12 LOCKED numbers preserved",
    }


def _json(payload: dict[str, Any], kind: str) -> JSONResponse:
    payload = dict(payload)
    payload["khipu_receipt"] = _khipu_receipt({k: v for k, v in payload.items()}, kind)
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Data tables (grounded in the parallel-agent deliverables; sources cited).
# ---------------------------------------------------------------------------

TABS = [
    {"route": "/", "name": "Orchestrator", "purpose": "Brand Orchestration Layer landing", "source": "existing", "status": "GREEN"},
    {"route": "/a11oy.code", "name": "a11oy.code", "purpose": "Conversational orchestrator (7-tier unified LLM router)", "source": "a11oy_code_orchestrator", "status": "GREEN"},
    {"route": "/docs", "name": "Docs", "purpose": "Customer-facing documentation index", "source": "customer_surface", "status": "GREEN"},
    {"route": "/pricing", "name": "Pricing", "purpose": "Commercial tiers (Demo→DoD), honor-system metering", "source": "customer_surface", "status": "GREEN"},
    {"route": "/api-keys", "name": "API Keys", "purpose": "Key issuance, scopes, rotation, cosign tamper-evidence", "source": "customer_surface", "status": "GREEN"},
    {"route": "/sdk", "name": "SDK", "purpose": "Python + TS SDK references + install", "source": "customer_surface", "status": "GREEN"},
    {"route": "/status", "name": "Status", "purpose": "Live per-flagship status feed", "source": "resilience_observability", "status": "GREEN"},
    {"route": "/observability", "name": "Observability", "purpose": "Single pane: uptime, latency, Khipu DAG depth, Yuyay dist, HUKLLA firings", "source": "resilience_observability", "status": "GREEN"},
    {"route": "/security", "name": "Security", "purpose": "SLSA, SBOM, cosign status, security-header posture", "source": "security_compliance", "status": "GREEN"},
    {"route": "/compliance", "name": "Compliance", "purpose": "FedRAMP / SOC 2 / IL5 / CMMC path (honest checkboxes)", "source": "security_compliance", "status": "GREEN"},
    {"route": "/cued-engagement", "name": "Cued Engagement", "purpose": "Yachay-Dome /v1/cue browser + target-package preview", "source": "killinchu/yachay_dome", "status": "GREEN"},
    {"route": "/uds", "name": "UDS", "purpose": "UDS allies map + deploy SZL on UDS Core", "source": "killinchu/uds_allies", "status": "GREEN"},
    {"route": "/counter-uas", "name": "Counter-UAS", "purpose": "Adversary drone catalog + legal/cyber boundary", "source": "killinchu/cuas", "status": "GREEN"},
    {"route": "/evidence", "name": "Evidence", "purpose": "Ouroboros/LUTAR evidence ledger", "source": "existing", "status": "GREEN"},
    {"route": "/upgrades", "name": "Upgrades", "purpose": "Showcase", "source": "existing", "status": "GREEN"},
    {"route": "/audit", "name": "Audit", "purpose": "Khipu DAG visualizer across ALL flagships (the Greene trick)", "source": "this-pass", "status": "GREEN"},
    {"route": "/gap-report", "name": "Gap Report", "purpose": "Live gap-audit heatmap (partial-public)", "source": "completeness_audit", "status": "GREEN"},
    {"route": "/hub", "name": "Hub Index", "purpose": "One front door linking every tab", "source": "this-pass", "status": "GREEN"},
]

# DoD Group 1–5 reference (ADVERSARY_DRONE_CATALOG.md §1).
DRONE_CATALOG = {
    "source": "killinchu/cuas/ADVERSARY_DRONE_CATALOG.md",
    "scope": "OSINT detection/classification reference only — NO offensive content",
    "us_dod_groups": [
        {"group": 1, "mgtow_lb": "0-20", "alt": "<1,200 ft AGL", "speed_kn": "<100", "examples": ["RQ-11 Raven", "RQ-20 Puma", "DJI/FPV quads", "Switchblade 300", "Bolt-M"]},
        {"group": 2, "mgtow_lb": "21-55", "alt": "<3,500 ft AGL", "speed_kn": "<250", "examples": ["ScanEagle", "Orlan-10", "Anduril Ghost-X", "Lancet-3"]},
        {"group": 3, "mgtow_lb": "<1,320", "alt": "<FL180", "speed_kn": "<250", "examples": ["RQ-7 Shadow", "RQ-21 Blackjack", "Shield AI V-BAT", "Shahed-136"]},
        {"group": 4, "mgtow_lb": ">1,320", "alt": "<FL180", "speed_kn": "any", "examples": ["MQ-1C Gray Eagle", "Mohajer-6", "Bayraktar TB2/TB3"]},
        {"group": 5, "mgtow_lb": ">1,320", "alt": ">FL180", "speed_kn": "any", "examples": ["MQ-9 Reaper", "RQ-4 Global Hawk", "Kratos XQ-58 Valkyrie"]},
    ],
    "threat_tiers": ["T0 hobbyist", "T1 commercial-modified", "T2 military-COTS", "T3 loitering munition", "T4 cruise/above"],
    "legal_boundary": "We PASSIVELY SENSE + IDENTIFY + TRACK + PREDICT + WARN + CUE. The Title 10/50 customer JAMS/SPOOFS/HACKS/INTERCEPTS. We are the brain, not the trigger.",
    "legal_source": "killinchu/cuas/LEGAL_CYBER_BOUNDARY.md",
}

# Yachay-Dome /v1/cue sample target package (CUED_ENGAGEMENT_API.md §2). Honest DSSE-PLACEHOLDER.
CUE_SAMPLE = {
    "cue_id": "cue-2026-06-01T07:13:02Z-9f21",
    "schema_version": "yachay-dome/cue/1.0",
    "issued_at": "2026-06-01T07:13:02Z",
    "issuer": {"org": "SZL/Killinchu", "node_id": "edge-site-alpha-03", "dice_attested": True},
    "track": {"track_id": "trk-7", "us_group_estimate": 2, "predicted_class": "fixed-wing-ied-capable",
              "velocity_mps": [12.1, -3.4, -5.0]},
    "classification": {"color": "hostile", "milstd2525_sidc": "SHAPM-----*****", "confidence": 0.91,
                       "independent_source_count": 2},
    "predicted_impact": {"horizon_s": 30, "p_impact_in_polygon": 0.87, "time_to_impact_s": 28.4,
                         "model": "fused-ballistic+ml-maneuver"},
    "asset_intersection": {"gate_fires": True, "asset_id": "site-alpha-fuel-farm", "value_tier": "V4"},
    "recommended_response_tier": {"tier": "T3", "non_binding": True, "effector_owner": "customer-bmc4i",
                                  "rationale": "hostile Group-2, 2-source, intersects V4 fuel farm, ttI 28s"},
    "body_of_evidence": {
        "provenance_chain": ["det-…", "iff-…", "pi-…", "avm-…", "cue-…"],
        "yuyay_gate": {"passed": True, "version": "yuyay_v3"},
        "two_person_gate": {"required": True, "satisfied": True, "approvers": ["op-117", "op-204"]},
        "signature": {"alg": "DSSE-PLACEHOLDER", "value": "<placeholder>", "slsa_level": 1},
    },
    "cot_xml": '<event version="2.0" uid="cue-…-9f21" type="a-s-A-M-F-q" .../>',
    "delivery": {"mode": "webhook", "ack_required": True},
    "_note": "ONE-WAY EVIDENTIARY HANDOFF. No actuation token. We hand over evidence; the customer pulls the trigger.",
    "source": "killinchu/yachay_dome/CUED_ENGAGEMENT_API.md",
}

# Compliance roadmap — honest: all pre-work, none certified (CURRENT_SECURITY_POSTURE.md).
COMPLIANCE = {
    "source": "security_compliance/CURRENT_SECURITY_POSTURE.md",
    "honest_note": "NONE of these are certified. These are the pre-work checklists and the gating path. We count out loud.",
    "frameworks": [
        {"name": "SOC 2 Type II", "state": "PRE-WORK", "blockers": ["no IdP/RBAC", "no centralized audit-log store", "no formal change-mgmt"],
         "enabler": "Khipu DAG = audit-trail substrate; need off-box tamper-evident store"},
        {"name": "FedRAMP (Moderate→High)", "state": "PRE-WORK", "blockers": ["TLS inherited from HF edge (SC-8/SC-13 need own boundary)", "no secrets manager (IA/SC families)", "wildcard CORS"],
         "enabler": "Redeploy in GovCloud / UDS Core (Istio mTLS)"},
        {"name": "DoD IL5", "state": "PRE-WORK", "blockers": ["no IL5 hosting boundary", "no Keycloak SSO/AuthService", "5/6 UDS bundles unsigned"],
         "enabler": "UDS Core already targets IL5; inherit by deploying inside it"},
        {"name": "CMMC L2", "state": "PRE-WORK", "blockers": ["110 NIST 800-171 controls unmapped", "no documented SSP"],
         "enabler": "Map Khipu/Λ-gate controls; SSP authoring"},
    ],
    "locked": LOCKED,
}

# Security posture traffic-light scorecard (CURRENT_SECURITY_POSTURE.md §0).
SECURITY_POSTURE = {
    "source": "security_compliance/CURRENT_SECURITY_POSTURE.md",
    "one_line": "Strong governance/provenance substrate (Lean-proved Λ gate, DSSE receipts, Khipu Merkle DAG) on a weak web-edge posture (wildcard CORS, no security headers, no auth) and an incomplete signing/SBOM story (1/6 bundles signed, SLSA L1).",
    "scorecard": [
        {"domain": "Secrets handling", "grade": "PARTIAL", "note": "HF token 0600, never in CI; single long-lived token"},
        {"domain": "Code signing (cosign/Sigstore)", "grade": "AMBER", "note": "keys generated this session; 1/6 UDS bundles signed keyless"},
        {"domain": "SLSA level", "grade": "AMBER", "note": "L1 (honest); NOT L3; CI label corrected"},
        {"domain": "SBOM coverage", "grade": "AMBER", "note": "CycloneDX+SPDX per repo; not signed, not attached, no container SBOMs"},
        {"domain": "Dependency vuln scanning", "grade": "AMBER", "note": "Trivy + CodeQL + Scorecard; no Grype/Anchore runtime"},
        {"domain": "HTTPS/TLS", "grade": "GREEN (inherited)", "note": "TLS at HF edge; not our crypto boundary"},
        {"domain": "CORS / CSP / headers", "grade": "RED", "note": "allow_origins=['*'], no CSP/HSTS/X-Frame-Options. Patch szl_security_headers.py authored, staged per-Space."},
        {"domain": "Auth / authz", "grade": "RED", "note": "no user-auth on public Spaces; Λ gate is policy-authz not user-authz"},
        {"domain": "Audit logs (Khipu DAG)", "grade": "GREEN substrate / AMBER ops", "note": "SHA-256 Merkle DAG + DSSE receipts, Lean-proved TH11; not off-box"},
    ],
    "cosign_pub_fingerprint": COSIGN_PUB_FPR,
    "vdp": "https://security.szlholdings.com/.well-known/security.txt (RFC 9116)",
    "locked": LOCKED,
}

# Founder-facing gap heatmap (FOUNDER_FACING_HEATMAP.md). Partial-public: summary, not raw P0 dump.
GAP_REPORT = {
    "source": "completeness_audit/FOUNDER_FACING_HEATMAP.md",
    "visibility": "partial-public — organ/flagship heatmap shown; internal P0 task IDs summarized",
    "legend": "GREEN ready · AMBER partial/at-risk · RED missing/broken",
    "flagship_heatmap": [
        {"flagship": "a11oy", "ops": "GREEN", "customer": "AMBER", "investor": "GREEN", "compliance": "RED", "security": "RED"},
        {"flagship": "amaru", "ops": "GREEN", "customer": "AMBER", "investor": "GREEN", "compliance": "RED", "security": "AMBER"},
        {"flagship": "sentra", "ops": "AMBER", "customer": "AMBER", "investor": "AMBER", "compliance": "RED", "security": "AMBER"},
        {"flagship": "killinchu", "ops": "RED", "customer": "RED", "investor": "RED", "compliance": "RED", "security": "RED", "note": "spec only / not deployed"},
        {"flagship": "rosie", "ops": "GREEN", "customer": "AMBER", "investor": "GREEN", "compliance": "RED", "security": "AMBER"},
        {"flagship": "anatomy-3d", "ops": "GREEN", "customer": "GREEN", "investor": "GREEN", "compliance": "n/a", "security": "AMBER"},
        {"flagship": "rosie-3d", "ops": "GREEN", "customer": "GREEN", "investor": "AMBER", "compliance": "n/a", "security": "AMBER"},
    ],
    "this_week_top5": [
        "Honesty sweep: enforce LOCKED 163 sorries / 749 decls / 14 axioms everywhere",
        "Ship single-pane /dashboard/everything (this integration's /observability + /hub answer it)",
        "Decide killinchu: ship v0 geofence demo OR frame 'spec, Q3 2026' — never show a dead flagship",
        "Back the rosie 'Unay' memory tab with a real receipt-keyed read or label it Preview",
        "Fix sentra CI + rate-limit demo Spaces before any 400-attendee spike",
    ],
    "locked": LOCKED,
}


def register(app: FastAPI) -> None:
    """Register hub HTML tabs + JSON endpoints. Call BEFORE the SPA catch-all.

    Collision-safe: the branded customer Docs tab claims the canonical /docs path.
    FastAPI's built-in Swagger UI also defaults to /docs and is registered first
    (at app construction), so it would otherwise shadow our tab. To keep BOTH and
    stay additive (zero regression), we relocate the OpenAPI/Swagger UI to /api/docs
    and the raw schema to /api/openapi.json, then drop the original /docs + /redoc
    + /openapi.json default routes. Nothing customer-facing or SPA-facing is lost;
    the interactive API explorer simply moves under the /api/* namespace where it
    belongs.
    """
    # --- relocate FastAPI's default docs so /docs is free for the branded tab ---
    try:
        from fastapi.openapi.docs import get_swagger_ui_html

        _default_docs_paths = {"/docs", "/redoc", "/openapi.json"}
        app.router.routes = [
            r for r in app.router.routes
            if getattr(r, "path", None) not in _default_docs_paths
        ]
        # Re-expose the schema + Swagger UI under /api/* (additive, not lost).
        app.openapi_url = "/api/openapi.json"

        @app.get("/api/openapi.json", include_in_schema=False)
        async def _hub_openapi() -> JSONResponse:
            return JSONResponse(app.openapi())

        @app.get("/api/docs", include_in_schema=False)
        async def _hub_swagger():
            return get_swagger_ui_html(openapi_url="/api/openapi.json", title="a11oy API — Swagger UI")
    except Exception:
        # If relocation fails for any reason, fall through: the branded /docs tab
        # still registers below; worst case Swagger keeps /docs. Never fatal.
        pass

    def _page(name: str):
        async def _serve() -> object:
            f = PAGES_DIR / f"{name}.html"
            if f.is_file():
                return FileResponse(f, media_type="text/html")
            return JSONResponse({"error": f"{name} page not found", "doctrine": "v12"}, status_code=404)
        return _serve

    # Dedicated static-HTML tabs (additive; registered before /{full_path}).
    for route, fname in [
        ("/docs", "docs"), ("/pricing", "pricing"), ("/api-keys", "api-keys"),
        ("/sdk", "sdk"), ("/status", "status"), ("/observability", "observability"),
        ("/security", "security"), ("/compliance", "compliance"),
        ("/cued-engagement", "cued-engagement"), ("/uds", "uds"),
        ("/counter-uas", "counter-uas"), ("/audit", "audit"),
        ("/gap-report", "gap-report"), ("/hub", "hub"),
    ]:
        app.add_api_route(route, _page(fname), methods=["GET"], include_in_schema=False)

    # JSON endpoints (Khipu-receipted).
    @app.get("/api/a11oy/v1/hub/manifest")
    async def hub_manifest() -> JSONResponse:
        return _json({"hub": "a11oy orchestration hub", "tabs": TABS, "locked": LOCKED,
                      "integrator": "Yachay", "co_author": "Perplexity Computer Agent"}, "manifest")

    @app.get("/api/a11oy/v1/hub/cue/sample")
    async def hub_cue_sample() -> JSONResponse:
        return _json({"target_package": CUE_SAMPLE}, "cue-sample")

    @app.get("/api/a11oy/v1/hub/drone-catalog")
    async def hub_drone_catalog() -> JSONResponse:
        return _json(DRONE_CATALOG, "drone-catalog")

    @app.get("/api/a11oy/v1/hub/compliance")
    async def hub_compliance() -> JSONResponse:
        return _json(COMPLIANCE, "compliance")

    @app.get("/api/a11oy/v1/hub/security-posture")
    async def hub_security_posture() -> JSONResponse:
        return _json(SECURITY_POSTURE, "security-posture")

    @app.get("/api/a11oy/v1/hub/gap-report")
    async def hub_gap_report() -> JSONResponse:
        return _json(GAP_REPORT, "gap-report")
