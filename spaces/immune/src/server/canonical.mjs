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
    const out = Object.create(null);
    for (const key of Object.keys(value).sort()) {
      if (["__proto__", "prototype", "constructor"].includes(key)) throw new RequestFault("PROTOTYPE_KEY_REJECTED", `prototype-sensitive key is not accepted: ${key}`);
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

function rejectUnknown(value, allowed, label) {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new RequestFault("UNKNOWN_FIELD", `unsupported ${label} field: ${key}`);
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
  rejectUnknown(body, new Set(["content", "source", "actor", ...(toolRequired ? ["tool"] : [])]), "request");
  const text = normalizeText(body.content);
  assertObject(body.source, "source");
  rejectUnknown(body.source, new Set(["kind", "trust"]), "source");
  const kinds = new Set(["user", "tool_response", "retrieval", "memory", "system"]);
  const trusts = new Set(["trusted", "untrusted", "unknown"]);
  if (!kinds.has(body.source.kind)) throw new RequestFault("INVALID_SOURCE", "source.kind is invalid");
  if (!trusts.has(body.source.trust)) throw new RequestFault("INVALID_SOURCE", "source.trust is invalid");

  const actor = body.actor ?? {};
  assertObject(actor, "actor");
  rejectUnknown(actor, new Set(["id", "role", "scopes"]), "actor");
  if (actor.id !== undefined && (typeof actor.id !== "string" || actor.id.length > 256)) throw new RequestFault("INVALID_ACTOR", "actor.id must be a string of at most 256 characters");
  if (actor.role !== undefined && (typeof actor.role !== "string" || actor.role.length > 128)) throw new RequestFault("INVALID_ACTOR", "actor.role must be a string of at most 128 characters");
  const scopes = actor.scopes ?? [];
  if (!Array.isArray(scopes) || scopes.length > 64 || scopes.some((scope) => typeof scope !== "string" || scope.length > 128)) {
    throw new RequestFault("INVALID_ACTOR", "actor.scopes must contain at most 64 short strings");
  }

  let tool = null;
  if (toolRequired) {
    assertObject(body.tool, "tool");
    rejectUnknown(body.tool, new Set(["name", "capability", "arguments"]), "tool");
    if (typeof body.tool.name !== "string" || !body.tool.name.trim() || body.tool.name.length > 256) throw new RequestFault("INVALID_TOOL", "tool.name must be 1-256 characters");
    if (typeof body.tool.capability !== "string" || !body.tool.capability.trim() || body.tool.capability.length > 256) throw new RequestFault("INVALID_TOOL", "tool.capability must be 1-256 characters");
    if (!Object.hasOwn(body.tool, "arguments")) throw new RequestFault("INVALID_TOOL", "tool.arguments is required");
    tool = {
      name: body.tool.name,
      capability: body.tool.capability,
      arguments: stable(body.tool.arguments),
    };
  }

  return {
    content: text.value,
    normalization: { changed: text.changed, appliedNfkc: text.appliedNfkc, removedZeroWidth: text.removedZeroWidth },
    source: { kind: body.source.kind, trust: body.source.trust },
    actor: {
      id: typeof actor.id === "string" ? actor.id : null,
      role: typeof actor.role === "string" ? actor.role : null,
      scopes: [...new Set(scopes)].sort(),
    },
    tool,
  };
}
