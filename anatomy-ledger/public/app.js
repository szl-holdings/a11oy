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
