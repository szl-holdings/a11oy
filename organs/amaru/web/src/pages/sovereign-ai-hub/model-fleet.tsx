import { useQuery } from '@tanstack/react-query';
import { Link } from 'wouter';
import { Badge } from '@/components/ui';
import {
  ArrowLeft,
  Layers,
  Search,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
} from 'lucide-react';
import { useState } from 'react';
import { fetchHub } from './shared';

interface ModelCard {
  modelVersionId: string;
  modelName: string;
  domain: string;
  version: string;
  algorithmFamily: string;
  lifecycle: string;
  isProduction: boolean;
  featureIds: string[];
  trainMetrics: Record<string, number>;
  testMetrics: Record<string, number>;
  tags: string[];
  createdAt: string;
}

const PROVIDER_COLORS: Record<string, string> = {
  vessels: '#06b6d4',
  terra: '#10b981',
  prism: '#8b5cf6',
  aegis: '#ef4444',
  szl: '#f59e0b',
  lyte: '#6366f1',
  sentra: '#ec4899',
};

const LIFECYCLE_COLORS: Record<string, string> = {
  experimental: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  staging: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  production: 'bg-green-500/20 text-green-400 border-green-500/30',
  deprecated: 'bg-red-500/20 text-red-400 border-red-500/30',
};

export default function ModelFleetConsole() {
  const [filterDomain, setFilterDomain] = useState<string>('');
  const [filterLifecycle, setFilterLifecycle] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');

  const { data: models, isLoading } = useQuery({
    queryKey: ['hub-models', filterDomain, filterLifecycle],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filterDomain) params.set('domain', filterDomain);
      if (filterLifecycle) params.set('lifecycle', filterLifecycle);
      return fetchHub<ModelCard[]>(`/ml/registry/models?${params}`);
    },
  });

  const { data: summary } = useQuery({
    queryKey: ['hub-registry-summary'],
    queryFn: () => fetchHub<{
      totalVersions: number;
      lifecycleCounts: Record<string, number>;
      domains: string[];
      productionModels: Array<{ modelVersionId: string; modelName: string; domain: string }>;
    }>('/ml/registry/summary'),
  });

  const filtered = (models ?? []).filter((m) =>
    searchTerm ? m.modelName.toLowerCase().includes(searchTerm.toLowerCase()) : true
  );

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · MODEL FLEET
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center border border-indigo-500/30">
            <Layers className="w-5 h-5 text-indigo-400" />
          </div>
          Model Fleet Console
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browsable model cards with lifecycle governance, routing lanes, and performance metrics.
        </p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Total Versions" value={summary.totalVersions} icon={<Layers className="w-4 h-4 text-indigo-400" />} />
          <StatCard label="Production" value={summary.lifecycleCounts?.production ?? 0} icon={<CheckCircle2 className="w-4 h-4 text-green-400" />} />
          <StatCard label="Staging" value={summary.lifecycleCounts?.staging ?? 0} icon={<Clock className="w-4 h-4 text-blue-400" />} />
          <StatCard label="Experimental" value={summary.lifecycleCounts?.experimental ?? 0} icon={<Zap className="w-4 h-4 text-yellow-400" />} />
        </div>
      )}

      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search models..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-card border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <select
          value={filterDomain}
          onChange={(e) => setFilterDomain(e.target.value)}
          className="bg-card border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All Domains</option>
          {(summary?.domains ?? []).map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          value={filterLifecycle}
          onChange={(e) => setFilterLifecycle(e.target.value)}
          className="bg-card border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All Stages</option>
          <option value="experimental">Experimental</option>
          <option value="staging">Staging</option>
          <option value="production">Production</option>
          <option value="deprecated">Deprecated</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Activity className="w-5 h-5 animate-spin mr-2" /> Loading model fleet...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No models found. Run ML pipeline bootstrap to seed the registry.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((model) => (
            <ModelCardView key={model.modelVersionId} model={model} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs font-mono uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-mono font-bold">{value}</p>
    </div>
  );
}

function ModelCardView({ model }: { model: ModelCard }) {
  const domainColor = PROVIDER_COLORS[model.domain] ?? '#6366f1';
  const accuracy = model.testMetrics?.accuracy ?? model.testMetrics?.r2 ?? model.testMetrics?.auc;

  return (
    <div className="rounded-lg border border-border bg-card p-4 hover:border-primary/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: domainColor }}
          />
          <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            {model.domain}
          </span>
        </div>
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${LIFECYCLE_COLORS[model.lifecycle] ?? ''}`}>
          {model.lifecycle}
        </span>
      </div>

      <h3 className="text-sm font-semibold truncate mb-1" title={model.modelName}>
        {model.modelName}
      </h3>
      <p className="text-xs text-muted-foreground mb-3">
        v{model.version} · {model.algorithmFamily}
      </p>

      <div className="grid grid-cols-2 gap-2 mb-3">
        {accuracy !== undefined && (
          <div>
            <p className="text-[10px] font-mono text-muted-foreground uppercase">Accuracy</p>
            <p className="text-sm font-mono font-bold">{(accuracy * 100).toFixed(1)}%</p>
          </div>
        )}
        {model.testMetrics?.f1 !== undefined && (
          <div>
            <p className="text-[10px] font-mono text-muted-foreground uppercase">F1 Score</p>
            <p className="text-sm font-mono font-bold">{(model.testMetrics.f1 * 100).toFixed(1)}%</p>
          </div>
        )}
        <div>
          <p className="text-[10px] font-mono text-muted-foreground uppercase">Features</p>
          <p className="text-sm font-mono font-bold">{model.featureIds?.length ?? 0}</p>
        </div>
        {model.isProduction && (
          <div className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-green-400" />
            <span className="text-xs text-green-400 font-mono">PROD</span>
          </div>
        )}
      </div>

      {model.tags && model.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {model.tags.slice(0, 4).map((tag) => (
            <span key={tag} className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border text-muted-foreground">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
