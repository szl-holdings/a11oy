# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_aegis_proof_cells_live.py"

spec = importlib.util.spec_from_file_location("verify_aegis_proof_cells_live", SCRIPT)
assert spec and spec.loader
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def _asset(path: str) -> bytes:
    mapping = {
        "/static/3d/aegis-proof-cells.html": ROOT / "console" / "3d" / "aegis-proof-cells.html",
        "/static/3d/aegis-proof-cells/app.mjs": ROOT / "console" / "3d" / "aegis-proof-cells" / "app.mjs",
        "/static/3d/aegis-proof-cells/styles.css": ROOT / "console" / "3d" / "aegis-proof-cells" / "styles.css",
        "/static/3d/aegis-proof-cells/registry.json": ROOT / "console" / "3d" / "aegis-proof-cells" / "registry.json",
    }
    return mapping[path].read_bytes()


def _fake_request(source_sha: str):
    def request(origin: str, path: str, method: str) -> dict[str, Any]:
        del origin
        if path == "/api/build-info":
            body = json.dumps(
                {"git_sha": source_sha, "source": "env:SZL_GIT_SHA"}
            ).encode()
            content_type = "application/json"
        else:
            body = _asset(path)
            content_type = (
                "application/json"
                if path.endswith(".json")
                else "text/css"
                if path.endswith(".css")
                else "application/javascript"
                if path.endswith(".mjs")
                else "text/html"
            )
        return {
            "url": f"https://example.invalid{path}",
            "method": method,
            "status": 200,
            "headers": {"content-type": content_type},
            "body": b"" if method == "HEAD" else body,
            "elapsed_ms": 1.0,
        }

    return request


def test_live_verifier_accepts_exact_source_bound_assets(monkeypatch) -> None:
    source_sha = "a" * 40
    monkeypatch.setattr(verifier, "_request", _fake_request(source_sha))
    report = verifier.verify_once("https://example.invalid", source_sha)

    assert report["ok"] is True
    assert report["status"] == "PASS"
    assert report["source_sha"] == source_sha
    assert report["observed_source_sha"] == source_sha
    assert report["registry"]["proof_cell_count"] == 11
    assert report["registry"]["procedure_capsule_count"] == 6
    assert report["registry"]["clean_room_classification"] == "REFERENCE_ONLY_CLEAN_ROOM"
    assert report["registry"]["source_code_copied"] is False
    assert report["registry"]["effectors"] == 0
    assert report["authority"]["external_writes"] == "DISABLED"
    assert report["failures"] == []


def test_live_verifier_fails_closed_on_revision_drift(monkeypatch) -> None:
    monkeypatch.setattr(verifier, "_request", _fake_request("b" * 40))
    report = verifier.verify_once("https://example.invalid", "a" * 40)

    assert report["ok"] is False
    assert report["status"] == "FAIL"
    assert any("runtime source mismatch" in failure for failure in report["failures"])


def test_live_verifier_fails_closed_on_missing_clean_room_contract(monkeypatch) -> None:
    source_sha = "c" * 40
    base = _fake_request(source_sha)

    def request(origin: str, path: str, method: str) -> dict[str, Any]:
        result = base(origin, path, method)
        if path.endswith("registry.json") and method == "GET":
            payload = json.loads(result["body"].decode())
            payload["bricklayer_boundary"]["source_code_copied"] = True
            result["body"] = json.dumps(payload).encode()
        return result

    monkeypatch.setattr(verifier, "_request", request)
    report = verifier.verify_once("https://example.invalid", source_sha)

    assert report["ok"] is False
    assert any("reject Bricklayer source copying" in failure for failure in report["failures"])
