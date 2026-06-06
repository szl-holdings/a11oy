import {
  type AutonomyMode,
  type EvidenceSource,
  type PolicyState,
  ProofEnvelope,
} from '@szl-holdings/design-system';
import { cn } from '@szl-holdings/shared-ui/utils';
import { Activity, CheckCircle2, FileText, ShieldAlert } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { DataStateBadge } from '@szl-holdings/shared-ui/data-state-badge';
import { sentraTwin as fallbackTwin, type ControlDrift as ControlDriftType } from '@/data/sentra-twin';
import { listCyberTwinControlDrifts } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';
import { toDataState, useSentraCoreLive } from '@/lib/use-sentra-core-live';

interface PostureDriftChange {
  control_id: string;
  name?: string;
  severity?: string;
  state?: string;
}

interface PostureDriftLive {
  lambda_score: number;
  added: PostureDriftChange[];
  removed: PostureDriftChange[];
  changed: PostureDriftChange[];
}

const ACCENT = '#f5f5f5';
const DRIFT_EVIDENCE: EvidenceSource[] = [
  {
    id: 'ev-ctrl-001',
    label: 'NIST CSF Gap Scanner — OT Segment',
    type: 'api',
    timestamp: new Date(Date.now() - 8 * 60_000).toISOString(),
    excerpt:
      'Respond family control RC.RP-1 failed automated playbook execution on legacy SCADA (SCADA-01, SCADA-02). 2 critical servers without verified backup integrity.',
  },
  {
    id: 'ev-ctrl-002',
    label: 'Signal Mesh — Control Drift Correlator',
    type: 'model',
    timestamp: new Date(Date.now() - 15 * 60_000).toISOString(),
    excerpt:
      'Correlated 3 control drift signals across Respond and Recover CSF families. Confidence 92% that gaps were exploited in current incident INC-2026-0891.',
  },
];

export default function ControlDrift() {
  const [autonomyMode, setAutonomyMode] = useState<AutonomyMode>('recommend');

  const fetcher = useCallback(() => listCyberTwinControlDrifts(), []);
  const { data: seedDrifts, source } = useApiQuery<ControlDriftType[]>(fetcher, 'controlDrifts', fallbackTwin.controlDrifts);

  // Build the posture-drift request body once per page mount. The hook
  // re-fetches whenever JSON.stringify(body) changes, so volatile values
  // like `new Date().toISOString()` would otherwise cause a request storm
  // on every render. Pinning the timestamps to mount-time keeps the
  // payload (and therefore the effect) stable.
  const livePostureBody = useMemo(() => {
    const mountedAt = Date.now();
    return {
      baseline: {
        snapshot_id: 'baseline-2026-05-01',
        captured_at: new Date(mountedAt - 14 * 86_400_000).toISOString(),
        controls: [
          { id: 'pr-ac-01', name: 'mfa-enforced', severity: 'critical' },
          { id: 'pr-ds-01', name: 'encryption-at-rest', severity: 'high' },
          { id: 'de-cm-01', name: 'edr-coverage', severity: 'high' },
        ],
      },
      current: {
        snapshot_id: 'current',
        captured_at: new Date(mountedAt).toISOString(),
        controls: [
          { id: 'pr-ac-01', name: 'mfa-enforced', severity: 'critical', state: 'partial' },
          { id: 'de-cm-01', name: 'edr-coverage', severity: 'high' },
        ],
      },
    };
  }, []);

  const livePosture = useSentraCoreLive<PostureDriftLive>({
    endpoint: '/posture-drift',
    body: livePostureBody,
  });
  const isLive = livePosture.source === 'live' && livePosture.data !== null;
  const pageState = isLive ? 'live' : toDataState(source);

  // Primary control-drift dataset: derived from the sentra-core posture_drift
  // response when the sidecar is live. The seeded twin is only used as a
  // fallback while the sidecar is unreachable (source === 'offline'/'seed').
  const FAMILY_BY_PREFIX: Record<string, ControlDriftType['family']> = {
    id: 'Identify',
    pr: 'Protect',
    de: 'Detect',
    rs: 'Respond',
    rc: 'Recover',
  };
  const liveDrifts: ControlDriftType[] =
    isLive && livePosture.data
      ? [...livePosture.data.removed, ...livePosture.data.changed].map((c, _i) => {
          const prefix = c.control_id.slice(0, 2).toLowerCase();
          const family = FAMILY_BY_PREFIX[prefix] ?? 'Protect';
          return {
            id: c.control_id,
            family,
            control: c.name ?? c.control_id,
            status: 'drift_detected',
            evidence:
              livePosture.data!.removed.includes(c)
                ? `Control ${c.control_id} removed from current posture snapshot (sentra-core Λ=${livePosture.data!.lambda_score.toFixed(2)}).`
                : `Control ${c.control_id} changed state to "${c.state ?? 'unknown'}" (sentra-core Λ=${livePosture.data!.lambda_score.toFixed(2)}).`,
          } as ControlDriftType;
        })
      : [];
  const controlDrifts = liveDrifts.length > 0 ? liveDrifts : seedDrifts;

  const familyNames = ['Identify', 'Protect', 'Detect', 'Respond', 'Recover'] as const;
  const families = familyNames.map((name) => {
    const matching = controlDrifts.filter((d) => d.family === name);
    const driftCount = matching.filter((d) => d.status === 'drift_detected').length;
    const totalCount =
      matching.length ||
      (name === 'Identify' ? 12 : name === 'Protect' ? 45 : name === 'Detect' ? 18 : name === 'Respond' ? 8 : 14);
    return { name, status: driftCount > 0 ? 'drift_detected' : 'compliant', count: totalCount, drift: driftCount };
  });

  return (
    <div className="space-y-8 animate-fade-in">
      <header>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-3xl font-display font-bold text-slate-100">Control Drift</h1>
          <DataStateBadge state={pageState} pulse={isLive} />
          {livePosture.data && (
            <span className="text-[10px] font-mono text-emerald-400">
              Λ = {livePosture.data.lambda_score.toFixed(2)}
            </span>
          )}
        </div>
        <p className="text-slate-400 mt-1">
          NIST CSF control family monitoring and drift detection · sourced live from sentra-core
          posture_drift.compute when available
        </p>
      </header>

      {livePosture.data && (
        <section className="sentra-panel p-5 space-y-4" data-testid="live-posture-summary">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">
                Live posture drift · sentra-core
              </div>
              <div className="text-2xl font-display font-bold text-slate-100 mt-1">
                Λ {livePosture.data.lambda_score.toFixed(3)}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-display font-bold text-emerald-300">{livePosture.data.added.length}</div>
                <div className="text-[9px] font-mono uppercase text-slate-500">Added</div>
              </div>
              <div>
                <div className="text-2xl font-display font-bold text-rose-300">{livePosture.data.removed.length}</div>
                <div className="text-[9px] font-mono uppercase text-slate-500">Removed</div>
              </div>
              <div>
                <div className="text-2xl font-display font-bold text-amber-300">{livePosture.data.changed.length}</div>
                <div className="text-[9px] font-mono uppercase text-slate-500">Changed</div>
              </div>
            </div>
          </div>
          {(livePosture.data.removed.length > 0 || livePosture.data.changed.length > 0) && (
            <ul className="space-y-1.5 text-xs font-mono text-slate-300">
              {livePosture.data.removed.map((c) => (
                <li key={`r-${c.control_id}`} className="flex items-center gap-2">
                  <span className="text-rose-400">REMOVED</span>
                  <span>{c.control_id}</span>
                  {c.name && <span className="text-slate-500">· {c.name}</span>}
                </li>
              ))}
              {livePosture.data.changed.map((c) => (
                <li key={`c-${c.control_id}`} className="flex items-center gap-2">
                  <span className="text-amber-400">CHANGED</span>
                  <span>{c.control_id}</span>
                  {c.state && <span className="text-slate-500">→ {c.state}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {families.map((family) => (
          <div key={family.name} className="sentra-panel p-4 text-center">
            <div className="text-[10px] text-slate-500 uppercase font-mono mb-2">{family.name}</div>
            <div
              className={cn(
                'text-2xl font-display font-bold mb-2',
                family.drift > 0 ? 'text-[#f5f5f5]' : 'text-[#c9b787]',
              )}
            >
              {family.drift > 0 ? family.drift : family.count}
            </div>
            <div className="text-[9px] font-mono text-slate-600">
              {family.drift > 0 ? 'DRIFT DETECTED' : 'CONTROLS OK'}
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-6">
        <h2 className="text-lg font-display font-bold text-slate-200">Active Drift Indicators</h2>

        <div className="space-y-4">
          {controlDrifts.map((drift, i) => (
            <div key={i} className="sentra-panel p-6">
              <div className="flex justify-between items-start">
                <div className="flex gap-4 flex-1">
                  <div className="w-12 h-12 rounded bg-[#f5f5f5]/10 flex items-center justify-center shrink-0">
                    <ShieldAlert className="w-6 h-6 text-[#f5f5f5]" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 font-mono uppercase tracking-widest">
                        {drift.family}
                      </span>
                      <h3 className="font-bold text-slate-100">{drift.control}</h3>
                    </div>
                    <p className="text-sm text-slate-400 mt-2 max-w-2xl">{drift.evidence}</p>

                    <div className="mt-6">
                      <h4 className="text-[10px] text-slate-500 uppercase font-mono font-bold mb-3">
                        Remediation Proof
                      </h4>
                      <ProofEnvelope
                        title="Automated Remediation — Deploy Respond Playbook"
                        accentColor={ACCENT}
                        evidence={DRIFT_EVIDENCE}
                        timestamp={DRIFT_EVIDENCE[0].timestamp}
                        confidence={92}
                        policyState={'requires-approval' as PolicyState}
                        autonomyMode={autonomyMode}
                        onAutonomyChange={setAutonomyMode}
                      >
                        <div className="p-4 bg-[#c9b787]/5 rounded border border-[#c9b787]/10 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <CheckCircle2 className="w-4 h-4 text-[#c9b787]" />
                            <div>
                              <div className="text-xs font-bold text-slate-200">
                                Automated Remediation Available
                              </div>
                              <p className="text-[10px] text-slate-500 mt-0.5">
                                Deploy baseline Respond playbook to OT firewall cluster.
                              </p>
                            </div>
                          </div>
                          <button className="px-4 py-1.5 rounded bg-[#c9b787] hover:bg-[#c9b787] text-white text-[11px] font-bold transition-colors">
                            Apply Fix
                          </button>
                        </div>
                      </ProofEnvelope>
                    </div>
                  </div>
                </div>
                <div className="text-right ml-4 shrink-0">
                  <div className="text-[10px] text-slate-500 font-mono uppercase">Detected</div>
                  <div className="text-xs font-bold text-slate-300">4h ago</div>
                  <div className="mt-4 flex flex-col items-end gap-2">
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <FileText className="w-3 h-3" />
                      NIST PR.IP-1
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400">
                      <Activity className="w-3 h-3" />
                      DRIFT MAGNITUDE: HIGH
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
