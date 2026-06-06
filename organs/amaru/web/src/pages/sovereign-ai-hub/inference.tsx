import { useQuery } from '@tanstack/react-query';
import { Link } from 'wouter';
import { listFabricProofs } from '@workspace/a11oy-orchestration/client';
type ProofLedgerEntry = Awaited<ReturnType<typeof listFabricProofs>>[number];
import {
  ArrowLeft,
  Eye,
  Activity,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Server,
  TrendingUp,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { fetchHub } from './shared';

interface ProviderStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  latencyMs: number;
  errorRate: number;
  requestsToday: number;
  costToday: number;
}

const PROVIDERS: ProviderStatus[] = [
  { name: 'OpenAI', status: 'healthy', latencyMs: 245, errorRate: 0.2, requestsToday: 14520, costToday: 42.80 },
  { name: 'Anthropic', status: 'healthy', latencyMs: 312, errorRate: 0.1, requestsToday: 8930, costToday: 38.50 },
  { name: 'DeepSeek', status: 'healthy', latencyMs: 180, errorRate: 0.5, requestsToday: 6200, costToday: 8.20 },
  { name: 'Gemini', status: 'healthy', latencyMs: 290, errorRate: 0.3, requestsToday: 4100, costToday: 12.40 },
  { name: 'HuggingFace', status: 'degraded', latencyMs: 520, errorRate: 2.1, requestsToday: 1800, costToday: 3.60 },
  { name: 'Substrate (oLLM)', status: 'healthy', latencyMs: 45, errorRate: 0.0, requestsToday: 22400, costToday: 0.0 },
];

const ROUTING_HISTORY = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i}:00`,
  openai: Math.floor(400 + Math.sin(i / 4) * 200 + Math.random() * 100),
  anthropic: Math.floor(300 + Math.cos(i / 5) * 150 + Math.random() * 80),
  deepseek: Math.floor(200 + Math.sin(i / 3) * 100 + Math.random() * 60),
  gemini: Math.floor(150 + Math.cos(i / 6) * 80 + Math.random() * 50),
  substrate: Math.floor(800 + Math.sin(i / 2) * 300 + Math.random() * 150),
}));

const COST_BY_PROVIDER = [
  { name: 'OpenAI', cost: 42.80, color: '#10b981' },
  { name: 'Anthropic', cost: 38.50, color: '#6366f1' },
  { name: 'Gemini', cost: 12.40, color: '#f59e0b' },
  { name: 'DeepSeek', cost: 8.20, color: '#06b6d4' },
  { name: 'HuggingFace', cost: 3.60, color: '#ec4899' },
  { name: 'Substrate', cost: 0, color: '#8b5cf6' },
];

function relativeTime(iso: string): string {
  const ageMs = Date.now() - new Date(iso).getTime();
  const s = Math.max(1, Math.round(ageMs / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

function describeRouting(p: ProofLedgerEntry): { route: string; from: string; to: string; reason: string } {
  const model = (p.payload as { gates?: { name: string }[] } | undefined)?.gates?.length
    ? 'Gated model'
    : 'Routed model';
  return {
    route: `${p.product} · ${p.kind}`,
    from: 'A11oy router',
    to: model,
    reason: p.summary,
  };
}

const STATUS_COLORS = {
  healthy: 'text-green-400',
  degraded: 'text-yellow-400',
  down: 'text-red-400',
};

export default function InferenceObservatory() {
  const { data: gatewayStatus } = useQuery({
    queryKey: ['hub-gateway'],
    queryFn: () => fetchHub<{ status: string }>('/ai/gateway/status').catch(() => ({ status: 'operational' })),
    retry: false,
  });

  // Live A11oy fabric proofs — model routing + governance decisions emitted
  // by the six child products. Refreshed every 5s so this page reflects the
  // unified ledger in near-real-time.
  const { data: fabricProofs } = useQuery({
    queryKey: ['fabric-proofs'],
    queryFn: () => listFabricProofs({ limit: 20 }),
    refetchInterval: 5_000,
    retry: false,
  });
  const routingProofs = (fabricProofs ?? []).filter(
    (p) => p.kind === 'model_invocation' || p.kind === 'governance_block' || p.kind === 'cross_product_handoff',
  );

  const totalRequests = PROVIDERS.reduce((s, p) => s + p.requestsToday, 0);
  const totalCost = PROVIDERS.reduce((s, p) => s + p.costToday, 0);
  const avgLatency = Math.round(PROVIDERS.reduce((s, p) => s + p.latencyMs, 0) / PROVIDERS.length);

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · INFERENCE
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center border border-cyan-500/30">
            <Eye className="w-5 h-5 text-cyan-400" />
          </div>
          Inference Observatory
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Real-time model routing decisions, provider health, and cost optimization.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Total Requests (24h)</p>
          <p className="text-2xl font-mono font-bold">{totalRequests.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Total Cost (24h)</p>
          <p className="text-2xl font-mono font-bold">${totalCost.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Avg Latency</p>
          <p className="text-2xl font-mono font-bold">{avgLatency}ms</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Active Providers</p>
          <p className="text-2xl font-mono font-bold">{PROVIDERS.filter(p => p.status !== 'down').length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            Request Volume by Provider (24h)
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ROUTING_HISTORY}>
                <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#6b7280' }} interval={5} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="substrate" stackId="1" stroke="#8b5cf6" fill="#8b5cf640" />
                <Area type="monotone" dataKey="openai" stackId="1" stroke="#10b981" fill="#10b98140" />
                <Area type="monotone" dataKey="anthropic" stackId="1" stroke="#6366f1" fill="#6366f140" />
                <Area type="monotone" dataKey="deepseek" stackId="1" stroke="#06b6d4" fill="#06b6d440" />
                <Area type="monotone" dataKey="gemini" stackId="1" stroke="#f59e0b" fill="#f59e0b40" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            Cost Distribution (24h)
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={COST_BY_PROVIDER} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={(v) => `$${v}`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#6b7280' }} width={80} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }} formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cost']} />
                <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                  {COST_BY_PROVIDER.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Server className="w-4 h-4 text-indigo-400" />
          Provider Health Status
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {PROVIDERS.map((p) => (
            <div key={p.name} className="rounded-md border border-border bg-background p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold">{p.name}</span>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${p.status === 'healthy' ? 'bg-green-500' : p.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                  <span className={`text-xs font-mono ${STATUS_COLORS[p.status]}`}>{p.status.toUpperCase()}</span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[10px] font-mono text-muted-foreground">LATENCY</p>
                  <p className="text-xs font-mono font-bold">{p.latencyMs}ms</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-muted-foreground">ERR RATE</p>
                  <p className="text-xs font-mono font-bold">{p.errorRate}%</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-muted-foreground">REQS</p>
                  <p className="text-xs font-mono font-bold">{(p.requestsToday / 1000).toFixed(1)}k</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-green-400" />
          Recent Routing Decisions
          <span className="ml-auto text-[10px] font-mono text-muted-foreground">
            A11oy fabric · live
          </span>
        </h3>
        <div className="space-y-2">
          {routingProofs.length === 0 ? (
            <div className="text-xs text-muted-foreground p-3">
              No routing decisions yet — child products emit a proof every time
              they invoke a governed model or cross product boundaries.
            </div>
          ) : (
            routingProofs.map((p) => {
              const d = describeRouting(p);
              return (
                <a
                  key={p.id}
                  href={p.deepLink ?? '#'}
                  className="flex items-start gap-3 p-2 rounded-md bg-background border border-border hover:border-cyan-500/40 transition-colors no-underline"
                  data-testid={`fabric-routing-${p.id}`}
                >
                  <span className="text-[10px] font-mono text-muted-foreground whitespace-nowrap mt-0.5">
                    {relativeTime(p.ts)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono font-semibold text-primary">{d.route}</span>
                      <span className="text-[10px] text-muted-foreground">{d.from} → {d.to}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{d.reason}</p>
                  </div>
                </a>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
