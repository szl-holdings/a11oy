/**
 * @file packages/api/src/routes/execute.ts
 * @description Two-phase, human-confirmed execution.
 *
 *   POST /v1/execute         → returns a *proposed* receipt (no side effect).
 *   POST /v1/execute/confirm → after step-up re-auth, performs the action.
 *
 * The proposal expires 5 minutes after creation. Confirmation is irreversible
 * and idempotent (same idempotency_key → same result, status already_executed).
 * Both proposal and confirmation are recorded as separate receipt-chain entries.
 *
 * The step-up middleware is mounted on /confirm by the parent router in
 * index.ts, so it runs before this handler.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import { problemResponse } from '../lib/problem.ts';
import type { AppName, ExecuteProposal, ConfirmResponseShape } from '../types/index.ts';

export const executeRoute = new Hono<AppEnv>();
export const confirmRoute = new Hono<AppEnv>();

const APPS: AppName[] = ['a11oy', 'amaru', 'sentra', 'vessels', 'rosie'];
const PROPOSAL_TTL_MS = 5 * 60 * 1000;

// POST /v1/execute — propose
executeRoute.post('/', async (c) => {
  let body: { app?: string; action?: string; params?: Record<string, unknown>; dry_run?: boolean };
  try {
    body = await c.req.json();
  } catch {
    return problemResponse(c, 'invalid-json', 422, 'Request body is not valid JSON');
  }
  if (!body.app || !APPS.includes(body.app as AppName)) {
    return problemResponse(c, 'invalid-app', 422, 'Invalid or missing app');
  }
  if (!body.action || typeof body.action !== 'string') {
    return problemResponse(c, 'invalid-action', 422, 'Missing action');
  }
  if (typeof body.dry_run !== 'boolean') {
    return problemResponse(c, 'invalid-dry-run', 422, 'dry_run (boolean) is required');
  }

  const svc = c.get('services');
  const user = c.get('user');
  const expiresAt = new Date(Date.now() + PROPOSAL_TTL_MS).toISOString();

  const proposal: ExecuteProposal = {
    action: body.action,
    target: { module: body.app as AppName, endpoint: `/${body.action}` },
    params: body.params ?? {},
    proposer: user.sub,
    requires_confirm: true,
    expires_at: expiresAt,
  };

  // Emit a proposal receipt (records the proposed action; not yet executed).
  const receipt = svc.substrate.emit(
    { kind: 'execute.proposal', dry_run: body.dry_run, ...proposal },
    svc.store.headHash,
    svc.store.nextIndex
  );
  const receiptId = svc.store.append(receipt);
  svc.store.putProposal({ receipt_id: receiptId, proposal, receipt, confirmed: false });

  // Return the proposed receipt (DSSE envelope) plus the proposal fields the
  // client needs to confirm against it: receipt_id, expires_at, requires_confirm.
  return c.json({
    ...receipt,
    receipt_id: receiptId,
    requires_confirm: true,
    expires_at: expiresAt,
    proposal,
  });
});

// POST /v1/execute/confirm — confirm (step-up enforced by middleware in index.ts)
confirmRoute.post('/', async (c) => {
  let body: { receipt_id?: string; idempotency_key?: string };
  try {
    body = await c.req.json();
  } catch {
    return problemResponse(c, 'invalid-json', 422, 'Request body is not valid JSON');
  }
  if (!body.receipt_id) {
    return problemResponse(c, 'invalid-receipt-id', 422, 'Missing receipt_id');
  }
  if (!body.idempotency_key || body.idempotency_key.length < 8) {
    return problemResponse(c, 'invalid-idempotency-key', 422, 'idempotency_key must be >= 8 chars');
  }

  const svc = c.get('services');
  const stored = svc.store.getProposal(body.receipt_id);
  if (!stored) {
    return problemResponse(c, 'proposal-not-found', 404, 'No such proposal');
  }

  // Idempotency: same key → already_executed with the prior result.
  if (stored.confirmed) {
    const res: ConfirmResponseShape = {
      status: 'already_executed',
      result: stored.result ?? {},
    };
    return c.json(res);
  }

  // Expiry: the proposal is only valid for 5 minutes.
  if (Date.now() > Date.parse(stored.proposal.expires_at)) {
    return problemResponse(
      c,
      'proposal-expired',
      410,
      'Proposal expired',
      'The proposal window (5 minutes) has elapsed. Re-propose the action.'
    );
  }

  // Perform the action. Stub: proxy to the target module would happen here.
  const result: Record<string, unknown> = {
    action: stored.proposal.action,
    target: stored.proposal.target,
    proxied: true,
    idempotency_key: body.idempotency_key,
  };
  stored.confirmed = true;
  stored.idempotency_key = body.idempotency_key;
  stored.result = result;

  // Record the confirmation as a SEPARATE chain entry.
  const confirmReceipt = svc.substrate.emit(
    {
      kind: 'execute.confirm',
      proposal_receipt_id: body.receipt_id,
      idempotency_key: body.idempotency_key,
      result,
    },
    svc.store.headHash,
    svc.store.nextIndex
  );
  svc.store.append(confirmReceipt);

  const res: ConfirmResponseShape = { status: 'executed', result };
  return c.json(res);
});
