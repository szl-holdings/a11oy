import { createHmac, timingSafeEqual } from "node:crypto";
import { canonicalJson, sha256 } from "./canonical.mjs";

const consumed = new Map();

function key() {
  try {
    const bytes = Buffer.from(process.env.IMMUNE_AUTHORITY_KEY?.trim() ?? "", "base64");
    return bytes.length >= 32 ? bytes : null;
  } catch { return null; }
}

export function authorityStatus() {
  return key() ? { state: "READY", mode: "HMAC_BOUND_ONE_TIME_ASSERTION" } : { state: "UNAVAILABLE", mode: "HMAC_BOUND_ONE_TIME_ASSERTION", reason: "IMMUNE_AUTHORITY_KEY is absent or invalid" };
}

function clean(now) {
  for (const [jti, expiresAt] of consumed) if (expiresAt <= now) consumed.delete(jti);
}

function validActor(actor) {
  return actor && typeof actor === "object" && !Array.isArray(actor) && typeof actor.id === "string" && actor.id.length > 0 && actor.id.length <= 256 &&
    (actor.role === null || actor.role === undefined || (typeof actor.role === "string" && actor.role.length <= 128)) &&
    Array.isArray(actor.scopes) && actor.scopes.length <= 64 && actor.scopes.every((scope) => typeof scope === "string" && scope.length <= 128);
}

function validSource(source) {
  return source && ["user", "tool_response", "retrieval", "memory", "system"].includes(source.kind) && ["trusted", "untrusted", "unknown"].includes(source.trust);
}

export function verifyAuthority(request, normalizedRequest, { consume = true, now = Date.now() } = {}) {
  const secret = key();
  if (!secret) return { state: "UNAVAILABLE", reason: "authority_key_unavailable" };
  try {
    const encoded = String(request.headers["x-immune-authority"] ?? "");
    const supplied = String(request.headers["x-immune-authority-signature"] ?? "").toLowerCase();
    if (!encoded || !/^[a-f0-9]{64}$/u.test(supplied)) return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_assertion_missing" };
    const expected = createHmac("sha256", secret).update("szl.immune.authority/v1\0").update(encoded).digest("hex");
    if (!timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(supplied, "hex"))) return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_signature_invalid" };
    const assertion = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    const validWindow = Number.isSafeInteger(assertion.issuedAtMs) && Number.isSafeInteger(assertion.expiresAtMs) && assertion.issuedAtMs <= now + 30_000 && assertion.expiresAtMs > now && assertion.expiresAtMs - assertion.issuedAtMs <= 300_000;
    if (assertion.schemaVersion !== "szl.immune.authority/v1" || !/^[A-Za-z0-9_-]{16,128}$/u.test(assertion.jti ?? "") || !validWindow || !validActor(assertion.actor) || !validSource(assertion.source)) return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_payload_invalid" };
    if (assertion.requestSha256 !== sha256(canonicalJson(normalizedRequest))) return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_request_binding_mismatch" };
    clean(now);
    if (consumed.has(assertion.jti)) return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_assertion_replayed" };
    if (consume) consumed.set(assertion.jti, assertion.expiresAtMs);
    return { state: "VERIFIED", actor: assertion.actor, source: assertion.source, jti: assertion.jti, expiresAtMs: assertion.expiresAtMs };
  } catch { return { state: "UNVERIFIED_CALLER_ASSERTION", reason: "authority_assertion_unverifiable" }; }
}

export function resetAuthorityForTest() { consumed.clear(); }
