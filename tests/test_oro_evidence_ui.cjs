// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {validateObservation, createController, createRenderer} = require("../oro/evidence_web/app.js");

const DIGEST = "a".repeat(64);
function observation() {
  return {
    schema: "szl.oro-evidence-observation/v1", status: "PARTIAL",
    collected_at: "2026-11-16T23:00:00+00:00", source_revision: "b".repeat(40),
    freshness: "NOT_ASSERTED", execution_authority: false, signing_authority: false,
    promotion_authority: false, capabilities: {execution: {available: false, reasons: ["CANONICAL_ORO_ADMISSION_NOT_BOUND"]}},
    sources: {
      canonical_khipu: {state: "DECLARED", count: 1, window_complete: false,
        omitted_parent_digests: ["c".repeat(64)], signature_verification: "UNKNOWN"},
      second_brain: {state: "UNKNOWN", count: 0},
      anatomy: {state: "MODELED", count: 0, summary: {nodes: 24}},
      hatun: {state: "UNKNOWN", count: 0}
    },
    projection: {schema: "szl.oro.evidence-dag/v1", status: "MODELED_READ_ONLY",
      execution_authority: false, nodes: [{
        node_id: "khipu:" + DIGEST, parents: [], digest: "d".repeat(64),
        evidence: {source: "szl-holdings/a11oy/wire-f", revision: "sha256:" + DIGEST,
          sha256: DIGEST, classification: "PUBLIC", proof_status: "UNVERIFIED",
          formula: null, execution_authority: false, promotion_authority: false}
      }]
    }
  };
}
function response(body, status = 200, contentType = "application/json") {
  return {ok: status >= 200 && status < 300, status,
    headers: {get: () => contentType}, text: async () => typeof body === "string" ? body : JSON.stringify(body)};
}
function timers() {
  let sequence = 0;
  const tasks = new Map();
  return {
    setTimer(fn, ms) { const id = ++sequence; tasks.set(id, {fn, ms}); return id; },
    clearTimer(id) { tasks.delete(id); },
    fire(ms) {
      const entry = [...tasks].find(([, task]) => task.ms === ms);
      assert.ok(entry, "expected timer " + ms);
      tasks.delete(entry[0]); entry[1].fn();
    }
  };
}
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.value = ""; this.disabled = false; }
  set innerHTML(_value) { throw new Error("HTML interpretation is forbidden"); }
  set textContent(value) { this.value = String(value); this.children = []; }
  get textContent() { return this.value + this.children.map(child => child.textContent).join(" "); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.value = ""; this.children = nodes; }
}
function document() {
  const elements = new Map();
  return {
    createElement: tag => new Element(tag),
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element(id));
      return elements.get(id);
    }
  };
}

test("503 after a successful observation clears all displayed handles and counts", async () => {
  const doc = document(), states = [], timer = timers();
  const good = observation(), failed = observation();
  failed.status = "UNAVAILABLE";
  failed.sources.canonical_khipu = {state: "UNAVAILABLE", reason: "OWNER_READ_FAILED", count: 0};
  const responses = [response(good), response(failed, 503)];
  const render = createRenderer(doc);
  const controller = createController({...timer, fetchImpl: async () => responses.shift(),
    onState: state => { states.push(state); render(state); }});
  await controller.refresh();
  assert.equal(doc.getElementById("handle-count").textContent, "1 handle");
  assert.equal(doc.getElementById("nodes").children[0].tagName, "details");
  await controller.refresh();
  assert.equal(states.at(-1).phase, "unavailable");
  assert.equal(doc.getElementById("handle-count").textContent, "Not observed");
  assert.doesNotMatch(doc.getElementById("nodes").textContent, /khipu:/);
  assert.match(doc.getElementById("sources").textContent, /source owner could not return/);
  assert.equal(doc.getElementById("source-revision").textContent, "Not observed");
  controller.dispose();
});

test("HTML fallback and malformed JSON never become a successful empty graph", async () => {
  for (const answer of [response("<html>shell</html>", 200, "text/html"), response("{", 200)]) {
    const states = [], timer = timers();
    const controller = createController({...timer, fetchImpl: async () => answer, onState: s => states.push(s)});
    await controller.refresh();
    assert.equal(states.at(-1).phase, "unavailable");
    assert.equal(states.at(-1).observation, null);
    controller.dispose();
  }
});

test("unknown sources do not turn a numeric zero into an observed count", () => {
  const doc = document();
  createRenderer(doc)({phase: "observed", observation: observation()});
  const sources = doc.getElementById("sources").children;
  assert.match(sources[1].textContent, /UNKNOWN.*Handle count not observed/);
  assert.match(sources[2].textContent, /MODELED.*0 declared handles.*Modeled summary: nodes 24/);
  assert.match(doc.getElementById("window-boundary").textContent, /Partial chain window.*1 parent reference is omitted/);
  assert.match(doc.getElementById("execution-reasons").textContent, /ORO execution is not bound to canonical action admission/);
});

test("declared authority and proof elevation are rejected", () => {
  for (const mutate of [
    b => { b.execution_authority = true; },
    b => { b.capabilities.execution.available = true; },
    b => { b.projection.nodes[0].evidence.proof_status = "PROVEN"; },
    b => { b.projection.nodes[0].evidence.classification = "RESTRICTED"; },
    b => { b.projection.nodes[0].parents = ["outside-window"]; },
    b => { b.projection.nodes[0].evidence.revision = "main"; },
    b => { b.projection.nodes[0].evidence.revision = "commit:" + "a".repeat(39); },
    b => { b.projection.nodes[0].evidence.revision = "sha256:" + "g".repeat(64); }
  ]) {
    const body = observation(); mutate(body);
    assert.throws(() => validateObservation(body), /MISMATCH/);
  }
});

test("refresh requests are deduplicated while the earlier read is pending", async () => {
  let resolveRead, reads = 0;
  const timer = timers();
  const controller = createController({...timer, onState() {},
    fetchImpl: () => { reads++; return new Promise(resolve => { resolveRead = resolve; }); }});
  const first = controller.refresh(), second = controller.refresh();
  assert.equal(first, second);
  assert.equal(reads, 1);
  resolveRead(response(observation()));
  await first;
  controller.dispose();
});

test("timeout aborts the transport and yields an explicit unavailable observation", async () => {
  const states = [], timer = timers();
  let signal;
  const controller = createController({...timer, onState: s => states.push(s),
    fetchImpl: async (_url, options) => { signal = options.signal; return new Promise(() => {}); }});
  const pending = controller.refresh();
  timer.fire(8000);
  await pending;
  assert.equal(signal.aborted, true);
  assert.equal(states.at(-1).phase, "unavailable");
  assert.equal(states.at(-1).reason, "OBSERVATION_TIMEOUT");
  controller.dispose();
});

test("display expiry clears a previously successful observation", async () => {
  const doc = document(), timer = timers(), states = [], render = createRenderer(doc);
  const controller = createController({...timer, fetchImpl: async () => response(observation()),
    onState: state => { states.push(state); render(state); }});
  await controller.refresh();
  timer.fire(35000);
  assert.equal(states.at(-1).phase, "stale");
  assert.equal(doc.getElementById("observation-status").textContent, "Observation expired");
  assert.equal(doc.getElementById("handle-count").textContent, "Not observed");
  assert.doesNotMatch(doc.getElementById("nodes").textContent, /khipu:/);
  controller.dispose();
});

test("untrusted text stays text and does not create elements or navigation", () => {
  const body = observation(), doc = document();
  const hostile = '<img src=x onerror="fetch(1)">';
  body.sources.anatomy.reason = hostile;
  body.projection.nodes[0].evidence.source = hostile;
  createRenderer(doc)({phase: "observed", observation: body});
  assert.match(doc.getElementById("sources").textContent, /<img/);
  assert.match(doc.getElementById("nodes").textContent, /<img/);
  function walk(node) {
    assert.notEqual(node.tagName, "img");
    assert.notEqual(node.tagName, "script");
    node.children.forEach(walk);
  }
  walk(doc.getElementById("sources")); walk(doc.getElementById("nodes"));
});

test("network failure after success never retains a previous claim", async () => {
  const doc = document(), timer = timers(), render = createRenderer(doc);
  let fail = false;
  const controller = createController({...timer, onState: render,
    fetchImpl: async () => { if (fail) throw new Error("private transport details"); return response(observation()); }});
  await controller.refresh(); fail = true; await controller.refresh();
  assert.equal(doc.getElementById("handle-count").textContent, "Not observed");
  assert.doesNotMatch(doc.getElementById("raw").textContent, /private transport/);
  assert.match(doc.getElementById("raw").textContent, /OBSERVATION_REQUEST_FAILED/);
  controller.dispose();
});
