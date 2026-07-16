import { createHash } from "node:crypto";

export const LIMITS = Object.freeze({
  maxBodyBytes: 1_048_576,
  maxFieldBytes: 65_536,
  maxDepth: 32,
});

const ZERO_WIDTH = /[\u200B-\u200D\u2060\uFEFF]/gu;
const SESSION_ID = /^[A-Za-z0-9_-]{16,128}$/u;

export class RequestFault extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = "RequestFault";
    this.code = code;
    this.status = status;
  }
}

export function normalizeText(value) {
  if (typeof value !== "string") throw new RequestFault("INVALID_TEXT", "content must be a string");
  if (Buffer.byteLength(value, "utf8") > LIMITS.maxFieldBytes) {
    throw new RequestFault("FIELD_TOO_LARGE", `content exceeds ${LIMITS.maxFieldBytes} UTF-8 bytes`, 413);
  }
  const nfkc = value.normalize("NFKC");
  const normalized = nfkc.replace(ZERO_WIDTH, "");
  return {
    value: normalized,
    changed: normalized !== value,
    removedZeroWidth: nfkc !== normalized,
    appliedNfkc: nfkc !== value,
  };
}

function stable(value, depth = 0) {
  if (depth > LIMITS.maxDepth) throw new RequestFault("MAX_DEPTH_EXCEEDED", `request exceeds depth ${LIMITS.maxDepth}`);
  if (value === null || typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new RequestFault("NON_CANONICAL_NUMBER", "only safe integers are accepted");
    return value;
  }
  if (Array.isArray(value)) return value.map((item) => stable(item, depth + 1));
  if (typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) {
      if (value[key] === undefined) throw new RequestFault("NON_CANONICAL_VALUE", "undefined values are not accepted");
      out[key] = stable(value[key], depth + 1);
    }
    return out;
  }
  throw new RequestFault("NON_CANONICAL_VALUE", `unsupported value type: ${typeof value}`);
}

export function canonicalJson(value) {
  return JSON.stringify(stable(value));
}

export function sha256(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(String(value), "utf8");
  return createHash("sha256").update(bytes).digest("hex");
}

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new RequestFault("INVALID_REQUEST", `${label} must be an object`);
  }
}

export function validateSessionId(value) {
  if (typeof value !== "string" || !SESSION_ID.test(value)) {
    throw new RequestFault("INVALID_SESSION", "x-immune-session must be 16-128 URL-safe characters");
  }
  return value;
}

export function validateInspectRequest(body, { toolRequired = false } = {}) {
  assertObject(body, "request");
  const allowed = new Set(["sessionId", "content", "source", "actor", ...(toolRequired ? ["tool"] : [])]);
  for (const key of Object.keys(body)) {
    if (!allowed.has(key)) throw new RequestFault("UNKNOWN_FIELD", `unsupported request field: ${key}`);
  }
  const text = normalizeText(body.content);
  assertObject(body.source, "source");
  const kinds = new Set(["user", "tool_response", "retrieval", "memory", "system"]);
  const trusts = new Set(["trusted", "untrusted", "unknown"]);
  if (!kinds.has(body.source.kind)) throw new RequestFault("INVALID_SOURCE", "source.kind is invalid");
  if (!trusts.has(body.source.trust)) throw new RequestFault("INVALID_SOURCE", "source.trust is invalid");

  const actor = body.actor ?? {};
  assertObject(actor, "actor");
  const scopes = actor.scopes ?? [];
  if (!Array.isArray(scopes) || scopes.length > 64 || scopes.some((scope) => typeof scope !== "string" || scope.length > 128)) {
    throw new RequestFault("INVALID_ACTOR", "actor.scopes must contain at most 64 short strings");
  }

  let tool = null;
  if (toolRequired) {
    assertObject(body.tool, "tool");
    if (typeof body.tool.name !== "string" || !body.tool.name.trim()) throw new RequestFault("INVALID_TOOL", "tool.name is required");
    if (typeof body.tool.capability !== "string" || !body.tool.capability.trim()) throw new RequestFault("INVALID_TOOL", "tool.capability is required");
    tool = {
      name: body.tool.name.slice(0, 256),
      capability: body.tool.capability.slice(0, 256),
      arguments: stable(body.tool.arguments),
    };
  }

  return {
    content: text.value,
    normalization: { changed: text.changed, appliedNfkc: text.appliedNfkc, removedZeroWidth: text.removedZeroWidth },
    source: { kind: body.source.kind, trust: body.source.trust },
    actor: {
      id: typeof actor.id === "string" ? actor.id.slice(0, 256) : null,
      role: typeof actor.role === "string" ? actor.role.slice(0, 128) : null,
      scopes: [...new Set(scopes)].sort(),
    },
    tool,
  };
}
