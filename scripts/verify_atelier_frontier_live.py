#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove the live SZL Atelier Frontier surface against one protected source SHA.

The verifier is read-only. It performs exact HEAD/GET probes against the
canonical A11oy origin, validates the clean-room registry and hard-zero MODELED
evaluator, and binds the result to ``/api/build-info``. It never creates a
receipt, credential, deployment, provider mutation, or other effector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REGISTRY_SCHEMA = "szl.atelier-frontier-registry/v1"
EVALUATION_SCHEMA = "szl.atelier-frontier-evaluation/v1"
TRUST_CEILING = 0.97
EXPECTED_REPOSITORY_COUNT = 26
ROUTES = {
    "build_info": "/api/build-info",
    "page": "/atelier/frontier",
    "registry": "/api/a11oy/v1/atelier/frontier/registry",
    "allowed": (
        "/api/a11oy/v1/atelier/frontier/evaluate"
        "?evidence=90&repeatability=90&coverage=90&governance=90"
        "&safety=1&energy_state=UNAVAILABLE"
    ),
    "denied": "/api/a11oy/v1/atelier/frontier/evaluate?safety=0",
}


class LiveProofError(RuntimeError):
    """The live surface does not satisfy the reviewed source-bound contract."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def normalize_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(str(value or "").strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise LiveProofError("origin must be a credential-free HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname.lower()}{port}"


def normalize_sha(value: str) -> str:
    source = str(value or "").strip().lower()
    if SHA40.fullmatch(source) is None:
        raise LiveProofError("source SHA must be an exact lowercase 40-character SHA")
    return source


def _http(method: str, url: str) -> tuple[int, Mapping[str, str], bytes]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": "SZL-atelier-frontier-live-proof/1.0",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.1",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        },
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=45) as response:
            body = b"" if method == "HEAD" else response.read(1_048_576)
            return response.status, dict(response.headers.items()), body
    except urllib.error.HTTPError as exc:
        body = b"" if method == "HEAD" else exc.read(65_536)
        return exc.code, dict(exc.headers.items()), body
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LiveProofError(f"{method} {url} failed: {type(exc).__name__}") from exc


def _json(body: bytes, *, route: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveProofError(f"{route} did not return valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise LiveProofError(f"{route} JSON is not an object")
    return payload


def _route_pair(origin: str, path: str) -> tuple[dict[str, Any], bytes]:
    url = origin + path
    head_status, head_headers, head_body = _http("HEAD", url)
    get_status, get_headers, get_body = _http("GET", url)
    if head_status != 200 or get_status != 200:
        raise LiveProofError(
            f"{path} is not exact-200 operational: HEAD={head_status}; GET={get_status}"
        )
    if head_body:
        raise LiveProofError(f"{path} HEAD returned a response body")
    evidence = {
        "url": url,
        "head_status": head_status,
        "get_status": get_status,
        "content_type": get_headers.get("content-type")
        or get_headers.get("Content-Type"),
        "bytes": len(get_body),
        "sha256": hashlib.sha256(get_body).hexdigest(),
        "redirect_location": get_headers.get("location")
        or get_headers.get("Location"),
        "head_content_type": head_headers.get("content-type")
        or head_headers.get("Content-Type"),
    }
    if evidence["redirect_location"] is not None:
        raise LiveProofError(f"{path} unexpectedly redirected")
    return evidence, get_body


def _validate_build(payload: Mapping[str, Any], source_sha: str) -> dict[str, Any]:
    build = payload.get("build")
    if (
        payload.get("status") != "OBSERVED"
        or payload.get("receipt_minted") is not False
        or not isinstance(build, Mapping)
        or str(build.get("state") or "").upper() != "OBSERVED"
        or str(build.get("revision") or "").lower() != source_sha
        or build.get("revision_source") != "env:SZL_GIT_SHA"
    ):
        raise LiveProofError("build identity is not bound to the exact protected source")
    return {
        "revision": source_sha,
        "revision_source": build["revision_source"],
        "receipt_minted": False,
    }


def _validate_page(body: bytes) -> dict[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LiveProofError("Atelier page is not valid UTF-8") from exc
    markers = (
        'data-szl-public-experience-v3="true"',
        "SZL Atelier · Frontier Workbench",
        "CLEAN-ROOM SYNTHESIS · READ-ONLY · NO AFFILIATION",
        "Source code copied: <b>NO</b>",
        "Brand assets copied: <b>NO</b>",
        "External writes: <b>DISABLED</b>",
        "Trust ceiling: <b>0.97</b>",
    )
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise LiveProofError(f"Atelier page lacks reviewed markers: {missing}")
    return {"markers_verified": list(markers)}


def _validate_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = payload.get("source_inventory")
    governance = payload.get("governance")
    if (
        payload.get("schema") != REGISTRY_SCHEMA
        or payload.get("evidence_class") != "REPORTED_SNAPSHOT"
        or not isinstance(source, Mapping)
        or source.get("organization") != "meta-success"
        or source.get("observed_public_repository_count")
        != EXPECTED_REPOSITORY_COUNT
        or source.get("affiliation") != "NONE"
        or source.get("clean_room") is not True
        or source.get("source_copy_used") is not False
        or source.get("visual_assets_copied") is not False
        or source.get("brand_identity_reused") is not False
        or not isinstance(source.get("repositories"), list)
        or len(source["repositories"]) != EXPECTED_REPOSITORY_COUNT
        or not isinstance(governance, Mapping)
        or governance.get("trust_ceiling") != TRUST_CEILING
        or governance.get("safety_gate") != "HARD_ZERO"
        or governance.get("external_writes") != "DISABLED"
        or governance.get("effectors") != []
        or governance.get("automatic_retries") != 0
    ):
        raise LiveProofError("live Atelier registry violates the clean-room contract")
    policies = source.get("reuse_policy_counts")
    if not isinstance(policies, Mapping) or policies.get("ADAPT_WITH_NOTICE") != 1:
        raise LiveProofError("verified permissive-license lane count drifted")
    snapshot = str(payload.get("snapshot_sha256") or "")
    if SHA256.fullmatch(snapshot) is None:
        raise LiveProofError("registry lacks a deterministic snapshot SHA-256")
    return {
        "repository_count": EXPECTED_REPOSITORY_COUNT,
        "adapt_with_notice_count": 1,
        "snapshot_sha256": snapshot,
        "source_copy_used": False,
        "external_writes": "DISABLED",
        "effectors": [],
    }


def _decision(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    decision = payload.get("decision")
    if payload.get("schema") != EVALUATION_SCHEMA or not isinstance(decision, Mapping):
        raise LiveProofError("evaluator response schema is invalid")
    if (
        payload.get("evidence_class") != "MODELED"
        or decision.get("external_writes") != "DISABLED"
        or decision.get("effectors") != []
        or decision.get("automatic_retries") != 0
        or payload.get("private_reasoning_collected") is not False
    ):
        raise LiveProofError("evaluator attached an unreviewed authority or claim")
    return decision


def _validate_allowed(payload: Mapping[str, Any]) -> dict[str, Any]:
    decision = _decision(payload)
    formula = payload.get("formula")
    fingerprint = payload.get("derivation_fingerprint")
    energy = payload.get("energy")
    if (
        decision.get("state") != "SANDBOX_CANDIDATE"
        or decision.get("reason") != "MODELED_THRESHOLD_MET_NO_EFFECTOR_BOUND"
        or not isinstance(formula, Mapping)
        or not isinstance(formula.get("score"), (int, float))
        or isinstance(formula.get("score"), bool)
        or float(formula["score"]) <= 0
        or float(formula["score"]) > TRUST_CEILING
        or formula.get("trust_ceiling") != TRUST_CEILING
        or not isinstance(fingerprint, Mapping)
        or SHA256.fullmatch(str(fingerprint.get("sha256") or "")) is None
        or fingerprint.get("signature_status") != "UNAVAILABLE"
        or fingerprint.get("persisted") is not False
        or not isinstance(energy, Mapping)
        or energy.get("state") != "UNAVAILABLE"
        or energy.get("score_used") is not None
        or energy.get("joules_claimed") is not False
        or energy.get("measured_claim_permitted") is not False
    ):
        raise LiveProofError("allowed MODELED evaluator response violates the contract")
    return {
        "state": decision["state"],
        "score": formula["score"],
        "fingerprint_sha256": fingerprint["sha256"],
        "external_writes": "DISABLED",
        "effectors": [],
    }


def _validate_denied(payload: Mapping[str, Any]) -> dict[str, Any]:
    decision = _decision(payload)
    formula = payload.get("formula")
    if (
        decision.get("state") != "DENIED"
        or decision.get("reason") != "SAFETY_GATE_FAILED"
        or not isinstance(formula, Mapping)
        or formula.get("score") != 0
        or formula.get("uncapped") != 0
    ):
        raise LiveProofError("safety=0 did not hard-zero the live evaluator")
    return {
        "state": "DENIED",
        "reason": "SAFETY_GATE_FAILED",
        "score": 0,
        "external_writes": "DISABLED",
        "effectors": [],
    }


def prove(origin: str, source_sha: str) -> dict[str, Any]:
    canonical_origin = normalize_origin(origin)
    source = normalize_sha(source_sha)
    routes: dict[str, Any] = {}

    evidence, body = _route_pair(canonical_origin, ROUTES["build_info"])
    evidence["contract"] = _validate_build(
        _json(body, route=ROUTES["build_info"]), source
    )
    routes["build_info"] = evidence

    evidence, body = _route_pair(canonical_origin, ROUTES["page"])
    evidence["contract"] = _validate_page(body)
    routes["page"] = evidence

    evidence, body = _route_pair(canonical_origin, ROUTES["registry"])
    evidence["contract"] = _validate_registry(
        _json(body, route=ROUTES["registry"])
    )
    routes["registry"] = evidence

    evidence, body = _route_pair(canonical_origin, ROUTES["allowed"])
    allowed = _validate_allowed(_json(body, route=ROUTES["allowed"]))
    evidence["contract"] = allowed
    routes["allowed"] = evidence

    repeat_evidence, repeat_body = _route_pair(
        canonical_origin, ROUTES["allowed"]
    )
    repeated = _validate_allowed(_json(repeat_body, route=ROUTES["allowed"]))
    if repeated["fingerprint_sha256"] != allowed["fingerprint_sha256"]:
        raise LiveProofError("identical MODELED inputs produced a different fingerprint")
    routes["allowed_repeat"] = {
        **repeat_evidence,
        "contract": repeated,
        "fingerprint_matches": True,
    }

    evidence, body = _route_pair(canonical_origin, ROUTES["denied"])
    evidence["contract"] = _validate_denied(
        _json(body, route=ROUTES["denied"])
    )
    routes["denied"] = evidence

    return {
        "schema": "szl.atelier-frontier-live-proof/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "ok": True,
        "origin": canonical_origin,
        "github_source_sha": source,
        "source_bound": True,
        "read_only": True,
        "receipt_minted": False,
        "external_writes": "DISABLED",
        "effectors": [],
        "routes": routes,
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = prove(args.origin, args.source_sha)
        code = 0
    except LiveProofError as exc:
        report = {
            "schema": "szl.atelier-frontier-live-proof/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "ok": False,
            "origin": str(args.origin),
            "github_source_sha": str(args.source_sha),
            "source_bound": False,
            "read_only": True,
            "receipt_minted": False,
            "external_writes": "DISABLED",
            "effectors": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 1
    write_report(args.report, report)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
