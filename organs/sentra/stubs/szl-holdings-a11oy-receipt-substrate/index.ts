// Local workspace type shim for @szl-holdings/a11oy-receipt-substrate.
//
// Type-only mirror of the real package's public envelope shape so the web
// app and the a11oy orchestration stub type-check offline without resolving
// the @szl-holdings registry package. Shapes mirror a11oy main
// packages/receipt-substrate/src/index.ts (szl-holdings/a11oy @ e1a48fe).
// Type-only imports are erased at build time; nothing here enters the bundle.

export type ReceiptProtocol = 'mcp' | 'cursor' | 'claude' | 'a11oy';

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
