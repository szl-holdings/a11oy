import { AtlasScenePanel as SharedAtlasScenePanel } from '@szl-holdings/design-system';
import { Activity, AlertTriangle, Info, XCircle } from 'lucide-react';

interface AtlasScenePanelProps {
  incidentId?: string;
  vesselId?: string;
  propertyId?: string;
  isDemo?: boolean;
}

const DEMO_TIMELINE = [
  {
    time: '14:02:11',
    event: 'Threat actor lateral movement detected — east network segment',
    type: 'critical' as const,
  },
  {
    time: '14:04:33',
    event: 'MITRE ATT&CK T1021.002: SMB/Windows Admin Shares enumeration',
    type: 'warning' as const,
  },
  {
    time: '14:07:19',
    event: 'Credential access attempt blocked — endpoint: WS-DEVOPS-04',
    type: 'warning' as const,
  },
  {
    time: '14:09:48',
    event: 'Isolation policy applied — 4 hosts quarantined',
    type: 'info' as const,
  },
  {
    time: '14:12:02',
    event: 'IR agent recommendation queued — awaiting CISO approval',
    type: 'info' as const,
  },
  {
    time: '14:15:30',
    event: 'SIEM correlation rule triggered — campaign fingerprint match',
    type: 'critical' as const,
  },
];

const DEMO_METRICS = [
  { label: 'Affected assets', value: '4', accent: 'var(--gi-text-primary)' },
  { label: 'Attack vector', value: 'SMB', accent: 'var(--gi-accent-amber)' },
  { label: 'MITRE stage', value: 'Lateral Movement', accent: 'var(--gi-text-secondary)' },
  { label: 'Containment', value: 'Partial', accent: 'var(--gi-accent-amber)' },
  { label: 'Blast radius', value: 'Low', accent: 'var(--gi-accent-amber)' },
  { label: 'Conf. score', value: '94%', accent: 'var(--gi-accent-amber)' },
];

const TYPE_CONFIG = {
  critical: { icon: XCircle, color: 'var(--gi-text-primary)', bg: 'rgba(245,245,245,0.08)' },
  warning: {
    icon: AlertTriangle,
    color: 'var(--gi-accent-amber)',
    bg: 'color-mix(in srgb, var(--gi-accent-amber) 8%, transparent)',
  },
  info: {
    icon: Info,
    color: 'var(--gi-accent-amber)',
    bg: 'color-mix(in srgb, var(--gi-accent-amber) 8%, transparent)',
  },
} as const;

const ACCENT = 'var(--gi-accent-amber)';

export function AtlasScenePanel({ incidentId, isDemo }: AtlasScenePanelProps) {
  const displayId = incidentId ? `INC-${incidentId.slice(-6).toUpperCase()}` : 'INC-2409-DEMO';

  const timelineContent = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {DEMO_TIMELINE.map((entry, i) => {
        const cfg = TYPE_CONFIG[entry.type];
        const Icon = cfg.icon;
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.75rem',
              padding: '0.5rem 0.625rem',
              borderRadius: '0.375rem',
              background: cfg.bg,
              border: `1px solid color-mix(in srgb, ${cfg.color} 18%, transparent)`,
            }}
          >
            <Icon size={12} style={{ color: cfg.color, flexShrink: 0, marginTop: '2px' }} />
            <div style={{ flex: 1 }}>
              <p
                style={{
                  fontSize: '0.75rem',
                  color: 'rgba(255,255,255,0.82)',
                  margin: 0,
                  lineHeight: 1.45,
                }}
              >
                {entry.event}
              </p>
              <span
                style={{
                  fontSize: '0.6rem',
                  fontFamily: 'monospace',
                  color: 'var(--gi-text-muted)',
                  letterSpacing: '0.08em',
                }}
              >
                {entry.time} UTC
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );

  const metricsContent = (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem' }}>
      {DEMO_METRICS.map((m, i) => (
        <div
          key={i}
          style={{
            background: 'rgba(255,255,255,0.025)',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '0.5rem',
            padding: '0.625rem 0.75rem',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              fontSize: '0.875rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              color: m.accent,
              margin: 0,
            }}
          >
            {m.value}
          </p>
          <p
            style={{
              fontSize: '0.6rem',
              fontFamily: 'monospace',
              color: 'var(--gi-text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0.25rem 0 0',
            }}
          >
            {m.label}
          </p>
        </div>
      ))}
    </div>
  );

  const headerRight = (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
      <Activity size={11} style={{ color: 'var(--gi-text-primary)' }} />
      <span
        style={{
          fontSize: '0.625rem',
          fontFamily: 'monospace',
          color: 'var(--gi-text-primary)',
          letterSpacing: '0.08em',
        }}
      >
        P1 · ACTIVE
      </span>
    </div>
  );

  return (
    <SharedAtlasScenePanel
      headerTitle={`ATLAS Scene — ${displayId}`}
      footerLabel="sentra · atlas scene · live-signal integrated"
      accentColor={ACCENT}
      isDemo={isDemo}
      headerRight={headerRight}
      defaultTab="timeline"
      tabs={[
        { id: 'timeline', label: 'Timeline', icon: Activity, content: timelineContent },
        { id: 'metrics', label: 'Metrics', icon: Info, content: metricsContent },
      ]}
    />
  );
}
