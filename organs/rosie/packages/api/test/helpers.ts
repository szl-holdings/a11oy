/**
 * @file packages/api/test/helpers.ts
 * @description Test helpers: build the app with a deterministic Ed25519 signer
 * and mint local JWTs signed by a key whose JWKS we inject (no network).
 */

import { generateKeyPair, exportJWK, SignJWT, createLocalJWKSet, type JSONWebKeySet } from 'jose';
import { createApp } from '../src/app.ts';
import { ReceiptStore } from '../src/lib/store.ts';
import { createSubstrate, type ReceiptSigner } from '../src/lib/receipt-substrate.ts';
import { dsseV1Pae } from '../src/lib/dsse-pae.ts';
import { generateKeyPairSync, sign as edSign } from 'node:crypto';
import type { AppEnv } from '../src/lib/env.ts';
import type { Hono } from 'hono';

export const ISSUER = 'https://sso.test/realms/szl';
export const AUDIENCE = 'rosie-api';

/** Build a real in-memory Ed25519 receipt signer for tests. */
export function testSigner(): ReceiptSigner {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  return {
    keyid: 'rosie-api-test-ed25519',
    alg: 'ed25519',
    sign(pae: Uint8Array): string {
      return Buffer.from(edSign(null, Buffer.from(pae), privateKey)).toString('base64url');
    },
    publicKey() {
      return publicKey;
    },
  };
}

export interface TestRig {
  app: Hono<AppEnv>;
  signer: ReceiptSigner;
  store: ReceiptStore;
  /** Mint a JWT with the given groups + optional step-up timestamp. */
  token(opts: { groups: string[]; stepUpAt?: string | number; sub?: string }): Promise<string>;
}

/** Build a fully wired test app with a local JWKS the auth middleware verifies against. */
export async function buildRig(opts: { now?: () => number } = {}): Promise<TestRig> {
  // Asymmetric key for signing test JWTs (EdDSA).
  const { privateKey, publicKey } = await generateKeyPair('EdDSA', { crv: 'Ed25519' });
  const jwk = await exportJWK(publicKey);
  jwk.kid = 'test-key';
  jwk.alg = 'EdDSA';
  jwk.use = 'sig';
  const jwks: JSONWebKeySet = { keys: [jwk] };
  const jwksResolver = createLocalJWKSet(jwks);

  const signer = testSigner();
  const store = new ReceiptStore();
  const app = createApp({
    services: {
      substrate: createSubstrate(signer),
      store,
      startedAt: Date.now(),
      version: '1.0.0-test',
      commit: 'testsha',
    },
    auth: { issuer: ISSUER, audience: AUDIENCE, jwksResolver },
    now: opts.now,
  });

  async function token(o: { groups: string[]; stepUpAt?: string | number; sub?: string }): Promise<string> {
    const claims: Record<string, unknown> = { groups: o.groups };
    if (o.stepUpAt !== undefined) claims.step_up_completed_at = o.stepUpAt;
    return new SignJWT(claims)
      .setProtectedHeader({ alg: 'EdDSA', kid: 'test-key' })
      .setSubject(o.sub ?? 'operator@szl')
      .setAudience(AUDIENCE)
      .setIssuer(ISSUER)
      .setIssuedAt()
      .setExpirationTime('10m')
      .sign(privateKey);
  }

  return { app, signer, store, token };
}

/** Build a valid signed receipt body+envelope for verify tests. */
export function buildSignedReceipt(signer: ReceiptSigner, body: unknown) {
  // Use the substrate directly to avoid duplicating PAE logic.
  const sub = createSubstrate(signer);
  return sub.emit(body, null, 0);
}

export { dsseV1Pae };
