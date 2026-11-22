/**
 * vc_data_integrity.ts - W3C Data Integrity "ecdsa-jcs-2019" proofs (create + verify).
 *
 * Why: wrap_dsse.ts labels its dev-path proof "ecdsa-rdfc-2022". That name is not
 * in the W3C Recommendation (Data Integrity ECDSA Cryptosuites v1.0, 2025-05-15
 * registers ecdsa-rdfc-2019, ecdsa-jcs-2019 and ecdsa-sd-2023), and the proof it
 * produces does not follow the suite it names:
 *   - signs only the JCS bytes of the document: created, verificationMethod and
 *     proofPurpose are NOT covered, so they can be rewritten without breaking the
 *     signature;
 *   - proofValue is "z" + base64url(DER signature); the spec requires a multibase
 *     base58-btc value of the 64-byte IEEE P1363 (r || s) signature;
 *   - no verifier exists.
 * This module implements the registered ecdsa-jcs-2019 suite, which is the
 * suite meant for JSON documents canonicalised with RFC 8785, so wrap_dsse.ts
 * can adopt it without a JSON-LD (RDFC) dependency.
 *
 * Spec: https://www.w3.org/TR/vc-di-ecdsa/#ecdsa-jcs-2019
 *   proofConfig  = proof options (type, cryptosuite, created, verificationMethod,
 *                  proofPurpose, @context if the document has one), no proofValue
 *   hashData     = SHA-256(JCS(proofConfig)) || SHA-256(JCS(document without proof))
 *   proofBytes   = ECDSA P-256 / SHA-256 over hashData, r || s (64 bytes)
 *   proofValue   = "z" + base58btc(proofBytes)
 *
 * Self-contained (node:crypto only). Callers supply the private key; this module
 * never generates, stores or reads key material.
 */
import { createHash, createPublicKey, sign, verify, type KeyObject } from "node:crypto";

const SUITE = "ecdsa-jcs-2019";
const B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const LONE_SURROGATE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

// --- RFC 8785 (strict; same rules as packages/receipt-substrate/src/jcs.ts) ---------
function jcsString(text: string): string {
  if (LONE_SURROGATE.test(text)) throw new Error("jcs: lone surrogate is not valid I-JSON");
  return JSON.stringify(text);
}

export function jcs(value: unknown): string {
  if (value === null) return "null";
  switch (typeof value) {
    case "string":
      return jcsString(value);
    case "boolean":
      return value ? "true" : "false";
    case "number":
      if (!Number.isFinite(value)) throw new Error("jcs: NaN and Infinity are not permitted");
      return JSON.stringify(value);
    case "object": {
      if (Array.isArray(value)) return `[${value.map(jcs).join(",")}]`;
      const proto = Object.getPrototypeOf(value);
      if (proto !== Object.prototype && proto !== null) throw new Error("jcs: only plain JSON objects are accepted");
      const obj = value as Record<string, unknown>;
      return `{${Object.keys(obj)
        .sort()
        .map((k) => `${jcsString(k)}:${jcs(obj[k])}`)
        .join(",")}}`;
    }
    default:
      throw new Error(`jcs: unsupported ${typeof value} value`);
  }
}

// --- base58btc (Bitcoin alphabet) ---------------------------------------------------
export function base58btcEncode(bytes: Buffer): string {
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros += 1;
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  let out = "";
  while (n > 0n) {
    out = B58[Number(n % 58n)] + out;
    n /= 58n;
  }
  return "1".repeat(zeros) + out;
}

export function base58btcDecode(text: string): Buffer | null {
  if (typeof text !== "string") return null;
  let zeros = 0;
  while (zeros < text.length && text[zeros] === "1") zeros += 1;
  let n = 0n;
  for (const ch of text) {
    const v = B58.indexOf(ch);
    if (v < 0) return null;
    n = n * 58n + BigInt(v);
  }
  let hex = n.toString(16);
  if (hex.length % 2) hex = `0${hex}`;
  const body = n === 0n ? Buffer.alloc(0) : Buffer.from(hex, "hex");
  return Buffer.concat([Buffer.alloc(zeros), body]);
}

// --- Data Integrity proofs ---------------------------------------------------------
export interface DataIntegrityProofOptions {
  readonly verificationMethod: string;
  readonly proofPurpose: string;
  /** XML Schema dateTime, e.g. 2026-11-19T08:00:00Z. */
  readonly created?: string;
}

export interface VerifiedResult {
  readonly valid: boolean;
  readonly errors: readonly string[];
}

const DATETIME = /^-?\d{4,}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

function proofConfigOf(proof: Record<string, unknown>): Record<string, unknown> {
  const { proofValue: _omit, ...config } = proof;
  return config;
}

function hashData(config: Record<string, unknown>, unsecuredDocument: unknown): Buffer {
  const configHash = createHash("sha256").update(jcs(config), "utf8").digest();
  const docHash = createHash("sha256").update(jcs(unsecuredDocument), "utf8").digest();
  return Buffer.concat([configHash, docHash]);
}

function withoutProof(doc: Record<string, unknown>): Record<string, unknown> {
  const { proof: _proof, ...rest } = doc;
  return rest;
}

/** Create a secured document: the input document plus an ecdsa-jcs-2019 `proof`. */
export function createProof<T extends Record<string, unknown>>(
  unsecuredDocument: T,
  options: DataIntegrityProofOptions,
  privateKey: KeyObject,
): T & { proof: Record<string, unknown> } {
  if ("proof" in unsecuredDocument) throw new Error("document already has a proof");
  if (options.created !== undefined && !DATETIME.test(options.created)) throw new Error("created must be an XML Schema dateTime");
  if (!options.verificationMethod || !options.proofPurpose) throw new Error("verificationMethod and proofPurpose are required");
  const proof: Record<string, unknown> = {
    type: "DataIntegrityProof",
    cryptosuite: SUITE,
    ...(options.created !== undefined && { created: options.created }),
    verificationMethod: options.verificationMethod,
    proofPurpose: options.proofPurpose,
    ...("@context" in unsecuredDocument && { "@context": unsecuredDocument["@context"] }),
  };
  const signature = sign("sha256", hashData(proof, unsecuredDocument), { key: privateKey, dsaEncoding: "ieee-p1363" });
  if (signature.length !== 64) throw new Error("key is not a P-256 key");
  return { ...unsecuredDocument, proof: { ...proof, proofValue: `z${base58btcEncode(signature)}` } };
}

export interface VerifyProofOptions {
  /** verificationMethod URL -> trusted P-256 public key. The signed proof selects the entry. */
  readonly keys: Readonly<Record<string, KeyObject | string>>;
  /** If set, the proof's proofPurpose must equal this (for example "assertionMethod"). */
  readonly expectedProofPurpose?: string;
}

/** Verify an ecdsa-jcs-2019 secured document. Never throws; malformed input fails verification. */
export function verifyProof(securedDocument: unknown, options: VerifyProofOptions): VerifiedResult {
  const fail = (...errors: string[]): VerifiedResult => ({ valid: false, errors });
  try {
    if (securedDocument === null || typeof securedDocument !== "object" || Array.isArray(securedDocument)) return fail("document must be an object");
    const doc = securedDocument as Record<string, unknown>;
    const proof = doc.proof;
    if (proof === null || typeof proof !== "object" || Array.isArray(proof)) return fail("exactly one proof object is required");
    const p = proof as Record<string, unknown>;
    if (p.type !== "DataIntegrityProof") return fail("proof.type must be DataIntegrityProof");
    if (p.cryptosuite !== SUITE) return fail(`proof.cryptosuite must be ${SUITE}`);
    if (typeof p.proofValue !== "string" || !p.proofValue.startsWith("z")) return fail("proofValue must be a base58-btc multibase string");
    if (typeof p.verificationMethod !== "string" || !Object.prototype.hasOwnProperty.call(options.keys, p.verificationMethod)) {
      return fail("verificationMethod is not a trusted key");
    }
    if (typeof p.proofPurpose !== "string") return fail("proofPurpose is required");
    if (options.expectedProofPurpose !== undefined && p.proofPurpose !== options.expectedProofPurpose) return fail("unexpected proofPurpose");
    if (p.created !== undefined && (typeof p.created !== "string" || !DATETIME.test(p.created))) return fail("created is not a valid dateTime");
    if ("@context" in doc ? jcs(p["@context"]) !== jcs(doc["@context"]) : "@context" in p) return fail("proof @context must equal the document @context");
    const signature = base58btcDecode(p.proofValue.slice(1));
    if (!signature || signature.length !== 64) return fail("proofValue must decode to a 64-byte P-256 signature");
    const trusted = options.keys[p.verificationMethod];
    const key = typeof trusted === "string" ? createPublicKey(trusted) : trusted;
    const ok = verify("sha256", hashData(proofConfigOf(p), withoutProof(doc)), { key, dsaEncoding: "ieee-p1363" }, signature);
    return ok ? { valid: true, errors: [] } : fail("signature does not verify");
  } catch (error) {
    return fail(error instanceof Error ? error.message : String(error));
  }
}
