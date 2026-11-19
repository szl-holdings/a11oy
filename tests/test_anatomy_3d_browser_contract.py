#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the seven shipped anatomy pages in an isolated, offline browser.

Page builders and inert constants are AST-extracted. Registered-GET integration
uses the backend contract suite's fake sources and effect traps; real signer,
provider, and persistence dependencies are never imported. All browser HTTP
requests are intercepted and fulfilled from labelled fixtures. These checks
qualify client presentation and passive polling, not production readiness.

Run: python -m pytest -q tests/test_anatomy_3d_browser_contract.py
Optional: SZL_TEST_CHROMIUM_EXECUTABLE selects an installed local browser;
SZL_ANATOMY_BROWSER_ARTIFACT_DIR receives screenshots and a fixture report.
Missing Playwright or a browser is a failure, including in CI.
"""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import typing
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "szl_anatomy_3d.py"
VENDOR = ROOT / "static-vendor" / "three.min.js"
STYLE_ASSETS = {
    "/assets/szl/szl-design-system.css": ROOT / "console/assets/szl/szl-design-system.css",
    "/assets/szl/szl-console.css": ROOT / "console/assets/szl/szl-console.css",
}
ORIGIN = "https://anatomy-fixture.invalid"
PAYLOAD = '<img src="/injected" onerror="window.__fixtureInjected=1"><svg onload="window.__fixtureInjected=2"></svg>'
CASES = [
    ("yuyay-13", "_page_yuyay13", "heart", "/api/a11oy/v4/yuyay-13/vote"),
    ("khipu-chain-3d", "_page_khipu_chain", "blood", "/api/a11oy/v4/khipu/chain"),
    ("immune-3d", "_page_immune", "immune", "/api/a11oy/v4/immune/observation"),
    ("lambda-spine-3d", "_page_lambda_spine", "skeleton", "/api/a11oy/v4/lambda/convergence"),
    ("nervous-3d", "_page_nervous", "nervous", "/api/a11oy/v4/spans/recent"),
    ("wires-3d", "_page_wires", "wires", "/api/a11oy/v4/orchestrate/routing"),
    ("body-3d", "_page_body", "body", "/api/a11oy/v4/body/composed"),
]

INIT = """(() => {
  window.__anatomyIntervals = new Map();
  let intervalId = 0;
  window.__anatomyUnhandled = [];
  window.addEventListener('unhandledrejection', event => {
    window.__anatomyUnhandled.push(String(event.reason));
  });
  window.setInterval = (callback, delay, ...args) => {
    if (typeof callback !== 'function') throw new Error('Unexpected string timer');
    const id = ++intervalId;
    window.__anatomyIntervals.set(id, () => callback(...args));
    return id;
  };
  window.clearInterval = id => window.__anatomyIntervals.delete(id);
  window.__runAnatomyPolls = async () => {
    await Promise.all([...window.__anatomyIntervals.values()].map(callback => callback()));
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  };
})();"""

SCENE_COUNTS = """() => {
  let meshes = 0, lines = 0;
  scene.traverse(object => { if (object.isMesh) meshes++; if (object.isLine) lines++; });
  return { meshes, lines, pickable: pickable.length,
    geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
}"""

LAYOUT_METRICS = """() => {
  const rect = selector => {
    const box = document.querySelector(selector).getBoundingClientRect();
    return {top:box.top, bottom:box.bottom, left:box.left, right:box.right,
            width:box.width, height:box.height};
  };
  const renderSize = renderer.getSize(new THREE.Vector2());
  return {header:rect('header'), observation:rect('#observation'), canvas:rect('#c'),
    footer:rect('footer'), viewportWidth:document.documentElement.clientWidth,
    viewportHeight:innerHeight, scrollWidth:document.documentElement.scrollWidth,
    scrollHeight:document.documentElement.scrollHeight, scrollY,
    rendererWidth:renderSize.x, rendererHeight:renderSize.y, cameraAspect:camera.aspect};
}"""


def _page_namespace():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and (
            node.name.startswith("_page_") or node.name in {"_palette", "_shell", "_observation_page"}
        ):
            assert not any(isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node))
            selected.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError):
                if target.id != "ANCHORS":
                    continue
                assert not any(isinstance(child, ast.Call) for child in ast.walk(node.value))
            selected.append(node)
    namespace = {
        "json": json, "html": html, "escape": html.escape, "Dict": typing.Dict, "List": typing.List,
        "Any": typing.Any, "Optional": typing.Optional,
        "_fingerprint": lambda: "unavailable",
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    assert {case[1] for case in CASES}.issubset(namespace)
    return namespace


def _observed(kind, namespace):
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    axes = [dict(axis=a["axis"], id=a["id"], score=0.9, floor=0.8,
                 verdict=None, evaluator="sample") for a in namespace["YUYAY_13"]]
    organs = ["brain", "heart", "blood", "immune", "skeleton", "nervous", "wires"]
    anatomies = [{"anatomy": organ, "state": "OBSERVED" if organ == "heart" else "MODELED",
                  "evidence_class": "SAMPLE" if organ == "heart" else "MODELED",
                  "reason": "OFFLINE TEST FIXTURE", "execution_authorized": False,
                  "signature_verified": False} for organ in organs]
    data = {
        "heart": {"lambda_aggregate": 0.9, "passing": True, "axes": axes},
        "blood": {"organ": "yuyay", "depth": 1, "head": "a" * 64, "returned_records": 1, "truncated": False,
                  "pendants": [{"seq": 1, "digest": "a" * 64, "prev": "0" * 64,
                                "action": "OFFLINE TEST FIXTURE", "organ": "yuyay", "ns": "a11oy",
                                "ts": 1.0, "payload_digest": "c" * 64}]},
        "immune": {"gate_count": 8, "gate_observations": [], "cross_organ_probe_performed": False},
        "skeleton": {"lambda": 0.9, "claim_status": "Conjecture 1; OFFLINE TEST FIXTURE",
                     "convergence_series": [0.9] * 13, "parent_receipt_sha256": None},
        "nervous": {"span_count": None, "trace_count": 1, "expired_rows": 0,
                    "correlation_only": True, "traces": [
            {"trace_ref": "b" * 64, "name": "Process trace summary",
             "started_at": observed_at, "duration_ms": 0.0,
             "span_count": 1, "status": "OK"}]},
        "wires": {"chosen": {"tier": "OFFLINE TEST FIXTURE", "energy": 0.5}, "routes": [
            {"tier": "OFFLINE TEST FIXTURE", "energy": 0.5}], "routing_performed": False,
            "energy_cost_scope": "ADVISORY_INPUT"},
        "body": {"anatomy_count": 7, "anatomies": anatomies, "observed_count": 1,
                 "operational_readiness": "NOT_ESTABLISHED", "doctrine": {"locked_formula_count": 8}},
    }[kind]
    return {
        "schema": "szl.anatomy.observation/v1", "ns": "a11oy", "kind": kind,
        "mode": "READ_ONLY", "state": "MODELED" if kind == "immune" else "OBSERVED",
        "evidence_class": "MODELED" if kind == "immune" else "SAMPLE",
        "reason": "OFFLINE_TEST_FIXTURE", "observed_at": None if kind == "immune" else observed_at,
        "age_seconds": None if kind == "immune" else 1, "max_age_seconds": 60, "storage_writes": 0,
        "receipt_minted_on_get": False, "execution_authorized": False,
        "model_invoked": False, "execution_performed": False, "identity_binding": "NOT_ESTABLISHED",
        "signature_verified": False, "signature_verification": "NOT_PERFORMED",
        "receipt_signature_status": "NOT_ESTABLISHED", "signature_count": 0, "receipt_sha256": None,
        "chain_verified": False, "chain_integrity": {"state": "NOT_ESTABLISHED", "scope": "NONE",
            "checked_records": 0, "prefix_verified": False}, "joules_measured": None,
        "energy_label": "UNAVAILABLE", "bounded": True,
        "data_scope": "PROCESS_WIDE_NOT_NAMESPACE_BOUND" if kind == "nervous" else "PROCESS_LOCAL_NONAUTHORITATIVE",
        "source_revision": None, "runtime_boot_id": None, "data": data,
    }


@pytest.fixture(scope="module")
def source_pages():
    return _page_namespace()


@pytest.fixture(scope="module")
def default_get_payloads():
    helper_path = ROOT / "tests/test_anatomy_3d_observation_contract.py"
    spec = importlib.util.spec_from_file_location("anatomy_browser_offline_api_fixtures", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # The backend contract suite owns its strict import stubs and fake app;
    # obtain current registered handler output, not duplicated frozen snapshots.
    payloads = helper.default_projection_responses()
    assert {case[2] for case in CASES}.issubset(payloads)
    return payloads


@pytest.fixture(scope="module")
def browser_runtime():
    artifact_setting = os.environ.get("SZL_ANATOMY_BROWSER_ARTIFACT_DIR")
    artifact_dir = Path(artifact_setting).resolve() if artifact_setting else None
    if artifact_dir:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    report = {"scope": "OFFLINE_BROWSER_FIXTURES_ONLY", "production_readiness_claimed": False,
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "vendor_sha256": hashlib.sha256(VENDOR.read_bytes()).hexdigest(), "cases": []}
    with sync_playwright() as controller:
        explicit = os.environ.get("SZL_TEST_CHROMIUM_EXECUTABLE")
        candidates = [Path(explicit)] if explicit else [
            Path(controller.chromium.executable_path),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        ]
        executable = next((str(path) for path in candidates if path.is_file()), None)
        assert executable, "Install the CI-pinned Playwright Chromium or select an installed browser"
        # Launch a temporary profile; never connect to a user browser or forward credentials.
        browser_env = {key: value for key, value in os.environ.items() if key.upper() in {
            "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "HOME", "USERPROFILE",
            "LOCALAPPDATA", "APPDATA", "DISPLAY", "XDG_RUNTIME_DIR", "LANG", "LC_ALL",
        }}
        browser = controller.chromium.launch(
            executable_path=executable, headless=True, env=browser_env,
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-gpu",
                  "--disable-background-networking", "--disable-component-update", "--no-first-run"],
        )
        report["browser_version"] = browser.version
        try:
            yield browser, report, artifact_dir
        finally:
            browser.close()
            if artifact_dir:
                (artifact_dir / "anatomy-browser-report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8")


class OfflinePage:
    def __init__(self, runtime, namespace, case, mode="good", payload=None, viewport=None):
        browser, self.report, self.artifact_dir = runtime
        self.slug, builder, kind, self.endpoint = case
        self.mode = mode
        self.payload = copy.deepcopy(payload) if payload is not None else _observed(kind, namespace)
        self.requests, self.unexpected, self.errors = [], [], []
        self.layouts = []
        self.context = browser.new_context(viewport=viewport or {"width": 1200, "height": 800}, service_workers="block")
        self.context.set_default_timeout(5000)
        self.context.add_init_script(INIT)
        self.html = namespace[builder]("a11oy")
        self.vendor = VENDOR.read_text(encoding="utf-8")
        self.context.route("**/*", self._intercept)
        self.context.route_web_socket("**/*", self._block_socket)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        try:
            self.page.goto(ORIGIN + "/" + self.slug, wait_until="load")
            assert not self.errors, self.errors
            self.wait_status()
            self.page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        except BaseException:
            self.close("load-failure")
            raise

    def _intercept(self, route):
        request = route.request
        self.requests.append({"method": request.method, "url": request.url})
        url = urlsplit(request.url)
        if request.method != "GET" or url.scheme + "://" + url.netloc != ORIGIN:
            self.unexpected.append(self.requests[-1])
            route.abort()

        elif url.path == "/" + self.slug:
            route.fulfill(status=200, content_type="text/html", body=self.html)
        elif url.path == "/anatomy-three.min.js":
            route.fulfill(status=200, content_type="application/javascript", body=self.vendor)
        elif url.path in STYLE_ASSETS:
            route.fulfill(status=200, content_type="text/css", body=STYLE_ASSETS[url.path].read_text(encoding="utf-8"))
        elif url.path == self.endpoint:
            query = parse_qs(url.query, keep_blank_values=True)
            allowed_queries = [{"organ": ["yuyay"]}, {"organ": ["yuyay"], "since": ["0"]}] if self.slug == "khipu-chain-3d" else [{}]
            if query not in allowed_queries:
                self.unexpected.append(self.requests[-1])
                route.abort()
                return
            if self.mode == "http_error":
                route.fulfill(status=503, json={"state": "UNAVAILABLE"})
            elif self.mode == "network_error":
                route.abort("failed")
            elif self.mode == "bad_json":
                route.fulfill(status=200, content_type="application/json", body="{invalid")
            elif self.mode == "bad_shape":
                broken = copy.deepcopy(self.payload)
                broken["data"] = None
                route.fulfill(status=200, json=broken)
            elif self.mode == "empty_object":
                route.fulfill(status=200, json={})
            elif self.mode in {"schema_mismatch", "namespace_mismatch"}:
                broken = copy.deepcopy(self.payload)
                broken["schema" if self.mode == "schema_mismatch" else "ns"] = "unexpected-fixture"
                route.fulfill(status=200, json=broken)
            elif self.mode.startswith("state_"):
                old_data = copy.deepcopy(self.payload)
                old_data["state"] = self.mode.removeprefix("state_").upper()
                old_data["reason"] = "OFFLINE_NONOBSERVED_FIXTURE_WITH_OLD_DATA"
                route.fulfill(status=200, json=old_data)
            else:
                route.fulfill(status=200, json=self.payload)
        else:
            self.unexpected.append(self.requests[-1])
            route.abort()

    def _block_socket(self, socket):
        attempt = {"method": "WEBSOCKET", "url": socket.url}
        self.requests.append(attempt)
        self.unexpected.append(attempt)
        socket.close()

    def poll(self):
        before = len(self.requests)
        assert self.page.evaluate("window.__anatomyIntervals.size") == 1
        self.page.evaluate("window.__runAnatomyPolls()")
        self.wait_status()
        assert len(self.requests) > before, "The poll timer must perform an intercepted observation read"
        self.assert_passive()

    def wait_status(self):
        expected = [self.payload["state"]] if self.mode == "good" else (
            ["STALE", "UNAVAILABLE"] if self.mode == "state_stale" else ["UNAVAILABLE"])
        self.page.wait_for_function(
            r"expected => expected.includes(document.querySelector('#fstat').textContent.trim().split(/\s+/, 1)[0])", arg=expected)

    def assert_passive(self):
        assert not self.unexpected, self.unexpected
        assert all(request["method"] == "GET" for request in self.requests)
        assert not self.errors, self.errors
        assert self.page.evaluate("window.__anatomyUnhandled") == []

    def counts(self):
        return self.page.evaluate(SCENE_COUNTS)

    def assert_stage_layout(self):
        layout = self.page.evaluate(LAYOUT_METRICS)
        self.layouts.append(layout)
        canvas = layout["canvas"]
        assert layout["observation"]["top"] >= layout["header"]["bottom"] - 1, layout
        assert canvas["top"] >= max(layout["header"]["bottom"], layout["observation"]["bottom"]) - 1, layout
        assert canvas["bottom"] <= layout["footer"]["top"] + 1, layout
        assert canvas["height"] >= 320 and canvas["width"] >= 280, layout
        assert canvas["left"] >= -1 and canvas["right"] <= layout["viewportWidth"] + 1, layout
        assert layout["scrollWidth"] <= layout["viewportWidth"] + 1, layout
        assert abs(layout["rendererWidth"] - canvas["width"]) <= 1, layout
        assert abs(layout["rendererHeight"] - canvas["height"]) <= 1, layout
        assert abs(layout["cameraAspect"] - canvas["width"] / canvas["height"]) <= 0.01, layout
        return layout

    def assert_good_state(self):
        status = self.page.locator("#fstat").inner_text()
        assert status.split(maxsplit=1)[0] == self.payload["state"], status

    def unavailable(self, expected=("UNAVAILABLE",)):
        status = self.page.locator("#fstat").inner_text()
        assert status.split(maxsplit=1)[0] in expected, status
        assert self.page.locator("#card.open").count() == 0

    def close(self, label):
        entry = {"page": self.slug, "case": label, "requests": self.requests,
                 "unexpected": self.unexpected, "browser_errors": self.errors, "layouts": self.layouts}
        if self.artifact_dir and label in {"passive-render", "narrow-layout", "max-routes-layout", "load-failure"}:
            try:
                self.page.screenshot(path=str(self.artifact_dir / (self.slug + "-" + label + ".png")), full_page=True)
            except Exception as error:
                entry["screenshot_error"] = type(error).__name__
        self.report["cases"].append(entry)
        self.context.close()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_pages_render_local_r128_and_poll_without_effects(browser_runtime, source_pages, case):
    client = OfflinePage(browser_runtime, source_pages, case)
    try:
        client.assert_good_state()
        assert client.page.evaluate("THREE.REVISION") == "128"
        assert client.page.evaluate("!renderer.getContext().isContextLost()")
        assert client.page.evaluate("renderer.info.render.calls") > 0
        client.assert_stage_layout()
        assert client.page.evaluate("""() => Array.from(document.styleSheets).some(sheet =>
          sheet.href && new URL(sheet.href).pathname === '/assets/szl/szl-design-system.css' && sheet.cssRules.length > 0)
        """)
        client.assert_passive()
        baseline = client.counts()
        for _ in range(6):
            client.poll()
            client.assert_good_state()
        assert client.counts() == baseline, "Repeated observations must not leak meshes, pick targets, or GPU resources"
    finally:
        client.close("passive-render")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_narrow_pages_keep_useful_stage_and_scroll(browser_runtime, source_pages, case):
    client = OfflinePage(browser_runtime, source_pages, case, viewport={"width": 360, "height": 640})
    try:
        client.page.emulate_media(reduced_motion="reduce")
        layout = client.assert_stage_layout()
        assert layout["scrollHeight"] > layout["viewportHeight"], "The narrow page must scroll instead of compressing the stage"
        client.page.locator("#c").scroll_into_view_if_needed()
        client.page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        layout = client.assert_stage_layout()
        assert layout["scrollY"] > 0, layout
        assert layout["canvas"]["top"] >= -1 and layout["canvas"]["bottom"] <= layout["viewportHeight"] + 1, layout
        target = client.page.evaluate("""() => {
          scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
          const bounds = cv.getBoundingClientRect();
          for (const object of pickable) {
            if (!object.visible || !object.userData.formula) continue;
            const points = [object.getWorldPosition(new THREE.Vector3())];
            // A torus or knot can be hollow at its center; sample real triangle interiors.
            const positions = object.geometry.getAttribute('position'), indices = object.geometry.index;
            const count = indices ? indices.count : positions.count;
            for (let index = 0; index + 2 < Math.min(count, 384); index += 3) {
              const center = new THREE.Vector3();
              for (let corner = 0; corner < 3; corner++)
                center.add(new THREE.Vector3().fromBufferAttribute(positions,
                  indices ? indices.getX(index + corner) : index + corner));
              points.push(center.multiplyScalar(1 / 3).applyMatrix4(object.matrixWorld));
            }
            for (const worldPoint of points) {
              const point = worldPoint.project(camera);
              // Browser MouseEvent coordinates are integer pixels; validate that exact ray.
              const x = Math.round(bounds.left + (point.x + 1) * bounds.width / 2);
              const y = Math.round(bounds.top + (1 - point.y) * bounds.height / 2);
              const probe = new THREE.Raycaster();
              probe.setFromCamera(new THREE.Vector2(
                ((x - bounds.left) / bounds.width) * 2 - 1,
                -((y - bounds.top) / bounds.height) * 2 + 1), camera);
              const hit = probe.intersectObjects(pickable, true)[0];
              if (point.z > -1 && point.z < 1 && x > bounds.left + 8 && x < bounds.right - 8 &&
                  y > bounds.top + 8 && y < bounds.bottom - 8 && document.elementFromPoint(x, y) === cv && hit) {
                let owner = hit.object;
                while (owner && !owner.userData.formula) owner = owner.parent;
                if (owner) return {x, y, name:owner.userData.formula.name};
              }
            }
          }
          return null;
        }""")
        assert target is not None, "No modeled shape can be reached inside the scrolled canvas"
        client.page.mouse.click(target["x"], target["y"])
        assert client.page.locator("#card.open").count() == 1, "Picking must use the canvas rectangle after scrolling"
        assert client.page.locator("#card h3").inner_text() == target["name"]
        client.page.keyboard.press("Escape")
        client.page.locator("footer").scroll_into_view_if_needed()
        footer = client.page.locator("footer").bounding_box()
        assert footer["y"] >= -1 and footer["y"] + footer["height"] <= 641, footer
        client.assert_passive()
    finally:
        client.close("narrow-layout")


def test_sixteen_route_meshes_fit_narrow_canvas(browser_runtime, source_pages):
    case = next(case for case in CASES if case[2] == "wires")
    payload = _observed("wires", source_pages)
    payload["data"]["routes"] = [{"tier": f"OFFLINE_ROUTE_{index}", "energy": index / 10} for index in range(16)]
    payload["data"]["chosen"] = copy.deepcopy(payload["data"]["routes"][0])
    client = OfflinePage(browser_runtime, source_pages, case, payload=payload, viewport={"width": 360, "height": 640})
    try:
        client.page.emulate_media(reduced_motion="reduce")
        client.page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        client.assert_good_state()
        client.assert_stage_layout()
        bounds = client.page.evaluate("""() => {
          scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
          return pickable.filter(object => object.userData.observation).map(object => {
            const box = new THREE.Box3().setFromObject(object), points = [];
            for (const x of [box.min.x, box.max.x])
              for (const y of [box.min.y, box.max.y])
                for (const z of [box.min.z, box.max.z])
                  points.push(new THREE.Vector3(x,y,z).project(camera));
            return {name:object.userData.formula.name,
              minX:Math.min(...points.map(p=>p.x)), maxX:Math.max(...points.map(p=>p.x)),
              minY:Math.min(...points.map(p=>p.y)), maxY:Math.max(...points.map(p=>p.y)),
              minZ:Math.min(...points.map(p=>p.z)), maxZ:Math.max(...points.map(p=>p.z))};
          });
        }""")
        assert len(bounds) == 16
        assert all(-1 <= item["minX"] <= item["maxX"] <= 1 and
                   -1 <= item["minY"] <= item["maxY"] <= 1 and
                   -1 <= item["minZ"] <= item["maxZ"] <= 1 for item in bounds), bounds
        client.assert_passive()
    finally:
        client.close("max-routes-layout")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
@pytest.mark.parametrize("failure", [
    "http_error", "network_error", "bad_json", "bad_shape", "empty_object",
    "schema_mismatch", "namespace_mismatch", "state_stale", "state_empty", "state_unavailable",
])
def test_failed_reads_clear_previous_observation(browser_runtime, source_pages, case, failure):
    client = OfflinePage(browser_runtime, source_pages, case, mode="http_error")
    try:
        client.unavailable()
        empty = client.counts()
        client.mode = "good"
        client.poll()
        client.assert_good_state()
        client.page.evaluate("showCard({id:'FIXTURE',name:'Previous observed fixture'}, 'previous evidence')")
        assert client.page.locator("#card.open").count() == 1
        client.mode = failure
        client.poll()
        expected = ("STALE", "UNAVAILABLE") if failure == "state_stale" else ("UNAVAILABLE",)
        client.unavailable(expected)
        assert client.counts() == empty, "Failed read retained old observation geometry or pick targets"
        assert "previous evidence" not in client.page.locator("#card").inner_text()
    finally:
        client.close(failure)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_evidence_card_treats_untrusted_fields_as_text(browser_runtime, source_pages, case):
    client = OfflinePage(browser_runtime, source_pages, case)
    try:
        client.assert_good_state()
        fields = {key: PAYLOAD for key in ("id", "name", "axis", "lean", "leanStatus", "status", "severity", "note")}
        fields["doi"] = 'javascript:window.__fixtureInjected=3'
        client.page.evaluate("([fields, extra]) => showCard(fields, extra)", [fields, PAYLOAD])
        card = client.page.locator("#card")
        assert PAYLOAD in card.text_content()
        assert card.locator("img,svg,script,iframe,object,[onerror],[onload]").count() == 0
        assert client.page.evaluate("window.__fixtureInjected") is None
        assert all(url.startswith("https://doi.org/") for url in card.locator("a").evaluate_all("links => links.map(a => a.href)"))
        client.assert_passive()
    finally:
        client.close("inert-text")


def test_untrusted_trace_name_is_rejected_without_active_html(browser_runtime, source_pages):
    case = next(case for case in CASES if case[2] == "nervous")
    client = OfflinePage(browser_runtime, source_pages, case)
    try:
        malicious_name = '<img src="/injected" onerror="window.__fixtureInjected=1">'
        client.page.evaluate("showCard({name:'Previous trace'}, 'previous trace evidence')")
        client.payload["data"]["traces"][0]["name"] = malicious_name
        client.page.evaluate("window.__runAnatomyPolls()")
        client.page.wait_for_function("document.querySelector('#fstat').textContent.includes('UNAVAILABLE')")
        client.unavailable()
        card = client.page.locator("#card")
        assert "previous trace evidence" not in card.text_content()
        assert card.locator("img,svg,script,iframe,object,[onerror],[onload]").count() == 0
        assert client.page.evaluate("window.__fixtureInjected") is None
        client.assert_passive()
    finally:
        client.close("rejected-trace-text")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_page_restore_resumes_one_passive_poll_timer(browser_runtime, source_pages, case):
    client = OfflinePage(browser_runtime, source_pages, case)
    try:
        client.assert_good_state()
        client.page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide', {persisted:true}))")
        assert client.page.evaluate("window.__anatomyIntervals.size") == 0
        client.unavailable()
        stopped_count = len(client.requests)
        client.page.evaluate("window.__runAnatomyPolls()")
        assert len(client.requests) == stopped_count
        client.page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
        client.wait_status()
        client.assert_good_state()
        assert client.page.evaluate("window.__anatomyIntervals.size") == 1
        client.page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
        client.wait_status()
        assert client.page.evaluate("window.__anatomyIntervals.size") == 1
        client.poll()
    finally:
        client.close("page-restore")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_registered_default_get_envelopes_reach_browser(browser_runtime, source_pages, default_get_payloads, case):
    payload = default_get_payloads[case[2]]
    client = OfflinePage(browser_runtime, source_pages, case, payload=payload)
    try:
        client.page.wait_for_function(
            "reason => document.querySelector('#fstat').textContent.includes(reason)", arg=payload["reason"])
        client.assert_good_state()
        assert payload["state"] in {"MODELED", "UNAVAILABLE", "STALE"}
        assert client.page.evaluate("THREE.REVISION") == "128"
        assert client.page.evaluate("!renderer.getContext().isContextLost()")
        assert client.page.evaluate("observationGroup.children.length") == 0
        assert client.page.locator("#card.open").count() == 0
        client.poll()
        assert payload["reason"] in client.page.locator("#fstat").inner_text()
        client.assert_passive()
    finally:
        client.close("registered-default")
