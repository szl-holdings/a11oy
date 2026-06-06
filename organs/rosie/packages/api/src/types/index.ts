/**
 * @file packages/api/src/types/index.ts
 * @description Shared API + receipt types.
 *
 * COORDINATION: The widget agent imports these via @szl-holdings/rosie-api-types
 * (this directory is the source; package.json exports map "./types"). Do NOT
 * redefine Receipt anywhere else — it mirrors the DSSE envelope used by
 * @szl-holdings/a11oy-receipt-substrate. Once that package is published, the
 * Receipt/ChainPointer/DsseSignature shapes here should be re-exported from it
 * (kept structurally identical in the meantime).
 */

export type AppName = 'a11oy' | 'amaru' | 'sentra' | 'vessels' | 'rosie';

// ── DSSE receipt (mirrors @szl-holdings/a11oy-receipt-substrate) ──────────────

export interface DsseSignature {
  keyid: string;
  /** base64url Ed25519 signature over the canonical DSSE v1 PAE. */
  sig: string;
  alg: 'ed25519';
}

export interface ChainPointer {
  /** SHA-256 of the previous receipt line, or "GENESIS". */
  prev_hash: string;
  index: number;
  ts: string;
}

export interface Receipt {
  /** base64 of the canonical-JSON receipt body. */
  payload: string;
  payloadType: string;
  signatures: DsseSignature[];
  chain: ChainPointer;
}

// ── Execution ─────────────────────────────────────────────────────────────────

export interface ExecuteTarget {
  module: AppName;
  endpoint: string;
}

export interface ExecuteProposal {
  action: string;
  target: ExecuteTarget;
  params: Record<string, unknown>;
  /** The human or agent subject (`sub`) that proposed the action. */
  proposer: string;
  requires_confirm: true;
  /** ISO-8601, 5 minutes from creation. */
  expires_at: string;
}

export interface ConfirmResponseShape {
  status: 'executed' | 'failed' | 'already_executed';
  result: Record<string, unknown>;
}

// ── Verification ────────────────────────────────────────────────────────────

export interface Verdict {
  verified: boolean;
  errors: string[];
}

// ── Mesh health ─────────────────────────────────────────────────────────────

export interface ModuleHealth {
  name: string;
  namespace: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  last_receipt: string | null;
  signing_key_id: string;
  replicas: { desired: number; ready: number };
}

export interface MeshHealthReport {
  generated_at: string;
  modules: ModuleHealth[];
}

// ── Console surfaces ──────────────────────────────────────────────────────────

export interface DoctrineViolation {
  term: string;
  line: number;
  column: number;
}

export interface DoctrineSweep {
  doctrine_version: string;
  clean: boolean;
  violations: DoctrineViolation[];
}

export interface Formula {
  id: string;
  gate: string;
  status: 'active' | 'advisory' | 'disabled';
  lean_ref?: string;
}

export interface LiveFormulas {
  generated_at: string;
  formulas: Formula[];
}

export interface About {
  name: string;
  version: string;
  surfaces: string[];
  doctrine_version: string;
  repository?: string;
}

// ── Ask ───────────────────────────────────────────────────────────────────────

export interface Citation {
  source: string;
  url: string;
  snippet?: string;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  conversation_id: string;
  receipt_id: string;
}

// ── Auth claims ─────────────────────────────────────────────────────────────

export interface RosieClaims {
  sub: string;
  aud: string | string[];
  groups: string[];
  /** ISO-8601 or epoch seconds; required (<5min old) for /v1/execute/confirm. */
  step_up_completed_at?: string | number;
  [k: string]: unknown;
}
