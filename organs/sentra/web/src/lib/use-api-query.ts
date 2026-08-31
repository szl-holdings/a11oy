import { useCallback, useEffect, useRef, useState } from 'react';

export type DataSource = 'live' | 'seed' | 'offline';

export interface ApiQueryResult<T> {
  data: T;
  source: DataSource;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

interface ApiResponse {
  [key: string]: unknown;
  source?: DataSource;
}

export function useApiQuery<T>(
  fetcher: () => Promise<ApiResponse | null>,
  dataKey: string,
  fallback: T,
): ApiQueryResult<T> {
  const [data, setData] = useState<T>(fallback);
  const [source, setSource] = useState<DataSource>('seed');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (!mountedRef.current) return;
      if (result && dataKey in result) {
        const payload = result[dataKey] as T;
        setData(payload);
        if (result.source) {
          setSource(result.source as DataSource);
        } else if (Array.isArray(payload) && payload.length > 0) {
          const allSeed = payload.every(
            (item) => item && typeof item === 'object' && 'source' in item && (item as { source: unknown }).source === 'seed',
          );
          setSource(allSeed ? 'seed' : 'live');
        } else {
          setSource('live');
        }
      } else {
        setData(fallback);
        setSource('seed');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Failed to load';
      setError(msg);
      setData(fallback);
      setSource('offline');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [fetcher, dataKey]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => { mountedRef.current = false; };
  }, [load]);

  return { data, source, loading, error, reload: load };
}

export function useApiMultiQuery<T extends Record<string, unknown>>(
  fetchers: { [K in keyof T]: { fetch: () => Promise<ApiResponse | null>; key: string; fallback: T[K] } },
): { data: T; source: DataSource; loading: boolean; error: string | null; reload: () => void } {
  const keys = Object.keys(fetchers) as (keyof T)[];
  const fallbackData = {} as T;
  for (const k of keys) fallbackData[k] = fetchers[k].fallback;

  const [data, setData] = useState<T>(fallbackData);
  const [source, setSource] = useState<DataSource>('seed');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(keys.map((k) => fetchers[k].fetch()));
      if (!mountedRef.current) return;
      const merged = {} as Record<string, unknown>;
      let anyLive = false;
      for (let i = 0; i < keys.length; i++) {
        const k = keys[i];
        const r = results[i];
        if (r && fetchers[k].key in r) {
          merged[k as string] = r[fetchers[k].key];
          if (r.source === 'live') anyLive = true;
        } else {
          merged[k as string] = fetchers[k].fallback;
        }
      }
      setData(merged as T);
      setSource(anyLive ? 'live' : 'seed');
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load');
      setData(fallbackData);
      setSource('offline');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => { mountedRef.current = false; };
  }, [load]);

  return { data, source, loading, error, reload: load };
}

export { SourceBadge } from './source-badge';
