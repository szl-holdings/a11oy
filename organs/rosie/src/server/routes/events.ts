// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * routes/events.ts — Express router for the /v1/events and /v1/receipts/:seq
 * endpoints, plus /healthz.
 *
 * POST /v1/events
 *   Accepts a RosieEvent body, validates with zod, ingests into the khipu-
 *   receipt DAG via EventStore, and returns the resulting receipt metadata.
 *
 * GET /v1/receipts/:seq
 *   Returns the stored EventReceiptEntry for the given 1-based seq number,
 *   or 404 if not found.
 *
 * GET /healthz
 *   Returns process health and current DAG head state.
 */

import { Router, type Request, type Response } from 'express';
import { z } from 'zod';
import { globalEventStore, type EventStore } from '../event-store.ts';

// ---------------------------------------------------------------------------
// Zod schema — RosieEvent
// ---------------------------------------------------------------------------

/** Matches the payload shape that a11oy mesh-router sends via notifyRosie(). */
const RosieEventSchema = z.object({
  type: z.string().min(1),
  source: z.string().min(1),
  payload: z.record(z.unknown()).default({}),
  traceparent: z.string().optional(),
});

export type RosieEvent = z.infer<typeof RosieEventSchema>;

// ---------------------------------------------------------------------------
// Router factory — accepts an EventStore so tests can inject a clean instance
// ---------------------------------------------------------------------------

export function createEventsRouter(store: EventStore = globalEventStore): Router {
  const router = Router();

  // -------------------------------------------------------------------------
  // GET /healthz
  // -------------------------------------------------------------------------
  router.get('/healthz', (_req: Request, res: Response) => {
    res.status(200).json({
      status: 'ok',
      head_seq: store.headSeq,
      root_hash: store.headRootHash,
    });
  });

  // -------------------------------------------------------------------------
  // POST /v1/events
  // -------------------------------------------------------------------------
  router.post('/v1/events', (req: Request, res: Response) => {
    const parsed = RosieEventSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({
        error: 'invalid_event',
        details: parsed.error.flatten(),
      });
      return;
    }

    const { type, source, payload, traceparent } = parsed.data;

    try {
      const result = store.ingest(type, source, payload, traceparent);
      res.status(200).json(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(500).json({ error: 'ingest_failed', message });
    }
  });

  // -------------------------------------------------------------------------
  // GET /v1/receipts/:seq
  // -------------------------------------------------------------------------
  router.get('/v1/receipts/:seq', (req: Request, res: Response) => {
    const seqNum = parseInt(req.params['seq'] ?? '', 10);
    if (Number.isNaN(seqNum) || seqNum < 1) {
      res.status(400).json({ error: 'invalid_seq', message: 'seq must be a positive integer' });
      return;
    }

    const entry = store.getBySeq(seqNum);
    if (!entry) {
      res.status(404).json({ error: 'not_found', seq: seqNum });
      return;
    }

    res.status(200).json(entry);
  });

  return router;
}
