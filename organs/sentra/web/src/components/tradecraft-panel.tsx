// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/components/tradecraft-panel.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Input } from '@szl-holdings/shared-ui/ui/input';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useMutation, useQuery } from '@tanstack/react-query';
import { type LucideIcon, Activity, AlertCircle, AlertTriangle, BookOpen, Brain, CheckCircle, ChevronRight, Database, FileText, Info, Loader2, Lock, Search, Shield, Star, TrendingUp, Zap } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'wouter';
import { api } from '@/lib/api';

interface TradecraftDecision {
  objectId: string;
  caseId: string | null;
  incidentId: string | null;
  decisionType: string;
  summary: string;
  confidence: string;
  confidenceLabel: 'high' | 'moderate' | 'low' | 'insufficient';
  impactLevel: string;
  urgency: string;
  recommendedAction: string;
  approvalRequired: boolean;
  humanReviewRequired: boolean;
  evidenceRefs: unknown[];
  gapsAndUnknowns: string[];
  createdAt: string;
}

interface AnalystNote {
  noteId: string;
  content: string;
  author: string;
  noteType: string;
  isKey: boolean;
  createdAt: string;
}

const DECISION_ICONS: Record<string, LucideIcon> = {
  TriageDecision: Zap,
  IncidentAssessment: AlertTriangle,
  RiskDecision: Shield,
  EscalationDecision: TrendingUp,
  ApprovalRecommendation: CheckCircle,
  ResponsePlan: Activity,
  ExecutiveBrief: BookOpen,
  ControlGapFinding: Lock,
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  moderate: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  low: 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
  insufficient: 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10',
};

const NOTE_TYPE_COLORS: Record<string, string> = {
  observation: 'text-[#c9b787]',
  hypothesis: 'text-[#8a8a8a]',
  assumption: 'text-[#c9b787]',
  gap: 'text-[#c9b787]',
  dissent: 'text-[#f5f5f5]',
  key_judgment: 'text-[#c9b787]',
  evidence_note: 'text-[#8a8a8a]',
  general: 'text-zinc-400',
};

interface TradecraftPanelProps {
  caseId?: string | null;
  incidentId?: string | null;
  title?: string;
  compact?: boolean;
}

export function TradecraftPanel({
  caseId,
  incidentId,
  title = 'Tradecraft Decisions',
  compact = false,
}: TradecraftPanelProps) {
  const [activeTab, setActiveTab] = useState<'decisions' | 'changes' | 'notes'>('decisions');

  const queryParams = new URLSearchParams();
  if (caseId) queryParams.set('caseId', caseId);
  if (incidentId) queryParams.set('incidentId', incidentId);
  queryParams.set('limit', '20');

  const { data: decisionsData } = useQuery({
    queryKey: ['tradecraft-decisions-panel', caseId, incidentId],
    queryFn: () => api.tradecraft.decisions(queryParams.toString()),
    refetchInterval: 60000,
    enabled: !!(caseId || incidentId),
  });

  const { data: notesData } = useQuery({
    queryKey: ['tradecraft-notebook-panel', caseId, incidentId],
    queryFn: () => api.tradecraft.notebook(queryParams.toString()),
    refetchInterval: 60000,
    enabled: !!(caseId || incidentId),
  });

  const decisions: TradecraftDecision[] = Array.isArray(decisionsData) ? decisionsData : [];
  const notes: AnalystNote[] = Array.isArray(notesData) ? notesData : [];

  const latestDecision = decisions[0];
  const prevDecision = decisions[1];

  function computeChanges(): Array<{
    field: string;
    prev: string;
    curr: string;
    critical: boolean;
  }> {
    if (!latestDecision || !prevDecision) return [];
    const changes: Array<{ field: string; prev: string; curr: string; critical: boolean }> = [];
    if (prevDecision.confidenceLabel !== latestDecision.confidenceLabel) {
      changes.push({
        field: 'Confidence',
        prev: prevDecision.confidenceLabel,
        curr: latestDecision.confidenceLabel,
        critical: true,
      });
    }
    if (prevDecision.impactLevel !== latestDecision.impactLevel) {
      changes.push({
        field: 'Impact',
        prev: prevDecision.impactLevel,
        curr: latestDecision.impactLevel,
        critical: true,
      });
    }
    if (prevDecision.urgency !== latestDecision.urgency) {
      changes.push({
        field: 'Urgency',
        prev: prevDecision.urgency,
        curr: latestDecision.urgency,
        critical: false,
      });
    }
    if (prevDecision.approvalRequired !== latestDecision.approvalRequired) {
      changes.push({
        field: 'Approval Required',
        prev: String(prevDecision.approvalRequired),
        curr: String(latestDecision.approvalRequired),
        critical: true,
      });
    }
    if (prevDecision.recommendedAction !== latestDecision.recommendedAction) {
      changes.push({
        field: 'Action',
        prev: prevDecision.recommendedAction.slice(0, 40),
        curr: latestDecision.recommendedAction.slice(0, 40),
        critical: false,
      });
    }
    return changes;
  }

  const changes = computeChanges();
  const tabs = [
    { id: 'decisions' as const, label: `Decisions (${decisions.length})`, icon: Brain },
    { id: 'changes' as const, label: `Changes (${changes.length})`, icon: Activity },
    { id: 'notes' as const, label: `Notes (${notes.length})`, icon: BookOpen },
  ];

  if (!caseId && !incidentId) {
    return (
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 text-center text-xs text-muted-foreground">
        Select a case or incident to view tradecraft analysis
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-xl bg-zinc-900 border border-zinc-800 flex flex-col',
        compact ? 'max-h-64' : 'max-h-[500px]',
      )}
    >
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800">
        <div className="flex items-center gap-1.5">
          <Brain className="w-3.5 h-3.5 text-[#c9b787]" />
          <span className="text-xs font-semibold text-zinc-100">{title}</span>
          {decisions.length > 0 && (
            <Badge
              variant="outline"
              className={cn(
                'text-[8px] px-1 py-0 ml-1',
                CONFIDENCE_COLORS[latestDecision?.confidenceLabel || 'low'],
              )}
            >
              {latestDecision?.confidenceLabel}
            </Badge>
          )}
        </div>
        <Link href="/tradecraft">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[10px] gap-1 text-muted-foreground hover:text-zinc-300"
          >
            Open Full <ChevronRight className="w-3 h-3" />
          </Button>
        </Link>
      </div>

      <div className="flex border-b border-zinc-800">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1 py-1.5 text-[9px] font-mono uppercase tracking-wider transition-colors',
              activeTab === tab.id
                ? 'text-zinc-100 border-b-2 border-[#c9b787]'
                : 'text-muted-foreground hover:text-zinc-300',
            )}
          >
            <tab.icon className="w-2.5 h-2.5" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {activeTab === 'decisions' &&
          (decisions.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground text-xs">
              No decisions yet for this case/incident
            </div>
          ) : (
            decisions.map((d) => {
              const Icon = DECISION_ICONS[d.decisionType] || FileText;
              const confScore = Math.round(parseFloat(d.confidence) * 100);
              return (
                <div
                  key={d.objectId}
                  className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <Icon className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[10px] font-semibold text-zinc-200">
                        {d.decisionType}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge
                        variant="outline"
                        className={cn('text-[8px] px-1 py-0', CONFIDENCE_COLORS[d.confidenceLabel])}
                      >
                        {confScore}%
                      </Badge>
                      {d.approvalRequired && (
                        <div
                          className="w-1.5 h-1.5 rounded-full bg-[#c9b787]"
                          title="Approval Required"
                        />
                      )}
                      {d.humanReviewRequired && (
                        <div
                          className="w-1.5 h-1.5 rounded-full bg-[#c9b787]"
                          title="Human Review Required"
                        />
                      )}
                    </div>
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">
                    {d.summary.slice(0, 120)}
                    {d.summary.length > 120 ? '…' : ''}
                  </p>
                  <div className="flex items-center justify-between text-[9px] font-mono text-zinc-600">
                    <span>
                      {d.impactLevel} impact · {d.urgency}
                    </span>
                    <span>{new Date(d.createdAt).toLocaleString()}</span>
                  </div>
                </div>
              );
            })
          ))}

        {activeTab === 'changes' &&
          (changes.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground text-xs">
              {decisions.length < 2
                ? 'Need 2+ decisions to show changes'
                : 'No changes detected between last two decisions'}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-[9px] text-muted-foreground">
                Changes from previous to latest decision:
              </p>
              {changes.map((c, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'p-2 rounded-lg border text-[10px]',
                    c.critical ? 'bg-[#f5f5f5]/5 border-[#f5f5f5]/20' : 'bg-zinc-950 border-zinc-800',
                  )}
                >
                  <span className="font-semibold text-zinc-300">{c.field}:</span>
                  <span className="text-muted-foreground ml-1.5 line-through">{c.prev}</span>
                  <span className="text-zinc-200 ml-1.5">→ {c.curr}</span>
                </div>
              ))}
            </div>
          ))}

        {activeTab === 'notes' &&
          (notes.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground text-xs">
              No analyst notes yet
            </div>
          ) : (
            notes.slice(0, 10).map((note) => (
              <div
                key={note.noteId}
                className={cn(
                  'p-2 rounded-lg border text-[10px]',
                  note.isKey
                    ? 'bg-[#c9b787]/5 border-[#c9b787]/20'
                    : 'bg-zinc-950 border-zinc-800',
                )}
              >
                <div className="flex items-center gap-1 mb-1">
                  {note.isKey && <Star className="w-2.5 h-2.5 text-[#c9b787]" />}
                  <span
                    className={cn(
                      'text-[9px] font-mono uppercase font-bold',
                      NOTE_TYPE_COLORS[note.noteType] || 'text-zinc-400',
                    )}
                  >
                    {note.noteType.replace('_', ' ')}
                  </span>
                  <span className="text-zinc-600 text-[9px]">— {note.author}</span>
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  {note.content.slice(0, 100)}
                  {note.content.length > 100 ? '…' : ''}
                </p>
              </div>
            ))
          ))}
      </div>
    </div>
  );
}

export function RelatedCasesPanel({
  caseId,
  incidentId,
}: {
  caseId?: string | null;
  incidentId?: string | null;
}) {
  const queryParam = incidentId
    ? `incidentId=${incidentId}&limit=50`
    : caseId
      ? `caseId=${caseId}&limit=50`
      : null;

  const { data: decisionsData } = useQuery({
    queryKey: ['related-cases-decisions', incidentId, caseId],
    queryFn: () => api.tradecraft.decisions(queryParam!),
    enabled: !!(incidentId || caseId),
  });

  const allDecisions: TradecraftDecision[] = Array.isArray(decisionsData) ? decisionsData : [];
  const relatedCaseIds = incidentId
    ? [...new Set(allDecisions.map((d) => d.caseId).filter((id): id is string => id !== null))]
    : [
        ...new Set(
          allDecisions
            .map((d) => d.caseId)
            .filter((id): id is string => id !== null && id !== caseId),
        ),
      ];

  const relatedIncidentIds =
    caseId && !incidentId
      ? [
          ...new Set(
            allDecisions.map((d) => d.incidentId).filter((id): id is string => id !== null),
          ),
        ]
      : [];

  if (relatedCaseIds.length === 0 && relatedIncidentIds.length === 0) return null;

  return (
    <div className="rounded-xl bg-zinc-900 border border-zinc-800">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-zinc-800">
        <Database className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] font-semibold text-zinc-300">Related Cases</span>
        <Badge variant="outline" className="text-[8px] px-1 py-0 ml-auto">
          {relatedCaseIds.length + relatedIncidentIds.length}
        </Badge>
      </div>
      <div className="p-2 space-y-1">
        {relatedCaseIds.slice(0, 5).map((cid) => (
          <div
            key={cid}
            className="flex items-center justify-between px-2 py-1.5 rounded bg-zinc-950 border border-zinc-800"
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[8px] font-mono text-[#c9b787] px-1 py-0 rounded border border-[#c9b787]/20 bg-[#c9b787]/5">
                CASE
              </span>
              <span className="text-[10px] font-mono text-zinc-300">{cid}</span>
            </div>
            <ChevronRight className="w-3 h-3 text-muted-foreground" />
          </div>
        ))}
        {relatedIncidentIds.slice(0, 3).map((iid) => (
          <div
            key={iid}
            className="flex items-center justify-between px-2 py-1.5 rounded bg-zinc-950 border border-zinc-800"
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[8px] font-mono text-[#c9b787] px-1 py-0 rounded border border-[#c9b787]/20 bg-[#c9b787]/5">
                INC
              </span>
              <span className="text-[10px] font-mono text-zinc-300">{iid}</span>
            </div>
            <ChevronRight className="w-3 h-3 text-muted-foreground" />
          </div>
        ))}
      </div>
    </div>
  );
}

interface EvidenceEntry {
  id: string;
  title: string;
  sourceType: string;
  source: string;
  freshness: string;
  score: number;
  content: string;
  timestamp: string | null;
}

interface EvidenceQueryResult {
  entries: EvidenceEntry[];
  totalIndexed: number;
  method: string;
  confidenceDowngraded: boolean;
  confidenceDowngradeReason: string | null;
  weakRetrievalWarning: string | null;
  latencyMs: number;
}

const FRESHNESS_COLORS: Record<string, string> = {
  current: 'text-[#c9b787]',
  recent: 'text-[#c9b787]',
  stale: 'text-[#c9b787]',
  unknown: 'text-zinc-500',
};

const SOURCE_TYPE_COLORS: Record<string, string> = {
  alert: 'text-[#f5f5f5]',
  incident: 'text-[#c9b787]',
  incident_timeline: 'text-[#c9b787]',
  case_summary: 'text-[#8a8a8a]',
  analyst_note: 'text-[#c9b787]',
  prior_decision: 'text-[#8a8a8a]',
};

export function EvidenceIndexPanel({
  caseId,
  incidentId,
}: {
  caseId?: string | null;
  incidentId?: string | null;
}) {
  const [queryInput, setQueryInput] = useState('');
  const [result, setResult] = useState<EvidenceQueryResult | null>(null);

  const queryMutation = useMutation({
    mutationFn: (q: string) =>
      api.tradecraft.evidenceQuery({
        query: q,
        caseId: caseId ?? undefined,
        incidentId: incidentId ?? undefined,
        maxResults: 15,
      }),
    onSuccess: (data) => {
      if (data?.entries) setResult(data as EvidenceQueryResult);
    },
  });

  const handleSearch = () => {
    const q = queryInput.trim();
    if (!q) return;
    queryMutation.mutate(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="rounded-xl bg-zinc-900 border border-zinc-800 flex flex-col max-h-[420px]">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-zinc-800">
        <Database className="w-3 h-3 text-[#c9b787]" />
        <span className="text-[10px] font-semibold text-zinc-100">Evidence Index</span>
        {result && (
          <Badge variant="outline" className="text-[8px] px-1 py-0 ml-auto text-zinc-500">
            {result.totalIndexed} indexed · {result.method}
          </Badge>
        )}
      </div>

      <div className="px-3 py-2 border-b border-zinc-800 flex gap-2">
        <Input
          value={queryInput}
          onChange={(e) => setQueryInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Query evidence (e.g. lateral movement, C2 exfil…)"
          className="h-7 text-[11px] bg-zinc-950 border-zinc-700 font-mono"
        />
        <Button
          size="sm"
          variant="outline"
          className="h-7 px-2.5 border-zinc-700"
          onClick={handleSearch}
          disabled={queryMutation.isPending || !queryInput.trim()}
        >
          {queryMutation.isPending ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Search className="w-3 h-3" />
          )}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {result?.confidenceDowngraded && (
          <div className="flex items-start gap-2 p-2 rounded-lg bg-[#c9b787]/5 border border-[#c9b787]/20 text-[10px]">
            <AlertCircle className="w-3 h-3 text-[#c9b787] mt-0.5 shrink-0" />
            <span className="text-[#c9b787]">{result.weakRetrievalWarning}</span>
          </div>
        )}

        {queryMutation.isError && (
          <div className="flex items-center gap-1.5 text-[10px] text-[#f5f5f5] p-2 rounded bg-[#f5f5f5]/5 border border-[#f5f5f5]/20">
            <AlertCircle className="w-3 h-3" />
            Evidence query failed. Check connection.
          </div>
        )}

        {!result && !queryMutation.isPending && (
          <div className="text-center py-6 text-muted-foreground text-xs space-y-1">
            <Info className="w-4 h-4 mx-auto mb-1.5 text-zinc-600" />
            <p>Enter a query to retrieve related evidence</p>
            <p className="text-[10px] text-zinc-600">Keyword + reranking with freshness scoring</p>
          </div>
        )}

        {queryMutation.isPending && (
          <div className="flex items-center justify-center py-6 gap-2 text-xs text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            Retrieving evidence…
          </div>
        )}

        {result && result.entries.length === 0 && (
          <div className="text-center py-4 text-muted-foreground text-xs">
            No evidence found for this query
          </div>
        )}

        {result?.entries.map((entry) => {
            const scorePercent = Math.round(entry.score * 100);
            return (
              <div
                key={entry.id}
                className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1"
              >
                <div className="flex items-start justify-between gap-2">
                  <span
                    className={cn(
                      'text-[9px] font-mono uppercase font-bold',
                      SOURCE_TYPE_COLORS[entry.sourceType] ?? 'text-zinc-400',
                    )}
                  >
                    {entry.sourceType.replace(/_/g, ' ')}
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={cn(
                        'text-[9px] font-mono',
                        FRESHNESS_COLORS[entry.freshness] ?? 'text-zinc-500',
                      )}
                    >
                      {entry.freshness}
                    </span>
                    <Badge variant="outline" className="text-[8px] px-1 py-0">
                      {scorePercent}%
                    </Badge>
                  </div>
                </div>
                <p className="text-[10px] font-semibold text-zinc-200 leading-snug">
                  {entry.title}
                </p>
                <p className="text-[9px] text-muted-foreground leading-relaxed line-clamp-2">
                  {entry.content.slice(0, 140)}
                  {entry.content.length > 140 ? '…' : ''}
                </p>
                <p className="text-[9px] font-mono text-zinc-600">{entry.source}</p>
              </div>
            );
          })}
      </div>
    </div>
  );
}
