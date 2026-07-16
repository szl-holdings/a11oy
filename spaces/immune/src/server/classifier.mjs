import { access, readFile } from "node:fs/promises";
import { createHash, createPublicKey, verify } from "node:crypto";
import { pathToFileURL } from "node:url";
import path from "node:path";

const HEX40 = /^[a-f0-9]{40}$/u;
const HEX64 = /^[a-f0-9]{64}$/u;

function env(name, fallback = null) {
  const value = process.env[name]?.trim();
  return value || fallback;
}

async function hashFile(file) {
  const content = await readFile(file);
  return createHash("sha256").update(content).digest("hex");
}

export function classifierManifest() {
  return {
    schemaVersion: "szl.immune.classifier-adapter/v1",
    state: env("IMMUNE_CLASSIFIER_STATE", "UNAVAILABLE"),
    modelId: env("IMMUNE_CLASSIFIER_MODEL_ID", "protectai/deberta-v3-small-prompt-injection-v2"),
    revision: env("IMMUNE_CLASSIFIER_REVISION"),
    weightsSha256: env("IMMUNE_CLASSIFIER_WEIGHTS_SHA256"),
    tokenizerSha256: env("IMMUNE_CLASSIFIER_TOKENIZER_SHA256"),
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
  return Buffer.concat([
    Buffer.from(`DSSEv1 ${typeBytes.length} `, "utf8"),
    typeBytes,
    Buffer.from(` ${payload.length} `, "utf8"),
    payload,
  ]);
}

async function qualificationReason(manifest) {
  if (!manifest.qualificationReceipt) return "qualification_receipt_missing";
  if (!manifest.qualificationKeyid) return "qualification_keyid_missing";
  try {
    const envelope = JSON.parse(await readFile(manifest.qualificationReceipt, "utf8"));
    const signature = envelope.signatures?.[0];
    const payloadBytes = Buffer.from(envelope.payload, "base64");
    const publicKeyBytes = Buffer.from(signature.publicKeySpki, "base64");
    const keyid = createHash("sha256").update(publicKeyBytes).digest("hex");
    if (keyid !== manifest.qualificationKeyid || signature.keyid !== keyid) return "qualification_key_not_allowed";
    const publicKey = createPublicKey({ key: publicKeyBytes, format: "der", type: "spki" });
    if (!verify(null, dssePae(envelope.payloadType, payloadBytes), publicKey, Buffer.from(signature.sig, "base64"))) {
      return "qualification_signature_invalid";
    }
    const payload = JSON.parse(payloadBytes.toString("utf8"));
    if (payload.schemaVersion !== "szl.immune.classifier-qualification/v1" || payload.verdict !== "QUALIFIED") return "qualification_payload_invalid";
    if (payload.modelId !== manifest.modelId || payload.revision !== manifest.revision || payload.weightsSha256 !== manifest.weightsSha256 || payload.tokenizerSha256 !== manifest.tokenizerSha256) {
      return "qualification_pin_mismatch";
    }
    return null;
  } catch {
    return "qualification_receipt_unverifiable";
  }
}

export async function classifierStatus() {
  const manifest = classifierManifest();
  const reasons = [];
  if (!HEX40.test(manifest.revision ?? "")) reasons.push("immutable_revision_missing");
  if (!HEX64.test(manifest.weightsSha256 ?? "")) reasons.push("weights_sha256_missing");
  if (!HEX64.test(manifest.tokenizerSha256 ?? "")) reasons.push("tokenizer_sha256_missing");
  if (!manifest.weightsPath) reasons.push("weights_path_missing");
  if (!manifest.tokenizerPath) reasons.push("tokenizer_path_missing");
  if (!manifest.adapterPath) reasons.push("adapter_path_missing");
  if (!manifest.runtime) reasons.push("runtime_unreported");
  if (!manifest.device) reasons.push("device_unreported");

  if (manifest.weightsPath) {
    try {
      await access(manifest.weightsPath);
      if (HEX64.test(manifest.weightsSha256 ?? "") && await hashFile(manifest.weightsPath) !== manifest.weightsSha256) {
        reasons.push("weights_hash_mismatch");
      }
    } catch {
      reasons.push("weights_unreadable");
    }
  }
  if (manifest.tokenizerPath) {
    try {
      await access(manifest.tokenizerPath);
      if (HEX64.test(manifest.tokenizerSha256 ?? "") && await hashFile(manifest.tokenizerPath) !== manifest.tokenizerSha256) {
        reasons.push("tokenizer_hash_mismatch");
      }
    } catch {
      reasons.push("tokenizer_unreadable");
    }
  }
  if (manifest.adapterPath) {
    try { await access(manifest.adapterPath); } catch { reasons.push("adapter_unreadable"); }
  }
  const qualification = await qualificationReason(manifest);
  if (qualification) reasons.push(qualification);

  const requested = new Set(["THIRD_PARTY_BASELINE", "SZL_TRAINED_CANDIDATE", "QUALIFIED"]);
  return {
    state: reasons.length === 0 && requested.has(manifest.state) ? manifest.state : "UNAVAILABLE",
    modelId: manifest.modelId,
    revision: manifest.revision,
    weightsSha256: manifest.weightsSha256,
    tokenizerSha256: manifest.tokenizerSha256,
    runtime: manifest.runtime,
    device: manifest.device,
    reasons: [...new Set(reasons)].sort(),
  };
}

export async function classify(content) {
  const status = await classifierStatus();
  if (status.state === "UNAVAILABLE") return { ...status, score: null, label: null, evaluated: false };
  try {
    const moduleUrl = pathToFileURL(path.resolve(classifierManifest().adapterPath));
    const adapter = await import(moduleUrl.href);
    if (typeof adapter.predict !== "function") throw new Error("adapter_predict_missing");
    const result = await adapter.predict({ content, manifest: classifierManifest() });
    if (!result || !Number.isFinite(result.score) || !["SAFE", "INJECTION"].includes(result.label)) {
      throw new Error("adapter_contract_invalid");
    }
    return { ...status, score: result.score, label: result.label, evaluated: true };
  } catch (error) {
    return { ...status, state: "UNAVAILABLE", score: null, label: null, evaluated: false, reasons: [...status.reasons, `adapter_failed:${error.message}`] };
  }
}
