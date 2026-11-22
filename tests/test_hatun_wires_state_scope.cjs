// SPDX-License-Identifier: Apache-2.0
// Source-owned, offline contract test for the Hatun /wires status projection.
// Exercises the exact embedded renderer functions, not a copied approximation.
"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "pages", "wires.html"), "utf8");
const lines = source.split(/\r?\n/);
const oneLine = (prefix) => {
  const line = lines.find((value) => value.trimStart().startsWith(prefix));
  assert.ok(line, "missing owned source function: " + prefix);
  return line.trim();
};
const code = [
  oneLine("var ALLOWED="),
  ...["text", "state", "pick", "wireCard"].map((name) => oneLine("function " + name + "(")),
].join("\n");
const makeElement = (tag) => ({
  tag, dataset: {}, children: [], className: "", textContent: "",
  append(...children) { this.children.push(...children); },
});
const sandbox = { document: { createElement: makeElement } };
vm.runInNewContext(code, sandbox, { filename: "wires-owned-renderer.js", timeout: 1000 });

test("source-authoritative in-process wire survives without claiming cross-Space LIVE", () => {
  const item = sandbox.wireCard({
    id: "D", status: "LIVE_IN_PROCESS",
    detail: "traceparent in process; cross-Space broker NOT wired",
  }, 0);
  assert.equal(item.dataset.state, "LIVE_IN_PROCESS");
  assert.equal(item.children[0].children[2].textContent, "LIVE_IN_PROCESS");
  assert.match(item.children[1].textContent, /cross-Space broker NOT wired/);
  assert.notEqual(item.dataset.state, "LIVE");
  assert.match(source, /\.wire\[data-state="LIVE_IN_PROCESS"\] \.wire-state,[^\n]*\{color:var\(--signal\)\}/);
});

test("unrecognized states are still unavailable, never promoted to LIVE", () => {
  for (const input of ["UNRECOGNIZED", "PRODUCTION_READY", "", null, undefined, "<script>"]) {
    const item = sandbox.wireCard({ id: "D", status: input }, 0);
    assert.equal(item.dataset.state, "UNAVAILABLE");
    assert.equal(item.children[0].children[2].textContent, "UNAVAILABLE");
  }
});

test("other known scoped and reported states preserve exact meaning", () => {
  for (const expected of ["LIVE", "MEASURED", "REPORTED", "DECLARED", "DEGRADED", "UNAVAILABLE"]) {
    assert.equal(sandbox.wireCard({ id: "B", state: expected }, 0).dataset.state, expected);
  }
  // Scope-specific process observation is intentionally NOT styled as full green LIVE.
  assert.match(source, /\.wire\[data-state="LIVE"\] \.wire-state[^\n]*var\(--success\)/);
});
