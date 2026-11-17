// SPDX-License-Identifier: Apache-2.0
// Read-only live x402 challenge witness. Unpaid HEAD only; never a settlement test.
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";

const SOURCE_WORKER = new URL("./worker.js", import.meta.url);
const LIVE_URL = "https://inference.a-11-oy.com/v1/chat/completions";
const ACCEPT_FIELDS = ["scheme", "network", "amount", "asset", "payTo", "maxTimeoutSeconds", "extra"];

function decodeHeader(value) {
  if (typeof value !== "string" || value.length > 32768 ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(value) || value.length % 4 === 1) {
    throw new Error("INVALID_PAYMENT_REQUIRED_HEADER");
  }
  const bytes = Buffer.from(value, "base64");
  if (bytes.toString("base64").replace(/=+$/, "") !== value.replace(/=+$/, "")) {
    throw new Error("INVALID_PAYMENT_REQUIRED_HEADER");
  }
  const parsed = JSON.parse(bytes.toString("utf8"));
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("INVALID_PAYMENT_REQUIRED_BODY");
  }
  return parsed;
}

function terms(value) {
  if (value?.x402Version !== 2 ||
      typeof value?.resource?.url !== "string" ||
      !Array.isArray(value?.accepts) || value.accepts.length === 0) {
    throw new Error("INVALID_X402_V2_CHALLENGE");
  }
  return {
    x402Version: value.x402Version,
    resource: { url: value.resource.url },
    accepts: value.accepts.map((entry) => {
      if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
        throw new Error("INVALID_PAYMENT_TERMS");
      }
      const result = {};
      for (const key of ACCEPT_FIELDS) {
        if (Object.hasOwn(entry, key)) result[key] = entry[key];
      }
      if (result.scheme !== "exact" ||
          typeof result.amount !== "string" || !/^[1-9][0-9]*$/.test(result.amount) ||
          typeof result.network !== "string" ||
          typeof result.asset !== "string" || typeof result.payTo !== "string" ||
          !Number.isInteger(result.maxTimeoutSeconds) || result.maxTimeoutSeconds <= 0) {
        throw new Error("INVALID_PAYMENT_TERMS");
      }
      return result;
    }),
  };
}

export function compareUnpaidChallenge(source, status, header) {
  if (status !== 402) return { state: "DRIFT", reason: "UNPAID_STATUS_NOT_402" };
  try {
    const expected = terms(source);
    const observed = terms(decodeHeader(header));
    if (!isDeepStrictEqual(expected, observed)) {
      return { state: "DRIFT", reason: "SOURCE_LIVE_PAYMENT_TERMS_MISMATCH" };
    }
    return { state: "MATCHED_UNPAID_PROTOCOL_ONLY", reason: "SOURCE_LIVE_CHALLENGE_PARITY" };
  } catch (error) {
    const known = new Set(["INVALID_PAYMENT_REQUIRED_HEADER", "INVALID_PAYMENT_REQUIRED_BODY",
      "INVALID_X402_V2_CHALLENGE", "INVALID_PAYMENT_TERMS"]);
    return { state: "DRIFT", reason: known.has(error?.message) ? error.message : "INVALID_PAYMENT_REQUIRED_BODY" };
  }
}

async function localSource() {
  const bytes = await readFile(SOURCE_WORKER);
  const module = await import(`data:text/javascript;base64,${bytes.toString("base64")}`);
  const request = new Request(LIVE_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: "unpaid-witness", messages: [{ role: "user", content: "no inference" }] }),
  });
  const response = await module.default.fetch(request, {});
  if (response.status !== 402) throw new Error("SOURCE_UNPAID_CHALLENGE_UNAVAILABLE");
  return { challenge: await response.json(), sha256: createHash("sha256").update(bytes).digest("hex") };
}

export async function probeLive(fetchImpl = fetch) {
  const source = await localSource();
  let verdict;
  let status = null;
  try {
    const response = await fetchImpl(LIVE_URL, {
      method: "HEAD",
      redirect: "manual",
      signal: AbortSignal.timeout(8000),
    });
    status = response.status;
    verdict = compareUnpaidChallenge(source.challenge, response.status, response.headers.get("payment-required"));
    await response.body?.cancel();
  } catch {
    verdict = { state: "UNAVAILABLE", reason: "NETWORK_OR_TIMEOUT" };
  }
  return {
    schema: "szl.x402-unpaid-protocol-witness/v1",
    observed_at: new Date().toISOString(),
    source_worker_sha256: source.sha256,
    endpoint: LIVE_URL,
    method: "HEAD",
    http_status: status,
    ...verdict,
    payment_settlement_verified: false,
    live_inference_verified: false,
    deployment_source_parity_verified: false,
  };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const verdict = await probeLive();
  process.stdout.write(JSON.stringify(verdict) + "\n");
  if (verdict.state !== "MATCHED_UNPAID_PROTOCOL_ONLY") process.exitCode = 2;
}
