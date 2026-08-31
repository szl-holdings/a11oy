// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardQuery } from '@szl-holdings/api-client-react';

import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Eye,
  GitBranch,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useState } from 'react';

const _ACCENT = '#f5f5f5';
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const API_BASE: string = (import.meta as any).env?.VITE_API_BASE ?? '';

interface DecisionFork {
  forkId: string;
  forkType: string;
  agentId: string;
  agentName: string;
  domain: string;
  decision: string;
  output: string;
  confidence: number;
  latencyMs: number;
  tokensUsed: number;
  timestamp: string;
}

interface JudgeEvaluation {
  qualityScore: number;
  safetyScore: number;
  correctnessScore: number;
  efficiencyScore: number;
  overallScore: number;
  strengths: string[];
  weaknesses: string[];
  regressionDetected: boolean;
}

interface ExecutionTrace {
  traceId: string;
  query: string;
  forks: DecisionFork[];
  startTime: string;
  endTime: string | null;
  totalLatencyMs: number;
  status: string;
  judgeEvaluation: JudgeEvaluation | null;
  regressionFlags: string[];
}

interface ObservabilityStats {
  totalTraces: number;
  avgOverallScore: number;
  avgLatencyMs: number;
  regressionRate: number;
  topWeaknesses: string[];
}

const FORK_TYPE_COLORS: Record<string, string> = {
  routing: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
  tool_call: 'text-[#8a8a8a] bg-[#8a8a8a]/10 border-[#8a8a8a]/20',
  validation: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
  synthesis: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
  escalation: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/20',
  governance_check: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/20',
};

const FORK_TYPE_ICONS: Record<string, typeof Activity> = {
  routing: GitBranch,
  tool_call: Zap,
  validation: Shield,
  synthesis: Activity,
  escalation: AlertTriangle,
  governance_check: Shield,
};

function ScoreBadge({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const color = pct >= 75 ? 'text-[#c9b787]' : pct >= 50 ? 'text-[#c9b787]' : 'text-[#f5f5f5]';
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${color}`}>{pct}</div>
      <div className="text-[10px] text-[#c9b787]/50">{label}</div>
    </div>
  );
}

function ForkCard({ fork, isLast }: { fork: DecisionFork; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const typeStyle =
    FORK_TYPE_COLORS[fork.forkType] ?? 'text-gray-400 bg-gray-500/10 border-gray-500/20';
  const Icon = FORK_TYPE_ICONS[fork.forkType] ?? Activity;

  return (
    <div className="relative">
      {!isLast && <div className="absolute left-4 top-10 bottom-0 w-px bg-[#c9b787]/10" />}
      <div
        className="relative bg-[#09080f]/80 border border-[#c9b787]/10 rounded-xl p-4 ml-0 hover:border-[#c9b787]/20 cursor-pointer transition-all"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          <div
            className={`w-8 h-8 rounded-lg border flex items-center justify-center shrink-0 ${typeStyle}`}
          >
            <Icon className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-[#c9b787]">{fork.agentName}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${typeStyle}`}>
                {fork.forkType}
              </span>
              <span className="text-[10px] text-[#c9b787]/50 ml-auto">{fork.latencyMs}ms</span>
            </div>
            <p className="text-xs text-[#c9b787]/60 mt-0.5 truncate">{fork.decision}</p>
            <div className="flex items-center gap-4 mt-1">
              <span className="text-[10px] text-[#c9b787]/40">Confidence: {fork.confidence}%</span>
              <span className="text-[10px] text-[#c9b787]/40">{fork.tokensUsed} tokens</span>
            </div>
          </div>
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-[#c9b787]/40 shrink-0" />
          ) : (
            <ChevronRight className="w-4 h-4 text-[#c9b787]/40 shrink-0" />
          )}
        </div>
        {expanded && (
          <div className="mt-3 pt-3 border-t border-[#c9b787]/10">
            <p className="text-xs text-[#c9b787]/70 leading-relaxed">{fork.output}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function TraceCard({
  trace,
  onSelect,
  isSelected,
}: {
  trace: ExecutionTrace;
  onSelect: () => void;
  isSelected: boolean;
}) {
  const score = trace.judgeEvaluation?.overallScore ?? 0;
  const scoreColor =
    score >= 0.75 ? 'text-[#c9b787]' : score >= 0.5 ? 'text-[#c9b787]' : 'text-[#f5f5f5]';
  const hasRegressions = trace.regressionFlags.length > 0;

  return (
    <div
      className={`bg-[#09080f]/80 border rounded-xl p-4 cursor-pointer transition-all ${isSelected ? 'border-[#c9b787]/40 bg-[#c9b787]/5' : 'border-[#c9b787]/10 hover:border-[#c9b787]/20'}`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-[#c9b787] truncate">{trace.query}</p>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-[10px] text-[#c9b787]/50">
              {trace.forks.length} decision forks
            </span>
            <span className="text-[10px] text-[#c9b787]/50">{trace.totalLatencyMs}ms</span>
            <span className={`text-[10px] ${scoreColor}`}>Score: {Math.round(score * 100)}</span>
            {hasRegressions && (
              <span className="text-[10px] text-[#f5f5f5] flex items-center gap-1">
                <TrendingDown className="w-3 h-3" />
                Regression
              </span>
            )}
            {trace.status === 'completed' && !hasRegressions && (
              <span className="text-[10px] text-[#c9b787] flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />
                OK
              </span>
            )}
          </div>
        </div>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${trace.status === 'completed' ? 'bg-[#c9b787]/10 text-[#c9b787]' : 'bg-[#f5f5f5]/10 text-[#f5f5f5]'}`}
        >
          {trace.status}
        </span>
      </div>
    </div>
  );
}

export default function AgentOpsExplorer() {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  const { data: statsData } = useStandardQuery<ObservabilityStats>({
    queryKey: ['nuro-mesh-observability-stats'],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/nuro-mesh/observability/stats`);
      return r.json();
    },
    refetchInterval: 30000,
  });

  const {
    data: tracesData,
    isLoading: tracesLoading,
    refetch,
  } = useStandardQuery<{ traces: ExecutionTrace[] }>({
    queryKey: ['nuro-mesh-observability-traces'],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/nuro-mesh/observability/traces?limit=30`);
      return r.json();
    },
    refetchInterval: 15000,
  });

  const { data: traceDetail } = useStandardQuery<ExecutionTrace>({
    queryKey: ['nuro-mesh-trace-detail', selectedTraceId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/nuro-mesh/observability/traces/${selectedTraceId}`);
      return r.json();
    },
    enabled: !!selectedTraceId,
  });

  const traces = tracesData?.traces ?? [];
  const selectedTrace = traceDetail ?? traces.find((t) => t.traceId === selectedTraceId);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#c9b787]/10 flex items-center justify-center">
            <GitBranch className="w-5 h-5 text-[#c9b787]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#c9b787]">AgentOps Decision Explorer</h1>
            <p className="text-xs text-[#c9b787]/50">
              Behavioral observability across all multi-agent orchestration runs
            </p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-xs text-[#c9b787]/60 hover:text-[#c9b787] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {statsData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Total Traces',
              value: statsData.totalTraces.toLocaleString(),
              icon: Activity,
              color: 'text-[#c9b787]',
              bg: 'bg-[#c9b787]/10',
            },
            {
              label: 'Avg Quality Score',
              value: `${Math.round(statsData.avgOverallScore * 100)}/100`,
              icon: CheckCircle,
              color: 'text-[#c9b787]',
              bg: 'bg-[#c9b787]/10',
            },
            {
              label: 'Avg Latency',
              value: `${(statsData.avgLatencyMs / 1000).toFixed(1)}s`,
              icon: Clock,
              color: 'text-[#c9b787]',
              bg: 'bg-[#c9b787]/10',
            },
            {
              label: 'Regression Rate',
              value: `${(statsData.regressionRate * 100).toFixed(1)}%`,
              icon: statsData.regressionRate > 0.1 ? TrendingDown : TrendingUp,
              color: statsData.regressionRate > 0.1 ? 'text-[#f5f5f5]' : 'text-[#c9b787]',
              bg: statsData.regressionRate > 0.1 ? 'bg-[#f5f5f5]/10' : 'bg-[#c9b787]/10',
            },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <div key={label} className="bg-[#09080f]/80 border border-[#c9b787]/10 rounded-xl p-4">
              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center`}>
                  <Icon className={`w-3.5 h-3.5 ${color}`} />
                </div>
                <div>
                  <div className="text-base font-bold text-[#c9b787]">{value}</div>
                  <div className="text-[10px] text-[#c9b787]/50">{label}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {statsData?.topWeaknesses && statsData.topWeaknesses.length > 0 && (
        <div className="bg-[#09080f]/80 border border-[#f5f5f5]/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-[#f5f5f5]" />
            <span className="text-sm font-medium text-[#f5f5f5]">Top Behavioral Weaknesses</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {statsData.topWeaknesses.map((w, i) => (
              <span
                key={i}
                className="text-xs px-2 py-1 bg-[#f5f5f5]/10 text-[#f5f5f5] rounded-lg border border-[#f5f5f5]/20"
              >
                {w}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-[#c9b787] flex items-center gap-2">
            <Eye className="w-4 h-4" />
            Recent Orchestration Traces
          </h2>
          {tracesLoading ? (
            <div className="text-center py-8 text-[#c9b787]/40 text-sm">Loading traces...</div>
          ) : traces.length === 0 ? (
            <div className="text-center py-8 text-[#c9b787]/30 text-sm">
              No traces captured yet. Run an orchestration to see behavioral data.
            </div>
          ) : (
            <div className="space-y-2">
              {traces.map((trace) => (
                <TraceCard
                  key={trace.traceId}
                  trace={trace}
                  onSelect={() =>
                    setSelectedTraceId(trace.traceId === selectedTraceId ? null : trace.traceId)
                  }
                  isSelected={trace.traceId === selectedTraceId}
                />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <h2 className="text-sm font-medium text-[#c9b787] flex items-center gap-2">
            <GitBranch className="w-4 h-4" />
            Decision Fork Explorer
          </h2>
          {!selectedTrace ? (
            <div className="bg-[#09080f]/80 border border-[#c9b787]/10 rounded-xl p-8 text-center">
              <GitBranch className="w-8 h-8 text-[#c9b787]/20 mx-auto mb-2" />
              <p className="text-sm text-[#c9b787]/40">
                Select a trace to explore its decision forks
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-[#09080f]/80 border border-[#c9b787]/10 rounded-xl p-4">
                <p className="text-xs font-medium text-[#c9b787] mb-1">Query</p>
                <p className="text-xs text-[#c9b787]/70 mb-3">{selectedTrace.query}</p>

                {selectedTrace.judgeEvaluation && (
                  <div>
                    <p className="text-xs font-medium text-[#c9b787] mb-2">
                      LLM-as-Judge Evaluation
                    </p>
                    <div className="grid grid-cols-5 gap-2 mb-3">
                      {[
                        { score: selectedTrace.judgeEvaluation.qualityScore, label: 'Quality' },
                        { score: selectedTrace.judgeEvaluation.safetyScore, label: 'Safety' },
                        { score: selectedTrace.judgeEvaluation.correctnessScore, label: 'Correct' },
                        {
                          score: selectedTrace.judgeEvaluation.efficiencyScore,
                          label: 'Efficient',
                        },
                        { score: selectedTrace.judgeEvaluation.overallScore, label: 'Overall' },
                      ].map(({ score, label }) => (
                        <ScoreBadge key={label} score={score} label={label} />
                      ))}
                    </div>
                    {selectedTrace.judgeEvaluation.strengths.length > 0 && (
                      <div className="mb-2">
                        <p className="text-[10px] text-[#c9b787]/70 mb-1">Strengths</p>
                        {selectedTrace.judgeEvaluation.strengths.map((s, i) => (
                          <p
                            key={i}
                            className="text-[10px] text-[#c9b787]/60 flex items-center gap-1"
                          >
                            <CheckCircle className="w-3 h-3" />
                            {s}
                          </p>
                        ))}
                      </div>
                    )}
                    {selectedTrace.judgeEvaluation.weaknesses.length > 0 && (
                      <div>
                        <p className="text-[10px] text-[#f5f5f5]/70 mb-1">Weaknesses</p>
                        {selectedTrace.judgeEvaluation.weaknesses.map((w, i) => (
                          <p
                            key={i}
                            className="text-[10px] text-[#f5f5f5]/60 flex items-center gap-1"
                          >
                            <AlertTriangle className="w-3 h-3" />
                            {w}
                          </p>
                        ))}
                      </div>
                    )}
                    {selectedTrace.regressionFlags.length > 0 && (
                      <div className="mt-2 p-2 bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 rounded-lg">
                        <p className="text-[10px] text-[#f5f5f5] font-medium">Regression Detected</p>
                        {selectedTrace.regressionFlags.map((f, i) => (
                          <p key={i} className="text-[10px] text-[#f5f5f5]/70">
                            {f}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                {selectedTrace.forks.map((fork, i) => (
                  <ForkCard
                    key={fork.forkId}
                    fork={fork}
                    isLast={i === selectedTrace.forks.length - 1}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
