#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Focused contracts for the event-driven A11oy public experience frontend."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "console" / "assets" / "a11oy-public-experience-v1.js"
CSS_PATH = ROOT / "console" / "assets" / "a11oy-public-experience-v1.css"
RENDERER_PATH = ROOT / "static" / "a11oy_landing.js"

CONTROLLER = CONTROLLER_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
RENDERER = RENDERER_PATH.read_text(encoding="utf-8")


def test_assets_are_licensed_bounded_and_syntactically_balanced() -> None:
    for source in (CONTROLLER, CSS, RENDERER):
        assert "SPDX-License-Identifier: Apache-2.0" in source[:240]

    without_comments = re.sub(r"/\*.*?\*/", "", CSS, flags=re.DOTALL)
    assert without_comments.count("{") == without_comments.count("}")
    assert len(CONTROLLER.encode("utf-8")) < 80_000
    assert len(CSS.encode("utf-8")) < 50_000
    assert len(RENDERER.encode("utf-8")) < 35_000


def test_controller_uses_only_the_versioned_same_origin_experience_api() -> None:
    for endpoint in (
        'API_ROOT + "/health"',
        'API_ROOT + "/estate"',
        'API_ROOT + "/scenarios"',
        'API_ROOT + "/sessions"',
        'API_ROOT + "/sessions/"',
        '"/events"',
        '"/approve"',
        'API_ROOT + "/receipts/"',
        '"/verify"',
    ):
        assert endpoint in CONTROLLER

    assert 'var API_ROOT = "/api/experience/v1"' in CONTROLLER
    assert "url.origin !== win.location.origin" in CONTROLLER
    assert 'credentials: "same-origin"' in CONTROLLER
    assert "Refused cross-origin API request" in CONTROLLER
    assert "/api/a11oy/" not in CONTROLLER
    assert "/api/lake/" not in CONTROLLER
    assert "/healthz" not in CONTROLLER
    assert not re.search(r'["\']/api/(?!experience/v1)', CONTROLLER)


def test_five_scenarios_are_an_exact_client_allowlist() -> None:
    expected = {
        "investigate-outage",
        "screen-vessel",
        "review-property",
        "review-contract",
        "route-inference",
    }
    block = CONTROLLER.split("var SCENARIO_ALLOWLIST", 1)[1].split("]);", 1)[0]
    found = set(re.findall(r'id: "([^"]+)"', block))
    assert found == expected
    assert "ALLOWED_SCENARIOS.has" in CONTROLLER
    assert "raw.public !== true || raw.active !== true" in CONTROLLER


def test_session_stream_and_capability_contracts_are_exact() -> None:
    assert "body: JSON.stringify({ scenario_id: selectedId })" in CONTROLLER
    for field in (
        "capability_token: capability.token",
        "scope: capability.scope",
        "expected_sequence: capability.issuedSequence",
    ):
        assert field in CONTROLLER
    assert 'headers["Idempotency-Key"] = key' in CONTROLLER
    assert 'headers: { Accept: "text/event-stream" }' in CONTROLLER
    assert '"?after=" + String(afterSequence)' in CONTROLLER
    assert "createSSEParser" in CONTROLLER
    assert "acceptOrderedEvent" in CONTROLLER
    assert "Experience event sequence gap" in CONTROLLER
    assert "Event stream ended without a terminator" in CONTROLLER
    assert "EventSource" not in CONTROLLER
    assert "setInterval" not in CONTROLLER + RENDERER
    assert "REQUEST_DEADLINE_MS" in CONTROLLER
    assert "STREAM_DEADLINE_MS" in CONTROLLER
    assert "armDeadline" in CONTROLLER
    assert "disarmDeadline(deadline)" in CONTROLLER
    assert "deadlineTimers.clear()" in CONTROLLER
    assert "localStorage" not in CONTROLLER
    assert "sessionStorage" not in CONTROLLER
    assert "approvalCapability: null" in CONTROLLER


def test_modal_drawers_isolate_background_and_preserve_focus_contract() -> None:
    assert "syncModalIsolation" in CONTROLLER
    assert 'node.setAttribute("inert", "")' in CONTROLLER
    assert "restoreModalIsolation" in CONTROLLER
    assert "restoreTargets.has(panel)" in CONTROLLER
    assert 'panel.querySelector("[data-a11oy-initial-focus]")' in CONTROLLER
    assert 'title.dataset.a11oyInitialFocus = "true"' in CONTROLLER


def test_rendering_is_text_safe_and_separates_receipt_truth_axes() -> None:
    combined = CONTROLLER + RENDERER
    for forbidden in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "new Function",
        "eval(",
    ):
        assert forbidden not in combined
    assert "textContent" in CONTROLLER
    for field in (
        '"Chain integrity"',
        '"Signer state"',
        '"Policy result"',
        '"Approval result"',
        '"Effect state"',
        '"Verification state"',
        '"Receipt digest"',
        '"Previous hash"',
        '"Current hash"',
    ):
        assert field in CONTROLLER
    assert (
        "Chain integrity, signer state, effect state, and verification state "
        "are separate checks."
    ) in CONTROLLER
    assert "body: JSON.stringify({})" in CONTROLLER
    assert "approvalState: isRecord(payload.approval_state)" in CONTROLLER
    assert "objectState(event.approvalState)" in CONTROLLER
    assert "approvalState: boundedText(payload.approval_state" not in CONTROLLER


def test_semantic_dom_keyboard_focus_and_url_contract() -> None:
    for element_id in (
        "a11oy-stage-canvas",
        "a11oy-lifecycle",
        "a11oy-runtime-state",
        "a11oy-live-region",
        "a11oy-run-demo",
        "a11oy-inspect-receipt",
        "a11oy-command-open",
        "a11oy-command-dialog",
        "a11oy-command-input",
        "a11oy-command-results",
        "a11oy-evidence-drawer",
        "a11oy-evidence-content",
        "a11oy-receipt-drawer",
        "a11oy-receipt-content",
        "a11oy-approval",
        "a11oy-approval-description",
        "a11oy-approval-submit",
    ):
        assert element_id in CONTROLLER

    for key in ('event.key === "/"', '"Escape"', '"ArrowDown"', '"ArrowUp"', '"Enter"', '"Tab"'):
        assert key in CONTROLLER
    assert "aria-activedescendant" in CONTROLLER
    assert 'setAttribute("aria-current", "step")' in CONTROLLER
    assert "restoreTargets" in CONTROLLER
    assert "target.focus()" in CONTROLLER
    assert 'url.searchParams.set("experience_focus", asset.id)' in CONTROLLER
    assert 'listen(win, "popstate", applyUrlFocus)' in CONTROLLER
    assert "pagehide" in CONTROLLER
    assert "requestControllers" in CONTROLLER
    assert "destroyRenderer()" in CONTROLLER


def test_css_has_responsive_motion_contrast_and_2d_parity() -> None:
    for token in (
        "min-width: 44px",
        "min-height: 44px",
        "min-height: 48px",
        "100dvh",
        "safe-area-inset-top",
        "safe-area-inset-right",
        "safe-area-inset-bottom",
        "safe-area-inset-left",
        "@media (max-width: 1024px)",
        "@media (max-width: 768px)",
        "@media (max-width: 390px)",
        "@media (prefers-reduced-motion: reduce)",
        "@media (prefers-contrast: more)",
        "@media (forced-colors: active)",
        '[data-experience-renderer="2d"]',
        ":focus-visible",
        "[hidden]",
    ):
        assert token in CSS
    assert "overflow-x: clip" in CSS
    assert "#a11oy-stage-canvas" in CSS
    assert "#a11oy-lifecycle" in CSS
    assert "--a11oy-proof: #5fb3a3" in CSS
    assert "--a11oy-lattice: #c9b787" in CSS
    assert "proof: 0x5fb3a3" in RENDERER
    assert "lattice: 0xc9b787" in RENDERER


def test_renderer_is_a_thin_state_only_adapter_with_one_guarded_lifecycle() -> None:
    assert 'import { boot } from "/static/3d/szl3d/szl3d_boot.js"' in RENDERER
    assert "export async function mountExperienceRenderer" in RENDERER
    assert "function update(view)" in RENDERER
    assert "stage.onFrame(animateFrame)" in RENDERER
    assert "if (!loopRunning)" in RENDERER
    assert "stage.stop()" in RENDERER
    assert "stage.dispose()" in RENDERER
    assert "intersectionObserver.disconnect()" in RENDERER
    assert "disposeObject(sceneRoot)" in RENDERER
    assert "view.stepStates" in RENDERER
    assert "view.currentStep" in RENDERER
    assert "completedIndex" not in RENDERER
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "EventSource",
        "WebSocket",
        "requestAnimationFrame",
        "/api/",
    ):
        assert forbidden not in RENDERER


def test_node_units_cover_stream_boundaries_ordering_and_public_filtering() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = r"""
const assert = require("node:assert/strict");
const api = require("./console/assets/a11oy-public-experience-v1.js");
const test = api.__test;

assert.equal(test.API_PATHS.health, "/api/experience/v1/health");
assert.equal(test.SCENARIO_ALLOWLIST.length, 5);
assert.equal(test.normalizeDataState("SIMULATION"), "SIMULATION");
assert.equal(test.normalizeDataState("made-up"), "UNAVAILABLE");

const earlyUnavailable = test.deriveLifecycleState([
  { stage: "CREATED" },
  { stage: "PROPOSED" },
  { stage: "EVIDENCE_BOUND" },
  { stage: "UNAVAILABLE", receipt_id: "sim-experience:early" },
]);
assert.equal(earlyUnavailable.states.PROPOSE, "complete");
assert.equal(earlyUnavailable.states.EVIDENCE, "complete");
assert.equal(earlyUnavailable.states.POLICY, "pending");
assert.equal(earlyUnavailable.states.APPROVAL, "pending");
assert.equal(earlyUnavailable.states.EXECUTE, "pending");
assert.equal(earlyUnavailable.states.VERIFY, "unavailable");
assert.equal(earlyUnavailable.states.RECEIPT, "complete");

const blockedAfterExecution = test.deriveLifecycleState([
  { stage: "CREATED" },
  { stage: "PROPOSED" },
  { stage: "EVIDENCE_BOUND" },
  { stage: "QUALIFIED" },
  { stage: "POLICY_EVALUATED" },
  { stage: "EXECUTING" },
  { stage: "BLOCKED", receipt_id: "sim-experience:blocked" },
]);
assert.equal(blockedAfterExecution.currentStep, "VERIFY");
assert.equal(blockedAfterExecution.states.POLICY, "complete");
assert.equal(blockedAfterExecution.states.EXECUTE, "complete");
assert.equal(blockedAfterExecution.states.VERIFY, "failed");
assert.equal(blockedAfterExecution.states.RECEIPT, "complete");

const frames = [];
const parser = test.createSSEParser((frame) => frames.push(frame));
parser.push("id: 0\r\nevent: experi", false);
parser.push("ence\r\ndata: {\"sequence\":0}\r\n\r\n", false);
parser.push("event: end\ndata: {\"terminal\":true}\n\n", true);
assert.deepEqual(frames, [
  { event: "experience", id: "0", data: "{\"sequence\":0}" },
  { event: "end", id: "", data: "{\"terminal\":true}" },
]);

const tracker = { lastSequence: -1, seenEventIds: new Set() };
const first = {
  event_id: "evt-0",
  session_id: "session-1",
  sequence: 0,
  stage: "CREATED",
  scenario_id: "investigate-outage",
  data_state: "SIMULATION",
};
assert.equal(
  test.acceptOrderedEvent(
    tracker,
    first,
    "session-1",
    "investigate-outage"
  ).accepted,
  true
);
assert.equal(
  test.acceptOrderedEvent(
    tracker,
    first,
    "session-1",
    "investigate-outage"
  ).duplicate,
  true
);
assert.throws(
  () => test.acceptOrderedEvent(
    tracker,
    { ...first, event_id: "evt-2", sequence: 2, stage: "PROPOSED" },
    "session-1",
    "investigate-outage"
  ),
  /sequence gap/
);

assert.equal(
  test.sanitizeAsset(
    { id: "private", title: "Private", public: false, active: true },
    "https://a-11-oy.com"
  ),
  null
);
const publicAsset = test.sanitizeAsset(
  {
    id: "a11oy",
    title: "A11oy",
    summary: "Governed execution with receipts.",
    public: true,
    active: true,
    live_url: "https://a-11-oy.com/verify",
    evidence_url: "https://example.invalid/private",
    data_state: "SNAPSHOT",
  },
  "https://a-11-oy.com"
);
assert.equal(publicAsset.livePath, "/verify");
assert.equal(publicAsset.evidencePath, null);
assert.equal(test.publicLink("https://szlholdings-killinchu.hf.space/defend", "https://a-11-oy.com"),
  "https://szlholdings-killinchu.hf.space/defend");
for (const url of ["javascript:alert(1)", "https://szlholdings-killinchu.hf.space.evil.test/",
  "https://name:password@szlholdings-killinchu.hf.space/", "https://szlholdings-killinchu.hf.space:8443/"]) {
  assert.equal(test.publicLink(url, "https://a-11-oy.com"), null);
}
const terminator = {session_id: "session-1", next_sequence: 1, stage: "RECEIPTED", terminal: true,
  receipt_id: "sim-experience:ok"};
const current = {stage: "RECEIPTED", receiptId: "sim-experience:ok"};
assert.equal(test.validateEndFrame(terminator, tracker, current, "session-1"), terminator);
for (const change of [{next_sequence: 2}, {stage: "VERIFIED"}, {receipt_id: "other"},
  {session_id: "other"}, {terminal: false}]) {
  assert.throws(() => test.validateEndFrame({...terminator, ...change}, tracker, current, "session-1"),
    /terminator/);
}
assert.equal(
  test.sanitizeScenario({ id: "not-allowlisted", title: "No" }),
  null
);
"""
    completed = subprocess.run(
        [node, "-e", script],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout


def test_node_session_projection_handles_terminal_failures_stale_requests_and_renderer_abort() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = r"""
const assert = require("node:assert/strict");
const api = require("./console/assets/a11oy-public-experience-v1.js");
const flush = () => new Promise(resolve => setImmediate(resolve));
const json = value => ({ok: true, status: 200, json: async () => value});
const pending = () => { let resolve; const promise = new Promise(done => {resolve = done;});
  return {promise, resolve}; };
const firstScenario = "investigate-outage";
function stream(session, stages, endOverride = {}) {
  const events = stages.map((stage, sequence) => ({
    event_id: "evt-" + session + "-" + sequence, session_id: session, scenario_id: firstScenario,
    sequence, stage, data_state: "SIMULATION", evidence: [], approval_state: {state: "NOT_REQUIRED"},
    receipt_id: sequence === stages.length - 1 ? "sim-experience:" + session : null,
  }));
  const last = events.at(-1);
  const end = {session_id: session, next_sequence: events.length, stage: last.stage, terminal: true,
    receipt_id: last.receipt_id, ...endOverride};
  return {ok: true, status: 200, headers: {get: () => "text/event-stream"}, body: null,
    text: async () => events.map(event => `id: ${event.sequence}\nevent: experience\ndata: ${JSON.stringify(event)}\n\n`).join("") +
      `event: end\ndata: ${JSON.stringify(end)}\n\n`};
}
function fixture(onRequest, withCanvas = false) {
  const media = [];
  const canvas = {hidden: true};
  const root = {dataset: {}, querySelector: () => null, contains: node => node === canvas,
    addEventListener() {}, removeEventListener() {}, dispatchEvent() {}};
  const win = {location: {origin: "https://a-11-oy.com", href: "https://a-11-oy.com/"},
    addEventListener() {}, removeEventListener() {},
    CustomEvent: class {constructor(name, options) {this.type = name; this.detail = options.detail;}},
    matchMedia() {const item = {matches: false, addEventListener(_, fn) {this.change = fn;},
      removeEventListener() {}}; media.push(item); return item;},
    crypto: {randomUUID: () => "request-key"},
    fetch: async (path, init) => {
      if (path.endsWith("/health")) return json({data_state: "SIMULATION"});
      if (path.endsWith("/scenarios")) return json({scenarios: [{id: firstScenario, title: "Outage", data_state: "SIMULATION"}]});
      if (path.endsWith("/estate")) return json({assets: []});
      return onRequest(path, init);
    }};
  const doc = {defaultView: win, getElementById: id => withCanvas && id === "a11oy-stage-canvas" ? canvas : null,
    addEventListener() {}, removeEventListener() {}, contains: () => false};
  root.ownerDocument = doc;
  return {root, media, canvas};
}
(async () => {
  for (const stage of ["RECEIPTED", "POLICY_DENIED", "BLOCKED", "UNAVAILABLE"]) {
    const f = fixture(path => path.endsWith("/sessions")
      ? json({session_id: "one", scenario_id: firstScenario, data_state: "SIMULATION"})
      : stream("one", ["CREATED", "PROPOSED", "EVIDENCE_BOUND", stage]));
    const handle = api.mount(f.root);
    await flush();
    await handle.runScenario(firstScenario);
    assert.equal(handle.state().stage, stage);
    assert.equal(handle.state().transport, "COMPLETE");
    assert.equal(handle.state().receiptId, "sim-experience:one");
    handle.destroy();
  }
  const malformed = fixture(path => path.endsWith("/sessions")
    ? json({session_id: "bad", scenario_id: firstScenario, data_state: "SIMULATION"})
    : stream("bad", ["CREATED", "RECEIPTED"], {next_sequence: 8}));
  const badHandle = api.mount(malformed.root);
  await flush();
  await badHandle.runScenario(firstScenario);
  assert.equal(badHandle.state().transport, "UNAVAILABLE");
  badHandle.destroy();

  const delayed = pending();
  let creates = 0;
  const stale = fixture(path => {
    if (path.endsWith("/sessions")) {
      if (++creates === 1) return delayed.promise;
      return json({session_id: "new", scenario_id: firstScenario, data_state: "SIMULATION"});
    }
    assert.ok(path.includes("/new/events"));
    return stream("new", ["CREATED", "RECEIPTED"]);
  });
  const staleHandle = api.mount(stale.root);
  await flush();
  const oldRun = staleHandle.runScenario(firstScenario);
  await staleHandle.runScenario(firstScenario);
  delayed.resolve(json({session_id: "old", scenario_id: firstScenario, data_state: "SIMULATION"}));
  await oldRun;
  assert.equal(staleHandle.state().sessionId, "new");
  assert.equal(staleHandle.state().transport, "COMPLETE");
  staleHandle.destroy();

  const adapter = pending();
  let disposals = 0;
  const visual = fixture(() => {throw Error("unexpected request");}, true);
  const visualHandle = api.mount(visual.root, {rendererLoader: async () => ({
    mountExperienceRenderer: () => adapter.promise,
  })});
  await flush();
  visual.media[0].matches = true;
  visual.media[0].change();
  adapter.resolve({ok: true, backend: "webgl2", destroy() {disposals += 1;},
    update() {throw Error("cancelled adapter cannot render");}});
  await flush();
  assert.equal(disposals, 1);
  assert.equal(visual.root.dataset.experienceRenderer, "2d");
  assert.equal(visual.canvas.hidden, true);
  visualHandle.destroy();
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        [node, "-e", script], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stdout


def test_controller_is_valid_commonjs_for_unit_loading() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    completed = subprocess.run(
        [node, "--check", str(CONTROLLER_PATH)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout


def test_expected_endpoint_and_stage_sets_remain_machine_readable() -> None:
    expected_endpoints = {
        "/api/experience/v1/health",
        "/api/experience/v1/estate",
        "/api/experience/v1/scenarios",
        "/api/experience/v1/sessions",
    }
    runtime_endpoints = {
        value
        for value in re.findall(r'API_ROOT \+ "(/[^"]+)"', CONTROLLER)
        if value in {"/health", "/estate", "/scenarios", "/sessions"}
    }
    assert {"/api/experience/v1" + value for value in runtime_endpoints} == expected_endpoints

    required_stages = {
        "CREATED",
        "PROPOSED",
        "EVIDENCE_BOUND",
        "QUALIFIED",
        "POLICY_EVALUATED",
        "APPROVAL_REQUIRED",
        "APPROVED",
        "EXECUTING",
        "VERIFIED",
        "RECEIPTED",
        "POLICY_DENIED",
        "BLOCKED",
        "VERIFICATION_FAILED",
        "RECOVERY_REQUIRED",
        "UNAVAILABLE",
    }
    stage_block = CONTROLLER.split("var EXPERIENCE_STAGES", 1)[1].split("]);", 1)[0]
    assert set(re.findall(r'"([A-Z_]+)"', stage_block)) == required_stages

    evidence = {
        "controller_sha_source": str(CONTROLLER_PATH.relative_to(ROOT)),
        "renderer_sha_source": str(RENDERER_PATH.relative_to(ROOT)),
        "css_sha_source": str(CSS_PATH.relative_to(ROOT)),
    }
    assert json.loads(json.dumps(evidence)) == evidence
