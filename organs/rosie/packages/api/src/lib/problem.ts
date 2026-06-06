/**
 * @file packages/api/src/lib/problem.ts
 * @description RFC 7807 problem-details helper.
 *
 * Every error response is application/problem+json with a `type` URI under
 * https://docs.szlholdings.com/errors/<short_name>.
 */

import type { Context } from 'hono';

export const ERROR_BASE = 'https://docs.szlholdings.com/errors';

export interface ProblemBody {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
}

/** Build an RFC 7807 problem body. */
export function problem(shortName: string, status: number, title: string, detail?: string): ProblemBody {
  return { type: `${ERROR_BASE}/${shortName}`, title, status, detail };
}

/** Write a problem+json response onto a Hono context. */
export function problemResponse(
  c: Context,
  shortName: string,
  status: number,
  title: string,
  detail?: string
): Response {
  const body = problem(shortName, status, title, detail);
  body.instance = c.req.path;
  c.header('Content-Type', 'application/problem+json');
  return c.body(JSON.stringify(body), status as never);
}
