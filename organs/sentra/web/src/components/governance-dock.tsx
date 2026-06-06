/**
 * Sentra — Governance Dock
 *
 * Phase 13 UX Normalization adoption: surfaces the shared @szl-holdings/omnia-shell
 * governance components on the Sentra trust & provenance surface so SOC operators
 * can see policy posture, incident evidence, ownership and deployment context
 * in the same enterprise-minimal language used across every SZL domain pack.
 */

import {
  DeploymentContext,
  OmniaEvidencePanel,
  OmniaTimeline,
  OwnershipMeta,
  PolicySummaryBar,
  StatusChipGroup,
  type EvidenceEntry,
  type TimelineEvent,
} from '@szl-holdings/omnia-shell';

const NOW = new Date();
const minutesAgo = (m: number) => new Date(NOW.getTime() - m * 60_000).toISOString();

const EVIDENCE: EvidenceEntry[] = [
  {
    id: 'ev-1',
    type: 'signal',
    label: 'EDR: lateral movement attempt (host srv-fe-04)',
    value: 'severity high',
    timestamp: minutesAgo(28),
    confidence: 0.94,
    domain: 'cyber',
  },
  {
    id: 'ev-2',
    type: 'derivation',
    label: 'Threat-actor cluster match: APT-39 tradecraft',
    timestamp: minutesAgo(26),
    confidence: 0.79,
    author: 'sentra-threat-engine',
    domain: 'cyber',
  },
  {
    id: 'ev-3',
    type: 'policy',
    label: 'OPA: szl.cyber.containment.auto-isolate',
    value: 'requires-approval',
    timestamp: minutesAgo(25),
    domain: 'cyber',
  },
  {
    id: 'ev-4',
    type: 'approval',
    label: 'On-call approver granted containment',
    timestamp: minutesAgo(22),
    author: 'soc-lead@szl.io',
    domain: 'cyber',
  },
  {
    id: 'ev-5',
    type: 'agent',
    label: 'Agent draft: incident retrospective',
    timestamp: minutesAgo(15),
    confidence: 0.83,
    author: 'agent-gateway',
    domain: 'cyber',
  },
];

const TIMELINE: TimelineEvent[] = [
  { id: 't1', label: 'EDR signal raised', timestamp: minutesAgo(28), severity: 'critical' },
  { id: 't2', label: 'Auto-triage classified', timestamp: minutesAgo(27), severity: 'warning' },
  { id: 't3', label: 'Containment proposed', timestamp: minutesAgo(25), severity: 'warning' },
  { id: 't4', label: 'Operator approved', timestamp: minutesAgo(22), severity: 'success' },
  { id: 't5', label: 'Host isolated, ticket opened', timestamp: minutesAgo(20), severity: 'info' },
  { id: 't6', label: 'Retrospective draft ready', timestamp: minutesAgo(15), severity: 'info' },
];

export function GovernanceDock() {
  return (
    <section className="space-y-6 mt-10">
      <header>
        <h2 className="text-xl font-display font-bold text-slate-100">Governance Dock</h2>
        <p className="text-slate-400 mt-1 text-sm">
          Shared OMNIA shell surface — policy posture, incident evidence, ownership, deployment.
        </p>
      </header>

      <StatusChipGroup
        chips={[
          { status: 'critical', label: '1 active incident', pulsing: true },
          { status: 'enforced', label: 'OPA policies' },
          { status: 'healthy', label: 'EDR sensors' },
          { status: 'advisory', label: 'Agent gateway' },
        ]}
      />

      <PolicySummaryBar
        policies={[
          { id: 'cyber.containment', name: 'Auto-isolate (high)', status: 'requires-approval' },
          { id: 'cyber.threat-intel', name: 'Threat-intel feed', status: 'enforced' },
          { id: 'cyber.retro', name: 'Retro draft', status: 'advisory' },
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OmniaEvidencePanel
          title="Active incident — evidence chain"
          entries={EVIDENCE}
          correlationId="sentra-2026-05-03-9d2a"
          auditId="audit-9d2a14"
        />
        <OmniaTimeline title="Incident timeline (last 30m)" events={TIMELINE} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OwnershipMeta
          ownerTeam="sentra-soc-team"
          system="Sentra Cyber Resilience Command"
          domain="cyber"
          lifecycle="production"
          healthEndpoint="/health"
          runbookUrl="https://backstage.szl/catalog/component/sentra/runbook"
          scorecard={{ score: 91, scale: 100 }}
          lastDeploy={minutesAgo(60 * 14)}
        />
        <DeploymentContext
          environment="production"
          deploymentStatus="healthy"
          version="2026.05.02-r9"
          uptimeSeconds={60 * 60 * 72}
          probes={[
            { name: 'web', status: 'healthy', latencyMs: 38 },
            { name: 'soc-api', status: 'healthy', latencyMs: 22 },
            { name: 'edr-stream', status: 'healthy', latencyMs: 14 },
          ]}
          slo={{ name: 'mttd', target: 95, current: 97.2 }}
        />
      </div>
    </section>
  );
}

export default GovernanceDock;
