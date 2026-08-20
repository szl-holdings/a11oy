import type { RelayDestination, DestinationOp, EntityType } from './types';

const A = (h: string) => `0x${h}`.padEnd(12, '0');

interface Spec {
  id: string;
  name: string;
  category: RelayDestination['category'];
  accent: string;
  ops: readonly DestinationOp[];
  entities: readonly EntityType[];
  rate: RelayDestination['rateLimit'];
  rpm: number;
  auth: RelayDestination['authState'];
  rotates: string | null;
  pii: boolean;
  contract: number;
  obs: number;
  health: number;
  state: RelayDestination['governanceState'];
  hash: string;
}

const SPECS: readonly Spec[] = [
  // CRM (5)
  { id: 'dst-crm-activate', name: 'Activate CRM', category: 'crm', accent: '#3b82f6', ops: ['upsert','update'], entities: ['contact','account','lead','opportunity'], rate: 'moderate', rpm: 600, auth: 'connected', rotates: '2026-08-01T00:00:00Z', pii: true, contract: 0.94, obs: 0.92, health: 96, state: 'green', hash: A('d11111') },
  { id: 'dst-crm-meridian', name: 'Meridian CRM', category: 'crm', accent: '#6366f1', ops: ['upsert','update','delete'], entities: ['contact','account','lead','opportunity'], rate: 'strict', rpm: 240, auth: 'connected', rotates: '2026-07-15T00:00:00Z', pii: true, contract: 0.9, obs: 0.88, health: 92, state: 'green', hash: A('d11112') },
  { id: 'dst-crm-summit', name: 'Summit CRM', category: 'crm', accent: '#0ea5e9', ops: ['upsert'], entities: ['contact','account'], rate: 'lenient', rpm: 1200, auth: 'connected', rotates: null, pii: true, contract: 0.86, obs: 0.84, health: 90, state: 'green', hash: A('d11113') },
  { id: 'dst-crm-northwind', name: 'Northwind Sales', category: 'crm', accent: '#22d3ee', ops: ['upsert','update'], entities: ['account','opportunity'], rate: 'moderate', rpm: 480, auth: 'expiring', rotates: '2026-05-12T00:00:00Z', pii: true, contract: 0.88, obs: 0.78, health: 78, state: 'amber', hash: A('d11114') },
  { id: 'dst-crm-aegis', name: 'Aegis Account Mirror', category: 'crm', accent: '#94a3b8', ops: ['upsert'], entities: ['account'], rate: 'tight', rpm: 120, auth: 'connected', rotates: null, pii: false, contract: 0.95, obs: 0.96, health: 94, state: 'green', hash: A('d11115') },
  // Support (4)
  { id: 'dst-support-helpdesk', name: 'Helpdesk Cloud', category: 'support', accent: '#10b981', ops: ['upsert','update'], entities: ['ticket','contact'], rate: 'moderate', rpm: 600, auth: 'connected', rotates: '2026-09-01T00:00:00Z', pii: true, contract: 0.9, obs: 0.88, health: 92, state: 'green', hash: A('d22221') },
  { id: 'dst-support-resolve', name: 'Resolve Hub', category: 'support', accent: '#22c55e', ops: ['upsert','update'], entities: ['ticket'], rate: 'strict', rpm: 240, auth: 'connected', rotates: '2026-06-30T00:00:00Z', pii: true, contract: 0.87, obs: 0.85, health: 88, state: 'green', hash: A('d22222') },
  { id: 'dst-support-pulse', name: 'Pulse Tickets', category: 'support', accent: '#16a34a', ops: ['upsert'], entities: ['ticket'], rate: 'lenient', rpm: 900, auth: 'rotation_required', rotates: '2026-05-08T00:00:00Z', pii: true, contract: 0.82, obs: 0.7, health: 64, state: 'red', hash: A('d22223') },
  { id: 'dst-support-incident', name: 'Incident Bridge', category: 'support', accent: '#84cc16', ops: ['upsert','event'], entities: ['incident'], rate: 'moderate', rpm: 360, auth: 'connected', rotates: null, pii: false, contract: 0.93, obs: 0.94, health: 95, state: 'green', hash: A('d22224') },
  // Marketing / Engagement (5)
  { id: 'dst-mkt-loop', name: 'Loop Marketing', category: 'marketing', accent: '#f97316', ops: ['upsert','update'], entities: ['contact'], rate: 'moderate', rpm: 480, auth: 'connected', rotates: '2026-07-01T00:00:00Z', pii: true, contract: 0.88, obs: 0.82, health: 86, state: 'green', hash: A('d33331') },
  { id: 'dst-mkt-cadence', name: 'Cadence Email', category: 'marketing', accent: '#fb923c', ops: ['upsert'], entities: ['contact'], rate: 'lenient', rpm: 1500, auth: 'connected', rotates: null, pii: true, contract: 0.84, obs: 0.78, health: 82, state: 'green', hash: A('d33332') },
  { id: 'dst-mkt-orbital', name: 'Orbital Ads', category: 'marketing', accent: '#fbbf24', ops: ['upsert','delete'], entities: ['contact'], rate: 'tight', rpm: 60, auth: 'connected', rotates: '2026-06-15T00:00:00Z', pii: true, contract: 0.79, obs: 0.74, health: 70, state: 'amber', hash: A('d33333') },
  { id: 'dst-mkt-paid-social', name: 'Paid Social Mirror', category: 'marketing', accent: '#facc15', ops: ['upsert'], entities: ['contact'], rate: 'tight', rpm: 60, auth: 'connected', rotates: '2026-06-01T00:00:00Z', pii: true, contract: 0.74, obs: 0.7, health: 64, state: 'amber', hash: A('d33334') },
  { id: 'dst-mkt-sms', name: 'Compliant SMS', category: 'marketing', accent: '#eab308', ops: ['upsert'], entities: ['contact'], rate: 'moderate', rpm: 300, auth: 'expired', rotates: '2026-05-04T00:00:00Z', pii: true, contract: 0.86, obs: 0.6, health: 38, state: 'red', hash: A('d33335') },
  // Collab (5)
  { id: 'dst-collab-slate', name: 'Slate Channels', category: 'collab', accent: '#a855f7', ops: ['event'], entities: ['event','incident'], rate: 'lenient', rpm: 600, auth: 'connected', rotates: '2026-09-01T00:00:00Z', pii: false, contract: 0.93, obs: 0.92, health: 96, state: 'green', hash: A('d44441') },
  { id: 'dst-collab-pages', name: 'Pages Wiki', category: 'collab', accent: '#9333ea', ops: ['upsert'], entities: ['document'], rate: 'moderate', rpm: 240, auth: 'connected', rotates: null, pii: false, contract: 0.9, obs: 0.86, health: 92, state: 'green', hash: A('d44442') },
  { id: 'dst-collab-tasks', name: 'Tasks Sync', category: 'collab', accent: '#7c3aed', ops: ['upsert','update'], entities: ['ticket'], rate: 'moderate', rpm: 360, auth: 'connected', rotates: '2026-08-01T00:00:00Z', pii: false, contract: 0.91, obs: 0.88, health: 92, state: 'green', hash: A('d44443') },
  { id: 'dst-collab-deck', name: 'Deck Studio', category: 'collab', accent: '#6d28d9', ops: ['upsert'], entities: ['document'], rate: 'lenient', rpm: 480, auth: 'connected', rotates: null, pii: false, contract: 0.84, obs: 0.78, health: 82, state: 'green', hash: A('d44444') },
  { id: 'dst-collab-docs', name: 'Docs Mirror', category: 'collab', accent: '#5b21b6', ops: ['upsert','update'], entities: ['document'], rate: 'moderate', rpm: 300, auth: 'connected', rotates: '2026-07-15T00:00:00Z', pii: false, contract: 0.87, obs: 0.84, health: 88, state: 'green', hash: A('d44445') },
  // Data / Warehouse (5)
  { id: 'dst-data-lakehouse', name: 'Sovereign Lakehouse', category: 'data', accent: '#06b6d4', ops: ['mirror'], entities: ['account','opportunity','ticket','event','kpi_snapshot'], rate: 'lenient', rpm: 6000, auth: 'connected', rotates: null, pii: true, contract: 0.96, obs: 0.95, health: 97, state: 'green', hash: A('d55551') },
  { id: 'dst-data-warehouse', name: 'Glacier Warehouse Mirror', category: 'data', accent: '#0891b2', ops: ['mirror'], entities: ['account','opportunity','ticket'], rate: 'lenient', rpm: 4800, auth: 'connected', rotates: null, pii: true, contract: 0.94, obs: 0.92, health: 94, state: 'green', hash: A('d55552') },
  { id: 'dst-data-feature-store', name: 'Feature Store', category: 'data', accent: '#0e7490', ops: ['upsert'], entities: ['kpi_snapshot'], rate: 'moderate', rpm: 1200, auth: 'connected', rotates: '2026-09-30T00:00:00Z', pii: false, contract: 0.93, obs: 0.9, health: 93, state: 'green', hash: A('d55553') },
  { id: 'dst-data-vector', name: 'Vector Index', category: 'data', accent: '#155e75', ops: ['upsert','delete'], entities: ['document','event'], rate: 'moderate', rpm: 600, auth: 'connected', rotates: null, pii: false, contract: 0.85, obs: 0.78, health: 84, state: 'green', hash: A('d55554') },
  { id: 'dst-data-replica', name: 'OLTP Replica', category: 'data', accent: '#164e63', ops: ['mirror'], entities: ['account','opportunity','ticket'], rate: 'moderate', rpm: 900, auth: 'connected', rotates: null, pii: true, contract: 0.91, obs: 0.88, health: 90, state: 'green', hash: A('d55555') },
  // Webhook (4)
  { id: 'dst-wh-realtime', name: 'Realtime Webhook', category: 'webhook', accent: '#ec4899', ops: ['event'], entities: ['event','incident'], rate: 'lenient', rpm: 6000, auth: 'connected', rotates: null, pii: false, contract: 0.84, obs: 0.7, health: 84, state: 'green', hash: A('d66661') },
  { id: 'dst-wh-finops', name: 'FinOps Notification', category: 'webhook', accent: '#db2777', ops: ['event'], entities: ['invoice','event'], rate: 'moderate', rpm: 600, auth: 'connected', rotates: '2026-08-15T00:00:00Z', pii: true, contract: 0.88, obs: 0.82, health: 88, state: 'green', hash: A('d66662') },
  { id: 'dst-wh-soc', name: 'SOC Bridge', category: 'webhook', accent: '#be185d', ops: ['event'], entities: ['incident','event'], rate: 'lenient', rpm: 3000, auth: 'connected', rotates: null, pii: false, contract: 0.94, obs: 0.95, health: 96, state: 'green', hash: A('d66663') },
  { id: 'dst-wh-audit', name: 'Audit Webhook', category: 'webhook', accent: '#9d174d', ops: ['event'], entities: ['event'], rate: 'tight', rpm: 60, auth: 'untested', rotates: '2026-05-20T00:00:00Z', pii: false, contract: 0.7, obs: 0.6, health: 56, state: 'amber', hash: A('d66664') },
  // Finance (4)
  { id: 'dst-fin-ledger', name: 'General Ledger', category: 'finance', accent: '#facc15', ops: ['upsert'], entities: ['invoice'], rate: 'moderate', rpm: 240, auth: 'connected', rotates: '2026-07-01T00:00:00Z', pii: true, contract: 0.95, obs: 0.92, health: 95, state: 'green', hash: A('d77771') },
  { id: 'dst-fin-billing', name: 'Billing Mirror', category: 'finance', accent: '#eab308', ops: ['upsert','update'], entities: ['invoice','account'], rate: 'moderate', rpm: 300, auth: 'connected', rotates: null, pii: true, contract: 0.93, obs: 0.9, health: 92, state: 'green', hash: A('d77772') },
  { id: 'dst-fin-treasury', name: 'Treasury Sync', category: 'finance', accent: '#ca8a04', ops: ['upsert'], entities: ['kpi_snapshot'], rate: 'tight', rpm: 60, auth: 'connected', rotates: '2026-06-30T00:00:00Z', pii: false, contract: 0.92, obs: 0.88, health: 92, state: 'green', hash: A('d77773') },
  { id: 'dst-fin-coll', name: 'Collections Hub', category: 'finance', accent: '#a16207', ops: ['upsert'], entities: ['invoice','contact'], rate: 'moderate', rpm: 180, auth: 'connected', rotates: null, pii: true, contract: 0.86, obs: 0.82, health: 86, state: 'green', hash: A('d77774') },
  // Logistics (4)
  { id: 'dst-log-fleet-ops', name: 'Fleet Ops Console', category: 'logistics', accent: '#0ea5e9', ops: ['upsert'], entities: ['shipment','voyage','asset'], rate: 'moderate', rpm: 360, auth: 'connected', rotates: '2026-08-01T00:00:00Z', pii: false, contract: 0.92, obs: 0.9, health: 93, state: 'green', hash: A('d88881') },
  { id: 'dst-log-port', name: 'Port Authority Bridge', category: 'logistics', accent: '#0284c7', ops: ['upsert','event'], entities: ['voyage','event'], rate: 'tight', rpm: 60, auth: 'connected', rotates: '2026-07-01T00:00:00Z', pii: false, contract: 0.88, obs: 0.84, health: 88, state: 'green', hash: A('d88882') },
  { id: 'dst-log-customs', name: 'Customs Filing', category: 'logistics', accent: '#0369a1', ops: ['upsert'], entities: ['shipment'], rate: 'tight', rpm: 30, auth: 'expiring', rotates: '2026-05-30T00:00:00Z', pii: true, contract: 0.83, obs: 0.78, health: 76, state: 'amber', hash: A('d88883') },
  { id: 'dst-log-eta', name: 'ETA Broadcaster', category: 'logistics', accent: '#075985', ops: ['event'], entities: ['voyage','event'], rate: 'lenient', rpm: 1200, auth: 'connected', rotates: null, pii: false, contract: 0.86, obs: 0.84, health: 88, state: 'green', hash: A('d88884') },
];

export const RELAY_DESTINATIONS: readonly RelayDestination[] = SPECS.map((s) => ({
  id: s.id,
  name: s.name,
  category: s.category,
  accent: s.accent,
  supportedOps: s.ops,
  supportedEntityTypes: s.entities,
  rateLimit: s.rate,
  rateLimitRpm: s.rpm,
  authState: s.auth,
  authRotatesAt: s.rotates,
  piiAllowed: s.pii,
  fieldContractStrength: s.contract,
  observabilityCoverage: s.obs,
  healthScore: s.health,
  governanceState: s.state,
  anchorHash: s.hash,
}));
