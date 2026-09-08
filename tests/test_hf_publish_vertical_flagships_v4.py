# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

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


def by_slug(module) -> dict[str, dict]:
    return {row["slug"]: row for row in module.FLAGSHIPS}


def test_overlay_and_immutable_base_compile() -> None:
    overlay = source(SCRIPT)
    base = source(BASE_SCRIPT)
    assert "SENTRA_OVERLAY_VERSION = \"receipt-verifier/v1\"" in overlay
    assert "Publish six source-bound" in base
    assert "exec(" not in overlay
    assert "eval(" not in overlay


def test_overlay_changes_only_sentra_contract_and_templates() -> None:
    base = load_base()
    overlay = load_overlay()
    base_rows = by_slug(base)
    overlay_rows = by_slug(overlay)

    assert set(base_rows) == set(overlay_rows) == {
        "terra", "sentra", "counsel", "finance", "vessels", "lyte"
    }
    for slug in set(base_rows) - {"sentra"}:
        assert overlay_rows[slug] == base_rows[slug]
        assert overlay.DOMAIN_CSS[slug] == base.DOMAIN_CSS[slug]
        assert overlay.DOMAIN_HTML[slug] == base.DOMAIN_HTML[slug]

    assert overlay_rows["sentra"] != base_rows["sentra"]
    assert overlay.DOMAIN_CSS["sentra"] != base.DOMAIN_CSS["sentra"]
    assert overlay.DOMAIN_HTML["sentra"] != base.DOMAIN_HTML["sentra"]


def test_sentra_binds_to_read_only_public_receipt_verifier() -> None:
    module = load_overlay()
    sentra = by_slug(module)["sentra"]
    assert sentra == {
        "slug": "sentra",
        "title": "Sentra",
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
        "slug": "sentra",
        "upstream": "https://upstream.example/evidence",
        "evidence_http": 200,
        "evidence": {"schema": "szl.vertical-evidence/v1", "source": "https://upstream.example/evidence", "status": "UNAVAILABLE", "observation_state": "UNAVAILABLE", "mode": "unavailable", "observed": False, "observed_at": None, "source_revision": None, "gateway_cached": False},
        "artifact_set_sha256": "c" * 64,
        "landing_sha256": "d" * 64,
        "panels_sha256": "e" * 64,
        "forge": forge,
        "root": {"http_status": 200, "marker_present": True, "evidence_attributes_present": True, "no_js_fallback_present": True},
        "panels": {"http_status": 200, "marker_present": True, "evidence_attributes_present": True, "no_js_fallback_present": True},
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
    row["evidence"]["status"] = "LIVE"
    assert not module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["evidence"]["status"] = "UNAVAILABLE"
    row["evidence_http"] = 503
    assert not module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["evidence_http"] = 200
    row["panels"]["marker_present"] = False
    assert not module.observation_passes(
        row, source_revision=revision, workflow_run_id=run_id
    )
    row["panels"]["marker_present"] = True
    for surface in ("root", "panels"):
        for requirement in ("evidence_attributes_present", "no_js_fallback_present"):
            row[surface][requirement] = False
            assert not module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
            row[surface][requirement] = True
    row["root"]["evidence_attributes_present"] = False
    row["slug"] = "terra"
    assert not module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["root_marker"] = module.TERRA_FORGE_MARKER
    assert module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)
    row["panels"]["no_js_fallback_present"] = False
    assert not module.observation_passes(row, source_revision=revision, workflow_run_id=run_id)


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


def test_entrypoint_preserves_current_topology_and_lyte_pin() -> None:
    entrypoint = source(ENTRYPOINT)
    intelligence = source(INTELLIGENCE)
    combined = source(COMBINED)
    for fragment in (
        "hf_publish_vertical_flagships_v4_impl.py",
        'PUBLIC_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance", "lyte")',
        'GENERATED_FLAGSHIP_SLUGS = ("terra", "sentra", "counsel", "finance")',
        'SOURCE_OWNED_FLAGSHIP_SLUGS = ("lyte",)',
        'LYTE_SOURCE_REVISION = "a6a653b0d93a0d150b868a044642ce4f5c71d766"',
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
        "needs: deploy",
        "scripts/hf_publish_vertical_flagships_v4.py",
        "ref: ${{ github.sha }}",
        "persist-credentials: false",
    ):
        assert fragment in sync


def test_archived_vertical_repositories_remain_out_of_source_links() -> None:
    module = load_overlay()
    rendered = "\n".join(
        module.html(row) + module.readme(row) for row in module.FLAGSHIPS
    )
    assert "https://github.com/szl-holdings/counsel" not in rendered
    assert "https://github.com/szl-holdings/szl-fleet-overlay" not in rendered
    assert "a11oy/tree/main/verticals/counsel" in rendered
    assert "a11oy/tree/main/verticals/vessels" in rendered


def generated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_overlay()
    for filename, content in (("index.html", "INDEX"), ("panels.html", "PANELS")):
        (tmp_path / filename).write_text(content, encoding="utf-8")
    config = {"title": "Test", "upstream": "https://upstream.example/evidence",
              "landing_sha256": hashlib.sha256(b"INDEX").hexdigest(),
              "panels_sha256": hashlib.sha256(b"PANELS").hexdigest()}
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    runtime = {}
    exec(compile(module.APP, "generated-app.py", "exec"), runtime)
    return runtime


class UpstreamResponse:
    def __init__(self, payload=b'{"ok":true}', *, status=200, content_type="application/json", encoding="identity"):
        self.payload = payload
        self.status_code = status
        self.is_success = 200 <= status < 300
        self.headers = {"content-type": content_type, "content-encoding": encoding}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_bytes(self, *, chunk_size):
        assert chunk_size == 8192
        yield self.payload


@pytest.mark.parametrize("response,error", [
    (UpstreamResponse(status=503), "upstream_http_error"),
    (UpstreamResponse(status=302), "upstream_http_error"),
    (UpstreamResponse(content_type="text/html"), "upstream_not_json"),
    (UpstreamResponse(encoding="gzip"), "upstream_compressed_response"),
    (UpstreamResponse(b"[]"), "upstream_not_object"),
    (UpstreamResponse(b"not JSON"), "JSONDecodeError"),
    (UpstreamResponse(b'{"x":NaN}'), "ValueError"),
    (UpstreamResponse(b'{"x":1e999}'), "ValueError"),
    (UpstreamResponse(b"x" * 262145), "ValueError"),
])
def test_gateway_transport_failures_are_unavailable(tmp_path, monkeypatch, response, error):
    runtime = generated_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime["httpx"], "stream", lambda *_args, **_kwargs: response)
    result = runtime["probe"]()
    assert result["status"] == result["observation_state"] == "UNAVAILABLE"
    assert result["observed"] is False
    assert result["observed_at"] is None
    assert result["data"] is None
    assert result["error"] == error
    assert result["checked_at"].endswith("Z")
    assert runtime["UPSTREAM_SLOTS"].acquire(blocking=False)
    runtime["UPSTREAM_SLOTS"].release()


def test_http_200_and_generic_business_status_cannot_declare_observation(tmp_path, monkeypatch):
    runtime = generated_runtime(tmp_path, monkeypatch)
    calls = []
    def stream(*args, **kwargs):
        calls.append((args, kwargs))
        return UpstreamResponse(b'{"ok":true,"metrics":{"status":"LIVE","fetched_at":1788609600}}')
    monkeypatch.setattr(runtime["httpx"], "stream", stream)
    result = runtime["probe"]()
    assert result["http_status"] == 200
    assert result["observed"] is False
    assert result["status"] == "UNAVAILABLE"
    assert result["source_states"] == []
    assert result["gateway_cached"] is False
    assert calls[0][1]["follow_redirects"] is False
    assert calls[0][1]["headers"]["Accept-Encoding"] == "identity"


def test_source_metadata_preserves_mixed_state_and_revision_scope(tmp_path, monkeypatch):
    runtime = generated_runtime(tmp_path, monkeypatch)
    contract = runtime["evidence_contract"]
    source = {"value": {"count": 7}, "freshness": {"status": "live", "fetched_at": "2026-09-08T12:00:00Z", "source_revision": "a" * 40}}
    live = contract({"feed": source})
    assert live["status"] == "LIVE"
    assert live["observed"] is True
    assert live["observed_at"] == "2026-09-08T12:00:00Z"
    assert live["source_revision"] == "a" * 40
    assert live["provenance"] == "UPSTREAM_REPORTED"
    assert live["freshness_policy"] == "upstream_reported_only"
    mixed = contract({"good": source, "missing": {"value": None, "freshness": {"status": "live"}}})
    assert mixed["status"] == "PARTIAL" and mixed["observed"] is True
    assert mixed["source_revision"] is None
    denied = contract({"status": "LIVE", "observation_state": "UNAVAILABLE", "observed": False, "feed": source})
    assert denied["status"] == "UNAVAILABLE" and denied["observed"] is False
    assert denied["observed_at"] is None
    missing_time = contract({"status": "LIVE"})
    assert missing_time["status"] == "UNAVAILABLE"
    assert missing_time["source_states"][0]["upstream_status"] == "LIVE"
    assert missing_time["observed_at"] is None
    contradictory = contract({"observation_state": "UNAVAILABLE", "freshness": source["freshness"]})
    assert contradictory["status"] == "UNAVAILABLE"
    assert contradictory["observed"] is False


@pytest.mark.parametrize("state", ["CACHED", "STALE", "SAMPLE", "MODELED", "ROADMAP", "BLOCKED"])
def test_source_states_are_never_promoted_to_live(tmp_path, monkeypatch, state):
    runtime = generated_runtime(tmp_path, monkeypatch)
    result = runtime["evidence_contract"]({"status": state, "observed_at": "2026-09-08T12:00:00Z"})
    assert result["status"] == state
    assert result["observed"] is (state in {"CACHED", "STALE"})


def test_gateway_concurrency_deadline_and_structure_are_bounded(tmp_path, monkeypatch):
    runtime = generated_runtime(tmp_path, monkeypatch)
    semaphore = runtime["UPSTREAM_SLOTS"]
    for _ in range(4):
        assert semaphore.acquire(blocking=False)
    assert runtime["probe"]()["error"] == "upstream_probe_busy"
    for _ in range(4):
        semaphore.release()
    ticks = iter([0, 11, 12])
    monkeypatch.setattr(runtime["time"], "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runtime["httpx"], "stream", lambda *_args, **_kwargs: UpstreamResponse())
    assert runtime["probe"]()["error"] == "TimeoutError"
    nested = {}
    for _ in range(14):
        nested = {"child": nested}
    with pytest.raises(ValueError, match="structure exceeds limit"):
        runtime["evidence_contract"](nested)


def test_api_live_and_readiness_keep_proof_layers_separate(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    runtime = generated_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime["httpx"], "stream", lambda *_args, **_kwargs: UpstreamResponse())
    with TestClient(runtime["app"]) as client:
        result = client.get("/api/live")
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["observed"] is False
        ready = client.get("/readyz").json()
        assert ready["ready"] is True
        assert ready["scope"] == "local_artifact_integrity_only"
        assert ready["upstream_evidence_checked"] is False


def test_rendered_contract_and_no_js_markup_are_real_elements():
    module = load_overlay()
    for row in module.FLAGSHIPS:
        page = module.html(row)
        assert module.evidence_markup_contract(page) == {"evidence_attributes_present": True, "no_js_fallback_present": True}
        assert 'data-provenance="ILLUSTRATIVE" data-mode="modeled"' in page
        assert "transport success alone is not evidence" in page
        assert "Freshness is reported by the upstream" in page
        assert 'href="/api/live"' in page and 'href="/build-receipt.json"' in page
        assert not module.evidence_markup_contract(page + '<section id="evidence"></section>')["evidence_attributes_present"]
        assert not module.evidence_markup_contract(page.replace('<noscript>', '<div>').replace('</noscript>', '</div>'))["no_js_fallback_present"]
    fake = '<script>"<p id=\"evidence\" data-provenance=\"UNAVAILABLE\">"</script>'
    assert not module.evidence_markup_contract(fake)["evidence_attributes_present"]


def test_browser_drops_live_state_after_http_failure_and_keeps_cached_non_live(tmp_path):
    module = load_overlay()
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; browser contract requires Node")
    harness = r'''
const assert=require('node:assert/strict');
const status={className:'status',children:[{},{}]},output={textContent:''},panel={dataset:{}};
global.document={getElementById:id=>({st:status,out:output,evidence:panel}[id])};
global.setInterval=()=>0;
let response={schema:'szl.vertical-evidence/v1',status:'LIVE',observation_state:'LIVE',observed:true,observed_at:'2026-09-08T12:00:00Z',provenance:'UPSTREAM_REPORTED',source_revision:'a'.repeat(40)};
global.fetch=async()=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>response});
'''+module.EVIDENCE_JS+r'''
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(status.className,'status is-live');
  assert.equal(panel.dataset.observedAt,'2026-09-08T12:00:00Z');
  let parsed=false;
  global.fetch=async()=>({ok:false,status:503,json:async()=>{parsed=true;return response;}});
  await loadEvidence();
  assert.equal(parsed,false);
  assert.equal(status.className,'status');
  assert.equal(panel.dataset.mode,'unavailable');
  assert.equal(panel.dataset.sourceRevision,'UNAVAILABLE');
  response={...response,status:'CACHED',observation_state:'CACHED'};
  global.fetch=async()=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>response});
  await loadEvidence();
  assert.equal(status.className,'status ');
  assert.equal(panel.dataset.mode,'cached');
  response={...response,status:'LIVE',observation_state:'LIVE',observed_at:null};
  await loadEvidence();
  assert.equal(panel.dataset.mode,'unavailable');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    script = tmp_path / "evidence-browser-test.cjs"
    script.write_text(harness, encoding="utf-8")
    subprocess.run([node, str(script)], check=True, capture_output=True, text=True, timeout=30)
