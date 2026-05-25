import { Activity, AlertTriangle, FlaskConical, Loader2 } from 'lucide-react';

export type DataState = 'live' | 'demo' | 'loading' | 'error';

interface Props {
  state: DataState;
  label?: string;
  className?: string;
}

const CONFIG: Record<DataState, { color: string; bg: string; border: string; icon: typeof Activity; defaultLabel: string }> = {
  live:    { color: '#22c55e', bg: 'rgba(34,197,94,0.10)',  border: 'rgba(34,197,94,0.35)',  icon: Activity,       defaultLabel: 'LIVE' },
  demo:    { color: '#d4a054', bg: 'rgba(212,160,84,0.10)', border: 'rgba(212,160,84,0.35)', icon: FlaskConical,   defaultLabel: 'DEMO' },
  loading: { color: '#8b7ac8', bg: 'rgba(139,122,200,0.10)', border: 'rgba(139,122,200,0.35)', icon: Loader2,      defaultLabel: 'LOADING' },
  error:   { color: '#ef4444', bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.35)',  icon: AlertTriangle, defaultLabel: 'ERROR' },
};

export function DataStateBadge({ state, label, className }: Props) {
  const cfg = CONFIG[state];
  const Icon = cfg.icon;
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 8px',
        borderRadius: 3,
        border: `1px solid ${cfg.border}`,
        background: cfg.bg,
        color: cfg.color,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: 1,
        textTransform: 'uppercase',
        fontFamily: 'inherit',
        lineHeight: 1.2,
      }}
    >
      <Icon
        size={11}
        className={state === 'loading' ? 'animate-spin' : undefined}
        style={{ flexShrink: 0 }}
      />
      {label ?? cfg.defaultLabel}
    </span>
  );
}

export default DataStateBadge;
