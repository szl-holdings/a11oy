import { X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { getDomainColor, getSeverityColor } from '../../lib/command/utils';
import type { DomainId, SeverityLevel, TimelineEvent } from '../types';

interface TimelineProps {
  events: TimelineEvent[];
}

const SEVERITY_OPTIONS: SeverityLevel[] = ['critical', 'high', 'medium', 'low', 'info'];
const DOMAIN_OPTIONS: DomainId[] = [
  'aegis',
  'vessels',
  'szl',
  'lyte',
  'prism',
  'terra',
  'carlota',
  'stephen',
];
const PAGE_SIZE = 8;

export function Timeline({ events }: TimelineProps) {
  const [domainFilter, setDomainFilter] = useState<DomainId | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityLevel | null>(null);
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (domainFilter && e.domain !== domainFilter) return false;
      if (severityFilter && e.severity !== severityFilter) return false;
      return true;
    });
  }, [events, domainFilter, severityFilter]);

  const visible = filtered.slice(0, page * PAGE_SIZE);
  const hasMore = visible.length < filtered.length;

  const domainsPresent = useMemo(() => {
    const s = new Set(events.map((e) => e.domain as DomainId));
    return DOMAIN_OPTIONS.filter((d) => s.has(d));
  }, [events]);

  const clearFilters = () => {
    setDomainFilter(null);
    setSeverityFilter(null);
    setPage(1);
  };

  const hasFilters = domainFilter !== null || severityFilter !== null;

  return (
    <div
      className="rounded-xl overflow-hidden flex flex-col h-full"
      style={{
        backgroundColor: 'var(--color-surface-base)',
        border: '1px solid var(--color-surface-border)',
      }}
    >
      <div
        className="p-4 flex flex-col gap-3"
        style={{
          borderBottom: '1px solid var(--color-surface-border)',
          backgroundColor: 'var(--color-bg-primary)',
        }}
      >
        <div className="flex items-center justify-between">
          <h2
            className="text-xs font-bold tracking-widest uppercase"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Cross-Domain Feed
          </h2>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider"
              style={{ color: 'var(--color-fg-muted)' }}
            >
              <X className="w-3 h-3" />
              Clear
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {domainsPresent.map((d) => {
            const active = domainFilter === d;
            const color = getDomainColor(d);
            return (
              <button
                key={d}
                onClick={() => {
                  setDomainFilter(active ? null : d);
                  setPage(1);
                }}
                className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded transition-colors"
                style={{
                  color: active ? 'var(--color-bg-primary)' : color,
                  backgroundColor: active ? color : `color-mix(in srgb, ${color} 12%, transparent)`,
                  border: `1px solid ${color}`,
                }}
              >
                {d}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {SEVERITY_OPTIONS.map((s) => {
            const active = severityFilter === s;
            const color = getSeverityColor(s);
            return (
              <button
                key={s}
                onClick={() => {
                  setSeverityFilter(active ? null : s);
                  setPage(1);
                }}
                className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded transition-colors"
                style={{
                  color: active ? 'var(--color-bg-primary)' : color,
                  backgroundColor: active ? color : `color-mix(in srgb, ${color} 12%, transparent)`,
                  border: `1px solid ${color}`,
                }}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>

      <div className="overflow-y-auto p-4 flex-1 flex flex-col gap-4 max-h-[600px]">
        {visible.length === 0 ? (
          <div
            className="flex-1 flex items-center justify-center text-xs"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            No events match the current filters.
          </div>
        ) : (
          <>
            {visible.map((event) => (
              <div
                key={event.id}
                className="relative pl-4 pb-4 last:pb-0"
                style={{ borderLeft: '1px solid var(--color-surface-border)' }}
                data-testid={`timeline-event-${event.id}`}
              >
                <div
                  className="absolute w-2 h-2 rounded-full top-1.5"
                  style={{
                    backgroundColor: getDomainColor(event.domain),
                    left: '-4.5px',
                  }}
                />
                <div className="flex flex-col gap-1">
                  <div
                    className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider"
                    style={{ color: 'var(--color-fg-muted)' }}
                  >
                    <span>{event.time}</span>
                    <span style={{ opacity: 0.5 }}>/</span>
                    <span style={{ color: getDomainColor(event.domain) }}>{event.domain}</span>
                    <span style={{ opacity: 0.5 }}>/</span>
                    <span style={{ color: getSeverityColor(event.severity) }}>
                      {event.severity}
                    </span>
                  </div>
                  <h4
                    className="text-sm font-semibold"
                    style={{ color: 'var(--color-fg-primary)' }}
                  >
                    {event.title}
                  </h4>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--color-fg-muted)' }}>
                    {event.detail}
                  </p>
                </div>
              </div>
            ))}

            {hasMore && (
              <button
                onClick={() => setPage((p) => p + 1)}
                className="w-full py-2 text-xs font-mono uppercase tracking-wider rounded-lg transition-colors"
                style={{
                  color: 'var(--color-fg-muted)',
                  backgroundColor: 'var(--color-bg-elevated)',
                  border: '1px solid var(--color-surface-border)',
                }}
              >
                Load more ({filtered.length - visible.length} remaining)
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
