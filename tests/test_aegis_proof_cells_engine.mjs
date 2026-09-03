// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import {
  analyzeCase,
  canonicalize,
  normalizeCaseInput,
  sha256Hex,
} from '../console/3d/aegis-proof-cells/engine.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const registry = JSON.parse(
  fs.readFileSync(path.join(root, 'console/3d/aegis-proof-cells/registry.json'), 'utf8'),
);
const demo = JSON.parse(
  fs.readFileSync(path.join(root, 'console/3d/aegis-proof-cells/demo.json'), 'utf8'),
);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

test('synthetic defensive case is admitted without authority', async () => {
  const result = await analyzeCase(clone(demo), registry);
  assert.equal(result.schema, 'szl.aegis-proof-cells.analysis/v1');
  assert.equal(result.decision.state, 'SANDBOX_READY');
  assert.equal(result.decision.reason, 'DEFENSIVE_ANALYSIS_ADMITTED');
  assert.equal(result.decision.external_writes, 'DISABLED');
  assert.deepEqual(result.decision.effectors, []);
  assert.equal(result.decision.automatic_retries, 0);
  assert.equal(result.decision.production_authorization, false);
  assert.equal(result.cells.length, 11);
  assert.match(result.case_id, /^AEGIS-[0-9A-F]{12}$/);
  assert.match(result.proof_chain.sha256, /^[0-9a-f]{64}$/);
  assert.equal(result.proof_chain.signature_status, 'UNAVAILABLE');
  assert.equal(result.proof_chain.persisted, false);
  assert.ok(result.decision.score > 0);
  assert.ok(result.decision.score <= 0.97);
});

test('identical canonical inputs yield identical receipts', async () => {
  const first = await analyzeCase(clone(demo), registry);
  const second = await analyzeCase(clone(demo), registry);
  assert.equal(first.case_id, second.case_id);
  assert.equal(first.proof_chain.sha256, second.proof_chain.sha256);
  assert.equal(canonicalize(first), canonicalize(second));
  assert.equal(await sha256Hex({ b: 2, a: 1 }), await sha256Hex({ a: 1, b: 2 }));
});

test('cross-tenant analysis is hard denied', async () => {
  const input = clone(demo);
  input.tenant = 'tenant-a';
  input.authorized_tenant = 'tenant-b';
  const result = await analyzeCase(input, registry);
  assert.equal(result.decision.state, 'DENIED');
  assert.equal(result.decision.reason, 'CROSS_TENANT_SCOPE');
  assert.equal(result.decision.score, 0);
  assert.ok(result.cells.every((cell) => cell.state === 'BLOCKED'));
});

test('offensive or destructive action is hard denied', async () => {
  for (const action of ['exploit', 'steal_credential', 'persist', 'destroy_data']) {
    const input = clone(demo);
    input.action = action;
    input.human_approval = true;
    const result = await analyzeCase(input, registry);
    assert.equal(result.decision.state, 'DENIED');
    assert.equal(result.decision.reason, 'PROHIBITED_ACTION');
    assert.equal(result.decision.production_authorization, false);
  }
});

test('stale or unavailable evidence causes abstention', async () => {
  for (const freshness of ['STALE', 'UNAVAILABLE']) {
    const input = clone(demo);
    input.evidence[0].freshness = freshness;
    const result = await analyzeCase(input, registry);
    assert.equal(result.decision.state, 'ABSTAINED');
    assert.equal(result.decision.reason, 'EVIDENCE_NOT_FRESH');
    assert.equal(result.decision.score, 0);
  }
});

test('mutating defensive action stops at human approval', async () => {
  const input = clone(demo);
  input.action = 'isolate';
  input.human_approval = false;
  const held = await analyzeCase(input, registry);
  assert.equal(held.decision.state, 'AWAITING_APPROVAL');
  assert.equal(held.decision.reason, 'HUMAN_APPROVAL_REQUIRED');
  assert.equal(held.decision.effectors.length, 0);

  input.human_approval = true;
  const reviewed = await analyzeCase(input, registry);
  assert.equal(reviewed.decision.state, 'SANDBOX_READY');
  assert.equal(reviewed.decision.production_authorization, false);
});

test('failed safety gate is a hard zero', async () => {
  const input = clone(demo);
  input.safety_gate = 0;
  const result = await analyzeCase(input, registry);
  assert.equal(result.decision.state, 'DENIED');
  assert.equal(result.decision.reason, 'SAFETY_GATE_FAILED');
  assert.equal(result.decision.score, 0);
});

test('secret-like fields are rejected before analysis', async () => {
  const input = clone(demo);
  input.api_token = 'do-not-process';
  const result = await analyzeCase(input, registry);
  assert.equal(result.decision.state, 'DENIED');
  assert.equal(result.decision.reason, 'SECRET_FIELD_REJECTED');
  assert.deepEqual(result.case_input.secret_fields_detected, ['$.api_token']);
});

test('input schema is bounded and rejects malformed evidence', () => {
  assert.throws(() => normalizeCaseInput(null), /JSON object/);
  const bad = clone(demo);
  bad.evidence[0].freshness = 'MAYBE';
  assert.throws(() => normalizeCaseInput(bad), /LIVE, CACHED, STALE, or UNAVAILABLE/);
  const huge = clone(demo);
  huge.evidence = Array.from({ length: 201 }, (_, index) => ({
    id: `e-${index}`,
    kind: 'event',
    source: 'synthetic',
    freshness: 'LIVE',
    summary: 'bounded test',
  }));
  assert.throws(() => normalizeCaseInput(huge), /exceeds 200 items/);
});
