import { mkdir, open, readFile } from "node:fs/promises";
import { createPrivateKey, createPublicKey, sign, verify } from "node:crypto";
import path from "node:path";
import { canonicalJson, sha256 } from "./canonical.mjs";

const PAYLOAD_TYPE = "application/vnd.szl.immune.receipt.v1+json";
let appendQueue = Promise.resolve();

function ledgerPath() {
  return process.env.IMMUNE_LEDGER_PATH || path.resolve("data", "immune", "v1-receipts.jsonl");
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
  } catch {
    return null;
  }
}

export function signerStatus() {
  const current = signer();
  return current
    ? { state: "READY", algorithm: "Ed25519", keyid: current.keyid }
    : { state: "UNAVAILABLE", algorithm: "Ed25519", keyid: null, reason: "IMMUNE_SIGNING_KEY is absent or invalid" };
}

export function dssePae(payloadType, payload) {
  const typeBytes = Buffer.from(payloadType, "utf8");
  const payloadBytes = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);
  return Buffer.concat([
    Buffer.from(`DSSEv1 ${typeBytes.length} `, "utf8"),
    typeBytes,
    Buffer.from(` ${payloadBytes.length} `, "utf8"),
    payloadBytes,
  ]);
}

async function records() {
  const content = await readFile(ledgerPath(), "utf8").catch((error) => error.code === "ENOENT" ? "" : Promise.reject(error));
  return content.split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
}

export async function verifyLedger() {
  const all = await records();
  const issues = [];
  let previous = null;
  for (let index = 0; index < all.length; index += 1) {
    const record = all[index];
    const expectedId = sha256(canonicalJson(record.envelope));
    if (record.receiptId !== expectedId) issues.push({ sequence: index + 1, code: "ENVELOPE_HASH_MISMATCH" });
    if ((record.chain?.previousEnvelopeSha256 ?? null) !== previous) issues.push({ sequence: index + 1, code: "CHAIN_LINK_MISMATCH" });
    const signature = record.envelope?.signatures?.[0];
    try {
      const payload = Buffer.from(record.envelope.payload, "base64");
      const publicKeyBytes = Buffer.from(signature.publicKeySpki, "base64");
      if (signature.keyid !== sha256(publicKeyBytes)) issues.push({ sequence: index + 1, code: "KEYID_MISMATCH" });
      const publicKey = createPublicKey({ key: publicKeyBytes, format: "der", type: "spki" });
      if (!verify(null, dssePae(record.envelope.payloadType, payload), publicKey, Buffer.from(signature.sig, "base64"))) {
        issues.push({ sequence: index + 1, code: "SIGNATURE_INVALID" });
      }
    } catch {
      issues.push({ sequence: index + 1, code: "SIGNATURE_UNVERIFIABLE" });
    }
    previous = expectedId;
  }
  return { ok: issues.length === 0, count: all.length, issues, lastHash: previous };
}

async function appendReceiptUnlocked(payload) {
  const currentSigner = signer();
  if (!currentSigner) return { state: "UNAVAILABLE", receiptId: null, reason: "signer_unavailable" };
  const chain = await verifyLedger();
  if (!chain.ok) return { state: "UNAVAILABLE", receiptId: null, reason: "existing_chain_invalid", chain };
  const publicPayload = { ...payload, previousEnvelopeSha256: chain.lastHash };
  const payloadBytes = Buffer.from(canonicalJson(publicPayload), "utf8");
  const signature = sign(null, dssePae(PAYLOAD_TYPE, payloadBytes), currentSigner.privateKey);
  const envelope = {
    schema: "szl.immune.dsse-envelope/v1",
    payloadType: PAYLOAD_TYPE,
    payload: payloadBytes.toString("base64"),
    signatures: [{
      keyid: currentSigner.keyid,
      sig: signature.toString("base64"),
      publicKeySpki: currentSigner.spki.toString("base64"),
    }],
  };
  const receiptId = sha256(canonicalJson(envelope));
  const record = {
    schemaVersion: "szl.immune.ledger-record/v1",
    receiptId,
    envelope,
    chain: { sequence: chain.count + 1, previousEnvelopeSha256: chain.lastHash },
  };
  await mkdir(path.dirname(ledgerPath()), { recursive: true });
  const handle = await open(ledgerPath(), "a", 0o600);
  try {
    await handle.writeFile(`${canonicalJson(record)}\n`, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  return { state: "SIGNED", receiptId, keyid: currentSigner.keyid, chain: record.chain };
}

export function appendReceipt(payload) {
  const task = appendQueue.then(() => appendReceiptUnlocked(payload));
  appendQueue = task.catch(() => undefined);
  return task;
}

export async function getReceipt(receiptId) {
  const record = (await records()).find((item) => item.receiptId === receiptId);
  if (!record) return null;
  return {
    schemaVersion: "szl.immune.receipt-response/v1",
    receiptId,
    envelope: record.envelope,
    payload: JSON.parse(Buffer.from(record.envelope.payload, "base64").toString("utf8")),
    chain: record.chain,
  };
}
