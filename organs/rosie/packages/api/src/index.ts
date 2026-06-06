/**
 * @file packages/api/src/index.ts
 * @description rosie-api bootstrap.
 *
 * Reads env, loads the runtime Ed25519 signer (no committed keys), wires the
 * in-memory store + receipt substrate, structured logging (pino), and starts
 * the Hono server on @hono/node-server.
 *
 * Env:
 *   PORT                  — listen port (default 8080)
 *   RECEIPTS_BACKEND_URL  — szl-receipts-server base URL (real backend)
 *   KEYCLOAK_ISSUER_URL   — OIDC issuer (realm) URL
 *   KEYCLOAK_AUDIENCE     — expected `aud` (default "rosie-api")
 *   SZL_ED25519_KEY_PATH  — PEM path for the signing key (Secret mount)
 *   SZL_KEY_ID            — signing key id surfaced in DSSE signatures[].keyid
 *   CORS_ORIGINS          — comma-separated widget hosts
 *   GIT_COMMIT            — build commit SHA (set by Dockerfile)
 *   APP_VERSION           — semver (set by Dockerfile)
 */

import { serve } from '@hono/node-server';
import pino from 'pino';
import { createApp } from './app.ts';
import { ReceiptStore } from './lib/store.ts';
import { createSubstrate, loadEd25519Signer } from './lib/receipt-substrate.ts';
import type { Services } from './lib/env.ts';

const log = pino({ name: 'rosie-api', level: process.env.LOG_LEVEL ?? 'info' });

const PORT = Number(process.env.PORT ?? 8080);
const ISSUER = process.env.KEYCLOAK_ISSUER_URL ?? 'https://sso.szlholdings.com/realms/szl';
const AUDIENCE = process.env.KEYCLOAK_AUDIENCE ?? 'rosie-api';
const KEY_PATH = process.env.SZL_ED25519_KEY_PATH;
const KEY_ID = process.env.SZL_KEY_ID ?? 'rosie-api-ed25519-2026';
const CORS_ORIGINS = (process.env.CORS_ORIGINS ?? '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

// Runtime-loaded Ed25519 signer (degraded/unsigned if no key present).
const signer = loadEd25519Signer(KEY_PATH, KEY_ID);
if (!signer.publicKey()) {
  log.warn('No Ed25519 key loaded (SZL_ED25519_KEY_PATH unset/absent); running in unsigned degraded mode.');
}

const services: Services = {
  substrate: createSubstrate(signer),
  store: new ReceiptStore(),
  startedAt: Date.now(),
  version: process.env.APP_VERSION ?? '1.0.0',
  commit: process.env.GIT_COMMIT ?? 'dev',
};

const app = createApp({
  services,
  auth: { issuer: ISSUER, audience: AUDIENCE },
  corsOrigins: CORS_ORIGINS.length ? CORS_ORIGINS : undefined,
});

// Structured request logging.
app.use('*', async (c, next) => {
  const start = Date.now();
  await next();
  log.info(
    { method: c.req.method, path: c.req.path, status: c.res.status, ms: Date.now() - start, rid: c.get('requestId') },
    'request'
  );
});

log.info({ port: PORT, issuer: ISSUER, audience: AUDIENCE, receipts_backend: process.env.RECEIPTS_BACKEND_URL }, 'starting rosie-api');

serve({ fetch: app.fetch, port: PORT }, (info) => {
  log.info({ port: info.port }, 'rosie-api listening');
});
