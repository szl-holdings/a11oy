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
  assert.equal(h.elements.get("receipts").textContent, "Recent receipts · UNAVAILABLE");
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
  assert.equal(h.elements.get("receipts").textContent, "Recent receipts · 0");
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
  assert.equal(h.elements.get("receipts").textContent, "Recent receipts · UNAVAILABLE");
});

test("each source expires independently, including after an earlier source expired", async () => {
  const h = await harness({body: {count: 7, version: "fixture-release"}});
  h.run('state.data.ledger.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.elements.get("receipts").textContent, "Recent receipts · UNAVAILABLE");
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
  const original = h.elements.get("inspect-card-recent-receipts");
  original.focus(); h.run('inspectSource("ledger")');
  h.elements.get("close-source-inspector").focus();
  original.isConnected = false;
  h.run('state.data.ledger.observedAt=Date.now()-60001');
  h.intervals[0]();
  assert.equal(h.run("document.activeElement.id"), "close-source-inspector");
  assert.equal(h.run("document.activeElement"), h.elements.get("close-source-inspector"));
  assert.match(h.elements.get("source-inspector").textContent, /STALE/);
  h.elements.get("source-inspector").close();
  assert.equal(h.run("document.activeElement"), h.elements.get("inspect-card-recent-receipts"));
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
    assert.equal(h.elements.get("receipts").textContent, "Recent receipts · UNAVAILABLE");
    assert.doesNotMatch(h.elements.get("content").textContent, /private details/);
  });
}

test("failed refresh does not retain an earlier headline count", async () => {
  const h = await harness({body: {count: 8}});
  h.respond({status: 503, body: {error: "unavailable"}});
  await h.run("refreshObservations()");
  assert.equal(h.elements.get("receipts").textContent, "Recent receipts · UNAVAILABLE");
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
  assert.equal(h.calls.length, 26);
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

function graphFixture(revision = "a".repeat(40), extra = []) {
  const edges = [{schema:"szl.evidence-edge/v1",subject:{kind:"runtime",id:revision},source_revision:revision,verdict:"OBSERVED",authority:{execution_authorized:false}},...extra];
  return {schema:"szl.evidence-graph/v1",state:"OBSERVED",reason:"SYNTHETIC TEST INPUT",graph:{
    schema:"szl.evidence-graph/v1",edge_count:edges.length,total_input_edges:edges.length,bounded:false,
    verdict_counts:Object.fromEntries(["OBSERVED","VERIFIED","DEGRADED","UNAVAILABLE"].map(v=>[v,edges.filter(e=>e.verdict===v).length])),
    digest_sha256:"b".repeat(64),edges
  }};
}
function setSource(h, name, body) {
  h.run(`state.data[${JSON.stringify(name)}]={ok:true,status:200,observedAt:Date.now(),json:${JSON.stringify(body)}}`);
}
function setBuild(h, revision = "a".repeat(40)) {
  setSource(h,"build",{status:"OBSERVED",build:{state:"OBSERVED",revision,revision_source:"env:SZL_GIT_SHA"}});
}
test("recent receipt window preserves the backend count scope", async () => {
  const h=await harness({body:{count:32,count_scope:"recent returned window, not the DAG total",signature_state:"SIGNED",chain_verified:null,chain_verification:"NOT_EVALUATED_BY_THIS_ROUTE"}});
  h.run('openRoom("evidence")');
  const text=h.elements.get("content").textContent;
  assert.match(text,/Recent receipts 32 recent returned window, not the DAG total/);
  assert.match(text,/NOT_EVALUATED_BY_THIS_ROUTE/);
  assert.doesNotMatch(text,/Minted|REPORTED VERIFIED/);
});
test("identity comparison ignores historical artifacts and never certifies deployment", async () => {
  const h=await harness();setBuild(h);
  setSource(h,"evidenceGraph",graphFixture("a".repeat(40),[{schema:"szl.evidence-edge/v1",subject:{kind:"artifact",id:"historical"},source_revision:null,verdict:"OBSERVED",authority:{execution_authorized:false}}]));
  h.run('openRoom("evidence")');
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"SOURCE-REPORTED MATCH");
  assert.match(h.elements.get("content").textContent,/no deployment verification/);
  assert.match(h.elements.get("content").textContent,/artifact · historical/);
  setBuild(h,"c".repeat(40));
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"DIFFERENT OBSERVATIONS");
});
test("missing malformed and conflicting identity cannot become a match", async () => {
  const h=await harness();setBuild(h);
  setSource(h,"evidenceGraph",graphFixture(null));
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
  setSource(h,"evidenceGraph",graphFixture("a".repeat(40),[{schema:"szl.evidence-edge/v1",subject:{kind:"runtime",id:"c".repeat(40)},source_revision:"c".repeat(40),verdict:"OBSERVED"}]));
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"CONFLICTING OBSERVATIONS");
  setSource(h,"evidenceGraph",graphFixture());
  setSource(h,"build",{status:"OBSERVED",build:{state:"OBSERVED",revision:"a".repeat(40),revision_source:"env:SPACE_COMMIT_SHA"}});
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
});
test("graph rejects inconsistent counts and wrong field types while preserving real zero", async () => {
  const h=await harness();
  for(const mutate of [
    b=>b.schema="other/v1",b=>b.graph.edge_count=2,b=>b.graph.edge_count="1",
    b=>b.graph.total_input_edges=null,b=>b.graph.bounded=null,b=>b.graph.digest_sha256=["b".repeat(64)],
    b=>b.graph.verdict_counts.VERIFIED=1,b=>b.graph.edges[0].subject=[],
    b=>b.graph.edges[0].verdict="ok",
  ]) {
    const b=graphFixture();mutate(b);setSource(h,"evidenceGraph",b);
    assert.equal(h.run("evidenceGraphView().ok"),false);
  }
  const b=graphFixture();b.graph.edges=[];b.graph.edge_count=0;b.graph.total_input_edges=0;b.graph.verdict_counts.OBSERVED=0;
  setSource(h,"evidenceGraph",b);h.run('openRoom("evidence")');
  assert.equal(h.run("evidenceGraphView().ok"),true);
  assert.match(h.elements.get("content").textContent,/Relationships 0/);
  assert.match(h.elements.get("content").textContent,/returned no relationships/);
});
test("one expired observation invalidates identity comparison without hiding retained payload", async () => {
  const h=await harness();setBuild(h);setSource(h,"evidenceGraph",graphFixture());
  h.run("state.data.build.observedAt=Date.now()-60001");
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
  assert.equal(h.run("evidenceGraphView().ok"),true);
  h.run('inspectSource("evidenceGraph")');
  assert.match(h.elements.get("source-inspector").textContent,/SYNTHETIC TEST INPUT/);
});
test("storage mode role and missing errors remain separate from durability", async () => {
  const h=await harness();
  setSource(h,"storage",{schema:"szl.a11oy-storage-status/v2",mode:"FENCED",role:"WRITER",writable:true,pending_publish:[],active_errors:null,stores:{gdw:{health:"BLOCKED",last_snapshot_age_s:null,unsnapshotted_change_age_s:5}}});
  h.run('openRoom("evidence")');
  const text=h.elements.get("content").textContent;
  assert.match(text,/Storage mode FENCED/);
  assert.match(text,/Storage role WRITER/);
  assert.match(text,/Active storage errors UNAVAILABLE/);
  assert.match(text,/Pending publication 0/);
  assert.match(text,/gdw/);assert.match(text,/BLOCKED/);
  assert.doesNotMatch(text,/DURABLE|ALL HEALTHY/);
  setSource(h,"storage",{schema:"szl.a11oy-storage-status/v2",mode:"DISABLED",role:"DISABLED",writable:true});
  h.run('openRoom("evidence")');
  assert.match(h.elements.get("content").textContent,/Storage mode DISABLED/);
});
test("relationship display is bounded and source text remains literal", async () => {
  const h=await harness(),bad='<img src=x onerror="alert(1)">';
  const extra=Array.from({length:14},(_,i)=>({schema:"szl.evidence-edge/v1",subject:{kind:"artifact",id:i?String(i):bad},source_revision:null,verdict:"OBSERVED"}));
  const b=graphFixture("a".repeat(40),extra);b.graph.bounded=true;b.graph.total_input_edges=20;
  setSource(h,"evidenceGraph",b);h.run('openRoom("evidence")');
  assert.match(h.elements.get("content").textContent,/Showing 12 of 15 returned relationships; 20 input relationships/);
  assert.match(h.elements.get("content").textContent,/Backend limit applied/);
  const view=h.run("graphRelationships(evidenceGraphView())");
  assert.equal(view.children[1].children.length,12);
  assert.equal(view.children[1].children[1].children[0].tag,"span");
  assert.equal(view.children[1].children[1].children[0].textContent,"artifact · "+bad);
});
test("new graph and storage sources participate in the same read-only batch", async () => {
  const h=await harness();
  assert.equal(h.calls.filter(c=>c.url==="/api/a11oy/v1/evidence/graph").length,1);
  assert.equal(h.calls.filter(c=>c.url==="/api/a11oy/v1/storage/status").length,1);
  const before=h.calls.length;h.run('inspectSource("storage")');assert.equal(h.calls.length,before);
});

test("non-string and missing runtime identities stay unavailable", async () => {
  const h=await harness();setBuild(h);
  for(const mutate of [
    b=>b.graph.edges[0].source_revision=["a".repeat(40)],
    b=>b.graph.edges[0].subject.id="",
    b=>{b.graph.edges[0].verdict="UNAVAILABLE";b.graph.verdict_counts.OBSERVED=0;b.graph.verdict_counts.UNAVAILABLE=1;},
  ]) {
    const b=graphFixture();mutate(b);setSource(h,"evidenceGraph",b);
    assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
  }
  setSource(h,"evidenceGraph",graphFixture());
  setSource(h,"build",{status:"OBSERVED",build:{state:"OBSERVED",revision:["a".repeat(40)],revision_source:"env:SZL_GIT_SHA"}});
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
});

test("unavailable graph cannot match even when retained identity fields agree", async () => {
  const h=await harness();setBuild(h);const b=graphFixture();b.state="UNAVAILABLE";
  setSource(h,"evidenceGraph",b);
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"UNAVAILABLE");
});
test("truncation flag must agree with returned and input counts", async () => {
  const h=await harness();
  for (const [total,bounded] of [[20,false],[1,true]]) {
    const b=graphFixture();b.graph.total_input_edges=total;b.graph.bounded=bounded;
    setSource(h,"evidenceGraph",b);assert.equal(h.run("evidenceGraphView().ok"),false);
  }
});

test("HF runtime identity may differ from the explicit Git source revision", async () => {
  const h=await harness();setBuild(h);
  const b=graphFixture();b.graph.edges[0].subject.id="d".repeat(40);
  b.graph.edges[0].runtime={revision:"d".repeat(40)};
  setSource(h,"evidenceGraph",b);
  assert.equal(h.run("runtimeBinding(evidenceGraphView()).state"),"SOURCE-REPORTED MATCH");
});
test("array and object storage labels cannot masquerade as reported strings", async () => {
  const h=await harness();
  for(const value of [["FENCED"],{},true,"","  "]) {
    setSource(h,"storage",{schema:"szl.a11oy-storage-status/v2",mode:value,role:value,writable:true,stores:{gdw:{health:value}}});
    h.run('openRoom("evidence")');
    const text=h.elements.get("content").textContent;
    assert.match(text,/Storage mode UNAVAILABLE/);assert.match(text,/Storage role UNAVAILABLE/);
    assert.match(text,/gdw · UNAVAILABLE/);
  }
});


test("static lineage export is a link, not an inferred successful run", async () => {
  const h=await harness();
  const before=h.calls.length;
  h.run('openRoom("evidence")');
  assert.match(h.elements.get("content").textContent,/Static lineage JSON/);
  assert.match(h.elements.get("content").textContent,/Evidence gaps \(unqualified\)/);
  assert.equal(h.calls.length,before);
  assert.equal(h.calls.filter(c=>c.url==="/api/a11oy/v1/evidence/openlineage").length,0);
  assert.equal(h.calls.filter(c=>c.url==="/api/a11oy/v1/evidence/discovery").length,0);
});
test("parent coverage without a denominator is explicitly unavailable", async () => {
  const h=await harness();
  const b=graphFixture();
  b.graph.parent_resolution={
    state:"UNAVAILABLE", authority:"OBSERVATION_ONLY",resolved:0,unresolved:0,
    denominator:0,ratio:null,unresolved_preview:[],preview_truncated:false,
    graph_bounded:false,signatures_verified:false
  };
  setSource(h,"evidenceGraph",b);
  h.run('openRoom("evidence")');
  const rendered=h.elements.get("content").textContent;
  assert.match(rendered,/Parent references UNAVAILABLE/);
  assert.match(rendered,/No parent-reference denominator/);
});
