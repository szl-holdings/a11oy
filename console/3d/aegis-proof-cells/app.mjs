const ALLOWED_MISSIONS = new Set([
  "alert-triage",
  "phishing",
  "endpoint",
  "vulnerability",
  "cloud",
  "threat-intel",
]);

const PROHIBITED_TOKENS = [
  "exploit",
  "exfiltrate",
  "credential theft",
  "steal credential",
  "dump credential",
  "deploy malware",
  "ransomware",
  "disable security",
  "evade detection",
  "persistence",
  "lateral movement",
  "destructive",
];

const APPROVAL_ACTIONS = new Set([
  "block-indicator",
  "isolate-host",
  "disable-account",
  "purge-email",
  "remediate",
]);

export function canonicalJSONString(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJSONString).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalJSONString(value[key])}`).join(",")}}`;
}

export async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizedBoolean(value) {
  if (typeof value === "boolean") return value;
  return ["1", "true", "yes", "on"].includes(normalizeText(value).toLowerCase());
}

function capsuleFor(registry, mission) {
  return registry.procedure_capsules.find((item) => item.mission === mission) ?? null;
}

function prohibitedAction(action) {
  const normalized = normalizeText(action).toLowerCase();
  return PROHIBITED_TOKENS.some((token) => normalized.includes(token));
}

export function evaluateCase(input, registry) {
  const tenantId = normalizeText(input.tenant_id);
  const passportTenantId = normalizeText(input.passport_tenant_id);
  const mission = normalizeText(input.mission).toLowerCase();
  const requestedAction = normalizeText(input.requested_action).toLowerCase() || "investigate";
  const alertId = normalizeText(input.alert_id) || "UNAVAILABLE";
  const source = normalizeText(input.source) || "UNAVAILABLE";
  const severity = normalizeText(input.severity).toUpperCase() || "UNAVAILABLE";
  const evidenceCount = Number.parseInt(String(input.evidence_count ?? "0"), 10);
  const evidenceFresh = normalizedBoolean(input.evidence_fresh);
  const humanApproved = normalizedBoolean(input.human_approved);
  const capsule = capsuleFor(registry, mission);

  let state = "SANDBOX_PLAN";
  let reason = "DEFENSIVE_PLAN_READY";

  if (!tenantId || !passportTenantId) {
    state = "DENIED";
    reason = "TENANT_PASSPORT_REQUIRED";
  } else if (tenantId !== passportTenantId) {
    state = "DENIED";
    reason = "CROSS_TENANT_SCOPE";
  } else if (!ALLOWED_MISSIONS.has(mission) || capsule === null) {
    state = "DENIED";
    reason = "UNSUPPORTED_DEFENSIVE_MISSION";
  } else if (prohibitedAction(requestedAction)) {
    state = "DENIED";
    reason = "PROHIBITED_ACTION";
  } else if (!Number.isFinite(evidenceCount) || evidenceCount <= 0 || !evidenceFresh) {
    state = "ABSTAINED";
    reason = "EVIDENCE_NOT_FRESH";
  } else if (APPROVAL_ACTIONS.has(requestedAction) && !humanApproved) {
    state = "AWAITING_APPROVAL";
    reason = "HUMAN_APPROVAL_REQUIRED";
  }

  const decisionGate = state === "DENIED" || state === "ABSTAINED" ? 0 : 1;
  const evidenceScore = Math.max(0, Math.min(1, Number.isFinite(evidenceCount) ? evidenceCount / 5 : 0));
  const freshnessScore = evidenceFresh ? 1 : 0;
  const scopeScore = tenantId && tenantId === passportTenantId ? 1 : 0;
  const procedureScore = capsule ? 1 : 0;
  const quality = Math.pow(
    Math.max(evidenceScore, 0.000001) ** 0.30
      * Math.max(freshnessScore, 0.000001) ** 0.25
      * Math.max(scopeScore, 0.000001) ** 0.25
      * Math.max(procedureScore, 0.000001) ** 0.20,
    1,
  );
  const modeledScore = Math.min(0.97, quality * decisionGate);

  const plan = capsule
    ? capsule.cells.map((cellId, index) => {
        const cell = registry.proof_cells.find((item) => item.id === cellId);
        return {
          sequence: index + 1,
          cell_id: cellId,
          cell_name: cell?.name ?? cellId,
          objective: cell?.purpose ?? "UNAVAILABLE",
          mode: "READ_ONLY_DEFENSIVE",
        };
      })
    : [];

  const derivation = {
    schema: "szl.aegis-proof-cells.evaluation/v1",
    input: {
      tenant_id: tenantId || "UNAVAILABLE",
      passport_tenant_id: passportTenantId || "UNAVAILABLE",
      alert_id: alertId,
      source,
      severity,
      mission: mission || "UNAVAILABLE",
      requested_action: requestedAction,
      evidence_count: Number.isFinite(evidenceCount) ? evidenceCount : 0,
      evidence_fresh: evidenceFresh,
      human_approved: humanApproved,
    },
    decision: {
      state,
      reason,
      evidence_class: "MODELED",
      score: Number(modeledScore.toFixed(8)),
      trust_ceiling: 0.97,
      production_authorization: false,
    },
    procedure_capsule: capsule?.id ?? "UNAVAILABLE",
    plan,
    context_contract: registry.context_types,
    authority: {
      default_effect: "DENY",
      external_writes: "DISABLED",
      effectors: [],
      automatic_retries: 0,
      credentials_accepted: false,
      cross_tenant_access: "DENIED",
      offensive_intrusion: "DENIED",
    },
  };

  return derivation;
}

export async function evaluateCaseWithReceipt(input, registry) {
  const result = evaluateCase(input, registry);
  return {
    ...result,
    proof_chain: {
      kind: "DETERMINISTIC_CLIENT_RECEIPT",
      sha256: await sha256Hex(canonicalJSONString(result)),
      signature_status: "UNAVAILABLE",
      persisted: false,
    },
  };
}

function text(element, value) {
  if (element) element.textContent = value;
}

function renderCells(registry) {
  const grid = document.querySelector("#cells");
  if (!grid) return;
  grid.replaceChildren();
  for (const cell of registry.proof_cells) {
    const article = document.createElement("article");
    article.className = "cell";
    const label = document.createElement("div");
    label.className = "cell-id";
    label.textContent = cell.id;
    const heading = document.createElement("h3");
    heading.textContent = cell.name;
    const paragraph = document.createElement("p");
    paragraph.textContent = cell.purpose;
    article.append(label, heading, paragraph);
    grid.append(article);
  }
}

async function readJson(path) {
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`${path} -> HTTP ${response.status}`);
  return response.json();
}

async function refreshEvidence(registry) {
  const output = document.querySelector("#evidence-output");
  const summary = [];
  for (const source of registry.live_read_only_sources) {
    try {
      const payload = await readJson(source.path);
      summary.push({
        id: source.id,
        state: "AVAILABLE",
        path: source.path,
        observed_at: payload.observed_at ?? "UNAVAILABLE",
        data_kind: payload.data_kind ?? payload.status ?? "REPORTED",
      });
    } catch (error) {
      summary.push({
        id: source.id,
        state: "UNAVAILABLE",
        path: source.path,
        reason: error instanceof Error ? error.message : String(error),
      });
    }
  }
  if (output) output.textContent = JSON.stringify(summary, null, 2);
  text(document.querySelector("#evidence-state"), `${summary.filter((row) => row.state === "AVAILABLE").length}/${summary.length} sources available`);
}

function readForm(form) {
  const data = new FormData(form);
  return Object.fromEntries(data.entries());
}

async function boot() {
  const registry = await readJson("/static/3d/aegis-proof-cells/registry.json");
  text(document.querySelector("#cell-count"), String(registry.proof_cells.length));
  text(document.querySelector("#capsule-count"), String(registry.procedure_capsules.length));
  text(document.querySelector("#mode"), registry.operating_mode);
  renderCells(registry);

  const form = document.querySelector("#case-form");
  const result = document.querySelector("#case-result");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const evaluated = await evaluateCaseWithReceipt(readForm(form), registry);
    if (result) result.textContent = JSON.stringify(evaluated, null, 2);
    text(document.querySelector("#decision-state"), evaluated.decision.state);
  });

  document.querySelector("#refresh-evidence")?.addEventListener("click", () => refreshEvidence(registry));
  await refreshEvidence(registry);
}

if (typeof document !== "undefined") {
  boot().catch((error) => {
    text(document.querySelector("#boot-state"), `UNAVAILABLE: ${error instanceof Error ? error.message : String(error)}`);
  });
}
