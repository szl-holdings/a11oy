/**
 * @file packages/api/src/app.ts
 * @description Hono app factory. Wires routers, auth, and step-up.
 *
 * The factory takes the injected services + an auth config so tests can call
 * `app.request(...)` directly with a local JWKS, and index.ts can wire the real
 * services + the remote Keycloak JWKS. /v1/health is mounted BEFORE auth so it
 * is reachable unauthenticated (liveness probe).
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import type { AppEnv, Services } from './lib/env.ts';
import { auth, type AuthConfig, GROUP_OPERATORS, GROUP_EXECUTORS } from './middleware/auth.ts';
import { stepUp } from './middleware/step-up.ts';
import { aboutRoute } from './routes/about.ts';
import { askRoute } from './routes/ask.ts';
import { executeRoute, confirmRoute } from './routes/execute.ts';
import { receiptsRoute } from './routes/receipts.ts';
import { meshRoute } from './routes/mesh.ts';
import { doctrineRoute } from './routes/doctrine.ts';
import { formulasRoute } from './routes/formulas.ts';

export interface AppOptions {
  services: Services;
  auth: AuthConfig;
  /** Allowed CORS origins (the widget hosts). */
  corsOrigins?: string[];
  /** Clock injection for step-up freshness checks (tests). */
  now?: () => number;
}

export function createApp(opts: AppOptions): Hono<AppEnv> {
  const app = new Hono<AppEnv>();

  // Request-id + service injection (runs for every request).
  app.use('*', async (c, next) => {
    const rid = c.req.header('x-request-id') ?? crypto.randomUUID();
    c.set('requestId', rid);
    c.set('services', opts.services);
    c.header('x-request-id', rid);
    await next();
  });

  app.use(
    '*',
    cors({
      origin: opts.corsOrigins ?? '*',
      allowMethods: ['GET', 'POST', 'OPTIONS'],
      allowHeaders: ['authorization', 'content-type', 'x-request-id'],
    })
  );

  // ── /v1/health — unauthenticated liveness ───────────────────────────────────
  app.get('/v1/health', (c) => {
    const svc = c.get('services');
    return c.json({
      status: 'ok' as const,
      version: svc.version,
      commit: svc.commit,
      uptime_s: (Date.now() - svc.startedAt) / 1000,
    });
  });

  // ── Read endpoints (szl-operators) ───────────────────────────────────────────
  const operatorAuth = auth(opts.auth, GROUP_OPERATORS);
  app.use('/v1/ask', operatorAuth);
  app.use('/v1/receipts', operatorAuth);
  app.use('/v1/receipts/*', operatorAuth);
  app.use('/v1/mesh/*', operatorAuth);
  app.use('/v1/doctrine/*', operatorAuth);
  app.use('/v1/formulas/*', operatorAuth);
  app.use('/v1/about', operatorAuth);

  // ── Execute endpoints (szl-executors) ────────────────────────────────────────
  const executorAuth = auth(opts.auth, GROUP_EXECUTORS);
  app.use('/v1/execute', executorAuth);
  app.use('/v1/execute/confirm', executorAuth);
  // Step-up re-auth gate runs after executor auth, only on confirm.
  app.use('/v1/execute/confirm', stepUp(opts.now));

  // ── Mount routers ────────────────────────────────────────────────────────────
  app.route('/v1/ask', askRoute);
  app.route('/v1/execute/confirm', confirmRoute);
  app.route('/v1/execute', executeRoute);
  app.route('/v1/receipts', receiptsRoute);
  app.route('/v1/mesh', meshRoute);
  app.route('/v1/doctrine', doctrineRoute);
  app.route('/v1/formulas', formulasRoute);
  app.route('/v1/about', aboutRoute);

  return app;
}
