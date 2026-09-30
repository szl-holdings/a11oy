# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Runtime-shipping contracts for the PurIQ v1 browser verifier."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

import serve


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
SERVE = (ROOT / "serve.py").read_text(encoding="utf-8")


def test_puriq_verifier_is_in_runtime_image_and_allowlist() -> None:
    assert "static/shared/puriq_receipt_v1.js" in DOCKERFILE
    assert '"puriq_receipt_v1.js": _VENDOR_JS_CT' in SERVE


def test_puriq_verifier_is_served_as_javascript() -> None:
    response = TestClient(serve.app).get("/static/shared/puriq_receipt_v1.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert "root.PurIQReceiptV1 = api" in response.text


def test_shared_module_route_remains_deny_by_default() -> None:
    response = TestClient(serve.app).get("/static/shared/not-allowlisted.js")

    assert response.status_code == 404
    assert response.json() == {
        "error": "shared module not allowlisted",
        "file": "not-allowlisted.js",
    }


def test_puriq_schema_identifier_resolves_to_immutable_json() -> None:
    assert "schemas/puriq-receipt-v1.json" in DOCKERFILE

    response = TestClient(serve.app).get("/schemas/puriq-receipt-v1.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/schema+json")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.json()["$id"] == (
        "https://a-11-oy.com/schemas/puriq-receipt-v1.json"
    )


def test_schema_route_remains_deny_by_default() -> None:
    response = TestClient(serve.app).get("/schemas/not-allowlisted.json")

    assert response.status_code == 404
    assert response.json() == {
        "error": "schema not allowlisted",
        "file": "not-allowlisted.json",
    }


def test_independent_python_golden_cross_check() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_puriq_receipt_v1_golden.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "puriq-receipt-v1-vectors.json").read_text(
            encoding="utf-8"
        )
    )["canonical_vectors"][0]

    assert fixture["sha256"] in result.stdout
    assert hashlib.sha256(fixture["canonical"].encode("utf-8")).hexdigest() == (
        fixture["sha256"]
    )
