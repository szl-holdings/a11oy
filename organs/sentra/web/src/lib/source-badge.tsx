import type { DataSource } from './use-api-query';

export function SourceBadge({ source }: { source: DataSource }) {
  const config = {
    live: { label: 'LIVE', color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
    seed: { label: 'SEED', color: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    offline: { label: 'OFFLINE', color: 'bg-red-500/15 text-red-400 border-red-500/30' },
  }[source];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[9px] font-mono uppercase tracking-wider ${config.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${source === 'live' ? 'bg-emerald-400 animate-pulse' : source === 'seed' ? 'bg-amber-400' : 'bg-red-400'}`} />
      {config.label}
    </span>
  );
}
