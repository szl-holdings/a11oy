# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_aegis_proof_cells_live.py"
WORKFLOW = ROOT / ".github" / "workflows" / "aegis-proof-cells.yml"

spec = importlib.util.spec_from_file_location("verify_aegis_proof_cells_live", SCRIPT)
assert spec and spec.loader
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def _live_proof_enabled(
    event_name: str, conclusion: str, publisher_event: str, head_branch: str
) -> bool:
    """Evaluate the workflow guard for bounded event fixtures without executing code."""
    condition = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"][
        "live-proof"
    ]["if"]
    for field, value in {
        "github.event_name": event_name,
        "github.event.workflow_run.conclusion": conclusion,
        "github.event.workflow_run.event": publisher_event,
        "github.event.workflow_run.head_branch": head_branch,
    }.items():
        condition = condition.replace(field, repr(value))
    condition = " ".join(condition.replace("&&", " and ").replace("||", " or ").split())
    tree = ast.parse(condition, mode="eval")

    def interpret(node: ast.AST) -> str | bool:
        if isinstance(node, ast.Expression):
            return interpret(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
            return interpret(node.left) == interpret(node.comparators[0])
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return all(bool(interpret(value)) for value in node.values)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(bool(interpret(value)) for value in node.values)
        raise AssertionError(f"unexpected live-proof guard syntax: {type(node).__name__}")

    return bool(interpret(tree))


def test_manual_canonical_sync_completion_runs_strict_live_proof() -> None:
    cases = [
        ("workflow_run", "success", "push", "main", True),
        ("workflow_run", "success", "workflow_dispatch", "main", True),
        ("workflow_run", "failure", "workflow_dispatch", "main", False),
        ("workflow_run", "success", "schedule", "main", False),
        ("workflow_run", "success", "workflow_dispatch", "feature", False),
        ("pull_request", "success", "workflow_dispatch", "main", False),
    ]
    for event_name, conclusion, publisher_event, head_branch, expected in cases:
        assert _live_proof_enabled(event_name, conclusion, publisher_event, head_branch) is expected


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
