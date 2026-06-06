// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * server/index.ts — HTTP event service for rosie.
 *
 * Binds Express to PORT (default 3000) and mounts the events router that
 * exposes:
 *   POST /v1/events    — ingest an operator event into the khipu-receipt DAG
 *   GET  /v1/receipts/:seq — retrieve a stored receipt by sequence number
 *   GET  /healthz      — liveness probe: {status, head_seq, root_hash}
 *
 * This resolves Wire C (PhD-CS report §3.3): a11oy mesh-router calls
 * POST /v1/events against this service. Previously no server existed; every
 * notifyRosie() call returned a TCP connection error.
 *
 * PhD-CS finding: PHD_CS_REVIEW.md §Wire C — BROKEN (no server)
 * Fixed-by: this file + src/server/routes/events.ts + src/server/event-store.ts
 */

import express from 'express';
import { createEventsRouter } from './routes/events.ts';

const PORT = parseInt(process.env['PORT'] ?? '3000', 10);

const app = express();
app.use(express.json());

// Mount the events + receipts + healthz router at root so paths resolve
// exactly as the mesh-router calls them: /v1/events, /v1/receipts/:seq, /healthz.
app.use('/', createEventsRouter());

/** Start the server. Returns the http.Server handle so callers (tests, bin)
 * can close it programmatically. */
export function startServer(port: number = PORT) {
  return app.listen(port, () => {
    console.log(`rosie HTTP event service listening on port ${port}`);
  });
}

export { app };

// ---------------------------------------------------------------------------
// Bin entry — run when invoked directly (rosie-server)
// ---------------------------------------------------------------------------
// Using import.meta.url to detect "is main" in ESM.
const selfUrl = import.meta.url;
const isMain =
  typeof selfUrl === 'string' &&
  process.argv[1] !== undefined &&
  (process.argv[1] === new URL(selfUrl).pathname ||
    process.argv[1].endsWith('rosie-server'));

if (isMain) {
  startServer();
}
