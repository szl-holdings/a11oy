/**
 * @file packages/api/src/routes/ask.ts
 * @description POST /v1/ask — question/answer surface that records an audit receipt.
 *
 * Reads from the receipt substrate + memory/state of the addressed organ. The
 * answer and the question are recorded together in a DSSE receipt for audit.
 * The backing answer engine is stubbed (in-memory) until RECEIPTS_BACKEND_URL
 * and the per-organ read adapters are wired; the receipt emission is real.
 */

import { Hono } from 'hono';
import { randomUUID } from 'node:crypto';
import type { AppEnv } from '../lib/env.ts';
import { problemResponse } from '../lib/problem.ts';
import type { AskResponse, AppName, Citation } from '../types/index.ts';

export const askRoute = new Hono<AppEnv>();

const APPS: AppName[] = ['a11oy', 'amaru', 'sentra', 'vessels', 'rosie'];

askRoute.post('/', async (c) => {
  let body: { app?: string; question?: string; conversation_id?: string };
  try {
    body = await c.req.json();
  } catch {
    return problemResponse(c, 'invalid-json', 422, 'Request body is not valid JSON');
  }
  if (!body.app || !APPS.includes(body.app as AppName)) {
    return problemResponse(c, 'invalid-app', 422, 'Invalid or missing app', `app must be one of ${APPS.join(', ')}`);
  }
  if (!body.question || typeof body.question !== 'string' || body.question.trim() === '') {
    return problemResponse(c, 'invalid-question', 422, 'Missing question');
  }

  const svc = c.get('services');
  const user = c.get('user');
  const conversationId = body.conversation_id ?? randomUUID();

  // Stub answer engine. Real impl reads a11oy receipts + amaru memory +
  // sentra verdicts + vessels state for the addressed organ.
  const answer = `Acknowledged for ${body.app}: "${body.question.trim()}". Backed by the ${body.app} read substrate.`;
  const citations: Citation[] = [
    {
      source: `${body.app} receipt substrate`,
      url: `https://docs.szlholdings.com/${body.app}/receipts`,
    },
  ];

  // Record the Q+A as an audit receipt on the chain.
  const receipt = svc.substrate.emit(
    {
      kind: 'ask',
      app: body.app,
      asker: user.sub,
      question: body.question.trim(),
      answer,
      conversation_id: conversationId,
    },
    svc.store.headHash,
    svc.store.nextIndex
  );
  const receiptId = svc.store.append(receipt);

  const res: AskResponse = {
    answer,
    citations,
    conversation_id: conversationId,
    receipt_id: receiptId,
  };
  return c.json(res);
});
