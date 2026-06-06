// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  GitMerge,
  Loader2,
  Shield,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  type AutonomousSocResponse,
  type AutonomousSocStage,
  type SmartScoreAlert,
  getAutonomousSocPage,
} from '../lib/sentra-api';
import { HealthcareCaseStudyBanner } from '../components/healthcare-case-study-banner';

const API = import.meta.env.VITE_API_URL ?? '/api';

const STAGE_ICONS: Record<string, typeof Brain> = {
  database: Database,
  brain: Brain,
  gitMerge: GitMerge,
  trendingUp: TrendingUp,
  zap: Zap,
  shield: Shield,
};

const PHASE_COLORS: Record<string, string> = {
  plan: '#c9b787',
  reason: '#8a8a8a',
  execute: '#f5f5f5',
  monitor: '#c9b787',
};

function AnimatedCounter({ target }: { target: number }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let frame: number;
    const step = Math.max(1, Math.floor(target / 40));
    const tick = () => {
      setVal((v) => {
        if (v >= target) return target;
        const next = Math.min(v + step, target);
        if (next < target) frame = requestAnimationFrame(tick);
        return next;
      });
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return <>{val.toLocaleString()}</>;
}

export default function AutonomousSOCCommand() {
  const [data, setData] = useState<AutonomousSocResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<SmartScoreAlert | null>(null);
  const [pipelinePulse, setPipelinePulse] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    // Fetch seed page data + live Sentra ML model registry in parallel
    Promise.all([
      getAutonomousSocPage(),
      fetch(`${API}/sentra/ml/model-registry`, { credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null),
    ])
      .then(([pageRes, registryRes]) => {
        if (!active) return;
        if (!pageRes) {
          setError('Unable to load Autonomous SOC data.');
          return;
        }
        // Augment the page with live model registry data if available
        if (registryRes?.data?.models && Array.isArray(registryRes.data.models)) {
          const liveModels: Array<{ modelName: string; version: string; status: string }> = registryRes.data.models;
          const activeLiveCount = liveModels.filter(m => m.status === 'active').length;
          setData({
            ...pageRes,
            mlModelClusters: pageRes.mlModelClusters?.map((c: { label: string; count: number; color: string }, i: number) =>
              i === 0 ? { ...c, count: Math.max(c.count, activeLiveCount * 1000) } : c,
            ) ?? pageRes.mlModelClusters,
          });
        } else {
          setData(pageRes);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setPipelinePulse((p) => p + 1), 2000);
    return () => clearInterval(iv);
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center gap-2 text-xs text-zinc-400">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading Autonomous SOC data…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-[#f5f5f5]/30 bg-[#f5f5f5]/5 p-4 text-xs text-[#f5f5f5]">
          {error ?? 'Autonomous SOC data unavailable.'}
        </div>
      </div>
    );
  }

  const { pipelineStages, smartScoreAlerts, mlModelClusters, agentixWorkforce, metrics, correlation } = data;
  const totalModels = mlModelClusters.reduce((s, c) => s + c.count, 0);

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-5 h-5 text-[#f5f5f5]" />
            <h1 className="text-lg font-semibold text-white">Autonomous SOC Command</h1>
            <span className="text-[9px] px-2 py-0.5 rounded-full border border-[#c9b787]/30 bg-[#c9b787]/10 text-[#c9b787] font-mono uppercase">
              Precision AI
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            Real-time autonomous detection & response pipeline — SmartScore prioritization, {totalModels.toLocaleString()}+ ML models, sub-30s incident resolution
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[10px] text-[#c9b787]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c9b787] animate-pulse" />
            Autonomous Mode Active
          </span>
        </div>
      </div>

      <HealthcareCaseStudyBanner currentPage="autonomous-soc-command" />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'ML Models Active', value: totalModels, sub: `across ${mlModelClusters.length} clusters`, color: '#8a8a8a', icon: Cpu },
          { label: 'Alerts Ingested (24h)', value: metrics.alertsIngested24h, sub: `${metrics.autoTriageRate} auto-resolved`, color: '#f5f5f5', icon: AlertTriangle },
          { label: 'Avg SmartScore Time', value: metrics.avgSmartScoreTime, sub: 'dynamic risk scoring', color: '#c9b787', icon: TrendingUp },
          { label: 'Auto-Triage Rate', value: metrics.autoTriageRate, sub: 'closed < 30s', color: '#c9b787', icon: Zap },
          { label: 'MTTR (Autonomous)', value: metrics.autonomousMttr, sub: 'vs 45m manual baseline', color: '#c9b787', icon: Clock },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-xl font-bold text-white font-mono">
                {typeof m.value === 'number' ? <AnimatedCounter target={m.value} /> : m.value}
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div>
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-[#c9b787]" />
          Detection & Response Pipeline
        </h2>
        <div className="flex items-center gap-1 overflow-x-auto pb-2">
          {pipelineStages.map((stage: AutonomousSocStage, i) => {
            const Icon = STAGE_ICONS[stage.icon] ?? Brain;
            const isActive = pipelinePulse % pipelineStages.length === i;
            return (
              <div key={stage.id} className="flex items-center gap-1 shrink-0">
                <div className={cn(
                  'rounded-xl border p-3 transition-all min-w-[140px]',
                  isActive ? 'border-[#c9b787]/40 bg-[#c9b787]/5' : 'border-white/8 bg-white/3',
                )}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="w-3.5 h-3.5" style={{ color: isActive ? '#c9b787' : '#8a8a8a' }} />
                    <span className="text-[10px] font-medium text-white">{stage.label}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-white font-mono">{stage.count.toLocaleString()}</span>
                    <span className="text-[10px] text-zinc-500">{stage.avgTime}</span>
                  </div>
                </div>
                {i < pipelineStages.length - 1 && (
                  <ArrowRight className={cn('w-3.5 h-3.5 shrink-0 transition-colors', isActive ? 'text-[#c9b787]' : 'text-zinc-700')} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-[#f5f5f5]" />
            SmartScore — Dynamic Risk Prioritization
          </h2>
          <div className="space-y-2">
            {smartScoreAlerts.map((alert) => (
              <button
                key={alert.id}
                onClick={() => setSelectedAlert(selectedAlert?.id === alert.id ? null : alert)}
                className={cn(
                  'w-full rounded-xl border p-3 text-left transition-all',
                  selectedAlert?.id === alert.id
                    ? 'border-[#f5f5f5]/30 bg-[#f5f5f5]/5'
                    : alert.severity === 'critical'
                      ? 'border-[#f5f5f5]/15 bg-white/3 hover:bg-white/5'
                      : 'border-white/8 bg-white/3 hover:bg-white/5',
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <span className="text-[11px] font-medium text-white leading-snug">{alert.title}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={cn(
                      'text-sm font-bold font-mono',
                      alert.score >= 95 ? 'text-[#f5f5f5]' : alert.score >= 85 ? 'text-[#c9b787]' : 'text-zinc-400',
                    )}>
                      {alert.score}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500 flex-wrap">
                  <span className={cn(
                    'px-1.5 py-0.5 rounded border',
                    alert.severity === 'critical' ? 'text-[#f5f5f5] border-[#f5f5f5]/30 bg-[#f5f5f5]/10' : 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
                  )}>
                    {alert.severity}
                  </span>
                  <span>{alert.source}</span>
                  <span className="text-[#c9b787]">Triaged in {alert.triageTime}</span>
                  <span>{alert.correlatedAlerts} correlated</span>
                </div>
                {selectedAlert?.id === alert.id && (
                  <div className="mt-3 pt-3 border-t border-white/8">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#c9b787]" />
                      <span className="text-[11px] text-[#c9b787] font-medium">Autonomous Resolution</span>
                    </div>
                    <p className="text-[11px] text-zinc-400">{alert.resolution}</p>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-zinc-500">
                      <span>Correlated {alert.correlatedAlerts} alerts into 1 case</span>
                      <span>Sources: {alert.source}</span>
                    </div>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-[#8a8a8a]" />
              ML Model Fleet — {totalModels.toLocaleString()} Models
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {mlModelClusters.map((cluster) => (
                <div key={cluster.category} className={cn(
                  'rounded-xl border p-3',
                  cluster.status === 'degraded' ? 'border-[#c9b787]/30 bg-[#c9b787]/5' : 'border-white/8 bg-white/3',
                )}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-medium text-white truncate">{cluster.category}</span>
                    <span className={cn(
                      'text-[9px] px-1.5 py-0.5 rounded border',
                      cluster.status === 'operational' ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10'
                        : cluster.status === 'retraining' ? 'text-[#8a8a8a] border-[#8a8a8a]/30 bg-[#8a8a8a]/10'
                        : 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10',
                    )}>
                      {cluster.status}
                    </span>
                  </div>
                  <div className="flex items-end justify-between mt-2">
                    <div>
                      <span className="text-sm font-bold text-white font-mono">{cluster.count}</span>
                      <span className="text-[10px] text-zinc-500 ml-1">models</span>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] text-[#c9b787] font-mono">{cluster.accuracy}%</span>
                      <span className="text-[9px] text-zinc-600 block">accuracy</span>
                    </div>
                  </div>
                  <div className="mt-1.5 h-1 rounded-full bg-white/5">
                    <div className="h-full rounded-full bg-[#c9b787]/50" style={{ width: `${cluster.accuracy}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Bot className="w-3.5 h-3.5 text-[#c9b787]" />
          AgentiX — Autonomous Agent Workforce
          <span className="text-[9px] text-zinc-600 font-mono ml-auto">Plan → Reason → Execute → Monitor</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
          {agentixWorkforce.map((agent) => (
            <div key={agent.id} className={cn(
              'rounded-xl border p-3 transition-all',
              agent.status === 'active' ? 'border-white/8 bg-white/3' : 'border-white/5 bg-white/[0.015]',
            )}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: `${PHASE_COLORS[agent.phase]}15`, border: `1px solid ${PHASE_COLORS[agent.phase]}30` }}>
                    <Bot className="w-3 h-3" style={{ color: PHASE_COLORS[agent.phase] }} />
                  </div>
                  <div>
                    <span className="text-[11px] font-medium text-white block">{agent.name}</span>
                    <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: PHASE_COLORS[agent.phase] }}>{agent.phase}</span>
                  </div>
                </div>
                <span className={cn(
                  'text-[9px] px-1.5 py-0.5 rounded border',
                  agent.status === 'active' ? 'text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10'
                    : agent.status === 'cooldown' ? 'text-[#8a8a8a] border-[#8a8a8a]/30 bg-[#8a8a8a]/10'
                    : 'text-zinc-500 border-zinc-700 bg-zinc-800/50',
                )}>
                  {agent.status}
                </span>
              </div>
              <p className="text-[10px] text-zinc-400 mb-2 leading-relaxed">{agent.task}</p>
              <div className="flex items-center gap-3 text-[10px] text-zinc-500">
                <span>{agent.alertsProcessed.toLocaleString()} processed</span>
                <span className="text-[#c9b787]">MTTR: {agent.mttr}</span>
                <span className="ml-auto font-mono">{agent.confidence}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-4">
        <div className="flex items-center gap-2 mb-3">
          <GitMerge className="w-4 h-4 text-[#c9b787]" />
          <span className="text-xs font-semibold text-[#c9b787]">Alert-to-Case Correlation Engine</span>
          <span className="text-[9px] text-zinc-500 font-mono ml-auto">Real-time · {correlation.compressionRatio} case compression</span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Raw Alerts (24h)', value: correlation.rawAlerts24h.toLocaleString(), color: '#f5f5f5' },
            { label: 'After Dedup', value: correlation.afterDedup.toLocaleString(), color: '#c9b787' },
            { label: 'Correlated Cases', value: correlation.correlatedCases.toLocaleString(), color: '#c9b787' },
            { label: 'Compression Ratio', value: correlation.compressionRatio, color: '#8a8a8a' },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-lg font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
              <div className="text-[9px] text-zinc-500">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
