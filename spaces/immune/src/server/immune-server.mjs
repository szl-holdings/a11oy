import { createServer as createHttpServer } from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { API_BASE, CONTRACT_VERSION } from "../shared/contract.generated.mjs";
import { STATIC_MANIFEST } from "../shared/static-manifest.generated.mjs";
import { RequestFault, canonicalJson, validateInspectRequest, validateSessionId, LIMITS } from "./canonical.mjs";
import { classify, classifierStatus } from "./classifier.mjs";
import { analyzeInnate, decide, POLICY_DOCUMENT, POLICY_HASH } from "./policy.mjs";
import { appendReceipt, getReceipt, ledgerLimits, signerStatus, verifyLedger } from "./receipts.mjs";
import { evaluateTripwires, tripwireRegistry } from "./tripwires.mjs";
import { getPublicSession, getSession, updateSession } from "./sessions.mjs";
import { admissionLimits, admitRequest, DeadlineFault, runWithDeadline } from "./admission.mjs";
import { commitmentStatus, commitValue } from "./commitments.mjs";
import { readStableFile } from "./files.mjs";
import { authorityStatus, verifyAuthority } from "./authority.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const publicRoot = path.resolve(here, "..", "public");
const spaceRoot = path.resolve(here, "..", "..");

function headers(contentType = "application/json; charset=utf-8", api = true, extra = {}) {
  return {
    "content-type": contentType,
    "cache-control": api ? "no-store" : "public, max-age=300",
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff", "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()", ...extra,
  };
}

function sendJson(response, status, body, extraHeaders = {}) {
  response.writeHead(status, headers("application/json; charset=utf-8", true, extraHeaders));
  response.end(JSON.stringify(body));
}

async function readJson(request, signal) {
  abortIfNeeded(signal);
  return new Promise((resolve, reject) => {
    const chunks = [];
    let bytes = 0;
    const cleanup = () => {
      request.off("data", onData); request.off("end", onEnd); request.off("error", onError); request.off("aborted", onAborted);
      signal?.removeEventListener("abort", onAbort);
    };
    const fail = (error) => { cleanup(); reject(error); };
    const onAbort = () => { cleanup(); request.resume(); reject(new DeadlineFault()); };
    const onError = () => fail(new RequestFault("BODY_READ_FAILED", "request body could not be read"));
    const onAborted = () => fail(new RequestFault("BODY_ABORTED", "request body was aborted"));
    const onData = (chunk) => {
      bytes += chunk.length;
      if (bytes > LIMITS.maxBodyBytes) { cleanup(); request.resume(); reject(new RequestFault("BODY_TOO_LARGE", `body exceeds ${LIMITS.maxBodyBytes} bytes`, 413)); }
      else chunks.push(chunk);
    };
    const onEnd = () => {
      cleanup();
      try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")); }
      catch { reject(new RequestFault("INVALID_JSON", "request body must be valid JSON")); }
    };
    request.on("data", onData); request.once("end", onEnd); request.once("error", onError); request.once("aborted", onAborted);
    signal?.addEventListener("abort", onAbort, { once: true });
    if (signal?.aborted) onAbort();
  });
}

function sessionIdFor(request) {
  return validateSessionId(String(request.headers["x-immune-session"] ?? ""));
}

function clientIp(request) {
  return request.socket.remoteAddress || "UNKNOWN";
}

function abortIfNeeded(signal) {
  if (signal?.aborted) throw new DeadlineFault();
}

async function admitted(request, response, handler) {
  const sessionId = sessionIdFor(request);
  const admission = admitRequest({ sessionId, ip: clientIp(request) });
  if (!admission.accepted) {
    return sendJson(response, 429, { error: "RATE_LIMITED", message: `request rejected by ${admission.scope} admission control` }, admission.headers);
  }
  try {
    const result = await runWithDeadline((signal) => handler({ sessionId, signal }), admission);
    return sendJson(response, result.status ?? 200, result.body ?? result, admission.headers);
  } catch (error) {
    if (error instanceof DeadlineFault) {
      response.once("finish", () => request.destroy());
      return sendJson(response, 504, { error: "DEADLINE_EXCEEDED", message: "request exceeded its bounded execution deadline" });
    }
    throw error;
  }
}

async function runDecision(request, body, { toolRequested, sessionId, signal }) {
  const started = performance.now();
  abortIfNeeded(signal);
  const session = getSession(sessionId, { increment: true });
  let normalized = validateInspectRequest(body, { toolRequired: toolRequested });
  const authority = toolRequested ? verifyAuthority(request, normalized) : { state: "NOT_REQUIRED" };
  if (toolRequested && authority.state === "VERIFIED") normalized = { ...normalized, actor: authority.actor, source: authority.source };
  const innate = analyzeInnate(normalized, session);
  abortIfNeeded(signal);
  const chainBefore = await verifyLedger();
  abortIfNeeded(signal);
  const tripwires = evaluateTripwires({
    actor: normalized.actor, tool: normalized.tool, session,
    unapprovedHosts: innate.unapprovedHosts, bypassDetected: innate.bypassDetected,
    chainOk: chainBefore.ok,
    sequenceGap: chainBefore.issues.some((issue) => ["CHAIN_LINK_MISMATCH", "CHAIN_SEQUENCE_MISMATCH", "PAYLOAD_CHAIN_LINK_MISMATCH"].includes(issue.code)),
  });
  for (const tripwire of tripwires.filter((item) => item.evaluationState === "FIRED")) {
    innate.findings.push({ code: `TRIPWIRE_${tripwire.id}`, severity: "critical", detail: tripwire.name, channel: "tripwire" });
  }
  const classifier = await classify(normalized.content, { signal });
  abortIfNeeded(signal);
  const signer = signerStatus();
  let outcome = decide({ findings: innate.findings, classifier, toolRequested, signerAvailable: signer.state === "READY" });
  const privacy = commitmentStatus();
  if (toolRequested && ["ALLOW", "REVIEW"].includes(outcome.decision) && authority.state !== "VERIFIED") outcome = { decision: "UNAVAILABLE", reasons: [authority.reason ?? "verified_authority_required"] };
  if (toolRequested && ["ALLOW", "REVIEW"].includes(outcome.decision) && privacy.state !== "READY") outcome = { decision: "UNAVAILABLE", reasons: ["keyed_commitments_required"] };
  const classifierScore = classifier.score === null ? null : { value: Math.round(classifier.score * 1_000_000), scale: 1_000_000 };
  const payload = {
    schemaVersion: "szl.immune.receipt-payload/v1", recordedAt: new Date().toISOString(),
    requestKind: toolRequested ? "tool_authorize" : "inspect",
    sessionCommitment: commitValue(sessionId, "session"),
    actorCommitment: normalized.actor.id ? commitValue(normalized.actor.id, "actor") : null,
    source: normalized.source,
    inputCommitment: commitValue(normalized.content, "input"),
    actionCommitment: normalized.tool ? commitValue(canonicalJson(normalized.tool), "action") : null,
    privacyDisclosure: privacy.disclosure,
    policyVersion: POLICY_DOCUMENT.schemaVersion, policySha256: POLICY_HASH,
    classifier: {
      state: classifier.state, modelId: classifier.modelId, revision: classifier.revision,
      weightsSha256: classifier.weightsSha256, adapterSha256: classifier.adapterSha256,
      adapterContractVersion: classifier.adapterContractVersion, runtime: classifier.runtime,
      device: classifier.device, evaluated: classifier.evaluated, label: classifier.label, score: classifierScore,
    },
    decision: outcome.decision, reasons: outcome.reasons,
    findingCodes: innate.findings.map((item) => item.code),
    latencyMs: Math.round(performance.now() - started), buildCommit: process.env.BUILD_COMMIT ?? "UNREPORTED",
  };
  abortIfNeeded(signal);
  let receipt;
  try { receipt = await appendReceipt(payload); }
  catch { receipt = { state: "UNAVAILABLE", receiptId: null, reason: "receipt_write_failed" }; }
  if (toolRequested && outcome.decision === "ALLOW" && receipt.state !== "SIGNED") {
    outcome = { decision: "UNAVAILABLE", reasons: ["signed_receipt_required"] };
  }
  return {
    schemaVersion: "szl.immune.decision/v1", decision: outcome.decision, reasons: outcome.reasons,
    findings: innate.findings, classifier, receipt, tripwires,
    normalization: normalized.normalization, privacy, authority: { state: authority.state, reason: authority.reason ?? null },
  };
}

async function status(signal) {
  abortIfNeeded(signal);
  const classifier = await classifierStatus();
  abortIfNeeded(signal);
  const signer = signerStatus();
  const chain = await verifyLedger();
  abortIfNeeded(signal);
  const privacy = commitmentStatus();
  const authority = authorityStatus();
  return {
    schemaVersion: "szl.immune.status/v1",
    service: { state: "READY", contractVersion: CONTRACT_VERSION, buildCommit: process.env.BUILD_COMMIT ?? "UNREPORTED" },
    policy: { state: "ACTIVE", version: POLICY_DOCUMENT.schemaVersion, sha256: POLICY_HASH, deterministicFirst: true },
    classifier, signer, privacy, authority,
    admission: { state: "ACTIVE", ...admissionLimits() },
    ledger: { limits: ledgerLimits(), externalAnchor: chain.externalAnchor },
    capabilities: {
      inspect: "READY_WITH_REVIEW_FALLBACK",
      toolAuthorization: classifier.state === "QUALIFIED" && signer.state === "READY" && privacy.state === "READY" && authority.state === "READY" ? "READY" : "UNAVAILABLE",
      receiptChain: signer.state === "READY" && chain.ok ? "READY" : "UNAVAILABLE",
      receiptReadback: privacy.publicReceiptReadback,
      globalMutation: "DENIED",
    }, chain,
  };
}

async function serveStatic(response, pathname) {
  const entry = resolveStaticPath(pathname);
  if (!entry) return false;
  try {
    const measured = await readStableFile(entry.target, { root: publicRoot, maxBytes: entry.bytes });
    if (measured.bytes.length !== entry.bytes || measured.sha256 !== entry.sha256) return false;
    response.writeHead(200, headers(entry.type, false));
    response.end(measured.bytes);
    return true;
  } catch { return false; }
}

export function resolveStaticPath(pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return null; }
  if (decoded.includes("\0")) return null;
  const entry = STATIC_MANIFEST[decoded];
  return entry ? { target: path.join(publicRoot, entry.file), ...entry } : null;
}

export function createImmuneServer() {
  return createHttpServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    try {
      if (request.method === "GET" && url.pathname === `${API_BASE}/status`) return await admitted(request, response, async ({ signal }) => status(signal));
      if (request.method === "GET" && url.pathname === `${API_BASE}/tripwires`) return await admitted(request, response, async () => ({ schemaVersion: "szl.immune.tripwires/v1", tripwires: tripwireRegistry() }));
      if (request.method === "GET" && url.pathname === `${API_BASE}/session/state`) return await admitted(request, response, async ({ sessionId }) => getPublicSession(sessionId));
      if (request.method === "POST" && url.pathname === `${API_BASE}/session/state`) return await admitted(request, response, async ({ sessionId, signal }) => { const body = await readJson(request, signal); abortIfNeeded(signal); return updateSession(sessionId, body); });
      if (request.method === "POST" && url.pathname === `${API_BASE}/inspect`) return await admitted(request, response, async ({ sessionId, signal }) => runDecision(request, await readJson(request, signal), { toolRequested: false, sessionId, signal }));
      if (request.method === "POST" && url.pathname === `${API_BASE}/tool-authorize`) return await admitted(request, response, async ({ sessionId, signal }) => runDecision(request, await readJson(request, signal), { toolRequested: true, sessionId, signal }));
      if (request.method === "GET" && url.pathname.startsWith(`${API_BASE}/receipts/`)) return await admitted(request, response, async ({ sessionId, signal }) => {
        const receiptId = url.pathname.slice(`${API_BASE}/receipts/`.length);
        if (!/^[a-f0-9]{64}$/u.test(receiptId)) throw new RequestFault("INVALID_RECEIPT_ID", "receiptId must be a SHA-256 digest");
        const privacy = commitmentStatus();
        if (privacy.publicReceiptReadback !== "READY_SESSION_SCOPED") return { status: 503, body: { error: "RECEIPT_READBACK_UNAVAILABLE", message: privacy.reason } };
        abortIfNeeded(signal);
        const receipt = await getReceipt(receiptId, { sessionCommitment: commitValue(sessionId, "session") });
        if (receipt?.state === "UNAVAILABLE") return { status: 503, body: { error: "LEDGER_UNAVAILABLE", message: receipt.reason } };
        return receipt ? { status: 200, body: receipt } : { status: 404, body: { error: "NOT_FOUND", message: "receipt not found or not owned by this session" } };
      });
      if (request.method === "GET" && url.pathname === "/openapi.json") {
        const { bytes } = await readStableFile(path.join(spaceRoot, "openapi.json"), { root: spaceRoot, maxBytes: 2 * 1024 * 1024 });
        response.writeHead(200, headers("application/json; charset=utf-8")); return response.end(bytes);
      }
      if (url.pathname === "/api/immune/state") {
        if (request.method !== "GET") return sendJson(response, 403, { error: "GLOBAL_MUTATION_DENIED", message: "use the v1 session-scoped state endpoint" });
        return await admitted(request, response, async ({ sessionId, signal }) => {
          abortIfNeeded(signal); const chain = await verifyLedger(); abortIfNeeded(signal);
          return { mode: "SESSION_SCOPED", ...getPublicSession(sessionId), ledgerCount: chain.count, lastHash: chain.lastHash };
        });
      }
      if (url.pathname === "/api/immune/reset" || url.pathname === "/api/immune/ledger") {
        if (request.method !== "GET") return sendJson(response, 403, { error: "GLOBAL_MUTATION_DENIED", message: "public global mutation is disabled" });
      }
      if (request.method === "GET" && url.pathname === "/api/immune/ledger/verify") return await admitted(request, response, async ({ signal }) => { abortIfNeeded(signal); const result = await verifyLedger(); abortIfNeeded(signal); return result; });
      if (request.method === "GET" && await serveStatic(response, url.pathname)) return;
      sendJson(response, 404, { error: "NOT_FOUND", message: "route not found" });
    } catch (error) {
      if (error instanceof RequestFault) return sendJson(response, error.status, { error: error.code, message: error.message });
      if (error instanceof TypeError) return sendJson(response, 400, { error: "INVALID_REQUEST", message: error.message });
      console.error("immune_request_failed", error?.message ?? "unknown");
      return sendJson(response, 500, { error: "INTERNAL_ERROR", message: "request failed closed" });
    }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number.parseInt(process.env.PORT ?? "7860", 10);
  createImmuneServer().listen(port, "0.0.0.0", () => console.log(`Immune v0.1 listening on ${port}`));
}
