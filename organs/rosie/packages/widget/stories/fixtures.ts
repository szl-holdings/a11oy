// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7
/**
 * fixtures.ts — deterministic sample data for stories. No network, no live
 * rosie-api. Receipt shapes match `OperationalReceipt` (schema_version 1.0.0).
 */

import type { OperationalReceipt, ProposedAction } from '../src/api-client.js';

export const sampleReceipt: OperationalReceipt = {
  schema_version: '1.0.0',
  receipt_id: 'rcpt_01J9F3K2Qh',
  event_type: 'A11OY_OPERATION',
  timestamp_iso8601: '2026-05-30T18:42:11Z',
  timestamp_tai64n: '@4000000068399b53',
  sequence: 412,
  actor_id: 'did:szl:operator:slutar',
  tool_name: 'receipted_retrieval',
  protocol: 'a11oy',
  payload_hash: 'b1946ac92492d2347c6235b4d2611184a4d2611184b1946ac9',
  prev_receipt_hash: 'a3f1c0de9b77aa01b2cc44ee55ff66001122334455667788',
  quorum_signatures: ['ed25519:zP8…a1', 'ed25519:zQ2…b7'],
  policy: {
    algorithm: 'SHA3-256',
    chaining: 'hash_chain',
    quorum: '2-of-3',
    nodes: ['node-a', 'node-b', 'node-c'],
  },
  qec_witness: {
    payload_byte: 177,
    shor_repetition_count: 9,
    shor_majority_payload: 177,
    css_x_parity: 0,
    css_z_parity: 0,
    css_consistent: true,
  },
  envelope: {
    protocol: 'a11oy',
    actor_id: 'did:szl:operator:slutar',
    tool_name: 'receipted_retrieval',
    invocation_id: 'inv_77c1',
    lambda_axes: ['safety', 'provenance'],
    payload: { query: 'recent receipts', limit: 5 },
  },
  merkle_root: 'c0ffee2233445566778899aabbccddeeff00112233445566',
};

export const sampleReceipt2: OperationalReceipt = {
  ...sampleReceipt,
  receipt_id: 'rcpt_01J9F4M7Tv',
  sequence: 413,
  tool_name: 'verify_signature',
  event_type: 'A11OY_OPERATION',
  payload_hash: 'd2611184b1946ac92492d2347c6235b4a4d2611184b1946ac9',
};

export const sampleAction: ProposedAction = {
  actionId: 'act_01J9F5P2Zb',
  action: 'deploy',
  target: 'amaru@v0.4.1',
  summary:
    'Deploy amaru v0.4.1 to the staging mesh. This emits a dual-attested ' +
    'receipt and is consequential — confirm to sign.',
  receiptPreview: {
    ...sampleReceipt,
    receipt_id: 'rcpt_preview_deploy',
    tool_name: 'deploy_package',
    sequence: 414,
    envelope: {
      ...sampleReceipt.envelope,
      tool_name: 'deploy_package',
      payload: { package: 'amaru', version: 'v0.4.1', target: 'staging-mesh' },
    },
  },
};

export const sampleExchanges = [
  { role: 'user' as const, text: 'Show me the recent receipts for this app' },
  {
    role: 'assistant' as const,
    text: 'Here are the two most recent receipts for a11oy.',
    receipts: [sampleReceipt, sampleReceipt2],
  },
  { role: 'user' as const, text: 'Verify the signature on the latest one' },
  {
    role: 'assistant' as const,
    text: 'The latest receipt (seq 413) verifies: 2-of-3 quorum satisfied, hash chain intact.',
  },
  { role: 'user' as const, text: 'Deploy amaru v0.4.1' },
  {
    role: 'assistant' as const,
    text: 'That is consequential. I have prepared the signed receipt preview — confirm to proceed.',
  },
];
