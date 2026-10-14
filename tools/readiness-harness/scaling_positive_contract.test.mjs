// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { validateSchema } from "./probe_runner.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const matrix = JSON.parse(readFileSync(join(here, "tabs.json"), "utf8"));
const stressTargets = JSON.parse(readFileSync(join(here, "stress", "stress-targets.json"), "utf8"));
const scalingTab = matrix.tabs.find((tab) => tab.key === "scaling");

const positiveCases = [
  ["kleiber", "scaling_kleiber_positive", { M_kg: 70, B_kcal_day: 1694.031844745511 }],
  ["mte", "scaling_mte_positive", { M_kg: 70, T_K: 310, B: 4.588225239766344e-8 }],
  ["heart", "scaling_heart_positive", { M_kg: 70, bpm: 83.32, lifespan_yr: 34.13 }],
  ["unified", "scaling_unified_positive", {
    phi: 160025.602769,
    inputs: { M_kg: 70, T_K: 310, delta_p_mV: 121.5, tau_c: 6.05 },
    status: "PROPOSED",
    note: "Engineering construct, not formal Lambda",
  }],
];

test("mass-required scaling probes exercise successful M=70 calculations", () => {
  assert.ok(scalingTab, "scaling tab must remain in the generated matrix");
  for (const [name, schemaName, response] of positiveCases) {
    const bare = `/api/a11oy/v1/scaling/${name}`;
    const positive = `${bare}?M=70`;
    const spec = matrix.endpoints[positive];
    assert.ok(spec, `${positive} must have an endpoint contract`);
    assert.equal(spec.method, "GET");
    assert.equal(spec.schema, schemaName);
    assert.deepEqual(spec.degradedRules.allowStatuses, [200]);
    assert.ok(scalingTab.endpoints.includes(positive));
    assert.ok(stressTargets.includes(positive));
    assert.equal(matrix.endpoints[bare], undefined, `${bare} is validation, not release success`);
    assert.ok(!scalingTab.endpoints.includes(bare));
    assert.ok(!stressTargets.includes(bare));
    assert.equal(validateSchema(schemaName, response).ok, true);
    assert.equal(validateSchema(schemaName, { error: { code: "validation_error" } }).ok, false);
  }
});

test("positive scaling contracts reject absent, zero, negative, or out-of-range calculations", () => {
  for (const [name, schemaName, response] of positiveCases) {
    const resultKeys = name === "kleiber" ? ["B_kcal_day"]
      : name === "mte" ? ["B"] : name === "heart" ? ["bpm", "lifespan_yr"] : ["phi"];
    for (const resultKey of resultKeys) {
      const missingCalculation = structuredClone(response);
      delete missingCalculation[resultKey];
      assert.equal(validateSchema(schemaName, missingCalculation).ok, false, name);
      for (const value of [0, -1, 1, null, true, "1", Number.NaN, Number.POSITIVE_INFINITY]) {
        assert.equal(validateSchema(schemaName, { ...response, [resultKey]: value }).ok, false,
          `${name}.${resultKey} must reject ${value}`);
      }
    }
  }
});

test("positive scaling contracts bind exact nested mass and temperature", () => {
  for (const [name, schemaName, response] of positiveCases) {
    const wrongMass = structuredClone(response);
    if (name === "unified") wrongMass.inputs.M_kg = 71;
    else wrongMass.M_kg = 71;
    assert.equal(validateSchema(schemaName, wrongMass).ok, false, `${name} wrong M`);
    if (name === "mte" || name === "unified") {
      const wrongTemperature = structuredClone(response);
      if (name === "unified") wrongTemperature.inputs.T_K = 311;
      else wrongTemperature.T_K = 311;
      assert.equal(validateSchema(schemaName, wrongTemperature).ok, false,
        `${name} wrong T_K`);
    }
  }
  const unified = positiveCases[3][2];
  assert.equal(validateSchema("scaling_unified_positive",
    { ...unified, status: "PROVEN" }).ok, false);
  for (const field of ["delta_p_mV", "tau_c"]) {
    const wrongDefault = structuredClone(unified);
    wrongDefault.inputs[field] += 1;
    assert.equal(validateSchema("scaling_unified_positive", wrongDefault).ok, false, field);
  }
});

test("positive contracts admit calculations from the actual registered Python handlers", () => {
  const script = [
    "import json, szl_scaling",
    "class App:",
    "    def __init__(self): self.routes = {}",
    "    def add_api_route(self, path, handler, **kwargs): self.routes[path] = handler",
    "app = App()",
    "szl_scaling.register(app, 'a11oy')",
    "names = ['kleiber', 'mte', 'heart', 'unified']",
    "print(json.dumps({n: app.routes['/api/a11oy/v1/scaling/' + n](M='70') for n in names}, allow_nan=False))",
  ].join("\n");
  const output = execFileSync(process.env.PYTHON || "python", ["-B", "-c", script], {
    cwd: resolve(here, "../.."), encoding: "utf8", timeout: 10000,
  });
  const actual = JSON.parse(output);
  for (const [name, schemaName] of positiveCases) {
    assert.equal(validateSchema(schemaName, actual[name]).ok, true, name);
  }
});
