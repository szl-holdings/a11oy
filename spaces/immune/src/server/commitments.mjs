import { createHash, createHmac } from "node:crypto";

function key() {
  try {
    const encoded = process.env.IMMUNE_COMMITMENT_KEY?.trim();
    if (!encoded) return null;
    const bytes = Buffer.from(encoded, "base64");
    return bytes.length >= 32 ? bytes : null;
  } catch { return null; }
}

export function commitmentStatus() {
  const keyed = Boolean(key());
  const readbackEnabled = process.env.IMMUNE_RECEIPT_READBACK === "1";
  return {
    state: keyed ? "READY" : "DEGRADED",
    scheme: keyed ? "HMAC-SHA-256" : "SHA-256",
    disclosure: keyed ? "KEYED_COMMITMENT" : "DICTIONARY_EXPOSURE_RISK",
    publicReceiptReadback: keyed && readbackEnabled ? "READY_SESSION_SCOPED" : "UNAVAILABLE",
    reason: keyed ? (readbackEnabled ? null : "receipt_readback_disabled") : "commitment_key_unavailable",
  };
}

export function commitValue(value, purpose) {
  const secret = key();
  const domain = Buffer.from(`szl.immune.commitment/v1\0${purpose}\0`, "utf8");
  const body = Buffer.from(String(value), "utf8");
  if (secret) {
    return { scheme: "HMAC-SHA-256", value: createHmac("sha256", secret).update(domain).update(body).digest("hex"), disclosure: "KEYED_COMMITMENT" };
  }
  return { scheme: "SHA-256", value: createHash("sha256").update(domain).update(body).digest("hex"), disclosure: "DICTIONARY_EXPOSURE_RISK" };
}
