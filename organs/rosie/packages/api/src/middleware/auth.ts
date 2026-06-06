/**
 * @file packages/api/src/middleware/auth.ts
 * @description OIDC Bearer (Keycloak via UDS authservice) JWT verification.
 *
 * Verifies the RS256/ES256 JWT against the Keycloak realm JWKS (same realm the
 * szl-receipts-server uses), enforces `aud === KEYCLOAK_AUDIENCE` and a required
 * group, and stashes the verified claims on c.var.user.
 *
 * The JWT signing public keys come from the realm JWKS endpoint — see the
 * key-custody runbook (PhD SecOps, in parallel) for the authoritative source.
 * No keys are committed here; the JWKS is fetched at runtime and cached by jose.
 *
 * /v1/health is exempt (mounted before this middleware).
 */

import type { Context, MiddlewareHandler } from 'hono';
import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose';
import { problemResponse } from '../lib/problem.ts';
import type { RosieClaims } from '../types/index.ts';

export interface AuthConfig {
  issuer: string;
  audience: string;
  /** Override the JWKS resolver — tests inject a local key set. */
  jwksResolver?: Parameters<typeof jwtVerify>[1];
}

export const GROUP_OPERATORS = 'szl-operators';
export const GROUP_EXECUTORS = 'szl-executors';

function groupsOf(payload: JWTPayload): string[] {
  const g = (payload as Record<string, unknown>).groups;
  if (Array.isArray(g)) return g.filter((x): x is string => typeof x === 'string');
  return [];
}

/**
 * Build the auth middleware. `requiredGroup` gates the route group:
 * szl-operators for reads, szl-executors for /v1/execute*.
 */
export function auth(cfg: AuthConfig, requiredGroup: string): MiddlewareHandler {
  const jwks =
    cfg.jwksResolver ??
    createRemoteJWKSet(new URL(`${cfg.issuer.replace(/\/$/, '')}/protocol/openid-connect/certs`));

  return async (c: Context, next) => {
    const header = c.req.header('authorization') ?? '';
    const match = /^Bearer\s+(.+)$/i.exec(header);
    if (!match) {
      return problemResponse(c, 'missing-bearer', 401, 'Missing bearer token', 'Provide an OIDC Bearer token in the Authorization header.');
    }
    let payload: JWTPayload;
    try {
      const verified = await jwtVerify(match[1], jwks, {
        audience: cfg.audience,
        issuer: cfg.issuer,
      });
      payload = verified.payload;
    } catch (e) {
      return problemResponse(c, 'invalid-token', 401, 'Invalid or expired token', (e as Error).message);
    }
    const groups = groupsOf(payload);
    if (!groups.includes(requiredGroup)) {
      return problemResponse(
        c,
        'insufficient-group',
        403,
        'Insufficient group membership',
        `This endpoint requires the '${requiredGroup}' group.`
      );
    }
    c.set('user', payload as unknown as RosieClaims);
    await next();
  };
}
