import { useQuery } from '@tanstack/react-query';
import { Link } from 'wouter';
import { useState } from 'react';
import {
  ArrowLeft,
  Database,
  Search,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3,
  Layers,
} from 'lucide-react';
import { fetchHub } from './shared';

interface ManagedDataset {
  datasetId: string;
  name: string;
  domain: string;
  version: string;
  description?: string;
  splitStrategy: string;
  rowCount: number;
  featureCount: number;
  featureIds: string[];
  labelColumn: string;
  qualityReport: {
    dataQualityScore: number;
    missingValuePct: number;
    duplicateRowPct: number;
    outliersDetected: number;
    passed: boolean;
    issues: string[];
  } | null;
  status: string;
  createdAt: string;
  refreshedAt: string | null;
}

interface DatasetSummary {
  total: number;
  ready: number;
  failed: number;
  totalRows: number;
  domains: string[];
  avgQualityScore: number;
}

interface FeatureSummary {
  totalDefinitions: number;
  activeDomains: string[];
  computedFeatures: number;
}

const DOMAIN_COLORS: Record<string, string> = {
  vessels: '#06b6d4',
  terra: '#10b981',
  prism: '#8b5cf6',
  aegis: '#ef4444',
  szl: '#f59e0b',
  lyte: '#6366f1',
  sentra: '#ec4899',
};

const DOMAIN_LABELS: Record<string, string> = {
  vessels: 'Maritime Intelligence',
  terra: 'Real Estate Intelligence',
  prism: 'Legal Intelligence',
  aegis: 'Cyber Threat Intelligence',
  szl: 'Financial Intelligence',
  lyte: 'Infrastructure Operations',
  sentra: 'Cyber Resilience',
};

export default function DataEstateCatalog() {
  const [filterDomain, setFilterDomain] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');

  const { data: datasets, isLoading } = useQuery({
    queryKey: ['hub-datasets', filterDomain],
    queryFn: () => {
      const params = filterDomain ? `?domain=${filterDomain}` : '';
      return fetchHub<ManagedDataset[]>(`/ml/datasets${params}`).catch(() => []);
    },
    retry: false,
  });

  const { data: summary } = useQuery({
    queryKey: ['hub-datasets-summary'],
    queryFn: () => fetchHub<DatasetSummary>('/ml/datasets/summary').catch(() => null),
    retry: false,
  });

  const { data: featureSummary } = useQuery({
    queryKey: ['hub-features-summary'],
    queryFn: () => fetchHub<FeatureSummary>('/ml/features/summary').catch(() => null),
    retry: false,
  });

  const { data: featureCatalog } = useQuery({
    queryKey: ['hub-features-catalog'],
    queryFn: () => fetchHub<Record<string, Array<{ featureId: string; name: string; domain: string; dataType: string; description: string; tags: string[] }>>>('/ml/features/catalog').catch(() => ({})),
    retry: false,
  });

  const filtered = (datasets ?? []).filter((d) =>
    searchTerm ? d.name.toLowerCase().includes(searchTerm.toLowerCase()) || d.domain.toLowerCase().includes(searchTerm.toLowerCase()) : true
  );

  const allDomains = [...new Set((datasets ?? []).map(d => d.domain))];

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <Link href="/sovereign-ai-hub" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
          <ArrowLeft className="w-3 h-3" /> Sovereign AI Hub
        </Link>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          SOVEREIGN AI HUB · DATA ESTATE
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/30">
            <Database className="w-5 h-5 text-emerald-400" />
          </div>
          Data Estate Catalog
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse domain datasets with freshness indicators, quality scores, and feature store metadata.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Total Datasets</p>
          <p className="text-2xl font-mono font-bold">{summary?.total ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Total Records</p>
          <p className="text-2xl font-mono font-bold">{(summary?.totalRows ?? 0).toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Avg Quality</p>
          <p className="text-2xl font-mono font-bold">{summary?.avgQualityScore ?? 0}/100</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-mono text-muted-foreground uppercase mb-1">Feature Defs</p>
          <p className="text-2xl font-mono font-bold">{featureSummary?.totalDefinitions ?? 0}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search datasets..."
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
          {allDomains.map((d) => (
            <option key={d} value={d}>{d} — {DOMAIN_LABELS[d] ?? d}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Activity className="w-5 h-5 animate-spin mr-2" /> Loading data estate...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Database className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No datasets found. Bootstrap domain datasets to populate the catalog.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((ds) => (
            <DatasetCard key={ds.datasetId} dataset={ds} />
          ))}
        </div>
      )}

      {featureCatalog && Object.keys(featureCatalog).length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            Feature Store Catalog
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(featureCatalog).map(([domain, features]) => (
              <div key={domain} className="rounded-md border border-border bg-background p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: DOMAIN_COLORS[domain] ?? '#6b7280' }} />
                  <span className="text-xs font-semibold uppercase">{domain}</span>
                  <span className="text-[10px] font-mono text-muted-foreground ml-auto">{features.length} features</span>
                </div>
                <div className="space-y-1">
                  {features.slice(0, 5).map((f) => (
                    <div key={f.featureId} className="text-[10px] text-muted-foreground flex items-center gap-2">
                      <span className="font-mono text-foreground/80">{f.name}</span>
                      <span className="text-muted-foreground/60">({f.dataType})</span>
                    </div>
                  ))}
                  {features.length > 5 && (
                    <p className="text-[10px] text-muted-foreground/50">+{features.length - 5} more</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DatasetCard({ dataset }: { dataset: ManagedDataset }) {
  const domainColor = DOMAIN_COLORS[dataset.domain] ?? '#6b7280';
  const quality = dataset.qualityReport;

  return (
    <div className="rounded-lg border border-border bg-card p-4 hover:border-primary/20 transition-colors">
      <div className="flex items-start gap-4">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center border shrink-0"
          style={{ backgroundColor: `${domainColor}15`, borderColor: `${domainColor}40` }}
        >
          <Database className="w-5 h-5" style={{ color: domainColor }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-semibold truncate">{dataset.name}</h4>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
              dataset.status === 'ready'
                ? 'bg-green-500/10 text-green-400 border-green-500/30'
                : dataset.status === 'failed'
                  ? 'bg-red-500/10 text-red-400 border-red-500/30'
                  : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
            }`}>
              {dataset.status}
            </span>
          </div>
          {dataset.description && (
            <p className="text-xs text-muted-foreground mb-2">{dataset.description}</p>
          )}
          <div className="flex flex-wrap gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Domain: </span>
              <span className="font-mono" style={{ color: domainColor }}>{dataset.domain}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Records: </span>
              <span className="font-mono">{dataset.rowCount.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Features: </span>
              <span className="font-mono">{dataset.featureCount}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Version: </span>
              <span className="font-mono">{dataset.version}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Split: </span>
              <span className="font-mono">{dataset.splitStrategy}</span>
            </div>
            {quality && (
              <div>
                <span className="text-muted-foreground">Quality: </span>
                <span className={`font-mono ${quality.dataQualityScore >= 80 ? 'text-green-400' : quality.dataQualityScore >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {quality.dataQualityScore}/100
                </span>
              </div>
            )}
          </div>
          {quality && quality.issues.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {quality.issues.map((issue, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                  {issue}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
