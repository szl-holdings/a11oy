// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * tests/server/events.test.ts — HTTP event service tests.
 *
 * Coverage (≥ 5 required by Wire C remediation spec):
 *
 *  T_srv_healthz            — GET /healthz returns {status:"ok", head_seq, root_hash}
 *  T_srv_ingest             — POST /v1/events creates a receipt with accepted:true
 *  T_srv_receipt_by_seq     — receipt is retrievable via GET /v1/receipts/:seq
 *  T_srv_malformed_400      — missing required fields → 400 with details
 *  T_srv_prefix_hash_chain  — two events maintain a prefix-hash chain (summation
 *                             invariant holds for both roots; root_hash values differ)
 *  T_srv_receipt_404        — GET /v1/receipts/9999 returns 404
 *  T_srv_traceparent        — traceparent field is stored and echoed in the entry
 *
 * Run via: vitest (included in vitest.config.ts include list).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import express from 'express';
import type { Express } from 'express';
import request from 'supertest';
import { EventStore } from '../../src/server/event-store.ts';
import { createEventsRouter } from '../../src/server/routes/events.ts';
import { verifySumInvariant } from '../../src/khipu-receipt.ts';

// ---------------------------------------------------------------------------
// Test fixture: fresh Express app + clean EventStore per test suite
// ---------------------------------------------------------------------------

function buildTestApp(): { app: Express; store: EventStore } {
  const store = new EventStore();
  const app = express();
  app.use(express.json());
  app.use('/', createEventsRouter(store));
  return { app, store };
}

describe('rosie HTTP event service', () => {
  let app: Express;
  let store: EventStore;

  beforeEach(() => {
    ({ app, store } = buildTestApp());
  });

  // -------------------------------------------------------------------------
  // T_srv_healthz
  // -------------------------------------------------------------------------
  it('T_srv_healthz: GET /healthz returns ok with head_seq and root_hash', async () => {
    const res = await request(app).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
    expect(typeof res.body.head_seq).toBe('number');
    expect(typeof res.body.root_hash).toBe('string');
    // Empty store: head_seq = 0, root_hash = 'genesis'
    expect(res.body.head_seq).toBe(0);
    expect(res.body.root_hash).toBe('genesis');
  });

  // -------------------------------------------------------------------------
  // T_srv_ingest
  // -------------------------------------------------------------------------
  it('T_srv_ingest: POST /v1/events creates a receipt and returns accepted:true', async () => {
    const res = await request(app)
      .post('/v1/events')
      .set('Content-Type', 'application/json')
      .send({ type: 'decision.approved', source: 'a11oy', payload: { score: 0.9 } });

    expect(res.status).toBe(200);
    expect(res.body.accepted).toBe(true);
    expect(typeof res.body.receipt_seq).toBe('number');
    expect(res.body.receipt_seq).toBe(1);
    expect(typeof res.body.root_hash).toBe('string');
    expect(res.body.root_hash.length).toBeGreaterThan(0);
  });

  // -------------------------------------------------------------------------
  // T_srv_receipt_by_seq
  // -------------------------------------------------------------------------
  it('T_srv_receipt_by_seq: receipt is retrievable via GET /v1/receipts/:seq', async () => {
    // First ingest an event.
    const ingestRes = await request(app)
      .post('/v1/events')
      .set('Content-Type', 'application/json')
      .send({ type: 'policy.evaluated', source: 'sentra', payload: {} });

    expect(ingestRes.status).toBe(200);
    const seq: number = ingestRes.body.receipt_seq;

    // Now retrieve it.
    const getRes = await request(app).get(`/v1/receipts/${seq}`);
    expect(getRes.status).toBe(200);
    expect(getRes.body.seq).toBe(seq);
    expect(getRes.body.eventType).toBe('policy.evaluated');
    expect(getRes.body.source).toBe('sentra');

    // Verify the stored receipt passes the summation invariant.
    const invCheck = verifySumInvariant(getRes.body.receipt);
    expect(invCheck.ok).toBe(true);
  });

  // -------------------------------------------------------------------------
  // T_srv_malformed_400
  // -------------------------------------------------------------------------
  it('T_srv_malformed_400: missing required fields returns 400 with details', async () => {
    // Missing `type` and `source` — both required by RosieEventSchema.
    const res = await request(app)
      .post('/v1/events')
      .set('Content-Type', 'application/json')
      .send({ payload: { foo: 'bar' } });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('invalid_event');
    expect(res.body.details).toBeDefined();
  });

  // -------------------------------------------------------------------------
  // T_srv_prefix_hash_chain
  // -------------------------------------------------------------------------
  it(
    'T_srv_prefix_hash_chain: two events maintain prefix-hash chain and summation invariant',
    async () => {
      // Ingest first event.
      const r1 = await request(app)
        .post('/v1/events')
        .set('Content-Type', 'application/json')
        .send({ type: 'event.alpha', source: 'a11oy', payload: { value: 10 } });
      expect(r1.status).toBe(200);
      const hash1: string = r1.body.root_hash;

      // Ingest second event.
      const r2 = await request(app)
        .post('/v1/events')
        .set('Content-Type', 'application/json')
        .send({ type: 'event.beta', source: 'a11oy', payload: { value: 20 } });
      expect(r2.status).toBe(200);
      const hash2: string = r2.body.root_hash;

      // Root hashes must differ (each event produces a distinct receipt).
      expect(hash1).not.toBe(hash2);

      // Retrieve both entries and verify summation invariants independently.
      const e1 = await request(app).get('/v1/receipts/1');
      const e2 = await request(app).get('/v1/receipts/2');
      expect(e1.status).toBe(200);
      expect(e2.status).toBe(200);

      expect(verifySumInvariant(e1.body.receipt).ok).toBe(true);
      expect(verifySumInvariant(e2.body.receipt).ok).toBe(true);

      // Prefix-hash chain: entry 2's prevHash equals entry 1's selfHash.
      expect(e2.body.prevHash).toBe(e1.body.selfHash);
    },
  );

  // -------------------------------------------------------------------------
  // T_srv_receipt_404
  // -------------------------------------------------------------------------
  it('T_srv_receipt_404: GET /v1/receipts/9999 returns 404 when store is empty', async () => {
    const res = await request(app).get('/v1/receipts/9999');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('not_found');
    expect(res.body.seq).toBe(9999);
  });

  // -------------------------------------------------------------------------
  // T_srv_traceparent
  // -------------------------------------------------------------------------
  it('T_srv_traceparent: traceparent field is accepted and stored in the receipt entry', async () => {
    const tp = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';
    const res = await request(app)
      .post('/v1/events')
      .set('Content-Type', 'application/json')
      .send({
        type: 'trace.span',
        source: 'ouroboros',
        payload: {},
        traceparent: tp,
      });

    expect(res.status).toBe(200);
    expect(res.body.accepted).toBe(true);

    const entry = await request(app).get(`/v1/receipts/${res.body.receipt_seq}`);
    expect(entry.status).toBe(200);
    expect(entry.body.traceparent).toBe(tp);
  });
});
