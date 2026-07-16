import { createServer as createHttpServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { API_BASE, CONTRACT_VERSION } from "../shared/contract.generated.mjs";
import { RequestFault, canonicalJson, sha256, validateInspectRequest, validateSessionId, LIMITS } from "./canonical.mjs";
import { classify, classifierStatus } from "./classifier.mjs";
import { analyzeInnate, decide, POLICY_DOCUMENT, POLICY_HASH } from "./policy.mjs";
import { appendReceipt, getReceipt, signerStatus, verifyLedger } from "./receipts.mjs";
import { evaluateTripwires, tripwireRegistry } from "./tripwires.mjs";
import { getPublicSession, getSession, updateSession } from "./sessions.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const publicRoot = path.resolve(here, "..", "public");
const spaceRoot = path.resolve(here, "..", "..");
const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8" };

function headers(contentType = "application/json; charset=utf-8", api = true) {
  return {
    "content-type": contentType,
    "cache-control": api ? "no-store" : "public, max-age=300",
    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
  };
}

function sendJson(response, status, body) {
  response.writeHead(status, headers());
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > LIMITS.maxBodyBytes) throw new RequestFault("BODY_TOO_LARGE", `body exceeds ${LIMITS.maxBodyBytes} bytes`, 413);
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    throw new RequestFault("INVALID_JSON", "request body must be valid JSON");
  }
}

function sessionIdFor(request, body = {}) {
  return validateSessionId(String(request.headers["x-immune-session"] ?? body.sessionId ?? ""));
}

async function runDecision(request, body, { toolRequested }) {
  const started = performance.now();
  const sessionId = sessionIdFor(request, body);
  const session = getSession(sessionId, { increment: true });
  const normalized = validateInspectRequest(body, { toolRequired: toolRequested });
  const innate = analyzeInnate(normalized, session);
  const chainBefore = await verifyLedger();
  const tripwires = evaluateTripwires({
    actor: normalized.actor,
    tool: normalized.tool,
    session,
    unapprovedHosts: innate.unapprovedHosts,
    bypassDetected: innate.bypassDetected,
    chainOk: chainBefore.ok,
    sequenceGap: chainBefore.issues.some((issue) => issue.code === "CHAIN_LINK_MISMATCH"),
  });
  for (const tripwire of tripwires.filter((item) => item.evaluationState === "FIRED")) {
    innate.findings.push({ code: `TRIPWIRE_${tripwire.id}`, severity: "critical", detail: tripwire.name, channel: "tripwire" });
  }
  const classifier = await classify(normalized.content);
  const signer = signerStatus();
  let outcome = decide({ findings: innate.findings, classifier, toolRequested, signerAvailable: signer.state === "READY" });
  const payload = {
    schemaVersion: "szl.immune.receipt-payload/v1",
    recordedAt: new Date().toISOString(),
    requestKind: toolRequested ? "tool_authorize" : "inspect",
    sessionHash: sha256(sessionId),
    actorHash: normalized.actor.id ? sha256(normalized.actor.id) : null,
    source: normalized.source,
    inputSha256: sha256(normalized.content),
    actionSha256: normalized.tool ? sha256(canonicalJson(normalized.tool)) : null,
    policyVersion: POLICY_DOCUMENT.schemaVersion,
    policySha256: POLICY_HASH,
    classifier: {
      state: classifier.state,
      modelId: classifier.modelId,
      revision: classifier.revision,
      weightsSha256: classifier.weightsSha256,
      evaluated: classifier.evaluated,
      label: classifier.label,
      score: classifier.score,
    },
    decision: outcome.decision,
    reasons: outcome.reasons,
    findingCodes: innate.findings.map((item) => item.code),
    latencyMs: Math.round(performance.now() - started),
    buildCommit: process.env.BUILD_COMMIT ?? "UNREPORTED",
  };
  let receipt;
  try {
    receipt = await appendReceipt(payload);
  } catch {
    receipt = { state: "UNAVAILABLE", receiptId: null, reason: "receipt_write_failed" };
  }
  if (toolRequested && outcome.decision === "ALLOW" && receipt.state !== "SIGNED") {
    outcome = { decision: "UNAVAILABLE", reasons: ["signed_receipt_required"] };
  }
  return {
    schemaVersion: "szl.immune.decision/v1",
    decision: outcome.decision,
    reasons: outcome.reasons,
    findings: innate.findings,
    classifier,
    receipt,
    tripwires,
    normalization: normalized.normalization,
  };
}

async function status() {
  const classifier = await classifierStatus();
  const signer = signerStatus();
  const chain = await verifyLedger();
  return {
    schemaVersion: "szl.immune.status/v1",
    service: { state: "READY", contractVersion: CONTRACT_VERSION, buildCommit: process.env.BUILD_COMMIT ?? "UNREPORTED" },
    policy: { state: "ACTIVE", version: POLICY_DOCUMENT.schemaVersion, sha256: POLICY_HASH, deterministicFirst: true },
    classifier,
    signer,
    capabilities: {
      inspect: "READY_WITH_REVIEW_FALLBACK",
      toolAuthorization: classifier.state === "QUALIFIED" && signer.state === "READY" ? "READY" : "UNAVAILABLE",
      receiptChain: signer.state === "READY" && chain.ok ? "READY" : "UNAVAILABLE",
      globalMutation: "DENIED",
    },
    chain,
  };
}

async function serveStatic(response, pathname) {
  const target = resolveStaticPath(pathname);
  if (!target) return false;
  try {
    const content = await readFile(target);
    response.writeHead(200, headers(MIME[path.extname(target)] ?? "application/octet-stream", false));
    response.end(content);
    return true;
  } catch {
    return false;
  }
}

export function resolveStaticPath(pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return null; }
  if (decoded.includes("\0")) return null;
  const requested = decoded === "/" ? "index.html" : decoded.replace(/^\/+/u, "");
  const target = path.resolve(publicRoot, requested);
  const relative = path.relative(publicRoot, target);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return null;
  return target;
}

export function createImmuneServer() {
  return createHttpServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    try {
      if (request.method === "GET" && url.pathname === `${API_BASE}/status`) return sendJson(response, 200, await status());
      if (request.method === "GET" && url.pathname === `${API_BASE}/tripwires`) return sendJson(response, 200, { schemaVersion: "szl.immune.tripwires/v1", tripwires: tripwireRegistry() });
      if (request.method === "GET" && url.pathname === `${API_BASE}/session/state`) return sendJson(response, 200, getPublicSession(sessionIdFor(request)));
      if (request.method === "POST" && url.pathname === `${API_BASE}/session/state`) return sendJson(response, 200, updateSession(sessionIdFor(request), await readJson(request)));
      if (request.method === "POST" && url.pathname === `${API_BASE}/inspect`) return sendJson(response, 200, await runDecision(request, await readJson(request), { toolRequested: false }));
      if (request.method === "POST" && url.pathname === `${API_BASE}/tool-authorize`) return sendJson(response, 200, await runDecision(request, await readJson(request), { toolRequested: true }));
      if (request.method === "GET" && url.pathname.startsWith(`${API_BASE}/receipts/`)) {
        const receiptId = url.pathname.slice(`${API_BASE}/receipts/`.length);
        if (!/^[a-f0-9]{64}$/u.test(receiptId)) throw new RequestFault("INVALID_RECEIPT_ID", "receiptId must be a SHA-256 digest");
        const receipt = await getReceipt(receiptId);
        return receipt ? sendJson(response, 200, receipt) : sendJson(response, 404, { error: "NOT_FOUND", message: "receipt not found" });
      }
      if (request.method === "GET" && url.pathname === "/openapi.json") {
        response.writeHead(200, headers("application/json; charset=utf-8"));
        return response.end(await readFile(path.join(spaceRoot, "openapi.json")));
      }
      if (url.pathname === "/api/immune/state") {
        if (request.method !== "GET") return sendJson(response, 403, { error: "GLOBAL_MUTATION_DENIED", message: "use the v1 session-scoped state endpoint" });
        const state = getPublicSession(sessionIdFor(request));
        const chain = await verifyLedger();
        return sendJson(response, 200, { mode: "SESSION_SCOPED", ...state, ledgerCount: chain.count, lastHash: chain.lastHash });
      }
      if (url.pathname === "/api/immune/reset" || url.pathname === "/api/immune/ledger") {
        if (request.method !== "GET") return sendJson(response, 403, { error: "GLOBAL_MUTATION_DENIED", message: "public global mutation is disabled" });
      }
      if (request.method === "GET" && url.pathname === "/api/immune/ledger/verify") return sendJson(response, 200, await verifyLedger());
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
