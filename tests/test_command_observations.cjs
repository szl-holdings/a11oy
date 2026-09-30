// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../pages/command-v2.html"), "utf8");
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length, 1, "The self-contained surface has one executable script");

async function harness(response = {}) {
  const elements = new Map(), calls = [], intervals = [];
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.dataset = {}; this.events = {}; this.style = {}; this.isConnected = true; this.open = false; }
    set textContent(value) { this.children = [String(value)]; }
    get textContent() { return this.children.map(c => typeof c === "string" ? c : c.textContent).join(" "); }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attrs[name] = String(value); if (name === "id") { this.id = value; elements.set(value, this); } }
    addEventListener(name, callback) { this.events[name] = callback; }
    focus() { document.activeElement = this; }
    showModal() { this.open = true; }
    close() { this.open = false; this.events.close?.(); }
  }
  const document = {
    body: new Element("body"), activeElement: null,
    createElement: tag => new Element(tag), createTextNode: text => String(text),
    getElementById: id => elements.get(id), addEventListener() {},
  };
  for (const id of ["open", "palette", "query", "hits", "rail", "dock", "canvas", "content", "release", "lambda", "signer", "receipts"]) {
    const element = new Element("div"); element.setAttribute("id", id);
  }
  let current = response;
  const context = vm.createContext({
    document, location: {hash: "#command"}, history: {replaceState() {}},
    AbortController, Date, console,
    setTimeout: () => 1, clearTimeout() {}, setInterval: fn => intervals.push(fn),
    fetch: async (url, options) => {
      calls.push({url, options});
      if (current.throw) throw current.throw;
      return {ok: (current.status || 200) < 400, status: current.status || 200,
        headers: {get: () => current.contentType || "application/json"},
        text: async () => current.raw ?? JSON.stringify(current.body ?? {})};
    },
  });
  vm.runInContext(scripts[0][1], context);
  await new Promise(resolve => setImmediate(resolve));
  return {context, elements, calls, intervals, run: code => vm.runInContext(code, context), respond: value => { current = value; }};
}

test("initial and missing counts are not fabricated as zero", async () => {
  const h = await harness();
  for (const value of ["null", "undefined", '""', '"0"', "true", "[]", "{}", "NaN", "Infinity", "-1", "0.5"]) {
    assert.equal(h.run(`count(${value})`), null, value);
  }
  assert.equal(h.run("count(0)"), 0);
  assert.equal(h.run("count(12)"), 12);
  assert.equal(h.elements.get("receipts").textContent, "Receipts · UNAVAILABLE");
  assert.equal(h.elements.get("release").dataset.state, "unavailable");
  assert.match(h.elements.get("content").textContent, /Readiness UNAVAILABLE/);
  assert.doesNotMatch(h.elements.get("content").textContent, /0 static|0 OK|0 lies/);
});

test("numeric advisory rejects coercion of null, blanks and booleans", async () => {
  const h = await harness();
  for (const value of ["null", "undefined", '""', '"0.95"', "true", "[]", "NaN", "Infinity"]) assert.equal(h.run(`num(${value})`), null);
  assert.equal(h.run("num(0)"), 0);
});

test("source-reported zero and false remain distinguishable from missing", async () => {
  const h = await harness({body: {count: 0, chain_verified: false, signature_state: "UNSIGNED"}});
  assert.equal(h.elements.get("receipts").textContent, "Receipts · 0");
  h.run('openRoom("evidence")');
  assert.match(h.elements.get("content").textContent, /REPORTED UNVERIFIED/);
});

test("source observation expires at the client freshness boundary", async () => {
  const h = await harness({body: {count: 7}});
  assert.equal(h.run('observationState({ok:true,json:{},observedAt:1000},61000)'), "OBSERVED");
  assert.equal(h.run('observationState({ok:true,json:{},observedAt:1000},61001)'), "STALE");
  assert.equal(h.run('observationState({ok:true,json:{},observedAt:1001},1000)'), "STALE");
  h.run('state.data.ledger.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.run('get("ledger").json'), null);
  assert.equal(h.elements.get("receipts").textContent, "Receipts · UNAVAILABLE");
});

test("each source expires independently, including after an earlier source expired", async () => {
  const h = await harness({body: {count: 7, version: "fixture-release"}});
  h.run('state.data.ledger.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.elements.get("receipts").textContent, "Receipts · UNAVAILABLE");
  assert.equal(h.elements.get("release").textContent, "Release · fixture-release");
  h.run('state.data.version.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.elements.get("release").textContent, "Release · UNAVAILABLE");
  const content = h.elements.get("content").children;
  h.intervals[0]();
  assert.equal(h.elements.get("content").children, content, "no rerender without a state transition");
});

test("expiry preserves inspector close focus and original source return target", async () => {
  const h = await harness({body: {count: 7}});
  const original = h.elements.get("inspect-card-receipts");
  original.focus(); h.run('inspectSource("ledger")');
  h.elements.get("close-source-inspector").focus();
  original.isConnected = false;
  h.run('state.data.ledger.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.run("document.activeElement.id"), "close-source-inspector");
  assert.equal(h.run("document.activeElement"), h.elements.get("close-source-inspector"));
  assert.match(h.elements.get("source-inspector").textContent, /STALE/);
  h.elements.get("source-inspector").close();
  assert.equal(h.run("document.activeElement"), h.elements.get("inspect-card-receipts"));
});

test("synthetic preview is visibly labeled, not presented as a runtime witness", async () => {
  const h = await harness({body: {preview: "SYNTHETIC SOFTWARE QA", count: 0}});
  assert.match(h.elements.get("content").textContent, /SYNTHETIC SOFTWARE QA/);
});

for (const [name, response] of Object.entries({
  "SPA HTML 200": {raw: "<!doctype html><h1>Not an API</h1>", contentType: "text/html"},
  "JSON with HTML content type": {raw: '{"count":12}', contentType: "text/html"},
  "JSON null": {raw: "null"}, "JSON array": {raw: "[]"}, "scalar": {raw: "42"},
  "HTTP 503 with plausible data": {status: 503, body: {count: 12}},
  "network failure": {throw: new Error("private details must not be rendered")},
  "timeout": {throw: Object.assign(new Error("timeout"), {name: "AbortError"})},
})) {
  test(`${name} fails closed`, async () => {
    const h = await harness(response);
    assert.equal(h.run('get("ledger").json'), null);
    assert.equal(h.run('observationState(state.data.ledger)'), "UNAVAILABLE");
    assert.equal(h.elements.get("receipts").textContent, "Receipts · UNAVAILABLE");
    assert.doesNotMatch(h.elements.get("content").textContent, /private details/);
  });
}

test("failed refresh does not retain an earlier headline count", async () => {
  const h = await harness({body: {count: 8}});
  h.respond({status: 503, body: {error: "unavailable"}});
  await h.run("refreshObservations()");
  assert.equal(h.elements.get("receipts").textContent, "Receipts · UNAVAILABLE");
});

test("health renders its degraded application state, not a measured 200", async () => {
  const h = await harness({body: {status: "DEGRADED"}});
  assert.match(h.elements.get("content").textContent, /Health DEGRADED REACHABLE · HTTP 200/);
  assert.doesNotMatch(h.elements.get("content").textContent, /MEASURED/);
});

test("refresh and inspection use only known same-origin GET endpoints", async () => {
  const h = await harness();
  const baseline = h.calls.length;
  h.run('inspectSource("ledger")');
  assert.equal(h.calls.length, baseline, "inspecting retained evidence makes no request");
  await h.run("refreshObservations()");
  assert.equal(h.calls.length, 22);
  for (const {url, options} of h.calls) {
    assert.ok(url.startsWith("/") && !url.startsWith("//"));
    assert.notEqual(url, "/api/a11oy/v1/kernel/probe");
    assert.equal(options.method, undefined);
    assert.equal(options.redirect, "error");
    assert.equal(options.credentials, "omit");
    assert.equal(options.cache, "no-store");
  }
});

test("inspector uses literal text and preserves the selected source across refresh", async () => {
  const hostile = '<img src=x onerror="alert(1)">';
  const h = await harness({body: {note: hostile}});
  h.run('inspectSource("ledger")');
  const dialog = h.elements.get("source-inspector");
  assert.equal(dialog.open, true);
  assert.match(dialog.textContent, /Receipt ledger/);
  const payload = dialog.children.find(child => child.tag === "pre");
  assert.equal(JSON.parse(payload.textContent).note, hostile);
  assert.ok(dialog.children.every(child => child.tag !== "img"));
  h.respond({body: {count: 4}}); await h.run("refreshObservations()");
  assert.equal(h.run("state.selectedSource"), "ledger");
  assert.match(dialog.textContent, /"count": 4/);
  dialog.close(); assert.equal(h.run("state.selectedSource"), null);
});

test("unknown inspector source cannot introduce a URL", async () => {
  const h = await harness(); h.run('inspectSource("https://example.com")');
  assert.equal(h.elements.has("source-inspector"), false);
});

test("refresh is single-flight", async () => {
  const h = await harness();
  h.run("state.refreshing=true"); const before = h.calls.length;
  await h.run("refreshObservations()"); assert.equal(h.calls.length, before);
});

test("existing explicit kernel probe still returns its own unknown contract", async () => {
  const h = await harness({body: {decision: "UNKNOWN", honesty: "UNKNOWN", certified: false}});
  await h.run('(async()=>{state.data.kernelProbe=await postJson(endpoints.kernelProbe,"{}");openRoom("kernel")})()');
  assert.equal(h.calls.at(-1).options.method, "POST");
  assert.equal(h.calls.at(-1).options.body, "{}");
  assert.equal(h.run('get("kernelProbe").json.certified'), false);
});
