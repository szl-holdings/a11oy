/**
 * @file packages/api/src/lib/env.ts
 * @description Hono environment bindings + the injected service surface.
 */

import type { ReceiptSubstrate } from './receipt-substrate.ts';
import type { ReceiptStore } from './store.ts';
import type { RosieClaims } from '../types/index.ts';

/** Services injected into the Hono app (enables test doubles). */
export interface Services {
  substrate: ReceiptSubstrate;
  store: ReceiptStore;
  /** Process start time, ms epoch — for uptime. */
  startedAt: number;
  version: string;
  commit: string;
}

/** Hono generic env: variables available on `c.var`. */
export interface AppEnv {
  Variables: {
    user: RosieClaims;
    services: Services;
    requestId: string;
  };
}
