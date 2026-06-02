// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
// Author: Yachay <yachay@szlholdings.dev>
// Co-Authored-By: Perplexity Computer Agent
// Change-class: ADDITIVE — Doctrine v11 LOCKED 749/14/163 UNCHANGED.
//
// Schema-strict tool registry for the Cross-Harness Receipt Bridge
// (Hermes + OpenClaw). Canonical TypeScript mirror of the runtime Python
// module `szl_bridge_schemas.py` that the live HF Space serves.
//
// Every tool call that crosses the bridge — whether it arrives as a Hermes
// `<tool_call>{"name":...,"arguments":{...}}</tool_call>` ChatML envelope or an
// OpenClaw tool event — MUST validate against a registered JSON Schema 2020-12
// schema here. A call whose `name` is unknown, or whose `arguments` fail schema
// validation, fails-CLOSED: the bridge mints a `kind:"schema_mismatch"` Khipu
// receipt and rejects the request (Sentra deny-by-default).
//
// Each schema:
//   * is JSON Schema 2020-12 (`$schema` declared),
//   * sets `additionalProperties: false` (no smuggled fields),
//   * declares its `required` arguments.

export const JSON_SCHEMA_DIALECT =
  "https://json-schema.org/draft/2020-12/schema" as const;

export interface ToolSchema {
  readonly $schema: string;
  readonly title: string;
  readonly description: string;
  readonly type: "object";
  readonly additionalProperties: false;
  readonly required: readonly string[];
  readonly properties: Record<string, Record<string, unknown>>;
}

function schema(
  properties: Record<string, Record<string, unknown>>,
  required: readonly string[],
  title: string,
  description: string,
): ToolSchema {
  return {
    $schema: JSON_SCHEMA_DIALECT,
    title,
    description,
    type: "object",
    additionalProperties: false,
    required,
    properties,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Registered tool schemas. At least 6 (search, fetch, write_file, exec,
// sign_receipt, predict). Each is JSON Schema 2020-12, additionalProperties:false.
// ─────────────────────────────────────────────────────────────────────────────

export const TOOL_SCHEMAS: Record<string, ToolSchema> = {
  search: schema(
    {
      q: { type: "string", minLength: 1, description: "Search query." },
      top_k: { type: "integer", minimum: 1, maximum: 100 },
      recency: { type: "string", enum: ["day", "week", "month", "year", "any"] },
    },
    ["q"],
    "search",
    "Full-text / web search. Returns ranked results for a query string.",
  ),
  fetch: schema(
    {
      url: { type: "string", minLength: 1, description: "http(s) URL to fetch." },
      max_bytes: { type: "integer", minimum: 1, maximum: 10_000_000 },
      method: { type: "string", enum: ["GET", "HEAD"] },
    },
    ["url"],
    "fetch",
    "Fetch the contents of a URL (read-only).",
  ),
  write_file: schema(
    {
      path: { type: "string", minLength: 1, description: "Destination path." },
      content: { type: "string", description: "UTF-8 file contents." },
      mode: { type: "string", enum: ["create", "overwrite", "append"] },
    },
    ["path", "content"],
    "write_file",
    "Write content to a file. State-changing — gated by Sentra.",
  ),
  exec: schema(
    {
      cmd: { type: "string", minLength: 1, description: "Command to execute." },
      args: { type: "array", items: { type: "string" } },
      timeout_s: { type: "integer", minimum: 1, maximum: 3600 },
    },
    ["cmd"],
    "exec",
    "Execute a sandboxed command. High severity — Sentra deny-by-default.",
  ),
  sign_receipt: schema(
    {
      actor_id: { type: "string", minLength: 1 },
      tool_name: { type: "string", minLength: 1 },
      payload: { type: "object" },
      kind: {
        type: "string",
        enum: [
          "action",
          "deliberation",
          "channel_ingress",
          "exec_audit",
          "schema_mismatch",
        ],
      },
    },
    ["actor_id", "tool_name", "payload"],
    "sign_receipt",
    "Mint a DSSE-signed Khipu receipt over an arbitrary payload.",
  ),
  predict: schema(
    {
      action: { type: "string", minLength: 1, description: "Action to forecast." },
      horizon: { type: "integer", minimum: 1, maximum: 1000 },
      confidence: { type: "number", minimum: 0.0, maximum: 1.0 },
    },
    ["action"],
    "predict",
    "PAC-Bayes pre-action forward-model prediction (predicted-vs-actual).",
  ),
};

export function registeredTools(): string[] {
  return Object.keys(TOOL_SCHEMAS).sort();
}

export function getSchema(name: string): ToolSchema | undefined {
  return TOOL_SCHEMAS[name];
}

export interface ValidationResult {
  readonly valid: boolean;
  readonly errors: string[];
  readonly schemaTitle: string | null;
  readonly dialect: string;
}

const PY_TYPE_CHECK: Record<string, (v: unknown) => boolean> = {
  object: (v) => typeof v === "object" && v !== null && !Array.isArray(v),
  array: (v) => Array.isArray(v),
  string: (v) => typeof v === "string",
  integer: (v) => typeof v === "number" && Number.isInteger(v),
  number: (v) => typeof v === "number" && Number.isFinite(v),
  boolean: (v) => typeof v === "boolean",
  null: (v) => v === null,
};

function typeOk(value: unknown, t: string): boolean {
  const check = PY_TYPE_CHECK[t];
  return check ? check(value) : true;
}

function validate(
  value: unknown,
  s: Record<string, unknown>,
  path: string,
  errors: string[],
): void {
  const t = s.type as string | undefined;
  if (t !== undefined && !typeOk(value, t)) {
    errors.push(`${path || "<root>"}: expected type ${t}, got ${typeof value}`);
    return;
  }

  if ("enum" in s && Array.isArray(s.enum) && !s.enum.includes(value as never)) {
    errors.push(`${path || "<root>"}: ${JSON.stringify(value)} not in enum ${JSON.stringify(s.enum)}`);
  }

  if (t === "string" && typeof value === "string") {
    if ("minLength" in s && value.length < (s.minLength as number)) {
      errors.push(`${path}: string shorter than minLength ${s.minLength}`);
    }
  }

  if ((t === "number" || t === "integer") && typeof value === "number") {
    if ("minimum" in s && value < (s.minimum as number)) {
      errors.push(`${path}: ${value} < minimum ${s.minimum}`);
    }
    if ("maximum" in s && value > (s.maximum as number)) {
      errors.push(`${path}: ${value} > maximum ${s.maximum}`);
    }
  }

  if (t === "array" && Array.isArray(value)) {
    const itemSchema = s.items as Record<string, unknown> | undefined;
    if (itemSchema && typeof itemSchema === "object") {
      value.forEach((item, i) => validate(item, itemSchema, `${path}[${i}]`, errors));
    }
  }

  if (t === "object" && typeof value === "object" && value !== null && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    const props = (s.properties as Record<string, Record<string, unknown>>) ?? {};
    const required = (s.required as string[]) ?? [];
    for (const req of required) {
      if (!(req in obj)) {
        errors.push(`${path || "<root>"}: missing required property '${req}'`);
      }
    }
    if (s.additionalProperties === false) {
      const extra = Object.keys(obj).filter((k) => !(k in props));
      if (extra.length > 0) {
        errors.push(`${path || "<root>"}: additional properties not allowed: ${JSON.stringify(extra.sort())}`);
      }
    }
    for (const [k, v] of Object.entries(obj)) {
      if (k in props) {
        validate(v, props[k], path ? `${path}.${k}` : k, errors);
      }
    }
  }
}

/**
 * Validate `args` against the registered schema for tool `name`.
 * Fails-CLOSED: an unknown tool name is invalid (deny-by-default).
 */
export function validateToolCall(name: string, args: unknown): ValidationResult {
  const s = TOOL_SCHEMAS[name];
  if (s === undefined) {
    return {
      valid: false,
      errors: [`unknown tool '${name}'; registered tools = ${JSON.stringify(registeredTools())}`],
      schemaTitle: null,
      dialect: JSON_SCHEMA_DIALECT,
    };
  }
  if (typeof args !== "object" || args === null || Array.isArray(args)) {
    return {
      valid: false,
      errors: [`arguments must be an object, got ${Array.isArray(args) ? "array" : typeof args}`],
      schemaTitle: s.title,
      dialect: JSON_SCHEMA_DIALECT,
    };
  }
  const errors: string[] = [];
  validate(args, s as unknown as Record<string, unknown>, "", errors);
  return {
    valid: errors.length === 0,
    errors,
    schemaTitle: s.title,
    dialect: JSON_SCHEMA_DIALECT,
  };
}
