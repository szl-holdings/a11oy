// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// Doctrine v7
/**
 * a11oy-receipt-substrate.d.ts — vendored ambient type surface for
 * `@szl-holdings/a11oy-receipt-substrate`.
 *
 * Chicken-and-egg note: the widget consumes the substrate's *types*, but the
 * substrate is published separately (by the a11oy wiring PR). To let the
 * widget build and type-check before that package is on the registry, this
 * file mirrors the **type-only** surface the widget uses. It is aliased in via
 * tsconfig `paths`. Because every widget import of the substrate is
 * `import type { … }`, these declarations are erased at build time and the
 * widget bundle never depends on the substrate at runtime.
 *
 * This declaration is a faithful copy of the public types in
 * `a11oy/packages/receipt-substrate/src/index.ts` (kept in sync by hand; the
 * shape is small and stable, schema_version "1.0.0"). When the real package is
 * installed it shadows this shim with no code change required.
 */

declare module '@szl-holdings/a11oy-receipt-substrate' {
  export type HashAlgorithm = 'SHA-256' | 'SHA3-256' | 'SHA3-512';
  export type ReceiptProtocol = 'mcp' | 'cursor' | 'claude' | 'a11oy';
  export type ReceiptEventType =
    | 'MCP_TOOL_CALL'
    | 'CURSOR_AGENT_EDIT'
    | 'CLAUDE_SUBAGENT_CALL'
    | 'A11OY_OPERATION';

  export interface ToolEnvelope {
    readonly protocol: ReceiptProtocol;
    readonly actor_id: string;
    readonly tool_name: string;
    readonly tool_version?: string;
    readonly invocation_id: string;
    readonly lambda_axes: readonly string[];
    readonly payload: unknown;
    readonly metadata?: Record<string, unknown>;
  }

  export interface ReceiptPolicy {
    readonly algorithm: HashAlgorithm;
    readonly chaining: 'hash_chain' | 'merkle_dag';
    readonly quorum: string;
    readonly nodes: readonly string[];
    readonly vertical?: string;
    readonly regime?: string;
  }

  export interface QecWitness {
    readonly payload_byte: number;
    readonly shor_repetition_count: 9;
    readonly shor_majority_payload: number;
    readonly css_x_parity: number;
    readonly css_z_parity: number;
    readonly css_consistent: boolean;
  }

  export interface OperationalReceipt {
    readonly schema_version: '1.0.0';
    readonly receipt_id: string;
    readonly event_type: ReceiptEventType;
    readonly timestamp_iso8601: string;
    readonly timestamp_tai64n: string;
    readonly sequence: number;
    readonly actor_id: string;
    readonly tool_name: string;
    readonly protocol: ReceiptProtocol;
    readonly payload_hash: string;
    readonly prev_receipt_hash: string | null;
    readonly quorum_signatures: readonly string[];
    readonly policy?: Pick<
      ReceiptPolicy,
      'algorithm' | 'chaining' | 'quorum' | 'nodes' | 'vertical' | 'regime'
    >;
    readonly qec_witness: QecWitness;
    readonly envelope: ToolEnvelope;
    readonly merkle_root: string;
  }

  export interface VerifyResult {
    readonly valid: boolean;
    readonly errors: readonly string[];
  }
}
