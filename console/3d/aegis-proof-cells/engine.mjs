// SPDX-License-Identifier: Apache-2.0
// Aegis Proof Cells — deterministic, defensive-only browser engine.

export const INPUT_SCHEMA = 'szl.aegis-proof-cells.case-input/v1';
export const RESULT_SCHEMA = 'szl.aegis-proof-cells.analysis/v1';
export const ENGINE_VERSION = '1.0.0';

const SECRET_KEY = /(password|passphrase|secret|token|api[_-]?key|credential|private[_-]?key|session[_-]?id)/i;
const SAFE_FRESHNESS = new Set(['LIVE', 'CACHED', 'STALE', 'UNAVAILABLE']);
const MAX_EVIDENCE = 200;
const MAX_TEXT = 4096;

function scalarText(value, name, { required = true, max = MAX_TEXT } = {}) {
  if (value === null || value === undefined) {
    if (required) throw new TypeError(`${name} is required`);
    return '';
  }
  if (typeof value !== 'string') throw new TypeError(`${name} must be a string`);
  const normalized = value.trim();
  if (required && !normalized) throw new TypeError(`${name} is required`);
  if (normalized.length > max) throw new RangeError(`${name} exceeds ${max} characters`);
  return normalized;
}

function boundedBoolean(value, name) {
  if (typeof value !== 'boolean') throw new TypeError(`${name} must be boolean`);
  return value;
}

function safetyGate(value) {
  if (value !== 0 && value !== 1) throw new TypeError('safety_gate must be 0 or 1');
  return value;
}

function confidence(value) {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new TypeError('evidence confidence must be a number between 0 and 1');
  }
  return Math.round(value * 10000) / 10000;
}

function scanSecretKeys(value, path = '$', findings = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanSecretKeys(item, `${path}[${index}]`, findings));
    return findings;
  }
  if (!value || typeof value !== 'object') return findings;
  for (const [key, child] of Object.entries(value)) {
    const next = `${path}.${key}`;
    if (SECRET_KEY.test(key)) findings.push(next);
    scanSecretKeys(child, next, findings);
  }
  return findings;
}

function normalizeEvidence(items) {
  if (!Array.isArray(items)) throw new TypeError('evidence must be an array');
  if (items.length > MAX_EVIDENCE) throw new RangeError(`evidence exceeds ${MAX_EVIDENCE} items`);
  return items.map((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new TypeError(`evidence[${index}] must be an object`);
    }
    const freshness = scalarText(item.freshness, `evidence[${index}].freshness`, { max: 32 }).toUpperCase();
    if (!SAFE_FRESHNESS.has(freshness)) {
      throw new TypeError(`evidence[${index}].freshness must be LIVE, CACHED, STALE, or UNAVAILABLE`);
    }
    return {
      id: scalarText(item.id, `evidence[${index}].id`, { max: 128 }),
      kind: scalarText(item.kind, `evidence[${index}].kind`, { max: 128 }),
      source: scalarText(item.source, `evidence[${index}].source`, { max: 256 }),
      freshness,
      observed_at: scalarText(item.observed_at, `evidence[${index}].observed_at`, { required: false, max: 64 }) || null,
      asset: scalarText(item.asset, `evidence[${index}].asset`, { required: false, max: 256 }) || null,
      principal: scalarText(item.principal, `evidence[${index}].principal`, { required: false, max: 256 }) || null,
      summary: scalarText(item.summary, `evidence[${index}].summary`, { max: MAX_TEXT }),
      confidence: confidence(item.confidence),
    };
  });
}

export function normalizeCaseInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new TypeError('case input must be a JSON object');
  }
  const secretFields = scanSecretKeys(input);
  return {
    schema: scalarText(input.schema || INPUT_SCHEMA, 'schema', { max: 128 }),
    tenant: scalarText(input.tenant, 'tenant', { max: 128 }),
    authorized_tenant: scalarText(input.authorized_tenant, 'authorized_tenant', { max: 128 }),
    principal: scalarText(input.principal, 'principal', { max: 256 }),
    purpose: scalarText(input.purpose, 'purpose', { max: 512 }),
    mission: scalarText(input.mission, 'mission', { max: 128 }).toLowerCase(),
    action: scalarText(input.action, 'action', { max: 128 }).toLowerCase(),
    human_approval: boundedBoolean(input.human_approval, 'human_approval'),
    safety_gate: safetyGate(input.safety_gate),
    evidence: normalizeEvidence(input.evidence),
    secret_fields_detected: secretFields,
  };
}

export function canonicalize(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
}

export async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(typeof value === 'string' ? value : canonicalize(value));
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function registrySets(registry) {
  if (!registry || registry.schema !== 'szl.aegis-proof-cells.registry/v1') {
    throw new TypeError('registry contract is unavailable or invalid');
  }
  if (registry.authority?.external_writes !== 'DISABLED' || (registry.authority?.effectors || []).length !== 0) {
    throw new TypeError('registry attempted to bind external authority');
  }
  return {
    allowed: new Set(registry.allowed_missions || []),
    gated: new Set(registry.approval_gated_actions || []),
    prohibited: new Set(registry.prohibited_actions || []),
  };
}

function decide(input, sets) {
  if (input.secret_fields_detected.length) {
    return { state: 'DENIED', reason: 'SECRET_FIELD_REJECTED' };
  }
  if (input.tenant !== input.authorized_tenant) {
    return { state: 'DENIED', reason: 'CROSS_TENANT_SCOPE' };
  }
  if (sets.prohibited.has(input.action)) {
    return { state: 'DENIED', reason: 'PROHIBITED_ACTION' };
  }
  if (!sets.allowed.has(input.mission)) {
    return { state: 'DENIED', reason: 'MISSION_NOT_ADMITTED' };
  }
  if (input.safety_gate !== 1) {
    return { state: 'DENIED', reason: 'SAFETY_GATE_FAILED' };
  }
  if (!input.evidence.length) {
    return { state: 'ABSTAINED', reason: 'EVIDENCE_REQUIRED' };
  }
  if (input.evidence.some((item) => item.freshness === 'STALE' || item.freshness === 'UNAVAILABLE')) {
    return { state: 'ABSTAINED', reason: 'EVIDENCE_NOT_FRESH' };
  }
  if (sets.gated.has(input.action) && input.human_approval !== true) {
    return { state: 'AWAITING_APPROVAL', reason: 'HUMAN_APPROVAL_REQUIRED' };
  }
  return { state: 'SANDBOX_READY', reason: 'DEFENSIVE_ANALYSIS_ADMITTED' };
}

function modeledScore(input, decision, ceiling) {
  if (decision.state !== 'SANDBOX_READY') return 0;
  const confidences = input.evidence.map((item) => item.confidence).filter((item) => item !== null);
  const confidenceMean = confidences.length
    ? confidences.reduce((sum, item) => sum + item, 0) / confidences.length
    : 0.5;
  const liveRatio = input.evidence.filter((item) => item.freshness === 'LIVE').length / input.evidence.length;
  const sourceCoverage = Math.min(1, new Set(input.evidence.map((item) => item.source)).size / 4);
  const contextCoverage = Math.min(1, new Set(input.evidence.map((item) => item.kind)).size / 5);
  const weighted = (confidenceMean * 0.35) + (liveRatio * 0.25) + (sourceCoverage * 0.2) + (contextCoverage * 0.2);
  return Math.round(Math.min(Number(ceiling || 0.97), weighted) * 100000000) / 100000000;
}

function countBy(items, key) {
  const counts = {};
  for (const item of items) counts[item[key]] = (counts[item[key]] || 0) + 1;
  return Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)));
}

function cellResults(input, decision, registry) {
  const blocked = decision.state === 'DENIED';
  const abstained = decision.state === 'ABSTAINED';
  const awaiting = decision.state === 'AWAITING_APPROVAL';
  const freshness = countBy(input.evidence, 'freshness');
  const kinds = countBy(input.evidence, 'kind');
  const assets = [...new Set(input.evidence.map((item) => item.asset).filter(Boolean))].sort();
  const sources = [...new Set(input.evidence.map((item) => item.source))].sort();

  const observations = {
    'signal-intake': `${input.evidence.length} bounded Evidence Atoms from ${sources.length} source(s); freshness ${canonicalize(freshness)}.`,
    'identity-scope': input.tenant === input.authorized_tenant
      ? `Tenant Passport matches ${input.tenant}; principal ${input.principal} is bound to the submitted purpose.`
      : 'Tenant Passport mismatch; no further action authority is admitted.',
    'asset-context': `${assets.length} explicit asset identifier(s); missing ownership or criticality remains unavailable rather than inferred.`,
    'detection-engineering': `Observed event kinds ${canonicalize(kinds)}; output is a non-executing detection test plan only.`,
    'threat-context': 'Technique mapping is a defensive hypothesis and requires source-cited ATT&CK evidence before promotion.',
    'exposure-analysis': 'Exposure priority may use KEV and reachability evidence; no exploit path or exploit procedure is generated.',
    'cloud-posture': 'Cloud configuration can be evaluated when tenant-scoped evidence is supplied; provider mutation is disabled.',
    'incident-investigation': `${input.evidence.length} observations are available for a bounded timeline; inference remains labeled separately.`,
    'evidence-provenance': `${sources.length} source label(s) preserved; the case fingerprint is derived from canonical input and output.`,
    'remediation-planning': awaiting
      ? 'A mutating defensive action is drafted but held at the human-approval gate.'
      : 'Any remediation output is advisory, reversible, and non-executing.',
    'debrief-outcomes': 'The Debrief Packet records the verdict, limitations, evidence counts, and unresolved questions.',
  };

  return registry.cells.map((cell) => ({
    id: cell.id,
    name: cell.name,
    state: blocked ? 'BLOCKED' : abstained ? 'ABSTAINED' : awaiting && cell.id === 'remediation-planning' ? 'AWAITING_APPROVAL' : 'COMPLETE',
    observation: observations[cell.id] || 'No observation available.',
    external_writes: 'DISABLED',
  }));
}

function outcomeGraph(input, decision) {
  const nodes = [
    { id: 'input', type: 'Tenant Passport', state: input.tenant === input.authorized_tenant ? 'VERIFIED' : 'DENIED' },
    { id: 'evidence', type: 'Evidence Atom set', state: input.evidence.length ? 'OBSERVED' : 'UNAVAILABLE' },
    { id: 'policy', type: 'Covenant Policy', state: decision.state },
    { id: 'analysis', type: 'Finding Packet', state: decision.state === 'SANDBOX_READY' ? 'MODELED' : 'WITHHELD' },
    { id: 'outcome', type: 'Debrief Packet', state: 'RECORDED_IN_RESPONSE' },
  ];
  return {
    nodes,
    edges: [
      ['input', 'policy'],
      ['evidence', 'policy'],
      ['policy', 'analysis'],
      ['analysis', 'outcome'],
    ],
  };
}

export async function analyzeCase(rawInput, registry) {
  const input = normalizeCaseInput(rawInput);
  const sets = registrySets(registry);
  const decision = decide(input, sets);
  const score = modeledScore(input, decision, registry.authority.trust_ceiling);
  const base = {
    schema: RESULT_SCHEMA,
    engine_version: ENGINE_VERSION,
    evidence_class: 'MODELED',
    case_input: input,
    decision: {
      ...decision,
      score,
      score_ceiling: registry.authority.trust_ceiling,
      score_claim: 'MODELED_TRIAGE_SUPPORT_NOT_MEASURED_EFFICACY',
      external_writes: 'DISABLED',
      effectors: [],
      automatic_retries: 0,
      production_authorization: false,
      human_approval_observed: input.human_approval,
    },
    cells: cellResults(input, decision, registry),
    outcome_graph: outcomeGraph(input, decision),
    limitations: [
      'No external system was changed.',
      'No exploit, credential, persistence, evasion, or destructive procedure was generated.',
      'Public-feed reachability is not independent validation of source accuracy.',
      'The modeled score is not measured risk reduction, efficacy, or production authorization.',
    ],
    private_reasoning_collected: false,
  };
  const fingerprint = await sha256Hex(base);
  return {
    ...base,
    case_id: `AEGIS-${fingerprint.slice(0, 12).toUpperCase()}`,
    proof_chain: {
      kind: 'DETERMINISTIC_RESPONSE_FINGERPRINT',
      sha256: fingerprint,
      signature_status: 'UNAVAILABLE',
      persisted: false,
      source_copy_used: false,
    },
  };
}

export function summarizeFeeds(results) {
  const rows = Array.isArray(results) ? results : [];
  return {
    total: rows.length,
    live: rows.filter((row) => row.state === 'LIVE').length,
    unavailable: rows.filter((row) => row.state === 'UNAVAILABLE').length,
    feeds: rows.map((row) => ({
      path: row.path,
      state: row.state,
      status: row.status ?? null,
      observed_at: row.observed_at ?? null,
      detail: row.detail ?? null,
    })),
  };
}
