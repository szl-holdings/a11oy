// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/pages/control-evidence-graph.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardQuery } from '@szl-holdings/api-client-react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
  RefreshCw,
  Shield,
} from 'lucide-react';
import { useState } from 'react';

const API = import.meta.env.VITE_API_URL ?? '/api';

const DS = {
  surface: 'rgba(255,255,255,0.03)',
  border: 'rgba(255,255,255,0.07)',
  text: {
    primary: 'rgba(255,255,255,0.9)',
    secondary: 'rgba(255,255,255,0.55)',
    muted: 'rgba(255,255,255,0.28)',
  },
};

const FRESHNESS_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  fresh: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)', label: 'Fresh' },
  aging: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)', label: 'Aging' },
  'stale-90d': { color: '#f5f5f5', bg: 'rgba(245,245,245,0.08)', label: 'Stale' },
};

const EVIDENCE_TYPE_COLORS: Record<string, string> = {
  'log-collection': '#c9b787',
  'config-scan': '#8a8a8a',
  'penetration-test': '#f5f5f5',
  attestation: '#c9b787',
  'automated-check': '#8a8a8a',
  'audit-report': '#c9b787',
};

function FreshnessBar({ score }: { score: number }) {
  const color = score > 70 ? '#c9b787' : score > 40 ? '#c9b787' : '#f5f5f5';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="text-[10px] font-mono w-7 shrink-0" style={{ color }}>
        {score}
      </span>
    </div>
  );
}

export default function ControlEvidenceGraph() {
  const [expandedControl, setExpandedControl] = useState<number | null>(null);
  const [filterStatus, setFilterStatus] = useState<'all' | 'effective' | 'gap'>('all');

  // Live backend route — /firestorm/* path is an active api-server endpoint.
  // Follow-up task #1715 will rename it to /aegis/* once the server migration lands.
  const { data, isLoading, refetch, dataUpdatedAt } = useStandardQuery({
    queryKey: ['control-evidence-graph'],
    queryFn: async () => {
      const r = await fetch(`${API}/firestorm/cognitive/control-evidence-graph`, {
        credentials: 'include',
      });
      if (!r.ok) throw new Error('Failed to load control evidence graph');
      return r.json();
    },
    staleTime: 60_000,
    retry: 1,
  });

  const result = data?.data ?? {};
  const allControls: Array<{
    controlId: number;
    name: string;
    framework: string;
    category: string;
    status: 'effective' | 'gap';
    freshnessScore: number;
    lastVerified: string;
    nextReviewDue: string;
    evidenceItems: Array<{
      id: string;
      type: string;
      description: string;
      collectedAt: string;
      collectedBy: string;
      freshnessStatus: string;
      verifiedBy: string;
      traceRef: string;
    }>;
    provenance: { source: string; traceId: string };
  }> = result.controls ?? [];
  const summary = result.summary ?? {};
  const provenance = result.provenance ?? {};

  const controls =
    filterStatus === 'all' ? allControls : allControls.filter((c) => c.status === filterStatus);

  return (
    <div className="p-6 space-y-6" style={{ maxWidth: 1280, margin: '0 auto' }}>
      <div className="flex items-start justify-between">
        <div>
          <h1
            className="text-xl font-bold flex items-center gap-2"
            style={{ color: DS.text.primary }}
          >
            <Shield className="w-5 h-5 text-[#c9b787]" />
            Control Evidence Graph
          </h1>
          <p className="text-sm mt-1" style={{ color: DS.text.secondary }}>
            Each control linked to evidence proving effectiveness, with freshness scoring and
            verification chains.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
          style={{
            background: 'rgba(201,183,135,0.08)',
            color: '#c9b787',
            border: '1px solid rgba(201,183,135,0.2)',
          }}
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Controls', value: summary.totalControls, color: 'text-[#c9b787]' },
          { label: 'Effective', value: summary.effectiveControls, color: 'text-[#c9b787]' },
          { label: 'Gaps', value: summary.gapControls, color: 'text-[#f5f5f5]' },
          {
            label: 'Avg Freshness',
            value: summary.avgFreshnessScore != null ? `${summary.avgFreshnessScore}%` : '—',
            color: 'text-[#c9b787]',
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="rounded-xl p-4"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <p className="text-[11px] mb-1" style={{ color: DS.text.muted }}>
              {label}
            </p>
            {isLoading ? (
              <div className="h-7 w-14 rounded animate-pulse" style={{ background: DS.border }} />
            ) : (
              <p className={cn('text-2xl font-bold', color)}>{value ?? '—'}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        {(['all', 'effective', 'gap'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilterStatus(f)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize"
            style={
              filterStatus === f
                ? {
                    background: 'rgba(201,183,135,0.1)',
                    color: '#c9b787',
                    border: '1px solid rgba(201,183,135,0.25)',
                  }
                : { background: DS.surface, color: DS.text.muted, border: `1px solid ${DS.border}` }
            }
          >
            {f}{' '}
            {f !== 'all' && (
              <span className="ml-1 opacity-60">
                {f === 'effective'
                  ? (summary.effectiveControls ?? '')
                  : (summary.gapControls ?? '')}
              </span>
            )}
          </button>
        ))}
        <span className="ml-auto text-[10px]" style={{ color: DS.text.muted }}>
          {controls.length} controls · {summary.totalEvidenceItems ?? 0} evidence items
        </span>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-[#c9b787]/40 border-t-emerald-400 rounded-full animate-spin" />
        </div>
      ) : (
        <div className="space-y-2">
          {controls.map((ctrl) => {
            const isExpanded = expandedControl === ctrl.controlId;
            const staleCount = ctrl.evidenceItems.filter(
              (e) => e.freshnessStatus === 'stale-90d',
            ).length;
            return (
              <div
                key={ctrl.controlId}
                className="rounded-xl overflow-hidden transition-all"
                style={{
                  background: DS.surface,
                  border: `1px solid ${ctrl.status === 'gap' ? 'rgba(245,245,245,0.2)' : DS.border}`,
                }}
              >
                <button
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
                  onClick={() => setExpandedControl(isExpanded ? null : ctrl.controlId)}
                >
                  <div className="shrink-0">
                    {ctrl.status === 'effective' ? (
                      <CheckCircle className="w-4 h-4 text-[#c9b787]" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-[#f5f5f5]" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p
                        className="text-sm font-medium truncate"
                        style={{ color: DS.text.primary }}
                      >
                        {ctrl.name}
                      </p>
                      <Badge
                        className={cn(
                          'text-[9px] shrink-0',
                          ctrl.status === 'effective'
                            ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20'
                            : 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20',
                        )}
                      >
                        {ctrl.status}
                      </Badge>
                      {staleCount > 0 && (
                        <Badge className="text-[9px] shrink-0 bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/20">
                          {staleCount} stale
                        </Badge>
                      )}
                    </div>
                    <div
                      className="flex items-center gap-4 text-[10px]"
                      style={{ color: DS.text.muted }}
                    >
                      <span>{ctrl.framework}</span>
                      <span>{ctrl.category}</span>
                      <span>{ctrl.evidenceItems.length} evidence items</span>
                    </div>
                  </div>
                  <div className="w-32 shrink-0">
                    <p className="text-[9px] mb-1" style={{ color: DS.text.muted }}>
                      Freshness
                    </p>
                    <FreshnessBar score={ctrl.freshnessScore} />
                  </div>
                  <div
                    className="text-[10px] text-right shrink-0 mr-2"
                    style={{ color: DS.text.muted }}
                  >
                    <p>{new Date(ctrl.lastVerified).toLocaleDateString()}</p>
                    <p>verified</p>
                  </div>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 shrink-0" style={{ color: DS.text.muted }} />
                  ) : (
                    <ChevronRight className="w-4 h-4 shrink-0" style={{ color: DS.text.muted }} />
                  )}
                </button>

                {isExpanded && (
                  <div
                    className="px-4 pb-4 space-y-3"
                    style={{ borderTop: `1px solid ${DS.border}` }}
                  >
                    <h4
                      className="text-[10px] font-semibold uppercase tracking-widest pt-3"
                      style={{ color: DS.text.muted }}
                    >
                      Evidence Items
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                      {ctrl.evidenceItems.map((ev) => {
                        const fc = FRESHNESS_CONFIG[ev.freshnessStatus] ?? FRESHNESS_CONFIG.fresh;
                        const typeColor = EVIDENCE_TYPE_COLORS[ev.type] ?? '#94a3b8';
                        return (
                          <div
                            key={ev.id}
                            className="p-3 rounded-lg space-y-1.5"
                            style={{
                              background: 'rgba(255,255,255,0.02)',
                              border: `1px solid ${DS.border}`,
                            }}
                          >
                            <div className="flex items-center gap-2">
                              <FileText className="w-3 h-3 shrink-0" style={{ color: typeColor }} />
                              <span
                                className="text-[10px] font-medium"
                                style={{ color: typeColor }}
                              >
                                {ev.type.replace(/-/g, ' ')}
                              </span>
                              <span
                                className="ml-auto text-[9px] px-1.5 py-0.5 rounded"
                                style={{ background: fc.bg, color: fc.color }}
                              >
                                {fc.label}
                              </span>
                            </div>
                            <p className="text-[10px]" style={{ color: DS.text.secondary }}>
                              {ev.description}
                            </p>
                            <div
                              className="flex items-center justify-between text-[9px]"
                              style={{ color: DS.text.muted }}
                            >
                              <span>
                                {ev.collectedBy === 'automated' ? '⚡ automated' : '👤 analyst'}
                              </span>
                              <span className="font-mono">{ev.traceRef}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div
                      className="flex items-center gap-2 text-[10px] pt-1"
                      style={{ color: DS.text.muted }}
                    >
                      <Eye className="w-3 h-3" />
                      <span>Verified by: {ctrl.provenance?.source}</span>
                      <span className="font-mono ml-auto">{ctrl.provenance?.traceId}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-center gap-6 text-[10px] pt-2" style={{ color: DS.text.muted }}>
        <Activity className="w-3 h-3" />
        <span>Verified by: {provenance.verifiedBy ?? 'Compliance Evidence Engine'}</span>
        <span>Runtime: {provenance.cognitiveRuntime ?? 'v2.1.0'}</span>
        {dataUpdatedAt > 0 && <span>Updated: {new Date(dataUpdatedAt).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
