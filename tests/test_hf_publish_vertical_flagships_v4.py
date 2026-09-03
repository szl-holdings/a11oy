# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path("scripts/hf_publish_vertical_flagships_v4.py")
WORKFLOW = Path(".github/workflows/hf-publish-vertical-flagships.yml")


def source() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    ast.parse(text)
    return text


def test_v4_keeps_one_runtime_but_six_distinct_domain_interfaces() -> None:
    text = source()
    assert 'PUBLIC_EXPERIENCE_VERSION = "4.0.0"' in text
    assert 'data-szl-domain-experience-v4="true"' in text
    assert '"terra":' in text and "parcel-map" in text and "UNDERWRITING QUEUE" in text
    assert '"sentra":' in text and "attack path graph" in text and "RESPONSE QUEUE" in text
    assert '"counsel":' in text and "AUTHORITY RAIL" in text and "MATTER / WORK PRODUCT" in text
    assert '"finance":' in text and "DECISION TAPE" in text and "STRESS LANES" in text
    assert '"vessels":' in text and "VOYAGE WATCH" in text and "maritime route chart" in text
    assert '"lyte":' in text and "SERVICE GRAPH" in text and "TRACE TIMELINE" in text
    assert text.count('app=FastAPI(title=CFG["title"]+" - SZL Holdings")') == 1


def test_every_vertical_preserves_mobile_accessibility_and_truth_contracts() -> None:
    text = source()
    required = (
        "viewport-fit=cover",
        "--touch:44px",
        "@media(pointer:coarse)",
        "@media(prefers-reduced-motion:reduce)",
        "@media(forced-colors:active)",
        "focus-visible",
        "overflow-wrap:anywhere",
        "MEASURED",
        "REPORTED",
        "MODELED",
        "UNAVAILABLE",
    )
    for fragment in required:
        assert fragment in text


def test_cards_are_license_complete_and_short_descriptions_are_bounded() -> None:
    text = source()
    assert "license: apache-2.0" in text
    assert "short_description:" in text
    assert "tags:" in text
    for phrase in (
        "Parcel-to-portfolio real estate decision intelligence",
        "Evidence-first cyber attack-path and response intelligence",
        "Matter workspace for research, drafting, and verification",
        "Provenance-first financial signal and decision console",
        "Fleet route, risk, and voyage intelligence with receipts",
        "Service, trace, incident, and agent observability command",
    ):
        assert len(phrase) <= 60
        assert phrase in text


def test_build_info_is_census_compatible_and_revision_bound() -> None:
    text = source()
    required = (
        '"schema":"szl.build-info/v1"',
        '"source_repository":CFG["source_repository"]',
        '"source_revision":CFG["source_revision"]',
        '"workflow_run_id":CFG["workflow_run_id"]',
        '"hf_repository":CFG["hf_repository"]',
        '"hf_revision":hf_revision()',
        '"artifact_set_sha256":CFG["artifact_set_sha256"]',
        'DEPLOYMENT_SOURCE_REPOSITORY = "szl-holdings/a11oy"',
        'GITHUB_RUN_ID',
        'GITHUB_SHA',
        '/api/build-info',
        '/.well-known/szl-source.json',
    )
    for fragment in required:
        assert fragment in text


def test_archived_vertical_repositories_remain_out_of_source_links() -> None:
    text = source()
    assert "https://github.com/szl-holdings/counsel" not in text
    assert "https://github.com/szl-holdings/szl-fleet-overlay" not in text
    assert "a11oy/tree/main/verticals/counsel" in text
    assert "a11oy/tree/main/verticals/vessels" in text


def test_owner_dispatch_workflow_points_at_v4_and_protected_main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow
    assert "scripts/hf_publish_vertical_flagships_v4.py" in workflow
    assert 'test "$GITHUB_REF" = refs/heads/main' in workflow
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)"' in workflow
    assert "persist-credentials: false" in workflow
