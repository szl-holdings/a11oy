// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/sentra/src/lib/live-badge.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { AlertTriangle, Radio, WifiOff } from 'lucide-react';

interface LiveDataBadgeProps {
  isLive?: boolean;
  isLoading?: boolean;
  isStale?: boolean;
  className?: string;
  size?: 'sm' | 'md';
  label?: string;
}

export function LiveDataBadge({
  isLive,
  isLoading,
  isStale,
  className = '',
  size = 'sm',
  label,
}: LiveDataBadgeProps) {
  if (isLoading) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20 ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
        Connecting...
      </span>
    );
  }
  if (isStale) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20 ${size === 'md' ? 'px-3 py-1.5' : ''} ${className}`}
      >
        <AlertTriangle className="w-3 h-3" />
        {label ?? 'Stale'}
      </span>
    );
  }
  if (!isLive) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#f5f5f5]/10 text-[#f5f5f5] border border-[#f5f5f5]/20 ${className}`}
      >
        <WifiOff className="w-3 h-3" />
        {label ?? 'Disconnected'}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20 ${size === 'md' ? 'px-3 py-1.5' : ''} ${className}`}
    >
      <Radio className="w-3 h-3 animate-pulse" />
      {label ?? 'Live'}
    </span>
  );
}
