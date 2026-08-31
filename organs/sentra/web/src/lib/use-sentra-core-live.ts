import { useEffect, useState } from 'react';
import type { DataState } from '@szl-holdings/shared-ui/data-state-badge';
import type { DataSource } from './use-api-query';

/**
 * Map our internal `DataSource` (live/seed/offline) to the shared
 * `DataStateBadge` vocabulary (live/seeded/stub). Use this when rendering
 * the canonical Sentra live-status indicator on existing pages.
 */
export function toDataState(source: DataSource): DataState {
  if (source === 'live') return 'live';
  if (source === 'offline') return 'stub';
  return 'seeded';
}

interface SentraCoreLiveOptions {
  endpoint: string;
  body?: Record<string, unknown>;
  method?: 'POST' | 'GET';
  /**
   * When ``true``, the request is NOT issued on mount or on body changes —
   * the hook stays idle until ``reload()`` is called explicitly. Use this
   * for state-changing ops (incident_response.run, evidence_pack.build)
   * so they run on operator action, not on render.
   */
  manual?: boolean;
}

interface SentraCoreLiveResult<T> {
  data: T | null;
  source: DataSource;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

async function ensureCsrf(): Promise<string | null> {
  const existing = readCsrfCookie();
  if (existing) return existing;
  try {
    await fetch('/api/csrf-token', { credentials: 'include' });
  } catch {
    return null;
  }
  return readCsrfCookie();
}

export function useSentraCoreLive<T>({
  endpoint,
  body,
  method = 'POST',
  manual = false,
}: SentraCoreLiveOptions): SentraCoreLiveResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<DataSource>('seed');
  const [loading, setLoading] = useState(!manual);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    // In manual mode, skip the initial fetch (and refetch on body change);
    // only `reload()` (which bumps `tick`) triggers the request.
    if (manual && tick === 0) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (method === 'POST') {
          const token = await ensureCsrf();
          if (token) headers['X-CSRF-Token'] = token;
        }
        const res = await fetch(`/api/sentra/core${endpoint}`, {
          method,
          headers,
          credentials: 'include',
          body: method === 'POST' && body ? JSON.stringify(body) : undefined,
        });
        if (!res.ok) {
          if (!cancelled) {
            setSource('offline');
            setError(`HTTP ${res.status}`);
          }
          return;
        }
        const json = (await res.json()) as { data?: T } & T;
        if (!cancelled) {
          setData((json.data ?? json) as T);
          setSource('live');
        }
      } catch (err) {
        if (!cancelled) {
          setSource('offline');
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [endpoint, method, JSON.stringify(body ?? {}), tick]);

  return { data, source, loading, error, reload: () => setTick((t) => t + 1) };
}
