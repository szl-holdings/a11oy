/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 */
"use strict";
const API = location.pathname.startsWith("/anatomy-ledger") ? "/api/a11oy/v1/anatomy-ledger" : "/api";
const byId = (id) => document.getElementById(id);
const setText = (id, text) => { byId(id).textContent = text; };
const pretty = (value) => JSON.stringify(value, null, 2);
let records = [];
let ledgerAvailable = false;

async function request(route, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${API}/${route}`, { ...options, signal: controller.signal, cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${data.error || "Request failed"}`);
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local service did not respond within 10 seconds.");
    throw error;
  } finally { clearTimeout(timer); }
}

function dateLabel(value) {
  if (typeof value !== "string" || !value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid timestamp in stored file" : date.toLocaleString();
}

function storedOutcome(record) {
  const outcome = record?.policy?.outcome;
  return ["ALLOW", "REVIEW", "BLOCK"].includes(outcome) ? outcome : "UNKNOWN";
}

function renderRecords() {
  const query = byId("record-search").value.toLowerCase();
  const outcome = byId("outcome-filter").value;
  const filtered = records.filter((record) => (!outcome || storedOutcome(record) === outcome) && pretty(record).toLowerCase().includes(query));
  const rows = byId("record-rows");
  rows.replaceChildren();
  for (const record of filtered.slice(0, 200)) {
    const row = document.createElement("tr");
    const sourceCell = document.createElement("td");
    const source = document.createElement("span");
    source.className = "record-source";
    source.textContent = typeof record?.source === "string" ? record.source : "Source not recorded";
    const subject = document.createElement("span");
    subject.className = "record-subject";
    subject.textContent = Array.isArray(record?.subjects) ? record.subjects.map((item) => typeof item?.name === "string" ? item.name : "Unnamed subject").join(", ") : "No subject extracted";
    sourceCell.append(source, subject);
    const outcomeCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `outcome ${storedOutcome(record)}`;
    badge.textContent = storedOutcome(record);
    outcomeCell.append(badge);
    const hash = document.createElement("td");
    hash.className = "digest";
    hash.textContent = typeof record?.recordHash === "string" ? `${record.recordHash.slice(0, 14)}…` : "Not recorded";
    const detailCell = document.createElement("td");
    const detail = document.createElement("button");
    detail.type = "button";
    detail.className = "record-details";
    detail.textContent = "Inspect ↗";
    detail.addEventListener("click", () => { setText("record-json", pretty(record)); byId("record-dialog").showModal(); });
    detailCell.append(detail);
    row.append(sourceCell, outcomeCell, hash, detailCell);
    rows.append(row);
  }
  byId("empty-state").hidden = filtered.length > 0;
  if (!ledgerAvailable) {
    setText("empty-title", "Ledger unavailable");
    setText("empty-description", "No evidence summary is available until the service can load the ledger. Check the error above.");
  } else if (records.length === 0) {
    setText("empty-title", "No evidence has been ingested");
    setText("empty-description", "The loaded ledger contains zero records. Import actual attestations with the ledger builder to begin inspection. No sample evidence has been inserted.");
  } else {
    setText("empty-title", "No matching records");
    setText("empty-description", "Try a different search or stored policy outcome.");
  }
  setText("record-summary", `${Math.min(filtered.length, 200)} of ${records.length} records displayed${filtered.length > 200 ? " · refine the search to see more" : ""}`);
}

async function refreshLedger() {
  byId("refresh").disabled = true;
  byId("load-error").hidden = true;
  const [status, ledger] = await Promise.allSettled([request("status"), request("ledger")]);
  setText("service-state", status.status === "fulfilled" ? "HTTP service connected" : "Service unavailable");
  byId("service-state").classList.toggle("connected", status.status === "fulfilled");
  if (ledger.status === "fulfilled") {
    const value = ledger.value;
    records = Array.isArray(value.records) ? value.records : [];
    ledgerAvailable = true;
    const integrity = value.chainIntegrity;
    const valid = integrity?.valid === true;
    setText("record-count", String(records.length));
    const counts = { ALLOW: 0, REVIEW: 0, BLOCK: 0, UNKNOWN: 0 };
    records.forEach((record) => { counts[storedOutcome(record)] += 1; });
    setText("record-hint", `${counts.BLOCK} BLOCK · ${counts.REVIEW} REVIEW · ${counts.ALLOW} ALLOW (stored)`);
    setText("chain-status", valid ? (records.length ? "Consistent" : "Empty") : "Inconsistent");
    byId("chain-status").className = `word-metric ${valid && records.length ? "good" : valid ? "" : "bad"}`;
    setText("chain-hint", valid ? "Internal consistency only; unanchored" : "Stored ledger failed validation");
    setText("chain-root", value.chainRoot || "No root — no records");
    setText("generated-at", dateLabel(value.generatedAt));
    setText("ledger-age", `Snapshot: ${dateLabel(value.generatedAt)}`);
    setText("loaded-at", new Date().toLocaleString());
    setText("ledger-disclosure", typeof value.disclosure === "string" ? value.disclosure : "No disclosure is recorded in this ledger.");
    const errors = Array.isArray(integrity?.errors) ? integrity.errors : [];
    byId("integrity-errors").hidden = valid;
    setText("integrity-errors", errors.length ? errors.join("; ") : "Chain validation was not established.");
  } else {
    records = [];
    ledgerAvailable = false;
    byId("load-error").hidden = false;
    setText("load-error", `Ledger could not be loaded. ${ledger.reason.message}`);
    setText("record-count", "—");
    setText("record-hint", "Evidence unavailable");
    setText("chain-status", "Unavailable");
    byId("chain-status").className = "word-metric bad";
    setText("chain-hint", "No chain inspected");
    for (const id of ["chain-root", "generated-at", "loaded-at"]) setText(id, "—");
    setText("ledger-age", "No snapshot loaded");
    setText("ledger-disclosure", "");
    byId("integrity-errors").hidden = true;
  }
  renderRecords();
  byId("refresh").disabled = false;
}

const sampleStatement = {
  _type: "https://in-toto.io/Statement/v1",
  subject: [{ name: "SAMPLE-artifact.tar.gz", digest: { sha256: "a".repeat(64) } }],
  predicateType: "https://slsa.dev/provenance/v1",
  predicate: { buildDefinition: { buildType: "https://github.com/actions/attest-build-provenance" }, runDetails: { builder: { id: "https://github.com/szl-holdings/a11oy/.github/workflows/anatomy-ledger.yml" } } },
};
const sampleIntent = {
  principal: { type: "A11oy::WorkloadIdentity", id: "agent:sample-reader", attrs: { kind: "agent", tenantId: "szl", assurance: 3, disabled: false, roles: ["reader"] } },
  action: { type: "A11oy::Action", id: "ReadResource" },
  resource: { type: "A11oy::ProtectedResource", id: "ledger:anatomy", attrs: { kind: "ledger", tenantId: "szl", classification: 2, requiredAssurance: 1, maxRisk: 400, allowedPurposes: ["inspect-evidence"], allowedEffects: ["read"], requiresApproval: false } },
  context: { requestId: "sample-inspection", sessionId: "sample", purpose: "inspect-evidence", intendedEffect: "read", riskScore: 10, humanApproval: false, mfa: false, networkZone: "command-surface", evidenceDigest: "", traceId: "sample-trace", timestamp: "" },
};

byId("refresh").addEventListener("click", refreshLedger);
byId("record-search").addEventListener("input", renderRecords);
byId("outcome-filter").addEventListener("change", renderRecords);
byId("close-dialog").addEventListener("click", () => byId("record-dialog").close());
byId("load-sample").addEventListener("click", () => {
  const mode = byId("evaluation-mode").value;
  const input = mode === "authorize" ? sampleIntent : mode === "evaluate" ? { statement: sampleStatement, verification: { verified: true } } : { command: sampleIntent, statement: sampleStatement, verification: { verified: true } };
  byId("policy-input").value = pretty(input);
  setText("evaluation-status", "SAMPLE LOADED");
  setText("evaluation-result", "SAMPLE input loaded. The claimed verification flag is deliberately untrusted. Submit to see how the service handles it.");
});
byId("evaluation-mode").addEventListener("change", () => {
  setText("evaluation-status", "NOT RUN");
  setText("evaluation-result", "Evaluation mode changed. Review or replace the input before submitting.");
});
byId("policy-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("evaluate-button");
  button.disabled = true;
  setText("evaluation-status", "RUNNING");
  try {
    const raw = byId("policy-input").value;
    if (new TextEncoder().encode(raw).length > 256 * 1024) throw new Error("Input exceeds the 256 KiB request limit.");
    const input = JSON.parse(raw);
    if (input === null || Array.isArray(input) || typeof input !== "object") throw new Error("Input must be a JSON object.");
    const value = await request(byId("evaluation-mode").value, { method: "POST", headers: { "Content-Type": "application/json" }, body: raw });
    setText("evaluation-result", pretty(value));
    setText("evaluation-status", value.outcome || (value.executable === false ? "NO EXECUTION" : "RESPONSE"));
  } catch (error) { setText("evaluation-result", error.message); setText("evaluation-status", "ERROR"); }
  finally { button.disabled = false; }
});
byId("run-checks").addEventListener("click", async () => {
  const button = byId("run-checks");
  button.disabled = true;
  setText("checks-result", "Running synthetic software checks…");
  byId("checks-details").hidden = true;
  try {
    const result = await request("prove");
    setText("checks-result", `${result.passed} passed · ${result.failed} failed · synthetic software QA`);
    setText("checks-json", pretty(result));
    byId("checks-details").hidden = false;
  } catch (error) { setText("checks-result", `Checks unavailable. ${error.message}`); }
  finally { button.disabled = false; }
});
refreshLedger();

// Decision lab: transport the original JSON bytes; never round-trip request numbers.
let latestCapsule = null;
let uploadedCapsule = null;
let labRevision = 0;
let replayRevision = 0;
function labJson(raw, limit) {
  if (new TextEncoder().encode(raw).length > limit) throw new Error(`JSON exceeds the ${limit / 1024} KiB limit.`);
  const tokens = raw.match(/"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g) || [];
  for (const token of tokens) {
    if (token.startsWith('"')) continue;
    const number = Number(token);
    if (!Number.isFinite(number) || Math.abs(number) > Number.MAX_SAFE_INTEGER) {
      throw new Error("This browser view cannot represent that numeric value exactly. Use the API or CLI for full 64-bit integers; the input has not been rounded or submitted.");
    }
  }
  const parsed = JSON.parse(raw);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("A JSON object is required.");
  return parsed;
}
async function labRequest(route, raw) {
  labJson(raw, route === "analyze" ? 128 * 1024 : 192 * 1024);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${API}/${route}`, { method: "POST", body: raw, headers: { "Content-Type": "application/json" }, cache: "no-store", signal: controller.signal });
    const text = await response.text();
    const data = labJson(text, 1024 * 1024);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${data.error || "Inspection failed"}`);
    return { data, text };
  } finally { clearTimeout(timer); }
}
function labElement(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}
function labClear() {
  labRevision += 1;
  replayRevision += 1;
  latestCapsule = null;
  byId("lab-download").disabled = true;
  byId("lab-replay-latest").disabled = true;
  byId("lab-summary").hidden = true;
  byId("lab-comparison").hidden = true;
  byId("lab-placeholder").hidden = false;
  byId("lab-error").hidden = true;
  byId("lab-replay-report").hidden = true;
}
function labError(error) {
  setText("lab-status", "INPUT / SERVICE ERROR");
  setText("lab-error", error.name === "AbortError" ? "The local service did not respond within 10 seconds." : error.message);
  byId("lab-error").hidden = false;
}
function showScenario(row, title) {
  setText("scenario-dialog-title", title);
  setText("scenario-dialog-summary", `Intent: ${row.intentOutcome}. Combined: ${row.combinedOutcome}. Execution remains disabled.`);
  const changes = byId("scenario-changes");
  changes.replaceChildren();
  for (const change of row.changes || []) {
    changes.append(labElement("p", `${change.path}: ${pretty(change.before)} → ${pretty(change.after)} (${change.kind})`, "digest"));
  }
  if (!changes.childNodes.length) changes.append(labElement("p", "Original input; no changed fields."));
  const trace = byId("scenario-trace");
  trace.replaceChildren();
  for (const item of row.trace || []) {
    const li = labElement("li", "");
    li.append(labElement("strong", `${item.stage} · ${item.code}`), labElement("p", item.detail), labElement("small", `${item.source} · ${item.evaluator}`));
    trace.append(li);
  }
  setText("scenario-json", pretty(row));
  byId("scenario-dialog").showModal();
}
function renderAnalysis(data, rawText) {
  if (data.executable !== false || data.evaluationOnly !== true || typeof data.replayCapsuleJson !== "string") throw new Error("Unexpected advisory response contract.");
  labJson(data.replayCapsuleJson, 192 * 1024);
  latestCapsule = data.replayCapsuleJson;
  setText("lab-status", "ANALYSIS COMPLETE");
  setText("lab-base-intent", data.base.intentOutcome);
  setText("lab-base-combined", data.base.combinedOutcome);
  setText("lab-scenario-count", String(data.scenarios.length));
  setText("lab-result-context", "Intent ALLOW describes supplied policy attributes. Unverified evidence remains a separate constraint. Every result is advisory.");
  setText("lab-input-digest", data.inputDigest);
  setText("lab-policy-digest", data.policy.digest);
  const files = byId("lab-policy-files");
  files.replaceChildren();
  for (const [name, hash] of Object.entries(data.policy.files)) {
    const group = document.createElement("div");
    group.append(labElement("dt", `${name} · ${data.policy.executedPython.includes(name) ? "executed Python" : "reference only"}`), labElement("dd", hash, "digest"));
    files.append(group);
  }
  const rows = byId("lab-scenario-rows");
  rows.replaceChildren();
  for (const [index, row] of [data.base, ...data.scenarios].entries()) {
    const title = index === 0 ? "Original request" : row.label;
    const tr = document.createElement("tr");
    tr.append(labElement("td", title));
    for (const outcome of [row.intentOutcome, row.combinedOutcome]) {
      const cell = document.createElement("td");
      cell.append(labElement("span", outcome, `outcome ${["BLOCK", "REVIEW", "ALLOW"].includes(outcome) ? outcome : "UNKNOWN"}`));
      tr.append(cell);
    }
    tr.append(labElement("td", (row.changes || []).map(change => `${change.path}: ${JSON.stringify(change.before)} → ${JSON.stringify(change.after)}`).join("; ") || "No changes", "digest"));
    const cell = document.createElement("td");
    const button = labElement("button", "Explain", "record-details");
    button.type = "button";
    button.setAttribute("aria-label", `Explain ${title}`);
    button.addEventListener("click", () => showScenario(row, title));
    cell.append(button); tr.append(cell); rows.append(tr);
  }
  setText("lab-disclosure", data.disclosure);
  setText("lab-analysis-json", rawText);
  byId("lab-placeholder").hidden = true;
  byId("lab-summary").hidden = false;
  byId("lab-comparison").hidden = false;
  byId("lab-download").disabled = false;
  byId("lab-replay-latest").disabled = false;
}
byId("close-scenario-dialog").addEventListener("click", () => byId("scenario-dialog").close());
byId("lab-input").addEventListener("input", () => { labClear(); setText("lab-status", "INPUT CHANGED"); });
byId("lab-use-inspector").addEventListener("click", () => { labClear(); byId("lab-input").value = byId("policy-input").value; setText("lab-status", "INPUT COPIED"); });
byId("lab-load-sample").addEventListener("click", async () => {
  labClear();
  const revision = labRevision;
  try {
    const command = structuredClone(sampleIntent);
    command.action.id = "DeployArtifact";
    command.principal.id = "agent:SAMPLE-operator";
    command.resource.id = "deployment:SAMPLE-only";
    command.resource.attrs.kind = "deployment";
    command.resource.attrs.allowedPurposes = ["sample-release-inspection"];
    command.resource.attrs.allowedEffects = ["deploy"];
    command.resource.attrs.requiresApproval = true;
    command.context.purpose = "sample-release-inspection";
    command.context.intendedEffect = "deploy";
    command.context.mfa = true;
    command.context.riskScore = 250;
    const canonical = value => value && typeof value === "object" ? (Array.isArray(value) ? value.map(canonical) : Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]))) : value;
    const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(canonical(sampleStatement))));
    if (revision !== labRevision) return;
    command.context.evidenceDigest = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
    byId("lab-input").value = pretty({ command, statement: sampleStatement, verification: { verified: true } });
    setText("lab-status", "SAMPLE LOADED");
  } catch (error) { if (revision === labRevision) labError(error); }
});
byId("lab-form").addEventListener("submit", async event => {
  event.preventDefault(); labClear();
  const revision = labRevision;
  const button = byId("lab-analyze"); button.disabled = true;
  setText("lab-status", "ANALYZING");
  try {
    const raw = byId("lab-input").value;
    const value = labJson(raw, 128 * 1024);
    const body = Object.hasOwn(value, "command") ? raw : `{"command":${raw}}`;
    const result = await labRequest("analyze", body);
    if (revision === labRevision) renderAnalysis(result.data, result.text);
  } catch (error) { if (revision === labRevision) labError(error); }
  finally { button.disabled = false; }
});
byId("lab-download").addEventListener("click", () => {
  if (!latestCapsule) return;
  const url = URL.createObjectURL(new Blob([latestCapsule], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "anatomy-unsigned-replay.json";
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
byId("lab-capsule-file").addEventListener("change", async event => {
  replayRevision += 1;
  const revision = replayRevision;
  byId("lab-replay-report").hidden = true;
  uploadedCapsule = null; byId("lab-replay-file").disabled = true;
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 192 * 1024) throw new Error("Capsule exceeds 192 KiB.");
    const raw = await file.text();
    if (revision !== replayRevision) return;
    labJson(raw, 192 * 1024);
    uploadedCapsule = raw;
    byId("lab-replay-file").disabled = false;
    setText("lab-file-status", `${file.name} · loaded locally. Replay submits it to this service.`);
  } catch (error) { if (revision === replayRevision) setText("lab-file-status", error.message); }
});
async function replayLab(raw, button) {
  if (!raw) return;
  const revision = ++replayRevision;
  button.disabled = true;
  byId("lab-replay-report").hidden = true;
  try {
    const { data, text } = await labRequest("replay", raw);
    if (revision !== replayRevision) return;
    if (data.executable !== false || data.authentic !== false) throw new Error("Unexpected replay trust boundary.");
    setText("lab-replay-status", data.valid ? "REPRODUCIBLE · UNSIGNED" : "REPLAY DIFFERENCES DETECTED");
    setText("lab-replay-message", data.valid ? "Inputs, policy, and computed result match. Authorship and authenticity remain unestablished." : "The capsule did not reproduce exactly. Inspect the differences below.");
    const issues = byId("lab-replay-issues"); issues.replaceChildren();
    for (const item of data.issues) issues.append(labElement("li", `${item.code}: ${item.detail}`));
    const matches = byId("lab-replay-digests"); matches.replaceChildren();
    for (const key of ["inputMatch", "policyMatch", "resultMatch"]) {
      const group = document.createElement("div");
      group.append(labElement("dt", key), labElement("dd", data[key] === true ? "Match" : data[key] === false ? "Mismatch" : "Not evaluated")); matches.append(group);
    }
    setText("lab-replay-json", text); byId("lab-replay-report").hidden = false;
  } catch (error) { if (revision === replayRevision) labError(error); }
  finally { button.disabled = button.id === "lab-replay-latest" ? !latestCapsule : !uploadedCapsule; }
}
byId("lab-replay-latest").addEventListener("click", event => replayLab(latestCapsule, event.currentTarget));
byId("lab-replay-file").addEventListener("click", event => replayLab(uploadedCapsule, event.currentTarget));
