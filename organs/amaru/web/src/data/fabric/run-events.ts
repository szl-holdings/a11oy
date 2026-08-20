import type { RelayRunEvent, RunEventType, AgentId, VerticalId, SeverityLevel } from './types';

// Deterministic LCG; no Math.random.
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

interface SyncSpec {
  id: string;
  name: string;
  destinationId: string;
  vertical: VerticalId;
  cadenceMin: number;
}

const SYNCS: readonly SyncSpec[] = [
  { id: 'sync-lyte-001', name: 'lyte.account → Activate CRM', destinationId: 'dst-crm-activate', vertical: 'lyte', cadenceMin: 15 },
  { id: 'sync-lyte-002', name: 'lyte.churn_signal → CSM Outreach', destinationId: 'dst-crm-activate', vertical: 'lyte', cadenceMin: 60 },
  { id: 'sync-lyte-003', name: 'lyte.invoice → Collections Hub', destinationId: 'dst-fin-coll', vertical: 'lyte', cadenceMin: 30 },
  { id: 'sync-lyte-004', name: 'lyte.payment → Treasury Sync', destinationId: 'dst-fin-treasury', vertical: 'lyte', cadenceMin: 5 },
  { id: 'sync-lyte-005', name: 'lyte.engagement → Loop Marketing', destinationId: 'dst-mkt-loop', vertical: 'lyte', cadenceMin: 30 },
  { id: 'sync-lyte-006', name: 'lyte.deal → Meridian CRM', destinationId: 'dst-crm-meridian', vertical: 'lyte', cadenceMin: 15 },
  { id: 'sync-lyte-007', name: 'lyte.renewal → Renewal Pipeline', destinationId: 'dst-crm-activate', vertical: 'lyte', cadenceMin: 60 },
  { id: 'sync-terra-001', name: 'terra.inspection → Tasks', destinationId: 'dst-collab-tasks', vertical: 'terra', cadenceMin: 60 },
  { id: 'sync-terra-002', name: 'terra.valuation → Feature Store', destinationId: 'dst-data-feature-store', vertical: 'terra', cadenceMin: 360 },
  { id: 'sync-terra-003', name: 'terra.tenant → Summit CRM', destinationId: 'dst-crm-summit', vertical: 'terra', cadenceMin: 60 },
  { id: 'sync-terra-004', name: 'terra.permit → Permit Channel', destinationId: 'dst-collab-slate', vertical: 'terra', cadenceMin: 60 },
  { id: 'sync-vessels-001', name: 'vessels.voyage → ETA Broadcaster', destinationId: 'dst-log-eta', vertical: 'vessels', cadenceMin: 5 },
  { id: 'sync-vessels-002', name: 'vessels.shipment → Customs Filing', destinationId: 'dst-log-customs', vertical: 'vessels', cadenceMin: 60 },
  { id: 'sync-vessels-003', name: 'vessels.position → Lakehouse', destinationId: 'dst-data-lakehouse', vertical: 'vessels', cadenceMin: 1 },
  { id: 'sync-vessels-004', name: 'vessels.incident → On-call', destinationId: 'dst-collab-slate', vertical: 'vessels', cadenceMin: 1 },
  { id: 'sync-counsel-001', name: 'counsel.deadline → Tasks', destinationId: 'dst-collab-tasks', vertical: 'counsel', cadenceMin: 60 },
  { id: 'sync-counsel-002', name: 'counsel.time_entry → Billing Mirror', destinationId: 'dst-fin-billing', vertical: 'counsel', cadenceMin: 30 },
  { id: 'sync-counsel-003', name: 'counsel.document → Vector Index', destinationId: 'dst-data-vector', vertical: 'counsel', cadenceMin: 60 },
  { id: 'sync-counsel-004', name: 'counsel.matter → Counsel Lakehouse', destinationId: 'dst-data-lakehouse', vertical: 'counsel', cadenceMin: 30 },
  { id: 'sync-carlota-001', name: 'carlota.engagement → Cadence', destinationId: 'dst-mkt-cadence', vertical: 'carlota', cadenceMin: 60 },
  { id: 'sync-carlota-002', name: 'carlota.pulse → Partner Channel', destinationId: 'dst-collab-slate', vertical: 'carlota', cadenceMin: 60 },
  { id: 'sync-carlota-003', name: 'carlota.deliverable → Pages', destinationId: 'dst-collab-pages', vertical: 'carlota', cadenceMin: 60 },
  { id: 'sync-aegis-001', name: 'aegis.incident → SOC Bridge', destinationId: 'dst-wh-soc', vertical: 'aegis', cadenceMin: 1 },
  { id: 'sync-aegis-002', name: 'aegis.vuln → Patching Tasks', destinationId: 'dst-collab-tasks', vertical: 'aegis', cadenceMin: 60 },
  { id: 'sync-sentra-001', name: 'sentra.detection → SOC Bridge', destinationId: 'dst-wh-soc', vertical: 'sentra', cadenceMin: 1 },
  { id: 'sync-sentra-002', name: 'sentra.runbook → Runbook Channel', destinationId: 'dst-collab-slate', vertical: 'sentra', cadenceMin: 5 },
];

const TYPE_FLOW: readonly RunEventType[] = [
  'planned',
  'approved',
  'started',
  'extracted',
  'transformed',
  'policy_checked',
  'delivered',
  'completed',
];

const FAILURE_CLASSES = ['auth_expired', 'rate_limit_exceeded', 'schema_drift', 'destination_5xx', 'pii_block'] as const;

const AGENT_BY_TYPE: Record<RunEventType, AgentId | null> = {
  planned: 'cartographer',
  approved: null,
  started: 'courier',
  extracted: 'courier',
  transformed: 'mapper',
  policy_checked: 'sentinel',
  delivered: 'courier',
  failed: 'fixer',
  retried: 'courier',
  quarantined: 'sentinel',
  rolled_back: 'fixer',
  completed: 'verity',
};

const SEVERITY_BY_TYPE: Record<RunEventType, SeverityLevel> = {
  planned: 'info',
  approved: 'info',
  started: 'info',
  extracted: 'info',
  transformed: 'info',
  policy_checked: 'low',
  delivered: 'info',
  failed: 'high',
  retried: 'medium',
  quarantined: 'high',
  rolled_back: 'critical',
  completed: 'info',
};

const SUMMARY: Record<RunEventType, string> = {
  planned: 'Cartographer planned batch',
  approved: 'Approval granted',
  started: 'Courier opened batch',
  extracted: 'Records extracted from source',
  transformed: 'Mapper applied transforms',
  policy_checked: 'Sentinel evaluated policies',
  delivered: 'Records delivered to destination',
  failed: 'Delivery failed',
  retried: 'Retry attempted with backoff',
  quarantined: 'Quarantined records flagged for review',
  rolled_back: 'Auto-rollback triggered',
  completed: 'Verity reconciled batch',
};

function shortHex(n: number) {
  return n.toString(16).padStart(8, '0').slice(0, 8);
}

function build(): readonly RelayRunEvent[] {
  const evts: RelayRunEvent[] = [];
  const now = Date.parse('2026-05-05T03:55:00Z');
  let chain = 0xa11_0a11;
  let id = 0;
  for (const sync of SYNCS) {
    const rng = lcg(0xc0d3_0a11 ^ (id * 0x9e3779b9));
    // Each sync produces 6–9 events covering its last few cycles.
    const cycleCount = 6 + Math.floor(rng() * 4);
    for (let c = 0; c < cycleCount; c++) {
      const baseAt = now - sync.cadenceMin * 60_000 * c - Math.floor(rng() * 30_000);
      // Inject one failure into ~1 in 8 cycles deterministically.
      const isFail = (id + c) % 8 === 0 && c !== 0;
      const flow: RunEventType[] = isFail
        ? ['planned', 'started', 'extracted', 'transformed', 'policy_checked', 'failed', 'retried', 'completed']
        : [...TYPE_FLOW];
      let stepOffset = 0;
      for (const t of flow) {
        const at = new Date(baseAt + stepOffset * 4_000).toISOString();
        const recordsAffected = t === 'extracted' || t === 'transformed' || t === 'delivered' || t === 'completed'
          ? 100 + Math.floor(rng() * 9_900)
          : 0;
        const latencyMs = t === 'started' || t === 'planned' ? 0 : 50 + Math.floor(rng() * 950);
        chain = (Math.imul(chain, 1664525) + 1013904223) >>> 0;
        const errorClass = t === 'failed' ? FAILURE_CLASSES[id % FAILURE_CLASSES.length] : null;
        evts.push({
          id: `evt-${shortHex(id)}-${c}-${t}`,
          syncId: sync.id,
          syncName: sync.name,
          destinationId: sync.destinationId,
          verticalId: sync.vertical,
          type: t,
          atIso: at,
          agentId: AGENT_BY_TYPE[t],
          summary: t === 'failed' ? `${SUMMARY[t]}: ${errorClass}` : SUMMARY[t],
          recordsAffected,
          latencyMs,
          stateHash: `0x${shortHex(chain)}`,
          evidenceRef: t === 'completed' || t === 'failed' || t === 'rolled_back' ? `evidence/${sync.id}/${c}` : null,
          severity: SEVERITY_BY_TYPE[t],
          errorClass,
        });
        stepOffset++;
      }
      id++;
    }
  }
  // Sort newest first.
  return evts.sort((a, b) => (a.atIso < b.atIso ? 1 : -1));
}

export const RELAY_RUN_EVENTS: readonly RelayRunEvent[] = build();
export const RELAY_SYNC_SPECS = SYNCS;
