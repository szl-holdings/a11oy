from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_hf_space_frontends_v1.py"
SPEC = importlib.util.spec_from_file_location("hf_space_frontends_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _space(**overrides):
    record = {
        "id": "SZLHOLDINGS/example-space",
        "sha": "a" * 40,
        "sdk": "docker",
        "cardData": {
            "short_description": "Governed example",
        },
        "runtime": {
            "stage": "RUNNING",
            "sha": "a" * 40,
        },
    }
    record.update(overrides)
    return record


def _page(**overrides):
    result = {
        "http_status": 200,
        "load_error": None,
        "console_errors": [],
        "page_errors": [],
        "metrics": {
            "viewport_meta": "width=device-width, initial-scale=1",
            "inner_width": 390,
            "scroll_width": 390,
            "horizontal_overflow": False,
            "primary_targets": 1,
            "undersized_primary_targets": [],
        },
    }
    result.update(overrides)
    return result


def test_space_url_prefers_observed_host() -> None:
    record = _space(host="szlholdings-custom.hf.space")
    assert MODULE.space_url(record) == "https://szlholdings-custom.hf.space/"


def test_space_url_fallback_is_deterministic() -> None:
    record = _space(id="SZLHOLDINGS/Example_Space.v1")
    assert MODULE.space_url(record) == "https://szlholdings-example-space-v1.hf.space/"


def test_metadata_accepts_bound_running_docker_space() -> None:
    assert MODULE.metadata_failures(_space()) == []


def test_metadata_rejects_runtime_and_revision_drift() -> None:
    record = _space(
        runtime={"stage": "PAUSED", "sha": "b" * 40},
        cardData={"short_description": "x" * 61},
        sdk=None,
    )
    codes = {failure["code"] for failure in MODULE.metadata_failures(record)}
    assert {
        "HF_RUNTIME_SHA_DIVERGENT",
        "SPACE_RUNTIME_NOT_RUNNING",
        "SPACE_SDK_UNAVAILABLE",
        "SHORT_DESCRIPTION_TOO_LONG",
    }.issubset(codes)


def test_static_space_requires_app_file() -> None:
    record = _space(sdk="static")
    codes = {failure["code"] for failure in MODULE.metadata_failures(record)}
    assert "APP_FILE_UNAVAILABLE" in codes


def test_organization_card_must_be_static() -> None:
    record = _space(id="SZLHOLDINGS/README", sdk="docker")
    codes = {failure["code"] for failure in MODULE.metadata_failures(record)}
    assert "ORG_CARD_SDK_DIVERGENT" in codes


def test_page_contract_passes_clean_result() -> None:
    assert MODULE.evaluate_page(_page()) == []


def test_page_contract_rejects_fixed_width_and_blank_shell() -> None:
    result = _page(
        metrics={
            "viewport_meta": "width=1024",
            "inner_width": 390,
            "scroll_width": 390,
            "horizontal_overflow": False,
            "primary_targets": 0,
            "undersized_primary_targets": [],
        }
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page(result)}
    assert codes == {"VIEWPORT_META_UNSAFE", "PRIMARY_TARGETS_MISSING"}


def test_browser_probe_counts_only_actionable_in_view_targets() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for contract in (
        "rect.bottom > 0",
        "rect.top < window.innerHeight",
        "Number(style.opacity) <= 0",
        "style.pointerEvents === 'none'",
        "node.hasAttribute('inert')",
        "el.matches(':disabled')",
        "el.getAttribute('aria-disabled') === 'true'",
        "el.getAttribute('role') === 'button' && el.tabIndex >= 0",
        ".filter(actionable)",
    ):
        assert contract in source


def test_page_contract_rejects_hard_viewport_failures() -> None:
    result = _page(
        http_status=500,
        page_errors=["ReferenceError: example"],
        metrics={
            "viewport_meta": None,
            "inner_width": 390,
            "scroll_width": 430,
            "horizontal_overflow": True,
            "primary_targets": 1,
            "undersized_primary_targets": [
                {"tag": "BUTTON", "text": "Run", "width": 36, "height": 32}
            ],
        },
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page(result)}
    assert codes == {
        "HTTP_FAILURE",
        "VIEWPORT_META_MISSING",
        "HORIZONTAL_OVERFLOW",
        "PRIMARY_TARGET_UNDERSIZED",
        "UNCAUGHT_PAGE_ERROR",
    }


def test_console_error_is_retained_but_not_automatically_hard_failed() -> None:
    result = _page(console_errors=[{"type": "error", "text": "optional font blocked"}])
    assert MODULE.evaluate_page(result) == []


def test_repository_and_runtime_sha_helpers_are_fail_closed() -> None:
    record = _space(sha="not-a-sha", runtime={"stage": "RUNNING", "sha": "also-bad"})
    assert MODULE.repository_sha(record) is None
    assert MODULE.runtime_sha(record) is None
    codes = {failure["code"] for failure in MODULE.metadata_failures(record)}
    assert "HF_REPOSITORY_SHA_UNAVAILABLE" in codes
