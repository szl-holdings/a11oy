#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Compare A11oy's declared primary model with its explicitly selected provider.

Supply --expected-source-sha and --expected-model-base-url from the reviewed
deployment. GET-only, no credentials, redirects, retries, signing or inference.
Exit 0 means only that the declaration occurs in the bounded provider listing;
it is not model qualification, execution admission or a release-gate verdict.
Taxonomy: services / operator diagnostics.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import httpx

ORIGIN = "https://szlholdings-a11oy.hf.space"
BUILD = ORIGIN + "/api/build-info"
MODELS = ORIGIN + "/api/a11oy/v1/code/models"
MAX_BYTES = 256 * 1024
MAX_MODELS = 256
MAX_SECONDS = 15
SHA40 = re.compile(r"[0-9a-f]{40}")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,191}")
DNS_NAME = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


class CheckBlocked(ValueError):
    pass


def require(condition, code):
    if condition is not True:
        raise CheckBlocked(code)


def model_base(value):
    require(type(value) is str and 0 < len(value) <= 2048
            and not any(char.isspace() or ord(char) < 32 for char in value),
            "EXPLICIT_HTTPS_MODEL_BASE_REQUIRED")
    try:
        parts = urlsplit(value)
        port = parts.port
        host = parts.hostname or ""
    except ValueError:
        raise CheckBlocked("EXPLICIT_HTTPS_MODEL_BASE_REQUIRED") from None
    require(parts.scheme == "https" and bool(host) and port in (None, 443)
            and parts.username is None and parts.password is None
            and "?" not in value and "#" not in value
            and parts.path.rstrip("/") in ("", "/v1"),
            "EXPLICIT_HTTPS_MODEL_BASE_REQUIRED")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        require(DNS_NAME.fullmatch(host) is not None
                and not host.endswith((".localhost", ".local", ".internal")),
                "PUBLIC_MODEL_HOST_REQUIRED")
    else:
        require(address.is_global, "PUBLIC_MODEL_HOST_REQUIRED")
    return value.rstrip("/")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON_INVALID")
        result[key] = value
    return result


def invalid_number(_):
    raise CheckBlocked("JSON_INVALID")


def fetch(client, url, allowed):
    require(client.auth is None and "authorization" not in client.headers
            and "cookie" not in client.headers and not client.cookies,
            "CREDENTIALLED_CLIENT_REFUSED")
    require(url in allowed, "READ_ROUTE_NOT_ADMITTED")
    deadline = time.monotonic() + MAX_SECONDS
    try:
        with client.stream("GET", url, follow_redirects=False, headers={
            "Accept": "application/json", "Accept-Encoding": "identity",
            "Cache-Control": "no-store",
        }) as response:
            require(response.status_code == 200 and str(response.url) == url,
                    "READ_RESPONSE_UNAVAILABLE")
            require(response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    == "application/json", "READ_JSON_REQUIRED")
            require(response.headers.get("content-encoding", "identity").lower() == "identity",
                    "READ_ENCODING_INVALID")
            declared = response.headers.get("content-length")
            require(declared is None or (declared.isdigit() and 0 < int(declared) <= MAX_BYTES),
                    "READ_SIZE_INVALID")
            raw = bytearray()
            for chunk in response.iter_bytes():
                require(time.monotonic() <= deadline, "READ_DEADLINE_EXCEEDED")
                raw.extend(chunk)
                require(len(raw) <= MAX_BYTES, "READ_SIZE_INVALID")
        require(time.monotonic() <= deadline, "READ_DEADLINE_EXCEEDED")
        require(bool(raw) and (declared is None or len(raw) == int(declared)), "READ_SIZE_INVALID")
        value = json.loads(bytes(raw), object_pairs_hook=unique_object, parse_constant=invalid_number)
        require(type(value) is dict, "READ_OBJECT_REQUIRED")
        return value
    except CheckBlocked:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise CheckBlocked("JSON_INVALID") from None
    except Exception:
        # Provider bodies, URLs, proxy details and exception text never enter a report.
        raise CheckBlocked("READ_TRANSPORT_UNAVAILABLE") from None


def source(value, expected):
    build = value.get("build")
    require(type(build) is dict and build.get("revision") == expected, "SOURCE_REVISION_MISMATCH")


def declaration(value, expected_base):
    backend = value.get("backend")
    require(type(backend) is dict and backend.get("configured") is True, "MODEL_NOT_CONFIGURED")
    require(model_base(value.get("endpoint")) == expected_base
            and model_base(backend.get("endpoint")) == expected_base, "MODEL_ENDPOINT_CHANGED")
    model = backend.get("primary_model")
    require(type(model) is str and MODEL_ID.fullmatch(model) is not None, "DECLARED_MODEL_INVALID")
    return model


def listing(value):
    rows = value.get("data")
    require(type(rows) is list and 0 < len(rows) <= MAX_MODELS, "MODEL_LIST_INVALID")
    ids = []
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is str
                and MODEL_ID.fullmatch(row["id"]) is not None, "MODEL_LIST_INVALID")
        ids.append(row["id"])
    require(len(set(ids)) == len(ids), "MODEL_LIST_INVALID")
    return sorted(ids)


def check(client, expected_source, expected_base):
    report = {
        "schema": "szl.model-declaration-check/v1",
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method": "GET_ONLY", "scope": "DECLARED_MODEL_VS_PROVIDER_LISTING",
        "status": "UNAVAILABLE", "declaration_matches_listing": False,
        "source_revision": None, "source_bracket_unchanged": False,
        "inference_verified": False, "weights_verified": False, "hardware_verified": False,
        "production_ready": False, "execution_authorized": False, "provider_state_changed": False,
    }
    stage = "INPUT"
    try:
        require(type(expected_source) is str and SHA40.fullmatch(expected_source) is not None,
                "EXACT_SOURCE_REQUIRED")
        expected_base = model_base(expected_base)
        provider = expected_base + "/models"
        allowed = frozenset((BUILD, MODELS, provider))
        stage = "SOURCE_BEFORE"
        source(fetch(client, BUILD, allowed), expected_source)
        report["source_revision"] = expected_source
        stage = "DECLARATION_BEFORE"
        declared = declaration(fetch(client, MODELS, allowed), expected_base)
        stage = "PROVIDER_LIST"
        models = listing(fetch(client, provider, allowed))
        stage = "DECLARATION_AFTER"
        require(declaration(fetch(client, MODELS, allowed), expected_base) == declared,
                "MODEL_DECLARATION_CHANGED")
        stage = "SOURCE_AFTER"
        source(fetch(client, BUILD, allowed), expected_source)
        report.update(source_bracket_unchanged=True, declared_model_id=declared,
                      advertised_model_ids=models, advertised_model_count=len(models),
                      expected_model_base_url=expected_base)
        matched = declared in models
        report.update(status="DECLARATION_LISTED" if matched else "DECLARED_MODEL_NOT_LISTED",
                      declaration_matches_listing=matched,
                      error=None if matched else "DECLARED_MODEL_NOT_LISTED")
    except CheckBlocked as exc:
        report.update(error=str(exc), failure_stage=stage)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-model-base-url", required=True)
    parser.add_argument("--output", help="New JSON report file; an existing file is never overwritten.")
    args = parser.parse_args(argv)
    with httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False,
                      trust_env=True) as client:
        report = check(client, args.expected_source_sha, args.expected_model_base_url)
    raw = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
    print(raw, end="")
    return 0 if report["declaration_matches_listing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
