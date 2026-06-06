import type { VerticalPlaybook } from './types';

export const VERTICAL_PLAYBOOKS: readonly VerticalPlaybook[] = [
  {
    verticalId: 'terra',
    title: 'Terra — Real Estate Intelligence',
    route: '/terra/',
    accent: '#16a34a',
    entries: [
      { trigger: 'inspection.fail', modelId: 'mdl-terra-inspection', destinationId: 'dst-collab-tasks', action: 'Open remediation task with photos', governanceState: 'green' },
      { trigger: 'avm.delta > 5%', modelId: 'mdl-terra-valuation', destinationId: 'dst-data-feature-store', action: 'Refresh portfolio valuation features', governanceState: 'green' },
      { trigger: 'permit.denied', modelId: 'mdl-terra-permit', destinationId: 'dst-collab-slate', action: 'Notify project owner channel', governanceState: 'amber' },
      { trigger: 'noi.snapshot', modelId: 'mdl-terra-noi', destinationId: 'dst-fin-ledger', action: 'Post NOI to GL', governanceState: 'green' },
    ],
  },
  {
    verticalId: 'vessels',
    title: 'Vessels — Maritime Intelligence',
    route: '/vessels/',
    accent: '#0ea5e9',
    entries: [
      { trigger: 'eta.changed', modelId: 'mdl-vessels-voyage', destinationId: 'dst-log-eta', action: 'Broadcast revised ETA', governanceState: 'green' },
      { trigger: 'port_call.arrived', modelId: 'mdl-vessels-port-call', destinationId: 'dst-log-port', action: 'Open berth assignment workflow', governanceState: 'green' },
      { trigger: 'incident.opened severity>=high', modelId: 'mdl-vessels-incident', destinationId: 'dst-collab-slate', action: 'Page on-call ops', governanceState: 'green' },
      { trigger: 'ets.computed', modelId: 'mdl-vessels-ets', destinationId: 'dst-fin-treasury', action: 'Settle EU Allowance liability', governanceState: 'amber' },
    ],
  },
  {
    verticalId: 'counsel',
    title: 'Counsel — Legal Matter Command',
    route: '/counsel/',
    accent: '#a855f7',
    entries: [
      { trigger: 'deadline.7d_window', modelId: 'mdl-counsel-deadline', destinationId: 'dst-collab-tasks', action: 'Schedule responsible attorney prep', governanceState: 'green' },
      { trigger: 'conflict.review', modelId: 'mdl-counsel-conflict', destinationId: 'dst-collab-slate', action: 'Open conflicts review channel', governanceState: 'amber' },
      { trigger: 'time_entry.logged', modelId: 'mdl-counsel-time-entry', destinationId: 'dst-fin-billing', action: 'Mirror billable into billing system', governanceState: 'green' },
      { trigger: 'document.sealed', modelId: 'mdl-counsel-document', destinationId: 'dst-data-vector', action: 'Index for privileged-aware search', governanceState: 'amber' },
    ],
  },
  {
    verticalId: 'carlota',
    title: 'Carlota Jo Consulting',
    route: '/carlota-jo/',
    accent: '#f97316',
    entries: [
      { trigger: 'engagement.stage=proposal', modelId: 'mdl-carlota-engagement', destinationId: 'dst-mkt-cadence', action: 'Trigger nurture cadence', governanceState: 'green' },
      { trigger: 'pulse.score<0.4', modelId: 'mdl-carlota-pulse', destinationId: 'dst-collab-slate', action: 'Notify partner channel', governanceState: 'amber' },
      { trigger: 'deliverable.delivered', modelId: 'mdl-carlota-deliverable', destinationId: 'dst-collab-pages', action: 'Post deliverable to client wiki', governanceState: 'green' },
      { trigger: 'campaign.launched', modelId: 'mdl-carlota-campaign', destinationId: 'dst-data-feature-store', action: 'Capture cost features for ROI model', governanceState: 'green' },
    ],
  },
  {
    verticalId: 'aegis',
    title: 'Aegis / Sentra — Cyber Resilience',
    route: '/sentra/',
    accent: '#ef4444',
    entries: [
      { trigger: 'incident.severity>=high', modelId: 'mdl-aegis-incident', destinationId: 'dst-wh-soc', action: 'Page SOC bridge', governanceState: 'green' },
      { trigger: 'vuln.exploited', modelId: 'mdl-aegis-vuln', destinationId: 'dst-collab-tasks', action: 'Open patching task', governanceState: 'green' },
      { trigger: 'detection.fired', modelId: 'mdl-sentra-detection', destinationId: 'dst-support-incident', action: 'Mirror to incident bridge', governanceState: 'green' },
      { trigger: 'runbook.failed', modelId: 'mdl-sentra-runbook', destinationId: 'dst-collab-slate', action: 'Notify runbook author', governanceState: 'amber' },
    ],
  },
  {
    verticalId: 'lyte',
    title: 'Lyte — License Intelligence',
    route: '/lexicon/',
    accent: '#facc15',
    entries: [
      { trigger: 'churn.risk>0.7', modelId: 'mdl-lyte-churn-signal', destinationId: 'dst-crm-activate', action: 'Flag CSM for outreach', governanceState: 'green' },
      { trigger: 'invoice.past_due_14d', modelId: 'mdl-lyte-invoice', destinationId: 'dst-fin-coll', action: 'Trigger collections workflow', governanceState: 'amber' },
      { trigger: 'engagement.depth<0.2', modelId: 'mdl-lyte-engagement', destinationId: 'dst-mkt-cadence', action: 'Re-engagement nurture', governanceState: 'green' },
      { trigger: 'renewal.30d_window', modelId: 'mdl-lyte-renewal', destinationId: 'dst-crm-activate', action: 'Open renewal opportunity', governanceState: 'green' },
    ],
  },
];
