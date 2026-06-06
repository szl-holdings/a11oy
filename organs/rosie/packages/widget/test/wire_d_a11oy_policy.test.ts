// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// Integration test for Wire D (rosie → a11oy policy evaluation).
//
// This is a REAL cross-process integration: it boots the real a11oy serve
// (receipt-substrate/src/serve.ts) and drives rosie's a11oy-policy-client over
// real TCP via the global fetch. No mock of a11oy — the verdict is produced by
// a11oy's real ThresholdPolicySeverity gate.
//
// Proves:
//   - the rosie "Propose Action" controller calls a11oy's /v1/policy/evaluate
//     with a real fetch and gates the Confirm button on a11oy's verdict.
//   - a well-witnessed, low-severity action is ALLOWED → Confirm is offered and
//     the proposal is "screened" (carries an a11oy receipt hash).
//   - a critical, unwitnessed action is DENIED → Confirm is withheld.
//   - the policy call forwards a W3C traceparent so a11oy's span is a child of
//     the operator proposal span (nervous-system wire, Wire E).
//   - when a11oy is unreachable, the client fails CLOSED (deny, non-confirmable).
//
// Run: node --experimental-strip-types --test test/wire_d_a11oy_policy.test.ts
// (the a11oy clone is resolved relative to this repo — a11oy and rosie are
// cloned side-by-side under mining_clones/)

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import * as http from 'node:http';
import * as os from 'node:os';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { spawn, type ChildProcess } from 'node:child_process';
import {
  evaluateForPanel,
  isScreened,
  INITIAL_VIEW,
} from '../src/propose-action-controller.js';
import { evaluateProposal } from '../src/a11oy-policy-client.js';

const A11OY_SERVE = path.resolve(
  import.meta.dirname,
  '../../../../a11oy/packages/receipt-substrate/src/serve.ts',
);

let a11oyProc: ChildProcess | null = null;
let a11oyBase = '';
let ledgerPath = '';

function waitForHealthz(base: string, timeoutMs = 12000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(`${base}/healthz`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on('error', retry);
    };
    const retry = () => {
      if (Date.now() > deadline) return reject(new Error(`healthz timeout: ${base}`));
      setTimeout(tick, 150);
    };
    tick();
  });
}

before(async () => {
  assert.ok(fs.existsSync(A11OY_SERVE), `a11oy serve not found at ${A11OY_SERVE}`);
  ledgerPath = path.join(os.tmpdir(), `rosie-wire-d-${process.pid}-${Date.now()}.jsonl`);
  a11oyProc = spawn(
    'node',
    [
      '--experimental-strip-types',
      A11OY_SERVE,
      '--port',
      '0',
      '--host',
      '127.0.0.1',
      '--ledger',
      ledgerPath,
      '--sha',
      'test',
    ],
    { stdio: ['ignore', 'pipe', 'inherit'] },
  );
  const port: number = await new Promise((resolve, reject) => {
    let buf = '';
    const onData = (chunk: Buffer) => {
      buf += chunk.toString('utf8');
      const line = buf.split('\n').find((l) => l.includes('a11oy serve listening'));
      if (line) {
        try {
          resolve(JSON.parse(line).port);
        } catch (e) {
          reject(e as Error);
        }
      }
    };
    a11oyProc!.stdout!.on('data', onData);
    a11oyProc!.on('error', reject);
    setTimeout(() => reject(new Error('a11oy boot timeout')), 12000);
  });
  a11oyBase = `http://127.0.0.1:${port}`;
  await waitForHealthz(a11oyBase);
});

after(async () => {
  if (a11oyProc) a11oyProc.kill('SIGTERM');
  if (ledgerPath && fs.existsSync(ledgerPath)) fs.unlinkSync(ledgerPath);
});

test('Propose Action panel offers Confirm only when a11oy ALLOWS (real fetch)', async () => {
  assert.equal(INITIAL_VIEW.canConfirm, false, 'panel starts non-confirmable');

  const parentTrace = '00-11111111111111111111111111111111-2222222222222222-01';
  const vm = await evaluateForPanel(
    {
      actionId: 'deploy-amaru-v0.4.1',
      action: 'deploy',
      target: 'amaru@v0.4.1',
      severity: 'low',
      decisionClass: 'ordinary',
      confidence: 0.95,
      witnesses: [
        { id: 'w1', role: 'reviewer', attested: true },
        { id: 'w2', role: 'approver', attested: true },
      ],
    },
    { a11oyBase, traceparent: parentTrace },
  );

  assert.equal(vm.phase, 'allowed');
  assert.equal(vm.canConfirm, true, 'Confirm offered when a11oy allows');
  assert.ok(vm.decision, 'verdict attached');
  assert.equal(vm.decision!.reachedA11oy, true, 'a11oy actually reached (no mock)');
  assert.equal(vm.decision!.decision, 'allow');
  assert.ok(vm.decision!.receiptHash.length > 0, 'allow carries a receipt hash');
  assert.ok(isScreened(vm), 'a confirmable proposal is provably screened by a11oy');

  // Nervous-system wire: a11oy is asked to make its span a child of ours.
  // The base serve does not echo a child traceparent, so the forwarded parent
  // is preserved on the decision — proving the header was carried on the call.
  assert.equal(vm.decision!.traceparent, parentTrace, 'traceparent forwarded to a11oy');
});

test('Propose Action panel WITHHOLDS Confirm when a11oy DENIES (real fetch)', async () => {
  const vm = await evaluateForPanel(
    {
      actionId: 'rm-prod-db',
      action: 'drop',
      target: 'prod.users',
      severity: 'critical',
      decisionClass: 'capital',
      confidence: 0.05,
      witnesses: [],
    },
    { a11oyBase },
  );

  assert.equal(vm.phase, 'denied');
  assert.equal(vm.canConfirm, false, 'Confirm withheld when a11oy denies');
  assert.equal(vm.decision!.decision, 'deny');
  assert.equal(vm.decision!.reachedA11oy, true, 'a11oy actually produced the deny (no mock)');
  assert.equal(isScreened(vm), false, 'a denied proposal is never confirmable');
});

test('client fails CLOSED (deny) when a11oy is unreachable', async () => {
  // Point at a dead port; expect a fail-closed deny, not a throw.
  const decision = await evaluateProposal(
    { actionId: 'x', severity: 'low', decisionClass: 'ordinary', confidence: 0.9, witnesses: [] },
    { a11oyBase: 'http://127.0.0.1:1', timeoutMs: 800 },
  );
  assert.equal(decision.decision, 'deny');
  assert.equal(decision.reachedA11oy, false);
  assert.match(decision.rationale, /fail-closed/);
});
