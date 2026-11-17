// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"use strict";
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
const test = require("node:test");

const SOURCE = readFileSync(join(__dirname, "../static/3d/surfaces/governedagent.js"), "utf8");
const TOKEN = "fixture-governed-agent-operator";
const TENANT = "fixture-governed-agent-tenant";
const completion = (state = "OBSERVED_COMPLETE", complete = true) => ({
  state, complete, evidence_basis: "UPSTREAM_REPORTED_UNVERIFIED",
  receipt_verification_asserted: false, model_qualified: false,
});
const result = (value = {}) => ({ ok: true, completion: completion(), steps: [], ...value });
function response(value, status = 200, contentType = "application/json") {
  return { ok: status >= 200 && status < 300, status,
    headers: { get: () => contentType }, text: async () => JSON.stringify(value) };
}
function fixture(implementation) {
  const fields = {};
  const requests = [];
  const timers = new Map();
  let tick = 0, confirmCalls = 0, confirmation = false, persistenceCalls = 0;
  const element = (tag = "div") => ({
    tag, value: "", textContent: "", innerHTML: "", disabled: false, style: {},
    children: [], attributes: {}, events: {},
    appendChild(child) { this.children.push(child); return child; },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, fn) { this.events[name] = fn; },
  });
  for (const name of ["operatorToken", "tenant", "task", "modelSel", "modeSel", "suiteSel",
    "profile", "runBtn", "runState", "receipt", "composes"]) fields[name] = element();
  const context = {
    window: { confirm: () => { confirmCalls += 1; return confirmation; },
      addEventListener() {}, removeEventListener() {} },
    document: { createElement: element, body: element() },
    TextEncoder, AbortController,
    setTimeout(fn) { timers.set(++tick, fn); return tick; },
    clearTimeout(id) { timers.delete(id); },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return implementation ? implementation(url, options) : response(result());
    },
  };
  for (const owner of [context, context.window]) {
    for (const name of ["localStorage", "sessionStorage", "indexedDB"]) {
      Object.defineProperty(owner, name, { get() {
        persistenceCalls += 1; throw new Error("Browser persistence is forbidden in this fixture");
      } });
    }
  }
  runInNewContext(SOURCE.replace(/^export default /m, "globalThis.surface = ") + "\n" +
    "globalThis.client = { invoke: _fireRun, leave: _leavePage, resume: _resumePage, " +
    "startPoll: (ctx) => { _ctx = ctx; _startHealthPoll(ctx); }, changed: _requestInputsChanged, " +
    "attach: (fields) => { _el = fields; _lifecycle += 1; }, " +
    "state: () => ({ ...S }), " +
    "overlay: (ctx) => { _ctx = ctx; _buildOverlay(); return _el; } };",
    context, { timeout: 1000 });
  context.client.attach(fields);
  function fill() {
    fields.operatorToken.value = TOKEN; fields.tenant.value = TENANT;
    fields.task.value = "Fixture task"; fields.modelSel.value = "fixture-model";
    fields.modeSel.value = "chat"; fields.suiteSel.value = "core_honest_v1";
  }
  fill();
  return { fields, requests, context, fill, element,
    invoke: () => context.client.invoke(), state: () => context.client.state(),
    expire: () => { for (const fn of timers.values()) fn(); },
    confirm: (value) => { confirmation = value; },
    confirmCount: () => confirmCalls, persistenceCount: () => persistenceCalls };
}

test("actual served client sends existing authorization and tenant contract once", async () => {
  const f = fixture();
  assert.equal(f.requests.length, 0);
  await f.invoke();
  assert.equal(f.requests.length, 1);
  const request = f.requests[0];
  assert.equal(request.url, "/api/a11oy/v1/agentloop/run");
  assert.equal(request.options.method, "POST");
  assert.equal(request.options.redirect, "error");
  assert.equal(request.options.credentials, "same-origin");
  assert.equal(request.options.cache, "no-store");
  assert.equal(request.options.headers.authorization, "Bearer " + TOKEN);
  assert.equal(request.options.headers["x-a11oy-tenant"], TENANT);
  assert.equal(request.options.headers["x-a11oy-second-approver"], undefined);
  assert.deepEqual(JSON.parse(request.options.body), {
    task: "Fixture task", mode: "chat", model_id: "fixture-model",
    eval_suite: "core_honest_v1", max_retries: 0, sandbox: false,
    consult_brain: false, allocate_energy: false,
  });
  assert.equal(f.fields.operatorToken.value, "");
  assert.match(f.fields.runState.textContent, /OBSERVED_COMPLETE.*upstream reported, unverified/);
  assert.doesNotMatch(f.fields.runState.textContent, /done|qualified=true/);
});

for (const [field, value] of [
  ["operatorToken", ""], ["operatorToken", "header\r\ninjection"],
  ["operatorToken", "x".repeat(4097)], ["tenant", ""], ["tenant", "wrong\nheader"],
  ["task", ""], ["task", "x".repeat(32001)], ["modelSel", ""],
  ["modeSel", "unknown"], ["suiteSel", ""], ["task", "\u2603".repeat(24000)],
]) {
  test("invalid " + field + " is blocked before fetch", async () => {
    const f = fixture(); f.fields[field].value = value;
    await f.invoke();
    assert.equal(f.requests.length, 0);
    assert.equal(f.fields.operatorToken.value, "");
    assert.match(f.state().runState, /^BLOCKED/);
  });
}

for (const [status, expected] of [[401, /operator credential/], [403, /tenant or policy/],
  [422, /request refused/], [503, /^UNKNOWN/]]) {
  test("HTTP " + status + " keeps its refusal or uncertain outcome", async () => {
    const f = fixture(() => response({ ok: true, error: "sensitive backend detail" }, status));
    await f.invoke();
    assert.match(f.state().runState, expected);
    assert.equal(f.state().outcomeUncertain, status >= 500);
    assert.equal(f.requests.length, 1);
    assert.doesNotMatch(f.fields.runState.textContent, /sensitive backend detail/);
  });
}

for (const [name, value, expected] of [
  ["bare HTTP success", { ok: true }, /^UNKNOWN/],
  ["missing completion", result({ completion: null }), /^UNKNOWN/],
  ["incomplete", result({ ok: false, completion: completion("INCOMPLETE", false) }), /^INCOMPLETE/],
  ["blocked", result({ ok: false, completion: completion("BLOCKED", false) }), /^BLOCKED/],
  ["conflicting success flag", result({ ok: false }), /^UNKNOWN/],
  ["conflicting incomplete flag", result({ completion: completion("INCOMPLETE", false) }), /^UNKNOWN/],
  ["contradictory completion", result({ completion: completion("OBSERVED_COMPLETE", false) }), /^UNKNOWN/],
  ["invented verified basis", result({ completion: { ...completion(), evidence_basis: "VERIFIED" } }), /^UNKNOWN/],
  ["claimed receipt verification", result({ completion: { ...completion(), receipt_verification_asserted: true } }), /^UNKNOWN/],
  ["claimed model qualification", result({ completion: { ...completion(), model_qualified: true } }), /^UNKNOWN/],
  ["array response", [], /^UNKNOWN/],
]) {
  test(name + " cannot become verified completion", async () => {
    const f = fixture(() => response(value));
    await f.invoke();
    assert.match(f.state().runState, expected);
    assert.equal(f.requests.length, 1);
    assert.equal(f.fields.operatorToken.value, "");
  });
}

test("HTML catch-all response is UNKNOWN and never automatically retried", async () => {
  const f = fixture(() => response({ ok: true }, 200, "text/html"));
  await f.invoke();
  assert.match(f.state().runState, /^UNKNOWN/);
  f.fill(); await f.invoke();
  assert.equal(f.confirmCount(), 1);
  assert.equal(f.requests.length, 1, "declined acknowledgement must not dispatch");
  assert.equal(f.fields.operatorToken.value, "");
});

test("transport failure needs explicit acknowledgement before a new request", async () => {
  const f = fixture(() => { throw new TypeError("fixture network failure"); });
  await f.invoke();
  assert.equal(f.requests.length, 1);
  assert.equal(f.state().outcomeUncertain, true);
  f.fill(); f.confirm(true); await f.invoke();
  assert.equal(f.confirmCount(), 1);
  assert.equal(f.requests.length, 2);
});

test("double-click while in flight makes one request and clears credential immediately", async () => {
  let release;
  const f = fixture(() => new Promise(resolve => { release = resolve; }));
  const first = f.invoke();
  assert.equal(f.fields.operatorToken.value, "");
  assert.equal(f.fields.runBtn.disabled, true);
  assert.equal(f.fields.task.disabled, true);
  assert.equal(f.fields.tenant.disabled, true);
  assert.equal(f.fields.modelSel.disabled, true);
  await f.invoke();
  assert.equal(f.requests.length, 1);
  release(response(result()));
  await first;
  assert.equal(f.fields.runBtn.disabled, false);
});

test("deadline abort retains UNKNOWN without retry or a remote-cancellation claim", async () => {
  const f = fixture((_, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new Error("fixture abort")));
  }));
  const pending = f.invoke();
  f.expire();
  await pending;
  assert.equal(f.requests[0].options.signal.aborted, true);
  assert.equal(f.state().outcomeUncertain, true);
  assert.match(f.state().runState, /execution may have occurred/);
  assert.equal(f.requests.length, 1);
});

test("unmount clears fields, aborts request and discards late completion", async () => {
  let release;
  const f = fixture(() => new Promise(resolve => { release = resolve; }));
  const pending = f.invoke();
  f.fields.operatorToken.value = "another-unsent-fixture";
  f.context.surface.unmount();
  assert.equal(f.fields.operatorToken.value, "");
  assert.equal(f.fields.tenant.value, "");
  assert.equal(f.requests[0].options.signal.aborted, true);
  release(response(result()));
  await pending;
  assert.equal(f.state().lastResult, null);
  assert.equal(f.state().outcomeUncertain, true);
  assert.match(f.state().runState, /^UNKNOWN/);
  assert.equal(f.requests.length, 1);
});

test("page exit clears unsent credentials and tenant without creating work", () => {
  const f = fixture();
  f.context.client.leave();
  assert.equal(f.fields.operatorToken.value, "");
  assert.equal(f.fields.tenant.value, "");
  assert.equal(f.requests.length, 0);
});

test("actual form contains labelled one-request credential and explicit model controls", () => {
  const f = fixture();
  const fields = f.context.client.overlay({
    live: { createBadge: () => ({ el: f.element() }) },
    label: { legend: () => f.element() }, container: f.element(),
  });
  assert.equal(fields.operatorToken.type, "password");
  assert.equal(fields.operatorToken.autocomplete, "off");
  assert.equal(fields.operatorToken.maxLength, 4096);
  assert.equal(fields.tenant.maxLength, 256);
  assert.equal(fields.modelSel.value, "");
  assert.equal(fields.modelSel.attributes["aria-label"], "Explicit configured model ID");
  assert.equal(fields.runBtn.textContent, "Send one governed request");
  assert.equal(f.requests.length, 0);
});


test("credential is never persisted or included in URL or body", async () => {
  const f = fixture();
  await f.invoke();
  f.context.surface.unmount();
  assert.equal(f.persistenceCount(), 0);
  assert.equal(f.fields.operatorToken.value, "");
  assert.ok(!f.requests[0].url.includes(TOKEN));
  assert.ok(!f.requests[0].options.body.includes(TOKEN));
});

test("late health callbacks cannot update a removed or resumed view", () => {
  const f = fixture(), polls = [];
  const ctx = { live: { poll: (url, interval, callback, options) => {
    const record = { url, callback, options, stopped: false };
    polls.push(record);
    return { stop() { record.stopped = true; } };
  } } };
  f.context.client.startPoll(ctx);
  assert.equal(polls[0].url, "/api/a11oy/v1/agentloop/health");
  polls[0].callback({ composes: { act_engine_available: true } }, { degraded: false });
  assert.equal(f.state().composes.act_engine_available, true);
  f.context.client.leave();
  assert.equal(polls[0].stopped, true);
  polls[0].callback({ composes: { act_engine_available: true } }, { label: "STALE" });
  polls[0].options.onState({ state: "live", label: "STALE" });
  assert.equal(f.state().composes, null);
  assert.equal(f.state().state, "init");
  assert.equal(f.state().label, null);
  f.context.client.resume();
  assert.equal(polls.length, 2, "returning to the page resumes only read-only health");
  polls[1].callback({ composes: { act_engine_available: false } }, { label: "CURRENT" });
  polls[0].callback({ composes: { act_engine_available: true } }, { label: "STALE" });
  assert.equal(f.state().composes.act_engine_available, false);
  assert.equal(f.state().label, "CURRENT");
  assert.equal(f.requests.length, 0);
});


test("changing request context clears the displayed previous result", async () => {
  const f = fixture();
  await f.invoke();
  assert.equal(f.state().lastResult.ok, true);
  f.fields.tenant.value = "different-fixture-tenant";
  f.context.client.changed();
  assert.equal(f.state().lastResult, null);
  assert.equal(f.state().lastReceipt, null);
  assert.match(f.state().runState, /^INPUT_CHANGED/);
  assert.equal(f.requests.length, 1);
});

test("editing inputs cannot erase an uncertain prior execution", async () => {
  const f = fixture(() => { throw new TypeError("fixture network failure"); });
  await f.invoke();
  f.fields.modelSel.value = "different-fixture-model";
  f.context.client.changed();
  assert.equal(f.state().outcomeUncertain, true);
  assert.match(f.state().runState, /^UNKNOWN/);
  f.fill(); await f.invoke();
  assert.equal(f.confirmCount(), 1);
  assert.equal(f.requests.length, 1);
});
