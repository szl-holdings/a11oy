import { mkdir, open } from "node:fs/promises";
import { createPrivateKey, createPublicKey, sign, verify } from "node:crypto";
import path from "node:path";
import { canonicalJson, sha256 } from "./canonical.mjs";
import { readStableFile } from "./files.mjs";

const PAYLOAD_TYPE = "application/vnd.szl.immune.receipt.v1+json";
const RECORD_SCHEMA = "szl.immune.ledger-record/v1";
let appendQueue = Promise.resolve();

function boundedInteger(name, fallback, minimum, maximum) {
  const value = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isSafeInteger(value) ? Math.min(maximum, Math.max(minimum, value)) : fallback;
}

export function ledgerLimits() {
  return {
    maxRecords: boundedInteger("IMMUNE_LEDGER_MAX_RECORDS", 10_000, 1, 1_000_000),
    maxBytes: boundedInteger("IMMUNE_LEDGER_MAX_BYTES", 64 * 1024 * 1024, 4_096, 512 * 1024 * 1024),
  };
}

function ledgerPath() {
  return process.env.IMMUNE_LEDGER_PATH || path.resolve("data", "immune", "v1-receipts.jsonl");
}

function trustedKeyids() {
  return new Set((process.env.IMMUNE_RECEIPT_TRUSTED_KEYIDS ?? "")
    .split(",").map((value) => value.trim().toLowerCase()).filter((value) => /^[a-f0-9]{64}$/u.test(value)));
}

function privateKeyFromEnvironment() {
  const encoded = process.env.IMMUNE_SIGNING_KEY?.trim();
  if (!encoded) return null;
  const bytes = Buffer.from(encoded, "base64");
  if (bytes.length === 32) {
    const prefix = Buffer.from("302e020100300506032b657004220420", "hex");
    return createPrivateKey({ key: Buffer.concat([prefix, bytes]), format: "der", type: "pkcs8" });
  }
  return createPrivateKey({ key: bytes, format: "der", type: "pkcs8" });
}

function signer() {
  try {
    const privateKey = privateKeyFromEnvironment();
    if (!privateKey) return null;
    const publicKey = createPublicKey(privateKey);
    const spki = publicKey.export({ format: "der", type: "spki" });
    return { privateKey, publicKey, spki, keyid: sha256(spki) };
  } catch { return null; }
}

export function signerStatus() {
  const current = signer();
  if (!current) return { state: "UNAVAILABLE", algorithm: "Ed25519", keyid: null, reason: "IMMUNE_SIGNING_KEY is absent or invalid" };
  if (!trustedKeyids().has(current.keyid)) {
    return { state: "UNAVAILABLE", algorithm: "Ed25519", keyid: current.keyid, reason: "signer keyid is not pinned in IMMUNE_RECEIPT_TRUSTED_KEYIDS" };
  }
  return { state: "READY", algorithm: "Ed25519", keyid: current.keyid };
}

export function dssePae(payloadType, payload) {
  const typeBytes = Buffer.from(payloadType, "utf8");
  const payloadBytes = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);
  return Buffer.concat([
    Buffer.from(`DSSEv1 ${typeBytes.length} `, "utf8"), typeBytes,
    Buffer.from(` ${payloadBytes.length} `, "utf8"), payloadBytes,
  ]);
}

async function records() {
  const limits = ledgerLimits();
  let bytes;
  try {
    bytes = (await readStableFile(ledgerPath(), { root: path.dirname(ledgerPath()), maxBytes: limits.maxBytes })).bytes;
  } catch (error) {
    if (error.code === "ENOENT") bytes = Buffer.alloc(0);
    else if (error.code === "file_size_limit_exceeded") return { records: [], fault: { sequence: 0, code: "LEDGER_BYTE_CAP_EXCEEDED" }, bytes: limits.maxBytes + 1 };
    else return { records: [], fault: { sequence: 0, code: `LEDGER_READ_INVALID:${error.code ?? "read_failed"}` }, bytes: 0 };
  }
  if (bytes.length > limits.maxBytes) return { records: [], fault: { sequence: 0, code: "LEDGER_BYTE_CAP_EXCEEDED" }, bytes: bytes.length };
  const content = bytes.toString("utf8");
  const lines = content.split(/\r?\n/u).filter(Boolean);
  if (lines.length > limits.maxRecords) {
    return { records: [], fault: { sequence: 0, code: "LEDGER_RECORD_CAP_EXCEEDED" }, bytes: Buffer.byteLength(content) };
  }
  try {
    return { records: lines.map((line) => JSON.parse(line)), fault: null, bytes: Buffer.byteLength(content) };
  } catch {
    return { records: [], fault: { sequence: 0, code: "LEDGER_JSON_INVALID" }, bytes: Buffer.byteLength(content) };
  }
}

function plainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function validCommitment(value) {
  if (!plainObject(value) || !["HMAC-SHA-256", "SHA-256"].includes(value.scheme) || !/^[a-f0-9]{64}$/u.test(value.value ?? "")) return false;
  return (value.scheme === "HMAC-SHA-256" && value.disclosure === "KEYED_COMMITMENT") ||
    (value.scheme === "SHA-256" && value.disclosure === "DICTIONARY_EXPOSURE_RISK");
}

function verifyRecords(snapshot, { includeRecords = false } = {}) {
  const all = snapshot.records;
  const issues = snapshot.fault ? [snapshot.fault] : [];
  const roots = trustedKeyids();
  if (all.length > 0 && roots.size === 0) issues.push({ sequence: 0, code: "TRUST_ROOTS_UNAVAILABLE" });
  let previous = null;
  for (let index = 0; index < all.length; index += 1) {
    const sequence = index + 1;
    const record = all[index];
    let expectedId = null;
    try {
      if (!plainObject(record) || !plainObject(record.envelope) || !plainObject(record.chain)) throw new Error("record_shape_invalid");
      expectedId = sha256(canonicalJson(record.envelope));
      if (record.schemaVersion !== RECORD_SCHEMA) issues.push({ sequence, code: "RECORD_SCHEMA_INVALID" });
      if (!/^[a-f0-9]{64}$/u.test(record.receiptId ?? "") || record.receiptId !== expectedId) issues.push({ sequence, code: "ENVELOPE_HASH_MISMATCH" });
      if (record.chain.sequence !== sequence) issues.push({ sequence, code: "CHAIN_SEQUENCE_MISMATCH" });
      if ((record.chain.previousEnvelopeSha256 ?? null) !== previous) issues.push({ sequence, code: "CHAIN_LINK_MISMATCH" });
      if (record.envelope.schema !== "szl.immune.dsse-envelope/v1") issues.push({ sequence, code: "ENVELOPE_SCHEMA_INVALID" });
      if (record.envelope.payloadType !== PAYLOAD_TYPE) issues.push({ sequence, code: "PAYLOAD_TYPE_INVALID" });
      if (typeof record.envelope.payload !== "string" || !Array.isArray(record.envelope.signatures) || record.envelope.signatures.length !== 1) throw new Error("envelope_shape_invalid");
      const signature = record.envelope.signatures[0];
      const payload = Buffer.from(record.envelope.payload, "base64");
      const decoded = JSON.parse(payload.toString("utf8"));
      if (!plainObject(decoded) || decoded.schemaVersion !== "szl.immune.receipt-payload/v1") issues.push({ sequence, code: "PAYLOAD_SCHEMA_INVALID" });
      if ((decoded.previousEnvelopeSha256 ?? null) !== previous) issues.push({ sequence, code: "PAYLOAD_CHAIN_LINK_MISMATCH" });
      if (!validCommitment(decoded.sessionCommitment) || !validCommitment(decoded.inputCommitment) ||
        (decoded.actorCommitment !== null && !validCommitment(decoded.actorCommitment)) ||
        (decoded.actionCommitment !== null && !validCommitment(decoded.actionCommitment))) issues.push({ sequence, code: "PAYLOAD_COMMITMENT_INVALID" });
      const publicKeyBytes = Buffer.from(signature.publicKeySpki, "base64");
      const computedKeyid = sha256(publicKeyBytes);
      if (signature.keyid !== computedKeyid) issues.push({ sequence, code: "KEYID_MISMATCH" });
      if (!roots.has(computedKeyid)) issues.push({ sequence, code: "SIGNER_NOT_TRUSTED" });
      const publicKey = createPublicKey({ key: publicKeyBytes, format: "der", type: "spki" });
      if (!verify(null, dssePae(record.envelope.payloadType, payload), publicKey, Buffer.from(signature.sig, "base64"))) {
        issues.push({ sequence, code: "SIGNATURE_INVALID" });
      }
    } catch { issues.push({ sequence, code: "RECORD_STRUCTURE_INVALID" }); }
    previous = expectedId;
  }
  return {
    ok: issues.length === 0,
    count: all.length,
    bytes: snapshot.bytes,
    issues,
    lastHash: previous,
    externalAnchor: { state: "NOT_IMPLEMENTED", label: "ROADMAP" },
    ...(includeRecords ? { records: all } : {}),
  };
}

async function verifyLedgerUnlocked(options = {}) {
  return verifyRecords(await records(), options);
}

export async function verifyLedger(options = {}) {
  await appendQueue;
  return verifyLedgerUnlocked(options);
}

async function appendReceiptUnlocked(payload) {
  const currentSigner = signer();
  const signerState = signerStatus();
  if (!currentSigner || signerState.state !== "READY") return { state: "UNAVAILABLE", receiptId: null, reason: signerState.reason ?? "signer_unavailable" };
  const chain = await verifyLedgerUnlocked();
  if (!chain.ok) return { state: "UNAVAILABLE", receiptId: null, reason: "existing_chain_invalid", chain };
  const publicPayload = { ...payload, previousEnvelopeSha256: chain.lastHash };
  const payloadBytes = Buffer.from(canonicalJson(publicPayload), "utf8");
  const signature = sign(null, dssePae(PAYLOAD_TYPE, payloadBytes), currentSigner.privateKey);
  const envelope = {
    schema: "szl.immune.dsse-envelope/v1", payloadType: PAYLOAD_TYPE, payload: payloadBytes.toString("base64"),
    signatures: [{ keyid: currentSigner.keyid, sig: signature.toString("base64"), publicKeySpki: currentSigner.spki.toString("base64") }],
  };
  const receiptId = sha256(canonicalJson(envelope));
  const record = { schemaVersion: RECORD_SCHEMA, receiptId, envelope, chain: { sequence: chain.count + 1, previousEnvelopeSha256: chain.lastHash } };
  const line = `${canonicalJson(record)}\n`;
  const limits = ledgerLimits();
  if (chain.count + 1 > limits.maxRecords) return { state: "UNAVAILABLE", receiptId: null, reason: "ledger_record_cap_reached" };
  if (chain.bytes + Buffer.byteLength(line) > limits.maxBytes) return { state: "UNAVAILABLE", receiptId: null, reason: "ledger_byte_cap_reached" };
  await mkdir(path.dirname(ledgerPath()), { recursive: true });
  const handle = await open(ledgerPath(), "a", 0o600);
  try { await handle.writeFile(line, "utf8"); await handle.sync(); }
  finally { await handle.close(); }
  return { state: "SIGNED", receiptId, keyid: currentSigner.keyid, chain: record.chain };
}

export function appendReceipt(payload) {
  const task = appendQueue.then(() => appendReceiptUnlocked(payload));
  appendQueue = task.catch(() => undefined);
  return task;
}

export async function getReceipt(receiptId, { sessionCommitment } = {}) {
  const chain = await verifyLedger({ includeRecords: true });
  if (!chain.ok) return { state: "UNAVAILABLE", reason: "ledger_verification_failed", chain };
  const record = chain.records.find((item) => item.receiptId === receiptId);
  if (!record) return null;
  const payload = JSON.parse(Buffer.from(record.envelope.payload, "base64").toString("utf8"));
  if (!sessionCommitment || canonicalJson(payload.sessionCommitment) !== canonicalJson(sessionCommitment)) return null;
  return {
    schemaVersion: "szl.immune.receipt-response/v1", receiptId, verified: true,
    envelope: record.envelope, payload, chain: record.chain,
    externalAnchor: { state: "NOT_IMPLEMENTED", label: "ROADMAP" },
  };
}
