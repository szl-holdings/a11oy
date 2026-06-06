import { useQuery } from '@tanstack/react-query';
import { Link } from 'wouter';
import {
  ArrowLeft,
  FlaskConical,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Play,
  BarChart3,
  Shield,
} from 'lucide-react';
import { fetchHub } from './shared';

interface FineTuningJob {
  id: number;
  agentId: string;
  provider: string;
  baseModel: string;
  status: string;
  trainingPairCount: number;
  createdAt: string;
  completedAt?: string;
}

interface CanaryStatus {
  agentId: string;
  isActive: boolean;
  canaryModel: string;
  baselineModel: string;
  trafficPct: number;
  canaryScore?: number;
  baselineScore?: number;
  activatedAt?: string;
}

interface TrainingRun {
  runId: string;
  domain: string;
  modelType: string;
  algorithmFamily: string;
  status: string;
  stage: string;
  trainMetrics: Record<string, number> | null;
  testMetrics: Record<string, number> | null;
  durationSeconds: number | null;
  triggeredBy: string;
  startedAt: string;
  completedAt: string | null;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  succeeded: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  running: <Activity className="w-4 h-4 text-yellow-400 animate-spin" />,
  pending: <Clock className="w-4 h-4 text-muted-foreground" />,
  validating_output: <Shield className="w-4 h-4 text-blue-400" />,
};

export default function DomainDistillery() {
  const { data: ftJobs, isLoading: ftLoading } = useQuery({
    queryKey: ['hub-ft-jobs'],
    queryFn: () => fetchHub<{ jobs: FineTuningJob[] }>('/fine-tuning/jobs').catch(() => ({ jobs: [] })),
    retry: false,
  });

  const { data: canaries } = useQuery({
    queryKey: ['hub-canaries'],
    queryFn: () => fetchHub<{ canaries: CanaryStatus[] }>('/fine-tuning/canary').catch(() => ({ canaries: [] })),
    retry: false,
  });

  const { data: trainingRuns } = useQuery({
    queryKey: ['hub-training-runs'],
    queryFn: () => fetchHub<TrainingRun[]>('/ml/training/runs').catch(() => []),
    retry: false,
  });

  const { data: pipelineHealth } = useQuery({
    queryKey: ['hub-pipeline-health'],
    queryFn: () => fetchHub<{ status: string; components: Record<string, { healthy: boolean }> }>('/fine-tuning/health').catch(() => null),
    retry: false,
  });

  const jobs = ftJobs?.jobs ?? [];
  const canaryList = canaries?.canaries ?? [];
  const runs = trainingRuns ?? [];

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · DOMAIN DISTILLERY
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center border border-amber-500/30">
            <FlaskConical className="w-5 h-5 text-amber-400" />
          </div>
          Domain Distillery
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Governed fine-tuning dashboard with canary testing, data quality gates, and training jobs.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Fine-Tuning Jobs</p>
          <p className="text-2xl font-mono font-bold">{jobs.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Active Canaries</p>
          <p className="text-2xl font-mono font-bold">{canaryList.filter(c => c.isActive).length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">ML Training Runs</p>
          <p className="text-2xl font-mono font-bold">{runs.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Pipeline Health</p>
          <p className="text-2xl font-mono font-bold text-green-400">{pipelineHealth?.status ?? 'OK'}</p>
        </div>
      </div>

      {canaryList.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Canary Deployments
          </h3>
          <div className="space-y-2">
            {canaryList.map((c) => (
              <div key={c.agentId} className="flex items-center gap-4 p-3 rounded-md bg-background border border-border">
                <div className={`w-2 h-2 rounded-full ${c.isActive ? 'bg-green-500 animate-pulse' : 'bg-muted-foreground'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold">{c.agentId}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.canaryModel} vs {c.baselineModel} · {c.trafficPct}% canary traffic
                  </p>
                </div>
                {c.canaryScore !== undefined && (
                  <div className="text-right">
                    <p className="text-xs font-mono">
                      <span className="text-green-400">{c.canaryScore?.toFixed(2)}</span>
                      {' / '}
                      <span className="text-muted-foreground">{c.baselineScore?.toFixed(2)}</span>
                    </p>
                    <p className="text-[10px] text-muted-foreground">canary / baseline</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-amber-400" />
            Fine-Tuning Jobs
          </h3>
          {ftLoading ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Activity className="w-4 h-4 animate-spin mr-2" /> Loading...
            </div>
          ) : jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No fine-tuning jobs found.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {jobs.slice(0, 20).map((job) => (
                <div key={job.id} className="flex items-center gap-3 p-2 rounded-md bg-background border border-border">
                  {STATUS_ICON[job.status] ?? <Clock className="w-4 h-4 text-muted-foreground" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold truncate">{job.agentId}</p>
                    <p className="text-[10px] text-muted-foreground">{job.provider} · {job.baseModel} · {job.trainingPairCount} pairs</p>
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground">{job.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            ML Training Runs
          </h3>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No training runs found. Bootstrap the ML pipeline to start.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {runs.slice(0, 20).map((run) => (
                <div key={run.runId} className="flex items-center gap-3 p-2 rounded-md bg-background border border-border">
                  {STATUS_ICON[run.status] ?? <Clock className="w-4 h-4 text-muted-foreground" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold truncate">{run.domain}/{run.modelType}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {run.algorithmFamily} · {run.stage} · {run.triggeredBy}
                    </p>
                  </div>
                  {run.testMetrics && (
                    <span className="text-[10px] font-mono text-green-400">
                      {run.testMetrics.accuracy
                        ? `${(run.testMetrics.accuracy * 100).toFixed(1)}%`
                        : run.testMetrics.r2
                          ? `R²=${run.testMetrics.r2.toFixed(3)}`
                          : ''}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
