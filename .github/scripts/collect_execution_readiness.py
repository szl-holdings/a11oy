#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""GET-only collection of an already admitted, completed canonical export.

No challenge, plan approval, execution, signing, credential creation, provider
configuration, or restart occurs here. Missing independent context fails closed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import szl_execution_readiness as gate

ORIGIN = "https://szlholdings-a11oy.hf.space"
HF_INFO = "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"
EXPORT_PREFIX = "/api/a11oy/v1/series-a/execution-observations/exports/"
MAX_BYTES = 2 * 1024 * 1024


class CollectionBlocked(ValueError):
    pass


def require(value, code):
    if value is not True:
        raise CollectionBlocked(code)


@lru_cache(maxsize=1)
def _relock():
    spec = importlib.util.spec_from_file_location("_execution_collector_relock", ROOT / ".github/scripts/verify_canonical_a11oy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fetch_json(client, url, *, authorization=None, tenant=None):
    allowed = {HF_INFO, ORIGIN + "/api/build-info", ORIGIN + "/api/a11oy/v1/series-a/status",
               ORIGIN + "/api/a11oy/v1/storage/status"}
    export = url.startswith(ORIGIN + EXPORT_PREFIX)
    require(url in allowed or (export and gate.acceptance.HEX64.fullmatch(url[len(ORIGIN + EXPORT_PREFIX):]) is not None),
            "FIXED_READ_ROUTE_REQUIRED")
    headers = {"Accept": "application/json", "Accept-Encoding": "identity", "Cache-Control": "no-store"}
    if authorization is not None or tenant is not None:
        require(export and type(authorization) is str and type(tenant) is str
                and bool(authorization) and bool(tenant)
                and not any(character in authorization + tenant for character in "\r\n"),
                "EXPORT_CREDENTIALS_REQUIRED")
        headers.update(Authorization="Bearer " + authorization, **{"x-a11oy-tenant": tenant})
    deadline = time.monotonic() + 60
    try:
        with client.stream("GET", url, headers=headers, follow_redirects=False) as response:
            require(response.status_code == 200 and str(response.url) == url, "READ_RESPONSE_UNAVAILABLE")
            require(response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json",
                    "READ_JSON_REQUIRED")
            require(response.headers.get("content-encoding", "identity").lower() == "identity", "READ_ENCODING_INVALID")
            declared = response.headers.get("content-length")
            require(declared is None or (declared.isdigit() and 0 < int(declared) <= MAX_BYTES), "READ_SIZE_INVALID")
            raw = bytearray()
            for chunk in response.iter_bytes():
                require(time.monotonic() <= deadline, "READ_DEADLINE_EXCEEDED")
                raw.extend(chunk)
                require(len(raw) <= MAX_BYTES, "READ_SIZE_INVALID")
        require(time.monotonic() <= deadline, "READ_DEADLINE_EXCEEDED")
        require(declared is None or len(raw) == int(declared), "READ_SIZE_MISMATCH")
        require(bool(raw), "READ_BODY_REQUIRED")
        result = gate.acceptance.strict_json(bytes(raw))
        require(type(result) is dict, "READ_OBJECT_REQUIRED")
        return result
    except CollectionBlocked:
        raise
    except Exception:
        # Never copy URLs containing signed material, bodies, tokens or provider
        # exception text into logs or a shared artifact.
        raise CollectionBlocked("READ_TRANSPORT_OR_BODY_UNAVAILABLE") from None


def bracket(client, context):
    hf = fetch_json(client, HF_INFO)
    runtime = hf.get("runtime")
    require(type(runtime) is dict and hf.get("id") == "SZLHOLDINGS/a11oy"
            and hf.get("sha") == runtime.get("sha") == context.runtime_revision
            and runtime.get("stage") == "RUNNING" and hf.get("sdk") == "docker"
            and hf.get("private") is False, "HF_IDENTITY_MISMATCH")
    build = fetch_json(client, ORIGIN + "/api/build-info")
    require(build.get("build", {}).get("revision") == context.source_revision, "SOURCE_IDENTITY_MISMATCH")
    series = fetch_json(client, ORIGIN + "/api/a11oy/v1/series-a/status")
    require(series.get("schema") == "szl.series-a-status/v1"
            and series.get("source_revision") == context.source_revision
            and series.get("runtime_boot_id") == context.runtime_boot_id
            and series.get("signing_key_source") == "persistent:env:SZL_COSIGN_PRIVATE_PEM",
            "PROCESS_IDENTITY_MISMATCH")
    storage = fetch_json(client, ORIGIN + "/api/a11oy/v1/storage/status")
    try:
        _relock().validate_state_store_status(storage)
    except Exception:
        raise CollectionBlocked("FENCED_STORAGE_UNAVAILABLE") from None
    try:
        response = _relock().requests.Response()
        response.status_code = 200
        response.url = ORIGIN + "/api/a11oy/v1/series-a/status"
        response.headers["content-type"] = "application/json"
        response._content = gate.acceptance.canonical(series)
        _relock().validate_route("series_a_status", response, context.source_revision, "SZL_GIT_SHA", ORIGIN,
                                 series_a_database="/tmp/a11oy-state/series-a/control-plane-v2.sqlite3")
    except Exception:
        raise CollectionBlocked("SERIES_A_PERSISTENCE_UNAVAILABLE") from None
    persisted = series.get("storage")
    require(type(persisted) is dict and re.fullmatch(r"store_[0-9a-f]{32}", str(persisted.get("instance_id"))) is not None
            and type(persisted.get("receipt_count")) is int and persisted["receipt_count"] >= 0
            and type(persisted.get("last_receipt_sequence")) is int
            and persisted["last_receipt_sequence"] >= persisted["receipt_count"], "SERIES_A_STORE_IDENTITY_REQUIRED")
    # Clock ages are validated above and naturally advance. Compare exact
    # identity/checkpoint/counter fields, including every registered store.
    return {"source_revision": context.source_revision, "runtime_revision": context.runtime_revision,
            "runtime_boot_id": context.runtime_boot_id, "storage_epoch": storage["epoch"],
            "storage_sequence": storage["lease"]["sequence"],
            "store_snapshots": {name: item["sha16"] for name, item in storage["stores"].items()},
            "series_store_id": persisted["instance_id"], "series_chain_head": persisted.get("chain_head"),
            "series_receipt_count": persisted["receipt_count"],
            "series_last_sequence": persisted["last_receipt_sequence"]}


def validate_current_export(export, context, *, now=None):
    """Validate the exact current producer wrapper and every native observation."""
    gate.acceptance.fields(export, "schema bundle storage_acknowledgment archive_only publication_eligible execution_authorized passive_probe_modified",
                           "INVALID_COMPLETED_EXPORT")
    require(export["schema"] == "szl.execution-observation-export/v1", "EXPORT_SCHEMA_MISMATCH")
    require(export["archive_only"] is False, "CURRENT_BOOT_EXPORT_REQUIRED")
    # Wrapper claims are not used to grant evidence, storage or authority.
    bundle = export["bundle"]
    require(len(gate.acceptance.canonical(bundle)) <= 1024 * 1024, "ARTIFACT_MEMBER_SIZE_INVALID")
    coverage = gate.validate_execution(bundle, context, source=context.source_revision, now=now)
    return bundle, coverage


def collect(client, context, *, operator_token, tenant, now=None):
    gate._context(context, context.source_revision)
    require(type(operator_token) is str and bool(operator_token) and type(tenant) is str and bool(tenant)
            and not any(character in operator_token + tenant for character in "\r\n"),
            "EXISTING_EXPORT_CREDENTIALS_REQUIRED")
    gate.canonical_matrix()  # exact deployed source owns passive coverage scope
    before = bracket(client, context)
    export = fetch_json(client, ORIGIN + EXPORT_PREFIX + context.run_nonce,
                        authorization=operator_token, tenant=tenant)
    bundle, coverage = validate_current_export(export, context, now=now)
    after = bracket(client, context)
    require(before == after, "SOURCE_RUNTIME_OR_STORAGE_CHANGED")
    return bundle, {"schema": "szl.execution-readiness-collection/v1", "method": "GET_ONLY",
                    "collected_at": (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z"),
                    "bracket": before, "bundle_sha256": coverage["bundle_sha256"],
                    "plan_sha256": coverage["plan_sha256"], "passive_probe_modified": False,
                    "execution_authorized": False, "provider_state_changed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--runtime-sha", required=True)
    parser.add_argument("--boot-id", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    try:
        require(all(type(value) is str and bool(value.strip())
                    for value in (args.runtime_sha, args.boot_id, args.run_nonce)),
                "EXECUTION_CONTEXT_REQUIRED")
        import httpx
        pins_raw = os.environ.get("A11OY_EXECUTION_AUTHORITY_PINS_JSON", "")
        require(bool(pins_raw) and len(pins_raw.encode()) <= 16384, "INDEPENDENT_AUTHORITY_PINS_REQUIRED")
        pins = gate.acceptance.strict_json(pins_raw.encode())
        gate.acceptance.fields(pins, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                               "INVALID_AUTHORITY_CONFIGURATION")
        require(pins["schema"] == "szl.execution-authority-pins/v1", "AUTHORITY_SCHEMA_MISMATCH")
        context = gate.acceptance.AdmissionContext(args.source_sha, args.runtime_sha, args.boot_id, args.run_nonce,
            pins["approval_public_pem"].encode(), pins["approval_key_id"],
            pins["runtime_public_pem"].encode(), pins["runtime_key_id"])
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False, trust_env=True) as client:
            bundle, report = collect(client, context, operator_token=os.environ.get("A11OY_CODE_ADMIN_KEY", ""),
                                     tenant=os.environ.get("A11OY_CODE_TENANT", ""))
        folder = Path(args.out_dir)
        folder.mkdir(parents=True, exist_ok=False)
        for name, value in (("execution-observations.json", bundle), ("execution-collection.json", report),
                            ("execution-authority-pins.json", pins)):
            with (folder / name).open("xb") as stream:
                stream.write(gate.acceptance.canonical(value))
        print(json.dumps({"collected": True, "bundle_sha256": report["bundle_sha256"],
                          "execution_authorized": False, "provider_state_changed": False}))
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, CollectionBlocked) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(exc)) else "EXECUTION_EXPORT_COLLECTION_UNAVAILABLE"
        print(json.dumps({"collected": False, "error": code, "execution_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
