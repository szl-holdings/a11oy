import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  GitBranch,
  Loader2,
  Server,
} from 'lucide-react';
import { useEffect, useState } from 'react';

interface HealthData {
  status: 'healthy' | 'ok' | 'degraded' | string;
  version?: string;
  environment?: string;
  uptime?: number;
  services?: {
    database?: {
      status: 'ok' | 'degraded' | 'not_configured' | string;
      latencyMs?: number | null;
    };
  };
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full shrink-0"
      style={{ backgroundColor: ok ? 'var(--color-low)' : 'var(--color-critical)' }}
    />
  );
}

export function ServiceStatusPanel() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const baseUrl = import.meta.env.BASE_URL?.replace(/\/$/, '') || '';
    const apiBase = baseUrl.replace(/\/command$/, '');

    fetch(`${apiBase}/api/health`)
      .then(async (r) => {
        const data = await r.json().catch(() => null);
        if (data && (r.ok || r.status === 503)) {
          setHealth(data as HealthData);
        } else {
          setError(true);
        }
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const apiOk = !error && (health?.status === 'healthy' || health?.status === 'ok');
  const dbStatus = health?.services?.database?.status;
  const dbOk = !error && dbStatus === 'ok';
  const dbLatency = health?.services?.database?.latencyMs;

  const items = [
    {
      icon: Server,
      label: 'API',
      value: loading
        ? '—'
        : error
          ? 'Unreachable'
          : health?.status === 'healthy' || health?.status === 'ok'
            ? 'Operational'
            : health?.status === 'degraded'
              ? 'Degraded'
              : (health?.status ?? 'Unknown'),
      ok: apiOk,
    },
    {
      icon: Database,
      label: 'Database',
      value: loading
        ? '—'
        : error
          ? '—'
          : dbStatus === 'ok'
            ? `${dbLatency ?? '?'}ms`
            : dbStatus === 'not_configured'
              ? 'Not configured'
              : 'Degraded',
      ok: dbOk,
    },
    {
      icon: Clock,
      label: 'Uptime',
      value: loading
        ? '—'
        : error
          ? '—'
          : health?.uptime != null
            ? formatUptime(health.uptime)
            : '—',
      ok: !error && health?.uptime != null,
    },
    {
      icon: GitBranch,
      label: 'Version',
      value: loading ? '—' : error ? '—' : (health?.version ?? '—'),
      ok: !error && !!health?.version,
    },
  ];

  return (
    <div
      className="rounded-xl p-5"
      style={{
        backgroundColor: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <span
          className="text-xs font-bold uppercase tracking-widest"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Service Status
        </span>
        {loading ? (
          <Loader2
            className="w-3.5 h-3.5 animate-spin"
            style={{ color: 'var(--color-fg-muted)' }}
          />
        ) : error ? (
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" style={{ color: 'var(--color-critical)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--color-critical)' }}>
              API unreachable
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <CheckCircle2
              className="w-3.5 h-3.5"
              style={{ color: apiOk ? 'var(--color-low)' : 'var(--color-medium)' }}
            />
            <span
              className="text-xs font-semibold"
              style={{ color: apiOk ? 'var(--color-low)' : 'var(--color-medium)' }}
            >
              {health?.environment ?? 'live'}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {items.map(({ icon: Icon, label, value, ok }) => (
          <div
            key={label}
            className="flex flex-col gap-2 rounded-lg p-3"
            style={{ backgroundColor: 'var(--color-bg-elevated)' }}
          >
            <div className="flex items-center gap-2">
              <Icon className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--color-fg-muted)' }} />
              <span
                className="text-[10px] font-bold uppercase tracking-wider"
                style={{ color: 'var(--color-fg-muted)' }}
              >
                {label}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {!loading && <StatusDot ok={ok} />}
              <span
                className="text-sm font-mono font-semibold"
                style={{
                  color: loading
                    ? 'var(--color-fg-muted)'
                    : ok
                      ? 'var(--color-fg-primary)'
                      : 'var(--color-critical)',
                }}
              >
                {value}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
