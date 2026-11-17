#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute the full served module with synthetic I/O and optional graphics faults."""

import json
import re
import shutil
import subprocess

import pytest

import a11oy_frontier_page as frontier


DRIVER = r"""
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(readFileSync(0, 'utf8'));
const requests = [], imports = [], importResolvers = [], unhandled = [];
const windowEvents = new Map(), groups = [];
const metrics = {constructed: 0, renders: 0, animationFrames: 0, pixelRatio: null};
let controls = null;
process.on('unhandledRejection', error => unhandled.push(String(error)));

class Element {
  constructor(id = '') {
    this.id = id; this.hidden = false; this.textContent = ''; this.innerHTML = '';
    this.children = []; this.dataset = {}; this.disabled = false; this.value = '';
    this.style = {setProperty() {}};
  }
  addEventListener() {}
  removeEventListener() {}
  getBoundingClientRect() { return {height: 48}; }
  replaceChildren(...children) { this.children = children; }
  appendChild(child) { this.children.push(child); }
  querySelectorAll() { return []; }
  querySelector() { return null; }
}
const elements = new Map(input.ids.map(id => [id, new Element(id)]));
elements.get('scene-status').hidden = input.noticeInitiallyHidden;
elements.get('scene-status').textContent = input.noticeText;
const document = {
  hidden: false, documentElement: new Element(),
  getElementById: id => elements.get(id) || null,
  createElement: () => new Element(),
  querySelectorAll: () => [],
  addEventListener() {}, removeEventListener() {},
};
const position = () => ({set() {}, copy() {}});
class Spatial {
  constructor() { this.position = position(); this.rotation = {x: 0, y: 0}; this.children = []; }
  add(...children) { this.children.push(...children); }
  clear() { this.children = []; }
  updateProjectionMatrix() {}
}
class Group extends Spatial { constructor() { super(); groups.push(this); } }
class Geometry { setFromPoints() { return this; } }
class Material { constructor(values) { Object.assign(this, values); } }
class WebGLRenderer {
  constructor() {
    metrics.constructed++;
    if (input.failure === 'renderer') throw new Error('WebGL context unavailable');
  }
  setPixelRatio(value) { metrics.pixelRatio = value; }
  setSize() {}
  render() { metrics.renders++; }
  dispose() {}
}
class OrbitControls {
  constructor() { controls = this; }
  update() {}
  dispose() {}
}
const THREE = {
  WebGLRenderer, Scene: Spatial, PerspectiveCamera: Spatial,
  AmbientLight: Spatial, PointLight: Spatial, Mesh: Spatial, Group,
  Vector3: Spatial, Line: Spatial, IcosahedronGeometry: Geometry,
  SphereGeometry: Geometry, BufferGeometry: Geometry,
  MeshStandardMaterial: Material, LineBasicMaterial: Material,
};
const optionalImport = specifier => {
  imports.push(specifier);
  if ((input.failure === 'three_import' && specifier === 'three')
      || (input.failure === 'controls_import' && specifier.includes('OrbitControls')))
    return Promise.reject(new Error('Optional module unavailable'));
  const module = specifier === 'three' ? THREE : {OrbitControls};
  return input.lateImports
    ? new Promise(resolve => importResolvers.push(() => resolve(module)))
    : Promise.resolve(module);
};
const context = {
  document, console, __sceneImport: optionalImport,
  innerWidth: 1280, innerHeight: 800, devicePixelRatio: 2,
  matchMedia: query => ({
    matches: query.includes('prefers-reduced-motion') ? input.reducedMotion : input.compact,
    addEventListener() {}, removeEventListener() {},
  }),
  addEventListener: (name, callback) => {
    if (!windowEvents.has(name)) windowEvents.set(name, []);
    windowEvents.get(name).push(callback);
  },
  removeEventListener: (name, callback) =>
    windowEvents.set(name, (windowEvents.get(name) || []).filter(fn => fn !== callback)),
  requestAnimationFrame: () => ++metrics.animationFrames,
  cancelAnimationFrame() {},
  fetch: async url => {
    requests.push(url);
    if (!Object.hasOwn(input.responses, url)) throw new Error('Unexpected request: ' + url);
    return {ok: true, status: 200, json: async () => input.responses[url]};
  },
};
context.window = context;
// Only dependency loading is substituted. All application bootstrap code runs.
const script = input.script
  .replaceAll("import('three')", "__sceneImport('three')")
  .replaceAll("import('three/addons/OrbitControls.js')",
              "__sceneImport('three/addons/OrbitControls.js')");
const snapshot = () => JSON.parse(JSON.stringify({
  requests, imports, unhandled, metrics,
  groupSizes: groups.map(group => group.children.length),
  autoRotate: controls ? controls.autoRotate : null,
  grid: elements.get('grid').innerHTML,
  manifestStatus: elements.get('status').textContent,
  brainStatus: elements.get('brain-result').textContent,
  brainNodeCount: elements.get('brain-node-count').textContent,
  surfaces: elements.get('surfaces-list').innerHTML,
  surfacesStatus: elements.get('surfaces-status').textContent,
  sceneHidden: elements.get('scene').hidden,
  noticeHidden: elements.get('scene-status').hidden,
  noticeText: elements.get('scene-status').textContent,
}));
(async () => {
  vm.runInNewContext(script, context, {timeout: 5000});
  await new Promise(resolve => setImmediate(resolve));
  const beforeImports = snapshot();
  importResolvers.forEach(resolve => resolve());
  await new Promise(resolve => setImmediate(resolve));
  const afterImports = snapshot();
  for (const callback of windowEvents.get('resize') || []) callback();
  await new Promise(resolve => setImmediate(resolve));
  process.stdout.write(JSON.stringify({beforeImports, afterImports, afterResize: snapshot()}));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


@pytest.fixture
def backend_manifest(monkeypatch):
    import szl_frontier_manifest as manifest

    operator = {
        "name": "Fixture operator", "category": "test", "status": "IDLE",
        "label": manifest.MEASURED, "ok": True, "running": False,
        "provenance": {"endpoint": "/api/a11oy/v1/operator/status"},
        "operational_evidence": {
            "predicate": "operator reports running=true",
            "satisfied": False, "reasons": ["operator_stopped"],
        },
    }
    composite = {
        "name": "Fixture composite", "category": "test", "status": "UNAVAILABLE",
        "label": manifest.UNAVAILABLE, "ok": True, "on_artifact_minted": False,
        "provenance": {"endpoint": "/api/a11oy/v1/provenance/chain"},
        "operational_evidence": {
            "predicate": "a composite artifact is present",
            "satisfied": False, "reasons": ["artifact_not_minted"],
        },
    }
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (lambda: operator, operator["name"], "test", operator["provenance"]),
    ])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance", lambda: composite)
    return manifest._build_manifest()


def run_page(manifest, **options):
    node = shutil.which("node")
    assert node, "Node is required for full Frontier module regression tests"
    html = frontier._page_html("a11oy")
    notice = re.search(r'<div id="scene-status"([^>]*)>([^<]*)<', html)
    assert notice, "Optional graphics need a visible, accessible fallback notice"
    assert 'role="status"' in notice[1] and 'aria-live="polite"' in notice[1]
    payload = {
        "script": html.split('<script type="module">', 1)[1].split("</script>", 1)[0],
        "ids": re.findall(r'\bid="([^"]+)"', html),
        "noticeText": notice[2].strip(),
        "noticeInitiallyHidden": " hidden" in notice[1],
        "failure": None, "lateImports": False, "reducedMotion": False, "compact": False,
        "responses": {
            "/api/a11oy/v1/frontier/manifest": manifest,
            "/api/a11oy/v1/fashion": {"lanes": [{"id": "fixture", "job": "test data"}]},
            "/api/a11oy/v1/brain/stats": {
                "label": "SAMPLE", "node_count": 7, "distinct_artifacts": 2,
            },
            "/api/a11oy/v1/brain/health/corpus-sources": {
                "label": "SAMPLE", "summary": {"counts": {"ADMITTED": 3}, "quarantined_entries": 1},
            },
            "/api/a11oy/v1/frontier/surfaces": {
                "ok": True, "count": 1,
                "surfaces": [{"id": "fixture", "title": "Fixture surface",
                              "label": "MODELED", "asset": "/static/3d/fixture.js",
                              "present": True}],
                "summary": {"count": 1, "present": 1, "unavailable": 0,
                            "label_counts": {"MODELED": 1}, "labels_valid": True},
            },
        },
    }
    payload.update(options)
    result = subprocess.run(
        [node, "--eval", DRIVER], input=json.dumps(payload),
        text=True, encoding="utf-8", capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def assert_data_loaded(snapshot, manifest):
    assert set(snapshot["requests"]) == {
        "/api/a11oy/v1/fashion", "/api/a11oy/v1/frontier/manifest",
        "/api/a11oy/v1/brain/stats", "/api/a11oy/v1/brain/health/corpus-sources",
        "/api/a11oy/v1/frontier/surfaces",
    }
    assert snapshot["unhandled"] == []
    for tile in manifest["capabilities"]:
        assert tile["name"] in snapshot["grid"]
        assert 'data-readiness-state="' + tile["operational_readiness"]["state"] + '"' in snapshot["grid"]
        for reason in tile["operational_readiness"]["reasons"]:
            assert "<code>" + reason + "</code>" in snapshot["grid"]
    assert snapshot["manifestStatus"].startswith("manifest reachable")
    assert snapshot["brainStatus"].startswith("Live status loaded.")
    assert snapshot["brainNodeCount"] == "7"
    assert "Fixture surface" in snapshot["surfaces"]
    assert snapshot["surfacesStatus"].startswith("live")


@pytest.mark.parametrize("failure", ["renderer", "three_import", "controls_import"])
def test_optional_graphics_failure_does_not_block_real_manifest_or_data_panels(backend_manifest, failure):
    output = run_page(backend_manifest, failure=failure)
    snapshot = output["afterResize"]
    assert_data_loaded(snapshot, backend_manifest)
    assert snapshot["sceneHidden"] is True
    assert snapshot["noticeHidden"] is False
    assert "3D view unavailable" in snapshot["noticeText"]
    assert "Data panels load independently." in snapshot["noticeText"]
    assert snapshot["metrics"]["animationFrames"] == 0
    assert set(snapshot["imports"]) == {"three", "three/addons/OrbitControls.js"}


@pytest.mark.parametrize("reduced,compact", [(False, False), (True, False), (False, True)])
def test_late_graphics_imports_replay_loaded_tiles_and_keep_motion_policy(backend_manifest, reduced, compact):
    output = run_page(
        backend_manifest, lateImports=True, reducedMotion=reduced, compact=compact,
    )
    before = output["beforeImports"]
    assert_data_loaded(before, backend_manifest)
    assert before["metrics"]["constructed"] == 0
    after = output["afterImports"]
    assert_data_loaded(after, backend_manifest)
    assert after["sceneHidden"] is False and after["noticeHidden"] is True
    assert after["groupSizes"] == [len(backend_manifest["capabilities"])] * 2
    assert after["autoRotate"] is (not (reduced or compact))
    assert after["metrics"]["pixelRatio"] == (1 if compact else 2)
    assert after["metrics"]["animationFrames"] == (0 if reduced or compact else 1)
    assert output["afterResize"]["metrics"]["renders"] == after["metrics"]["renders"] + 1
