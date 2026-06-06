/**
 * @file packages/api/src/middleware/step-up.ts
 * @description Step-up re-auth enforcement for /v1/execute/confirm.
 *
 * The "human-confirm" guarantee is enforced at the auth layer: the JWT must
 * carry a fresh `step_up_completed_at` claim (< STEP_UP_MAX_AGE_MS old). This
 * forces an interactive re-authentication (Keycloak step-up / ACR) immediately
 * before an irreversible execution, so a long-lived bearer token alone cannot
 * confirm an action. Mirrors the human-confirm intent of the receipt model.
 */

import type { Context, MiddlewareHandler } from 'hono';
import { problemResponse } from '../lib/problem.ts';
import type { RosieClaims } from '../types/index.ts';

/** Maximum allowed age of a step-up re-auth before confirm: 5 minutes. */
export const STEP_UP_MAX_AGE_MS = 5 * 60 * 1000;

/** Parse an ISO-8601 string or epoch-seconds number into epoch milliseconds. */
export function parseStepUp(value: string | number | undefined): number | null {
  if (value === undefined || value === null) return null;
  if (typeof value === 'number') {
    // Heuristic: treat <1e12 as epoch seconds, else milliseconds.
    return value < 1e12 ? value * 1000 : value;
  }
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : t;
}

/** Middleware that rejects confirm requests lacking a fresh step-up claim. */
export function stepUp(now: () => number = Date.now): MiddlewareHandler {
  return async (c: Context, next) => {
    const user = c.get('user') as RosieClaims | undefined;
    const completedAt = parseStepUp(user?.step_up_completed_at);
    if (completedAt === null) {
      return problemResponse(
        c,
        'step-up-required',
        403,
        'Step-up re-authentication required',
        'The token must carry a step_up_completed_at claim. Re-authenticate before confirming.'
      );
    }
    const age = now() - completedAt;
    if (age > STEP_UP_MAX_AGE_MS || age < 0) {
      return problemResponse(
        c,
        'step-up-stale',
        403,
        'Step-up re-authentication stale',
        `step_up_completed_at must be less than ${STEP_UP_MAX_AGE_MS / 1000}s old.`
      );
    }
    await next();
  };
}
