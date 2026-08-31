import { useQuery } from '@tanstack/react-query';
import { Link } from 'wouter';
import {
  ArrowLeft,
  Brain,
  Activity,
  Eye,
  Compass,
  Target,
  Play,
  CheckCircle2,
  RefreshCcw,
  ArrowUpDown,
  Sparkles,
  AlertTriangle,
  BarChart3,
} from 'lucide-react';
import { fetchHub } from './shared';

const COGNITIVE_PHASES = [
  { name: 'Perceive', icon: Eye, color: '#06b6d4', description: 'Ingest and detect signals' },
  { name: 'Orient', icon: Compass, color: '#8b5cf6', description: 'Contextualize with history' },
  { name: 'Plan', icon: Target, color: '#f59e0b', description: 'Generate action options' },
  { name: 'Execute', icon: Play, color: '#10b981', description: 'Take governed action' },
  { name: 'Verify', icon: CheckCircle2, color: '#6366f1', description: 'Validate outcomes' },
  { name: 'Reflect', icon: RefreshCcw, color: '#ec4899', description: 'Learn from results' },
  { name: 'Update', icon: ArrowUpDown, color: '#14b8a6', description: 'Update self-model' },
  { name: 'Adapt', icon: Sparkles, color: '#f97316', description: 'Evolve tradecraft' },
];

interface CognitiveTrace {
  traceId: string;
  objective: string;
  status: string;
  phases: Array<{
    name: string;
    status: string;
    durationMs: number;
    output?: string;
  }>;
  startedAt: string;
  completedAt?: string;
  totalDurationMs: number;
}

interface SkillUsage {
  skillId: string;
  name: string;
  invocations: number;
  avgConfidence: number;
  domain: string;
}

const MOCK_SKILLS: SkillUsage[] = [
  { skillId: 's1', name: 'entity-extraction', invocations: 1240, avgConfidence: 0.92, domain: 'cross-domain' },
  { skillId: 's2', name: 'threat-triage', invocations: 890, avgConfidence: 0.88, domain: 'aegis' },
  { skillId: 's3', name: 'deal-scoring', invocations: 670, avgConfidence: 0.85, domain: 'szl' },
  { skillId: 's4', name: 'vessel-anomaly', invocations: 520, avgConfidence: 0.91, domain: 'vessels' },
  { skillId: 's5', name: 'property-valuation', invocations: 480, avgConfidence: 0.87, domain: 'terra' },
  { skillId: 's6', name: 'case-outcome', invocations: 390, avgConfidence: 0.83, domain: 'prism' },
  { skillId: 's7', name: 'evidence-chain', invocations: 340, avgConfidence: 0.94, domain: 'cross-domain' },
  { skillId: 's8', name: 'risk-scoring', invocations: 290, avgConfidence: 0.89, domain: 'sentra' },
  { skillId: 's9', name: 'sla-prediction', invocations: 210, avgConfidence: 0.86, domain: 'lyte' },
  { skillId: 's10', name: 'fusion-scan', invocations: 180, avgConfidence: 0.90, domain: 'cross-domain' },
];

const DRIFT_ALERTS = [
  { id: 1, type: 'behavioral', message: 'Agent entity-extraction showing 12% accuracy drop on maritime entities', severity: 'medium', timestamp: '34m ago' },
  { id: 2, type: 'performance', message: 'Cognitive loop P95 latency increased from 1.2s to 2.8s', severity: 'high', timestamp: '1h ago' },
  { id: 3, type: 'pattern', message: 'New cross-domain pattern detected: real-estate ↔ cyber correlation', severity: 'info', timestamp: '2h ago' },
];

const REASONING_METRICS = [
  { label: 'Avg Loop Duration', value: '1.4s', trend: 'stable' },
  { label: 'Plan Quality Score', value: '87/100', trend: 'up' },
  { label: 'Verify Pass Rate', value: '94.2%', trend: 'up' },
  { label: 'Self-Correction Rate', value: '8.3%', trend: 'down' },
  { label: 'Evidence Coverage', value: '91.5%', trend: 'up' },
  { label: 'Counterfactual Yield', value: '23%', trend: 'stable' },
];

export default function CognitiveInsights() {
  const { data: checkpoints } = useQuery({
    queryKey: ['hub-cognitive-checkpoints'],
    queryFn: () => fetchHub<{ checkpoints: Array<{ id: string; agentId: string; objective: string; status: string; createdAt: string }> }>('/cognitive-runtime/checkpoints').catch(() => ({ checkpoints: [] })),
    retry: false,
  });

  const traces = checkpoints?.checkpoints ?? [];

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · COGNITIVE INSIGHTS
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center border border-violet-500/30">
            <Brain className="w-5 h-5 text-violet-400" />
          </div>
          Cognitive Insights
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Agent reasoning traces, cognitive loop visualization, skill utilization, and drift detection.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
          <Brain className="w-4 h-4 text-violet-400" />
          8-Phase Cognitive Loop (OODA+)
        </h3>
        <div className="flex items-center gap-1 overflow-x-auto pb-2">
          {COGNITIVE_PHASES.map((phase, i) => (
            <div key={phase.name} className="flex items-center">
              <div className="flex flex-col items-center min-w-[90px]">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center border-2"
                  style={{ borderColor: phase.color, backgroundColor: `${phase.color}15` }}
                >
                  <phase.icon className="w-5 h-5" style={{ color: phase.color }} />
                </div>
                <p className="text-[10px] font-mono font-bold mt-1" style={{ color: phase.color }}>{phase.name}</p>
                <p className="text-[9px] text-muted-foreground text-center">{phase.description}</p>
              </div>
              {i < COGNITIVE_PHASES.length - 1 && (
                <div className="w-6 h-px bg-border mx-1 shrink-0" />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {REASONING_METRICS.map((m) => (
          <div key={m.label} className="rounded-lg border border-border bg-card p-3 text-center">
            <p className="text-[10px] font-mono text-muted-foreground uppercase mb-1">{m.label}</p>
            <p className="text-sm font-mono font-bold">{m.value}</p>
            <p className={`text-[10px] ${m.trend === 'up' ? 'text-green-400' : m.trend === 'down' ? 'text-red-400' : 'text-muted-foreground'}`}>
              {m.trend === 'up' ? '↑' : m.trend === 'down' ? '↓' : '→'} {m.trend}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Skill Utilization Heatmap
          </h3>
          <div className="space-y-2">
            {MOCK_SKILLS.map((skill) => {
              const maxInvocations = Math.max(...MOCK_SKILLS.map(s => s.invocations));
              const pct = (skill.invocations / maxInvocations) * 100;
              return (
                <div key={skill.skillId} className="flex items-center gap-3">
                  <span className="text-xs font-mono w-36 truncate text-muted-foreground">{skill.name}</span>
                  <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        background: `linear-gradient(90deg, ${skill.avgConfidence > 0.9 ? '#10b981' : skill.avgConfidence > 0.85 ? '#6366f1' : '#f59e0b'}, ${skill.avgConfidence > 0.9 ? '#10b98180' : skill.avgConfidence > 0.85 ? '#6366f180' : '#f59e0b80'})`,
                      }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground w-12 text-right">{skill.invocations}</span>
                  <span className="text-[10px] font-mono w-10 text-right" style={{ color: skill.avgConfidence > 0.9 ? '#10b981' : '#f59e0b' }}>
                    {(skill.avgConfidence * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Drift Detection Alerts
          </h3>
          <div className="space-y-2">
            {DRIFT_ALERTS.map((alert) => (
              <div key={alert.id} className={`p-3 rounded-md border ${
                alert.severity === 'high' ? 'border-red-500/30 bg-red-500/5' :
                alert.severity === 'medium' ? 'border-yellow-500/30 bg-yellow-500/5' :
                'border-border bg-background'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[10px] font-mono uppercase ${
                    alert.severity === 'high' ? 'text-red-400' :
                    alert.severity === 'medium' ? 'text-yellow-400' :
                    'text-muted-foreground'
                  }`}>
                    {alert.type} · {alert.severity}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground">{alert.timestamp}</span>
                </div>
                <p className="text-xs text-muted-foreground">{alert.message}</p>
              </div>
            ))}
          </div>

          {traces.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-semibold mb-2 text-muted-foreground">Recent Cognitive Checkpoints</h4>
              <div className="space-y-1">
                {traces.slice(0, 5).map((t) => (
                  <div key={t.id} className="text-[10px] p-2 rounded bg-background border border-border flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${t.status === 'completed' ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    <span className="font-mono truncate flex-1">{t.objective}</span>
                    <span className="text-muted-foreground">{t.agentId}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
