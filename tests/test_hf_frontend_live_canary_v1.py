from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_hf_frontend_live_canary_v1.py"
SPEC = importlib.util.spec_from_file_location("hf_frontend_live_canary_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _page_result(**overrides):
    result = {
        "surface": "fixture",
        "viewport": {"width": 390, "height": 844},
        "http_status": 200,
        "load_error": None,
        "page_errors": [],
        "console_errors": [],
        "metrics": {
            "viewport_meta": "width=device-width, initial-scale=1",
            "inner_width": 390,
            "scroll_width": 390,
            "horizontal_overflow": False,
            "undersized_primary_targets": [],
        },
    }
    result.update(overrides)
    return result


def _build_payload(revision: str):
    return {
        "status": "OBSERVED",
        "build": {
            "revision": revision,
            "revision_source": "env:SZL_GIT_SHA",
        },
    }


def test_page_contract_passes_clean_fixture() -> None:
    assert MODULE.evaluate_page_result(_page_result()) == []


def test_page_contract_rejects_overflow_and_undersized_targets() -> None:
    result = _page_result(
        metrics={
            "viewport_meta": "width=device-width, initial-scale=1",
            "inner_width": 390,
            "scroll_width": 430,
            "horizontal_overflow": True,
            "undersized_primary_targets": [
                {"tag": "A", "text": "Open", "width": 36, "height": 30}
            ],
        }
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page_result(result)}
    assert codes == {"HORIZONTAL_OVERFLOW", "PRIMARY_TARGET_UNDERSIZED"}


def test_page_contract_rejects_missing_viewport_and_script_error() -> None:
    result = _page_result(
        page_errors=["ReferenceError: fixture"],
        metrics={
            "viewport_meta": None,
            "inner_width": 390,
            "scroll_width": 390,
            "horizontal_overflow": False,
            "undersized_primary_targets": [],
        },
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page_result(result)}
    assert codes == {"VIEWPORT_META_MISSING", "PAGE_SCRIPT_ERROR"}


def test_identity_contract_accepts_exact_source_and_running_runtime() -> None:
    source = "a" * 40
    hf_sha = "b" * 40
    identity = {
        "organization_deployment": {"source_sha": "c" * 40},
        "a11oy_space_build": _build_payload(source),
        "a11oy_domain_build": _build_payload(source),
        "a11oy_space_metadata": {
            "sha": hf_sha,
            "runtime": {"stage": "RUNNING", "sha": hf_sha},
        },
    }
    assert MODULE.evaluate_identity(identity) == []


def test_identity_contract_rejects_divergence_and_unbound_runtime() -> None:
    identity = {
        "organization_deployment": {},
        "a11oy_space_build": _build_payload("a" * 40),
        "a11oy_domain_build": _build_payload("b" * 40),
        "a11oy_space_metadata": {
            "sha": "c" * 40,
            "runtime": {"stage": "PAUSED", "sha": "d" * 40},
        },
    }
    codes = {failure["code"] for failure in MODULE.evaluate_identity(identity)}
    assert {
        "ORG_SOURCE_REVISION_UNAVAILABLE",
        "DOMAIN_SPACE_SOURCE_DIVERGENCE",
        "HF_RUNTIME_IDENTITY_FAILED",
    }.issubset(codes)


def test_summary_is_fail_closed() -> None:
    clean = _page_result()
    clean["failures"] = []
    summary = MODULE.build_summary([clean], [])
    assert summary["status"] == "PASS"
    blocked = _page_result()
    blocked["failures"] = [{"code": "HORIZONTAL_OVERFLOW"}]
    summary = MODULE.build_summary([blocked], [{"code": "SOURCE"}])
    assert summary["status"] == "BLOCKED"
    assert summary["page_failures"] == 1
    assert summary["identity_failures"] == 1
