#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed operational qualification for the canonical SZL HF Space estate.

The manifest is policy, not evidence.  This program obtains fresh Hugging Face API
metadata and fresh application-path responses, then writes a machine-readable
receipt.  It never promotes an UNKNOWN revision, runtime, path, or inference result
to PASS.  A required check that is not evidenced fails its Space; one failed Space
fails the complete estate qualification (there is no majority threshold).
"""

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from szl_spaces_surface import SPACES as CANONICAL_SPACES  # noqa: E402

SCHEMA = "szl.hf-space-operational-manifest/v1"
RECEIPT_SCHEMA = "szl.hf-space-operational-receipt/v1"
UNKNOWN = "UNKNOWN"
_DYNAMIC_SDKS = {"docker", "gradio"}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ContractError(ValueError):
    """The qualification policy does not match the canonical estate contract."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    final_url: str

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class UrllibTransport:
    """Small dependency-free HTTP transport, injectable for offline tests."""

    def request(
        self,
        method: str,
        url: str,
        timeout: float,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        request_headers = {
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "User-Agent": "szl-hf-space-qualification/1.0",
        }
        if headers:
            request_headers.update(headers)
        data = None
        if body is not None:
            data = json.dumps(body, sort_keys=True).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status=int(response.getcode()),
                    headers={k.lower(): v for k, v in response.headers.items()},
                    body=response.read(2 * 1024 * 1024),
                    final_url=response.geturl(),
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                status=int(exc.code),
                headers={k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])},
                body=exc.read(2 * 1024 * 1024),
                final_url=exc.geturl(),
            )


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def _expected_app_url(space: Mapping[str, str]) -> str:
    suffix = ".static.hf.space" if space["sdk"] == "static" else ".hf.space"
    return f"https://szlholdings-{space['slug']}{suffix}"


def validate_manifest(
    manifest: Mapping[str, Any],
    inventory: list[dict[str, str]] | None = None,
) -> None:
    """Validate policy and exact lockstep with ``szl_spaces_surface.SPACES``."""
    canonical = inventory if inventory is not None else CANONICAL_SPACES
    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if manifest.get("organization") != "SZLHOLDINGS":
        errors.append("organization must be SZLHOLDINGS")
    spaces = manifest.get("spaces")
    if not isinstance(spaces, list):
        raise ContractError("spaces must be a list")

    canonical_by_name = {row["name"]: row for row in canonical}
    manifest_names = [row.get("name") for row in spaces if isinstance(row, dict)]
    if len(spaces) != len(canonical) or set(manifest_names) != set(canonical_by_name):
        errors.append(
            "manifest inventory must exactly equal canonical inventory: "
            f"manifest={sorted(str(x) for x in manifest_names)} "
            f"canonical={sorted(canonical_by_name)}"
        )
    if len(manifest_names) != len(set(manifest_names)):
        errors.append("manifest contains duplicate Space names")

    for raw in spaces:
        if not isinstance(raw, dict):
            errors.append("each Space entry must be an object")
            continue
        name = raw.get("name")
        canonical_space = canonical_by_name.get(name)
        if canonical_space is None:
            continue
        prefix = f"spaces[{name}]"
        for field in ("slug", "sdk"):
            if raw.get(field) != canonical_space[field]:
                errors.append(
                    f"{prefix}.{field} must equal canonical {canonical_space[field]!r}"
                )
        if raw.get("repo_id") != f"SZLHOLDINGS/{name}":
            errors.append(f"{prefix}.repo_id does not match canonical repository")
        if raw.get("app_url") != _expected_app_url(canonical_space):
            errors.append(f"{prefix}.app_url does not match canonical SDK host")

        revision = raw.get("exact_revision")
        if not isinstance(revision, dict):
            errors.append(f"{prefix}.exact_revision must be an object")
        else:
            policy = revision.get("policy")
            expected = revision.get("expected")
            if policy not in {"PINNED", "OBSERVE"}:
                errors.append(f"{prefix}.exact_revision.policy must be PINNED or OBSERVE")
            if policy == "PINNED" and (
                not isinstance(expected, str) or not _SHA_RE.fullmatch(expected)
            ):
                errors.append(f"{prefix}.exact_revision.expected must be a 40-char SHA")
            if policy == "OBSERVE" and expected != UNKNOWN:
                errors.append(f"{prefix}.exact_revision.expected must stay UNKNOWN")

        runtime = raw.get("runtime")
        if not isinstance(runtime, dict):
            errors.append(f"{prefix}.runtime must be an object")
        else:
            policy = runtime.get("policy")
            expected = runtime.get("expected_stage")
            if policy not in {"REQUIRED_RUNNING", "OBSERVE"}:
                errors.append(f"{prefix}.runtime.policy is unsupported")
            if canonical_space["sdk"] in _DYNAMIC_SDKS:
                if policy != "REQUIRED_RUNNING" or expected != "RUNNING":
                    errors.append(f"{prefix} dynamic runtime must require RUNNING")
            elif policy == "OBSERVE" and expected != UNKNOWN:
                errors.append(f"{prefix} observed runtime expected_stage must be UNKNOWN")

        paths = raw.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{prefix}.paths must contain at least one required path")
        else:
            seen_paths: set[tuple[str, str]] = set()
            for path_policy in paths:
                if not isinstance(path_policy, dict):
                    errors.append(f"{prefix}.paths entries must be objects")
                    continue
                path = path_policy.get("path")
                method = path_policy.get("method")
                key = (str(method), str(path))
                if key in seen_paths:
                    errors.append(f"{prefix}.paths contains duplicate {method} {path}")
                seen_paths.add(key)
                if method not in {"GET", "HEAD", "POST"}:
                    errors.append(f"{prefix}.paths method {method!r} is unsupported")
                if not isinstance(path, str) or not path.startswith("/"):
                    errors.append(f"{prefix}.paths path must begin with /")
                statuses = path_policy.get("expected_status")
                if not isinstance(statuses, list) or not statuses or not all(
                    isinstance(value, int) for value in statuses
                ):
                    errors.append(f"{prefix}.paths expected_status must be integer list")
                if path_policy.get("required") is not True:
                    errors.append(f"{prefix}.paths must be explicitly required")
                required_keys = path_policy.get("required_json_keys")
                if not isinstance(required_keys, list) or not all(
                    isinstance(value, str) for value in required_keys
                ):
                    errors.append(f"{prefix}.paths required_json_keys must be string list")

        inference = raw.get("inference")
        if not isinstance(inference, dict):
            errors.append(f"{prefix}.inference must be an object")
        else:
            policy = inference.get("policy")
            if policy not in {UNKNOWN, "REQUIRED"}:
                errors.append(f"{prefix}.inference.policy must be UNKNOWN or REQUIRED")
            if policy == UNKNOWN:
                for field in (
                    "path",
                    "method",
                    "request_body",
                    "expected_model",
                    "expected_revision",
                    "response_model_field",
                    "response_revision_field",
                ):
                    if inference.get(field) != UNKNOWN:
                        errors.append(f"{prefix}.inference.{field} must stay UNKNOWN")
            else:
                if inference.get("method") not in {"GET", "POST"}:
                    errors.append(f"{prefix}.inference method is unsupported")
                if not str(inference.get("path", "")).startswith("/"):
                    errors.append(f"{prefix}.inference path must begin with /")
                for field in (
                    "expected_model",
                    "expected_revision",
                    "response_model_field",
                    "response_revision_field",
                ):
                    if inference.get(field) in (None, "", UNKNOWN):
                        errors.append(f"{prefix}.inference.{field} is required")
                keys = inference.get("required_json_keys")
                if not isinstance(keys, list) or not all(isinstance(x, str) for x in keys):
                    errors.append(f"{prefix}.inference.required_json_keys must be string list")

    if errors:
        raise ContractError("; ".join(errors))


def _request_with_retries(
    transport: Any,
    *,
    method: str,
    url: str,
    timeout: float,
    attempts: int,
    sleep_s: float,
    body: Any = None,
) -> tuple[HttpResponse | None, str | None, int]:
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = transport.request(method, url, timeout, body=body)
            if (
                response.status in {408, 425, 429, 500, 502, 503, 504}
                and attempt < attempts
            ):
                if sleep_s > 0:
                    time.sleep(sleep_s)
                continue
            return response, None, attempt
        except Exception as exc:  # noqa: BLE001 - receipt captures transport failure
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < attempts and sleep_s > 0:
                time.sleep(sleep_s)
    return None, last_error or "request not attempted", attempts


def _json_field(data: Any, dotted: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _qualify_space(
    space: Mapping[str, Any],
    transport: Any,
    attempts: int,
    timeout: float,
    sleep_s: float,
) -> dict[str, Any]:
    failures: list[str] = []
    api_url = f"https://huggingface.co/api/spaces/{space['repo_id']}"
    api_response, api_error, api_attempts = _request_with_retries(
        transport,
        method="GET",
        url=api_url,
        timeout=timeout,
        attempts=attempts,
        sleep_s=sleep_s,
    )
    metadata: dict[str, Any] = {}
    metadata_error = api_error
    if api_response is not None:
        if api_response.status == 200:
            try:
                parsed = api_response.json()
                if isinstance(parsed, dict):
                    metadata = parsed
                else:
                    metadata_error = "HF API JSON is not an object"
            except Exception as exc:  # noqa: BLE001
                metadata_error = f"HF API JSON decode failed: {exc}"
        else:
            metadata_error = f"HF API HTTP {api_response.status}"

    observed_revision = metadata.get("sha") if isinstance(metadata.get("sha"), str) else UNKNOWN
    revision_policy = space["exact_revision"]
    if revision_policy["policy"] == "PINNED":
        revision_status = "PASS" if observed_revision == revision_policy["expected"] else "FAIL"
        if revision_status == "FAIL":
            failures.append(
                f"revision expected {revision_policy['expected']} observed {observed_revision}"
            )
    else:
        revision_status = "MEASURED" if observed_revision != UNKNOWN else UNKNOWN

    runtime_obj = metadata.get("runtime") if isinstance(metadata.get("runtime"), dict) else {}
    observed_stage = runtime_obj.get("stage") if isinstance(runtime_obj.get("stage"), str) else UNKNOWN
    runtime_policy = space["runtime"]
    if runtime_policy["policy"] == "REQUIRED_RUNNING":
        runtime_status = "PASS" if observed_stage == runtime_policy["expected_stage"] else "FAIL"
        if runtime_status == "FAIL":
            failures.append(
                f"runtime expected {runtime_policy['expected_stage']} observed {observed_stage}"
            )
    else:
        runtime_status = "MEASURED" if observed_stage != UNKNOWN else UNKNOWN

    path_receipts: list[dict[str, Any]] = []
    for path_policy in space["paths"]:
        url = _join_url(space["app_url"], path_policy["path"])
        response, error, used_attempts = _request_with_retries(
            transport,
            method=path_policy["method"],
            url=url,
            timeout=timeout,
            attempts=attempts,
            sleep_s=sleep_s,
            body=path_policy.get("request_body"),
        )
        receipt: dict[str, Any] = {
            "method": path_policy["method"],
            "path": path_policy["path"],
            "url": url,
            "required": True,
            "attempts": used_attempts,
            "http_status": response.status if response else UNKNOWN,
            "content_type": (
                response.headers.get("content-type", UNKNOWN) if response else UNKNOWN
            ),
            "final_url": response.final_url if response else UNKNOWN,
            "status": "FAIL",
            "error": error or UNKNOWN,
        }
        reason: str | None = None
        if response is None:
            reason = error or "no HTTP response"
        elif response.status not in path_policy["expected_status"]:
            reason = f"HTTP {response.status} not in {path_policy['expected_status']}"
        else:
            expected_ct = path_policy.get("expected_content_type", UNKNOWN)
            observed_ct = response.headers.get("content-type", "")
            if expected_ct != UNKNOWN and expected_ct.lower() not in observed_ct.lower():
                reason = f"content-type {observed_ct or UNKNOWN} does not include {expected_ct}"
            required_keys = path_policy.get("required_json_keys", [])
            if reason is None and required_keys:
                try:
                    payload = response.json()
                    missing = [key for key in required_keys if _json_field(payload, key) is None]
                    if missing:
                        reason = f"missing JSON keys: {', '.join(missing)}"
                except Exception as exc:  # noqa: BLE001
                    reason = f"JSON contract decode failed: {exc}"
        if reason is None:
            receipt["status"] = "PASS"
        else:
            receipt["error"] = reason
            failures.append(f"{path_policy['method']} {path_policy['path']}: {reason}")
        path_receipts.append(receipt)

    inference_policy = space["inference"]
    inference_receipt: dict[str, Any] = {
        "policy": inference_policy["policy"],
        "path": inference_policy["path"],
        "expected_model": inference_policy["expected_model"],
        "expected_revision": inference_policy["expected_revision"],
        "observed_model": UNKNOWN,
        "observed_revision": UNKNOWN,
        "http_status": UNKNOWN,
        "status": UNKNOWN,
        "error": UNKNOWN,
    }
    if inference_policy["policy"] == "REQUIRED":
        inference_url = _join_url(space["app_url"], inference_policy["path"])
        response, error, used_attempts = _request_with_retries(
            transport,
            method=inference_policy["method"],
            url=inference_url,
            timeout=timeout,
            attempts=attempts,
            sleep_s=sleep_s,
            body=inference_policy.get("request_body"),
        )
        inference_receipt.update(
            {"url": inference_url, "attempts": used_attempts, "error": error or UNKNOWN}
        )
        reason = None
        if response is None:
            reason = error or "no inference response"
        elif response.status != 200:
            reason = f"HTTP {response.status}"
            inference_receipt["http_status"] = response.status
        else:
            inference_receipt["http_status"] = response.status
            try:
                payload = response.json()
                missing = [
                    key
                    for key in inference_policy.get("required_json_keys", [])
                    if _json_field(payload, key) is None
                ]
                observed_model = _json_field(
                    payload, inference_policy["response_model_field"]
                )
                observed_revision_value = _json_field(
                    payload, inference_policy["response_revision_field"]
                )
                inference_receipt["observed_model"] = observed_model or UNKNOWN
                inference_receipt["observed_revision"] = observed_revision_value or UNKNOWN
                if missing:
                    reason = f"missing JSON keys: {', '.join(missing)}"
                elif observed_model != inference_policy["expected_model"]:
                    reason = (
                        f"model expected {inference_policy['expected_model']} "
                        f"observed {observed_model or UNKNOWN}"
                    )
                elif observed_revision_value != inference_policy["expected_revision"]:
                    reason = (
                        f"model revision expected {inference_policy['expected_revision']} "
                        f"observed {observed_revision_value or UNKNOWN}"
                    )
            except Exception as exc:  # noqa: BLE001
                reason = f"inference JSON decode failed: {exc}"
        if reason is None:
            inference_receipt["status"] = "PASS"
        else:
            inference_receipt["status"] = "FAIL"
            inference_receipt["error"] = reason
            failures.append(f"inference: {reason}")

    return {
        "name": space["name"],
        "repo_id": space["repo_id"],
        "sdk": space["sdk"],
        "app_url": space["app_url"],
        "hf_api": {
            "url": api_url,
            "http_status": api_response.status if api_response else UNKNOWN,
            "attempts": api_attempts,
            "error": metadata_error or UNKNOWN,
        },
        "exact_revision_receipt": {
            "policy": revision_policy["policy"],
            "expected": revision_policy["expected"],
            "observed": observed_revision,
            "status": revision_status,
            "source": "HF_API",
        },
        "runtime_receipt": {
            "policy": runtime_policy["policy"],
            "expected_stage": runtime_policy["expected_stage"],
            "observed_stage": observed_stage,
            "status": runtime_status,
            "source": "HF_API",
        },
        "path_receipts": path_receipts,
        "inference_receipt": inference_receipt,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def qualify(
    manifest: Mapping[str, Any],
    transport: Any,
    *,
    attempts: int = 2,
    timeout: float = 10.0,
    sleep_s: float = 1.0,
    max_workers: int = 8,
    only: set[str] | None = None,
) -> dict[str, Any]:
    validate_manifest(manifest)
    selected = [
        space for space in manifest["spaces"] if not only or space["name"] in only
    ]
    if only and {space["name"] for space in selected} != only:
        missing = sorted(only - {space["name"] for space in selected})
        raise ContractError(f"unknown --only Space(s): {', '.join(missing)}")
    started = utc_now()
    results_by_name: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _qualify_space, space, transport, attempts, timeout, sleep_s
            ): space["name"]
            for space in selected
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results_by_name[name] = future.result()
            except Exception as exc:  # noqa: BLE001 - per-Space fail-closed receipt
                results_by_name[name] = {
                    "name": name,
                    "status": "FAIL",
                    "failures": [f"unhandled qualification error: {type(exc).__name__}: {exc}"],
                    "exact_revision_receipt": {"status": UNKNOWN},
                    "runtime_receipt": {"status": UNKNOWN},
                    "path_receipts": [],
                    "inference_receipt": {"status": UNKNOWN},
                }
    ordered_results = [results_by_name[space["name"]] for space in selected]
    failed = [row["name"] for row in ordered_results if row["status"] != "PASS"]
    manifest_digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    return {
        "schema": RECEIPT_SCHEMA,
        "claim_scope": "DECLARED_RUNTIME_PATHS_AND_REQUIRED_INFERENCE_ONLY",
        "started_at": started,
        "finished_at": utc_now(),
        "manifest_sha256": manifest_digest,
        "inventory_source": manifest["inventory_source"],
        "inventory_count": len(selected),
        "complete_estate": len(selected) == len(manifest["spaces"]),
        "attempts_per_request": attempts,
        "timeout_seconds": timeout,
        "max_workers": max_workers,
        "overall_status": "PASS" if not failed else "FAIL",
        "passed_spaces": len(ordered_results) - len(failed),
        "failed_spaces": len(failed),
        "failed_space_names": failed,
        "majority_threshold": False,
        "spaces": ordered_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=str(REPO_ROOT / "huggingface" / "space-operational-manifest.json"),
    )
    parser.add_argument("--summary-file", required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args(argv)
    if args.attempts < 1 or args.timeout <= 0 or args.max_workers < 1:
        parser.error("attempts and max-workers must be >=1; timeout must be >0")

    output_path = Path(args.summary_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        manifest = load_manifest(args.manifest)
        receipt = qualify(
            manifest,
            UrllibTransport(),
            attempts=args.attempts,
            timeout=args.timeout,
            sleep_s=args.sleep,
            max_workers=args.max_workers,
            only=set(args.only) or None,
        )
    except Exception as exc:  # noqa: BLE001 - emit refusal receipt when possible
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "claim_scope": "CONTRACT_VALIDATION_ONLY",
            "finished_at": utc_now(),
            "overall_status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "majority_threshold": False,
            "spaces": [],
        }
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "HF Space qualification: "
        f"status={receipt['overall_status']} "
        f"passed={receipt.get('passed_spaces', 0)} "
        f"failed={receipt.get('failed_spaces', 0)} "
        f"receipt={output_path}"
    )
    if receipt.get("failed_space_names"):
        print("Failed Spaces: " + ", ".join(receipt["failed_space_names"]))
    return 0 if receipt["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
