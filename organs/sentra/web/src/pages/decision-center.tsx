import { useStandardQuery } from '@szl-holdings/api-client-react';
import {
  type AutonomyMode,
  type EvidenceSource,
  type PolicyState,
  ProofEnvelope,
} from '@szl-holdings/design-system';
import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import { Activity, AlertTriangle, Cpu, ShieldAlert, Zap } from 'lucide-react';
import { useState } from 'react';

const ACCENT = '#f5f5f5';

interface NarrativeSignal {
  signalId: string;
  type: string;
  severity: string;
  occurredAt: string;
  freshness: number;
  confidence: number;
  tags: string[];
  rawPayload: Record<string, unknown>;
  entityRefs: { entityId: string; displayName: string }[];
}

interface NarrativeEvidence {
  evidenceId: string;
  type: string;
  summary: string;
  confidence: number;
  freshness: number;
  observedAt: string;
  signalId?: string;
}

interface NarrativeRecommendation {
  recommendationId: string;
  title: string;
  summary: string;
  rationale: string;
  suggestedAction: string;
  confidence: number;
  freshness: number;
  projectedImpact: string;
  projectedRisk: string;
  projectedImpactUsd: number;
  projectedRiskReductionPct: number;
  generatedAt: string;
  evidenceIds: string[];
  signalIds: string[];
  tags: string[];
}

interface NarrativePayload {
  id: string;
  title: string;
  org: string;
  fetchedAt: string;
  scenario: {
    name: string;
    summary: string;
    peakRiskExposureUsd: number;
    estimatedSavingsPerDayUsd: number;
  };
  signals: NarrativeSignal[];
  evidenceItems: NarrativeEvidence[];
  recommendation: NarrativeRecommendation;
}

const SIGNAL_ICONS: Record<string, typeof ShieldAlert> = {
  anomaly: ShieldAlert,
  'threshold-breach': AlertTriangle,
  drift: Cpu,
};

function severityClass(sev: string): string {
  if (sev === 'critical') return 'text-[#f5f5f5] border-[#f5f5f5]/40 bg-[#f5f5f5]/10';
  if (sev === 'high') return 'text-[#c9b787] border-[#c9b787]/40 bg-[#c9b787]/10';
  if (sev === 'medium') return 'text-[#c9b787] border-[#c9b787]/40 bg-[#c9b787]/10';
  return 'text-slate-400 border-slate-500/40 bg-slate-500/10';
}

export default function DecisionCenter() {
  const [autonomyMode, setAutonomyMode] = useState<AutonomyMode>('recommend');

  const { data, isLoading, error } = useStandardQuery<NarrativePayload>({
    queryKey: ['narratives', 'sentra-ransomware'],
    queryFn: () => apiFetch<NarrativePayload>('/narratives/sentra-ransomware', { skipAuth: true }),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in">
        <header>
          <h1 className="text-3xl font-display font-bold text-slate-100">Decision Center</h1>
          <p className="text-slate-400 mt-1">Loading live signal mesh…</p>
        </header>
        <div className="sentra-panel p-12 text-center text-slate-500 text-sm">
          Connecting to signal mesh…
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6 animate-fade-in">
        <header>
          <h1 className="text-3xl font-display font-bold text-slate-100">Decision Center</h1>
          <p className="text-[#f5f5f5] mt-1">Signal mesh unavailable.</p>
        </header>
        <div className="sentra-panel p-6 text-sm text-slate-400">
          {error instanceof Error ? error.message : 'Failed to fetch narrative payload.'}
        </div>
      </div>
    );
  }

  const { recommendation, signals, evidenceItems, scenario, fetchedAt } = data;

  const evidenceSources: EvidenceSource[] = evidenceItems.map((ev) => ({
    id: ev.evidenceId,
    label: ev.summary,
    type:
      ev.type === 'threat-intel' ? 'api' : ev.type === 'regulatory-rule' ? 'document' : 'signal',
    timestamp: ev.observedAt,
    excerpt: `${ev.summary} (confidence ${(ev.confidence * 100).toFixed(0)}%, freshness ${(ev.freshness * 100).toFixed(0)}%)`,
  }));

  const policyState: PolicyState =
    autonomyMode === 'approved-act' ? 'allowed' : 'requires-approval';

  return (
    <div className="space-y-8 animate-fade-in">
      <header className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-display font-bold text-slate-100">Decision Center</h1>
          <p className="text-slate-400 mt-1">{scenario.name} — live signal mesh recommendation</p>
        </div>
        <div className="px-4 py-2 rounded border border-[#f5f5f5]/40 bg-[#f5f5f5]/10 flex items-center gap-3">
          <Activity className="w-5 h-5 text-[#f5f5f5] animate-pulse" />
          <div className="text-right">
            <div className="text-[10px] text-[#f5f5f5] font-mono uppercase tracking-widest">
              Live Mesh
            </div>
            <div className="text-sm font-bold text-slate-100">
              {signals.length} signals · {evidenceItems.length} evidence
            </div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ProofEnvelope
            title={recommendation.title}
            accentColor={ACCENT}
            evidence={evidenceSources}
            timestamp={recommendation.generatedAt}
            confidence={recommendation.confidence}
            policyState={policyState}
            policyReason={
              autonomyMode === 'approved-act'
                ? 'Auto execution allowed in OT isolation policy band.'
                : 'Review required before isolating production OT assets.'
            }
            autonomyMode={autonomyMode}
            onAutonomyChange={setAutonomyMode}
            domain="sentra.ot-isolation"
            actionLabel={recommendation.suggestedAction}
          >
            <div className="space-y-4">
              <p className="text-sm text-slate-300 leading-relaxed">{recommendation.summary}</p>
              <div className="p-4 rounded bg-slate-900/60 border border-slate-700/40">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">
                  Rationale
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{recommendation.rationale}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded border border-[#c9b787]/20 bg-[#c9b787]/5">
                  <div className="text-[10px] uppercase tracking-widest text-[#c9b787] mb-1">
                    Projected Impact
                  </div>
                  <div className="text-lg font-bold text-[#c9b787]">
                    ${(recommendation.projectedImpactUsd / 1_000_000).toFixed(1)}M
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                    {recommendation.projectedImpact}
                  </p>
                </div>
                <div className="p-3 rounded border border-[#f5f5f5]/20 bg-[#f5f5f5]/5">
                  <div className="text-[10px] uppercase tracking-widest text-[#f5f5f5] mb-1">
                    Risk if Inaction
                  </div>
                  <div className="text-lg font-bold text-[#f5f5f5]">
                    -{recommendation.projectedRiskReductionPct}% risk reduction lost
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 leading-snug">
                    {recommendation.projectedRisk}
                  </p>
                </div>
              </div>
            </div>
          </ProofEnvelope>

          <div className="sentra-panel p-6">
            <h3 className="text-sm font-display font-bold text-slate-200 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-[#f5f5f5]" />
              Live Signal Stream — {signals.length} clustered
            </h3>
            <div className="space-y-3">
              {signals.map((s) => {
                const Icon = SIGNAL_ICONS[s.type] ?? ShieldAlert;
                return (
                  <div
                    key={s.signalId}
                    className="p-3 rounded bg-slate-900/40 border border-slate-700/40"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-2 flex-1">
                        <Icon className="w-4 h-4 text-[#f5f5f5] mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-slate-200 truncate">
                            {String(s.rawPayload.eventType ?? s.type)}
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {s.entityRefs.map((e) => e.displayName).join(', ') || '—'}
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${severityClass(s.severity)}`}
                        >
                          {s.severity}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {new Date(s.occurredAt).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {s.tags.map((t) => (
                        <span
                          key={t}
                          className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono uppercase"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="sentra-panel p-5">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">
              Scenario
            </div>
            <div className="text-sm font-bold text-slate-100 mb-2">{scenario.name}</div>
            <p className="text-xs text-slate-400 leading-relaxed">{scenario.summary}</p>
          </div>
          <div className="sentra-panel p-5 space-y-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">
                Peak Risk Exposure
              </div>
              <div className="text-2xl font-bold text-[#f5f5f5]">
                ${(scenario.peakRiskExposureUsd / 1_000_000).toFixed(1)}M
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">
                Cost Avoidance / Day
              </div>
              <div className="text-2xl font-bold text-[#c9b787]">
                ${(scenario.estimatedSavingsPerDayUsd / 1_000_000).toFixed(1)}M
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">
                AI Confidence
              </div>
              <div className="text-2xl font-bold text-slate-100">
                {(recommendation.confidence * 100).toFixed(0)}%
              </div>
            </div>
            <div className="pt-3 border-t border-slate-700/40 text-[10px] text-slate-500 font-mono">
              Mesh fetched {new Date(fetchedAt).toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
