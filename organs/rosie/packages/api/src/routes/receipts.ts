/**
 * @file packages/api/src/routes/receipts.ts
 * @description Receipt read, stream, and verification.
 *
 *   GET  /v1/receipts          → paginated list (app, since, limit, cursor)
 *   GET  /v1/receipts/stream   → SSE stream (event: receipt + 30s heartbeat)
 *   GET  /v1/receipts/:id      → single receipt with DSSE envelope + chain
 *   POST /v1/receipts/verify   → DSSE + chain verification (same as Gradio tab)
 *
 * Route order matters: /stream and /verify are registered before /:id so they
 * are not captured by the id param.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import { problemResponse } from '../lib/problem.ts';
import { sseStream, SSE_HEADERS } from '../lib/sse.ts';
import type { Receipt } from '../types/index.ts';

export const receiptsRoute = new Hono<AppEnv>();

// GET /v1/receipts — list (paginated)
receiptsRoute.get('/', (c) => {
  const svc = c.get('services');
  const app = c.req.query('app');
  const since = c.req.query('since');
  const limit = Math.min(Math.max(Number(c.req.query('limit') ?? 50), 1), 200);
  const offset = Number(c.req.query('cursor') ?? 0) || 0;
  const { items, nextOffset } = svc.store.list({ app, since, limit, offset });
  return c.json({ items, next_cursor: nextOffset === null ? null : String(nextOffset) });
});

// GET /v1/receipts/stream — Server-Sent Events
receiptsRoute.get('/stream', (c) => {
  const svc = c.get('services');
  const app = c.req.query('app');
  // Heartbeat may be shortened via query for tests; defaults to 30s.
  const heartbeatMs = Number(c.req.query('heartbeat_ms')) || undefined;
  const existing = svc.store.all().filter((r) => !app || decodeApp(r) === app);

  async function* gen(): AsyncIterable<Receipt> {
    for (const r of existing) yield r;
    // Real impl would tail the substrate; the stub replays the snapshot and
    // then relies on the heartbeat to keep the connection open.
  }

  for (const [k, v] of Object.entries(SSE_HEADERS)) c.header(k, v);
  return c.body(sseStream(gen(), { heartbeatMs }) as unknown as ReadableStream);
});

// POST /v1/receipts/verify — DSSE + chain verification
receiptsRoute.post('/verify', async (c) => {
  const svc = c.get('services');
  let body: Receipt;
  try {
    body = (await c.req.json()) as Receipt;
  } catch {
    return problemResponse(c, 'invalid-json', 422, 'Request body is not valid JSON');
  }
  let verdict;
  try {
    verdict = svc.substrate.verify(body);
  } catch (e) {
    verdict = { verified: false, errors: [`verification error: ${(e as Error).message}`] };
  }
  return c.json(verdict);
});

// GET /v1/receipts/:id — single receipt
receiptsRoute.get('/:id', (c) => {
  const svc = c.get('services');
  const id = c.req.param('id');
  const receipt = svc.store.get(id);
  if (!receipt) {
    return problemResponse(c, 'receipt-not-found', 404, 'No such receipt');
  }
  return c.json(receipt);
});

function decodeApp(r: Receipt): string | undefined {
  try {
    const body = JSON.parse(Buffer.from(r.payload, 'base64').toString('utf8')) as Record<string, unknown>;
    if (typeof body.app === 'string') return body.app;
    const target = body.target as { module?: string } | undefined;
    return target?.module;
  } catch {
    return undefined;
  }
}
