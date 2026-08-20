/**
 * IncidentPipelineCard — operator-facing trigger for the end-to-end
 * Sentra incident → Guard Dog Brain optimizer → A11oy governance →
 * proof + research evolution pipeline.
 *
 * Incidents are sourced from Sentra's live incident stream
 * (listIncidents → /sentra/incidents) with the seeded sentraTwin catalog
 * as a fallback. The operator picks which real incident to enqueue;
 * a synthetic rehearsal incident is also offered so the pipeline can be
 * exercised when no real events are open.
 */
import { useEffect, useState } from 'react';
import { AlertOctagon, CheckCircle2, Loader2, ShieldX, XCircle, Zap } from 'lucide-react';
import { sentraTwin } from '@/data/sentra-twin';
import { listIncidents } from '@/lib/sentra-api';
import { useA11oyConstitution } from '@/brain/hooks/useA11oyConstitution';
import {
  runIncidentPipeline,
  type PipelineIncident,
  type PipelineRunResult,
  type PipelineStep,
} from '@/brain/lib/incidentPipeline';

const SYNTHETIC_INCIDENT: PipelineIncident = {
  id: 'inc-synth-001',
  title: 'Synthetic: Lateral movement on auth-service-prod',
  severity: 'high',
  mitreStage: 'Lateral Movement',
  detectedAt: new Date().toISOString(),
  description:
    'Synthetic rehearsal incident for end-to-end Guard Dog Brain pipeline exercise.',
  affectedAssets: ['auth-service-prod', 'identity-broker-01'],
};

function StatusIcon({ status }: { status: PipelineStep['status'] }) {
  if (status === 'ok') return <CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e]" />;
  if (status === 'running') return <Loader2 className="w-3.5 h-3.5 text-[#c9b787] animate-spin" />;
  if (status === 'blocked') return <ShieldX className="w-3.5 h-3.5 text-[#f59e0b]" />;
  if (status === 'error') return <XCircle className="w-3.5 h-3.5 text-[#ef4444]" />;
  return <div className="w-3.5 h-3.5 rounded-full border border-slate-600" />;
}

export function IncidentPipelineCard() {
  const { clauses, constitutionVersion, status: constitutionStatus } = useA11oyConstitution();
  const [incidents, setIncidents] = useState<PipelineIncident[]>([]);
  const [incidentSource, setIncidentSource] = useState<'live' | 'seed' | 'synthetic'>('synthetic');
  const [selectedId, setSelectedId] = useState<string>(SYNTHETIC_INCIDENT.id);
  const [steps, setSteps] = useState<PipelineStep[] | null>(null);
  const [result, setResult] = useState<PipelineRunResult | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { incidents: live, source } = await listIncidents();
        if (cancelled) return;
        if (live.length > 0) {
          setIncidents(live);
          setIncidentSource(source);
          setSelectedId(live[0].id);
          return;
        }
      } catch {
        // fall through to seed
      }
      if (cancelled) return;
      const seed = sentraTwin.incidents;
      if (seed.length > 0) {
        setIncidents(seed);
        setIncidentSource('seed');
        setSelectedId(seed[0].id);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const allOptions: PipelineIncident[] = [...incidents, SYNTHETIC_INCIDENT];
  const chosen = allOptions.find((i) => i.id === selectedId) ?? SYNTHETIC_INCIDENT;

  async function handleTrigger() {
    setRunning(true);
    setResult(null);
    setSteps(null);
    try {
      const source: 'live' | 'fallback' | 'seed' =
        constitutionStatus === 'live' ? 'live' : 'fallback';
      const r = await runIncidentPipeline({
        incident: chosen,
        constitution: clauses,
        constitutionVersion,
        constitutionSource: source,
        onStep: (s) => setSteps(s),
      });
      setResult(r);
      // Notify same-tab listeners (storage events do not fire in the writing
      // tab) so GuardDogBrainPanel and ResearchPage refresh immediately.
      window.dispatchEvent(new CustomEvent('sentra-brain-updated'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="sentra-panel p-5 space-y-4" data-testid="incident-pipeline-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#ef4444]/10 border border-[#ef4444]/20 flex items-center justify-center">
            <AlertOctagon className="w-4 h-4 text-[#ef4444]" />
          </div>
          <div>
            <div className="text-sm font-display font-bold text-slate-100">
              Incident Pipeline · End-to-End
            </div>
            <div className="text-[10px] text-slate-500 font-mono">
              Sentra incident → Optimizer → A11oy governance → Proof + Research
              {' · '}source: {incidentSource}
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={handleTrigger}
          disabled={running}
          data-testid="trigger-synthetic-incident"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#c9b787]/15 border border-[#c9b787]/30 text-[11px] font-mono uppercase tracking-wider text-[#c9b787] hover:bg-[#c9b787]/25 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {running ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
          {running ? 'Running' : 'Enqueue selected incident'}
        </button>
      </div>

      <label className="block">
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
          Incident to enqueue
        </span>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          data-testid="incident-selector"
          className="mt-1 w-full bg-slate-900/60 border border-slate-700/40 rounded px-2 py-1.5 text-[11px] text-slate-100 font-mono"
          disabled={running}
        >
          {allOptions.map((inc) => (
            <option key={inc.id} value={inc.id}>
              [{inc.severity}] {inc.id} · {inc.title}
            </option>
          ))}
        </select>
      </label>

      {steps && (
        <div className="space-y-1.5" data-testid="pipeline-steps">
          {steps.map((step) => (
            <div
              key={step.id}
              data-testid={`pipeline-step-${step.id}`}
              data-status={step.status}
              className="flex items-start gap-2 p-2 rounded bg-slate-900/40 border border-slate-700/30"
            >
              <div className="mt-0.5"><StatusIcon status={step.status} /></div>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] text-slate-200 font-medium">{step.label}</div>
                {step.detail && (
                  <div className="text-[10px] text-slate-500 font-mono truncate">{step.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {result && (
        <div
          className="rounded p-2.5 border text-[10px] font-mono"
          data-testid="pipeline-result"
          data-approved={String(result.approved)}
          style={{
            background: result.approved ? 'rgba(34,197,94,0.05)' : 'rgba(245,158,11,0.05)',
            borderColor: result.approved ? 'rgba(34,197,94,0.2)' : 'rgba(245,158,11,0.2)',
            color: result.approved ? '#22c55e' : '#f59e0b',
          }}
        >
          {result.approved
            ? `APPROVED · proof ${result.proofEntry?.id ?? '—'} · research ${result.researchEntry?.id ?? '—'}`
            : `BLOCKED · governance gate stopped the action`}
        </div>
      )}
    </div>
  );
}
