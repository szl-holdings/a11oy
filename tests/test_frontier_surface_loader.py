#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run the emitted Frontier module against real catalog fixtures and failed reads."""

import copy
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

import a11oy_frontier_page as frontier


# Reuse the full-module graphics/DOM harness; only synthetic I/O and observations
# are extended here. No loader or validator is copied out of the application.
_spec = importlib.util.spec_from_file_location(
    "_frontier_bootstrap_support", Path(__file__).with_name("test_frontier_bootstrap.py")
)
_bootstrap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bootstrap)
backend_manifest = _bootstrap.backend_manifest

SURFACES_EP = "/api/a11oy/v1/frontier/surfaces"
MANIFEST_EP = "/api/a11oy/v1/frontier/manifest"
_MISSING = object()


def _replace_once(source, old, new):
    assert source.count(old) == 1, "The shared bootstrap harness changed"
    return source.replace(old, new, 1)


DRIVER = _replace_once(
    _bootstrap.DRIVER,
    "const requests = [], imports = [], importResolvers = [], unhandled = [];",
    "const requests = [], imports = [], importResolvers = [], unhandled = [], jsonReads = [];",
)
DRIVER = _replace_once(
    DRIVER,
    "  addEventListener() {}\n  removeEventListener() {}",
    """  addEventListener(name, callback) {
    this.events ??= new Map();
    if (!this.events.has(name)) this.events.set(name, []);
    this.events.get(name).push(callback);
  }
  dispatch(name) {
    for (const callback of this.events?.get(name) || [])
      callback({target: this, currentTarget: this, preventDefault() {}});
  }
  removeEventListener() {}""",
)
DRIVER = _replace_once(
    DRIVER,
    "    return {ok: true, status: 200, json: async () => input.responses[url]};",
    """    const response = input.http[url] || {};
    if (response.networkError) throw new Error(response.networkError);
    const status = response.status ?? 200;
    return {
      ok: status >= 200 && status < 300, status,
      json: async () => {
        jsonReads.push(url);
        if (response.jsonError) throw new SyntaxError(response.jsonError);
        return input.responses[url];
      },
    };""",
)
DRIVER = _replace_once(
    DRIVER,
    "  surfacesStatus: elements.get('surfaces-status').textContent,",
    """  surfacesStatus: elements.get('surfaces-status').textContent,
  surfacesStatusClass: elements.get('surfaces-status').className,
  surfacesRollup: elements.get('surfaces-rollup').innerHTML,
  surfaceFilters: elements.get('surface-filters').innerHTML,
  surfacePageStatus: elements.get('surface-page-status').textContent,
  searchDisabled: elements.get('surface-search').disabled,
  prevDisabled: elements.get('surface-prev').disabled,
  nextDisabled: elements.get('surface-next').disabled,
  manifestStatusClass: elements.get('status').className,
  manifestRollup: elements.get('rollup').innerHTML,
  jsonReads,""",
)
DRIVER = _replace_once(
    DRIVER,
    "  process.stdout.write(JSON.stringify({beforeImports, afterImports, afterResize: snapshot()}));",
    """  const afterResize = snapshot();
  for (const event of input.events) {
    const element = elements.get(event.id);
    if (Object.hasOwn(event, 'value')) element.value = event.value;
    element.dispatch(event.type);
  }
  await new Promise(resolve => setImmediate(resolve));
  process.stdout.write(JSON.stringify({
    beforeImports, afterImports, afterResize, afterEvents: snapshot(),
  }));""",
)


def run_catalog(manifest, catalog, *, http=None, events=(), failure=None):
    node = shutil.which("node")
    assert node, "Node is required for full Frontier module regression tests"
    html = frontier._page_html("a11oy")
    notice = re.search(r'<div id="scene-status"([^>]*)>([^<]*)<', html)
    assert notice
    payload = {
        "script": html.split('<script type="module">', 1)[1].split("</script>", 1)[0],
        "ids": re.findall(r'\bid="([^"]+)"', html),
        "noticeText": notice[2].strip(),
        "noticeInitiallyHidden": " hidden" in notice[1],
        "failure": failure, "lateImports": False, "reducedMotion": False, "compact": False,
        "http": http or {}, "events": list(events),
        "responses": {
            MANIFEST_EP: manifest,
            SURFACES_EP: catalog,
            "/api/a11oy/v1/fashion": {"lanes": []},
            "/api/a11oy/v1/brain/stats": {
                "label": "SAMPLE", "node_count": 7, "distinct_artifacts": 2,
            },
            "/api/a11oy/v1/brain/health/corpus-sources": {
                "label": "SAMPLE", "summary": {"counts": {"ADMITTED": 3}, "quarantined_entries": 1},
            },
        },
    }
    result = subprocess.run(
        [node, "--eval", DRIVER], input=json.dumps(payload),
        text=True, encoding="utf-8", capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def producer_catalog(tmp_path, monkeypatch, entries):
    """Build through the real registry/asset parser, including its missing branches."""
    registry = tmp_path / "static" / "3d" / "holographic.html"
    registry.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (sid, title, source) in enumerate(entries):
        asset = f"/static/3d/surfaces/fixture-{index}.js"
        if source is not None:
            target = tmp_path / asset.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        rows.append(f'{{ id: "{sid}", title: "{title}", mod: "{asset}" }}')
    registry.write_text("const SURFACES = [" + ",".join(rows) + "];", encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(frontier, "_REPO_ROOT", tmp_path)
        return frontier.build_surfaces_manifest()


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    return producer_catalog(
        tmp_path, monkeypatch, [("fixture", "Fixture surface", 'const label = "MODELED";')]
    )


def assert_unavailable(snapshot):
    assert snapshot["surfacesStatus"].startswith("surfaces unavailable:")
    assert "err" in snapshot["surfacesStatusClass"].split()
    assert "UNAVAILABLE" in snapshot["surfacesRollup"]
    assert "<b>0</b> surfaces" not in snapshot["surfacesRollup"]
    assert snapshot["surfaceFilters"] == ""
    assert "unknown" in snapshot["surfaces"]
    assert "unavailable" in snapshot["surfacePageStatus"].lower()
    assert snapshot["searchDisabled"] is True
    assert snapshot["prevDisabled"] is True
    assert snapshot["nextDisabled"] is True
    assert "labels_valid=undefined" not in snapshot["surfacesStatus"]
    assert snapshot["unhandled"] == []


def assert_catalog_loaded(snapshot, catalog):
    assert snapshot["surfacesStatus"].startswith(f'live · {catalog["count"]} surfaces')
    assert "labels_valid=true" in snapshot["surfacesStatus"]
    assert "err" not in snapshot["surfacesStatusClass"].split()
    assert f'<b>{catalog["count"]}</b> surfaces' in snapshot["surfacesRollup"]
    assert f'ALL {catalog["count"]}</button>' in snapshot["surfaceFilters"]
    assert snapshot["searchDisabled"] is False
    assert snapshot["unhandled"] == []


def test_real_repository_catalog_is_consumed_without_padding(backend_manifest):
    catalog = frontier.build_surfaces_manifest()
    assert catalog["ok"] is True and catalog["count"] > 0
    assert catalog["count"] == len(catalog["surfaces"])
    snapshot = run_catalog(backend_manifest, catalog)["afterEvents"]
    assert_catalog_loaded(snapshot, catalog)
    assert snapshot["surfaces"].count('class="surface-pill"') == min(12, catalog["count"])
    assert snapshot["prevDisabled"] is True
    assert snapshot["nextDisabled"] is (catalog["count"] <= 12)


def test_genuine_empty_registry_is_valid_not_unknown(backend_manifest, tmp_path, monkeypatch):
    catalog = producer_catalog(tmp_path, monkeypatch, [])
    assert catalog["ok"] is True
    assert catalog["summary"] == {
        "count": 0, "present": 0, "unavailable": 0, "label_counts": {}, "labels_valid": True,
    }
    snapshot = run_catalog(backend_manifest, catalog)["afterEvents"]
    assert_catalog_loaded(snapshot, catalog)
    assert "0 matching / 0 total" in snapshot["surfacePageStatus"]
    assert "unknown" not in snapshot["surfaces"]
    assert snapshot["prevDisabled"] is True and snapshot["nextDisabled"] is True


def test_missing_registry_error_is_not_a_healthy_empty_catalog(
    backend_manifest, tmp_path, monkeypatch
):
    with monkeypatch.context() as patch:
        patch.setattr(frontier, "_REPO_ROOT", tmp_path)
        catalog = frontier.build_surfaces_manifest()
    assert catalog["ok"] is False and catalog["count"] == 0
    snapshot = run_catalog(backend_manifest, catalog)["afterEvents"]
    assert_unavailable(snapshot)
    assert "registry not found" in snapshot["surfacesStatus"]


def test_all_labels_and_partial_unavailability_survive_without_catalog_failure(
    backend_manifest, tmp_path, monkeypatch
):
    entries = [
        (label.lower(), label + " fixture", f'const label = "{label}";')
        for label in frontier._VALID_LABELS
    ] + [("missing", "Missing asset", None), ("undeclared", "Undeclared label", "const x = 1;")]
    catalog = producer_catalog(tmp_path, monkeypatch, entries)
    assert catalog["summary"]["present"] == 7
    assert catalog["summary"]["unavailable"] == 2
    assert catalog["count"] == 8
    snapshot = run_catalog(backend_manifest, catalog)["afterEvents"]
    assert_catalog_loaded(snapshot, catalog)
    assert "Missing asset" in snapshot["surfaces"] and "Undeclared label" in snapshot["surfaces"]
    for label in (*frontier._VALID_LABELS, frontier.UNAVAILABLE):
        assert f">{label}</span>" in snapshot["surfaces"]


@pytest.mark.parametrize("body", ["policy", "valid", "non_json"])
def test_http_payment_response_is_rejected_before_json(backend_manifest, catalog, body):
    response = catalog if body == "valid" else {"error": "payment_required"}
    http = {SURFACES_EP: {"status": 402}}
    if body == "non_json":
        http[SURFACES_EP]["jsonError"] = "Unexpected token <"
    snapshot = run_catalog(backend_manifest, response, http=http)["afterEvents"]
    assert_unavailable(snapshot)
    assert "HTTP 402" in snapshot["surfacesStatus"]
    assert "payment required" in snapshot["surfacesStatus"]
    assert SURFACES_EP not in snapshot["jsonReads"]


@pytest.mark.parametrize("http", [
    {"status": 503}, {"jsonError": "Invalid JSON"}, {"networkError": "Network unavailable"},
])
def test_other_failed_reads_keep_catalog_unknown(backend_manifest, catalog, http):
    snapshot = run_catalog(backend_manifest, catalog, http={SURFACES_EP: http})["afterEvents"]
    assert_unavailable(snapshot)


_BAD_CATALOGS = [
    ("null-envelope", (), None),
    ("array-envelope", (), []),
    ("policy-envelope", (), {"error": "payment_required", "status": 402}),
    ("ok-missing", ("ok",), _MISSING),
    ("ok-false", ("ok",), False),
    ("ok-string", ("ok",), "true"),
    ("surfaces-missing", ("surfaces",), _MISSING),
    ("surfaces-object", ("surfaces",), {}),
    ("summary-missing", ("summary",), _MISSING),
    ("summary-array", ("summary",), []),
    ("count-missing", ("count",), _MISSING),
    ("count-string", ("count",), "1"),
    ("count-boolean", ("count",), True),
    ("count-negative", ("count",), -1),
    ("count-fractional", ("count",), 1.5),
    ("count-unsafe", ("count",), 9007199254740992),
    ("count-mismatch", ("count",), 2),
    ("summary-count-mismatch", ("summary", "count"), 0),
    ("summary-count-boolean", ("summary", "count"), True),
    ("present-count-mismatch", ("summary", "present"), 0),
    ("present-count-boolean", ("summary", "present"), True),
    ("unavailable-count-mismatch", ("summary", "unavailable"), 1),
    ("unavailable-count-negative", ("summary", "unavailable"), -1),
    ("labels-valid-missing", ("summary", "labels_valid"), _MISSING),
    ("labels-valid-false", ("summary", "labels_valid"), False),
    ("labels-valid-string", ("summary", "labels_valid"), "true"),
    ("histogram-array", ("summary", "label_counts"), []),
    ("histogram-missing-label", ("summary", "label_counts"), {}),
    ("histogram-extra-label", ("summary", "label_counts"), {"MODELED": 1, "UNKNOWN": 0}),
    ("histogram-count-mismatch", ("summary", "label_counts", "MODELED"), 2),
    ("histogram-count-boolean", ("summary", "label_counts", "MODELED"), True),
    ("null-entry", ("surfaces", 0), None),
    ("blank-id", ("surfaces", 0, "id"), "  "),
    ("nontext-title", ("surfaces", 0, "title"), 3),
    ("blank-asset", ("surfaces", 0, "asset"), ""),
    ("invalid-label", ("surfaces", 0, "label"), "UNKNOWN"),
    ("prototype-label", ("surfaces", 0, "label"), "constructor"),
    ("present-missing", ("surfaces", 0, "present"), _MISSING),
    ("present-not-boolean", ("surfaces", 0, "present"), "true"),
]


def changed(value, path, replacement):
    if not path:
        return copy.deepcopy(replacement)
    result = copy.deepcopy(value)
    target = result
    for key in path[:-1]:
        target = target[key]
    if replacement is _MISSING:
        del target[path[-1]]
    else:
        target[path[-1]] = replacement
    return result


@pytest.mark.parametrize("_name,path,value", _BAD_CATALOGS, ids=[row[0] for row in _BAD_CATALOGS])
def test_malformed_catalog_never_becomes_healthy_empty(
    backend_manifest, catalog, _name, path, value
):
    snapshot = run_catalog(backend_manifest, changed(catalog, path, value))["afterEvents"]
    assert_unavailable(snapshot)


def test_duplicate_ids_are_rejected_even_with_consistent_counts(backend_manifest, catalog):
    duplicate = copy.deepcopy(catalog)
    duplicate["surfaces"] *= 2
    duplicate["count"] = duplicate["summary"]["count"] = duplicate["summary"]["present"] = 2
    duplicate["summary"]["label_counts"] = {"MODELED": 2}
    assert_unavailable(run_catalog(backend_manifest, duplicate)["afterEvents"])


def test_missing_asset_cannot_claim_a_present_label(backend_manifest, catalog):
    contradiction = copy.deepcopy(catalog)
    contradiction["surfaces"][0].update(label="MEASURED", present=False)
    contradiction["summary"].update(present=0, label_counts={"MEASURED": 1})
    assert_unavailable(run_catalog(backend_manifest, contradiction)["afterEvents"])


def test_disabled_catalog_cannot_be_replaced_by_empty_results_on_events(backend_manifest):
    events = [
        {"id": "surface-search", "type": "input", "value": "fixture"},
        {"id": "surface-next", "type": "click"},
        {"id": "surface-prev", "type": "click"},
        {"id": "surface-search", "type": "input", "value": ""},
    ]
    output = run_catalog(backend_manifest, {"error": "payment_required"}, events=events)
    assert_unavailable(output["afterResize"])
    assert_unavailable(output["afterEvents"])
    for key in ("surfaces", "surfacesRollup", "surfaceFilters", "surfacePageStatus"):
        assert output["afterEvents"][key] == output["afterResize"][key]


@pytest.mark.parametrize("failure", ["renderer", "three_import", "controls_import"])
@pytest.mark.parametrize("catalog_available", [True, False])
def test_graphics_faults_do_not_block_independent_data_or_catalog_failure(
    backend_manifest, catalog, failure, catalog_available
):
    response = catalog if catalog_available else {"error": "payment_required"}
    snapshot = run_catalog(backend_manifest, response, failure=failure)["afterEvents"]
    if catalog_available:
        assert_catalog_loaded(snapshot, catalog)
    else:
        assert_unavailable(snapshot)
    assert snapshot["manifestStatus"].startswith("manifest reachable")
    for tile in backend_manifest["capabilities"]:
        assert tile["name"] in snapshot["grid"]
    assert snapshot["brainNodeCount"] == "7"
    assert snapshot["brainStatus"].startswith("Live status loaded.")
    assert snapshot["sceneHidden"] is True and snapshot["noticeHidden"] is False
    assert "3D view unavailable" in snapshot["noticeText"]
    assert snapshot["unhandled"] == []


def test_surface_text_and_attributes_are_escaped(backend_manifest, catalog):
    escaped = copy.deepcopy(catalog)
    escaped["surfaces"][0].update(
        id='fixture"><img src=x onerror=1>',
        title='<img src=x onerror=1> & "quoted"',
        asset='/static/a" onmouseover="1',
    )
    snapshot = run_catalog(backend_manifest, escaped)["afterEvents"]
    assert_catalog_loaded(snapshot, escaped)
    rendered = snapshot["surfaces"]
    assert "<img" not in rendered
    assert "&lt;img src=x onerror=1&gt; &amp; &quot;quoted&quot;" in rendered
    assert 'title="/static/a&quot; onmouseover=&quot;1"' in rendered
    assert 'href="/holographic#fixture%22%3E%3Cimg%20src%3Dx%20onerror%3D1%3E"' in rendered


def test_source_error_text_does_not_become_catalog_markup(backend_manifest):
    payload = {"ok": False, "error": '<img src=x onerror=1> payment required'}
    snapshot = run_catalog(backend_manifest, payload)["afterEvents"]
    assert_unavailable(snapshot)
    assert "<img" in snapshot["surfacesStatus"]  # textContent, never innerHTML.
    assert "<img" not in snapshot["surfaces"] + snapshot["surfacesRollup"]


def test_manifest_non_json_payment_keeps_http_reason_and_other_panels(backend_manifest, catalog):
    snapshot = run_catalog(
        backend_manifest, catalog,
        http={MANIFEST_EP: {"status": 402, "jsonError": "Unexpected token <"}},
    )["afterEvents"]
    assert snapshot["manifestStatus"].startswith("manifest unavailable:")
    assert "HTTP 402" in snapshot["manifestStatus"]
    assert "payment required" in snapshot["manifestStatus"]
    assert "err" in snapshot["manifestStatusClass"].split()
    assert MANIFEST_EP not in snapshot["jsonReads"]
    assert snapshot["manifestRollup"] == "" and snapshot["grid"] == ""
    assert_catalog_loaded(snapshot, catalog)
    assert snapshot["brainNodeCount"] == "7"


@pytest.mark.parametrize("manifest", [
    None, [], {"error": "payment_required"}, {"ok": True},
    {"ok": False, "capabilities": [], "summary": {"tiles": 0}},
    {"ok": True, "capabilities": {}, "summary": {"tiles": 0}},
    {"ok": True, "capabilities": [], "summary": []},
    {"ok": True, "capabilities": [], "summary": {"tiles": 1}},
    {"ok": True, "capabilities": [], "summary": {"tiles": False}},
])
def test_malformed_capability_envelope_cannot_render_healthy_empty(manifest, catalog):
    snapshot = run_catalog(manifest, catalog)["afterEvents"]
    assert snapshot["manifestStatus"].startswith("manifest unavailable:")
    assert "err" in snapshot["manifestStatusClass"].split()
    assert snapshot["manifestRollup"] == "" and snapshot["grid"] == ""
    assert_catalog_loaded(snapshot, catalog)
    assert snapshot["brainNodeCount"] == "7"
