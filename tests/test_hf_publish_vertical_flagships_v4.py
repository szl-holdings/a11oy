# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from urllib.error import HTTPError
from html.parser import HTMLParser
import shutil
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPT = Path("scripts/hf_publish_vertical_flagships_v4_impl.py")
BASE_SCRIPT = Path("scripts/_hf_publish_vertical_flagships_v4_impl_base.py")
ENTRYPOINT = Path("scripts/hf_publish_vertical_flagships_v4.py")
INTELLIGENCE = Path("scripts/hf_publish_vertical_services_intelligence_v4.py")
COMBINED = Path("scripts/hf_publish_vertical_services.py")
WORKFLOW = Path(".github/workflows/hf-publish-vertical-flagships.yml")
SYNC_WORKFLOW = Path(".github/workflows/hf-sync.yml")
PUBLIC_VERIFY = Path("szl_public_verify.py")
TERRA_BUNDLE = Path("deployments/vertical-forge/terra")
SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"
# Explicit reviewed exception to the immutable renderer's historical runtime.
# Independent pins prevent changing both a producer and a mutable alias from
# silently qualifying arbitrary image/dependency changes. The baseline is
# PURIQ 91717976275b685bef5f6ba9caa40b43fc1efff5; these are generated-file hashes,
# not a signature or a fresh vulnerability-database clearance.
REVIEWED_DOCKER_SHA256 = "7184015f0d0c58f58a67ade27d71e40a6b2f7ca1d6af670794d2dc9da4cc516e"
REVIEWED_REQUIREMENTS_SHA256 = "a68dadf1194259c52c37c9fa52bde3ecd48ffc1c69bf1addfe8cfe43442cd351"


def assert_reviewed_runtime(module) -> None:
    assert hashlib.sha256(module.DOCKER.encode("utf-8")).hexdigest() == REVIEWED_DOCKER_SHA256
    assert hashlib.sha256(module.REQ.encode("utf-8")).hexdigest() == REVIEWED_REQUIREMENTS_SHA256


def source(path: Path = SCRIPT) -> str:
    text = path.read_text(encoding="utf-8")
    ast.parse(text)
    return text


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
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


def load_overlay():
    return load_module("szl_hf_flagship_v4_overlay_test", SCRIPT)


def load_base():
    return load_module("szl_hf_flagship_v4_base_test", BASE_SCRIPT)


def test_generated_hub_commit_title_binds_exact_source(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_overlay()
    assert module._BASE.upload_text is module.upload_text
    calls = []

    class FakeHub:
        def upload_file(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(oid="b" * 40)

    source_revision = "a" * 40
    monkeypatch.setenv("GITHUB_SHA", source_revision)
    module.upload_text(FakeHub(), "SZLHOLDINGS/sentra", "README.md", "# Sentra\n")
    assert calls == [{
        "path_or_fileobj": b"# Sentra\n",
        "path_in_repo": "README.md",
        "repo_id": "SZLHOLDINGS/sentra",
        "repo_type": "space",
        "commit_message": (
            "feat(domain-v4): publish README.md from "
            f"szl-holdings/a11oy@{source_revision}"
        ),
    }]
    monkeypatch.setenv("GITHUB_SHA", "not-a-revision")
    with pytest.raises(RuntimeError, match="exact 40-hex GITHUB_SHA"):
        module.upload_text(FakeHub(), "SZLHOLDINGS/sentra", "README.md", "# Sentra\n")
    assert len(calls) == 1


def by_slug(module) -> dict[str, dict]:
    return {row["slug"]: row for row in module.FLAGSHIPS}


def test_overlay_and_immutable_base_compile() -> None:
    overlay = source(SCRIPT)
    base = source(BASE_SCRIPT)
    assert "SENTRA_OVERLAY_VERSION = \"receipt-verifier/v1\"" in overlay
    assert "Publish six source-bound" in base
    assert "exec(" not in overlay
    assert "eval(" not in overlay


def test_overlay_changes_only_declared_sentra_and_finance_contracts() -> None:
    base = load_base()
    overlay = load_overlay()
    base_rows = by_slug(base)
    overlay_rows = by_slug(overlay)

    assert set(base_rows) == set(overlay_rows) == {
        "terra", "sentra", "counsel", "finance", "vessels", "lyte"
    }
    for slug in set(base_rows) - {"sentra", "finance"}:
        assert overlay_rows[slug] == base_rows[slug]
    for slug in set(base_rows) - {"sentra", "finance"}:
        assert overlay.DOMAIN_CSS[slug] == base.DOMAIN_CSS[slug]
        assert overlay.DOMAIN_HTML[slug] == base.DOMAIN_HTML[slug]

    # Finance has one exact reviewed presentation addition; every other
    # product remains byte-identical except the existing Sentra overlay.
    workspace = load_module("szl_finance_workspace_contract", Path("scripts/hf_finance_workspace.py"))
    assert hashlib.sha256(workspace.HTML.encode()).hexdigest() == "a7614cc33d459131988bc0523f488c91524286273ea7cef4226e8979b2767a33"
    assert hashlib.sha256(workspace.CSS.encode()).hexdigest() == "74f10839de99d1d40ebb793f76e5399645c130b8326731e6f2d13a86214b69fd"
    assert overlay.DOMAIN_HTML["finance"] == workspace.HTML
    assert overlay.DOMAIN_CSS["finance"] == base.DOMAIN_CSS["finance"] + workspace.CSS

    # Finance changes only two explicit bindings; other metadata and sibling visual
    # templates stay equal to the immutable renderer. This is not a wildcard
    # exception for finance changes or permission for another publisher.
    assert overlay_rows["finance"] == {
        **base_rows["finance"],
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/puriq-markets",
        "upstream": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/overview",
    }
    # Shared livebar probe is REACHABLE on HTTP success. Restore the historical
    # LIVE mapper only to prove the finance suffix is still the sole APP addition.
    restored_app = overlay.APP.replace(
        '{"status":"REACHABLE" if r.is_success else "UNAVAILABLE",'
        '"honesty":"HTTP success is reachability, not MEASURED","receipt_verified":False,',
        '{"status":"LIVE" if r.is_success else "UNAVAILABLE",',
        1,
    )
    # /healthz is process-scoped with a computed `ok`; restore the historical
    # constant handler for the same byte-identity proof.
    assert overlay.APP.count(overlay._HEALTHZ_PROCESS_SCOPED) == 1
    restored_app = restored_app.replace(
        overlay._HEALTHZ_PROCESS_SCOPED, overlay._HEALTHZ_CONSTANT, 1
    )
    assert restored_app.startswith(base.APP)
    addition = restored_app[len(base.APP):]
    assert 'if CFG.get("slug") == "finance":' in addition
    assert 'CANONICAL_REVISION_MISMATCH' in addition
    assert 'USE_PRIVATE_CANONICAL_SOURCE_ENDPOINT' in addition
    # Only the independently pinned, reviewed runtime change is admitted.
    # The immutable base, metadata and visual isolation checks above remain.
    assert_reviewed_runtime(overlay)

    assert overlay_rows["sentra"] != base_rows["sentra"]
    assert overlay.DOMAIN_CSS["sentra"] != base.DOMAIN_CSS["sentra"]
    assert overlay.DOMAIN_HTML["sentra"] != base.DOMAIN_HTML["sentra"]


def test_sentra_binds_to_read_only_public_receipt_verifier() -> None:
    module = load_overlay()
    sentra = by_slug(module)["sentra"]
    assert sentra == {
        "slug": "sentra",
        "title": "CHAPAQ",
        "vertical": "ASSURANCE COMMAND",
        "short": "Public receipt verification and assurance evidence",
        "source": (
            "https://github.com/szl-holdings/a11oy/blob/main/"
            "scripts/hf_publish_vertical_flagships_v4_impl.py"
        ),
        "upstream": (
            "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
        ),
        "workflow": ("RECEIPT", "SIGNATURE", "DIGEST", "CHAIN", "VERDICT"),
        "lens": "receipt",
        "labels": ("Verifier contract", "Integrity checks", "Evidence verdict"),
    }
    panel = module.DOMAIN_HTML["sentra"]
    assert "receipt verification graph" in panel
    assert "VERIFICATION EVIDENCE QUEUE" in panel
    assert "PASS requires an actual caller-supplied receipt" in panel
    assert "performs no admission or approval" in panel
    assert "vert/cyber/feed" not in sentra["upstream"]


def test_sentra_verifier_handoff_is_fixed_navigation_with_explicit_trust_scope() -> None:
    module = load_overlay()
    rendered = module.html(by_slug(module)["sentra"])

    class HandoffParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "a" and values.get("id") == "sentra-open-verifier":
                self.links.append(values)

    parser = HandoffParser()
    parser.feed(rendered)
    assert len(parser.links) == 1
    link = parser.links[0]
    assert link["href"] == "https://szlholdings-a11oy.hf.space/verify"
    assert set(link["rel"].split()) == {"noopener", "noreferrer"}
    assert link["target"] == "_blank"
    assert not any(name.startswith("on") for name in link)

    start = rendered.index('<section id="sentra-verifier-handoff"')
    end = rendered.index("</section>", start) + len("</section>")
    handoff = rendered[start:end]
    assert "Offline checks run in your browser" in handoff
    assert "Online checks require a separate explicit action" in handoff
    assert "Runtime keys are REPO_DECLARED until pinned out of band" in handoff
    assert "Independent validation: UNKNOWN" in handoff
    assert "output truth, signer authority, authorization, admission, approval" in handoff
    for forbidden in ("<script", "<form", "<iframe", "prefetch", "preload", "envelope=", "receipt="):
        assert forbidden not in handoff
    assert 'data-iris="closed"' in rendered
    assert "root.dataset.iris='closed'" in rendered
    for slug in {row["slug"] for row in module.FLAGSHIPS} - {"sentra"}:
        assert 'id="sentra-open-verifier"' not in module.html(by_slug(module)[slug])


def test_public_verifier_manifest_is_a_real_read_only_route() -> None:
    verifier = PUBLIC_VERIFY.read_text(encoding="utf-8")
    ast.parse(verifier)
    assert '"schema": "szl.public-receipt-verifier/manifest/v1"' in verifier
    assert "_verify_manifest" in verifier
    assert 'methods=["GET"]' in verifier
    assert 'f"{p}/receipt"' in verifier


def test_terra_forge_0_2_2_remains_exact_and_chained() -> None:
    module = load_overlay()
    page, forge = module.load_terra_forge_bundle()

    assert module.TERRA_FORGE_MARKER == 'data-szl-vertical-forge="0.2.2"'
    assert module.TERRA_FORGE_GENERATOR == "szl-vertical-forge/0.2.2"
    assert 'data-szl-vertical-forge="0.2.2"' in page
    assert 'href="/panels"' in page
    assert 'href="/build-receipt.json"' in page
    assert 'const EP="/api/live"' in page
    assert forge == {
        "schema": "szl.vertical-forge.deployment-source/v1",
        "generator": "szl-vertical-forge/0.2.2",
        "source_repository": "szl-holdings/szl-vertical-forge",
        "source_revision": "6a05a17004d245f929176e01e29b20a0ab0e8bb3",
        "source_pull_request": (
            "https://github.com/szl-holdings/szl-vertical-forge/pull/3"
        ),
        "fleet_master_hash": (
            "26f1316c4c15886ebbb80cd625bc92d741dce83f4ccff02ce04eaefa4c03e34f"
        ),
        "fleet_config_sha256": (
            "4b85cb67e7003cee620119835c91a92e954f3c863fc2faa505b07aeb4a1c2a46"
        ),
        "vertical_config_sha256": (
            "c6ba3bd447dafd2bb8dff96d1762718ad392fff121cf04fd64057db5ddac378c"
        ),
        "artifact_sha256": (
            "3970b3ac1065db1c531d141d3d0aa7ae1903546d6b10197b6f03794d72bca5c4"
        ),
        "chain_hash": (
            "26f1316c4c15886ebbb80cd625bc92d741dce83f4ccff02ce04eaefa4c03e34f"
        ),
    }


def test_terra_forge_fails_closed_after_byte_tampering(
    tmp_path: Path,
) -> None:
    module = load_overlay()
    target = tmp_path / "terra"
    shutil.copytree(TERRA_BUNDLE, target)
    index = target / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8") + "\nTAMPERED\n",
        encoding="utf-8",
    )
    module.TERRA_FORGE_BUNDLE = target
    with pytest.raises(RuntimeError, match="artifact_sha256 mismatch"):
        module.load_terra_forge_bundle()


def test_entrypoint_constraining_propagates_into_base_main() -> None:
    module = load_overlay()
    module.FLAGSHIPS = (by_slug(module)["terra"],)
    module._BASE.main = lambda: len(module._BASE.FLAGSHIPS)
    assert module.main() == 1
    assert tuple(row["slug"] for row in module._BASE.FLAGSHIPS) == ("terra",)


def test_runtime_routes_integrity_and_build_receipt_contract_survive() -> None:
    module = load_overlay()
    ast.parse(module.APP)
    for fragment in (
        'Path("panels.html").read_text(encoding="utf-8")',
        '@app.get("/readyz")',
        '@app.get("/api/live")',
        '@app.get("/api/source")',
        '@app.get("/api/build-info")',
        '@app.get("/build-receipt.json")',
        '@app.get("/.well-known/szl-source.json")',
        '@app.get("/panels",response_class=HTMLResponse)',
        '"schema":"szl.vertical-shell-readiness/v1"',
        '"schema":"szl.vertical-shell-deployment/v1"',
        '"state":"VERIFIED_RUNTIME_ARTIFACTS"',
        'sha256_text(INDEX)==CFG["landing_sha256"]',
        'sha256_text(PANELS)==CFG["panels_sha256"]',
    ):
        assert fragment in module.APP
    assert "COPY app.py config.json index.html panels.html ./" in module.DOCKER


def test_observation_admission_still_requires_every_bound_surface() -> None:
    module = load_overlay()
    revision = "a" * 40
    run_id = "12345"
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
            "source_revision": revision,
            "workflow_run_id": int(run_id),
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
            "source_revision": revision,
            "workflow_run_id": int(run_id),
            "artifact_set_sha256": "c" * 64,
            "landing_sha256": "d" * 64,
            "panels_sha256": "e" * 64,
            "forge": forge,
        },
    }
    assert module.observation_passes(
        row, source_revision=revision, workflow_run_id=run_id
    )
    row["panels"]["marker_present"] = False
    assert not module.observation_passes(
        row, source_revision=revision, workflow_run_id=run_id
    )


def test_mobile_accessibility_and_truth_tokens_remain_in_base() -> None:
    module = load_overlay()
    combined = module.BASE_CSS + "\n".join(module.DOMAIN_CSS.values())
    for fragment in (
        "viewport-fit=cover",
        "--touch:44px",
        "@media(pointer:coarse)",
        "@media(prefers-reduced-motion:reduce)",
        "@media(forced-colors:active)",
        "focus-visible",
        "overflow-wrap:anywhere",
    ):
        assert fragment in source(BASE_SCRIPT) or fragment in combined
    rendered = module.html(by_slug(module)["sentra"])
    for state in ("MEASURED", "REPORTED", "MODELED", "UNAVAILABLE"):
        assert state in rendered


def test_cards_are_complete_and_descriptions_remain_bounded() -> None:
    module = load_overlay()
    for row in module.FLAGSHIPS:
        card = module.readme(row)
        assert "license: apache-2.0" in card
        assert "short_description:" in card
        assert "tags:" in card
        assert row["short"] in card
        assert len(row["short"]) <= 60


def test_entrypoint_preserves_current_topology_and_lyte_source_resolution() -> None:
    entrypoint = source(ENTRYPOINT)
    intelligence = source(INTELLIGENCE)
    combined = source(COMBINED)
    for fragment in (
        "hf_publish_vertical_flagships_v4_impl.py",
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance", "lyte")',
        'GENERATED_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance")',
        'SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)',
        'lyte_receipt_is_complete(lyte)',
        'FOLDED_INTO_KILLINCHU = ("vessels",)',
        'KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"',
        'SENTRA_SPACE = "SZLHOLDINGS/sentra"',
        "constrain_public_flagships",
        "install_existing_space_guard()",
        '"szl.hf-vertical-estate/v8"',
        "ensure_space_secret_reader",
        "secret_values_readable",
    ):
        assert fragment in entrypoint
    assert "api.create_repo" not in entrypoint
    assert '"caller_supplied_endpoints_allowed": False' in intelligence
    assert '"effectors_enabled": False' in intelligence
    assert 'SOURCE_REPOSITORY = "szl-holdings/vertical-services"' in combined


def test_canonical_workflows_still_use_exact_tested_source() -> None:
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
        "needs: [source-admission, deploy]",
        "scripts/hf_publish_vertical_flagships_v4.py",
        "ref: ${{ github.sha }}",
        "persist-credentials: false",
    ):
        assert fragment in sync
    vertical = sync.split("  publish-vertical-flagships:", 1)[1].split(
        "\n  readiness-verdict:", 1
    )[0]
    assert "needs: [source-admission, deploy]" in vertical
    assert "if: ${{ needs.source-admission.outputs.publish == 'true' && needs.deploy.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships }}" in vertical
    assert "run_attempt == 1" not in vertical
    assert "steps.exact_main_owner.outputs.publish == 'true' && steps.vertical_plan.outputs.vertical_flagships == 'true'" in vertical
    assert 'test "$GITHUB_REF" = refs/heads/main' in sync
    assert "require-default-branch-tip: true" in sync
    assert "        default: false" in sync


def test_archived_vertical_repositories_remain_out_of_source_links() -> None:
    module = load_overlay()
    rendered = "\n".join(
        module.html(row) + module.readme(row) for row in module.FLAGSHIPS
    )
    assert "https://github.com/szl-holdings/counsel" not in rendered
    assert "https://github.com/szl-holdings/szl-fleet-overlay" not in rendered
    assert "a11oy/tree/main/verticals/counsel" in rendered
    assert "a11oy/tree/main/verticals/vessels" in rendered


@pytest.mark.parametrize("field,old,new", [
    ("DOCKER", "USER szl", "USER root"),
    ("DOCKER", "sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf",
     "sha256:" + "0" * 64),
    ("DOCKER", "--no-server-header", "--reload"),
    ("DOCKER", "EXPOSE 7860", "RUN echo unreviewed\nEXPOSE 7860"),
    ("REQ", "fastapi==0.141.1", "fastapi==0.116.1"),
    ("REQ", "starlette==1.6.0", "starlette"),
    ("REQ", "pip==26.2.1", "pip==25.0.1"),
    ("REQ", "websockets==17.1", "websockets==17.1\nundeclared-fixture==1.0"),
])
def test_runtime_exception_rejects_unreviewed_mutations(field, old, new) -> None:
    overlay = load_overlay()
    assert_reviewed_runtime(overlay)
    candidate = SimpleNamespace(DOCKER=overlay.DOCKER, REQ=overlay.REQ)
    original = getattr(candidate, field)
    assert old in original
    setattr(candidate, field, original.replace(old, new, 1))
    with pytest.raises(AssertionError):
        assert_reviewed_runtime(candidate)


def test_probe_http_success_is_reachable_not_measured() -> None:
    module = load_overlay()
    assert '"status":"LIVE" if r.is_success' not in module.APP
    assert '"status":"REACHABLE" if r.is_success else "UNAVAILABLE"' in module.APP
    assert '"honesty":"HTTP success is reachability, not MEASURED"' in module.APP
    assert '"receipt_verified":False' in module.APP


def test_livebar_and_sentra_iris_stay_closed_without_a_receipt() -> None:
    module = load_overlay()
    sentra = module.html(by_slug(module)["sentra"])
    finance = module.html(by_slug(module)["finance"])
    lyte = module.html(by_slug(module)["lyte"])
    for page in (sentra, finance, lyte):
        assert "j.status==='LIVE'?'is-live'" not in page
        assert "s.className='status'+(ok?' is-live':'')" not in page
        assert "s.className='status';" in page
        assert "j.status==='MEASURED'&&j.receipt_verified===true" in page
        assert "j.status==='REACHABLE'||j.status==='LIVE'" in page
        assert "root.dataset.iris=ok?'gated':'closed'" not in page
        assert "root.dataset.iris='closed'" in page
        assert "is-live" not in page[page.find("<script>"):]
    assert 'data-iris="closed"' in sentra
    assert "iris-aperture" in sentra
    assert "html[data-iris=open] .iris-aperture{transform:scale(.42)}" in module.DOMAIN_CSS["sentra"]
    assert "scale(1)" not in module.DOMAIN_CSS["sentra"]


# SIMULATED provider transaction contracts; no deployment is established here.
_TX_SOURCE = "a" * 40
_TX_PARENT = "b" * 40
_TX_COMMIT = "c" * 40


def _load_transaction_fixture(path):
    return load_module("sentra_contract_" + Path(path).stem, Path(path))


@pytest.fixture
def sentra_wrapper(monkeypatch):
    module = _load_transaction_fixture("scripts/hf_publish_vertical_flagships_v4.py")
    for name, value in {"GITHUB_SHA": _TX_SOURCE, "GITHUB_REF": "refs/heads/main",
                        "GITHUB_REPOSITORY": "szl-holdings/a11oy", "GITHUB_RUN_ID": "77",
                        "GITHUB_TOKEN": "fixture-read-credential"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(module, "_github_json", lambda *a, **k: pytest.fail("legacy credential fallback"))
    return module


def _transaction_source_responses(module):
    contexts = ("source-contract", *module.SENTRA_DOCTRINE_CHECKS)
    return {
        "/repos/szl-holdings/a11oy/branches/main": {
            "commit": {"sha": _TX_SOURCE}, "protected": True,
            "protection": {"enabled": True, "required_status_checks": {
                "contexts": ["source-contract"],
                "checks": [{"context": "source-contract", "app_id": 15368}]}},
        },
        f"/repos/szl-holdings/a11oy/commits/{_TX_SOURCE}": {
            "sha": _TX_SOURCE, "commit": {"verification": {"verified": True, "reason": "valid"}}},
        f"/repos/szl-holdings/a11oy/commits/{_TX_SOURCE}/check-runs?filter=latest&per_page=100&page=1": {
            "total_count": len(contexts), "check_runs": [
                {"name": name, "head_sha": _TX_SOURCE, "app": {"id": 15368},
                 "status": "completed", "conclusion": "success"} for name in contexts]},
    }


@pytest.mark.parametrize("status", [401, 403])
def test_authenticated_source_errors_never_fall_back(sentra_wrapper, monkeypatch, status):
    calls = []

    def fail(request, **kwargs):
        calls.append(request)
        raise HTTPError(request.full_url, status, "fixture", {}, None)

    monkeypatch.setattr(sentra_wrapper.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=fail))
    with pytest.raises(sentra_wrapper.SentraPublicationError) as error:
        sentra_wrapper._sentra_github_json("/repos/szl-holdings/a11oy/branches/main")
    assert error.value.http_status == status
    assert len(calls) == 1
    assert dict((key.lower(), value) for key, value in calls[0].header_items())["cache-control"] == "no-cache"


def test_source_admission_uses_protected_policy_and_exact_check_authority(sentra_wrapper, monkeypatch):
    responses = _transaction_source_responses(sentra_wrapper)
    monkeypatch.setattr(sentra_wrapper, "_sentra_github_json", lambda path: responses[path])
    assert sentra_wrapper._sentra_source_admission() == _TX_SOURCE


@pytest.mark.parametrize("defect", ["moved", "unprotected", "missing-policy", "unsigned", "failed", "pending", "wrong-head", "wrong-app", "missing-doctrine", "unbounded"])
def test_unresolved_source_never_admits(sentra_wrapper, monkeypatch, defect):
    responses = _transaction_source_responses(sentra_wrapper)
    branch = responses["/repos/szl-holdings/a11oy/branches/main"]
    signature = responses[f"/repos/szl-holdings/a11oy/commits/{_TX_SOURCE}"]["commit"]["verification"]
    checks = responses[f"/repos/szl-holdings/a11oy/commits/{_TX_SOURCE}/check-runs?filter=latest&per_page=100&page=1"]
    if defect == "moved": branch["commit"]["sha"] = _TX_PARENT
    elif defect == "unprotected": branch["protected"] = False
    elif defect == "missing-policy": branch["protection"] = {}
    elif defect == "unsigned": signature["verified"] = False
    elif defect == "failed": checks["check_runs"][0]["conclusion"] = "failure"
    elif defect == "pending": checks["check_runs"][0]["status"] = "in_progress"
    elif defect == "wrong-head": checks["check_runs"][0]["head_sha"] = _TX_PARENT
    elif defect == "wrong-app": checks["check_runs"][0]["app"]["id"] = 1
    elif defect == "missing-doctrine": checks["check_runs"].pop()
    elif defect == "unbounded": checks["total_count"] = 401
    monkeypatch.setattr(sentra_wrapper, "_sentra_github_json", lambda path: responses[path])
    with pytest.raises(sentra_wrapper.SentraPublicationError): sentra_wrapper._sentra_source_admission()


class _SentraFixtureApi:
    def __init__(self, module):
        self.module = module
        self.head = _TX_PARENT
        self.override = {}
        self.extra_files = []
        self.commits = []
        self.forbidden_calls = []
        self.commit_error = None
        self.files = {}

    def space_info(self, repo_id):
        assert repo_id == self.module.SENTRA_SPACE
        fields = {"id": repo_id, "sha": self.head, "private": False, "sdk": "docker",
                  "runtime": SimpleNamespace(stage="RUNNING", hardware="cpu-basic", requested_hardware="cpu-basic", storage=None)}
        return SimpleNamespace(**{**fields, **self.override})

    def list_repo_files(self, repo_id, *, repo_type, revision):
        assert repo_id == self.module.SENTRA_SPACE and repo_type == "space"
        return [*self.module.SENTRA_FILES, ".gitattributes", *self.extra_files]

    def auth_check(self, **kwargs):
        assert kwargs == {"repo_id": self.module.SENTRA_SPACE, "repo_type": "space", "write": True}

    def create_commit(self, **kwargs):
        self.commits.append(kwargs)
        if self.commit_error: raise self.commit_error
        assert kwargs["parent_commit"] == self.head
        self.files = {op.path_in_repo: op.path_or_fileobj for op in kwargs["operations"]}
        self.head = _TX_COMMIT
        return SimpleNamespace(oid=_TX_COMMIT)

    def __getattr__(self, name):
        if name in {"upload_file", "create_repo", "delete_file", "delete_repo", "restart_space",
                    "request_space_hardware", "request_space_storage", "add_space_secret", "add_space_variable",
                    "update_repo_settings", "pause_space"}:
            def forbidden(*args, **kwargs):
                self.forbidden_calls.append(name)
                raise AssertionError(name)
            return forbidden
        raise AttributeError(name)


@pytest.fixture
def sentra_transaction(sentra_wrapper, monkeypatch, tmp_path):
    renderer = _load_transaction_fixture("scripts/hf_publish_vertical_flagships_v4_impl.py")
    api = _SentraFixtureApi(sentra_wrapper)
    fake_hub = ModuleType("huggingface_hub")
    fake_hub.CommitOperationAdd = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setattr(sentra_wrapper, "FLAGSHIP_RECEIPT", tmp_path / "_transaction_receipt.json")
    monkeypatch.setattr(sentra_wrapper, "_sentra_source_admission", lambda: _TX_SOURCE)
    monkeypatch.setattr(sentra_wrapper, "load_module", lambda name, path: renderer)
    monkeypatch.setattr(renderer._BASE, "token_from_env", lambda: ("fixture-writer-credential", "SIMULATED"))
    monkeypatch.setattr(renderer._BASE, "HfApi", lambda **kwargs: api)
    monkeypatch.setattr(sentra_wrapper, "_sentra_file_bytes", lambda revision, path: b"retained-attributes" if path == ".gitattributes" else api.files[path])
    monkeypatch.setattr(renderer, "observe_flagship", lambda row: row.update(build_info={"hf_revision": api.head}))
    monkeypatch.setattr(renderer, "observation_passes", lambda *a, **k: True)
    return sentra_wrapper, renderer, api


def _transaction_receipt(module):
    return json.loads(module.FLAGSHIP_RECEIPT.read_text(encoding="utf-8"))


def test_single_cas_fixed_files_readback_and_no_other_mutators(sentra_transaction, capsys):
    module, renderer, api = sentra_transaction
    expected, _ = renderer.render_sentra_payload(_TX_SOURCE, 77)
    assert module.publish_sentra_existing() == 0
    assert len(api.commits) == 1
    commit = api.commits[0]
    assert commit["repo_id"] == module.SENTRA_SPACE and commit["repo_type"] == "space"
    assert commit["revision"] == "main" and commit["parent_commit"] == _TX_PARENT
    assert api.files == expected and tuple(api.files) == module.SENTRA_FILES
    assert api.forbidden_calls == []
    result = _transaction_receipt(module)
    assert result["provider_write_confirmed"] is True and result["provider_commit_sha"] == _TX_COMMIT
    assert result["immutable_readback_complete"] is True and result["source_still_current"] is True
    assert result["independent_validation"] == "UNKNOWN" and result["receipt_signature_state"] == "UNAVAILABLE"
    assert "fixture-writer-credential" not in capsys.readouterr().out


@pytest.mark.parametrize("defect", ["private", "visibility-unknown", "non-docker", "paid-current", "paid-requested", "identity", "building", "extra-file", "404"])
def test_unqualified_target_has_zero_writes(sentra_transaction, monkeypatch, defect):
    module, _, api = sentra_transaction
    if defect == "private": api.override["private"] = True
    elif defect == "visibility-unknown": api.override["private"] = None
    elif defect == "non-docker": api.override["sdk"] = "gradio"
    elif defect == "identity": api.override["id"] = "SZLHOLDINGS/other"
    elif defect == "extra-file": api.extra_files = ["unowned.py"]
    elif defect == "404":
        monkeypatch.setattr(api, "space_info", lambda *a: (_ for _ in ()).throw(HTTPError("fixture", 404, "fixture", {}, None)))
    else:
        rt = api.space_info(module.SENTRA_SPACE).runtime
        if defect == "paid-current": rt.hardware = "cpu-upgrade"
        elif defect == "paid-requested": rt.requested_hardware = "cpu-upgrade"
        else: rt.stage = "BUILDING"
        api.override["runtime"] = rt
    assert module.publish_sentra_existing() == 1
    assert api.commits == [] and api.forbidden_calls == []
    assert _transaction_receipt(module)["provider_write_attempted"] is False


@pytest.mark.parametrize("phase", ["before", "after"])
def test_source_supersession_retains_actual_effects_without_retry(sentra_transaction, monkeypatch, phase):
    module, _, api = sentra_transaction
    calls = []

    def admit():
        calls.append(1)
        if len(calls) == (2 if phase == "before" else 3):
            raise module.SentraPublicationError("Source superseded")
        return _TX_SOURCE

    monkeypatch.setattr(module, "_sentra_source_admission", admit)
    assert module.publish_sentra_existing() == 1
    assert len(api.commits) == (0 if phase == "before" else 1)
    assert _transaction_receipt(module)["provider_write_confirmed"] is (phase == "after")
    assert api.forbidden_calls == []


@pytest.mark.parametrize("status", [401, 409, 500])
def test_failed_or_ambiguous_commit_is_never_retried(sentra_transaction, status):
    module, _, api = sentra_transaction
    api.commit_error = HTTPError("fixture", status, "fixture", {}, None)
    assert module.publish_sentra_existing() == 1
    assert len(api.commits) == 1 and api.forbidden_calls == []
    assert _transaction_receipt(module)["provider_write_attempted"] is True
    assert _transaction_receipt(module)["provider_write_confirmed"] is False


def test_immutable_byte_mismatch_keeps_confirmed_write_and_blocks(sentra_transaction, monkeypatch):
    module, _, api = sentra_transaction
    monkeypatch.setattr(module, "_sentra_file_bytes", lambda revision, path: b"retained-attributes" if path == ".gitattributes" else b"wrong")
    assert module.publish_sentra_existing() == 1
    assert len(api.commits) == 1 and _transaction_receipt(module)["provider_write_confirmed"] is True
    assert _transaction_receipt(module)["complete"] is False and api.forbidden_calls == []


def test_runtime_requires_returned_commit_and_is_bounded(sentra_transaction, monkeypatch):
    module, renderer, api = sentra_transaction
    monkeypatch.setattr(renderer, "observe_flagship", lambda row: row.update(build_info={"hf_revision": _TX_PARENT}))
    ticks = iter([0, 0, 1801])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    assert module.publish_sentra_existing() == 1
    assert len(api.commits) == 1 and _transaction_receipt(module)["runtime_state"] == "UNKNOWN"


def test_pure_renderer_matches_existing_writer_bytes(monkeypatch, tmp_path):
    renderer = _load_transaction_fixture("scripts/hf_publish_vertical_flagships_v4_impl.py")
    for name, value in {"GITHUB_SHA": _TX_SOURCE, "GITHUB_RUN_ID": "77"}.items(): monkeypatch.setenv(name, value)
    expected, _ = renderer.render_sentra_payload(_TX_SOURCE, 77)
    captured = {}
    api = SimpleNamespace(repo_exists=lambda **k: True, auth_check=lambda **k: None,
                          upload_file=lambda **k: captured.update({k["path_in_repo"]: k["path_or_fileobj"]}),
                          restart_space=lambda *a: None)
    monkeypatch.setattr(renderer, "FLAGSHIPS", tuple(item for item in renderer.FLAGSHIPS if item["slug"] == "sentra"))
    monkeypatch.setattr(renderer._BASE, "token_from_env", lambda: ("fixture-writer-credential", "SIMULATED"))
    monkeypatch.setattr(renderer._BASE, "HfApi", lambda **k: api)
    monkeypatch.setattr(renderer._BASE, "load_terra_forge_bundle", lambda: ("", {}))
    monkeypatch.setattr(renderer._BASE, "observe_flagship", lambda row: None)
    monkeypatch.setattr(renderer._BASE, "observation_passes", lambda *a, **k: True)
    monkeypatch.chdir(tmp_path)
    assert renderer.main() == 0
    assert captured == expected


def test_source_refusal_precedes_writer_credential_resolution(sentra_transaction, monkeypatch):
    module, renderer, api = sentra_transaction
    token_reads = []
    monkeypatch.setattr(renderer._BASE, "token_from_env", lambda: token_reads.append(True))
    monkeypatch.setattr(module, "_sentra_source_admission", lambda: (_ for _ in ()).throw(
        module.SentraPublicationError("Source permission unavailable", 403)))
    assert module.publish_sentra_existing() == 1
    assert token_reads == [] and api.commits == [] and api.forbidden_calls == []
    assert _transaction_receipt(module)["http_status"] == 403


def test_target_parent_changes_before_cas_has_zero_writes(sentra_transaction, monkeypatch):
    module, _, api = sentra_transaction
    observe = api.space_info
    calls = []

    def changed(repo_id):
        calls.append(True)
        result = observe(repo_id)
        if len(calls) > 1:
            result.sha = "d" * 40
        return result

    monkeypatch.setattr(api, "space_info", changed)
    assert module.publish_sentra_existing() == 1
    assert api.commits == [] and api.forbidden_calls == []


def test_source_check_pagination_preserves_required_authority(sentra_wrapper, monkeypatch):
    responses = _transaction_source_responses(sentra_wrapper)
    first = f"/repos/szl-holdings/a11oy/commits/{_TX_SOURCE}/check-runs?filter=latest&per_page=100&page=1"
    final = {"total_count": 103, "check_runs": responses[first]["check_runs"]}
    responses[first] = {"total_count": 103, "check_runs": [
        {"name": f"unrelated-{i}", "app": {"id": 15368}, "head_sha": _TX_SOURCE,
         "status": "completed", "conclusion": "success"} for i in range(100)]}
    responses[first.rsplit("&page=", 1)[0] + "&page=2"] = final
    monkeypatch.setattr(sentra_wrapper, "_sentra_github_json", lambda path: responses[path])
    assert sentra_wrapper._sentra_source_admission() == _TX_SOURCE


def test_immutable_readback_uses_canonical_space_route_and_bounded_body(sentra_wrapper, monkeypatch):
    requests = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            assert limit == sentra_wrapper.SENTRA_MAX_FILE_BYTES + 1
            return b"retained-attributes"

    def observe(request, **kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(sentra_wrapper.urllib.request, "urlopen", observe)
    assert sentra_wrapper._sentra_file_bytes(_TX_PARENT, ".gitattributes") == b"retained-attributes"
    assert requests[0].full_url == f"https://huggingface.co/spaces/SZLHOLDINGS/sentra/resolve/{_TX_PARENT}/.gitattributes"
    assert dict((key.lower(), value) for key, value in requests[0].header_items())["cache-control"] == "no-cache"
    with pytest.raises(sentra_wrapper.SentraPublicationError):
        sentra_wrapper._sentra_file_bytes(_TX_PARENT, "../unowned.py")
    assert len(requests) == 1
