# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path("scripts/hf_publish_vertical_flagships_v4_impl.py")
ENTRYPOINT = Path("scripts/hf_publish_vertical_flagships_v4.py")
INTELLIGENCE = Path("scripts/hf_publish_vertical_services_intelligence_v4.py")
COMBINED = Path("scripts/hf_publish_vertical_services.py")
WORKFLOW = Path(".github/workflows/hf-publish-vertical-flagships.yml")
SYNC_WORKFLOW = Path(".github/workflows/hf-sync.yml")
TERRA_BUNDLE = Path("deployments/vertical-forge/terra")


def source() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    ast.parse(text)
    return text


def load_implementation():
    spec = importlib.util.spec_from_file_location("szl_hf_flagship_v4_impl_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    fake_hub = ModuleType("huggingface_hub")
    fake_hub.HfApi = type("HfApi", (), {})
    previous = sys.modules.get("huggingface_hub")
    sys.modules["huggingface_hub"] = fake_hub
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("huggingface_hub", None)
        else:
            sys.modules["huggingface_hub"] = previous
    return module


def domain_html() -> dict[str, str]:
    tree = ast.parse(source())
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DOMAIN_HTML"
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("DOMAIN_HTML assignment not found")


def test_v4_renderer_retains_six_domain_templates() -> None:
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


def test_terra_forge_bundle_is_chained_to_exact_merged_source() -> None:
    module = load_implementation()
    page, forge = module.load_terra_forge_bundle()

    assert 'data-szl-vertical-forge="0.2.1"' in page
    assert 'href="/panels"' in page
    assert 'href="/build-receipt.json"' in page
    assert 'const EP="/api/live"' in page
    assert forge == {
        "schema": "szl.vertical-forge.deployment-source/v1",
        "generator": "szl-vertical-forge/0.2.1",
        "source_repository": "szl-holdings/szl-vertical-forge",
        "source_revision": "5febe88a571cd001cdc5e9d7c5073373dd6d480c",
        "source_pull_request": "https://github.com/szl-holdings/szl-vertical-forge/pull/1",
        "fleet_master_hash": "712c20ee1ab8be96b2d8ec7cba120321fb2e2487872c2ce088fce39353e97571",
        "fleet_config_sha256": "4b85cb67e7003cee620119835c91a92e954f3c863fc2faa505b07aeb4a1c2a46",
        "vertical_config_sha256": "c6ba3bd447dafd2bb8dff96d1762718ad392fff121cf04fd64057db5ddac378c",
        "artifact_sha256": "37876f7fef0f1bc18b65b508b2f5c5c78376403435843a6c3edfb63be0c5fd92",
        "chain_hash": "712c20ee1ab8be96b2d8ec7cba120321fb2e2487872c2ce088fce39353e97571",
    }


def test_terra_forge_bundle_fails_closed_after_byte_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_implementation()
    target = tmp_path / "terra"
    shutil.copytree(TERRA_BUNDLE, target)
    index = target / "index.html"
    index.write_text(index.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")
    monkeypatch.setattr(module, "TERRA_FORGE_BUNDLE", target)

    with pytest.raises(RuntimeError, match="artifact_sha256 mismatch"):
        module.load_terra_forge_bundle()


def test_flagship_runtime_exposes_landing_panels_readiness_and_receipt_routes() -> None:
    module = load_implementation()
    ast.parse(module.APP)
    for fragment in (
        'Path("panels.html").read_text(encoding="utf-8")',
        '@app.get("/readyz")',
        '@app.get("/build-receipt.json")',
        '@app.get("/panels",response_class=HTMLResponse)',
        '"schema":"szl.vertical-shell-readiness/v1"',
        '"schema":"szl.vertical-shell-deployment/v1"',
        '"state":"VERIFIED_RUNTIME_ARTIFACTS"',
        'sha256_text(INDEX)==CFG["landing_sha256"]',
        'sha256_text(PANELS)==CFG["panels_sha256"]',
    ):
        assert fragment in module.APP
    assert "COPY app.py config.json index.html panels.html ./" in module.DOCKER
    assert '(("app.py", APP)' in source()
    assert '("panels.html", panels)' in source()


def test_live_admission_requires_both_surfaces_and_matching_forge_receipt() -> None:
    module = load_implementation()
    source_revision = "a" * 40
    workflow_run_id = "12345"
    forge = {"fleet_master_hash": "b" * 64}
    row = {
        "artifact_set_sha256": "c" * 64,
        "landing_sha256": "d" * 64,
        "panels_sha256": "e" * 64,
        "forge": forge,
        "root": {"http_status": 200, "marker_present": True},
        "panels": {"http_status": 200, "marker_present": True},
        "build_info_http": 200,
        "build_info": {
            "schema": "szl.build-info/v1",
            "source_repository": "szl-holdings/a11oy",
            "source_revision": source_revision,
            "workflow_run_id": int(workflow_run_id),
            "artifact_set_sha256": "c" * 64,
            "hf_revision": "f" * 40,
            "forge": forge,
        },
        "readyz_http": 200,
        "readyz": {
            "schema": "szl.vertical-shell-readiness/v1",
            "ready": True,
            "state": "MEASURED",
        },
        "deployment_receipt_http": 200,
        "deployment_receipt": {
            "schema": "szl.vertical-shell-deployment/v1",
            "state": "VERIFIED_RUNTIME_ARTIFACTS",
            "source_revision": source_revision,
            "workflow_run_id": int(workflow_run_id),
            "artifact_set_sha256": "c" * 64,
            "landing_sha256": "d" * 64,
            "panels_sha256": "e" * 64,
            "forge": forge,
        },
    }

    assert module.observation_passes(
        row,
        source_revision=source_revision,
        workflow_run_id=workflow_run_id,
    )
    row["panels"]["marker_present"] = False
    assert not module.observation_passes(
        row,
        source_revision=source_revision,
        workflow_run_id=workflow_run_id,
    )
    row["panels"]["marker_present"] = True
    row["deployment_receipt"]["forge"] = None
    assert not module.observation_passes(
        row,
        source_revision=source_revision,
        workflow_run_id=workflow_run_id,
    )


def test_demo_visuals_have_visible_illustrative_disclosures() -> None:
    templates = domain_html()
    badge = '<span class="illus">Illustrative — schematic, not live data</span>'

    assert templates["terra"].count(badge) == 1
    assert templates["counsel"].count(badge) == 1
    assert templates["finance"].count(badge) == 1
    assert templates["lyte"].count(badge) == 2

    assert 'class="panel parcel-map" aria-label=' in templates["terra"]
    assert 'class="panel matter">' + badge in templates["counsel"]
    assert 'class="tape" aria-label=' in templates["finance"]
    assert 'class="panel services">' + badge in templates["lyte"]
    assert 'class="panel waterfall">' + badge in templates["lyte"]


def test_disclosures_remain_accessible_on_counsel_and_narrow_terra() -> None:
    text = source()
    assert '.illus{color:#5b3a12;border-color:#8b5e34}' in text
    assert '@media(max-width:480px){.parcel-map{min-height:0;display:grid;' in text
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in text
    assert '.parcel-map>.illus{grid-column:1/-1' in text
    assert '.parcel{position:static;min-height:88px}' in text


def test_every_vertical_template_preserves_mobile_accessibility_and_truth_contracts() -> None:
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


def test_entrypoint_publishes_four_spaces_and_folds_two_into_killinchu() -> None:
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    intelligence = INTELLIGENCE.read_text(encoding="utf-8")
    combined = COMBINED.read_text(encoding="utf-8")
    ast.parse(entrypoint)
    ast.parse(intelligence)
    ast.parse(combined)

    for fragment in (
        "hf_publish_vertical_flagships_v4_impl.py",
        "hf_publish_vertical_services.py",
        "hf_publish_vertical_services_intelligence_v4.py",
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte")',
        'FOLDED_INTO_KILLINCHU = ("sentra", "vessels")',
        'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"',
        "constrain_public_flagships",
        "retired Killinchu capability plane reached public writer",
        '"szl.hf-vertical-estate/v7"',
        'flagship["public_flagship_slugs"]',
        'flagship["folded_into_killinchu"]',
        "combined_runtime",
        "ensure_space_secret_reader",
        "backported-metadata-only",
        "secret_values_readable",
    ):
        assert fragment in entrypoint

    for retired in ("sentra", "vessels"):
        assert retired in entrypoint
    assert "api.create_repo" not in entrypoint

    for fragment in (
        'SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"',
        'EXPECTED_VERSION = "2.2.0"',
        '"szl.vertical-intelligence-live-proof/v4"',
        '"caller_supplied_endpoints_allowed": False',
        '"effectors_enabled": False',
    ):
        assert fragment in intelligence

    for fragment in (
        'SOURCE_REPOSITORY = "szl-holdings/vertical-services"',
        'SOURCE_REVISION = "b191c14bf7449a52f1ec3d5959722b396af7fddd"',
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
