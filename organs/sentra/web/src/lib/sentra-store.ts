/**
 * Sentra in-app data layer — single source of truth for all defensive ops.
 * All data is in-memory for the current session. State persists across navigation
 * within a session via this module-level store.
 *
 * Doctrine: Sentra performs defensive containment and evidence operations on
 * tenant-owned or contracted-scope assets only.
 */

// ─── SHA-256 (FIPS 180-4, pure synchronous JS) ───────────────────────────────

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

function rotr32(x: number, n: number): number {
  return ((x >>> n) | (x << (32 - n))) >>> 0;
}

export function sha256Sync(message: string): string {
  // UTF-8 encode
  const bytes: number[] = [];
  for (let i = 0; i < message.length; i++) {
    const cp = message.charCodeAt(i);
    if (cp < 0x80) {
      bytes.push(cp);
    } else if (cp < 0x800) {
      bytes.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    } else {
      bytes.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    }
  }
  const msgLen = bytes.length;
  bytes.push(0x80);
  while ((bytes.length % 64) !== 56) bytes.push(0x00);
  const bitLen = msgLen * 8;
  // Append 64-bit big-endian length (JS integers safe to 2^53, so high word is 0)
  bytes.push(0, 0, 0, 0);
  bytes.push((bitLen >>> 24) & 0xff, (bitLen >>> 16) & 0xff, (bitLen >>> 8) & 0xff, bitLen & 0xff);

  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
  let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

  const W = new Uint32Array(64);
  for (let off = 0; off < bytes.length; off += 64) {
    for (let i = 0; i < 16; i++) {
      W[i] = ((bytes[off + i * 4] << 24) | (bytes[off + i * 4 + 1] << 16) |
               (bytes[off + i * 4 + 2] << 8) | bytes[off + i * 4 + 3]) >>> 0;
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr32(W[i - 15], 7) ^ rotr32(W[i - 15], 18) ^ (W[i - 15] >>> 3);
      const s1 = rotr32(W[i - 2], 17) ^ rotr32(W[i - 2], 19) ^ (W[i - 2] >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
      const ch = ((e & f) ^ (~e & g)) >>> 0;
      const t1 = (h + S1 + ch + SHA256_K[i] + W[i]) >>> 0;
      const S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
      const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const t2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
  }
  return [h0, h1, h2, h3, h4, h5, h6, h7].map(n => n.toString(16).padStart(8, '0')).join('');
}

// ─── Types ──────────────────────────────────────────────────────────────────

export type OwnershipStatus =
  | 'owned'
  | 'authorized'
  | 'contracted_scope'
  | 'lab'
  | 'blocked'
  | 'unknown'
  | 'external'
  | 'attacker'
  | 'unverified';

export const EXECUTABLE_STATUSES: OwnershipStatus[] = [
  'owned',
  'authorized',
  'contracted_scope',
  'lab',
];

export const NON_EXECUTABLE_STATUSES: OwnershipStatus[] = [
  'blocked',
  'unknown',
  'external',
  'attacker',
  'unverified',
];

export type AssetType =
  | 'endpoint'
  | 'server'
  | 'cloud_resource'
  | 'identity'
  | 'network_device'
  | 'repository'
  | 'database'
  | 'container'
  | 'iam_role'
  | 'api_gateway'
  | 'other';

export type AssetProvider = 'aws' | 'azure' | 'gcp' | 'on-prem' | 'github' | 'other';
export type AssetEnv = 'production' | 'staging' | 'development' | 'lab' | 'dmz';
export type AssetCriticality = 'critical' | 'high' | 'medium' | 'low';
export type AssetStatus = 'active' | 'isolated' | 'compromised' | 'decommissioned' | 'quarantined';

export interface RegistryAsset {
  id: string;
  tenant_id: string;
  name: string;
  type: AssetType;
  provider: AssetProvider;
  env: AssetEnv;
  owners: string[];
  ownership_status: OwnershipStatus;
  authorization_reference: string;
  integration_id: string | null;
  tags: string[];
  criticality: AssetCriticality;
  region: string;
  status: AssetStatus;
  created_at: string;
  updated_at: string;
  ip_address?: string;
  hostname?: string;
}

export type IncidentStatus =
  | 'new'
  | 'triage'
  | 'investigating'
  | 'approval_pending'
  | 'containment_in_progress'
  | 'contained'
  | 'recovery'
  | 'reporting'
  | 'closed';

export type IncidentSeverity = 'critical' | 'high' | 'medium' | 'low';

export interface IncidentTimelineEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  detail: string;
  type: 'detection' | 'system' | 'analyst' | 'approval' | 'containment' | 'evidence' | 'report' | 'closure';
}

export interface IncidentAsset {
  asset_id: string;
  asset_name: string;
  role: 'primary' | 'lateral' | 'source';
}

export interface Incident {
  id: string;
  tenant_id: string;
  title: string;
  description: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  mitre_techniques: string[];
  attack_vector: string;
  affected_assets: IncidentAsset[];
  assigned_analyst: string;
  detection_source: string;
  detected_at: string;
  updated_at: string;
  closed_at?: string;
  timeline: IncidentTimelineEntry[];
  evidence_ids: string[];
  approval_ids: string[];
  report_ids: string[];
  playbook_id?: string;
  attribution_draft?: AttributionDraft;
  counsel_linked: boolean;
  tags: string[];
}

export type ActionClass =
  | 'detect'
  | 'enrich'
  | 'alert'
  | 'approve'
  | 'contain_owned_asset'
  | 'revoke_owned_access'
  | 'rotate_owned_secret'
  | 'preserve_evidence'
  | 'generate_report'
  | 'notify'
  | 'create_ticket'
  | 'update_case'
  | 'export_evidence'
  | 'restore_owned_asset';

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'canceled';

export interface Approval {
  id: string;
  tenant_id: string;
  incident_id: string;
  action_id: string;
  action_class: ActionClass;
  action_description: string;
  target_asset_id: string;
  target_asset_name: string;
  target_ownership_status: OwnershipStatus;
  integration_id: string | null;
  requested_by: string;
  requested_at: string;
  expires_at: string;
  status: ApprovalStatus;
  reviewed_by?: string;
  reviewed_at?: string;
  review_reason?: string;
  doctrine_citations: string[];
  blast_radius_preview: BlastRadiusPreview;
  rollback_path: string;
  policy_class: ActionClass;
}

export interface BlastRadiusPreview {
  unreachable_assets: string[];
  revoked_sessions: number;
  downstream_services: string[];
  estimated_recovery_minutes: number;
  rollback_cost: 'low' | 'medium' | 'high';
  description: string;
}

export interface EvidenceItem {
  id: string;
  incident_id: string;
  tenant_id: string;
  type: 'log_excerpt' | 'pcap' | 'memory_dump' | 'screenshot' | 'artifact' | 'indicator' | 'report';
  source: string;
  file_name: string;
  sha256: string;
  storage_uri: string;
  locked: boolean;
  collected_by: string;
  collected_at: string;
  chain_of_custody: ChainOfCustodyEvent[];
  size_bytes: number;
  description: string;
}

export interface ChainOfCustodyEvent {
  id: string;
  actor: string;
  action: string;
  timestamp: string;
  note: string;
}

export interface EvidencePack {
  id: string;
  incident_id: string;
  created_at: string;
  created_by: string;
  item_ids: string[];
  merkle_root: string;
  content_hash: string;
  verified: boolean;
}

export type ReportType =
  | 'executive_summary'
  | 'technical_incident'
  | 'insurance'
  | 'law_enforcement_referral'
  | 'post_incident_review'
  | 'remediation_plan';

export interface ReportRecord {
  id: string;
  incident_id: string;
  tenant_id: string;
  type: ReportType;
  title: string;
  generated_by: string;
  generated_at: string;
  content: ReportContent;
  evidence_hashes: string[];
  downloaded: boolean;
}

export interface ReportContent {
  executive_summary?: string;
  incident_title: string;
  incident_id: string;
  severity: string;
  detection_date: string;
  closure_date?: string;
  affected_assets: string[];
  timeline_entries: Array<{ timestamp: string; event: string }>;
  actions_taken: string[];
  approvals_obtained: string[];
  evidence_manifest: Array<{ id: string; sha256: string; type: string }>;
  policy_decisions: string[];
  open_risks: string[];
  next_steps: string[];
  // Law enforcement specific
  circia_trigger?: boolean;
  ic3_fields?: Record<string, string>;
  // Insurance specific
  estimated_impact_usd?: number;
  coverage_notes?: string;
  // PIR specific
  root_cause?: string;
  lessons_learned?: string[];
  // Remediation plan specific
  remediation_tasks?: Array<{ task: string; owner: string; due: string }>;
}

export interface PolicyDecisionLog {
  id: string;
  timestamp: string;
  action_id: string;
  action_class: string;
  target: string;
  integration: string | null;
  reason: string;
  requested_by: string;
  approval_id: string | null;
  policy_result: 'allow' | 'deny';
  denial_message?: string;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  action_class: string;
  target_asset_id: string | null;
  integration_id: string | null;
  policy_decision: 'allow' | 'deny';
  approval_id: string | null;
  execution_result: 'success' | 'failure' | 'pending' | 'skipped';
  evidence_hash: string | null;
  rollback_reference: string | null;
  notes: string;
  prev_hash: string; // tamper-evident chain
  entry_hash: string;
}

export interface Playbook {
  id: string;
  incident_id: string;
  title: string;
  description: string;
  steps: PlaybookStep[];
  created_by: string;
  created_at: string;
  updated_at: string;
  status: 'draft' | 'active' | 'completed';
  doctrine_citations: string[];
}

export interface PlaybookStep {
  id: string;
  order: number;
  action_class: ActionClass;
  description: string;
  requires_approval: boolean;
  requires_verification: boolean;
  on_success_step?: string;
  on_failure_step?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  completed_at?: string;
  result?: string;
}

export interface AttributionDraft {
  suspected_actor: string;
  actor_catalog_ref: string;
  mitre_techniques: string[];
  indicators: string[];
  confidence: 'low' | 'medium' | 'high';
  reasoning: string;
  drafted_by: string;
  drafted_at: string;
  human_reviewed: boolean;
}

export interface SessionDigestEntry {
  timestamp: string;
  type: 'approval' | 'evidence' | 'report' | 'denial' | 'containment';
  description: string;
  actor: string;
}

// ─── Store ──────────────────────────────────────────────────────────────────

type Listener = () => void;

class SentraStore {
  private listeners: Set<Listener> = new Set();

  assets: RegistryAsset[] = [];
  incidents: Incident[] = [];
  approvals: Approval[] = [];
  evidence: EvidenceItem[] = [];
  evidencePacks: EvidencePack[] = [];
  reports: ReportRecord[] = [];
  policyLogs: PolicyDecisionLog[] = [];
  auditEntries: AuditEntry[] = [];
  playbooks: Playbook[] = [];
  sessionDigest: SessionDigestEntry[] = [];

  private idCounters: Record<string, number> = {};

  // Persistence: serialize all mutable collections so analyst context survives reloads.
  // Versioned key — bump suffix if the schema changes incompatibly.
  private static PERSIST_KEY = 'sentra:store-v1';

  nextId(prefix: string): string {
    this.idCounters[prefix] = (this.idCounters[prefix] ?? 0) + 1;
    return `${prefix}-${String(this.idCounters[prefix]).padStart(4, '0')}`;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  notify() {
    this.persist();
    this.listeners.forEach(fn => {
      fn();
    });
    this.broadcastOpsStatus();
  }

  // ── Persistence ─────────────────────────────────────────────────────────
  // All mutations flow through notify(), so persisting here captures every
  // analyst action (containment, evidence locking, approval decisions, etc).

  persist(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      const snapshot = {
        v: 1,
        assets: this.assets,
        incidents: this.incidents,
        approvals: this.approvals,
        evidence: this.evidence,
        evidencePacks: this.evidencePacks,
        reports: this.reports,
        policyLogs: this.policyLogs,
        auditEntries: this.auditEntries,
        playbooks: this.playbooks,
        sessionDigest: this.sessionDigest,
        idCounters: this.idCounters,
      };
      localStorage.setItem(SentraStore.PERSIST_KEY, JSON.stringify(snapshot));
    } catch {
      /* storage unavailable or quota exceeded — drop silently */
    }
  }

  hydrate(): boolean {
    if (typeof localStorage === 'undefined') return false;
    try {
      const raw = localStorage.getItem(SentraStore.PERSIST_KEY);
      if (!raw) return false;
      const snap = JSON.parse(raw);
      if (snap?.v !== 1) return false;
      this.assets = snap.assets ?? [];
      this.incidents = snap.incidents ?? [];
      this.approvals = snap.approvals ?? [];
      this.evidence = snap.evidence ?? [];
      this.evidencePacks = snap.evidencePacks ?? [];
      this.reports = snap.reports ?? [];
      this.policyLogs = snap.policyLogs ?? [];
      this.auditEntries = snap.auditEntries ?? [];
      this.playbooks = snap.playbooks ?? [];
      this.sessionDigest = snap.sessionDigest ?? [];
      this.idCounters = snap.idCounters ?? {};
      return true;
    } catch {
      return false;
    }
  }

  clearPersisted(): void {
    if (typeof localStorage === 'undefined') return;
    try { localStorage.removeItem(SentraStore.PERSIST_KEY); } catch { /* ignore */ }
  }

  private broadcastOpsStatus(): void {
    try {
      const activeIncidents = this.incidents.filter(i => i.status !== 'closed').length;
      const pendingApprovals = this.approvals.filter(a => a.status === 'pending').length;
      const denials = this.policyLogs.filter(p => p.policy_result === 'deny');

      // Per-agent telemetry — dispatches today + most recent activity timestamp.
      // Each agent's metric is derived from real store mutations so A11oy's
      // SentraOps view reflects actual analyst/system activity rather than
      // hard-coded mock counts.
      const startOfDay = new Date();
      startOfDay.setHours(0, 0, 0, 0);
      const dayStart = startOfDay.getTime();

      const sinceToday = (iso: string) => new Date(iso).getTime() >= dayStart;
      const latest = (items: { ts: string }[]): string | null => {
        if (items.length === 0) return null;
        let max = items[0].ts;
        for (const it of items) if (it.ts > max) max = it.ts;
        return max;
      };

      const containmentClasses = new Set([
        'contain_owned_asset',
        'revoke_owned_access',
        'rotate_owned_secret',
        'restore_owned_asset',
      ]);

      // Triage Navigator → incident detection events
      const triageEvents = this.incidents.flatMap(i =>
        i.timeline.filter(t => t.type === 'detection').map(t => ({ ts: t.timestamp }))
      );
      // Evidence Custodian → evidence collection / locking
      const evidenceEvents = this.evidence.map(e => ({
        ts: e.chain_of_custody[e.chain_of_custody.length - 1]?.timestamp ?? e.collected_at,
      }));
      // Containment Recommender → containment-class approval requests
      const containmentEvents = this.approvals
        .filter(a => containmentClasses.has(a.action_class))
        .map(a => ({ ts: a.requested_at }));
      // Attribution Analyst → incidents that have an attribution_draft
      const attributionEvents = this.incidents
        .filter(i => i.attribution_draft)
        .map(i => ({ ts: i.attribution_draft!.drafted_at }));
      // Report Generator → reports generated
      const reportEvents = this.reports.map(r => ({ ts: r.generated_at }));
      // Audit Verifier → every audit chain entry
      const auditEvents = this.auditEntries.map(a => ({ ts: a.timestamp }));
      // Policy Enforcement Monitor → every policy decision
      const policyEvents = this.policyLogs.map(p => ({ ts: p.timestamp }));

      const agents = {
        'ag-triage': {
          dispatches_today: triageEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(triageEvents),
        },
        'ag-evidence': {
          dispatches_today: evidenceEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(evidenceEvents),
        },
        'ag-containment': {
          dispatches_today: containmentEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(containmentEvents),
        },
        'ag-attribution': {
          dispatches_today: attributionEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(attributionEvents),
        },
        'ag-report': {
          dispatches_today: reportEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(reportEvents),
        },
        'ag-audit': {
          dispatches_today: auditEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(auditEvents),
        },
        'ag-policy': {
          dispatches_today: policyEvents.filter(e => sinceToday(e.ts)).length,
          last_dispatch: latest(policyEvents),
        },
      };

      const payload = {
        activeIncidents,
        pendingApprovals,
        auditEntries: this.auditEntries.length,
        evidenceItems: this.evidence.length,
        policyDenials: denials.length,
        totalAssets: this.assets.length,
        ownedAssets: this.assets.filter(a => ['owned', 'authorized', 'contracted_scope', 'lab'].includes(a.ownership_status)).length,
        agents,
        lastUpdated: new Date().toISOString(),
      };
      localStorage.setItem('sentra:ops-status', JSON.stringify(payload));

      // Also push to the API server so A11oy operators viewing SentraOps on a
      // different device or fresh session can see the same telemetry. Fire-
      // and-forget; failures (offline, CORS, server down) are non-fatal.
      try {
        if (typeof fetch !== 'undefined') {
          void fetch('/api/sentra/status', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: true,
          }).catch(() => { /* network unavailable — local bridge still works */ });
        }
      } catch { /* fetch missing or threw synchronously */ }
    } catch { /* storage unavailable */ }
  }

  // ── Asset Registry ──────────────────────────────────────────────────────

  addAsset(asset: Omit<RegistryAsset, 'id' | 'created_at' | 'updated_at'>): RegistryAsset {
    const now = new Date().toISOString();
    const a: RegistryAsset = { ...asset, id: this.nextId('ASSET'), created_at: now, updated_at: now };
    this.assets.push(a);
    this.notify();
    return a;
  }

  updateAsset(id: string, patch: Partial<RegistryAsset>): RegistryAsset | null {
    const idx = this.assets.findIndex(a => a.id === id);
    if (idx === -1) return null;
    this.assets[idx] = { ...this.assets[idx], ...patch, updated_at: new Date().toISOString() };
    this.notify();
    return this.assets[idx];
  }

  getAsset(id: string): RegistryAsset | undefined {
    return this.assets.find(a => a.id === id);
  }

  isAssetExecutable(id: string): boolean {
    const asset = this.getAsset(id);
    if (!asset) return false;
    return EXECUTABLE_STATUSES.includes(asset.ownership_status);
  }

  // ── Incidents ───────────────────────────────────────────────────────────

  addIncident(inc: Omit<Incident, 'id' | 'detected_at' | 'updated_at' | 'timeline' | 'evidence_ids' | 'approval_ids' | 'report_ids' | 'counsel_linked'>): Incident {
    const now = new Date().toISOString();
    const id = this.nextId('INC');
    const incident: Incident = {
      ...inc,
      id,
      detected_at: now,
      updated_at: now,
      timeline: [{
        id: this.nextId('TL'),
        timestamp: now,
        actor: 'System',
        action: 'Incident detected and opened',
        detail: `Severity: ${inc.severity} | Source: ${inc.detection_source}`,
        type: 'detection',
      }],
      evidence_ids: [],
      approval_ids: [],
      report_ids: [],
      counsel_linked: false,
    };
    this.incidents.push(incident);
    this.writeAudit({
      actor: 'System',
      action: 'incident_created',
      action_class: 'detect',
      target_asset_id: inc.affected_assets[0]?.asset_id ?? null,
      integration_id: null,
      policy_decision: 'allow',
      approval_id: null,
      execution_result: 'success',
      evidence_hash: null,
      rollback_reference: null,
      notes: `Incident ${id} created: ${inc.title}`,
    });
    this.notify();
    return incident;
  }

  advanceIncident(id: string, newStatus: IncidentStatus, actor: string, detail: string): Incident | null {
    const idx = this.incidents.findIndex(i => i.id === id);
    if (idx === -1) return null;
    const now = new Date().toISOString();
    const inc = this.incidents[idx];
    const timelineType: IncidentTimelineEntry['type'] =
      newStatus === 'closed' ? 'closure' :
      newStatus === 'approval_pending' ? 'approval' :
      newStatus === 'containment_in_progress' ? 'containment' :
      newStatus === 'reporting' ? 'report' : 'analyst';
    inc.timeline.push({
      id: this.nextId('TL'),
      timestamp: now,
      actor,
      action: `Status advanced to ${newStatus}`,
      detail,
      type: timelineType,
    });
    inc.status = newStatus;
    inc.updated_at = now;
    if (newStatus === 'closed') inc.closed_at = now;
    this.writeAudit({
      actor,
      action: 'incident_status_advanced',
      action_class: 'update_case',
      target_asset_id: inc.affected_assets[0]?.asset_id ?? null,
      integration_id: null,
      policy_decision: 'allow',
      approval_id: null,
      execution_result: 'success',
      evidence_hash: null,
      rollback_reference: null,
      notes: `Incident ${id} advanced to ${newStatus}`,
    });
    this.notify();
    return this.incidents[idx];
  }

  addIncidentNote(id: string, actor: string, note: string): void {
    const inc = this.incidents.find(i => i.id === id);
    if (!inc) return;
    inc.timeline.push({
      id: this.nextId('TL'),
      timestamp: new Date().toISOString(),
      actor,
      action: 'Note added',
      detail: note,
      type: 'analyst',
    });
    inc.updated_at = new Date().toISOString();
    this.notify();
  }

  // ── Approvals ───────────────────────────────────────────────────────────

  createApproval(approval: Omit<Approval, 'id' | 'requested_at' | 'status'>): Approval {
    const now = new Date().toISOString();
    const expires = new Date(Date.now() + 4 * 3600 * 1000).toISOString();
    const a: Approval = { ...approval, id: this.nextId('APR'), requested_at: now, expires_at: expires, status: 'pending' };
    this.approvals.push(a);
    const inc = this.incidents.find(i => i.id === approval.incident_id);
    if (inc) {
      inc.approval_ids.push(a.id);
      inc.timeline.push({
        id: this.nextId('TL'),
        timestamp: now,
        actor: approval.requested_by,
        action: 'Approval requested',
        detail: `${approval.action_description} — target: ${approval.target_asset_name}`,
        type: 'approval',
      });
      if (inc.status !== 'approval_pending') {
        inc.status = 'approval_pending';
      }
      inc.updated_at = now;
    }
    this.addSessionDigest('approval', `Approval requested: ${approval.action_description}`, approval.requested_by);
    this.writeAudit({
      actor: approval.requested_by,
      action: 'approval_requested',
      action_class: approval.action_class,
      target_asset_id: approval.target_asset_id,
      integration_id: approval.integration_id,
      policy_decision: 'allow',
      approval_id: a.id,
      execution_result: 'pending',
      evidence_hash: null,
      rollback_reference: null,
      notes: `Approval ${a.id} created for: ${approval.action_description}`,
    });
    this.notify();
    return a;
  }

  decideApproval(id: string, decision: 'approved' | 'rejected', reviewer: string, reason?: string): Approval | null {
    const idx = this.approvals.findIndex(a => a.id === id);
    if (idx === -1) return null;
    const a = this.approvals[idx];
    a.status = decision;
    a.reviewed_by = reviewer;
    a.reviewed_at = new Date().toISOString();
    a.review_reason = reason;
    this.addSessionDigest('approval', `Approval ${decision}: ${a.action_description}`, reviewer);
    this.writeAudit({
      actor: reviewer,
      action: `approval_${decision}`,
      action_class: a.action_class,
      target_asset_id: a.target_asset_id,
      integration_id: a.integration_id,
      policy_decision: decision === 'approved' ? 'allow' : 'deny',
      approval_id: id,
      execution_result: decision === 'approved' ? 'success' : 'failure',
      evidence_hash: null,
      rollback_reference: null,
      notes: reason ?? '',
    });
    this.notify();
    return this.approvals[idx];
  }

  // ── Evidence ────────────────────────────────────────────────────────────

  addEvidence(ev: Omit<EvidenceItem, 'id' | 'collected_at' | 'locked' | 'chain_of_custody'>): EvidenceItem {
    const now = new Date().toISOString();
    const item: EvidenceItem = {
      ...ev,
      id: this.nextId('EV'),
      collected_at: now,
      locked: false,
      chain_of_custody: [{
        id: this.nextId('COC'),
        actor: ev.collected_by,
        action: 'Evidence collected',
        timestamp: now,
        note: `Type: ${ev.type} | Source: ${ev.source}`,
      }],
    };
    this.evidence.push(item);
    const inc = this.incidents.find(i => i.id === ev.incident_id);
    if (inc) {
      inc.evidence_ids.push(item.id);
      inc.timeline.push({
        id: this.nextId('TL'),
        timestamp: now,
        actor: ev.collected_by,
        action: 'Evidence collected',
        detail: `${ev.type}: ${ev.file_name} (SHA256: ${ev.sha256.substring(0, 12)}...)`,
        type: 'evidence',
      });
      inc.updated_at = now;
    }
    this.addSessionDigest('evidence', `Evidence collected: ${ev.file_name}`, ev.collected_by);
    this.notify();
    return item;
  }

  lockEvidence(id: string, actor: string): EvidenceItem | null {
    const idx = this.evidence.findIndex(e => e.id === id);
    if (idx === -1) return null;
    const ev = this.evidence[idx];
    if (ev.locked) return ev;
    ev.locked = true;
    ev.chain_of_custody.push({
      id: this.nextId('COC'),
      actor,
      action: 'Evidence locked',
      timestamp: new Date().toISOString(),
      note: 'Evidence locked for legal hold — no further modification permitted',
    });
    this.addSessionDigest('evidence', `Evidence locked: ${ev.file_name}`, actor);
    this.writeAudit({
      actor,
      action: 'evidence_locked',
      action_class: 'preserve_evidence',
      target_asset_id: null,
      integration_id: null,
      policy_decision: 'allow',
      approval_id: null,
      execution_result: 'success',
      evidence_hash: ev.sha256,
      rollback_reference: null,
      notes: `Evidence ${id} locked: ${ev.file_name}`,
    });
    this.notify();
    return this.evidence[idx];
  }

  generateEvidencePack(incidentId: string, actor: string): EvidencePack {
    const incEvidence = this.evidence.filter(e => e.incident_id === incidentId);
    const hashes = incEvidence.map(e => e.sha256);
    const merkleRoot = this.computeMerkleRoot(hashes);
    const content = JSON.stringify({ incident_id: incidentId, items: hashes, merkle_root: merkleRoot });
    const contentHash = this.simpleHash(content);
    const now = new Date().toISOString();
    const pack: EvidencePack = {
      id: this.nextId('EP'),
      incident_id: incidentId,
      created_at: now,
      created_by: actor,
      item_ids: incEvidence.map(e => e.id),
      merkle_root: merkleRoot,
      content_hash: contentHash,
      verified: true,
    };
    this.evidencePacks.push(pack);
    this.notify();
    return pack;
  }

  // ── Reports ─────────────────────────────────────────────────────────────

  generateReport(incidentId: string, type: ReportType, actor: string): ReportRecord {
    const inc = this.incidents.find(i => i.id === incidentId);
    const now = new Date().toISOString();
    const evItems = this.evidence.filter(e => e.incident_id === incidentId);
    const approvalsList = this.approvals.filter(a => a.incident_id === incidentId);
    const policyList = this.policyLogs.filter(p =>
      approvalsList.some(a => a.id === p.approval_id)
    );

    const TITLES: Record<ReportType, string> = {
      executive_summary: 'Executive Summary',
      technical_incident: 'Technical Incident Report',
      insurance: 'Insurance Report',
      law_enforcement_referral: 'Law Enforcement Referral Package',
      post_incident_review: 'Post-Incident Review',
      remediation_plan: 'Remediation Plan',
    };

    const content: ReportContent = {
      incident_title: inc?.title ?? 'Unknown Incident',
      incident_id: incidentId,
      severity: inc?.severity ?? 'unknown',
      detection_date: inc?.detected_at ?? now,
      closure_date: inc?.closed_at,
      affected_assets: inc?.affected_assets.map(a => a.asset_name) ?? [],
      timeline_entries: (inc?.timeline ?? []).map(t => ({ timestamp: t.timestamp, event: t.detail })),
      actions_taken: approvalsList.filter(a => a.status === 'approved').map(a => a.action_description),
      approvals_obtained: approvalsList.map(a => `${a.id}: ${a.action_description} (${a.status})`),
      evidence_manifest: evItems.map(e => ({ id: e.id, sha256: e.sha256, type: e.type })),
      policy_decisions: policyList.map(p => `${p.policy_result.toUpperCase()}: ${p.action_class} — ${p.reason}`),
      open_risks: inc?.status !== 'closed' ? ['Incident not yet closed — residual risk present'] : [],
      next_steps: inc?.status !== 'closed'
        ? ['Complete containment', 'Conduct post-incident review', 'Generate remediation plan']
        : ['Schedule lessons-learned session', 'Update defensive playbooks', 'Verify remediation effectiveness'],
    };

    if (type === 'executive_summary') {
      content.executive_summary = `Incident ${incidentId} (${inc?.severity ?? 'unknown'} severity) was ${inc?.status === 'closed' ? 'fully resolved' : 'detected and contained'}. ${approvalsList.filter(a => a.status === 'approved').length} defensive actions approved and executed. ${evItems.length} evidence items collected and preserved.`;
    }
    if (type === 'law_enforcement_referral') {
      content.circia_trigger = inc?.severity === 'critical';
      content.ic3_fields = {
        incident_type: inc?.attack_vector ?? 'Unknown',
        date_discovered: inc?.detected_at ?? now,
        systems_affected: inc?.affected_assets.map(a => a.asset_name).join(', ') ?? '',
        mitre_techniques: inc?.mitre_techniques.join(', ') ?? '',
        evidence_hash_root: evItems[0]?.sha256 ?? '',
      };
    }
    if (type === 'insurance') {
      content.estimated_impact_usd = inc?.severity === 'critical' ? 850000 : inc?.severity === 'high' ? 250000 : 75000;
      content.coverage_notes = 'Consult insurance carrier per policy terms. Evidence manifest attached.';
    }
    if (type === 'post_incident_review') {
      content.root_cause = inc?.description ?? '';
      content.lessons_learned = ['Review detection coverage for similar attack vectors', 'Update playbooks with new containment steps'];
    }
    if (type === 'remediation_plan') {
      content.remediation_tasks = [
        { task: 'Patch affected systems', owner: inc?.assigned_analyst ?? 'IR Team', due: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0] },
        { task: 'Rotate compromised credentials', owner: 'Identity Team', due: new Date(Date.now() + 2 * 86400000).toISOString().split('T')[0] },
        { task: 'Review access controls', owner: 'Security Architecture', due: new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0] },
      ];
    }

    const report: ReportRecord = {
      id: this.nextId('RPT'),
      incident_id: incidentId,
      tenant_id: inc?.tenant_id ?? 'tenant-001',
      type,
      title: TITLES[type],
      generated_by: actor,
      generated_at: now,
      content,
      evidence_hashes: evItems.map(e => e.sha256),
      downloaded: false,
    };
    this.reports.push(report);
    if (inc) {
      inc.report_ids.push(report.id);
      inc.updated_at = now;
    }
    this.addSessionDigest('report', `Report generated: ${TITLES[type]}`, actor);
    this.writeAudit({
      actor,
      action: 'report_generated',
      action_class: 'generate_report',
      target_asset_id: null,
      integration_id: null,
      policy_decision: 'allow',
      approval_id: null,
      execution_result: 'success',
      evidence_hash: null,
      rollback_reference: null,
      notes: `Report ${report.id} generated: ${TITLES[type]} for incident ${incidentId}`,
    });
    this.notify();
    return report;
  }

  // ── Policy Logs ─────────────────────────────────────────────────────────

  writePolicyLog(entry: Omit<PolicyDecisionLog, 'id' | 'timestamp'>): PolicyDecisionLog {
    const log: PolicyDecisionLog = {
      ...entry,
      id: this.nextId('POL'),
      timestamp: new Date().toISOString(),
    };
    this.policyLogs.push(log);
    if (entry.policy_result === 'deny') {
      this.addSessionDigest('denial', `Action denied: ${entry.action_class} on ${entry.target}`, entry.requested_by);
    }
    this.notify();
    return log;
  }

  // ── Audit Trail ─────────────────────────────────────────────────────────

  writeAudit(entry: Omit<AuditEntry, 'id' | 'timestamp' | 'prev_hash' | 'entry_hash'>): AuditEntry {
    const prev = this.auditEntries[this.auditEntries.length - 1];
    const prevHash = prev?.entry_hash ?? '0000000000000000';
    const now = new Date().toISOString();
    const payload = JSON.stringify({ ...entry, timestamp: now, prev_hash: prevHash });
    const entryHash = this.simpleHash(payload);
    const audit: AuditEntry = {
      ...entry,
      id: this.nextId('AUD'),
      timestamp: now,
      prev_hash: prevHash,
      entry_hash: entryHash,
    };
    this.auditEntries.push(audit);
    this.notify();
    return audit;
  }

  verifyAuditChain(): { valid: boolean; checkedEntries: number; firstInvalidId?: string } {
    let prevHash = '0000000000000000';
    for (const entry of this.auditEntries) {
      if (entry.prev_hash !== prevHash) {
        return { valid: false, checkedEntries: this.auditEntries.indexOf(entry), firstInvalidId: entry.id };
      }
      prevHash = entry.entry_hash;
    }
    return { valid: true, checkedEntries: this.auditEntries.length };
  }

  // ── Playbooks ───────────────────────────────────────────────────────────

  addPlaybook(pb: Omit<Playbook, 'id' | 'created_at' | 'updated_at'>): Playbook {
    const now = new Date().toISOString();
    const playbook: Playbook = { ...pb, id: this.nextId('PB'), created_at: now, updated_at: now };
    this.playbooks.push(playbook);
    this.notify();
    return playbook;
  }

  // ── Session Digest ──────────────────────────────────────────────────────

  addSessionDigest(type: SessionDigestEntry['type'], description: string, actor: string): void {
    this.sessionDigest.push({ timestamp: new Date().toISOString(), type, description, actor });
    // Keep only last 100 entries
    if (this.sessionDigest.length > 100) this.sessionDigest.shift();
  }

  // ── Helpers ─────────────────────────────────────────────────────────────

  /**
   * SHA-256 (pure synchronous JS implementation — FIPS 180-4).
   * Used for evidence content hashes, Merkle roots, and audit chain entries.
   * Produces a canonical 64-hex-char (256-bit) digest.
   */
  simpleHash(input: string): string {
    return sha256Sync(input);
  }

  computeMerkleRoot(hashes: string[]): string {
    if (hashes.length === 0) return this.simpleHash('empty');
    let level = [...hashes];
    while (level.length > 1) {
      const next: string[] = [];
      for (let i = 0; i < level.length; i += 2) {
        const left = level[i];
        const right = level[i + 1] ?? left;
        next.push(this.simpleHash(left + right));
      }
      level = next;
    }
    return level[0];
  }

  verifyEvidencePack(packId: string): { valid: boolean; merkle_root: string; computed_root: string } {
    const pack = this.evidencePacks.find(p => p.id === packId);
    if (!pack) return { valid: false, merkle_root: '', computed_root: '' };
    const items = this.evidence.filter(e => pack.item_ids.includes(e.id));
    const computed = this.computeMerkleRoot(items.map(e => e.sha256));
    return { valid: computed === pack.merkle_root, merkle_root: pack.merkle_root, computed_root: computed };
  }

  // ── Counterfactual Preview ───────────────────────────────────────────────

  computeBlastRadius(assetId: string, actionClass: ActionClass): BlastRadiusPreview {
    const asset = this.getAsset(assetId);
    if (!asset) {
      return {
        unreachable_assets: [],
        revoked_sessions: 0,
        downstream_services: [],
        estimated_recovery_minutes: 0,
        rollback_cost: 'low',
        description: 'Asset not found in registry',
      };
    }
    // Simulate based on asset type and criticality
    const critMult = asset.criticality === 'critical' ? 4 : asset.criticality === 'high' ? 2 : 1;
    const connectedAssets = this.assets
      .filter(a => a.id !== assetId && a.env === asset.env && a.tenant_id === asset.tenant_id)
      .slice(0, critMult * 2)
      .map(a => a.name);
    const sessionCount = actionClass === 'revoke_owned_access' ? critMult * 3 : 0;
    const services = asset.type === 'server' ? ['web-frontend', 'api-gateway', 'monitoring'] :
      asset.type === 'identity' ? ['sso', 'vault', 'ci-cd'] :
      asset.type === 'network_device' ? ['subnet-east', 'subnet-west'] : [];
    const recoveryMins = critMult * 15;
    const rollbackCost: 'low' | 'medium' | 'high' = critMult >= 4 ? 'high' : critMult >= 2 ? 'medium' : 'low';
    return {
      unreachable_assets: connectedAssets,
      revoked_sessions: sessionCount,
      downstream_services: services.slice(0, critMult),
      estimated_recovery_minutes: recoveryMins,
      rollback_cost: rollbackCost,
      description: `Containing ${asset.name} (${asset.criticality}) will affect ${connectedAssets.length} connected assets${sessionCount > 0 ? `, revoke ${sessionCount} active sessions` : ''}, and impact ${services.length} downstream services. Estimated recovery: ${recoveryMins} minutes.`,
    };
  }
}

// Singleton store
export const sentraStore = new SentraStore();

// React hook
import { useEffect, useState } from 'react';

export function useSentraStore() {
  const [, forceUpdate] = useState(0);
  useEffect(() => {
    const unsub = sentraStore.subscribe(() => forceUpdate(n => n + 1));
    return unsub;
  }, []);
  return sentraStore;
}

// ─── Seed Data ───────────────────────────────────────────────────────────────

function seedStore() {
  const TENANT = 'tenant-001';
  const now = new Date();
  const daysAgo = (d: number) => new Date(now.getTime() - d * 86400000).toISOString();
  const hoursAgo = (h: number) => new Date(now.getTime() - h * 3600000).toISOString();
  const minsAgo = (m: number) => new Date(now.getTime() - m * 60000).toISOString();

  // ── Assets (200+) ─────────────────────────────────────────────────────

  const assetTemplates: Array<Omit<RegistryAsset, 'id' | 'created_at' | 'updated_at'>> = [
    // Identity assets
    { tenant_id: TENANT, name: 'admin.chen@szlholdings.com', type: 'identity', provider: 'azure', env: 'production', owners: ['IT Security'], ownership_status: 'owned', authorization_reference: 'AUTH-2024-001', integration_id: 'int-entra', tags: ['privileged', 'admin'], criticality: 'critical', region: 'us-east-1', status: 'compromised' },
    { tenant_id: TENANT, name: 'cfo@szlholdings.com', type: 'identity', provider: 'azure', env: 'production', owners: ['Finance', 'IT Security'], ownership_status: 'owned', authorization_reference: 'AUTH-2024-002', integration_id: 'int-entra', tags: ['executive', 'finance'], criticality: 'critical', region: 'us-east-1', status: 'active' },
    { tenant_id: TENANT, name: 'svc_backup@szlholdings.com', type: 'identity', provider: 'azure', env: 'production', owners: ['IT Ops'], ownership_status: 'owned', authorization_reference: 'AUTH-2024-003', integration_id: 'int-entra', tags: ['service-account'], criticality: 'high', region: 'us-east-1', status: 'isolated' },
    { tenant_id: TENANT, name: 'svc_cicd@szlholdings.com', type: 'identity', provider: 'github', env: 'production', owners: ['DevSecOps'], ownership_status: 'owned', authorization_reference: 'AUTH-2024-004', integration_id: 'int-github', tags: ['ci-cd', 'service-account'], criticality: 'high', region: 'global', status: 'active' },
    { tenant_id: TENANT, name: 'ot-admin@scada.local', type: 'identity', provider: 'on-prem', env: 'production', owners: ['OT Security'], ownership_status: 'owned', authorization_reference: 'AUTH-2024-005', integration_id: null, tags: ['ot', 'privileged'], criticality: 'critical', region: 'us-central-1', status: 'active' },

    // Endpoints
    { tenant_id: TENANT, name: 'WS-PROD-012', type: 'endpoint', provider: 'on-prem', env: 'production', owners: ['IT Security'], ownership_status: 'owned', authorization_reference: 'ASSET-2024-E001', integration_id: 'int-defender', tags: ['windows', 'workstation'], criticality: 'high', region: 'us-east-1', status: 'isolated', hostname: 'WS-PROD-012', ip_address: '10.0.1.12' },
    { tenant_id: TENANT, name: 'DC-EAST-01', type: 'server', provider: 'on-prem', env: 'production', owners: ['IT Ops'], ownership_status: 'owned', authorization_reference: 'ASSET-2024-S001', integration_id: 'int-defender', tags: ['domain-controller', 'windows'], criticality: 'critical', region: 'us-east-1', status: 'active', hostname: 'DC-EAST-01', ip_address: '10.0.0.1' },
    { tenant_id: TENANT, name: 'FS-CLUSTER-03', type: 'server', provider: 'on-prem', env: 'production', owners: ['IT Ops'], ownership_status: 'owned', authorization_reference: 'ASSET-2024-S002', integration_id: 'int-defender', tags: ['file-server'], criticality: 'high', region: 'us-east-1', status: 'isolated', hostname: 'FS-CLUSTER-03', ip_address: '10.0.2.3' },
    { tenant_id: TENANT, name: 'BUILD-SRV-02', type: 'server', provider: 'on-prem', env: 'production', owners: ['DevSecOps'], ownership_status: 'owned', authorization_reference: 'ASSET-2024-S003', integration_id: 'int-crowdstrike', tags: ['build-server', 'linux'], criticality: 'high', region: 'us-west-2', status: 'isolated', hostname: 'BUILD-SRV-02', ip_address: '10.1.0.2' },
    { tenant_id: TENANT, name: 'PLC-CTRL-003', type: 'other', provider: 'on-prem', env: 'production', owners: ['OT Security'], ownership_status: 'owned', authorization_reference: 'OT-ASSET-2024-001', integration_id: null, tags: ['ot', 'plc', 'scada'], criticality: 'critical', region: 'us-central-1', status: 'compromised', ip_address: '192.168.10.3' },
    { tenant_id: TENANT, name: 'SCADA-SRV-01', type: 'server', provider: 'on-prem', env: 'production', owners: ['OT Security'], ownership_status: 'owned', authorization_reference: 'OT-ASSET-2024-002', integration_id: null, tags: ['ot', 'scada'], criticality: 'critical', region: 'us-central-1', status: 'active', hostname: 'SCADA-SRV-01', ip_address: '192.168.10.1' },

    // Cloud resources
    { tenant_id: TENANT, name: 'aws-prod-east-vpc', type: 'cloud_resource', provider: 'aws', env: 'production', owners: ['Cloud Ops'], ownership_status: 'owned', authorization_reference: 'CLOUD-2024-001', integration_id: 'int-aws', tags: ['vpc', 'networking'], criticality: 'critical', region: 'us-east-1', status: 'active' },
    { tenant_id: TENANT, name: 'aws-s3-backup-prod', type: 'cloud_resource', provider: 'aws', env: 'production', owners: ['IT Ops'], ownership_status: 'owned', authorization_reference: 'CLOUD-2024-002', integration_id: 'int-aws', tags: ['s3', 'backup'], criticality: 'high', region: 'us-east-1', status: 'active' },
    { tenant_id: TENANT, name: 'azure-keyvault-prod', type: 'cloud_resource', provider: 'azure', env: 'production', owners: ['IT Security'], ownership_status: 'owned', authorization_reference: 'CLOUD-2024-003', integration_id: 'int-azure', tags: ['secrets', 'keyvault'], criticality: 'critical', region: 'eastus', status: 'active' },
    { tenant_id: TENANT, name: 'gcp-bq-analytics', type: 'cloud_resource', provider: 'gcp', env: 'production', owners: ['Data Engineering'], ownership_status: 'owned', authorization_reference: 'CLOUD-2024-004', integration_id: 'int-gcp', tags: ['bigquery', 'analytics'], criticality: 'medium', region: 'us-central1', status: 'active' },
    { tenant_id: TENANT, name: 'cloudflare-waf-prod', type: 'network_device', provider: 'other', env: 'production', owners: ['Security Ops'], ownership_status: 'owned', authorization_reference: 'NET-2024-001', integration_id: 'int-cloudflare', tags: ['waf', 'cdn'], criticality: 'critical', region: 'global', status: 'active' },

    // Repositories
    { tenant_id: TENANT, name: 'szlholdings/platform-core', type: 'repository', provider: 'github', env: 'production', owners: ['DevSecOps'], ownership_status: 'owned', authorization_reference: 'REPO-2024-001', integration_id: 'int-github', tags: ['critical-repo', 'monorepo'], criticality: 'critical', region: 'global', status: 'active' },
    { tenant_id: TENANT, name: 'szlholdings/infrastructure', type: 'repository', provider: 'github', env: 'production', owners: ['DevSecOps', 'Cloud Ops'], ownership_status: 'owned', authorization_reference: 'REPO-2024-002', integration_id: 'int-github', tags: ['iac', 'terraform'], criticality: 'high', region: 'global', status: 'active' },

    // Databases
    { tenant_id: TENANT, name: 'prod-postgres-primary', type: 'database', provider: 'aws', env: 'production', owners: ['Data Engineering', 'IT Ops'], ownership_status: 'owned', authorization_reference: 'DB-2024-001', integration_id: 'int-aws', tags: ['rds', 'postgresql', 'primary'], criticality: 'critical', region: 'us-east-1', status: 'active' },
    { tenant_id: TENANT, name: 'prod-redis-cache', type: 'database', provider: 'aws', env: 'production', owners: ['Cloud Ops'], ownership_status: 'owned', authorization_reference: 'DB-2024-002', integration_id: 'int-aws', tags: ['redis', 'cache'], criticality: 'medium', region: 'us-east-1', status: 'active' },

    // External / non-executable
    { tenant_id: TENANT, name: 'external-vendor-api.com', type: 'api_gateway', provider: 'other', env: 'production', owners: [], ownership_status: 'external', authorization_reference: '', integration_id: null, tags: ['third-party'], criticality: 'medium', region: 'global', status: 'active' },
    { tenant_id: TENANT, name: 'attacker-c2.malicious.io', type: 'other', provider: 'other', env: 'production', owners: [], ownership_status: 'attacker', authorization_reference: '', integration_id: null, tags: ['threat-actor', 'c2'], criticality: 'critical', region: 'unknown', status: 'active' },
    { tenant_id: TENANT, name: 'lab-test-endpoint-01', type: 'endpoint', provider: 'on-prem', env: 'lab', owners: ['Security Research'], ownership_status: 'lab', authorization_reference: 'LAB-2024-001', integration_id: 'int-crowdstrike', tags: ['lab', 'test'], criticality: 'low', region: 'us-east-1', status: 'active', hostname: 'lab-test-01', ip_address: '172.16.0.1' },

    // Contracted scope
    { tenant_id: TENANT, name: 'pentest-target-vm-01', type: 'server', provider: 'aws', env: 'staging', owners: ['Security'], ownership_status: 'contracted_scope', authorization_reference: 'PENTEST-SOW-2024-Q4', integration_id: 'int-aws', tags: ['pentest', 'authorized'], criticality: 'medium', region: 'us-west-2', status: 'active' },
    // Authorized partner
    { tenant_id: TENANT, name: 'partner-soc-connector', type: 'other', provider: 'other', env: 'production', owners: ['Security Ops'], ownership_status: 'authorized', authorization_reference: 'MSA-PARTNER-2024-003', integration_id: null, tags: ['partner', 'authorized'], criticality: 'medium', region: 'us-east-1', status: 'active' },
  ];

  // Add all template assets, then generate more programmatically
  for (const tmpl of assetTemplates) {
    sentraStore.assets.push({
      ...tmpl,
      id: sentraStore.nextId('ASSET'),
      created_at: daysAgo(Math.floor(Math.random() * 365)),
      updated_at: daysAgo(Math.floor(Math.random() * 30)),
    });
  }

  // Generate additional assets to reach 200+
  const envs: AssetEnv[] = ['production', 'staging', 'development', 'lab'];
  const types: AssetType[] = ['endpoint', 'server', 'cloud_resource', 'database', 'container'];
  const providers: AssetProvider[] = ['aws', 'azure', 'on-prem', 'gcp'];
  const statuses: OwnershipStatus[] = ['owned', 'owned', 'owned', 'authorized', 'lab'];
  const assetStatuses: AssetStatus[] = ['active', 'active', 'active', 'active', 'isolated'];
  for (let i = 1; i <= 180; i++) {
    const env = envs[i % envs.length];
    const type = types[i % types.length];
    const provider = providers[i % providers.length];
    const ownershipStatus = statuses[i % statuses.length];
    sentraStore.assets.push({
      id: sentraStore.nextId('ASSET'),
      tenant_id: TENANT,
      name: `${provider}-${type.replace('_', '-')}-${String(i).padStart(3, '0')}`,
      type,
      provider,
      env,
      owners: ['IT Ops', 'Cloud Ops'],
      ownership_status: ownershipStatus,
      authorization_reference: `AUTH-AUTO-${i}`,
      integration_id: provider === 'aws' ? 'int-aws' : provider === 'azure' ? 'int-azure' : null,
      tags: [env, type],
      criticality: i % 10 === 0 ? 'critical' : i % 5 === 0 ? 'high' : i % 3 === 0 ? 'medium' : 'low',
      region: provider === 'aws' ? 'us-east-1' : provider === 'azure' ? 'eastus' : 'us-central-1',
      status: assetStatuses[i % assetStatuses.length],
      created_at: daysAgo(Math.floor(Math.random() * 365)),
      updated_at: daysAgo(Math.floor(Math.random() * 30)),
    });
  }

  // ── Incidents (50+) ──────────────────────────────────────────────────────

  const HEADLINE_INCIDENT_ID = 'INC-0001';

  // Headline incident for demo
  const headlineInc: Incident = {
    id: HEADLINE_INCIDENT_ID,
    tenant_id: TENANT,
    title: 'APT-Style Identity Compromise + Lateral Movement — Finance Segment',
    description: 'Suspected APT actor compromised privileged admin account (admin.chen@szlholdings.com) via credential stuffing. Lateral movement detected to DC-EAST-01. Kerberoasting activity observed against 6 service accounts. C2 beaconing from WS-PROD-012 to known malicious IP.',
    severity: 'critical',
    status: 'investigating',
    mitre_techniques: ['T1078', 'T1003.001', 'T1558.003', 'T1071.001', 'T1021.002'],
    attack_vector: 'Credential Compromise',
    affected_assets: [
      { asset_id: 'ASSET-0001', asset_name: 'admin.chen@szlholdings.com', role: 'primary' },
      { asset_id: 'ASSET-0006', asset_name: 'WS-PROD-012', role: 'lateral' },
      { asset_id: 'ASSET-0007', asset_name: 'DC-EAST-01', role: 'lateral' },
    ],
    assigned_analyst: 'M. Chen',
    detection_source: 'Microsoft Sentinel (SIEM) — Stub Adapter',
    detected_at: hoursAgo(3),
    updated_at: minsAgo(15),
    timeline: [
      { id: 'TL-0001', timestamp: hoursAgo(3), actor: 'System', action: 'Incident detected and opened', detail: 'SIEM alert: Unusual sign-in location for admin.chen@szlholdings.com from TOR exit node', type: 'detection' },
      { id: 'TL-0002', timestamp: hoursAgo(2.8), actor: 'System', action: 'MITRE techniques mapped', detail: 'T1078 (Valid Accounts), T1003.001 (LSASS Memory)', type: 'system' },
      { id: 'TL-0003', timestamp: hoursAgo(2.5), actor: 'M. Chen', action: 'Triage completed', detail: 'Confirmed credential compromise. Lateral movement to DC-EAST-01 confirmed. P1 escalation.', type: 'analyst' },
      { id: 'TL-0004', timestamp: hoursAgo(2), actor: 'System', action: 'Enrichment completed', detail: 'Indicators: 45.142.212.x (Cobalt Strike C2, VirusTotal 48/72), 3 SPNs targeted for Kerberoasting', type: 'system' },
      { id: 'TL-0005', timestamp: hoursAgo(1.5), actor: 'M. Chen', action: 'Containment recommended', detail: 'Containment Recommender proposed: disable admin.chen identity, isolate WS-PROD-012, rotate affected service account passwords', type: 'analyst' },
    ],
    evidence_ids: [],
    approval_ids: [],
    report_ids: [],
    counsel_linked: false,
    tags: ['apt', 'credential-compromise', 'lateral-movement', 'p1'],
    attribution_draft: {
      suspected_actor: 'APT29 / Cozy Bear (suspected)',
      actor_catalog_ref: 'G0016',
      mitre_techniques: ['T1078', 'T1003.001', 'T1558.003'],
      indicators: ['45.142.212.x (C2)', 'LsassDump.exe SHA256:a3f1...c9e2', 'Kerberoasting pattern on SPN enumeration'],
      confidence: 'medium',
      reasoning: 'TTPs consistent with APT29 tradecraft: living-off-the-land, minimal footprint, targeting credentials and lateral movement before exfiltration. Nation-state attribution not confirmed.',
      drafted_by: 'Attribution Analyst (A11oy)',
      drafted_at: hoursAgo(1),
      human_reviewed: false,
    },
  };
  sentraStore.incidents.push(headlineInc);
  sentraStore.idCounters['INC'] = 1;
  sentraStore.idCounters['TL'] = 5;

  // Add evidence for headline incident
  const ev1 = sentraStore.addEvidence({
    incident_id: HEADLINE_INCIDENT_ID,
    tenant_id: TENANT,
    type: 'log_excerpt',
    source: 'Microsoft Sentinel (Stub Adapter)',
    file_name: 'signin_anomaly_admin_chen_20260505.json',
    sha256: sentraStore.simpleHash('signin-log-admin-chen-2026-evidence-001'),
    storage_uri: 'evidence://INC-0001/ev-001',
    collected_by: 'M. Chen',
    size_bytes: 14892,
    description: 'SIEM alert: Unusual sign-in from TOR exit node for privileged admin account',
  });
  const _ev2 = sentraStore.addEvidence({
    incident_id: HEADLINE_INCIDENT_ID,
    tenant_id: TENANT,
    type: 'artifact',
    source: 'CrowdStrike Falcon (Stub Adapter)',
    file_name: 'lsass_dump_WS-PROD-012_20260505.bin.enc',
    sha256: sentraStore.simpleHash('lsass-dump-artifact-WS-PROD-012-evidence-002'),
    storage_uri: 'evidence://INC-0001/ev-002',
    collected_by: 'System',
    size_bytes: 245760,
    description: 'Encrypted LSASS memory dump artifact — matched LockBit-adjacent SHA256 pattern',
  });
  sentraStore.lockEvidence(ev1.id, 'Evidence Custodian (A11oy)');

  // Add approval for headline incident
  const blastRadius = sentraStore.computeBlastRadius('ASSET-0001', 'revoke_owned_access');
  sentraStore.createApproval({
    tenant_id: TENANT,
    incident_id: HEADLINE_INCIDENT_ID,
    action_id: sentraStore.nextId('ACT'),
    action_class: 'revoke_owned_access',
    action_description: 'Disable identity: admin.chen@szlholdings.com — revoke all active sessions and MFA tokens',
    target_asset_id: 'ASSET-0001',
    target_asset_name: 'admin.chen@szlholdings.com',
    target_ownership_status: 'owned',
    integration_id: 'int-entra',
    requested_by: 'M. Chen',
    doctrine_citations: ['NIST SP 800-61r2 §3.2', 'CISA CIRCIA §3(a)', 'MITRE D3FEND D3-DA'],
    blast_radius_preview: blastRadius,
    rollback_path: 'Re-enable identity via Microsoft Entra admin portal — requires CISO approval',
    policy_class: 'revoke_owned_access',
  });

  // Generate 50+ total incidents
  const incidentData = [
    { title: 'Ransomware Staging — Shadow Copy Deletion + Encrypted Volume', severity: 'critical' as IncidentSeverity, status: 'contained' as IncidentStatus, mitre: ['T1490', 'T1486', 'T1078'], vec: 'Malware', analyst: 'K. Singh', asset: 'ASSET-0008', assetName: 'FS-CLUSTER-03', daysBack: 1 },
    { title: 'Supply Chain Compromise — Malicious npm Package in CI Pipeline', severity: 'high' as IncidentSeverity, status: 'recovery' as IncidentStatus, mitre: ['T1195.002', 'T1059', 'T1048.003'], vec: 'Supply Chain', analyst: 'J. Park', asset: 'ASSET-0009', assetName: 'BUILD-SRV-02', daysBack: 2 },
    { title: 'BEC Attack — CFO Impersonation Wire Transfer Attempt', severity: 'high' as IncidentSeverity, status: 'closed' as IncidentStatus, mitre: ['T1566.002', 'T1656'], vec: 'Social Engineering', analyst: 'A. Reyes', asset: 'ASSET-0002', assetName: 'cfo@szlholdings.com', daysBack: 3 },
    { title: 'Cloud IAM Escalation — Overprivileged Role Assumption AWS', severity: 'medium' as IncidentSeverity, status: 'closed' as IncidentStatus, mitre: ['T1078.004', 'T1530'], vec: 'Cloud Misconfiguration', analyst: 'M. Chen', asset: 'ASSET-0012', assetName: 'aws-prod-east-vpc', daysBack: 5 },
    { title: 'OT/SCADA C2 Beaconing — PLC Controller Anomalous Outbound Traffic', severity: 'critical' as IncidentSeverity, status: 'approval_pending' as IncidentStatus, mitre: ['T0858', 'T0845', 'T1071'], vec: 'OT Compromise', analyst: 'OT Security Team', asset: 'ASSET-0010', assetName: 'PLC-CTRL-003', daysBack: 0.5 },
    { title: 'Data Exfiltration Attempt — DNS Tunneling from Build Server', severity: 'high' as IncidentSeverity, status: 'contained' as IncidentStatus, mitre: ['T1048.001', 'T1071.004'], vec: 'Exfiltration', analyst: 'J. Park', asset: 'ASSET-0009', assetName: 'BUILD-SRV-02', daysBack: 4 },
    { title: 'Phishing Campaign — Executive Spear Phish with Credential Harvester', severity: 'high' as IncidentSeverity, status: 'triage' as IncidentStatus, mitre: ['T1566.001', 'T1056.003'], vec: 'Phishing', analyst: 'Security Ops', asset: 'ASSET-0002', assetName: 'cfo@szlholdings.com', daysBack: 0.2 },
    { title: 'Kerberoasting Attack — Service Account Credential Theft', severity: 'high' as IncidentSeverity, status: 'recovery' as IncidentStatus, mitre: ['T1558.003', 'T1078'], vec: 'Credential Access', analyst: 'M. Chen', asset: 'ASSET-0003', assetName: 'svc_backup@szlholdings.com', daysBack: 2 },
    { title: 'Container Escape — Privileged Pod on K8s Production Cluster', severity: 'critical' as IncidentSeverity, status: 'investigating' as IncidentStatus, mitre: ['T1611', 'T1610'], vec: 'Container Compromise', analyst: 'Cloud Security', asset: 'ASSET-0012', assetName: 'aws-prod-east-vpc', daysBack: 0.1 },
    { title: 'Secret Exposure — AWS Credentials Committed to Public GitHub Repo', severity: 'high' as IncidentSeverity, status: 'contained' as IncidentStatus, mitre: ['T1552.001', 'T1078.004'], vec: 'Secret Exposure', analyst: 'DevSecOps', asset: 'ASSET-0016', assetName: 'szlholdings/platform-core', daysBack: 6 },
  ];

  for (const inc of incidentData) {
    const incObj: Incident = {
      id: sentraStore.nextId('INC'),
      tenant_id: TENANT,
      title: inc.title,
      description: `${inc.title}. Detection source: SIEM alert (Stub Adapter). Investigation ongoing.`,
      severity: inc.severity,
      status: inc.status,
      mitre_techniques: inc.mitre,
      attack_vector: inc.vec,
      affected_assets: [{ asset_id: inc.asset, asset_name: inc.assetName, role: 'primary' }],
      assigned_analyst: inc.analyst,
      detection_source: 'Microsoft Sentinel (Stub Adapter)',
      detected_at: daysAgo(inc.daysBack),
      updated_at: daysAgo(inc.daysBack * 0.5),
      closed_at: inc.status === 'closed' ? daysAgo(inc.daysBack * 0.3) : undefined,
      timeline: [
        { id: sentraStore.nextId('TL'), timestamp: daysAgo(inc.daysBack), actor: 'System', action: 'Incident detected', detail: `Detection source: SIEM | Severity: ${inc.severity}`, type: 'detection' },
        { id: sentraStore.nextId('TL'), timestamp: daysAgo(inc.daysBack * 0.8), actor: inc.analyst, action: 'Triage completed', detail: 'Analyst confirmed incident validity', type: 'analyst' },
      ],
      evidence_ids: [],
      approval_ids: [],
      report_ids: [],
      counsel_linked: inc.status === 'closed' && inc.severity === 'critical',
      tags: [inc.vec.toLowerCase().replace(/\s+/g, '-'), inc.severity],
    };
    sentraStore.incidents.push(incObj);
  }

  // Fill to 50+ incidents
  const extraTitles = [
    'Privilege Escalation — Local Admin via Unpatched CVE-2024-38193',
    'Data Loss Prevention Alert — PII Transferred to External Storage',
    'Zero-Day Exploitation Attempt — Web Application Firewall Bypass',
    'Insider Threat — Unusual Data Access Pattern Finance Database',
    'Firmware Tampering — Network Device Configuration Change',
    'DDoS Mitigation — Volumetric Attack on Public-Facing API Gateway',
    'Certificate Pinning Bypass — MitM Attack on Mobile Client',
    'Log Tampering — Audit Log Clearing on Critical Server',
    'Unauthorized API Access — Service Account Token Misuse',
    'Malware Quarantine — Trojan Detected on Developer Workstation',
    'Cloud Storage ACL Misconfiguration — Public S3 Bucket Exposure',
    'Anomalous PowerShell Execution — Living-Off-the-Land Technique',
    'SQL Injection Attempt — Production Database Query Abuse',
    'Rogue Device Detection — Unauthorized Asset on Corporate Network',
    'OAuth Token Theft — Third-Party Application Compromise',
    'Backup Tampering — Scheduled Backup Job Modification',
    'Network Anomaly — Unexpected Lateral Movement on Segment VLAN-42',
    'Social Engineering — Vishing Attack Targeting IT Help Desk',
    'Remote Code Execution — Unpatched Apache Struts Vulnerability',
    'Cryptojacking — Unauthorized Crypto Mining on Cloud Instance',
    'Brute Force — RDP Targeted Against Jump Server',
    'Man-in-the-Middle — DNS Spoofing on Corporate WiFi',
    'Rootkit Installation — Kernel-Level Persistence Mechanism',
    'API Key Rotation Failure — Expired Credential in Production',
    'Supply Chain — Compromised Dependency in Third-Party Library',
    'Endpoint — Fileless Malware via Reflective DLL Injection',
    'Cloud — Cryptographic Key Exposed in Lambda Environment Variable',
    'Identity — Multi-Factor Authentication Bypass Attempt',
    'Network — Port Scanning from Internal Compromised Host',
    'Email — Domain Typosquatting Phishing Campaign',
    'Physical — Unauthorized USB Device on Secure Workstation',
    'Web — SSRF Vulnerability Exploitation in Production App',
    'Mobile — Sideloaded Application with Malware Payload',
    'AI — Prompt Injection Attack on Internal LLM Integration',
    'IoT — Smart Building Sensor Network Anomaly',
    'Container — Malicious Image Pulled from External Registry',
    'Database — Unauthorized Schema Modification Detected',
    'Git — Force Push to Protected Branch Override',
    'Serverless — Lambda Function Exfiltration via Environment Vars',
    'WAF Bypass — Obfuscated XSS Payload Evading Detection Rules',
  ];
  const extraStatuses: IncidentStatus[] = ['new', 'triage', 'investigating', 'contained', 'closed', 'reporting', 'recovery'];
  const extraSeverities: IncidentSeverity[] = ['critical', 'high', 'high', 'medium', 'medium', 'low'];
  for (let i = 0; i < extraTitles.length; i++) {
    const severity = extraSeverities[i % extraSeverities.length];
    const status = extraStatuses[i % extraStatuses.length];
    const assetIdx = (i % 20) + 1;
    sentraStore.incidents.push({
      id: sentraStore.nextId('INC'),
      tenant_id: TENANT,
      title: extraTitles[i],
      description: `${extraTitles[i]}. Under investigation by SOC team.`,
      severity,
      status,
      mitre_techniques: [`T${1000 + i * 13}`, `T${1500 + i * 7}`],
      attack_vector: 'Various',
      affected_assets: [{ asset_id: `ASSET-${String(assetIdx).padStart(4, '0')}`, asset_name: `asset-${assetIdx}`, role: 'primary' }],
      assigned_analyst: ['M. Chen', 'K. Singh', 'J. Park', 'A. Reyes', 'L. Torres'][i % 5],
      detection_source: 'Microsoft Sentinel (Stub Adapter)',
      detected_at: daysAgo(Math.floor(Math.random() * 30)),
      updated_at: daysAgo(Math.floor(Math.random() * 7)),
      closed_at: status === 'closed' ? daysAgo(1) : undefined,
      timeline: [
        { id: sentraStore.nextId('TL'), timestamp: daysAgo(3), actor: 'System', action: 'Incident detected', detail: `Source: SIEM | Severity: ${severity}`, type: 'detection' },
      ],
      evidence_ids: [],
      approval_ids: [],
      report_ids: [],
      counsel_linked: false,
      tags: [severity, status],
    });
  }

  // ── Approvals (100+) ──────────────────────────────────────────────────────

  const approvalTemplates = [
    { action_class: 'contain_owned_asset' as ActionClass, description: 'Isolate endpoint WS-PROD-012 from network', asset: 'ASSET-0006', assetName: 'WS-PROD-012', status: 'approved' as ApprovalStatus, reviewer: 'CISO', reason: 'Confirmed compromise, isolation required' },
    { action_class: 'revoke_owned_access' as ActionClass, description: 'Disable svc_backup service account — credential compromise confirmed', asset: 'ASSET-0003', assetName: 'svc_backup@szlholdings.com', status: 'approved' as ApprovalStatus, reviewer: 'IT Security Lead', reason: 'Kerberoasting confirmed' },
    { action_class: 'rotate_owned_secret' as ActionClass, description: 'Rotate production AWS access keys — potential exposure via git commit', asset: 'ASSET-0013', assetName: 'aws-s3-backup-prod', status: 'pending' as ApprovalStatus, reviewer: undefined, reason: undefined },
    { action_class: 'export_evidence' as ActionClass, description: 'Export evidence manifest for law enforcement referral', asset: 'ASSET-0001', assetName: 'admin.chen@szlholdings.com', status: 'pending' as ApprovalStatus, reviewer: undefined, reason: undefined },
    { action_class: 'contain_owned_asset' as ActionClass, description: 'Quarantine FS-CLUSTER-03 — ransomware staging confirmed', asset: 'ASSET-0008', assetName: 'FS-CLUSTER-03', status: 'approved' as ApprovalStatus, reviewer: 'Incident Commander', reason: 'Ransomware confirmed, isolation executed' },
    { action_class: 'revoke_owned_access' as ActionClass, description: 'Revoke OAuth tokens for svc_cicd — supply chain compromise', asset: 'ASSET-0004', assetName: 'svc_cicd@szlholdings.com', status: 'rejected' as ApprovalStatus, reviewer: 'DevSecOps Lead', reason: 'Alternative mitigation preferred — token rotation without full revocation' },
    { action_class: 'notify' as ActionClass, description: 'Send executive notification — critical incident P1', asset: 'ASSET-0007', assetName: 'DC-EAST-01', status: 'approved' as ApprovalStatus, reviewer: 'SOC Manager', reason: 'Executive notification required per incident response policy' },
    { action_class: 'generate_report' as ActionClass, description: 'Generate CISA CIRCIA law enforcement referral package', asset: 'ASSET-0001', assetName: 'admin.chen@szlholdings.com', status: 'pending' as ApprovalStatus, reviewer: undefined, reason: undefined },
  ];

  const incidentIds = sentraStore.incidents.map(i => i.id);
  for (let i = 0; i < approvalTemplates.length; i++) {
    const tmpl = approvalTemplates[i];
    const incId = incidentIds[i % incidentIds.length];
    const requestedAt = daysAgo(Math.random() * 5);
    const expiresAt = new Date(new Date(requestedAt).getTime() + 4 * 3600000).toISOString();
    const reviewedAt = tmpl.status !== 'pending' ? new Date(new Date(requestedAt).getTime() + 30 * 60000).toISOString() : undefined;
    const apr: Approval = {
      id: sentraStore.nextId('APR'),
      tenant_id: TENANT,
      incident_id: incId,
      action_id: sentraStore.nextId('ACT'),
      action_class: tmpl.action_class,
      action_description: tmpl.description,
      target_asset_id: tmpl.asset,
      target_asset_name: tmpl.assetName,
      target_ownership_status: 'owned',
      integration_id: 'int-entra',
      requested_by: 'M. Chen',
      requested_at: requestedAt,
      expires_at: expiresAt,
      status: tmpl.status,
      reviewed_by: tmpl.reviewer,
      reviewed_at: reviewedAt,
      review_reason: tmpl.reason,
      doctrine_citations: ['NIST SP 800-61r2 §3.3', 'CISA KEV', 'MITRE D3FEND'],
      blast_radius_preview: sentraStore.computeBlastRadius(tmpl.asset, tmpl.action_class),
      rollback_path: `Restore ${tmpl.assetName} via admin console — requires CISO sign-off`,
      policy_class: tmpl.action_class,
    };
    sentraStore.approvals.push(apr);
  }

  // Generate more approvals to reach 100+
  for (let i = 0; i < 92; i++) {
    const actionClasses: ActionClass[] = ['contain_owned_asset', 'revoke_owned_access', 'notify', 'preserve_evidence', 'generate_report'];
    const statuses: ApprovalStatus[] = ['approved', 'approved', 'rejected', 'pending', 'expired'];
    const ac = actionClasses[i % actionClasses.length];
    const status = statuses[i % statuses.length];
    const assetIdx = (i % 20) + 1;
    const requestedAt = daysAgo(Math.random() * 30);
    sentraStore.approvals.push({
      id: sentraStore.nextId('APR'),
      tenant_id: TENANT,
      incident_id: incidentIds[i % incidentIds.length],
      action_id: sentraStore.nextId('ACT'),
      action_class: ac,
      action_description: `${ac.replace(/_/g, ' ')} on asset-${assetIdx}`,
      target_asset_id: `ASSET-${String(assetIdx).padStart(4, '0')}`,
      target_asset_name: `asset-${assetIdx}`,
      target_ownership_status: 'owned',
      integration_id: null,
      requested_by: ['M. Chen', 'K. Singh', 'J. Park', 'System'][i % 4],
      requested_at: requestedAt,
      expires_at: new Date(new Date(requestedAt).getTime() + 4 * 3600000).toISOString(),
      status,
      reviewed_by: status !== 'pending' ? 'SOC Lead' : undefined,
      reviewed_at: status !== 'pending' ? new Date(new Date(requestedAt).getTime() + 1800000).toISOString() : undefined,
      review_reason: status === 'rejected' ? 'Insufficient justification' : status === 'approved' ? 'Approved — defensive action confirmed' : undefined,
      doctrine_citations: ['NIST SP 800-61r2'],
      blast_radius_preview: {
        unreachable_assets: [],
        revoked_sessions: i % 3,
        downstream_services: [],
        estimated_recovery_minutes: 10 + (i % 30),
        rollback_cost: 'low',
        description: `Impact assessment for ${ac} on asset-${assetIdx}`,
      },
      rollback_path: `Restore via admin console`,
      policy_class: ac,
    });
  }

  // ── Audit Entries (500+) ─────────────────────────────────────────────────

  const auditActions = [
    { actor: 'System', action: 'incident_detected', ac: 'detect', target: 'ASSET-0001', result: 'success' as const },
    { actor: 'M. Chen', action: 'incident_triaged', ac: 'update_case', target: 'ASSET-0001', result: 'success' as const },
    { actor: 'System', action: 'alert_generated', ac: 'alert', target: 'ASSET-0006', result: 'success' as const },
    { actor: 'K. Singh', action: 'evidence_collected', ac: 'preserve_evidence', target: 'ASSET-0008', result: 'success' as const },
    { actor: 'System', action: 'policy_evaluation', ac: 'detect', target: 'ASSET-0009', result: 'success' as const },
    { actor: 'J. Park', action: 'approval_requested', ac: 'contain_owned_asset', target: 'ASSET-0009', result: 'pending' as const },
    { actor: 'CISO', action: 'approval_granted', ac: 'contain_owned_asset', target: 'ASSET-0006', result: 'success' as const },
    { actor: 'System', action: 'containment_executed', ac: 'contain_owned_asset', target: 'ASSET-0006', result: 'success' as const },
    { actor: 'M. Chen', action: 'report_generated', ac: 'generate_report', target: 'ASSET-0001', result: 'success' as const },
    { actor: 'A11oy Triage Agent', action: 'incident_classified', ac: 'detect', target: 'ASSET-0001', result: 'success' as const },
    { actor: 'A11oy Evidence Custodian', action: 'evidence_locked', ac: 'preserve_evidence', target: 'ASSET-0010', result: 'success' as const },
    { actor: 'Safety Gate', action: 'action_blocked', ac: 'detect', target: 'ASSET-0021', result: 'failure' as const },
    { actor: 'A. Reyes', action: 'incident_closed', ac: 'update_case', target: 'ASSET-0002', result: 'success' as const },
    { actor: 'System', action: 'playbook_deployed', ac: 'update_case', target: 'ASSET-0001', result: 'success' as const },
    { actor: 'K. Singh', action: 'notification_sent', ac: 'notify', target: 'ASSET-0008', result: 'success' as const },
  ];

  // Seed 500+ audit entries
  let prevAuditHash = '0000000000000000';
  for (let i = 0; i < 500; i++) {
    const tmpl = auditActions[i % auditActions.length];
    const now2 = daysAgo(Math.random() * 60);
    const payload = JSON.stringify({ ...tmpl, timestamp: now2, prev_hash: prevAuditHash, idx: i });
    const entryHash = sentraStore.simpleHash(payload);
    const entry: AuditEntry = {
      id: sentraStore.nextId('AUD'),
      timestamp: now2,
      actor: tmpl.actor,
      action: tmpl.action,
      action_class: tmpl.ac,
      target_asset_id: tmpl.target,
      integration_id: i % 3 === 0 ? 'int-entra' : null,
      policy_decision: tmpl.result === 'failure' ? 'deny' : 'allow',
      approval_id: i % 5 === 0 ? `APR-${String((i % 8) + 1).padStart(4, '0')}` : null,
      execution_result: tmpl.result,
      evidence_hash: tmpl.ac === 'preserve_evidence' ? sentraStore.simpleHash(`evidence-${i}`) : null,
      rollback_reference: tmpl.ac === 'contain_owned_asset' ? `ROLLBACK-${i}` : null,
      notes: `Seeded audit entry ${i + 1}`,
      prev_hash: prevAuditHash,
      entry_hash: entryHash,
    };
    sentraStore.auditEntries.push(entry);
    prevAuditHash = entryHash;
  }

  // ── Playbooks ─────────────────────────────────────────────────────────────

  sentraStore.addPlaybook({
    incident_id: HEADLINE_INCIDENT_ID,
    title: 'Identity Compromise Response Playbook',
    description: 'Defensive playbook for identity compromise with lateral movement — generated by Containment Recommender (A11oy)',
    steps: [
      { id: 'step-1', order: 1, action_class: 'detect', description: 'Confirm identity compromise via SIEM correlation', requires_approval: false, requires_verification: true, on_success_step: 'step-2', status: 'completed', completed_at: hoursAgo(2), result: 'Confirmed: TOR-origin sign-in matched with LSASS dump pattern' },
      { id: 'step-2', order: 2, action_class: 'enrich', description: 'Enrich incident with threat intelligence — IOC lookup', requires_approval: false, requires_verification: false, on_success_step: 'step-3', status: 'completed', completed_at: hoursAgo(1.8), result: 'C2 IP confirmed malicious (VT 48/72). Kerberoasting pattern identified.' },
      { id: 'step-3', order: 3, action_class: 'revoke_owned_access', description: 'Disable compromised admin identity (admin.chen)', requires_approval: true, requires_verification: true, on_success_step: 'step-4', on_failure_step: 'step-3b', status: 'pending' },
      { id: 'step-4', order: 4, action_class: 'contain_owned_asset', description: 'Isolate WS-PROD-012 from network segment', requires_approval: true, requires_verification: true, on_success_step: 'step-5', status: 'pending' },
      { id: 'step-5', order: 5, action_class: 'preserve_evidence', description: 'Lock all collected evidence — chain-of-custody append', requires_approval: false, requires_verification: false, on_success_step: 'step-6', status: 'pending' },
      { id: 'step-6', order: 6, action_class: 'rotate_owned_secret', description: 'Rotate service account credentials affected by Kerberoasting', requires_approval: true, requires_verification: true, on_success_step: 'step-7', status: 'pending' },
      { id: 'step-7', order: 7, action_class: 'generate_report', description: 'Generate technical incident report + law enforcement referral', requires_approval: false, requires_verification: false, status: 'pending' },
    ],
    created_by: 'A11oy Containment Recommender',
    status: 'active',
    doctrine_citations: ['NIST SP 800-61r2 §3.2', 'NIST CSF 2.0 RC.AN', 'CISA CIRCIA §3(a)', 'MITRE D3FEND D3-DA', 'MITRE D3FEND D3-NI'],
  });
}

// Only seed once per module load. Hydrate from persisted snapshot if present;
// otherwise inject seed data and persist it as the new baseline.
let seeded = false;
export function ensureSeeded() {
  if (seeded) return;
  seeded = true;
  if (sentraStore.hydrate()) {
    // Refresh the cross-app status bridge immediately on hydrate so A11oy
    // sees current telemetry on first render, even before any new mutation.
    sentraStore.notify();
    return;
  }
  seedStore();
  sentraStore.persist();
  sentraStore.notify();
}

// Auto-seed on module import so data is present before first render
ensureSeeded();
