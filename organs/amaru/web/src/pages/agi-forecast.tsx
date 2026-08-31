import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getAgiForecastStatus,
  refreshAgiForecast,
  type AgiForecastDerived,
  type AgiForecastHistoryEntry,
  type AgiForecastStatus,
  type AgiForecastStatusPresent,
} from '@/lib/api';

type GaugeStatus = AgiForecastStatusPresent['statuses'][number];

function relativeTime(iso: string | null): string {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

function formatGaugeValue(v: GaugeStatus['value']): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '—';
    return Math.abs(v) >= 1000 || (Math.abs(v) > 0 && Math.abs(v) < 0.01)
      ? v.toExponential(3)
      : v.toFixed(3);
  }
  return String(v);
}

function GaugeStatusTable({ statuses }: { statuses: readonly GaugeStatus[] }) {
  if (statuses.length === 0) {
    return (
      <div className="text-[12px] font-mono text-[#666]">
        No gauges registered.
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0e0e0e] overflow-hidden">
      <div className="px-5 py-3 border-b border-[rgba(255,255,255,0.06)] flex items-baseline justify-between">
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-[#666]">
          Per-Gauge Status
        </div>
        <div className="text-[11px] font-mono text-[#8a8a8a] tabular-nums">
          {statuses.filter((s) => s.ok).length}/{statuses.length} ok
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#555]">
            <tr className="border-b border-[rgba(255,255,255,0.04)]">
              <th className="text-left px-5 py-2 font-normal">Gauge</th>
              <th className="text-left px-3 py-2 font-normal">Source</th>
              <th className="text-left px-3 py-2 font-normal">Status</th>
              <th className="text-right px-3 py-2 font-normal">Value</th>
              <th className="text-left px-3 py-2 font-normal">Last Fetched</th>
              <th className="text-left px-5 py-2 font-normal">Error</th>
            </tr>
          </thead>
          <tbody>
            {statuses.map((s) => (
              <tr
                key={s.id}
                className="border-b border-[rgba(255,255,255,0.03)] last:border-b-0 hover:bg-[rgba(255,255,255,0.02)]"
              >
                <td className="px-5 py-2.5">
                  <div className="font-mono text-[#f5f5f5]">{s.label ?? s.id}</div>
                  {s.label && s.label !== s.id && (
                    <div className="text-[10px] font-mono text-[#555]">{s.id}</div>
                  )}
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-[#8a8a8a]">
                  {s.source ?? '—'}
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={
                      'inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.12em] ' +
                      (s.ok
                        ? 'bg-[rgba(120,200,140,0.08)] text-[#7bc88c] border border-[rgba(120,200,140,0.2)]'
                        : 'bg-[rgba(220,80,80,0.08)] text-[#dc8a8a] border border-[rgba(220,80,80,0.25)]')
                    }
                  >
                    <span
                      className={
                        'inline-block w-1.5 h-1.5 rounded-full ' +
                        (s.ok ? 'bg-[#7bc88c]' : 'bg-[#dc8a8a]')
                      }
                    />
                    {s.ok ? 'ok' : 'failed'}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[#c9b787]">
                  {formatGaugeValue(s.value)}
                </td>
                <td className="px-3 py-2.5 font-mono text-[11px] text-[#8a8a8a]">
                  <div>{relativeTime(s.lastFetchedAt)}</div>
                  {s.lastFetchedAt && (
                    <div className="text-[10px] text-[#555]" title={s.lastFetchedAt}>
                      {new Date(s.lastFetchedAt).toISOString().replace('T', ' ').slice(0, 19)}Z
                    </div>
                  )}
                </td>
                <td className="px-5 py-2.5 font-mono text-[11px] text-[#dc8a8a] max-w-[280px]">
                  {s.error ? (
                    <span className="line-clamp-2" title={s.error}>{s.error}</span>
                  ) : (
                    <span className="text-[#444]">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type MetricKey = keyof AgiForecastDerived;

interface MetricSpec {
  readonly key: MetricKey;
  readonly title: string;
  readonly unit: string;
  readonly explainer: string;
  readonly format: (v: number) => string;
}

const METRICS: readonly MetricSpec[] = [
  {
    key: 'horizonVelocity',
    title: 'Horizon Velocity',
    unit: 'signal-units / day',
    explainer:
      'Average per-day change across capability signals — how fast frontier capability is moving.',
    format: (v) => v.toFixed(3),
  },
  {
    key: 'alignmentDebt',
    title: 'Alignment Debt',
    unit: 'signal-units / day',
    explainer:
      'Capability velocity minus safety velocity. Positive means capability is outpacing safety.',
    format: (v) => (v >= 0 ? '+' : '') + v.toFixed(3),
  },
  {
    key: 'lutarReadiness',
    title: 'Lutar Readiness',
    unit: 'composite, 0 – 1',
    explainer:
      'Go / no-go score. 1 means safety is fully keeping pace; 0 means capability is running unchecked.',
    format: (v) => v.toFixed(2),
  },
];

function fmt(v: number | null, spec: MetricSpec): string {
  if (v === null || !Number.isFinite(v)) return '—';
  return spec.format(v);
}

function Sparkline({ values }: { values: ReadonlyArray<number | null> }) {
  const W = 220;
  const H = 48;
  const pad = 4;
  const present = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (present.length < 2) {
    return (
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-[#555]">
        not enough history
      </div>
    );
  }
  const min = Math.min(...present);
  const max = Math.max(...present);
  const span = max - min || 1;
  const stepX = (W - pad * 2) / Math.max(values.length - 1, 1);
  const points = values
    .map((v, i) => {
      if (v === null || !Number.isFinite(v)) return null;
      const x = pad + i * stepX;
      const y = H - pad - ((v - min) / span) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter((p): p is string => p !== null)
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="w-full h-12"
      aria-label="Recent history sparkline"
    >
      <polyline
        fill="none"
        stroke="#c9b787"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

function MetricCard({
  spec,
  current,
  history,
}: {
  spec: MetricSpec;
  current: number | null;
  history: ReadonlyArray<AgiForecastHistoryEntry>;
}) {
  const series = history.map((h) => h.derived[spec.key]);
  const first = series.find((v): v is number => v !== null && Number.isFinite(v));
  const last = [...series].reverse().find((v): v is number => v !== null && Number.isFinite(v));
  const delta = first !== undefined && last !== undefined ? last - first : null;
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0e0e0e] p-5 flex flex-col gap-4">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-[#666]">
          {spec.title}
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <div className="font-mono text-3xl text-[#f5f5f5] tabular-nums">
            {fmt(current, spec)}
          </div>
          <div className="text-[11px] text-[#666]">{spec.unit}</div>
        </div>
        {delta !== null && Number.isFinite(delta) && (
          <div className="mt-1 text-[11px] font-mono text-[#8a8a8a] tabular-nums">
            {delta >= 0 ? '+' : ''}
            {delta.toFixed(3)} over last {history.length} day{history.length === 1 ? '' : 's'}
          </div>
        )}
      </div>
      <Sparkline values={series} />
      <p className="text-[12px] leading-relaxed text-[#8a8a8a]">{spec.explainer}</p>
    </div>
  );
}

function StatusLine({ data }: { data: AgiForecastStatus }) {
  if (!data.present) {
    return (
      <div className="text-[12px] font-mono text-[#666]">
        {data.message}
      </div>
    );
  }
  const okCount = data.statuses.filter((s) => s.ok).length;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] font-mono text-[#666]">
      <span>
        snapshot date{' '}
        <span className="text-[#c9b787]">{data.date}</span>
      </span>
      <span>
        last run{' '}
        <span className="text-[#c9b787]">
          {new Date(data.lastRunAt).toISOString().replace('T', ' ').slice(0, 19)}Z
        </span>
      </span>
      <span>
        signals{' '}
        <span className="text-[#c9b787]">
          {okCount}/{data.statuses.length} ok
        </span>
      </span>
      <span>
        receipt{' '}
        <span className="text-[#c9b787]">{data.summary.receiptHash.slice(0, 12)}…</span>
      </span>
    </div>
  );
}

export default function AgiForecastPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AgiForecastStatus>({
    queryKey: ['agi-forecast', 'status'],
    queryFn: getAgiForecastStatus,
    refetchInterval: 60_000,
  });

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      await refreshAgiForecast();
      await refetch();
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : String(err));
      // Still refetch so the panel re-syncs with whatever the scheduler last wrote.
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

  const busy = isRefreshing || isFetching;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-2xl font-display font-semibold text-[#f5f5f5]">
            AGI Forecast — Derived Metrics
          </h1>
          <p className="mt-1 max-w-2xl text-[13px] text-[#8a8a8a]">
            Today's horizon-velocity, alignment-debt, and lutar-readiness, derived from the
            public-only gauge snapshot. Values are read straight from{' '}
            <code className="font-mono text-[#c9b787]">buildDailySummary</code> — no
            recalculation happens in the browser.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={busy}
          className="shrink-0 rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0e0e0e] px-3 py-1.5 text-[11px] font-mono uppercase tracking-[0.15em] text-[#8a8a8a] hover:text-[#f5f5f5] hover:border-[rgba(201,183,135,0.4)] transition-colors disabled:opacity-40"
          title="Trigger a fresh scheduled-style run via POST /api/agi-forecast/refresh"
        >
          {isRefreshing ? 'running ingest…' : isFetching ? 'refreshing…' : 'refresh now'}
        </button>
      </header>

      {isLoading && (
        <div className="text-[12px] font-mono text-[#666]">loading snapshot…</div>
      )}

      {isError && (
        <div className="rounded-lg border border-[rgba(220,80,80,0.3)] bg-[rgba(220,80,80,0.05)] p-4 text-[12px] text-[#dc8a8a]">
          Failed to load forecast snapshot: {error instanceof Error ? error.message : String(error)}
        </div>
      )}

      {refreshError && (
        <div className="rounded-lg border border-[rgba(220,80,80,0.3)] bg-[rgba(220,80,80,0.05)] p-4 text-[12px] text-[#dc8a8a]">
          Manual refresh failed: {refreshError}
        </div>
      )}

      {data && !data.present && (
        <div className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0e0e0e] p-4 text-[12px] text-[#8a8a8a]">
          {data.message}
        </div>
      )}

      {data && data.present && (
        <>
          <StatusLine data={data} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {METRICS.map((spec) => (
              <MetricCard
                key={spec.key}
                spec={spec}
                current={data.summary.derived[spec.key]}
                history={data.history}
              />
            ))}
          </div>
          <GaugeStatusTable statuses={data.statuses} />
        </>
      )}
    </div>
  );
}
