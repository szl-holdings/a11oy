const sessionId = sessionStorage.getItem("szl-immune-session") || crypto.randomUUID();
sessionStorage.setItem("szl-immune-session", sessionId);
const byId = (id) => document.getElementById(id);
const short = (value, length = 18) => value ? `${String(value).slice(0, length)}${String(value).length > length ? "…" : ""}` : "UNREPORTED";
const requestHeaders = { "content-type": "application/json", "x-immune-session": sessionId };

function setText(id, value) { byId(id).textContent = value ?? "—"; }
function renderItems(id, items, shape) {
  const list = byId(id);
  list.replaceChildren();
  if (!items?.length) {
    const item = document.createElement("li");
    item.className = "empty";
    item.textContent = "No findings.";
    list.append(item);
    return;
  }
  for (const value of items) {
    const item = document.createElement("li");
    const rendered = shape(value);
    item.textContent = rendered.text;
    for (const [key, data] of Object.entries(rendered.data ?? {})) item.dataset[key] = data;
    list.append(item);
  }
}

function renderClassifier(classifier) {
  setText("adaptive-state", classifier.state);
  setText("adaptive-model", classifier.modelId);
  setText("adaptive-revision", classifier.revision);
  setText("adaptive-weights", classifier.weightsSha256);
  setText("adaptive-runtime", [classifier.runtime, classifier.device].filter(Boolean).join(" / ") || "UNREPORTED");
  setText("adaptive-result", classifier.evaluated ? `${classifier.label} / ${classifier.score}` : "NOT EVALUATED");
  renderItems("adaptive-reasons", classifier.reasons, (reason) => ({ text: reason }));
}

function renderDecision(data) {
  renderItems("findings", data.findings, (item) => ({ text: `${item.code} — ${item.detail}`, data: { severity: item.severity } }));
  renderItems("tripwires", data.tripwires, (item) => ({ text: `${item.id} · ${item.implementationStatus} · ${item.evaluationState} — ${item.evidence.join("; ")}`, data: { state: item.evaluationState } }));
  renderClassifier(data.classifier);
  const verdict = byId("verdict");
  verdict.className = `verdict verdict-${data.decision.toLowerCase()}`;
  verdict.querySelector("strong").textContent = data.decision;
  verdict.querySelector("small").textContent = data.reasons.join(" · ");
  setText("receipt-state", data.receipt.state);
  setText("receipt-id", data.receipt.receiptId);
  setText("receipt-chain", data.receipt.chain ? `sequence ${data.receipt.chain.sequence} · previous ${short(data.receipt.chain.previousEnvelopeSha256)}` : data.receipt.reason);
  if (data.receipt.receiptId) byId("receipt-query").value = data.receipt.receiptId;
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...requestHeaders, ...(options.headers ?? {}) } });
  const body = await response.json();
  if (!response.ok) throw new Error(`${body.error}: ${body.message}`);
  return body;
}

async function loadStatus() {
  const [status, session, tripwires] = await Promise.all([
    api("/api/immune/v1/status"),
    api("/api/immune/v1/session/state"),
    api("/api/immune/v1/tripwires"),
  ]);
  const operational = status.service.state === "READY";
  const overall = byId("overall-state");
  overall.textContent = operational ? "INSPECT READY" : status.service.state;
  overall.className = `state ${operational ? "state-ready" : "state-warn"}`;
  setText("policy-state", status.policy.state);
  setText("policy-hash", short(status.policy.sha256, 24));
  setText("classifier-state", status.classifier.state);
  setText("classifier-pin", status.classifier.revision ? `${short(status.classifier.revision)} / ${short(status.classifier.weightsSha256)}` : "immutable pin absent");
  setText("signer-state", status.signer.state);
  setText("signer-id", status.signer.keyid || status.signer.reason);
  setText("tool-state", status.capabilities.toolAuthorization);
  renderClassifier(status.classifier);
  byId("strict-mode").checked = session.strictMode;
  setText("session-count", `${session.requestCount} requests`);
  renderItems("tripwires", tripwires.tripwires, (item) => ({ text: `${item.id} · ${item.implementationStatus} · ${item.evaluationState}`, data: { state: item.evaluationState } }));
}

document.querySelectorAll('input[name="mode"]').forEach((input) => input.addEventListener("change", () => {
  byId("tool-fields").hidden = document.querySelector('input[name="mode"]:checked').value !== "tool";
}));

byId("strict-mode").addEventListener("change", async (event) => {
  try {
    const session = await api("/api/immune/v1/session/state", { method: "POST", body: JSON.stringify({ strictMode: event.target.checked }) });
    setText("session-count", `${session.requestCount} requests`);
  } catch (error) {
    event.target.checked = !event.target.checked;
    alert(error.message);
  }
});

byId("inspect-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("run-button");
  button.disabled = true;
  const mode = document.querySelector('input[name="mode"]:checked').value;
  try {
    const body = {
      content: byId("content").value,
      source: { kind: byId("source-kind").value, trust: byId("source-trust").value },
      actor: { id: byId("actor-id").value || undefined, role: byId("actor-role").value || undefined, scopes: [] },
    };
    if (mode === "tool") {
      const capability = byId("tool-capability").value;
      body.actor.scopes = capability ? [capability] : [];
      body.tool = { name: byId("tool-name").value, capability, arguments: JSON.parse(byId("tool-arguments").value || "{}") };
    }
    renderDecision(await api(`/api/immune/v1/${mode === "tool" ? "tool-authorize" : "inspect"}`, { method: "POST", body: JSON.stringify(body) }));
    const session = await api("/api/immune/v1/session/state");
    setText("session-count", `${session.requestCount} requests`);
  } catch (error) {
    const verdict = byId("verdict");
    verdict.className = "verdict verdict-unavailable";
    verdict.querySelector("strong").textContent = "REQUEST FAILED";
    verdict.querySelector("small").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

byId("receipt-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const receipt = await api(`/api/immune/v1/receipts/${byId("receipt-query").value}`);
    byId("receipt-output").textContent = JSON.stringify(receipt, null, 2);
  } catch (error) {
    byId("receipt-output").textContent = error.message;
  }
});

loadStatus().catch((error) => {
  const overall = byId("overall-state");
  overall.textContent = "UNAVAILABLE";
  overall.className = "state state-warn";
  byId("receipt-output").textContent = error.message;
});
