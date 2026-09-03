# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_atelier_frontier_live.py"
SPEC = importlib.util.spec_from_file_location("verify_atelier_frontier_live", SCRIPT)
assert SPEC and SPEC.loader
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)

SOURCE = "a" * 40
ORIGIN = "https://szlholdings-a11oy.hf.space"
FINGERPRINT = "b" * 64
SNAPSHOT = "c" * 64


def _body(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _payloads() -> dict[str, object]:
    return {
        "build_info": {
            "status": "OBSERVED",
            "receipt_minted": False,
            "build": {
                "state": "OBSERVED",
                "revision": SOURCE,
                "revision_source": "env:SZL_GIT_SHA",
            },
        },
        "page": (
            '<html lang="en" data-szl-public-experience-v3="true">'
            "<title>SZL Atelier · Frontier Workbench</title>"
            "<p>CLEAN-ROOM SYNTHESIS · READ-ONLY · NO AFFILIATION</p>"
            "<span>Source code copied: <b>NO</b></span>"
            "<span>Brand assets copied: <b>NO</b></span>"
            "<span>External writes: <b>DISABLED</b></span>"
            "<span>Trust ceiling: <b>0.97</b></span>"
            "</html>"
        ),
        "registry": {
            "schema": live.REGISTRY_SCHEMA,
            "evidence_class": "REPORTED_SNAPSHOT",
            "snapshot_sha256": SNAPSHOT,
            "source_inventory": {
                "organization": "meta-success",
                "observed_public_repository_count": 26,
                "affiliation": "NONE",
                "clean_room": True,
                "source_copy_used": False,
                "visual_assets_copied": False,
                "brand_identity_reused": False,
                "repositories": [{"name": f"repo-{index}"} for index in range(26)],
                "reuse_policy_counts": {
                    "ADAPT_WITH_NOTICE": 1,
                    "CLEAN_ROOM_ONLY": 25,
                },
            },
            "governance": {
                "trust_ceiling": 0.97,
                "safety_gate": "HARD_ZERO",
                "external_writes": "DISABLED",
                "effectors": [],
                "automatic_retries": 0,
            },
        },
        "allowed": {
            "schema": live.EVALUATION_SCHEMA,
            "evidence_class": "MODELED",
            "formula": {
                "score": 0.9,
                "uncapped": 0.9,
                "trust_ceiling": 0.97,
            },
            "decision": {
                "state": "SANDBOX_CANDIDATE",
                "reason": "MODELED_THRESHOLD_MET_NO_EFFECTOR_BOUND",
                "external_writes": "DISABLED",
                "effectors": [],
                "automatic_retries": 0,
            },
            "derivation_fingerprint": {
                "sha256": FINGERPRINT,
                "signature_status": "UNAVAILABLE",
                "persisted": False,
            },
            "energy": {
                "state": "UNAVAILABLE",
                "score_used": None,
                "joules_claimed": False,
                "measured_claim_permitted": False,
            },
            "private_reasoning_collected": False,
        },
        "denied": {
            "schema": live.EVALUATION_SCHEMA,
            "evidence_class": "MODELED",
            "formula": {"score": 0, "uncapped": 0, "trust_ceiling": 0.97},
            "decision": {
                "state": "DENIED",
                "reason": "SAFETY_GATE_FAILED",
                "external_writes": "DISABLED",
                "effectors": [],
                "automatic_retries": 0,
            },
            "private_reasoning_collected": False,
        },
    }


def _fake_http(payloads: dict[str, object]):
    allowed_gets = 0

    def request(method: str, url: str):
        nonlocal allowed_gets
        path = url.removeprefix(ORIGIN)
        route = next(name for name, value in live.ROUTES.items() if value == path)
        headers = {
            "content-type": (
                "text/html; charset=utf-8" if route == "page" else "application/json"
            )
        }
        if method == "HEAD":
            return 200, headers, b""
        if route == "allowed":
            allowed_gets += 1
        return 200, headers, _body(payloads[route])

    return request


def test_normalization_is_credential_free_and_exact() -> None:
    assert live.normalize_origin(ORIGIN + "/") == ORIGIN
    assert live.normalize_sha(SOURCE.upper()) == SOURCE
    for bad in ("http://example.com", "https://user@example.com", "https://example.com/x"):
        with pytest.raises(live.LiveProofError):
            live.normalize_origin(bad)
    with pytest.raises(live.LiveProofError):
        live.normalize_sha("abc")


def test_complete_source_bound_live_proof_passes_without_network() -> None:
    payloads = _payloads()
    with mock.patch.object(live, "_http", side_effect=_fake_http(payloads)) as request:
        report = live.prove(ORIGIN, SOURCE)
    assert report["status"] == "PASS"
    assert report["github_source_sha"] == SOURCE
    assert report["source_bound"] is True
    assert report["routes"]["registry"]["contract"]["repository_count"] == 26
    assert report["routes"]["allowed_repeat"]["fingerprint_matches"] is True
    assert report["routes"]["denied"]["contract"]["score"] == 0
    assert request.call_count == 12


def test_registry_count_drift_fails_closed() -> None:
    payloads = _payloads()
    payloads["registry"]["source_inventory"]["observed_public_repository_count"] = 25  # type: ignore[index]
    with mock.patch.object(live, "_http", side_effect=_fake_http(payloads)):
        with pytest.raises(live.LiveProofError, match="clean-room contract"):
            live.prove(ORIGIN, SOURCE)


def test_missing_page_honesty_marker_fails_closed() -> None:
    payloads = _payloads()
    payloads["page"] = str(payloads["page"]).replace(
        "External writes: <b>DISABLED</b>", "External writes: ENABLED"
    )
    with mock.patch.object(live, "_http", side_effect=_fake_http(payloads)):
        with pytest.raises(live.LiveProofError, match="lacks reviewed markers"):
            live.prove(ORIGIN, SOURCE)


def test_build_revision_must_match_exact_protected_source() -> None:
    payloads = _payloads()
    payloads["build_info"]["build"]["revision"] = "d" * 40  # type: ignore[index]
    with mock.patch.object(live, "_http", side_effect=_fake_http(payloads)):
        with pytest.raises(live.LiveProofError, match="exact protected source"):
            live.prove(ORIGIN, SOURCE)


def test_identical_modeled_inputs_must_repeat_the_fingerprint() -> None:
    payloads = _payloads()
    original = _fake_http(payloads)
    allowed_gets = 0

    def drift(method: str, url: str):
        nonlocal allowed_gets
        status, headers, body = original(method, url)
        if method == "GET" and url.endswith(live.ROUTES["allowed"]):
            allowed_gets += 1
            if allowed_gets == 2:
                value = json.loads(body)
                value["derivation_fingerprint"]["sha256"] = "e" * 64
                body = _body(value)
        return status, headers, body

    with mock.patch.object(live, "_http", side_effect=drift):
        with pytest.raises(live.LiveProofError, match="different fingerprint"):
            live.prove(ORIGIN, SOURCE)


def test_safety_zero_must_produce_exact_hard_zero_denial() -> None:
    payloads = _payloads()
    payloads["denied"]["formula"]["score"] = 0.01  # type: ignore[index]
    with mock.patch.object(live, "_http", side_effect=_fake_http(payloads)):
        with pytest.raises(live.LiveProofError, match="hard-zero"):
            live.prove(ORIGIN, SOURCE)


def test_redirect_or_non_200_is_never_accepted() -> None:
    payloads = _payloads()
    original = _fake_http(payloads)

    def redirect(method: str, url: str):
        if method == "GET" and url.endswith(live.ROUTES["page"]):
            return 302, {"location": "/"}, b""
        return original(method, url)

    with mock.patch.object(live, "_http", side_effect=redirect):
        with pytest.raises(live.LiveProofError, match="exact-200"):
            live.prove(ORIGIN, SOURCE)
