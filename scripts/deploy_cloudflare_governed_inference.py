#!/usr/bin/env python3
"""Deploy and prove the bounded Cloudflare Workers AI inference route.

Authority is intentionally narrow:

* one versioned Worker script with an ``AI`` binding;
* one exact route: ``a-11-oy.com/api/v2/*``;
* no DNS mutation;
* no change to the existing catch-all A11oy product Worker;
* rollback to the exact prior route owner on failed public proof.

The report is secret-free. It never records credentials or complete provider IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = "https://api.cloudflare.com/client/v4"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKER = ROOT / "cloudflare" / "a11oy-governed-inference-worker.mjs"
ZONE_NAME = "a-11-oy.com"
ROUTE_PATTERN = "a-11-oy.com/api/v2/*"
SCRIPT_PREFIX = "szl-a11oy-governed-inference-"
EDGE_MARKER = "a11oy-governed-inference-v1"
EXPECTED_CONTRACT_SCHEMA = "szl.cloudflare-governed-inference-contract/v1"
EXPECTED_RESPONSE_SCHEMA = "szl.cloudflare-governed-inference-response/v1"
EXPECTED_RECEIPT_SCHEMA = "szl.cloudflare-governed-inference-receipt/v1"
LOCKED_FORMULAS = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
PROBE_PROMPT = (
    "State that Lambda remains Conjecture 1 and advisory. "
    "Do not execute any action. Cite the doctrine evidence handle."
)
MODEL_CANDIDATES = {
    "@cf/zai-org/glm-4.7-flash",
    "@cf/google/gemma-4-26b-a4b-it",
}
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DeployError(RuntimeError):
    """Fail-closed deployment, provider-state, or public-proof error."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def script_name(source_revision: str) -> str:
    revision = source_revision.strip().lower()
    if FULL_SHA_RE.fullmatch(revision) is None:
        raise DeployError("source revision must be an exact lowercase Git SHA")
    return SCRIPT_PREFIX + revision[:16]


def select_token() -> tuple[str, str | None]:
    for name in (
        "CLOUDFLARE_API_TOKEN",
        "CF_API_TOKEN",
        "CLOUDFLARE_TOKEN",
        "CF_TOKEN",
        "CLOUDFLARE_WORKERS_API_TOKEN",
        "CLOUDFLARE_DNS_API_TOKEN",
        "CLOUDFLARE_ZONE_API_TOKEN",
        "CLOUDFLARE_WORKER_API_TOKEN",
        "CF_WORKERS_API_TOKEN",
        "CF_ZONE_API_TOKEN",
    ):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    return "", None


def safe_error(error: BaseException, bearer: str) -> str:
    try:
        text = str(error)
    except Exception:
        text = "<unprintable>"
    if bearer:
        text = text.replace(bearer, "<redacted>")
    return " ".join(text.split())[:2000] or "<empty>"


def request_json(
    method: str,
    path: str,
    *,
    bearer: str,
    payload: Any | None = None,
) -> dict[str, Any]:
    body = None
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {bearer}",
        "user-agent": "szl-cloudflare-governed-inference-deployer/1",
    }
    if payload is not None:
        body = canonical_json(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    request = urllib.request.Request(
        API + path,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:3000]
        raise DeployError(f"Cloudflare HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DeployError(f"Cloudflare request failed: {type(exc).__name__}") from exc
    if not isinstance(value, dict) or value.get("success") is not True:
        errors = value.get("errors") if isinstance(value, dict) else value
        raise DeployError(
            "Cloudflare rejected request: "
            + canonical_json(errors)[:3000]
        )
    return value


def worker_metadata(source_revision: str) -> dict[str, Any]:
    revision = source_revision.strip().lower()
    if FULL_SHA_RE.fullmatch(revision) is None:
        raise DeployError("source revision must be an exact lowercase Git SHA")
    return {
        "main_module": "worker.mjs",
        "compatibility_date": "2026-09-04",
        "bindings": [
            {"type": "ai", "name": "AI"},
            {
                "type": "plain_text",
                "name": "SZL_SOURCE_REVISION",
                "text": revision,
            },
        ],
    }


def multipart_module(
    source: bytes,
    source_revision: str,
) -> tuple[bytes, str]:
    boundary = "----szl" + secrets.token_hex(16)
    metadata = canonical_json(worker_metadata(source_revision)).encode("utf-8")
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="metadata"\r\n'
            "Content-Type: application/json\r\n\r\n"
        ).encode("utf-8"),
        metadata,
        b"\r\n",
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="worker.mjs"; '
            'filename="worker.mjs"\r\n'
            "Content-Type: application/javascript+module\r\n\r\n"
        ).encode("utf-8"),
        source,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def upload_worker(
    account_id: str,
    bearer: str,
    target_script: str,
    worker: Path,
    source_revision: str,
) -> dict[str, Any]:
    body, boundary = multipart_module(worker.read_bytes(), source_revision)
    request = urllib.request.Request(
        f"{API}/accounts/{account_id}/workers/scripts/{target_script}",
        data=body,
        method="PUT",
        headers={
            "accept": "application/json",
            "authorization": f"Bearer {bearer}",
            "content-type": f"multipart/form-data; boundary={boundary}",
            "user-agent": "szl-cloudflare-governed-inference-deployer/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")[:3000]
        raise DeployError(f"Worker upload HTTP {exc.code}: {text}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DeployError(f"Worker upload failed: {type(exc).__name__}") from exc
    if not isinstance(value, dict) or value.get("success") is not True:
        errors = value.get("errors") if isinstance(value, dict) else value
        raise DeployError(
            "Worker upload rejected: " + canonical_json(errors)[:3000]
        )
    return value


def delete_worker(
    account_id: str,
    bearer: str,
    name: str,
) -> dict[str, Any]:
    return request_json(
        "DELETE",
        f"/accounts/{account_id}/workers/scripts/{urllib.parse.quote(name, safe='')}",
        bearer=bearer,
    )


def verify_token(bearer: str) -> dict[str, Any]:
    value = request_json("GET", "/user/tokens/verify", bearer=bearer)
    result = value.get("result") or {}
    if str(result.get("status") or "").lower() != "active":
        raise DeployError("Cloudflare token is not active")
    return {
        "status": "ACTIVE",
        "provider_id_suffix": str(result.get("id") or "")[-6:] or None,
    }


def resolve_zone(bearer: str) -> tuple[str, str]:
    query = urllib.parse.urlencode(
        {
            "name": ZONE_NAME,
            "status": "active",
            "page": 1,
            "per_page": 50,
            "match": "all",
        }
    )
    value = request_json("GET", f"/zones?{query}", bearer=bearer)
    rows = value.get("result") or []
    if not isinstance(rows, list) or len(rows) != 1:
        raise DeployError(
            f"expected exactly one active {ZONE_NAME} zone; observed {len(rows) if isinstance(rows, list) else 'invalid'}"
        )
    zone = rows[0]
    zone_id = str(zone.get("id") or "")
    account = zone.get("account") or {}
    account_id = str(account.get("id") or "")
    if not zone_id or not account_id:
        raise DeployError("zone or account identity unavailable")
    if str(zone.get("name") or "").lower() != ZONE_NAME:
        raise DeployError("zone identity mismatch")
    return zone_id, account_id


def fetch_routes(zone_id: str, bearer: str) -> list[dict[str, Any]]:
    value = request_json(
        "GET",
        f"/zones/{zone_id}/workers/routes?per_page=100&page=1",
        bearer=bearer,
    )
    rows = value.get("result") or []
    if not isinstance(rows, list):
        raise DeployError("invalid Cloudflare route table")
    info = value.get("result_info") or {}
    try:
        pages = int(info.get("total_pages") or 1)
    except (TypeError, ValueError):
        raise DeployError("invalid Cloudflare route pagination") from None
    if pages != 1:
        raise DeployError(f"route table spans {pages} pages")
    return [row for row in rows if isinstance(row, dict)]


def route_plan(
    current: list[dict[str, Any]],
    target_script: str,
) -> dict[str, Any]:
    matches = [
        row for row in current
        if str(row.get("pattern") or "") == ROUTE_PATTERN
    ]
    if len(matches) > 1:
        raise DeployError("duplicate governed inference route")
    if not matches:
        return {
            "action": "create",
            "pattern": ROUTE_PATTERN,
            "route_id": None,
            "prior_script": None,
            "target_script": target_script,
        }
    route = matches[0]
    route_id = str(route.get("id") or "")
    prior_script = str(route.get("script") or "")
    if not route_id or not prior_script:
        raise DeployError("governed inference route identity is incomplete")
    if prior_script == target_script:
        action = "verify-noop"
    elif prior_script.startswith(SCRIPT_PREFIX):
        action = "update"
    else:
        raise DeployError(
            f"governed inference route is owned by foreign script {prior_script!r}"
        )
    return {
        "action": action,
        "pattern": ROUTE_PATTERN,
        "route_id": route_id,
        "prior_script": prior_script,
        "target_script": target_script,
    }


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": plan.get("action"),
        "pattern": plan.get("pattern"),
        "prior_script": plan.get("prior_script"),
        "target_script": plan.get("target_script"),
        "route_id_suffix": str(plan.get("route_id") or "")[-6:] or None,
    }


def apply_route_plan(
    zone_id: str,
    bearer: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "pattern": ROUTE_PATTERN,
        "script": plan["target_script"],
    }
    if plan["action"] == "create":
        value = request_json(
            "POST",
            f"/zones/{zone_id}/workers/routes",
            bearer=bearer,
            payload=payload,
        )
        state = "CREATED"
    elif plan["action"] == "update":
        value = request_json(
            "PUT",
            f"/zones/{zone_id}/workers/routes/{plan['route_id']}",
            bearer=bearer,
            payload=payload,
        )
        state = "UPDATED"
    elif plan["action"] == "verify-noop":
        return {
            "state": "ALREADY_CURRENT",
            "route_id": plan["route_id"],
            "script": plan["target_script"],
        }
    else:
        raise DeployError(f"unsupported route action: {plan['action']}")
    result = value.get("result") or {}
    route_id = str(result.get("id") or plan.get("route_id") or "")
    script = str(result.get("script") or plan["target_script"])
    pattern = str(result.get("pattern") or ROUTE_PATTERN)
    if not route_id or script != plan["target_script"] or pattern != ROUTE_PATTERN:
        raise DeployError("route mutation readback mismatch")
    return {
        "state": state,
        "route_id": route_id,
        "script": script,
        "pattern": pattern,
    }


def rollback_route(
    zone_id: str,
    bearer: str,
    plan: dict[str, Any],
    applied: dict[str, Any] | None,
) -> dict[str, Any]:
    if not applied or applied.get("state") == "ALREADY_CURRENT":
        return {"state": "NOT_REQUIRED"}
    route_id = str(applied.get("route_id") or plan.get("route_id") or "")
    if not route_id:
        return {"state": "FAILED", "error": "route id unavailable"}
    try:
        if plan["action"] == "create":
            request_json(
                "DELETE",
                f"/zones/{zone_id}/workers/routes/{route_id}",
                bearer=bearer,
            )
            return {"state": "CREATED_ROUTE_REMOVED"}
        if plan["action"] == "update":
            prior_script = str(plan.get("prior_script") or "")
            if not prior_script.startswith(SCRIPT_PREFIX):
                raise DeployError("prior script is outside the owned prefix")
            value = request_json(
                "PUT",
                f"/zones/{zone_id}/workers/routes/{route_id}",
                bearer=bearer,
                payload={
                    "pattern": ROUTE_PATTERN,
                    "script": prior_script,
                },
            )
            result = value.get("result") or {}
            if (
                str(result.get("script") or prior_script) != prior_script
                or str(result.get("pattern") or ROUTE_PATTERN) != ROUTE_PATTERN
            ):
                raise DeployError("rollback route readback mismatch")
            return {"state": "PRIOR_SCRIPT_RESTORED", "script": prior_script}
        return {"state": "NOT_REQUIRED"}
    except DeployError as exc:
        return {"state": "FAILED", "error": safe_error(exc, bearer)}


def observation(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = canonical_json(payload).encode("utf-8") if payload is not None else None
    headers = {
        "accept": "application/json",
        "cache-control": "no-cache, no-store, max-age=0",
        "pragma": "no-cache",
        "user-agent": "szl-cloudflare-governed-inference-proof/1",
    }
    if body is not None:
        headers["content-type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST" if body is not None else "GET",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            raw = response.read(262144)
            status = int(response.status)
            response_headers = {
                key.lower(): value for key, value in response.headers.items()
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(262144)
        status = int(exc.code)
        response_headers = {
            key.lower(): value for key, value in exc.headers.items()
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": None,
            "body": {},
            "headers": {},
            "error": type(exc).__name__,
        }
    try:
        parsed = json.loads(raw.decode("utf-8"))
        body_value = parsed if isinstance(parsed, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        body_value = {}
    return {
        "status": status,
        "body": body_value,
        "headers": response_headers,
    }


def validate_probe_payload(
    health: dict[str, Any],
    contract: dict[str, Any],
    inference: dict[str, Any],
    inference_headers: dict[str, str],
    *,
    source_revision: str,
    prompt: str = PROBE_PROMPT,
) -> dict[str, Any]:
    if health.get("status") != "READY":
        raise DeployError("live governed health is not READY")
    if health.get("source_revision") != source_revision:
        raise DeployError("live governed health source revision mismatch")
    if health.get("ai_binding") is not True:
        raise DeployError("live Workers AI binding is unavailable")
    if (health.get("doctrine") or {}).get("state") != "LOCKED":
        raise DeployError("live doctrine is not LOCKED")
    if health.get("owned_model_served") is not False:
        raise DeployError("external runtime was mislabeled as owned-model inference")
    if health.get("action_authority") != "NONE":
        raise DeployError("live health gained action authority")

    if contract.get("schema") != EXPECTED_CONTRACT_SCHEMA:
        raise DeployError("live contract schema mismatch")
    if contract.get("source_revision") != source_revision:
        raise DeployError("live contract source revision mismatch")
    runtime = contract.get("runtime") or {}
    if runtime.get("tools") is not False:
        raise DeployError("live contract enables tools")
    if runtime.get("action_authority") != "NONE":
        raise DeployError("live contract gained action authority")
    if runtime.get("output_state") != "PROPOSAL_ONLY":
        raise DeployError("live contract output boundary mismatch")
    owned = contract.get("owned_model") or {}
    if owned.get("served_by_this_runtime") is not False:
        raise DeployError("owned model service status was fabricated")
    formula = (contract.get("governance") or {}).get("lambda") or {}
    if (
        formula.get("status") != "CONJECTURE_1_ADVISORY"
        or formula.get("can_authorize") is not False
    ):
        raise DeployError("Lambda contract drift")

    if inference.get("schema") != EXPECTED_RESPONSE_SCHEMA:
        raise DeployError("live inference schema mismatch")
    if inference.get("source_revision") != source_revision:
        raise DeployError("live inference source revision mismatch")
    if inference.get("state") != "PROPOSAL":
        raise DeployError("live inference is not proposal-only")
    if inference.get("executed") is not False:
        raise DeployError("live inference executed an action")
    if inference.get("authority_state") != "NO_ACTION_AUTHORITY":
        raise DeployError("live inference gained action authority")
    if inference.get("tool_execution") is not False:
        raise DeployError("live inference executed a tool")
    output = inference.get("output")
    if not isinstance(output, str) or not output.strip():
        raise DeployError("live inference returned no output")
    model = inference.get("model") or {}
    if model.get("candidate") not in MODEL_CANDIDATES:
        raise DeployError("live inference model candidate mismatch")
    if model.get("kind") != "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE":
        raise DeployError("live inference model kind mismatch")
    if model.get("owned_model_served") is not False:
        raise DeployError("live inference mislabeled owned model service")
    authority = inference.get("formula_authority") or {}
    if authority.get("locked_proven_ids") != LOCKED_FORMULAS:
        raise DeployError("locked formula identity drift")
    lambda_rule = authority.get("lambda") or {}
    if (
        lambda_rule.get("status") != "CONJECTURE_1_ADVISORY"
        or lambda_rule.get("can_authorize") is not False
    ):
        raise DeployError("live inference Lambda authority drift")
    nemo = inference.get("nemo") or []
    if (
        not isinstance(nemo, list)
        or len(nemo) != 2
        or [row.get("stage") for row in nemo]
        != ["PRE_GENERATION", "POST_GENERATION"]
        or any(row.get("decision") != "ALLOW_PROPOSAL_ONLY" for row in nemo)
    ):
        raise DeployError("live Nemo witness sequence mismatch")
    receipt = inference.get("receipt") or {}
    if receipt.get("schema") != EXPECTED_RECEIPT_SCHEMA:
        raise DeployError("live receipt schema mismatch")
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        raise DeployError("live receipt payload unavailable")
    expected_digest = sha256_text(canonical_json(payload))
    if receipt.get("receipt_sha256") != expected_digest:
        raise DeployError("live receipt digest mismatch")
    if prompt in canonical_json(receipt):
        raise DeployError("raw probe prompt persisted in receipt")
    signature = receipt.get("signature") or {}
    if (
        signature.get("status") != "UNSIGNED_EDGE"
        or signature.get("durable") is not False
        or signature.get("must_be_signed_before_consequential_action") is not True
    ):
        raise DeployError("live receipt honesty boundary mismatch")
    anatomy = inference.get("anatomy_observation") or {}
    event = anatomy.get("event") or {}
    if (
        anatomy.get("delivery") != "DELIVERED_INLINE"
        or anatomy.get("observer_authority") != "NONE"
        or anatomy.get("persistence") != "EPHEMERAL_ISOLATE_NO_DURABLE_BINDING"
        or event.get("raw_prompt_present") is not False
        or event.get("private_reasoning_present") is not False
    ):
        raise DeployError("live Anatomy observation boundary mismatch")
    if inference_headers.get("x-szl-edge") != EDGE_MARKER:
        raise DeployError("live edge marker mismatch")
    if inference_headers.get("x-szl-governed-inference") != "v1":
        raise DeployError("live governed inference header missing")

    return {
        "health": "READY",
        "source_revision": source_revision,
        "model_candidate": model["candidate"],
        "model_kind": model["kind"],
        "output_sha256": inference.get("output_sha256"),
        "receipt_sha256": receipt.get("receipt_sha256"),
        "evidence_handle_count": len(inference.get("evidence_handles") or []),
        "citation_count": len(inference.get("citations") or []),
        "nemo_witness_count": len(nemo),
        "second_brain_state": (inference.get("second_brain") or {}).get("state"),
        "action_authority": False,
        "tool_execution": False,
        "owned_model_served": False,
        "raw_prompt_persisted_in_receipt": False,
    }


def public_probe(
    source_revision: str,
    *,
    health_attempts: int = 24,
) -> dict[str, Any]:
    base = f"https://{ZONE_NAME}"
    last_health: dict[str, Any] = {}
    last_contract: dict[str, Any] = {}
    health_headers: dict[str, str] = {}
    for attempt in range(1, health_attempts + 1):
        observed_health = observation(f"{base}/api/v2/governed-health")
        observed_contract = observation(f"{base}/api/v2/governed-contract")
        last_health = observed_health.get("body") or {}
        last_contract = observed_contract.get("body") or {}
        health_headers = observed_health.get("headers") or {}
        if (
            observed_health.get("status") == 200
            and observed_contract.get("status") == 200
            and last_health.get("status") == "READY"
            and last_health.get("source_revision") == source_revision
            and last_contract.get("source_revision") == source_revision
            and health_headers.get("x-szl-edge") == EDGE_MARKER
        ):
            break
        if attempt == health_attempts:
            raise DeployError(
                "public health did not converge to exact source revision: "
                + canonical_json(
                    {
                        "status": observed_health.get("status"),
                        "health_state": last_health.get("status"),
                        "health_source": last_health.get("source_revision"),
                        "contract_source": last_contract.get("source_revision"),
                        "edge": health_headers.get("x-szl-edge"),
                    }
                )
            )
        time.sleep(min(5, attempt))
    else:  # pragma: no cover
        raise DeployError("public health convergence loop exhausted")

    last_inference: dict[str, Any] = {}
    inference_headers: dict[str, str] = {}
    inference_status: int | None = None
    for inference_attempt in range(1, 4):
        observed = observation(
            f"{base}/api/v2/governed-infer",
            payload={
                "prompt": PROBE_PROMPT,
                "effort": "fast",
                "max_new_tokens": 96,
                "evidence": [
                    {
                        "source": "deployment-live-proof",
                        "text": (
                            "This request is a bounded deployment witness and "
                            "carries no action authority."
                        ),
                    }
                ],
            },
        )
        inference_status = observed.get("status")
        last_inference = observed.get("body") or {}
        inference_headers = observed.get("headers") or {}
        if inference_status == 200:
            break
        if inference_attempt != 3:
            time.sleep(5 * inference_attempt)
    if inference_status != 200:
        raise DeployError(
            "live inference failed: "
            + canonical_json(
                {
                    "status": inference_status,
                    "error": last_inference.get("error"),
                }
            )
        )
    summary = validate_probe_payload(
        last_health,
        last_contract,
        last_inference,
        inference_headers,
        source_revision=source_revision,
    )
    summary["health_attempts"] = attempt
    summary["inference_attempts"] = inference_attempt
    return summary


def route_uses_script(routes: list[dict[str, Any]], name: str) -> bool:
    return any(str(row.get("script") or "") == name for row in routes)


def retire_prior_script(
    account_id: str,
    zone_id: str,
    bearer: str,
    prior_script: str | None,
    target_script: str,
) -> dict[str, Any]:
    if (
        not prior_script
        or prior_script == target_script
        or not prior_script.startswith(SCRIPT_PREFIX)
    ):
        return {"state": "NOT_REQUIRED"}
    routes = fetch_routes(zone_id, bearer)
    if route_uses_script(routes, prior_script):
        return {"state": "RETAINED_REFERENCED", "script": prior_script}
    try:
        delete_worker(account_id, bearer, prior_script)
        return {"state": "DELETED_UNREFERENCED", "script": prior_script}
    except DeployError as exc:
        return {
            "state": "RETAINED_DELETE_FAILED",
            "script": prior_script,
            "error": safe_error(exc, bearer),
        }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bearer, token_source = select_token()
    target_script = ""
    report: dict[str, Any] = {
        "schema": "szl.cloudflare-governed-inference-deployment/v1",
        "status": "FAILED",
        "zone": ZONE_NAME,
        "route_pattern": ROUTE_PATTERN,
        "source_revision": args.source_revision.strip().lower(),
        "worker_source": args.worker.relative_to(ROOT).as_posix()
        if args.worker.is_relative_to(ROOT)
        else str(args.worker),
        "token_source": token_source,
        "token_recorded": False,
        "complete_provider_ids_recorded": False,
        "dns_mutated": False,
        "root_product_worker_mutated": False,
        "ai_binding_requested": True,
        "rollback": {"state": "NOT_REQUIRED"},
    }
    zone_id = ""
    account_id = ""
    plan: dict[str, Any] | None = None
    applied: dict[str, Any] | None = None
    uploaded = False

    try:
        revision = args.source_revision.strip().lower()
        if FULL_SHA_RE.fullmatch(revision) is None:
            raise DeployError("source revision must be an exact lowercase Git SHA")
        if not args.worker.is_file():
            raise DeployError(f"Worker source not found: {args.worker}")
        if not bearer:
            raise DeployError("Cloudflare API token is unavailable")
        target_script = script_name(revision)
        report["target_script"] = target_script
        report["token"] = verify_token(bearer)
        zone_id, account_id = resolve_zone(bearer)
        report["zone_id_suffix"] = zone_id[-6:]
        report["account_id_suffix"] = account_id[-6:]
        routes = fetch_routes(zone_id, bearer)
        plan = route_plan(routes, target_script)
        report["plan"] = public_plan(plan)

        if args.dry_run:
            report["status"] = "DRY_RUN_VERIFIED"
            write_report(args.report, report)
            print(canonical_json(report))
            return 0

        if plan["action"] == "verify-noop":
            report["probe"] = public_probe(revision)
            report["status"] = "LIVE_NOOP"
            write_report(args.report, report)
            print(canonical_json(report))
            return 0

        upload_worker(
            account_id,
            bearer,
            target_script,
            args.worker,
            revision,
        )
        uploaded = True
        report["worker_upload"] = {
            "state": "UPLOADED",
            "script": target_script,
            "ai_binding": "AI",
            "source_revision_binding": revision,
        }
        applied = apply_route_plan(zone_id, bearer, plan)
        report["route_apply"] = {
            "state": applied.get("state"),
            "script": applied.get("script"),
            "pattern": applied.get("pattern"),
            "route_id_suffix": str(applied.get("route_id") or "")[-6:] or None,
        }
        report["probe"] = public_probe(revision)
        report["prior_script_retirement"] = retire_prior_script(
            account_id,
            zone_id,
            bearer,
            plan.get("prior_script"),
            target_script,
        )
        report["status"] = "LIVE"
        write_report(args.report, report)
        print(canonical_json(report))
        return 0
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = safe_error(exc, bearer)
        if plan and zone_id:
            report["rollback"] = rollback_route(
                zone_id,
                bearer,
                plan,
                applied,
            )
        if uploaded and account_id and target_script:
            # Delete only the versioned candidate created by this run. Never
            # delete the exact prior route owner.
            if not plan or target_script != plan.get("prior_script"):
                try:
                    delete_worker(account_id, bearer, target_script)
                    report["candidate_cleanup"] = {
                        "state": "DELETED",
                        "script": target_script,
                    }
                except DeployError as cleanup_error:
                    report["candidate_cleanup"] = {
                        "state": "FAILED",
                        "script": target_script,
                        "error": safe_error(cleanup_error, bearer),
                    }
        write_report(args.report, report)
        print(canonical_json(report))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
