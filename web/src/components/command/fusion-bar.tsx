import { AlertTriangle, ChevronRight, Info, Loader2, Search, X, Zap } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface DomainSignal {
  title: string;
  summary: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  timestamp: number;
}

interface DomainResult {
  domain: string;
  domainLabel: string;
  relevanceScore: number;
  signals: DomainSignal[];
  insight: string;
}

interface Correlation {
  title: string;
  domains: string[];
  description: string;
  confidence: number;
}

interface FusedResult {
  query: string;
  answeredAt: number;
  domainsQueried: string[];
  domainResults: DomainResult[];
  fusedAnswer: string;
  correlations: Correlation[];
  recommendedActions: string[];
  overallRisk: 'critical' | 'high' | 'medium' | 'low' | 'nominal';
  confidence: number;
  liveDataSources?: string[];
}

interface FusionBarProps {
  apiBase?: string;
}

const DOMAIN_COLORS: Record<string, string> = {
  vessels: 'var(--gi-accent-blue)',
  aegis: '#ef4444',
  terra: '#22c55e',
  prism: '#8b5cf6',
  lyte: '#f59e0b',
  'szl-holdings': '#8b7ac8',
  carlota: '#ec4899',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#6b7280',
  info: '#22c55e',
};

const SUGGESTIONS = [
  'Brief me on compound risks this week',
  "What's the maritime impact on real estate?",
  'Current cyber threat posture and legal implications',
  'Portfolio risk snapshot across all domains',
  'Summarize overnight signals',
];

function RiskBadge({ risk }: { risk: string }) {
  const color = SEVERITY_COLORS[risk] ?? '#6b7280';
  return (
    <span
      className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
      }}
    >
      {risk}
    </span>
  );
}

function DomainBadge({ domain, live = false }: { domain: string; live?: boolean }) {
  const color = DOMAIN_COLORS[domain] ?? '#6b7280';
  return (
    <span
      className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded inline-flex items-center gap-1"
      style={{
        color,
        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      {domain}
      {live && (
        <span
          className="inline-flex items-center gap-0.5"
          style={{ color: '#22c55e' }}
          title={`Real-time data from ${domain} database`}
          aria-label={`Real-time data from ${domain} database`}
          data-testid={`live-indicator-${domain}`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: '#22c55e', boxShadow: '0 0 4px #22c55e' }}
          />
          Live
        </span>
      )}
    </span>
  );
}

export function FusionBar({ apiBase = '' }: FusionBarProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FusedResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setShowSuggestions(false);

    try {
      const res = await fetch(`${apiBase}/api/cross-domain-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed }),
      });
      const data = await res.json();
      if (data.success && data.result) {
        setResult(data.result);
      } else {
        setError('Query failed — please try again.');
      }
    } catch {
      setError('Unable to reach the fusion engine.');
    } finally {
      setLoading(false);
    }
  }

  function handleSuggestion(s: string) {
    setQuery(s);
    setShowSuggestions(false);
    submit(s);
  }

  function clear() {
    setQuery('');
    setResult(null);
    setError(null);
    inputRef.current?.focus();
  }

  return (
    <div ref={panelRef} className="w-full flex flex-col gap-4">
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-xl"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-surface-border)',
          boxShadow: result
            ? '0 0 0 1px #8b7ac8, 0 0 20px color-mix(in srgb, #8b7ac8 12%, transparent)'
            : undefined,
        }}
      >
        <Zap className="w-4 h-4 shrink-0" style={{ color: '#8b7ac8' }} />
        <input
          ref={inputRef}
          className="flex-1 bg-transparent outline-none text-sm placeholder:text-sm"
          style={{ color: 'var(--color-fg-primary)' }}
          placeholder="Ask anything — brief me on compound risks, maritime impact, cyber posture…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!result) setShowSuggestions(e.target.value.length === 0);
          }}
          onFocus={() => {
            if (!query && !result) setShowSuggestions(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submit(query);
            if (e.key === 'Escape') {
              setShowSuggestions(false);
              clear();
            }
          }}
        />
        {loading && (
          <Loader2 className="w-4 h-4 animate-spin shrink-0" style={{ color: '#8b7ac8' }} />
        )}
        {(query || result) && !loading && (
          <button
            onClick={clear}
            aria-label="Clear search"
            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
          >
            <X className="w-4 h-4" style={{ color: 'var(--color-fg-muted)' }} />
          </button>
        )}
        {!loading && (
          <button
            onClick={() => submit(query)}
            disabled={!query.trim()}
            className="shrink-0 px-3 py-1 rounded-lg text-xs font-bold tracking-wide transition-opacity disabled:opacity-30"
            style={{ backgroundColor: '#8b7ac8', color: '#fff' }}
          >
            Ask
          </button>
        )}
      </div>

      {showSuggestions && !result && (
        <div
          className="rounded-xl overflow-hidden"
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-surface-border)',
          }}
        >
          <div
            className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest"
            style={{
              color: 'var(--color-fg-muted)',
              borderBottom: '1px solid var(--color-surface-border)',
            }}
          >
            Suggested queries
          </div>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleSuggestion(s)}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-white/5 transition-colors"
              style={{ color: 'var(--color-fg-secondary)' }}
            >
              <Search className="w-3 h-3 shrink-0" style={{ color: 'var(--color-fg-muted)' }} />
              {s}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
          style={{
            backgroundColor: 'color-mix(in srgb, #ef4444 10%, transparent)',
            border: '1px solid color-mix(in srgb, #ef4444 30%, transparent)',
            color: '#ef4444',
          }}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          <div
            className="rounded-xl p-5 flex flex-col gap-3"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-surface-border)',
              borderLeftWidth: '3px',
              borderLeftColor: SEVERITY_COLORS[result.overallRisk] ?? '#6b7280',
            }}
          >
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4" style={{ color: '#8b7ac8' }} />
                <span
                  className="text-xs font-bold uppercase tracking-widest"
                  style={{ color: '#8b7ac8' }}
                >
                  Fusion Intelligence
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <RiskBadge risk={result.overallRisk} />
                <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                  {result.domainsQueried.length} domains · {Math.round(result.confidence * 100)}%
                  confidence
                </span>
              </div>
            </div>

            <p
              className="text-sm leading-relaxed"
              style={{ color: 'var(--color-fg-primary)', whiteSpace: 'pre-wrap' }}
            >
              {result.fusedAnswer.replace(/\*\*(.*?)\*\*/g, '$1')}
            </p>

            <div className="flex flex-wrap gap-1.5">
              {result.domainsQueried.map((d) => (
                <DomainBadge
                  key={d}
                  domain={d}
                  live={result.liveDataSources?.includes(d) ?? false}
                />
              ))}
            </div>
          </div>

          {result.correlations.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3
                className="text-[10px] font-bold uppercase tracking-widest px-1"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                Cross-Domain Correlations
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {result.correlations.map((c, i) => (
                  <div
                    key={i}
                    className="rounded-lg p-3 flex flex-col gap-1.5"
                    style={{
                      backgroundColor: 'var(--color-bg-elevated)',
                      border: '1px solid var(--color-surface-border)',
                    }}
                  >
                    <div className="text-xs font-bold" style={{ color: 'var(--color-fg-primary)' }}>
                      {c.title}
                    </div>
                    <div
                      className="text-[11px] leading-relaxed"
                      style={{ color: 'var(--color-fg-muted)' }}
                    >
                      {c.description}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap mt-1">
                      {c.domains.map((d) => (
                        <DomainBadge
                          key={d}
                          domain={d}
                          live={result.liveDataSources?.includes(d) ?? false}
                        />
                      ))}
                      <span
                        className="text-[10px] ml-auto"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        {Math.round(c.confidence * 100)}% conf.
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.recommendedActions.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3
                className="text-[10px] font-bold uppercase tracking-widest px-1"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                Recommended Actions
              </h3>
              <div
                className="rounded-xl overflow-hidden"
                style={{
                  backgroundColor: 'var(--color-bg-elevated)',
                  border: '1px solid var(--color-surface-border)',
                }}
              >
                {result.recommendedActions.map((action, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-4 py-3"
                    style={{
                      borderBottom:
                        i < result.recommendedActions.length - 1
                          ? '1px solid var(--color-surface-border)'
                          : undefined,
                    }}
                  >
                    <ChevronRight className="w-3.5 h-3.5 shrink-0" style={{ color: '#8b7ac8' }} />
                    <span className="text-xs" style={{ color: 'var(--color-fg-secondary)' }}>
                      {action}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.domainResults.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3
                className="text-[10px] font-bold uppercase tracking-widest px-1"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                Domain Breakdown
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {result.domainResults.slice(0, 6).map((dr) => (
                  <div
                    key={dr.domain}
                    className="rounded-lg p-3 flex flex-col gap-2"
                    style={{
                      backgroundColor: 'var(--color-bg-elevated)',
                      border: '1px solid var(--color-surface-border)',
                      borderLeftWidth: '2px',
                      borderLeftColor: DOMAIN_COLORS[dr.domain] ?? '#6b7280',
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className="text-xs font-bold"
                        style={{ color: 'var(--color-fg-primary)' }}
                      >
                        {dr.domainLabel}
                      </span>
                      <div className="flex items-center gap-1">
                        <Info className="w-3 h-3" style={{ color: 'var(--color-fg-muted)' }} />
                        <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                          {Math.round(dr.relevanceScore * 100)}% relevant
                        </span>
                      </div>
                    </div>
                    <p
                      className="text-[11px] leading-relaxed"
                      style={{ color: 'var(--color-fg-muted)' }}
                    >
                      {dr.insight}
                    </p>
                    {dr.signals.slice(0, 2).map((sig, j) => (
                      <div
                        key={j}
                        className="text-[10px] px-2 py-1 rounded"
                        style={{
                          backgroundColor: `color-mix(in srgb, ${SEVERITY_COLORS[sig.severity] ?? '#6b7280'} 8%, transparent)`,
                          color: SEVERITY_COLORS[sig.severity] ?? '#6b7280',
                          border: `1px solid color-mix(in srgb, ${SEVERITY_COLORS[sig.severity] ?? '#6b7280'} 20%, transparent)`,
                        }}
                      >
                        {sig.title}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
