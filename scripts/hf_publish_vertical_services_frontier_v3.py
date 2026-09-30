#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Promote the exact vertical-services frontier-v3 runtime through one writer.

This wrapper deliberately reuses the reviewed v2 deployment implementation and
changes only source identity, version, smoke routes, public-source probes, and
terminal frontier verification. The underlying publisher retains its exact
Dockerfile-derived upload, source-tip guard, secret preservation, restart,
byte-attestation, and immutable receipt path.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
BASE_IMPL = HERE / "hf_publish_vertical_services.py"

SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"
EXPECTED_VERSION = "2.2.0"
USER_AGENT = "SZLHOLDINGS-Vertical-Frontier-v3-Publisher/1.0"

CANONICAL_VERTICALS = (
    "sentra",
    "lyte",
    "killinchu",
    "finance",
    "terra",
    "counsel",
)

LIVE_PROBES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("sentra", "cisa-kev", {"limit": 3}),
    ("lyte", "github-actions", {"repository": "vertical-services", "limit": 10}),
    ("killinchu", "noaa-ais-2025", {}),
    ("finance", "sec-submissions", {"cik": "320193", "limit": 3}),
    ("finance", "polymarket-markets", {"limit": 5}),
    ("finance", "coinbase-spot", {"base": "BTC", "currency": "USD"}),
    ("finance", "treasury-average-rates", {"limit": 5}),
    ("terra", "nyc-pluto", {"borough": "MN", "limit": 1}),
    ("terra", "nyc-hpd-violations", {"limit": 5}),
    ("terra", "nyc-dob-violations", {"limit": 5}),
    ("counsel", "federal-register", {"limit": 3}),
)

SMOKE_PATHS = (
    "/",
    "/healthz",
    "/readyz",
    "/api/build-info",
    "/api/catalog",
    "/api/verticals",
    "/sentra/healthz",
    "/lyte/healthz",
    "/killinchu/healthz",
    "/vessels/healthz",
    "/finance/healthz",
    "/terra/healthz",
    "/counsel/healthz",
    "/api/verticals/aegis/frontier",
    "/api/verticals/defend/frontier",
    "/api/verticals/puriq/frontier",
    "/api/verticals/markets/frontier",
    "/api/verticals/real-estate/frontier",
    "/api/verticals/business-observability/frontier",
    "/api/verticals/prism/frontier",
    "/api/verticals/vessels/frontier",
    "/experience/defend",
    "/experience/lyte",
    "/experience/killinchu",
    "/experience/puriq",
    "/experience/terra",
    "/experience/prism",
    "/api/verticals/sentra/anatomy",
    "/api/verticals/lyte/formulas",
    "/api/verticals/killinchu/connectors",
    "/api/verticals/finance/readyz",
    "/api/verticals/terra/anatomy",
    "/api/verticals/counsel/formulas",
)

ALIASES = {
    "aegis": "sentra",
    "defend": "sentra",
    "puriq": "finance",
    "markets": "finance",
    "real-estate": "terra",
    "business-observability": "lyte",
    "prism": "counsel",
    "vessels": "killinchu",
}

EXPERIENCES = {
    "defend": ("Killinchu Defend Plane", "threat-shield"),
    "lyte": ("Lyte Signal Lattice", "service-lattice"),
    "killinchu": ("Killinchu Voyage Radar", "voyage-radar"),
    "puriq": ("PURIQ Market Chamber", "probability-orbit"),
    "terra": ("Terra Parcel Loom", "parcel-grid"),
    "prism": ("PRISM Authority Chain", "authority-chain"),
}


def load_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "szl_vertical_services_v2_base",
        BASE_IMPL,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base publisher: {BASE_IMPL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_text(base: ModuleType, path: str) -> tuple[int, str]:
    separator = "&" if "?" in path else "?"
    request = urllib.request.Request(
        f"{base.ORIGIN}{path}{separator}szl_frontier_verify={time.time_ns()}",
        headers={
            "Accept": "text/html, application/json;q=0.8",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def verify_frontier(base: ModuleType) -> dict[str, Any]:
    failures: list[str] = []
    aliases: list[dict[str, Any]] = []
    for alias, canonical in ALIASES.items():
        status, body = base.request_json(f"/api/verticals/{alias}/frontier")
        item = {
            "alias": alias,
            "canonical": body.get("vertical") if isinstance(body, dict) else None,
            "http_status": status,
            "alias_resolved": (
                body.get("alias_resolved") if isinstance(body, dict) else None
            ),
            "hatun_can_authorize": (
                body.get("hatun", {}).get("can_authorize")
                if isinstance(body, dict)
                else None
            ),
            "effectors_enabled": (
                body.get("hatun", {}).get("effectors_enabled")
                if isinstance(body, dict)
                else None
            ),
            "source_revision": (
                body.get("source", {}).get("build", {}).get("revision")
                if isinstance(body, dict)
                else None
            ),
        }
        if (
            status != 200
            or item["canonical"] != canonical
            or item["alias_resolved"] is not True
            or item["hatun_can_authorize"] is not False
            or item["effectors_enabled"] is not False
            or item["source_revision"] != SOURCE_REVISION
        ):
            failures.append(f"alias/{alias}: frontier contract mismatch")
        aliases.append(item)

    experiences: list[dict[str, Any]] = []
    experience_hashes: set[str] = set()
    for alias, (title, motif) in EXPERIENCES.items():
        status, text = request_text(base, f"/experience/{alias}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        item = {
            "alias": alias,
            "http_status": status,
            "title_observed": title in text,
            "motif_observed": f'data-motif="{motif}"' in text,
            "viewport_observed": "viewport-fit=cover" in text,
            "reduced_motion_observed": (
                "@media(prefers-reduced-motion:reduce)" in text
            ),
            "forced_colors_observed": "@media(forced-colors:active)" in text,
            "sha256": digest,
        }
        if (
            status != 200
            or item["title_observed"] is not True
            or item["motif_observed"] is not True
            or item["viewport_observed"] is not True
            or item["reduced_motion_observed"] is not True
            or item["forced_colors_observed"] is not True
        ):
            failures.append(f"experience/{alias}: public experience mismatch")
        experiences.append(item)
        experience_hashes.add(digest)
    if len(experience_hashes) != len(EXPERIENCES):
        failures.append("experiences: six public interfaces are not byte-distinct")

    finance_status, finance = base.request_json("/api/verticals/finance/connectors")
    terra_status, terra = base.request_json("/api/verticals/terra/connectors")
    finance_ids = {
        item.get("id")
        for item in finance.get("connectors", [])
        if isinstance(item, dict)
    } if isinstance(finance, dict) else set()
    terra_ids = {
        item.get("id")
        for item in terra.get("connectors", [])
        if isinstance(item, dict)
    } if isinstance(terra, dict) else set()
    expected_finance = {
        "sec-submissions",
        "sec-companyfacts",
        "polymarket-markets",
        "coinbase-spot",
        "treasury-average-rates",
    }
    expected_terra = {
        "nyc-pluto",
        "nyc-hpd-violations",
        "nyc-dob-violations",
    }
    if finance_status != 200 or not expected_finance.issubset(finance_ids):
        failures.append("finance: frontier connector set is incomplete")
    if terra_status != 200 or not expected_terra.issubset(terra_ids):
        failures.append("terra: frontier connector set is incomplete")

    session = secrets.token_urlsafe(32)
    headers = {"X-SZL-Session": session}
    boundary_probes: list[dict[str, Any]] = []
    boundary_requests = (
        (
            "puriq",
            "polymarket-markets",
            {"limit": 2},
            ("trading_enabled", "custody_enabled"),
        ),
        (
            "finance",
            "coinbase-spot",
            {"base": "BTC", "currency": "USD"},
            ("trading_enabled", "custody_enabled"),
        ),
        (
            "terra",
            "nyc-hpd-violations",
            {"limit": 2},
            ("person_level_prospecting",),
        ),
        (
            "real-estate",
            "nyc-dob-violations",
            {"limit": 2},
            ("person_level_prospecting",),
        ),
    )
    evidence_ref = ""
    for vertical, connector, parameters, false_fields in boundary_requests:
        status, body = base.request_json(
            f"/api/verticals/{vertical}/connectors/{connector}/fetch",
            method="POST",
            payload={"parameters": parameters, "force_refresh": True},
            headers=headers,
        )
        observation = body.get("observation", {}) if isinstance(body, dict) else {}
        receipt = body.get("receipt", {}) if isinstance(body, dict) else {}
        item = {
            "vertical": vertical,
            "connector": connector,
            "http_status": status,
            "receipt_id": receipt.get("receipt_id"),
            "state": receipt.get("state"),
            "boundaries": {field: observation.get(field) for field in false_fields},
        }
        if connector == "polymarket-markets" and isinstance(
            receipt.get("receipt_id"), str
        ):
            evidence_ref = receipt["receipt_id"]
        if (
            status != 200
            or receipt.get("state") != "OBSERVED"
            or not isinstance(receipt.get("receipt_id"), str)
            or len(receipt["receipt_id"]) != 64
            or any(observation.get(field) is not False for field in false_fields)
        ):
            failures.append(f"boundary/{vertical}/{connector}: contract mismatch")
        boundary_probes.append(item)

    brain_status, brain = base.request_json(
        "/api/verticals/puriq/second-brain",
        headers=headers,
    )
    memory_count = (
        brain.get("memory", {}).get("count") if isinstance(brain, dict) else None
    )
    if brain_status != 200 or not isinstance(memory_count, int) or memory_count < 2:
        failures.append("puriq: Second-Brain session memory did not observe receipts")

    hatun_status, hatun = base.request_json(
        "/api/verticals/puriq/hatun/evaluate",
        method="POST",
        payload={
            "intent": "review the source-bound public market evidence",
            "requested_action": "market.review",
            "axes": {
                "evidence": 0.95,
                "freshness": 0.92,
                "reversibility": 0.97,
            },
            "evidence_refs": [evidence_ref or "receipt-unavailable"],
        },
        headers=headers,
    )
    if (
        hatun_status != 200
        or not isinstance(hatun, dict)
        or hatun.get("decision") != "REVIEW"
        or hatun.get("can_authorize") is not False
        or hatun.get("can_execute") is not False
        or hatun.get("effectors_enabled") is not False
        or "Conjecture 1" not in str(hatun.get("lambda_status"))
    ):
        failures.append("puriq: Hatun review boundary did not close")

    health_status, health = base.request_json("/healthz")
    if (
        health_status != 200
        or not isinstance(health, dict)
        or health.get("hatun_can_authorize") is not False
        or health.get("effectors_enabled") is not False
        or health.get("version") != EXPECTED_VERSION
    ):
        failures.append("root: frontier authority boundary mismatch")

    return {
        "schema": "szl.vertical-frontier-live-proof/v3",
        "source_revision": SOURCE_REVISION,
        "expected_version": EXPECTED_VERSION,
        "aliases": aliases,
        "experiences": experiences,
        "unique_experience_count": len(experience_hashes),
        "connector_sets": {
            "finance": sorted(finance_ids),
            "terra": sorted(terra_ids),
        },
        "boundary_probes": boundary_probes,
        "second_brain": {
            "http_status": brain_status,
            "memory_count": memory_count,
            "raw_session_token_recorded": False,
        },
        "hatun": {
            "http_status": hatun_status,
            "decision": hatun.get("decision") if isinstance(hatun, dict) else None,
            "can_authorize": (
                hatun.get("can_authorize") if isinstance(hatun, dict) else None
            ),
            "can_execute": (
                hatun.get("can_execute") if isinstance(hatun, dict) else None
            ),
        },
        "trading_enabled": False,
        "custody_enabled": False,
        "person_level_real_estate_prospecting": False,
        "effectors_enabled": False,
        "failures": failures,
        "complete": not failures,
        "truth_label": "MEASURED",
    }


def configure(base: ModuleType) -> ModuleType:
    base.SOURCE_REVISION = SOURCE_REVISION
    base.EXPECTED_VERSION = EXPECTED_VERSION
    base.USER_AGENT = USER_AGENT
    base.CANONICAL_VERTICALS = CANONICAL_VERTICALS
    base.LIVE_PROBES = LIVE_PROBES
    base.SMOKE_PATHS = SMOKE_PATHS

    prior_verify = base.verify_contract

    def verify_contract_v3() -> dict[str, Any]:
        result = prior_verify()
        frontier = verify_frontier(base)
        result["frontier_v3"] = frontier
        result["complete"] = bool(
            result.get("complete") is True and frontier.get("complete") is True
        )
        return result

    base.verify_contract = verify_contract_v3
    return base


def main() -> int:
    base = configure(load_base())
    return int(base.main())


if __name__ == "__main__":
    raise SystemExit(main())
