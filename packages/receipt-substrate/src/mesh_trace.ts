// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// mesh_trace.ts — W3C Trace Context (version 00) helpers for a11oy's mesh
// server. This mirrors @szl-holdings/anatomy-contracts' trace helpers; it is
// inlined here so the receipt-substrate package keeps zero runtime deps and
// runs under `node --experimental-strip-types` with no install step. The two
// implementations are kept in lock-step (same regex, same semantics) and are
// the basis of the nervous-system wire (Wire E): a child span keeps the
// parent's trace-id and gets a fresh span-id.

import { randomBytes } from "node:crypto";

const TRACEPARENT_RE = /^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$/;

export function isValidTraceparent(value: string): boolean {
  if (!TRACEPARENT_RE.test(value)) return false;
  const traceId = value.slice(3, 35);
  const parentId = value.slice(36, 52);
  if (/^0{32}$/.test(traceId)) return false;
  if (/^0{16}$/.test(parentId)) return false;
  return true;
}

function randHex(bytes: number): string {
  return randomBytes(bytes).toString("hex");
}

export function newTraceparent(): string {
  return `00-${randHex(16)}-${randHex(8)}-01`;
}

export function childTraceparent(parent: string): string {
  if (!isValidTraceparent(parent)) return newTraceparent();
  const traceId = parent.slice(3, 35);
  const flags = parent.slice(53, 55);
  return `00-${traceId}-${randHex(8)}-${flags}`;
}

export function traceIdOf(traceparent: string): string | null {
  if (!isValidTraceparent(traceparent)) return null;
  return traceparent.slice(3, 35);
}

/** In-memory span record for cross-process trace verification in tests. */
export interface SpanRecord {
  readonly name: string;
  readonly traceId: string;
  readonly spanId: string;
  readonly parentSpanId: string | null;
}

/** Parse a traceparent into {traceId, spanId} or null. */
export function parseTraceparent(
  traceparent: string,
): { traceId: string; spanId: string } | null {
  if (!isValidTraceparent(traceparent)) return null;
  return { traceId: traceparent.slice(3, 35), spanId: traceparent.slice(36, 52) };
}
