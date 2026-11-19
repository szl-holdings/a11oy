"use strict";

/* Offline browser-contract tests: never fetch production or invoke a model. */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "pages", "second-brain.html"), "utf8");
const INLINE_SCRIPT = /<script>\s*([\s\S]*?)\s*<\/script>/i;
const inline = html.match(INLINE_SCRIPT);
assert.ok(inline, "one inline Second Brain application script is required");
const script = inline[1];
const section = script.match(/function classifyBrain\([\s\S]*?(?=function emptyMembrane\()/);
assert.ok(section, "a standalone auditable state classifier is required");
const classify = vm.runInNewContext(section[0] + "\nclassifyBrain", {});

function observed(json, ok = true) { return { ok, status: ok ? 200 : 503, json }; }
const rag = {
  ok: true, built: true, mode: "seed",
  brain_handle_plane: { state: "INDEXED_RETRIEVAL_ONLY", count: 9465, training_authority: "NONE" }
};
const missing = {
  state: "UNAVAILABLE_MODEL_TAG_MISSING", ready_for_grounded_navigation: false,
  live_grounded_turn_verified_this_request: false,
  profile: {
    expected_model: "khipu:latest", served_model: null,
    exact_tag_observed: false, artifact_binding: "UNBOUND"
  }
};

test("the inline UI script parses without external dependencies", () => {
  assert.doesNotThrow(() => new vm.Script(script));
});

test("inline script extraction accepts uppercase SCRIPT tags", () => {
  const uppercase = "<SCRIPT>const uppercase = true;</SCRIPT>".match(INLINE_SCRIPT);
  assert.ok(uppercase);
  assert.equal(uppercase[1], "const uppercase = true;");
});

test("HTTP 200 alone cannot become indexed memory or a verified inference turn", () => {
  const x = classify(observed({ ok: true }), observed({}), observed({}));
  assert.equal(x.index_state, "UNAVAILABLE");
  assert.equal(x.model_state, "UNAVAILABLE");
  assert.equal(x.grounded_state, "NOT_VERIFIED");
  assert.equal(x.independent_attestation, false);
  assert.equal(x.production_admission, "NOT_ASSERTED");
});

test("real indexed handles stay distinct from unavailable Khipu model identity", () => {
  const x = classify(observed(rag), observed(missing), observed({ overall_status: "PARTIALLY OPERATIONAL" }));
  assert.equal(x.index_state, "INDEXED_RETRIEVAL_ONLY");
  assert.equal(x.model_state, "UNAVAILABLE_MODEL_TAG_MISSING");
  assert.equal(x.grounded_state, "NOT_VERIFIED");
  assert.equal(x.capability_state, "PARTIALLY OPERATIONAL");
});

test("a ready-looking flag with no exact served tag remains unverified", () => {
  const m = structuredClone(missing);
  m.ready_for_grounded_navigation = true;
  m.live_grounded_turn_verified_this_request = true;
  assert.equal(classify(observed(rag), observed(m), observed({})).grounded_state, "NOT_VERIFIED");
});

test("a wrong served alias cannot qualify a real turn", () => {
  const m = structuredClone(missing);
  Object.assign(m, { ready_for_grounded_navigation: true, live_grounded_turn_verified_this_request: true });
  Object.assign(m.profile, { exact_tag_observed: true, served_model: "other:latest", artifact_binding: "MEASURED" });
  assert.equal(classify(observed(rag), observed(m), observed({})).grounded_state, "NOT_VERIFIED");
});

test("backend-reported readiness never becomes independent attestation", () => {
  const m = structuredClone(missing);
  Object.assign(m, { ready_for_grounded_navigation: true, live_grounded_turn_verified_this_request: true });
  Object.assign(m.profile, { exact_tag_observed: true, served_model: "khipu:latest", artifact_binding: "MEASURED" });
  const x = classify(observed(rag), observed(m), observed({ overall_status: "OPERATIONAL" }));
  assert.equal(x.grounded_state, "BACKEND_REPORTED_ONLY");
  assert.equal(x.independent_attestation, false);
  assert.equal(x.production_admission, "NOT_ASSERTED");
});

test("the unbound artifact is a hard blocker despite other positive flags", () => {
  const m = structuredClone(missing);
  Object.assign(m, { ready_for_grounded_navigation: true, live_grounded_turn_verified_this_request: true });
  Object.assign(m.profile, { exact_tag_observed: true, served_model: "khipu:latest" });
  assert.equal(classify(observed(rag), observed(m), observed({})).grounded_state, "NOT_VERIFIED");
});

test("untrusted state text and wrong capability labels are not echoed as badges", () => {
  const m = { state: "<img src=x onerror=alert(1)>", profile: {} };
  const x = classify(observed({ built: false }), observed(m), observed({ overall_status: "PRODUCTION_CERTIFIED" }));
  assert.equal(x.model_state, "UNAVAILABLE");
  assert.equal(x.capability_state, "UNAVAILABLE");
  assert.equal(x.index_state, "UNAVAILABLE");
});

test("missing or unsuccessful observations fail closed", () => {
  const x = classify(observed(rag, false), observed(missing, false), observed(null, false));
  assert.equal(x.index_state, "UNAVAILABLE");
  assert.equal(x.model_state, "UNAVAILABLE");
  assert.equal(x.grounded_state, "NOT_VERIFIED");
});

test("a screen reader can discover both status updates and an illustrative canvas", () => {
  assert.match(html, /id="runtime-status" role="status" aria-live="polite"/);
  assert.match(html, /id="retrieval-status" role="status" aria-live="polite"/);
  assert.match(html, /canvas[^>]*illustrative, not measured/i);
});

test("the frontend uses bounded same-origin readbacks, no auto-promotion", () => {
  assert.match(script, /new AbortController\(\)/);
  assert.match(script, /redirect:"error"/);
  assert.match(script, /credentials:"same-origin"/);
  assert.match(script, /Promise\.all\(\[/);
  assert.match(script, /q\.length>240/);
  assert.doesNotMatch(script, /brain\.ok\?"REACHABLE"/);
  assert.doesNotMatch(script, /\.innerHTML\s*=/);
});

function element() {
  return {
    textContent: "", className: "", disabled: false, value: "",
    children: [], listeners: Object.create(null),
    appendChild(child) { this.children.push(child); },
    addEventListener(event, fn) { this.listeners[event] = fn; }
  };
}

function makeHarness(responses, canvasAvailable = true) {
  const ids = ["chips", "runtime-status", "retrieval-status", "brain", "go", "handles",
    "membrane", "raw", "q"];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements.q.value = "second brain fold";
  const graphics = { fillRect() {}, beginPath() {}, ellipse() {}, stroke() {},
    moveTo() {}, lineTo() {}, arc() {}, fill() {}, fillText() {} };
  elements.brain.getContext = () => canvasAvailable ? graphics : null;
  const calls = [];
  const fetch = async (url, opts) => {
    calls.push({ url, opts });
    const data = responses[url];
    if (!data) return { ok: false, status: 503, headers: { get: () => "application/json" } };
    return {
      ok: true, status: 200, headers: { get: () => "application/json; charset=utf-8" },
      json: async () => structuredClone(data)
    };
  };
  const context = {
    window: { matchMedia: () => ({ matches: true }) },
    document: { getElementById: id => elements[id], createElement: () => element() },
    AbortController, setTimeout, clearTimeout, requestAnimationFrame: () => {},
    fetch, console
  };
  vm.runInNewContext(script, context);
  return { elements, calls, context };
}
const responses = {
  "/api/a11oy/v1/honest": {
    locked_formula_count: 8,
    locked_formula_ids: ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
  },
  "/api/a11oy/v1/brain/capabilities": { overall_status: "PARTIALLY OPERATIONAL" },
  "/api/a11oy/v1/formulas/selftest": { reported: true },
  "/api/a11oy/v1/brain/membrane": { membrane: {} },
  "/api/a11oy/code/rag/status": rag,
  "/api/a11oy/v1/ayllu/second-brain": missing,
  "/api/build-info": { build: { revision: "b".repeat(40) } }
};
const flushed = () => new Promise(resolve => setImmediate(resolve));

test("mounted browser actually renders retrieval and unavailable inference separately", async () => {
  const { elements, calls, context } = makeHarness(responses);
  await flushed();
  assert.equal(calls.length, 7);
  assert.ok(calls.every(c => c.opts.credentials === "same-origin" && c.opts.redirect === "error"));
  const badges = elements.chips.children.map(x => x.textContent);
  assert.ok(badges.includes("retrieval · INDEXED_RETRIEVAL_ONLY"));
  assert.ok(badges.includes("model · UNAVAILABLE_MODEL_TAG_MISSING"));
  assert.ok(badges.includes("grounded turn · NOT_VERIFIED"));
  assert.ok(badges.includes("capabilities · PARTIALLY OPERATIONAL"));
  assert.match(elements["runtime-status"].textContent, /does not independently certify/);
  assert.equal(context.window.__probe.certified_production_ready, false);
  assert.equal(context.window.__probe.evidence.independent_attestation, false);
});

test("unavailable response cannot falsely show eight observed formula IDs", async () => {
  const broken = { ...responses, "/api/a11oy/v1/honest": {
    locked_formula_count: 8, locked_formula_ids: ["F1", "WRONG", "F7", "F11", "F12", "F18", "F19", "F22"]
  } };
  const { elements, context } = makeHarness(broken);
  await flushed();
  assert.equal(context.window.__probe.locked_formula_count, null);
  assert.deepEqual(Array.from(context.window.__probe.locked_formula_ids), []);
  assert.ok(elements.chips.children.some(x => x.textContent === "formula evidence · UNAVAILABLE"));
});

test("oversized user query abstains locally with no new backend requests", async () => {
  const { elements, calls } = makeHarness(responses);
  await flushed();
  elements.q.value = "x".repeat(241);
  await elements.go.listeners.click();
  assert.equal(calls.length, 7);
  assert.match(elements["retrieval-status"].textContent, /ABSTAIN/);
  assert.equal(elements.go.disabled, false);
});

test("canvas-disabled mode preserves textual evidence instead of throwing", async () => {
  const { elements, context } = makeHarness(responses, false);
  await flushed();
  assert.equal(context.window.__probe.evidence.model_state, "UNAVAILABLE_MODEL_TAG_MISSING");
  assert.match(elements["runtime-status"].textContent, /Canvas unavailable/);
});
