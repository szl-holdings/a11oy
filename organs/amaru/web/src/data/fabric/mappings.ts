import type { RelayMapping, FieldMapping, GovernanceState, VerticalId, TransformKind } from './types';
import { RELAY_MODELS } from './models';
import { RELAY_DESTINATIONS } from './destinations';

const A = (h: string) => `0x${h}`.padEnd(12, '0');

// ── Deterministic LCG (seeded; no Math.random anywhere) ────────────────────
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

const TRANSFORM_BY_KIND: Record<string, TransformKind> = {
  email: 'lowercase',
  phone: 'format_date', // not literal — placeholder; we override below
  name: 'identity',
  address: 'identity',
  gov_id: 'redact',
  financial: 'identity',
  health: 'redact',
  none: 'identity',
};

interface Cross {
  modelId: string;
  destinationId: string;
  vertical: VerticalId;
  reason: string;
}

// Curated cross-product: each model gets 2–4 destination pairings that make
// sense for its entity type. ~70 mappings in total, no banned-name destinations.
const CROSSES: readonly Cross[] = [
  // Lyte ── 18
  { modelId: 'mdl-lyte-account', destinationId: 'dst-crm-activate', vertical: 'lyte', reason: 'GTM uses Activate as system of action' },
  { modelId: 'mdl-lyte-account', destinationId: 'dst-data-feature-store', vertical: 'lyte', reason: 'Account features for ML' },
  { modelId: 'mdl-lyte-account', destinationId: 'dst-fin-billing', vertical: 'lyte', reason: 'Billing requires legal entity mirror' },
  { modelId: 'mdl-lyte-invoice', destinationId: 'dst-fin-ledger', vertical: 'lyte', reason: 'GL posting' },
  { modelId: 'mdl-lyte-invoice', destinationId: 'dst-fin-coll', vertical: 'lyte', reason: 'Collections workflow' },
  { modelId: 'mdl-lyte-invoice', destinationId: 'dst-wh-finops', vertical: 'lyte', reason: 'Webhook fan-out' },
  { modelId: 'mdl-lyte-payment', destinationId: 'dst-fin-treasury', vertical: 'lyte', reason: 'Treasury reconciliation' },
  { modelId: 'mdl-lyte-payment', destinationId: 'dst-data-lakehouse', vertical: 'lyte', reason: 'Lakehouse mirror' },
  { modelId: 'mdl-lyte-churn-signal', destinationId: 'dst-crm-activate', vertical: 'lyte', reason: 'CSM activation' },
  { modelId: 'mdl-lyte-churn-signal', destinationId: 'dst-mkt-cadence', vertical: 'lyte', reason: 'Re-engagement cadence' },
  { modelId: 'mdl-lyte-pipeline', destinationId: 'dst-data-feature-store', vertical: 'lyte', reason: 'Pipeline KPIs to feature store' },
  { modelId: 'mdl-lyte-engagement', destinationId: 'dst-mkt-loop', vertical: 'lyte', reason: 'Engagement triggers nurture' },
  { modelId: 'mdl-lyte-engagement', destinationId: 'dst-data-feature-store', vertical: 'lyte', reason: 'Feature mirror' },
  { modelId: 'mdl-lyte-renewal', destinationId: 'dst-crm-activate', vertical: 'lyte', reason: 'Renewal opportunity' },
  { modelId: 'mdl-lyte-renewal', destinationId: 'dst-collab-tasks', vertical: 'lyte', reason: 'AE follow-up task' },
  { modelId: 'mdl-lyte-deal', destinationId: 'dst-crm-meridian', vertical: 'lyte', reason: 'Multi-CRM activation' },
  { modelId: 'mdl-lyte-deal', destinationId: 'dst-data-warehouse', vertical: 'lyte', reason: 'Warehouse mirror' },
  { modelId: 'mdl-lyte-deal', destinationId: 'dst-collab-slate', vertical: 'lyte', reason: 'Win/loss notifications' },

  // Terra ── 12
  { modelId: 'mdl-terra-asset', destinationId: 'dst-data-lakehouse', vertical: 'terra', reason: 'Portfolio mirror' },
  { modelId: 'mdl-terra-asset', destinationId: 'dst-collab-pages', vertical: 'terra', reason: 'Asset wiki' },
  { modelId: 'mdl-terra-inspection', destinationId: 'dst-collab-tasks', vertical: 'terra', reason: 'Remediation task' },
  { modelId: 'mdl-terra-inspection', destinationId: 'dst-collab-slate', vertical: 'terra', reason: 'Inspector channel' },
  { modelId: 'mdl-terra-listing', destinationId: 'dst-mkt-loop', vertical: 'terra', reason: 'Listing email blast' },
  { modelId: 'mdl-terra-tenant', destinationId: 'dst-crm-summit', vertical: 'terra', reason: 'Tenant CRM mirror (PII-gated)' },
  { modelId: 'mdl-terra-valuation', destinationId: 'dst-data-feature-store', vertical: 'terra', reason: 'AVM features' },
  { modelId: 'mdl-terra-valuation', destinationId: 'dst-fin-treasury', vertical: 'terra', reason: 'Mark-to-market reporting' },
  { modelId: 'mdl-terra-permit', destinationId: 'dst-collab-pages', vertical: 'terra', reason: 'Permit wiki' },
  { modelId: 'mdl-terra-permit', destinationId: 'dst-collab-slate', vertical: 'terra', reason: 'Permit status channel' },
  { modelId: 'mdl-terra-noi', destinationId: 'dst-fin-ledger', vertical: 'terra', reason: 'Post NOI to GL' },
  { modelId: 'mdl-terra-noi', destinationId: 'dst-data-feature-store', vertical: 'terra', reason: 'NOI features' },

  // Vessels ── 12
  { modelId: 'mdl-vessels-vessel', destinationId: 'dst-log-fleet-ops', vertical: 'vessels', reason: 'Fleet console mirror' },
  { modelId: 'mdl-vessels-vessel', destinationId: 'dst-data-lakehouse', vertical: 'vessels', reason: 'Fleet mirror' },
  { modelId: 'mdl-vessels-voyage', destinationId: 'dst-log-eta', vertical: 'vessels', reason: 'ETA broadcaster' },
  { modelId: 'mdl-vessels-voyage', destinationId: 'dst-log-port', vertical: 'vessels', reason: 'Port authority bridge' },
  { modelId: 'mdl-vessels-position', destinationId: 'dst-data-lakehouse', vertical: 'vessels', reason: 'Position mirror' },
  { modelId: 'mdl-vessels-shipment', destinationId: 'dst-log-customs', vertical: 'vessels', reason: 'Customs filing' },
  { modelId: 'mdl-vessels-shipment', destinationId: 'dst-fin-ledger', vertical: 'vessels', reason: 'Revenue recognition' },
  { modelId: 'mdl-vessels-port-call', destinationId: 'dst-log-port', vertical: 'vessels', reason: 'Port call event' },
  { modelId: 'mdl-vessels-ets', destinationId: 'dst-fin-treasury', vertical: 'vessels', reason: 'EUA liability' },
  { modelId: 'mdl-vessels-ets', destinationId: 'dst-data-warehouse', vertical: 'vessels', reason: 'ETS reporting mirror' },
  { modelId: 'mdl-vessels-incident', destinationId: 'dst-collab-slate', vertical: 'vessels', reason: 'On-call paging' },
  { modelId: 'mdl-vessels-incident', destinationId: 'dst-support-incident', vertical: 'vessels', reason: 'Incident bridge' },

  // Counsel ── 12
  { modelId: 'mdl-counsel-matter', destinationId: 'dst-data-lakehouse', vertical: 'counsel', reason: 'Matter mirror (privileged)' },
  { modelId: 'mdl-counsel-matter', destinationId: 'dst-collab-pages', vertical: 'counsel', reason: 'Matter brief wiki' },
  { modelId: 'mdl-counsel-deadline', destinationId: 'dst-collab-tasks', vertical: 'counsel', reason: 'Schedule prep' },
  { modelId: 'mdl-counsel-deadline', destinationId: 'dst-collab-slate', vertical: 'counsel', reason: 'Deadline channel' },
  { modelId: 'mdl-counsel-document', destinationId: 'dst-data-vector', vertical: 'counsel', reason: 'Privileged-aware index' },
  { modelId: 'mdl-counsel-document', destinationId: 'dst-data-lakehouse', vertical: 'counsel', reason: 'Sealed mirror' },
  { modelId: 'mdl-counsel-time-entry', destinationId: 'dst-fin-billing', vertical: 'counsel', reason: 'Billable mirror' },
  { modelId: 'mdl-counsel-billing', destinationId: 'dst-fin-ledger', vertical: 'counsel', reason: 'Receivables to GL' },
  { modelId: 'mdl-counsel-billing', destinationId: 'dst-fin-coll', vertical: 'counsel', reason: 'Collections' },
  { modelId: 'mdl-counsel-conflict', destinationId: 'dst-collab-slate', vertical: 'counsel', reason: 'Conflicts review channel' },
  { modelId: 'mdl-counsel-ticket', destinationId: 'dst-support-helpdesk', vertical: 'counsel', reason: 'Intake helpdesk' },
  { modelId: 'mdl-counsel-ticket', destinationId: 'dst-collab-tasks', vertical: 'counsel', reason: 'Triage task' },

  // Carlota ── 8
  { modelId: 'mdl-carlota-engagement', destinationId: 'dst-crm-summit', vertical: 'carlota', reason: 'Engagement CRM' },
  { modelId: 'mdl-carlota-engagement', destinationId: 'dst-mkt-cadence', vertical: 'carlota', reason: 'Nurture cadence' },
  { modelId: 'mdl-carlota-deliverable', destinationId: 'dst-collab-pages', vertical: 'carlota', reason: 'Client wiki delivery' },
  { modelId: 'mdl-carlota-stakeholder', destinationId: 'dst-crm-summit', vertical: 'carlota', reason: 'Stakeholder mirror (PII-gated)' },
  { modelId: 'mdl-carlota-brand', destinationId: 'dst-collab-deck', vertical: 'carlota', reason: 'Brand kit to deck studio' },
  { modelId: 'mdl-carlota-pulse', destinationId: 'dst-data-feature-store', vertical: 'carlota', reason: 'Pulse features' },
  { modelId: 'mdl-carlota-pulse', destinationId: 'dst-collab-slate', vertical: 'carlota', reason: 'Partner channel' },
  { modelId: 'mdl-carlota-campaign', destinationId: 'dst-data-feature-store', vertical: 'carlota', reason: 'Cost features for ROI' },

  // Aegis / Sentra ── 10
  { modelId: 'mdl-aegis-incident', destinationId: 'dst-wh-soc', vertical: 'aegis', reason: 'SOC bridge' },
  { modelId: 'mdl-aegis-incident', destinationId: 'dst-support-incident', vertical: 'aegis', reason: 'Incident bridge' },
  { modelId: 'mdl-aegis-asset', destinationId: 'dst-data-lakehouse', vertical: 'aegis', reason: 'Asset mirror' },
  { modelId: 'mdl-aegis-vuln', destinationId: 'dst-collab-tasks', vertical: 'aegis', reason: 'Patching task' },
  { modelId: 'mdl-aegis-vuln', destinationId: 'dst-data-feature-store', vertical: 'aegis', reason: 'Vuln features' },
  { modelId: 'mdl-sentra-detection', destinationId: 'dst-wh-soc', vertical: 'sentra', reason: 'Detection feed' },
  { modelId: 'mdl-sentra-detection', destinationId: 'dst-data-lakehouse', vertical: 'sentra', reason: 'Detection mirror' },
  { modelId: 'mdl-sentra-runbook', destinationId: 'dst-collab-slate', vertical: 'sentra', reason: 'Runbook channel' },
  { modelId: 'mdl-sentra-cvss-trend', destinationId: 'dst-data-feature-store', vertical: 'sentra', reason: 'CVSS trend features' },
  { modelId: 'mdl-sentra-coverage', destinationId: 'dst-collab-pages', vertical: 'sentra', reason: 'Coverage page' },

  // Cross-cutting ── 8
  { modelId: 'mdl-shared-contact', destinationId: 'dst-crm-activate', vertical: 'lyte', reason: 'Master contact mirror' },
  { modelId: 'mdl-shared-contact', destinationId: 'dst-mkt-loop', vertical: 'lyte', reason: 'Marketing mirror (PII-gated)' },
  { modelId: 'mdl-shared-ticket', destinationId: 'dst-support-helpdesk', vertical: 'lyte', reason: 'Helpdesk mirror' },
  { modelId: 'mdl-shared-incident', destinationId: 'dst-wh-soc', vertical: 'aegis', reason: 'SRE → SOC bridge' },
  { modelId: 'mdl-shared-event', destinationId: 'dst-data-lakehouse', vertical: 'lyte', reason: 'Product event mirror' },
  { modelId: 'mdl-shared-event', destinationId: 'dst-data-feature-store', vertical: 'lyte', reason: 'Event features' },
  { modelId: 'mdl-shared-acquisition', destinationId: 'dst-crm-meridian', vertical: 'lyte', reason: 'Diligence pipeline' },
  { modelId: 'mdl-shared-finance-snapshot', destinationId: 'dst-fin-treasury', vertical: 'lyte', reason: 'Treasury snapshot' },
];

function buildMapping(cross: Cross, idx: number): RelayMapping | null {
  const model = RELAY_MODELS.find((m) => m.id === cross.modelId);
  const dest = RELAY_DESTINATIONS.find((d) => d.id === cross.destinationId);
  if (!model || !dest) return null;
  const rng = lcg(0xa11_0a11 ^ (idx * 0x9e3779b1));
  const transformations: FieldMapping[] = model.fields.slice(0, Math.min(model.fields.length, 8)).map((f, fi) => {
    const isPii = f.piiClass !== 'none';
    const piiAllowed = dest.piiAllowed;
    let transform: TransformKind = TRANSFORM_BY_KIND[f.piiClass] ?? 'identity';
    let piiHandling: FieldMapping['piiHandling'] = 'pass';
    if (isPii && !piiAllowed) {
      transform = f.piiClass === 'email' || f.piiClass === 'phone' ? 'hash' : 'redact';
      piiHandling = transform === 'hash' ? 'hash' : 'redact';
    } else if (isPii) {
      piiHandling = 'pass';
    }
    if (f.piiClass === 'phone') transform = 'identity';
    const conf = 0.7 + rng() * 0.29;
    return {
      sourceField: f.name,
      destinationField: f.name === 'id' ? `${model.entityType}_id` : f.name,
      transform,
      confidence: Math.round(conf * 100) / 100,
      piiHandling,
      note:
        isPii && !piiAllowed
          ? 'Destination contract forbids PII — applying redaction'
          : isPii
            ? 'PII pass-through under contract'
            : `Direct ${transform}`,
    };
  });
  const piiBlocked = transformations.some((t) => t.piiHandling === 'redact' || t.piiHandling === 'hash');
  const piiPass = transformations.some((t) => t.piiHandling === 'pass' && (t.sourceField.includes('email') || t.sourceField.includes('name') || t.sourceField.includes('phone') || t.sourceField.includes('address')));
  const compatibility = Math.round(
    (model.qualityScore * 0.4 + dest.fieldContractStrength * 100 * 0.4 + (1 - model.piiScore) * 100 * 0.2),
  );
  const confidence = Math.round(transformations.reduce((s, t) => s + t.confidence, 0) / transformations.length * 100) / 100;
  const piiWarnings: string[] = [];
  if (piiBlocked) piiWarnings.push('Some PII fields auto-redacted/hashed for destination contract.');
  if (piiPass && model.piiFieldCount > 4) piiWarnings.push('High PII fan-out — review contract.');
  const qualityWarnings: string[] = [];
  if (model.qualityScore < 85) qualityWarnings.push('Source quality < 85; downstream confidence will be capped.');
  if (model.governanceState === 'amber') qualityWarnings.push('Source in governed-preview; review before promoting.');
  const approvalRequired = piiBlocked || piiPass || model.piiScore > 0.6 || dest.authState !== 'connected' || dest.governanceState === 'amber';
  let approvalReason: string | null = null;
  if (approvalRequired) {
    if (piiBlocked) approvalReason = 'PII redaction/hash applied';
    else if (piiPass) approvalReason = 'PII pass-through to permitted destination';
    else if (dest.authState !== 'connected') approvalReason = `Destination auth state is ${dest.authState}`;
    else approvalReason = 'Destination governance amber';
  }
  let governanceState: GovernanceState = 'green';
  if (model.governanceState === 'red' || dest.governanceState === 'red') governanceState = 'red';
  else if (model.governanceState === 'amber' || dest.governanceState === 'amber' || piiBlocked) governanceState = 'amber';
  const id = `map-${cross.modelId.replace('mdl-', '')}-to-${cross.destinationId.replace('dst-', '')}`;
  const proposedBy: RelayMapping['proposedBy'] =
    confidence >= 0.9 && !approvalRequired ? 'mapper-agent' : approvalRequired ? 'cartographer-suggestion' : 'operator';
  return {
    id,
    name: `${model.name} → ${dest.name}`,
    modelId: model.id,
    destinationId: dest.id,
    verticalId: cross.vertical,
    compatibilityScore: compatibility,
    confidence,
    mappedFieldCount: transformations.length,
    unmappedSourceFieldCount: Math.max(0, model.fieldCount - transformations.length),
    unmappedDestinationFieldCount: 0,
    transformations,
    qualityWarnings,
    piiWarnings,
    approvalRequired,
    approvalReason,
    governanceState,
    proposedBy,
    anchorHash: A((idx * 7 + 13).toString(16)),
  };
}

export const RELAY_MAPPINGS: readonly RelayMapping[] = CROSSES.map(buildMapping).filter(
  (m): m is RelayMapping => m !== null,
);
