/**
 * @file packages/api/src/routes/mesh.ts
 * @description GET /v1/mesh/health — per-module mesh health.
 *
 * Aggregates from a11oy + szl-receipts-server + sentra. The stub returns the
 * static module topology with the last receipt timestamp drawn from the local
 * chain; the real impl queries each module's /healthz and the receipts server.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import type { MeshHealthReport, ModuleHealth } from '../types/index.ts';

export const meshRoute = new Hono<AppEnv>();

meshRoute.get('/health', (c) => {
  const svc = c.get('services');
  const all = svc.store.all();
  const lastReceipt = all.length ? all[all.length - 1].chain.ts : null;

  const modules: ModuleHealth[] = [
    {
      name: 'a11oy',
      namespace: 'szl-organs',
      status: 'healthy',
      last_receipt: lastReceipt,
      signing_key_id: 'szl-a11oy-ed25519-2026',
      replicas: { desired: 2, ready: 2 },
    },
    {
      name: 'szl-receipts-server',
      namespace: 'szl-receipts',
      status: 'healthy',
      last_receipt: lastReceipt,
      signing_key_id: 'szl-receipts-ed25519-2026',
      replicas: { desired: 2, ready: 2 },
    },
    {
      name: 'sentra',
      namespace: 'szl-organs',
      status: 'healthy',
      last_receipt: lastReceipt,
      signing_key_id: 'szl-sentra-ed25519-2026',
      replicas: { desired: 2, ready: 2 },
    },
  ];

  const report: MeshHealthReport = {
    generated_at: new Date().toISOString(),
    modules,
  };
  return c.json(report);
});
