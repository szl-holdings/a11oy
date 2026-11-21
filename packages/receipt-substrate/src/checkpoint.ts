// Signed tree heads for the receipt Merkle log, in the interoperable C2SP formats:
//   - signed note   https://c2sp.org/signed-note        (Ed25519, signature type 0x01)
//   - checkpoint    https://c2sp.org/tlog-checkpoint     (origin / size / base64 root)
// These are the formats Sigstore's Rekor v2, the Go checksum database and the
// transparency-dev witness network use, so a verifier written for them can read
// an a11oy receipt-log head.
//
// Why: the current receipts carry no cryptographic signature (quorum_signatures
// are node-name strings). Anyone who can write the JSONL can rewrite the whole
// chain and recompute every hash. A signed checkpoint binds (origin, size, root)
// to a key that the verifier configured out of band.
//
// This module only VERIFIES with caller-supplied public keys and formats text.
// signNote() takes a caller-supplied private KeyObject; the module never creates,
// stores or reads key material.
import * as crypto from "node:crypto";
import { verifyConsistency, type Hash } from "./merkle_log.ts";

const ED25519_TYPE = 0x01;
const EM_DASH_PREFIX = "\u2014 ";

export interface VerifierKey {
  readonly name: string;
  readonly keyId: number; // uint32
  readonly publicKey: Buffer; // raw 32-byte Ed25519 key
}

export interface NoteVerification {
  readonly valid: boolean;
  readonly errors: readonly string[];
  readonly text?: string;
  readonly verifiedKeyNames: readonly string[];
}

function strictBase64Decode(text: string): Buffer | null {
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(text) || text.length % 4 !== 0) return null;
  const decoded = Buffer.from(text, "base64");
  // canonical encoding only (RFC 4648 3.5): re-encoding must give the same text
  return decoded.toString("base64") === text ? decoded : null;
}

function validKeyName(name: string): boolean {
  return name.length > 0 && !/[\s+]/u.test(name);
}

/** key ID = SHA-256(key name || 0x0A || 0x01 || 32-byte Ed25519 public key)[:4], big-endian uint32. */
export function ed25519KeyId(name: string, publicKey: Buffer): number {
  const digest = crypto
    .createHash("sha256")
    .update(Buffer.concat([Buffer.from(name, "utf8"), Buffer.from([0x0a, ED25519_TYPE]), publicKey]))
    .digest();
  return digest.readUInt32BE(0);
}

/** Parse "name+hex(keyid)+base64(0x01||pubkey)" and check the key ID matches. */
export function parseVerifierKey(vkey: string): VerifierKey {
  const parts = vkey.split("+");
  if (parts.length !== 3) throw new Error("vkey: expected name+keyid+key");
  const [name, idHex, keyB64] = parts;
  if (!validKeyName(name)) throw new Error("vkey: invalid key name");
  if (!/^[0-9a-f]{8}$/.test(idHex)) throw new Error("vkey: key id must be 8 lowercase hex digits");
  const material = strictBase64Decode(keyB64);
  if (!material || material.length !== 33 || material[0] !== ED25519_TYPE) {
    throw new Error("vkey: only Ed25519 (type 0x01, 32-byte key) is supported");
  }
  const publicKey = material.subarray(1);
  const keyId = Number.parseInt(idHex, 16);
  if (ed25519KeyId(name, publicKey) !== keyId) throw new Error("vkey: key id does not match name and key");
  return { name, keyId, publicKey };
}

function ed25519PublicKeyObject(raw: Buffer): crypto.KeyObject {
  return crypto.createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x: raw.toString("base64url") }, format: "jwk" });
}

function checkNoteText(text: string): string | null {
  if (!text.endsWith("\n")) return "note text must end with a newline";
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u0009\u000b-\u001f]/.test(text)) return "note text must not contain control characters other than newline";
  if (!text.isWellFormed()) return "note text is not valid UTF-8 (lone surrogate)";
  return null;
}

/** Produce a signed note. The caller supplies the key; nothing is generated or stored here. */
export function signNote(text: string, keyName: string, privateKey: crypto.KeyObject, publicKeyRaw: Buffer): string {
  const problem = checkNoteText(text);
  if (problem) throw new Error(`signNote: ${problem}`);
  if (!validKeyName(keyName)) throw new Error("signNote: invalid key name");
  const sig = crypto.sign(null, Buffer.from(text, "utf8"), privateKey);
  const id = Buffer.alloc(4);
  id.writeUInt32BE(ed25519KeyId(keyName, publicKeyRaw));
  return `${text}\n${EM_DASH_PREFIX}${keyName} ${Buffer.concat([id, sig]).toString("base64")}\n`;
}

/**
 * Verify a signed note against configured keys, following c2sp.org/signed-note:
 * signatures from unknown (name, id) pairs are ignored; a known key whose
 * signature fails rejects the whole note; at least one known key must verify.
 * `requiredKeyNames` (optional) demands that each listed name verified (witness policy).
 */
export function verifyNote(note: string, keys: readonly VerifierKey[], requiredKeyNames: readonly string[] = []): NoteVerification {
  const fail = (...errors: string[]): NoteVerification => ({ valid: false, errors, verifiedKeyNames: [] });
  if (typeof note !== "string" || note.length === 0) return fail("note must be a non-empty string");
  if (!note.endsWith("\n")) return fail("note must end with a newline");
  const split = note.lastIndexOf("\n\n");
  if (split < 0) return fail("note has no blank line before the signatures");
  const text = note.slice(0, split + 1);
  const problem = checkNoteText(text);
  if (problem) return fail(problem);
  const sigLines = note.slice(split + 2, -1).split("\n");
  if (sigLines.length === 0 || sigLines.some((l) => l === "")) return fail("note has no signature lines");
  if (sigLines.length > 16 * 4) return fail("too many signature lines");

  const verified: string[] = [];
  const seen = new Set<string>();
  for (const line of sigLines) {
    if (!line.startsWith(EM_DASH_PREFIX)) return fail("signature line must start with an em dash and a space");
    const rest = line.slice(EM_DASH_PREFIX.length);
    const sp = rest.indexOf(" ");
    if (sp <= 0) return fail("malformed signature line");
    const name = rest.slice(0, sp);
    const raw = strictBase64Decode(rest.slice(sp + 1));
    if (!validKeyName(name) || !raw || raw.length < 4) return fail("malformed signature line");
    const id = raw.readUInt32BE(0);
    const dedupe = `${name}/${id}`;
    if (seen.has(dedupe)) return fail("duplicate signature line for the same key name and key id");
    seen.add(dedupe);
    const key = keys.find((k) => k.name === name && k.keyId === id);
    if (!key) continue; // unknown key: ignored
    const signature = raw.subarray(4);
    let ok = false;
    try {
      ok = signature.length === 64 && crypto.verify(null, Buffer.from(text, "utf8"), ed25519PublicKeyObject(key.publicKey), signature);
    } catch {
      ok = false;
    }
    if (!ok) return fail(`signature from known key ${name} does not verify`);
    verified.push(name);
  }
  if (verified.length === 0) return fail("no signature from a known key");
  const missing = requiredKeyNames.filter((n) => !verified.includes(n));
  if (missing.length > 0) return fail(`missing required signer(s): ${missing.join(", ")}`);
  return { valid: true, errors: [], text, verifiedKeyNames: verified };
}

// ---------------------------------------------------------------------------
// tlog-checkpoint body
// ---------------------------------------------------------------------------

export interface CheckpointBody {
  readonly origin: string;
  readonly size: number;
  readonly rootHash: Buffer; // 32 bytes
}

export function formatCheckpointBody(body: CheckpointBody): string {
  if (!body.origin || /[\n\r]/.test(body.origin)) throw new Error("checkpoint: invalid origin");
  if (!Number.isSafeInteger(body.size) || body.size < 0) throw new Error("checkpoint: invalid size");
  if (body.rootHash.length !== 32) throw new Error("checkpoint: root hash must be 32 bytes");
  return `${body.origin}\n${body.size}\n${body.rootHash.toString("base64")}\n`;
}

/** Strict parse: >= 3 non-empty lines; size is canonical ASCII decimal; root is canonical base64 of 32 bytes. */
export function parseCheckpointBody(text: string): CheckpointBody & { readonly extensions: readonly string[] } {
  if (!text.endsWith("\n")) throw new Error("checkpoint: text must end with a newline");
  const lines = text.slice(0, -1).split("\n");
  if (lines.length < 3 || lines.some((l) => l === "")) throw new Error("checkpoint: need at least three non-empty lines");
  const [origin, sizeText, rootText, ...extensions] = lines;
  if (!/^(0|[1-9][0-9]*)$/.test(sizeText)) throw new Error("checkpoint: size must be canonical ASCII decimal");
  const size = Number(sizeText);
  if (!Number.isSafeInteger(size)) throw new Error("checkpoint: size out of range");
  const root = strictBase64Decode(rootText);
  if (!root || root.length !== 32) throw new Error("checkpoint: root hash must be canonical base64 of 32 bytes");
  return { origin, size, rootHash: root, extensions };
}

export interface TrustedHead {
  readonly size: number;
  readonly rootHash: Buffer;
}

export interface CheckpointVerifyOptions {
  /** The log origin this verifier expects (first line of the body). */
  readonly origin: string;
  readonly keys: readonly VerifierKey[];
  readonly requiredKeyNames?: readonly string[];
  /** Previously verified head. When set, the new head must extend it (RFC 9162 consistency) and never shrink. */
  readonly previous?: TrustedHead;
  readonly consistencyPath?: readonly Hash[];
}

export interface CheckpointVerification {
  readonly valid: boolean;
  readonly errors: readonly string[];
  readonly head?: TrustedHead;
}

/** Verify a signed checkpoint note: signature, origin, and (optionally) append-only growth from a trusted head. */
export function verifyCheckpoint(note: string, options: CheckpointVerifyOptions): CheckpointVerification {
  const fail = (...errors: string[]): CheckpointVerification => ({ valid: false, errors });
  const verified = verifyNote(note, options.keys, options.requiredKeyNames ?? []);
  if (!verified.valid || verified.text === undefined) return fail(...verified.errors);
  let body: ReturnType<typeof parseCheckpointBody>;
  try {
    body = parseCheckpointBody(verified.text);
  } catch (error) {
    return fail(error instanceof Error ? error.message : String(error));
  }
  if (body.origin !== options.origin) return fail("checkpoint origin does not match the expected origin");
  const head: TrustedHead = { size: body.size, rootHash: body.rootHash };
  const prev = options.previous;
  if (prev) {
    if (body.size < prev.size) return fail("checkpoint is smaller than the trusted head (log shrank)");
    if (body.size === prev.size) {
      if (!body.rootHash.equals(prev.rootHash)) return fail("same size as the trusted head but a different root (split view)");
    } else if (prev.size === 0) {
      // the empty tree is consistent with every tree; nothing to prove
    } else if (!verifyConsistency(prev.size, body.size, prev.rootHash, body.rootHash, options.consistencyPath ?? [])) {
      return fail("no valid consistency proof from the trusted head");
    }
  }
  return { valid: true, errors: [], head };
}
