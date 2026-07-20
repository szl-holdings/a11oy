// VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — artifacts/a11oy/src/components/DefenseDataState.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import type { ReactNode } from 'react';

const T = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.08)',
  text: '#f5f5f5',
  dim: '#8a8a8a',
  muted: '#5e5e5e',
  accent: '#c9b787',
};

interface RefreshBarProps {
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;
  onRefresh: () => void;
}

export function RefreshBar({ loading, error, lastUpdated, onRefresh }: RefreshBarProps) {
  return (
    <div className="flex items-center justify-end gap-3 mb-4">
      {error ? (
        <span className="text-[10px] font-mono" style={{ color: '#ef4444' }}>
          ERROR — {error}
        </span>
      ) : lastUpdated ? (
        <span className="text-[10px] font-mono" style={{ color: T.muted }}>
          Updated {new Date(lastUpdated).toLocaleTimeString()}
        </span>
      ) : null}
      <button
        onClick={onRefresh}
        disabled={loading}
        className="px-3 py-1.5 rounded-md text-[10px] font-mono uppercase tracking-widest transition-all"
        style={{
          background: loading ? 'transparent' : 'rgba(201,183,135,0.08)',
          border: `1px solid ${loading ? T.border : 'rgba(201,183,135,0.25)'}`,
          color: loading ? T.muted : T.accent,
          cursor: loading ? 'wait' : 'pointer',
        }}
      >
        {loading ? 'Refreshing…' : '↻ Refresh'}
      </button>
    </div>
  );
}

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = 'Loading defense data…' }: LoadingStateProps) {
  return (
    <div
      className="rounded-lg px-6 py-12 text-center"
      style={{ background: T.surface, border: `1px solid ${T.border}` }}
    >
      <div className="inline-flex items-center gap-3">
        <span
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ background: T.accent }}
        />
        <span className="text-xs font-mono" style={{ color: T.dim }}>
          {label}
        </span>
      </div>
    </div>
  );
}

interface ErrorStateProps {
  error: string;
  onRetry: () => void;
  children?: ReactNode;
}

export function ErrorState({ error, onRetry, children }: ErrorStateProps) {
  return (
    <div
      className="rounded-lg px-6 py-8 text-center"
      style={{ background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.2)' }}
    >
      <div className="text-xs font-mono mb-2" style={{ color: '#ef4444' }}>
        DEFENSE FEED UNAVAILABLE
      </div>
      <div className="text-[10px] font-mono mb-4" style={{ color: T.dim }}>
        {error}
      </div>
      {children}
      <button
        onClick={onRetry}
        className="px-3 py-1.5 rounded-md text-[10px] font-mono uppercase tracking-widest"
        style={{
          background: 'rgba(201,183,135,0.08)',
          border: '1px solid rgba(201,183,135,0.25)',
          color: T.accent,
          cursor: 'pointer',
        }}
      >
        Retry
      </button>
    </div>
  );
}
