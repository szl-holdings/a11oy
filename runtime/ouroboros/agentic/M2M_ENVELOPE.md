# Machine-to-Machine Envelope — Anti-Hallucination Contract

**Operator:** Lutar, Stephen P. — ORCID 0009-0001-0110-4173 — SZL Holdings
**Doctrine:** V6
**License:** Apache-2.0

Every message between Cursor ↔ MCP server ↔ a11oy-core ↔ Claude Code ↔ Replit Agent rides this envelope. No envelope = the call is rejected before it reaches the formulas. This is the structural reason this stack cannot hallucinate within its own loop.

## Why this exists

Hallucination has three failure modes:
1. **Fabricated facts** — model invents a number, URL, or claim
2. **Identity drift** — model speaks for another model or for the operator without authority
3. **Replay drift** — a result can't be reproduced; the same input produces different bytes

The envelope eliminates all three at the protocol layer.

## Envelope schema

```typescript
interface Envelope<T> {
  // ────────── identity ──────────
  replayRoot: ReplaySha;        // always "1ed4d2..." — stamped by a11oy-core
  agent: "cursor" | "claude" | "replit" | "a11oy" | "mcp"; // who's speaking
  agentVersion: string;         // semver, monotonic
  nonce: string;                // 128-bit, unique per call
  ts: string;                   // ISO 8601 UTC, ms precision

  // ────────── doctrine ──────────
  doctrine: {
    lambda?: number;            // if provided, must be ≥ 0.90
    axes?: Partial<Axes>;       // partial 9-axis scores
    forbiddenScanned: true;     // sender attests it ran the forbidden-pattern scan
    licenseAllowlistOk: true;   // sender attests license check passed
  };

  // ────────── claim provenance ──────────
  claims: Array<{
    text: string;
    evidence: Array<
      | { kind: "url";        url: string }
      | { kind: "file";       path: string; sha256: string }
      | { kind: "formula";    name: string; inputs: unknown; output: unknown }
      | { kind: "test";       command: string; exitCode: number; stdoutSha256: string }
      | { kind: "i_dont_know" }   // ← first-class "I don't know"
    >;
  }>;

  // ────────── action ──────────
  action?: {
    name: string;               // e.g. "open_draft_pr", "run_test"
    blocked?: boolean;          // true iff doctrine gate rejected
    reasons?: string[];
  };

  // ────────── payload ──────────
  payload: T;

  // ────────── integrity ──────────
  hmac?: string;                // optional HMAC-SHA256 over canonical JSON
}
```

## Hard rejection rules (the receiver MUST reject if)

| # | Condition | Why |
|---|---|---|
| R1 | `replayRoot` missing or doesn't match the canonical SHA | Identity / replay drift |
| R2 | Any `claim` has zero entries in `evidence` | Hallucination prevention |
| R3 | A claim's only evidence is `{kind:"url"}` and the URL is on a known LLM-output domain | No self-citation loops |
| R4 | `agent` field is one of the forbidden values (operator, perplexity, etc.) | Identity safety |
| R5 | `doctrine.forbiddenScanned !== true` | Doctrine compliance |
| R6 | Any string field contains a forbidden pattern (unless `Claude Mythos Preview` literal) | Doctrine V6 |
| R7 | `doctrine.lambda < 0.90` | Λ gate |
| R8 | `doctrine.axes.moralGrounding < 0.95` or `measurabilityHonesty < 0.95` | Hard floors |
| R9 | `nonce` already seen in this session | Replay attack |
| R10 | `ts` more than 60s ahead of receiver clock, or more than 10 minutes behind | Replay window |

If `hmac` is present, it MUST verify against the shared session key. If the key isn't established, that's acceptable for in-process calls but required across process boundaries.

## "I don't know" is a first-class citizen

A response of:

```json
{
  "claims": [{
    "text": "I cannot determine X.",
    "evidence": [{"kind": "i_dont_know"}]
  }]
}
```

is **valid and preferred** over a fabricated answer. The doctrine prefers honest non-answers to plausible fabrications. Every agent config (`.cursorrules`, `CLAUDE.md`, `replit-agent.md`) makes this explicit.

## Example — a clean tool call

```json
{
  "replayRoot": "1ed4d253e876f428c6e182f8ed8a569585442556b339529bbf8ec2522581698b",
  "agent": "claude",
  "agentVersion": "1.0.0",
  "nonce": "01HV9M5K7Q1XJ8B2N3P4D5R6S7",
  "ts": "2026-05-16T11:58:30.123Z",
  "doctrine": {
    "lambda": 0.94,
    "axes": {"moralGrounding": 0.97, "measurabilityHonesty": 0.96},
    "forbiddenScanned": true,
    "licenseAllowlistOk": true
  },
  "claims": [
    {
      "text": "Bekenstein bound for r=1m, E=1J is approximately 8.65e34 bits.",
      "evidence": [
        {"kind": "formula", "name": "bekensteinBound", "inputs": {"radius_m": 1, "energy_j": 1}, "output": 8.65e34}
      ]
    }
  ],
  "action": {"name": "respond"},
  "payload": {"answer": "8.65e34 bits"}
}
```

## Example — a refused fabrication

If a model tries:

```json
{
  "claims": [{
    "text": "The Riemann hypothesis was proven in 2024.",
    "evidence": []
  }]
}
```

Receiver rejects via R2. Sender must either:
1. Provide evidence (URL, formula, test, file), OR
2. Restate the claim with `evidence: [{"kind": "i_dont_know"}]`

## Implementation — TypeScript validator

```typescript
// 12_agentic/a11oy-core/src/envelope.ts (separate file in payload)
export function validateEnvelope<T>(e: Envelope<T>): { ok: boolean; rejections: string[] }
```

(See `a11oy-core/src/envelope.ts` for the canonical implementation.)

## What this buys you

- **Replit Agent** can't drift away from a11oy's doctrine — every message it sends back is checked
- **Cursor** can't paste a fabricated "let me just write this for you" — without evidence, the call fails
- **Claude Code** speaks honestly via `i_dont_know` when it doesn't know — and the operator sees the gap
- **Cross-agent** loops are nonce-protected and replay-stamped
- **Audit trail** — every accepted envelope is logged to `cto_acceptance_log.jsonl`, every rejection is logged to `cto_rejection_log.jsonl`

That's the "no hallucinations, no liability" structural layer.
