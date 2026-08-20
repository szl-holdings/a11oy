from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_hf_frontend_live_canary_v1.py"
WORKFLOW = ROOT / ".github" / "workflows" / "hf-frontend-live-canary-v1.yml"
LANDING = ROOT / "a11oy_landing.html"
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
            "primary_targets": 1,
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


def _organization_deployment(revision: str):
    return {
        "schema": "szl.hf-static-deployment/v1",
        "source": {
            "repository": "szl-holdings/.github",
            "manifest": "huggingface/org-card.manifest.json",
            "revision": revision,
        },
        "target": {
            "repo_id": "SZLHOLDINGS/README",
            "repo_type": "space",
            "live_base_url": "https://szlholdings-readme.static.hf.space",
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
            "primary_targets": 1,
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
            "primary_targets": 1,
            "undersized_primary_targets": [],
        },
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page_result(result)}
    assert codes == {"VIEWPORT_META_MISSING", "PAGE_SCRIPT_ERROR"}


def _space_metadata(
    revision: str,
    stage: str = "RUNNING",
    *,
    include_runtime_sha: bool = True,
    space_id: str = "SZLHOLDINGS/a11oy",
    sdk: str = "docker",
):
    runtime = {"stage": stage}
    if include_runtime_sha:
        runtime["sha"] = revision
    return {
        "id": space_id,
        "sha": revision,
        "sdk": sdk,
        "runtime": runtime,
    }


def test_page_contract_rejects_fixed_width_and_blank_shell() -> None:
    result = _page_result(
        metrics={
            "viewport_meta": "width=1024",
            "inner_width": 390,
            "scroll_width": 390,
            "horizontal_overflow": False,
            "primary_targets": 0,
            "undersized_primary_targets": [],
        }
    )
    codes = {failure["code"] for failure in MODULE.evaluate_page_result(result)}
    assert codes == {"VIEWPORT_META_UNSAFE", "PRIMARY_TARGETS_MISSING"}


def test_identity_contract_accepts_exact_source_and_running_runtime() -> None:
    source = "a" * 40
    hf_sha = "b" * 40
    org_sha = "c" * 40
    identity = {
        "organization_deployment": _organization_deployment(org_sha),
        "a11oy_space_build": _build_payload(source),
        "a11oy_domain_build": _build_payload(source),
        "a11oy_space_metadata": _space_metadata(hf_sha),
        "organization_space_metadata": _space_metadata(
            org_sha,
            include_runtime_sha=False,
            space_id="SZLHOLDINGS/README",
            sdk="static",
        ),
    }
    assert MODULE.evaluate_identity(identity, source) == []


def test_identity_contract_rejects_equal_but_stale_source() -> None:
    expected = "f" * 40
    stale = "a" * 40
    identity = {
        "organization_deployment": _organization_deployment("c" * 40),
        "a11oy_space_build": _build_payload(stale),
        "a11oy_domain_build": _build_payload(stale),
        "a11oy_space_metadata": _space_metadata("b" * 40),
        "organization_space_metadata": _space_metadata(
            "c" * 40,
            include_runtime_sha=False,
            space_id="SZLHOLDINGS/README",
            sdk="static",
        ),
    }
    codes = {
        failure["code"] for failure in MODULE.evaluate_identity(identity, expected)
    }
    assert {"SPACE_SOURCE_BINDING_FAILED", "DOMAIN_SOURCE_BINDING_FAILED"}.issubset(codes)


def test_identity_contract_rejects_divergence_and_unbound_runtime() -> None:
    identity = {
        "organization_deployment": {},
        "a11oy_space_build": _build_payload("a" * 40),
        "a11oy_domain_build": _build_payload("b" * 40),
        "a11oy_space_metadata": {
            "sha": "c" * 40,
            "runtime": {"stage": "PAUSED", "sha": "d" * 40},
        },
        "organization_space_metadata": _space_metadata(
            "e" * 40,
            stage="PAUSED",
            include_runtime_sha=False,
            space_id="SZLHOLDINGS/README",
            sdk="static",
        ),
    }
    codes = {
        failure["code"]
        for failure in MODULE.evaluate_identity(identity, "a" * 40)
    }
    assert {
        "ORG_DEPLOYMENT_IDENTITY_FAILED",
        "DOMAIN_SPACE_SOURCE_DIVERGENCE",
        "HF_RUNTIME_IDENTITY_FAILED",
        "ORG_HF_RUNTIME_IDENTITY_FAILED",
    }.issubset(codes)


def test_organization_deployment_rejects_unrelated_sha() -> None:
    payload = {"unrelated": {"cache_key": "b" * 40}}
    assert MODULE._organization_deployment_revision(payload) is None


def test_workflow_binds_canary_to_exact_github_sha() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert '--expected-source-sha "$EXPECTED_SOURCE_SHA"' in workflow
    assert workflow.count("- a11oy_landing.html") == 1
    assert "workflows: [\"Sync and Relock Canonical Hugging Face Space\"]" in workflow
    assert "github.event.workflow_run.head_sha" in workflow
    assert "ref: ${{ env.EXPECTED_SOURCE_SHA }}" in workflow
    assert workflow.count("git/ref/heads/main") == 2
    assert "\n  push:\n" not in workflow
    assert 'issue_output="$(gh issue list' in workflow
    assert "mapfile -t issue_matches < <(" not in workflow
    assert 'gh issue reopen "$number" --repo "$GITHUB_REPOSITORY" || true' not in workflow
    assert '--comment "All live viewport' in workflow
    assert 'actions/runs/${GITHUB_RUN_ID}." || true' not in workflow


def test_measured_frontdoor_targets_have_minimum_touch_height() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    assert ".nav nav a{display:inline-flex;align-items:center;min-height:44px" in landing
    assert "#fw-hash-btn{display:inline-flex;align-items:center;min-height:44px}" in landing


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
