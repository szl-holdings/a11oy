// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  FileText,
  RefreshCw,
  Shield,
  Target,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { type AegisWhatChangedEvent, aegisWhatChanged as fallbackEvents } from '@/data/threat-twin';
import { listThreatTwinActions } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

const ACCENT = 'hsl(220 72% 56%)';

function relTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const EVENT_ICONS: Record<AegisWhatChangedEvent['eventType'], React.ElementType> = {
  new_threat: AlertTriangle,
  severity_change: Target,
  status_change: Activity,
  asset_compromised: Shield,
  exposure_discovered: BarChart3,
  approval_action: Shield,
  governance_update: FileText,
  readiness_change: BarChart3,
  containment_action: Shield,
};

const EVENT_LABELS: Record<AegisWhatChangedEvent['eventType'], string> = {
  new_threat: 'New Threat',
  severity_change: 'Severity',
  status_change: 'Status',
  asset_compromised: 'Asset',
  exposure_discovered: 'Exposure',
  approval_action: 'Approval',
  governance_update: 'Governance',
  readiness_change: 'Readiness',
  containment_action: 'Containment',
};

const SEV_STYLE = {
  info: {
    bg: 'rgba(255,255,255,0.02)',
    border: 'rgba(255,255,255,0.06)',
    badge: 'rgba(255,255,255,0.06)',
    badgeText: 'rgba(255,255,255,0.4)',
  },
  warning: { bg: '#c08a2c06', border: '#c08a2c25', badge: '#c08a2c20', badgeText: '#c08a2c' },
  critical: { bg: '#5e5e5e10', border: '#5e5e5e40', badge: '#5e5e5e25', badgeText: '#f5f5f5' },
};

function EventCard({ event }: { event: AegisWhatChangedEvent }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = EVENT_ICONS[event.eventType] ?? Activity;
  const s = SEV_STYLE[event.severity];
  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className="rounded-xl border p-4 cursor-pointer transition-all hover:bg-white/2"
      style={{ background: s.bg, borderColor: s.border }}
    >
      <div className="flex items-start gap-3">
        <div className="p-1.5 rounded-lg flex-shrink-0" style={{ background: s.badge }}>
          <Icon size={14} style={{ color: s.badgeText }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <span
              className="text-xs px-1.5 py-0.5 rounded font-medium"
              style={{ background: s.badge, color: s.badgeText }}
            >
              {EVENT_LABELS[event.eventType]}
            </span>
            <span className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.5)' }}>
              {event.entityName}
            </span>
            <span className="text-xs capitalize" style={{ color: 'rgba(255,255,255,0.2)' }}>
              · {event.entityType} · {event.source}
            </span>
          </div>
          <div
            className="text-sm font-medium"
            style={{
              color:
                event.severity === 'critical'
                  ? '#f5f5f5'
                  : event.severity === 'warning'
                    ? '#c08a2c'
                    : 'rgba(255,255,255,0.75)',
            }}
          >
            {event.summary}
          </div>
          {expanded && event.detail && (
            <div
              className="mt-2 text-xs leading-relaxed"
              style={{ color: 'rgba(255,255,255,0.45)' }}
            >
              {event.detail}
            </div>
          )}
          <div className="mt-1 text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>
            {relTime(event.occurredAt)} {event.actor && `· by ${event.actor}`}
          </div>
        </div>
        <ArrowUpRight size={13} style={{ color: 'rgba(255,255,255,0.12)', flexShrink: 0 }} />
      </div>
    </div>
  );
}

export default function AegisWhatChanged() {
  const [filter, setFilter] = useState('all');
  const [entityFilter, setEntityFilter] = useState('all');

  const fetcher = useCallback(() => listThreatTwinActions(), []);
  const { data: aegisWhatChanged } = useApiQuery<AegisWhatChangedEvent[]>(fetcher, 'actions', fallbackEvents);

  const filtered = aegisWhatChanged.filter((e) => {
    if (filter !== 'all' && e.severity !== filter) return false;
    if (entityFilter !== 'all' && e.entityType !== entityFilter) return false;
    return true;
  });

  const counts = {
    critical: aegisWhatChanged.filter((e) => e.severity === 'critical').length,
    warning: aegisWhatChanged.filter((e) => e.severity === 'warning').length,
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'rgba(255,255,255,0.95)' }}>
            What Changed
          </h1>
          <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Threat, exposure, and governance events across the security posture
          </p>
        </div>
        <button
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg hover:bg-white/5"
          style={{ border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)' }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div
          className="rounded-xl border p-4"
          style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.06)' }}
        >
          <div className="text-xs mb-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Events (rolling)
          </div>
          <div className="text-2xl font-bold" style={{ color: 'rgba(255,255,255,0.9)' }}>
            {aegisWhatChanged.length}
          </div>
        </div>
        <div
          className="rounded-xl border p-4"
          style={{ background: '#5e5e5e08', borderColor: '#5e5e5e30' }}
        >
          <div className="text-xs mb-1" style={{ color: '#f5f5f5' }}>
            Critical
          </div>
          <div className="text-2xl font-bold" style={{ color: '#f5f5f5' }}>
            {counts.critical}
          </div>
        </div>
        <div
          className="rounded-xl border p-4"
          style={{ background: '#c08a2c08', borderColor: '#c08a2c25' }}
        >
          <div className="text-xs mb-1" style={{ color: '#c08a2c' }}>
            Warnings
          </div>
          <div className="text-2xl font-bold" style={{ color: '#c08a2c' }}>
            {counts.warning}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-2">
        {['all', 'critical', 'warning', 'info'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="text-xs px-3 py-1 rounded-lg capitalize transition-colors"
            style={{
              background: filter === f ? 'hsl(220 72% 56% / 0.12)' : 'rgba(255,255,255,0.04)',
              color: filter === f ? ACCENT : 'rgba(255,255,255,0.4)',
              border: `1px solid ${filter === f ? 'hsl(220 72% 56% / 0.3)' : 'rgba(255,255,255,0.06)'}`,
            }}
          >
            {f}
          </button>
        ))}
        <span style={{ color: 'rgba(255,255,255,0.12)' }}>|</span>
        {['all', 'threat', 'exposure', 'governance'].map((f) => (
          <button
            key={f}
            onClick={() => setEntityFilter(f)}
            className="text-xs px-3 py-1 rounded-lg capitalize transition-colors"
            style={{
              background: entityFilter === f ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
              color: entityFilter === f ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.35)',
              border: `1px solid ${entityFilter === f ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)'}`,
            }}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {filtered.length === 0 ? (
          <div className="py-16 text-center text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>
            No events match filter.
          </div>
        ) : (
          filtered.map((e) => <EventCard key={e.id} event={e} />)
        )}
      </div>
    </div>
  );
}
