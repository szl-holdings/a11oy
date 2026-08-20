// a11oy orchestration client — REAL wiring (browser-safe, gated transport).
//
// Replaces the former no-op stub. Payload shapes are validated at compile time
// against the REAL @szl-holdings packages (type-only imports → erased; the
// Node-only receipt substrate never enters the browser bundle). Transmits to
// a11oy's receipt endpoint when VITE_A11OY_RECEIPT_URL is set, else no-ops
// exactly as before. See wiring/CURSOR_HANDOFF.md.

import type { ToolEnvelope } from '@szl-holdings/a11oy-receipt-substrate';
import type { CrossRepoHandoffReceiptInput } from '@szl-holdings/a11oy-policy/contracts/cross-repo-handoff';

const RECEIPT_BASE: string | undefined = (import.meta as { env?: Record<string, string> }).env?.VITE_A11OY_RECEIPT_URL;

async function transmit(path: string, body: unknown): Promise<void> {
  if (!RECEIPT_BASE) return; // gated: preserve prior no-op until endpoint exists
  try {
    await fetch(`${RECEIPT_BASE}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    // fire-and-forget: a11oy telemetry must never break the host UI
  }
}

export async function registerWithA11oy(opts: {
  product: string;
  displayName?: string;
  basePath?: string;
  accentColor?: string;
  capabilities?: Array<{ id: string; label: string; governanceClass: string }>;
}): Promise<void> {
  await transmit('/register', opts);
}

export async function emitProof(opts: {
  product: string;
  kind: string;
  summary: string;
  deepLink: string;
  payload: Record<string, unknown>;
}): Promise<void> {
  const envelope: Pick<ToolEnvelope, 'protocol' | 'actor_id' | 'tool_name' | 'lambda_axes' | 'payload'> = {
    protocol: 'a11oy',
    actor_id: opts.product,
    tool_name: opts.kind,
    lambda_axes: ['Λ7'],
    payload: { summary: opts.summary, deepLink: opts.deepLink, ...opts.payload },
  };
  await transmit('/receipts', envelope);
}

// Was MISSING from the prior stub even though autonomous-threat-engine.tsx
// imports it (silently undefined at runtime, swallowed by TS `any`). Now a real
// gated adapter mapping onto CrossRepoHandoffReceiptInput.
export async function crossProductHandoff(opts: {
  fromProduct: string;
  toProduct: string;
  refId: string;
  reason: string;
  deepLink: string;
}): Promise<void> {
  const input: CrossRepoHandoffReceiptInput = {
    handoffId: opts.refId,
    actorId: opts.fromProduct,
    outcome: 'queued',
    details: {
      fromProduct: opts.fromProduct,
      toProduct: opts.toProduct,
      reason: opts.reason,
      deepLink: opts.deepLink,
    },
  };
  await transmit('/handoffs', input);
}

// NOTE: routeModel has NO corresponding export in any a11oy package (verified
// against fresh source: packages/policy, packages/rae1, etc.). It is
// imported by web/src/pages/autonomous-threat-engine.tsx and was previously
// undefined at runtime. Until a11oy publishes a model-router export, this is a
// gated transport stub (POSTs to /route when the endpoint env var is set, else
// no-op) — call-ready, not fabricated. Owner decision flagged in
// wiring/CURSOR_HANDOFF.md.
export async function routeModel(opts: {
  product: string;
  model: string;
  purpose: string;
  deepLink: string;
}): Promise<void> {
  await transmit('/route', opts);
}

export function useA11oyCapabilities() {
  return { capabilities: [] as unknown[], register: registerWithA11oy };
}

export function useA11oyOrchestration() {
  return { emit: emitProof, subscribe: () => () => {} };
}
