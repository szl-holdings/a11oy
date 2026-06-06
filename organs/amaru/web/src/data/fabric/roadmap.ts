import type { RoadmapPhase } from './types';

export const AMARU_ROADMAP: readonly RoadmapPhase[] = [
  {
    id: 'phase-1-discover',
    phase: 1,
    title: 'Discover',
    tagline: 'Bring every source under the spine.',
    description:
      'Cartographer connects warehouses, OLTP stores, event streams, object stores, and ticketing systems. PII is detected on first touch; freshness is monitored from the first refresh.',
    status: 'complete',
    capabilities: [
      'Source connectors (24 demo adapters, contract-typed)',
      'PII inference with redacted sampling',
      'Freshness clock per source',
      'Quality score baseline',
    ],
    verticalImpact: ['lyte', 'terra', 'vessels', 'counsel', 'carlota', 'aegis', 'sentra'],
    evidence: ['src.profile_v1 receipts', 'lutar Σ ≥ 0.74 across all green sources'],
  },
  {
    id: 'phase-2-model',
    phase: 2,
    title: 'Model',
    tagline: 'Compose entities the business actually uses.',
    description:
      'Cartographer + Mapper turn raw sources into entity-typed activation models with explicit fields, cursors, and quality. Every model is replay-grade.',
    status: 'complete',
    capabilities: ['Entity inference', 'SQL preview', 'Quality + PII scoring', 'Activation readiness rollup'],
    verticalImpact: ['lyte', 'terra', 'vessels', 'counsel', 'carlota', 'aegis', 'sentra'],
    evidence: ['model.candidate_v1', 'fields.classified_v1'],
  },
  {
    id: 'phase-3-govern',
    phase: 3,
    title: 'Govern',
    tagline: 'No batch ships without a witness.',
    description:
      'Sentinel evaluates every batch against the policy registry. Verity reconciles every acknowledgement. Scribe writes the proof ledger. The Lutar Σ envelope is computed per run.',
    status: 'active',
    capabilities: [
      'Policy registry (30+ policies)',
      'Approval queue with reason codes',
      'Hash-chained proof ledger',
      'Lutar Σ per run',
      'Evidence pack export',
    ],
    verticalImpact: ['counsel', 'aegis', 'sentra', 'lyte', 'vessels'],
    evidence: ['policy.checked_v1', 'receipt.decision_v1', 'sigil.composition_v1'],
  },
  {
    id: 'phase-4-activate',
    phase: 4,
    title: 'Activate',
    tagline: 'Move the receipt, not the rumour.',
    description:
      'Courier delivers governed batches into 36+ destinations across CRM, support, marketing, collab, data, webhook, finance, and logistics. Every batch carries its receipt.',
    status: 'active',
    capabilities: ['Batched delivery', 'Retry/backoff', 'Quarantine with evidence', 'Cross-destination idempotency keys'],
    verticalImpact: ['lyte', 'terra', 'vessels', 'counsel', 'carlota', 'aegis'],
    evidence: ['delivery.batch_v1', 'delivery.settled_v1'],
  },
  {
    id: 'phase-5-learn',
    phase: 5,
    title: 'Learn',
    tagline: 'Close the loop on lift.',
    description:
      'Forecaster predicts the lift each sync should produce on its destination KPI. The actual is observed and the prediction error is fed back into the cadence recommender.',
    status: 'planned',
    capabilities: ['Lift forecast', 'Prediction error tracking', 'Cadence recommender', 'Retirement review'],
    verticalImpact: ['lyte', 'terra', 'carlota'],
    evidence: ['outcome.forecast_v1', 'outcome.actual_v1'],
  },
  {
    id: 'phase-6-federate',
    phase: 6,
    title: 'Federate',
    tagline: 'One spine, many sovereign deployments.',
    description:
      'Amaru becomes a federation primitive: each tenant runs its own spine, shares only proofs and receipts. Cross-tenant policies are negotiated, not assumed.',
    status: 'planned',
    capabilities: ['Tenant-scoped spines', 'Federated proof exchange', 'Cross-tenant policy negotiation', 'Sovereign deployment recipes'],
    verticalImpact: ['counsel', 'aegis', 'sentra'],
    evidence: ['federation.handshake_v1', 'policy.negotiated_v1'],
  },
];
