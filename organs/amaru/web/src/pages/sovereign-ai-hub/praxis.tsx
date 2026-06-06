import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'wouter';
import { useState } from 'react';
import {
  ArrowLeft,
  Sparkles,
  Search,
  Activity,
  Network,
  AlertCircle,
  Zap,
  Send,
  Globe,
} from 'lucide-react';
import { Button } from '@/components/ui';
import { fetchHub } from './shared';

interface FusionAlert {
  id: string;
  severity: string;
  category: string;
  title: string;
  summary: string;
  domains: string[];
  status: string;
  createdAt: string;
  evidenceChain?: Array<{ domain: string; fact: string; confidence: number }>;
}

interface FusionStats {
  totalAlerts: number;
  bySeverity: Record<string, number>;
  byDomain: Record<string, number>;
  scanCount: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'border-red-500/30 bg-red-500/10 text-red-400',
  high: 'border-orange-500/30 bg-orange-500/10 text-orange-400',
  medium: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  low: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  info: 'border-muted bg-muted/10 text-muted-foreground',
};

const DOMAIN_COLORS: Record<string, string> = {
  vessels: '#06b6d4',
  terra: '#10b981',
  prism: '#8b5cf6',
  aegis: '#ef4444',
  szl: '#f59e0b',
  sentra: '#ec4899',
};

export default function PraxisPlayground() {
  const [query, setQuery] = useState('');

  const { data: alerts } = useQuery({
    queryKey: ['hub-fusion-alerts'],
    queryFn: () => fetchHub<{ alerts: FusionAlert[] }>('/fusion/alerts?limit=20').catch(() => ({ alerts: [] })),
    retry: false,
  });

  const { data: stats } = useQuery({
    queryKey: ['hub-fusion-stats'],
    queryFn: () => fetchHub<{ stats: FusionStats }>('/fusion/stats').catch(() => ({ stats: { totalAlerts: 0, bySeverity: {}, byDomain: {}, scanCount: 0 } })),
    retry: false,
  });

  const { data: patterns } = useQuery({
    queryKey: ['hub-fusion-patterns'],
    queryFn: () => fetchHub<{ patterns: Array<{ id: string; name: string; description: string; domains: string[]; triggerCount: number }> }>('/fusion/patterns').catch(() => ({ patterns: [] })),
    retry: false,
  });

  const scanMutation = useMutation({
    mutationFn: () => fetchHub('/fusion/scan', { method: 'POST', body: JSON.stringify({}) }),
  });

  const fusionAlerts = alerts?.alerts ?? [];
  const fusionStats = stats?.stats;
  const fusionPatterns = patterns?.patterns ?? [];

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · PRAXIS PLAYGROUND
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-pink-500/10 flex items-center justify-center border border-pink-500/30">
            <Sparkles className="w-5 h-5 text-pink-400" />
          </div>
          PRAXIS Playground
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Interactive cross-domain intelligence workspace — entity resolution, fusion queries, evidence threading.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Fusion Alerts</p>
          <p className="text-2xl font-mono font-bold">{fusionStats?.totalAlerts ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Critical</p>
          <p className="text-2xl font-mono font-bold text-red-400">{(fusionStats?.bySeverity as Record<string, number> | undefined)?.critical ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Domains Active</p>
          <p className="text-2xl font-mono font-bold">{Object.keys(fusionStats?.byDomain ?? {}).length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Scans</p>
          <p className="text-2xl font-mono font-bold">{fusionStats?.scanCount ?? 0}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-pink-400" />
          Intelligence Query
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Query the fusion cortex... (e.g. 'vessels linked to sanctioned entities')"
            className="flex-1 bg-background border border-border rounded-md px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button
            variant="default"
            size="sm"
            onClick={() => scanMutation.mutate()}
            isLoading={scanMutation.isPending}
          >
            <Zap className="w-4 h-4 mr-1" /> Scan
          </Button>
        </div>
        {scanMutation.isSuccess && (
          <div className="mt-3 p-3 rounded-md bg-green-500/10 border border-green-500/20 text-xs text-green-400">
            Fusion scan completed. Alerts updated below.
          </div>
        )}
      </div>

      {fusionPatterns.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Network className="w-4 h-4 text-indigo-400" />
            Cross-Domain Patterns
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {fusionPatterns.slice(0, 8).map((p) => (
              <div key={p.id} className="p-3 rounded-md bg-background border border-border">
                <div className="flex items-start justify-between mb-1">
                  <p className="text-xs font-semibold">{p.name}</p>
                  <span className="text-[10px] font-mono text-muted-foreground">{p.triggerCount} triggers</span>
                </div>
                <p className="text-[10px] text-muted-foreground mb-2">{p.description}</p>
                <div className="flex gap-1">
                  {p.domains.map((d) => (
                    <span
                      key={d}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded-full border"
                      style={{ borderColor: `${DOMAIN_COLORS[d] ?? '#6b7280'}50`, color: DOMAIN_COLORS[d] ?? '#6b7280' }}
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-400" />
          Fusion Alert Feed
        </h3>
        {fusionAlerts.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No fusion alerts yet. Run a scan to detect cross-domain patterns.
          </p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {fusionAlerts.map((alert) => (
              <div key={alert.id} className={`p-3 rounded-md border ${SEVERITY_COLORS[alert.severity] ?? SEVERITY_COLORS.info}`}>
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase">{alert.severity}</span>
                    <span className="text-xs font-semibold">{alert.title}</span>
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground">{alert.status}</span>
                </div>
                <p className="text-xs text-muted-foreground mb-2">{alert.summary}</p>
                <div className="flex gap-1 flex-wrap">
                  {alert.domains.map((d) => (
                    <span
                      key={d}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded-full border"
                      style={{ borderColor: `${DOMAIN_COLORS[d] ?? '#6b7280'}50`, color: DOMAIN_COLORS[d] ?? '#6b7280' }}
                    >
                      {d}
                    </span>
                  ))}
                </div>
                {alert.evidenceChain && alert.evidenceChain.length > 0 && (
                  <div className="mt-2 pl-3 border-l-2 border-border space-y-1">
                    {alert.evidenceChain.slice(0, 3).map((e, i) => (
                      <div key={i} className="text-[10px]">
                        <span className="font-mono" style={{ color: DOMAIN_COLORS[e.domain] ?? '#6b7280' }}>[{e.domain}]</span>{' '}
                        <span className="text-muted-foreground">{e.fact}</span>{' '}
                        <span className="text-muted-foreground/60">({(e.confidence * 100).toFixed(0)}%)</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
