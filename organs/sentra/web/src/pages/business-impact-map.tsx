// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/business-impact-map.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardQuery } from '@szl-holdings/api-client-react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Building2,
  ChevronDown,
  ChevronRight,
  DollarSign,
  FileText,
  RefreshCw,
  Shield,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';
import { AccessDeniedNotice, HttpError, isAccessDenied } from '../components/AccessDeniedNotice';
import { CognitiveBreadcrumbs } from '../components/CognitiveBreadcrumbs';
import { CopyLinkButton } from '../components/CopyLinkButton';
import { useDrilldown } from '../lib/cognitive-nav';

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

const ENTITY_TYPE_COLORS: Record<string, string> = {
  revenue: '#c9b787',
  operations: '#c9b787',
  data: '#8a8a8a',
  'supply-chain': '#c9b787',
  compliance: '#8a8a8a',
  brand: '#c9b787',
};

const ENTITY_ICONS: Record<string, typeof Building2> = {
  revenue: DollarSign,
  operations: Activity,
  data: Shield,
  'supply-chain': BarChart3,
  compliance: FileText,
  brand: TrendingUp,
};

const SEV_CONFIG: Record<string, { color: string; bg: string }> = {
  critical: { color: '#f5f5f5', bg: 'rgba(245,245,245,0.08)' },
  high: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)' },
  medium: { color: '#8a8a8a', bg: 'rgba(138,138,138,0.08)' },
  low: { color: '#c9b787', bg: 'rgba(201,183,135,0.08)' },
};

function fmt(n: number | null | undefined) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

export default function BusinessImpactMap() {
  const [expandedIncident, setExpandedIncident] = useState<number | null>(null);
  const drilldown = useDrilldown();

  // Live backend route — /firestorm/* path is an active api-server endpoint.
  // Follow-up task #1715 will rename it to /aegis/* once the server migration lands.
  const { data, isLoading, error, refetch, dataUpdatedAt } = useStandardQuery({
    queryKey: ['business-impact-map'],
    queryFn: async () => {
      const r = await fetch(`${API}/firestorm/cognitive/business-impact-map`, {
        credentials: 'include',
      });
      if (!r.ok) throw new HttpError(r.status, 'Failed to load business impact map');
      return r.json();
    },
    staleTime: 60_000,
    retry: (failureCount, err) => !isAccessDenied(err) && failureCount < 1,
  });

  const denied = isAccessDenied(error);

  const result = data?.data ?? {};
  const execNarrative = result.execNarrative ?? {};
  const businessEntities: Array<{
    id: string;
    name: string;
    type: string;
    owner: string;
    annualRevenue: number | null;
    atRisk: number | null;
  }> = result.businessEntities ?? [];
  const incidentImpacts: Array<{
    incidentId: number;
    title: string;
    severity: string;
    status: string;
    estimatedFinancialImpact: number;
    estimatedDowntimeHours: number;
    affectedEntities: Array<{
      entityId: string;
      entityName: string;
      entityType: string;
      impactType: string;
      businessRiskScore: number;
    }>;
    citations: Array<{ source: string; ref: string; confidence: number }>;
    provenance: { source: string; traceRef: string };
  }> = result.incidentImpacts ?? [];
  const findingImpacts: Array<{
    findingId: number;
    title: string;
    severity: string;
    businessEntity: { id: string; name: string; type: string };
    complianceExposure: string;
    estimatedFineExposure: number;
    citations: Array<{ source: string; ref: string; confidence: number }>;
  }> = result.findingImpacts ?? [];
  const provenance = result.provenance ?? {};

  const riskTrendColor =
    execNarrative.riskTrend === 'increasing'
      ? 'text-[#f5f5f5]'
      : execNarrative.riskTrend === 'decreasing'
        ? 'text-[#c9b787]'
        : 'text-[#c9b787]';

  return (
    <div className="p-6 space-y-6" style={{ maxWidth: 1280, margin: '0 auto' }}>
      <CognitiveBreadcrumbs accent="#c9b787" />
      <div className="flex items-start justify-between">
        <div>
          <h1
            className="text-xl font-bold flex items-center gap-2"
            style={{ color: DS.text.primary }}
          >
            <TrendingUp className="w-5 h-5 text-[#c9b787]" />
            Business Impact Map
          </h1>
          <p className="text-sm mt-1" style={{ color: DS.text.secondary }}>
            Incidents and risks tied to revenue and operations entities — executive-ready narrative
            with evidence provenance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <CopyLinkButton accent="#c9b787" />
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
      </div>

      {denied && (
        <AccessDeniedNotice
          status={(error as HttpError).status}
          accent="#c9b787"
          resourceLabel="the business impact map"
        />
      )}

      {!denied && !isLoading && execNarrative.executiveSummary && (
        <div
          className="rounded-xl p-5 space-y-4"
          style={{ background: 'rgba(201,183,135,0.04)', border: '1px solid rgba(201,183,135,0.15)' }}
        >
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#c9b787]" />
            <h2 className="text-sm font-semibold" style={{ color: DS.text.primary }}>
              Executive Narrative
            </h2>
            <Badge className="ml-auto text-[9px] bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20">
              Verified
            </Badge>
          </div>
          <p className="text-sm" style={{ color: DS.text.secondary }}>
            {execNarrative.executiveSummary}
          </p>
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: 'Risk Score', value: execNarrative.riskScore, color: 'text-[#f5f5f5]' },
              { label: 'Risk Trend', value: execNarrative.riskTrend, color: riskTrendColor },
              {
                label: 'Total Exposure',
                value: fmt(execNarrative.totalEstimatedExposure),
                color: 'text-[#c9b787]',
              },
              {
                label: 'Active Incidents',
                value: execNarrative.activeIncidentCount,
                color: 'text-[#c9b787]',
              },
              {
                label: 'Critical Findings',
                value: execNarrative.criticalFindings,
                color: 'text-[#f5f5f5]',
              },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="text-center p-3 rounded-lg"
                style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
              >
                <p className={cn('text-lg font-bold', color)}>{value ?? '—'}</p>
                <p className="text-[10px] mt-0.5" style={{ color: DS.text.muted }}>
                  {label}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!denied && isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-[#c9b787]/40 border-t-emerald-400 rounded-full animate-spin" />
        </div>
      )}

      {!denied && !isLoading && (
        <>
          <div
            className="rounded-xl p-4 space-y-3"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <h3
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: DS.text.muted }}
            >
              Business Entities at Risk
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {businessEntities.map((entity) => {
                const color = ENTITY_TYPE_COLORS[entity.type] ?? '#94a3b8';
                const Icon = ENTITY_ICONS[entity.type] ?? Building2;
                return (
                  <div
                    key={entity.id}
                    className="flex items-center gap-3 p-3 rounded-xl"
                    style={{ background: `${color}08`, border: `1px solid ${color}20` }}
                  >
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                      style={{ background: `${color}18` }}
                    >
                      <Icon className="w-4 h-4" style={{ color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-[11px] font-medium truncate"
                        style={{ color: DS.text.primary }}
                      >
                        {entity.name}
                      </p>
                      <p className="text-[10px]" style={{ color: DS.text.muted }}>
                        {entity.owner}
                      </p>
                    </div>
                    {entity.atRisk != null && (
                      <div className="text-right shrink-0">
                        <p className="text-[11px] font-bold" style={{ color }}>
                          {fmt(entity.atRisk)}
                        </p>
                        <p className="text-[9px]" style={{ color: DS.text.muted }}>
                          at risk
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-3">
            <h3
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: DS.text.muted }}
            >
              Incident → Business Entity Mapping
            </h3>
            {incidentImpacts.map((impact) => {
              const sevConf = SEV_CONFIG[impact.severity as string] ?? SEV_CONFIG.medium;
              const isExpanded = expandedIncident === impact.incidentId;
              return (
                <div
                  key={impact.incidentId}
                  className="rounded-xl overflow-hidden"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <div className="w-full flex items-center gap-4 p-4 hover:bg-white/[0.02] transition-colors">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                      style={{ background: sevConf.bg, border: `1px solid ${sevConf.color}30` }}
                    >
                      <AlertTriangle className="w-4 h-4" style={{ color: sevConf.color }} />
                    </div>
                    <button
                      className="flex-1 min-w-0 text-left"
                      onClick={() => setExpandedIncident(isExpanded ? null : impact.incidentId)}
                    >
                      <div className="flex items-center gap-2 mb-0.5">
                        <p
                          className="text-sm font-medium truncate"
                          style={{ color: DS.text.primary }}
                        >
                          {impact.title}
                        </p>
                        <Badge
                          className="text-[9px] shrink-0"
                          style={{
                            background: sevConf.bg,
                            color: sevConf.color,
                            borderColor: `${sevConf.color}30`,
                          }}
                        >
                          {impact.severity}
                        </Badge>
                        <Badge
                          className={cn(
                            'text-[9px] shrink-0',
                            impact.status === 'closed'
                              ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20'
                              : 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/20',
                          )}
                        >
                          {impact.status}
                        </Badge>
                      </div>
                      <div
                        className="flex items-center gap-4 text-[10px]"
                        style={{ color: DS.text.muted }}
                      >
                        <span>{impact.affectedEntities.length} entities affected</span>
                        <span>{impact.estimatedDowntimeHours}h est. downtime</span>
                      </div>
                    </button>
                    <div className="text-right shrink-0">
                      <p className="text-base font-bold text-[#c9b787]">
                        {fmt(impact.estimatedFinancialImpact)}
                      </p>
                      <p className="text-[10px]" style={{ color: DS.text.muted }}>
                        est. impact
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        drilldown(`/compliance/incident-proof?id=${impact.incidentId}`, {
                          fromContext: impact.title,
                        })
                      }
                      className="flex items-center gap-1 text-[10px] px-2 py-1.5 rounded transition-colors shrink-0"
                      style={{
                        background: 'rgba(201,183,135,0.1)',
                        color: '#c9b787',
                        border: '1px solid rgba(201,183,135,0.25)',
                      }}
                      aria-label="Open proof chain"
                    >
                      Proof Chain
                      <ArrowUpRight className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => setExpandedIncident(isExpanded ? null : impact.incidentId)}
                      aria-label="Toggle details"
                      className="shrink-0"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4" style={{ color: DS.text.muted }} />
                      ) : (
                        <ChevronRight className="w-4 h-4" style={{ color: DS.text.muted }} />
                      )}
                    </button>
                  </div>

                  {isExpanded && (
                    <div
                      className="px-4 pb-4 space-y-3"
                      style={{ borderTop: `1px solid ${DS.border}` }}
                    >
                      <div className="grid grid-cols-2 gap-3 pt-3">
                        <div className="space-y-2">
                          <p
                            className="text-[10px] font-semibold uppercase tracking-widest"
                            style={{ color: DS.text.muted }}
                          >
                            Affected Business Entities
                          </p>
                          {impact.affectedEntities.map((ent) => {
                            const color = ENTITY_TYPE_COLORS[ent.entityType] ?? '#94a3b8';
                            return (
                              <div
                                key={ent.entityId}
                                className="flex items-center gap-2 p-2.5 rounded-lg"
                                style={{ background: `${color}06`, border: `1px solid ${color}15` }}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full shrink-0"
                                  style={{ background: color }}
                                />
                                <span
                                  className="text-[11px] flex-1"
                                  style={{ color: DS.text.secondary }}
                                >
                                  {ent.entityName}
                                </span>
                                <span className="text-[10px]" style={{ color: DS.text.muted }}>
                                  {ent.impactType.replace(/-/g, ' ')}
                                </span>
                                <span className="text-[11px] font-bold" style={{ color }}>
                                  {ent.businessRiskScore}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                        <div className="space-y-2">
                          <p
                            className="text-[10px] font-semibold uppercase tracking-widest"
                            style={{ color: DS.text.muted }}
                          >
                            Evidence Citations
                          </p>
                          {impact.citations.map((cit, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-2 p-2.5 rounded-lg text-[10px]"
                              style={{
                                background: 'rgba(201,183,135,0.06)',
                                border: '1px solid rgba(201,183,135,0.12)',
                              }}
                            >
                              <FileText className="w-3 h-3 text-[#c9b787] shrink-0" />
                              <div className="flex-1 min-w-0">
                                <p style={{ color: DS.text.primary }}>{cit.source}</p>
                                <p className="font-mono truncate" style={{ color: DS.text.muted }}>
                                  {cit.ref}
                                </p>
                              </div>
                              <span
                                className="font-bold shrink-0"
                                style={{ color: cit.confidence > 90 ? '#c9b787' : '#c9b787' }}
                              >
                                {cit.confidence}%
                              </span>
                            </div>
                          ))}
                          <div
                            className="text-[9px] pt-1 font-mono"
                            style={{ color: DS.text.muted }}
                          >
                            {impact.provenance.traceRef}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {findingImpacts.length > 0 && (
            <div
              className="rounded-xl p-4 space-y-3"
              style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
            >
              <h3
                className="text-xs font-semibold uppercase tracking-widest"
                style={{ color: DS.text.muted }}
              >
                Finding → Compliance Exposure
              </h3>
              <div className="space-y-2">
                {findingImpacts.map((f) => {
                  const sevConf = SEV_CONFIG[f.severity as string] ?? SEV_CONFIG.medium;
                  const entityColor = ENTITY_TYPE_COLORS[f.businessEntity.type] ?? '#94a3b8';
                  return (
                    <div
                      key={f.findingId}
                      className="flex items-center gap-3 p-3 rounded-xl"
                      style={{
                        background: 'rgba(255,255,255,0.02)',
                        border: `1px solid ${DS.border}`,
                      }}
                    >
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                        style={{ background: sevConf.bg }}
                      >
                        <Shield className="w-3.5 h-3.5" style={{ color: sevConf.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className="text-[11px] font-medium truncate"
                          style={{ color: DS.text.primary }}
                        >
                          {f.title}
                        </p>
                        <div
                          className="flex items-center gap-3 text-[10px]"
                          style={{ color: DS.text.muted }}
                        >
                          <span style={{ color: entityColor }}>{f.businessEntity.name}</span>
                          <span>{f.complianceExposure}</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-bold text-[#f5f5f5]">
                          {fmt(f.estimatedFineExposure)}
                        </p>
                        <p className="text-[9px]" style={{ color: DS.text.muted }}>
                          fine exposure
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      <div className="flex items-center gap-6 text-[10px] pt-2" style={{ color: DS.text.muted }}>
        <Activity className="w-3 h-3" />
        <span>Verified by: {provenance.verifiedBy ?? 'CONSTELLATION Business Impact Engine'}</span>
        <span>Runtime: {provenance.cognitiveRuntime ?? 'v2.1.0'}</span>
        {dataUpdatedAt > 0 && <span>Updated: {new Date(dataUpdatedAt).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
