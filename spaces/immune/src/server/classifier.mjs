import { createHash, createPublicKey, verify } from "node:crypto";
import { readStableFile, hashStableFile } from "./files.mjs";

const HEX40 = /^[a-f0-9]{40}$/u;
const HEX64 = /^[a-f0-9]{64}$/u;
export const ADAPTER_CONTRACT_VERSION = "szl.immune.classifier-adapter/v1";
const QUALIFICATION_PAYLOAD_TYPE = "application/vnd.szl.immune.classifier-qualification.v1+json";

function env(name, fallback = null) {
  const value = process.env[name]?.trim();
  return value || fallback;
}

export function classifierManifest() {
  return {
    schemaVersion: "szl.immune.classifier-manifest/v1",
    state: env("IMMUNE_CLASSIFIER_STATE", "UNAVAILABLE"),
    modelId: env("IMMUNE_CLASSIFIER_MODEL_ID", "protectai/deberta-v3-small-prompt-injection-v2"),
    revision: env("IMMUNE_CLASSIFIER_REVISION"),
    weightsSha256: env("IMMUNE_CLASSIFIER_WEIGHTS_SHA256"),
    tokenizerSha256: env("IMMUNE_CLASSIFIER_TOKENIZER_SHA256"),
    adapterSha256: env("IMMUNE_CLASSIFIER_ADAPTER_SHA256"),
    adapterContractVersion: env("IMMUNE_CLASSIFIER_ADAPTER_CONTRACT", ADAPTER_CONTRACT_VERSION),
    weightsPath: env("IMMUNE_CLASSIFIER_WEIGHTS_PATH"),
    tokenizerPath: env("IMMUNE_CLASSIFIER_TOKENIZER_PATH"),
    adapterPath: env("IMMUNE_CLASSIFIER_ADAPTER_PATH"),
    runtime: env("IMMUNE_CLASSIFIER_RUNTIME"),
    device: env("IMMUNE_CLASSIFIER_DEVICE"),
    qualificationReceipt: env("IMMUNE_CLASSIFIER_QUALIFICATION_RECEIPT"),
    qualificationKeyid: env("IMMUNE_QUALIFICATION_KEYID"),
  };
}

function dssePae(payloadType, payload) {
  const typeBytes = Buffer.from(payloadType, "utf8");
  return Buffer.concat([Buffer.from(`DSSEv1 ${typeBytes.length} `, "utf8"), typeBytes, Buffer.from(` ${payload.length} `, "utf8"), payload]);
}

async function qualificationReason(manifest) {
  if (!manifest.qualificationReceipt) return "qualification_receipt_missing";
  if (!HEX64.test(manifest.qualificationKeyid ?? "")) return "qualification_keyid_missing_or_invalid";
  try {
    const receiptFile = await readStableFile(manifest.qualificationReceipt, { maxBytes: 1024 * 1024 });
    const envelope = JSON.parse(receiptFile.bytes.toString("utf8"));
    if (envelope.payloadType !== QUALIFICATION_PAYLOAD_TYPE || !Array.isArray(envelope.signatures) || envelope.signatures.length !== 1) return "qualification_envelope_invalid";
    const signature = envelope.signatures?.[0];
    const payloadBytes = Buffer.from(envelope.payload, "base64");
    const publicKeyBytes = Buffer.from(signature.publicKeySpki, "base64");
    const keyid = createHash("sha256").update(publicKeyBytes).digest("hex");
    if (keyid !== manifest.qualificationKeyid || signature.keyid !== keyid) return "qualification_key_not_allowed";
    const publicKey = createPublicKey({ key: publicKeyBytes, format: "der", type: "spki" });
    if (!verify(null, dssePae(envelope.payloadType, payloadBytes), publicKey, Buffer.from(signature.sig, "base64"))) return "qualification_signature_invalid";
    const payload = JSON.parse(payloadBytes.toString("utf8"));
    if (payload.schemaVersion !== "szl.immune.classifier-qualification/v1" || payload.verdict !== "QUALIFIED") return "qualification_payload_invalid";
    const bound = ["modelId", "revision", "weightsSha256", "tokenizerSha256", "adapterSha256", "adapterContractVersion", "runtime", "device"];
    if (bound.some((field) => payload[field] !== manifest[field])) return "qualification_pin_mismatch";
    return null;
  } catch {
    return "qualification_receipt_unverifiable";
  }
}

async function evaluateManifest({ includeAdapterBytes = false } = {}) {
  const manifest = classifierManifest();
  const reasons = [];
  let adapterBytes = null;
  if (!HEX40.test(manifest.revision ?? "")) reasons.push("immutable_revision_missing");
  if (!HEX64.test(manifest.weightsSha256 ?? "")) reasons.push("weights_sha256_missing");
  if (!HEX64.test(manifest.tokenizerSha256 ?? "")) reasons.push("tokenizer_sha256_missing");
  if (!HEX64.test(manifest.adapterSha256 ?? "")) reasons.push("adapter_sha256_missing");
  if (manifest.adapterContractVersion !== ADAPTER_CONTRACT_VERSION) reasons.push("adapter_contract_unsupported");
  if (!manifest.weightsPath) reasons.push("weights_path_missing");
  if (!manifest.tokenizerPath) reasons.push("tokenizer_path_missing");
  if (!manifest.adapterPath) reasons.push("adapter_path_missing");
  if (!manifest.runtime) reasons.push("runtime_unreported");
  if (!manifest.device) reasons.push("device_unreported");

  if (manifest.weightsPath) {
    try {
      const measured = await hashStableFile(manifest.weightsPath);
      if (HEX64.test(manifest.weightsSha256 ?? "") && measured.sha256 !== manifest.weightsSha256) reasons.push("weights_hash_mismatch");
    } catch (error) { reasons.push(`weights_unavailable:${error.code ?? "read_failed"}`); }
  }
  if (manifest.tokenizerPath) {
    try {
      const measured = await hashStableFile(manifest.tokenizerPath, { maxBytes: 1024 * 1024 * 1024 });
      if (HEX64.test(manifest.tokenizerSha256 ?? "") && measured.sha256 !== manifest.tokenizerSha256) reasons.push("tokenizer_hash_mismatch");
    } catch (error) { reasons.push(`tokenizer_unavailable:${error.code ?? "read_failed"}`); }
  }
  if (manifest.adapterPath) {
    try {
      const measured = await readStableFile(manifest.adapterPath, { maxBytes: 4 * 1024 * 1024 });
      if (HEX64.test(manifest.adapterSha256 ?? "") && measured.sha256 !== manifest.adapterSha256) reasons.push("adapter_hash_mismatch");
      if (includeAdapterBytes) adapterBytes = measured.bytes;
    } catch (error) { reasons.push(`adapter_unavailable:${error.code ?? "read_failed"}`); }
  }
  const qualification = await qualificationReason(manifest);
  if (qualification) reasons.push(qualification);
  const requested = new Set(["THIRD_PARTY_BASELINE", "SZL_TRAINED_CANDIDATE", "QUALIFIED"]);
  const status = {
    state: reasons.length === 0 && requested.has(manifest.state) ? manifest.state : "UNAVAILABLE",
    modelId: manifest.modelId,
    revision: manifest.revision,
    weightsSha256: manifest.weightsSha256,
    tokenizerSha256: manifest.tokenizerSha256,
    adapterSha256: manifest.adapterSha256,
    adapterContractVersion: manifest.adapterContractVersion,
    runtime: manifest.runtime,
    device: manifest.device,
    reasons: [...new Set(reasons)].sort(),
  };
  return { status, manifest, adapterBytes };
}

export async function classifierStatus() {
  return (await evaluateManifest()).status;
}

export async function classify(content, { signal } = {}) {
  const qualified = await evaluateManifest({ includeAdapterBytes: true });
  const status = qualified.status;
  if (status.state === "UNAVAILABLE") return { ...status, score: null, label: null, evaluated: false };
  if (signal?.aborted) return { ...status, state: "UNAVAILABLE", score: null, label: null, evaluated: false, reasons: [...status.reasons, "request_deadline_exceeded"] };
  try {
    const moduleUrl = `data:text/javascript;base64,${qualified.adapterBytes.toString("base64")}`;
    const adapter = await import(moduleUrl);
    if (adapter.adapterContractVersion !== ADAPTER_CONTRACT_VERSION || typeof adapter.predict !== "function") throw new Error("adapter_contract_invalid");
    const result = await adapter.predict({
      content,
      signal,
      identity: {
        modelId: qualified.manifest.modelId,
        revision: qualified.manifest.revision,
        weightsSha256: qualified.manifest.weightsSha256,
        tokenizerSha256: qualified.manifest.tokenizerSha256,
        adapterSha256: qualified.manifest.adapterSha256,
        adapterContractVersion: qualified.manifest.adapterContractVersion,
        runtime: qualified.manifest.runtime,
        device: qualified.manifest.device,
      },
    });
    if (signal?.aborted) throw new Error("request_deadline_exceeded");
    if (!result || !Number.isFinite(result.score) || result.score < 0 || result.score > 1 || !["SAFE", "INJECTION"].includes(result.label)) throw new Error("adapter_result_invalid");
    return { ...status, score: result.score, label: result.label, evaluated: true };
  } catch (error) {
    return { ...status, state: "UNAVAILABLE", score: null, label: null, evaluated: false, reasons: [...status.reasons, `adapter_failed:${error.message}`] };
  }
}
