# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path("scripts/hf_publish_vertical_flagships_v4_impl.py")
ENTRYPOINT = Path("scripts/hf_publish_vertical_flagships_v4.py")
COMBINED = Path("scripts/hf_publish_vertical_services.py")
WORKFLOW = Path(".github/workflows/hf-publish-vertical-flagships.yml")
SYNC_WORKFLOW = Path(".github/workflows/hf-sync.yml")


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
        "GITHUB_RUN_ID",
        "GITHUB_SHA",
        "/api/build-info",
        "/.well-known/szl-source.json",
    )
    for fragment in required:
        assert fragment in text


def test_archived_vertical_repositories_remain_out_of_source_links() -> None:
    text = source()
    assert "https://github.com/szl-holdings/counsel" not in text
    assert "https://github.com/szl-holdings/szl-fleet-overlay" not in text
    assert "a11oy/tree/main/verticals/counsel" in text
    assert "a11oy/tree/main/verticals/vessels" in text


def test_owner_dispatch_and_canonical_automatic_writer_point_at_v4() -> None:
    manual = WORKFLOW.read_text(encoding="utf-8")
    sync = SYNC_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in manual
    assert "\n  push:" not in manual
    assert "scripts/hf_publish_vertical_flagships_v4.py" in manual
    assert 'test "$GITHUB_REF" = refs/heads/main' in manual
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)"' in manual
    assert "persist-credentials: false" in manual

    for fragment in (
        "publish-vertical-flagships:",
        "needs: deploy",
        "Publish and live-verify six domain-native flagship Spaces",
        "scripts/hf_publish_vertical_flagships_v4.py",
        "hf-vertical-flagships-${{ github.run_id }}-${{ github.run_attempt }}",
        "huggingface_hub==1.10.1",
        "ref: ${{ github.sha }}",
        "persist-credentials: false",
    ):
        assert fragment in sync


def test_single_writer_entrypoint_adds_source_bound_combined_runtime() -> None:
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    combined = COMBINED.read_text(encoding="utf-8")
    ast.parse(entrypoint)
    ast.parse(combined)

    for fragment in (
        "hf_publish_vertical_flagships_v4_impl.py",
        "hf_publish_vertical_services.py",
        "combined_runtime",
        "szl.hf-vertical-estate/v5",
        "ensure_space_secret_reader",
        "backported-metadata-only",
        "secret_values_readable",
    ):
        assert fragment in entrypoint

    for fragment in (
        'SOURCE_REPOSITORY = "szl-holdings/vertical-services"',
        'SOURCE_REVISION = "dfc16a3c89e0b4bc070dc7e8ae2415e9bcb04eab"',
        'EXPECTED_VERSION = "2.0.0"',
        'HF_REPOSITORY = "SZLHOLDINGS/vertical-services"',
        'SIGNING_SECRET = "SENTRA_SIGNING_KEY"',
        'CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"',
        'CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"',
        '"--require-default-branch-tip"',
        '"--restart-space"',
        '"--attest"',
        '"/readyz"',
        '"/api/build-info"',
        '"OBSERVED"',
        "vessels_space_retained",
    ):
        assert fragment in combined

    assert "delete_repo" not in combined
    assert "delete_space" not in combined


def test_combined_runtime_v2_closes_operational_fabric_contract() -> None:
    combined = COMBINED.read_text(encoding="utf-8")
    required = (
        "CANONICAL_VERTICALS",
        '"killinchu"',
        '"/killinchu/healthz"',
        '"/vessels/healthz"',
        '"/api/verticals"',
        '"/api/verticals/sentra/anatomy"',
        '"/api/verticals/lyte/formulas"',
        '"/api/verticals/killinchu/connectors"',
        '"source_bound"',
        '"observation_store_writable"',
        '"required_connector_contracts_ready"',
        '"persistent_signing_key"',
        '"formula_registry_bound"',
        '"official_source_connectors_wired"',
        '"vessels_canonical_home"',
        '"SZLHOLDINGS/killinchu"',
        '"effectors_enabled"',
        '"receipt_minted"',
        '"szl.vertical-catalog/v2"',
        '"szl.hf-vertical-services-publication/v2"',
    )
    for fragment in required:
        assert fragment in combined


def test_combined_runtime_executes_six_bounded_live_source_probes() -> None:
    combined = COMBINED.read_text(encoding="utf-8")
    for fragment in (
        '("sentra", "cisa-kev", {"limit": 3})',
        '("lyte", "github-actions", {"repository": "vertical-services", "limit": 10})',
        '("killinchu", "noaa-ais-2025", {})',
        '("finance", "sec-submissions", {"cik": "320193", "limit": 3})',
        '("terra", "nyc-pluto", {"borough": "MN", "limit": 1})',
        '("counsel", "federal-register", {"limit": 3})',
        '"force_refresh": True',
        '"X-SZL-Session"',
        '"session_token_recorded": False',
        '"payload_sha256"',
        '"receipt_id"',
        '"live_connector_probe"',
        '"live_observations"',
    ):
        assert fragment in combined

    assert "caller_supplied_urls" not in combined
    assert "session_token_recorded\": True" not in combined
