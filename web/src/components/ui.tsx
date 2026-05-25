import { useState } from 'react';
import type { ReactNode } from 'react';

export function StatusPill({ status }: { status: 'LIVE' | 'GATED' | 'APPROVED' | 'ROADMAP' | 'WARN' | 'ERROR' | 'CONNECTING' }) {
  const styles: Record<string, { bg: string; color: string }> = {
    LIVE:       { bg: 'rgba(201,183,135,0.15)', color: '#c9b787' },
    GATED:      { bg: 'rgba(94,94,94,0.15)', color: '#5e5e5e' },
    APPROVED:   { bg: 'rgba(201,183,135,0.15)', color: '#c9b787' },
    ROADMAP:    { bg: 'rgba(94,94,94,0.15)',   color: '#5e5e5e' },
    WARN:       { bg: 'rgba(201,183,135,0.15)', color: '#c9b787' },
    ERROR:      { bg: 'rgba(245,245,245,0.12)',  color: '#f5f5f5' },
    CONNECTING: { bg: 'rgba(94,94,94,0.15)',     color: '#5e5e5e' },
  };
  const s = styles[status] ?? styles.LIVE;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium"
      style={{ backgroundColor: s.bg, color: s.color }}
    >
      {status === 'LIVE' && <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: s.color }} />}
      {status}
    </span>
  );
}


export function ApprovalGate({
  label = 'Requires human approval',
  onApprove,
  onReject,
}: {
  label?: string;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  return (
    <div
      className="px-3 py-2 rounded text-xs"
      style={{ backgroundColor: 'rgba(201,183,135,0.1)', border: '1px solid rgba(201,183,135,0.25)' }}
    >
      <div className="flex items-center gap-2 font-medium" style={{ color: '#c9b787' }}>
        <svg width="12" height="12" fill="none" viewBox="0 0 16 16">
          <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 6.5a1 1 0 011 1v2a1 1 0 01-2 0v-2a1 1 0 011-1zm0-2.5a1 1 0 100-2 1 1 0 000 2z" fill="currentColor"/>
        </svg>
        {label}
      </div>
      {(onApprove || onReject) && (
        <div className="flex items-center gap-2 mt-2">
          {onApprove && (
            <button
              onClick={onApprove}
              className="px-3 py-1 rounded text-xs font-medium"
              style={{ backgroundColor: 'rgba(201,183,135,0.15)', color: '#c9b787', border: '1px solid rgba(201,183,135,0.3)', cursor: 'pointer' }}
            >
              ✓ Approve
            </button>
          )}
          {onReject && (
            <button
              onClick={onReject}
              className="px-3 py-1 rounded text-xs font-medium"
              style={{ backgroundColor: 'rgba(245,245,245,0.08)', color: '#f5f5f5', border: '1px solid rgba(245,245,245,0.15)', cursor: 'pointer' }}
            >
              ✕ Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function PageHeader({
  label,
  title,
  subtitle,
  status,
  children,
}: {
  label: string;
  title: string;
  subtitle?: string;
  status?: 'LIVE' | 'GATED' | 'APPROVED' | 'ROADMAP' | 'WARN' | 'ERROR' | 'CONNECTING';
  children?: ReactNode;
}) {
  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-2">
        <span className="text-xs font-mono" style={{ color: 'var(--color-a11oy-gold)' }}>{label}</span>
        {status && <StatusPill status={status} />}
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
          style={{ backgroundColor: 'rgba(201,183,135,0.06)', color: 'rgba(201,183,135,0.5)', border: '1px solid rgba(201,183,135,0.12)' }}
        >
          Governed Environment
        </span>
      </div>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight" style={{ color: 'var(--color-a11oy-text)' }}>
            {title}
          </h1>
          {subtitle && (
            <p className="mt-1 text-sm" style={{ color: 'var(--color-a11oy-text-sub)' }}>{subtitle}</p>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

export function Card({ children, className = '', onClick, style }: { children: ReactNode; className?: string; onClick?: () => void; style?: React.CSSProperties }) {
  return (
    <div
      className={`rounded-lg border p-4 ${className} ${onClick ? 'cursor-pointer transition-colors hover:border-[#c9b787]/30' : ''}`}
      style={{ backgroundColor: 'var(--color-a11oy-card)', borderColor: 'var(--color-a11oy-border)', ...style }}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h2 className={`text-sm font-display font-semibold mb-3 ${className}`} style={{ color: 'var(--color-a11oy-text)' }}>
      {children}
    </h2>
  );
}

export function KpiCard({ label, value, sub, accent, trend }: { label: string; value: string | number; sub?: string; accent?: string; trend?: 'up' | 'down' | 'neutral' }) {
  return (
    <div
      className="rounded-lg border p-4 flex flex-col gap-1"
      style={{ backgroundColor: 'var(--color-a11oy-card)', borderColor: 'var(--color-a11oy-border)' }}
    >
      <div className="text-xs font-mono uppercase tracking-wide" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{label}</div>
      <div className="flex items-end gap-2">
        <div className="text-2xl font-display font-semibold leading-none" style={{ color: accent ?? 'var(--color-a11oy-text)' }}>
          {value}
        </div>
        {trend && (
          <span className="text-xs mb-0.5 font-mono" style={{ color: trend === 'up' ? '#c9b787' : trend === 'down' ? '#f5f5f5' : '#5e5e5e' }}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
          </span>
        )}
      </div>
      {sub && <div className="text-xs" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{sub}</div>}
    </div>
  );
}

export function SeverityDot({ severity }: { severity: 'critical' | 'high' | 'medium' | 'low' | 'info' }) {
  const colors: Record<string, string> = {
    critical: '#f5f5f5',
    high: '#c9b787',
    medium: '#8a8a8a',
    low: '#5e5e5e',
    info: '#5e5e5e',
  };
  return (
    <span
      className="inline-block w-2 h-2 rounded-full flex-shrink-0"
      style={{ backgroundColor: colors[severity] ?? '#5e5e5e' }}
    />
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    critical:     { bg: 'rgba(245,245,245,0.10)', color: '#f5f5f5' },
    high:         { bg: 'rgba(201,183,135,0.12)', color: '#c9b787' },
    medium:       { bg: 'rgba(138,138,138,0.10)', color: '#8a8a8a' },
    low:          { bg: 'rgba(94,94,94,0.10)', color: '#5e5e5e' },
    info:         { bg: 'rgba(94,94,94,0.10)', color: '#5e5e5e' },
    active:       { bg: 'rgba(201,183,135,0.12)', color: '#c9b787' },
    escalated:    { bg: 'rgba(245,245,245,0.10)', color: '#f5f5f5' },
    acknowledged: { bg: 'rgba(138,138,138,0.10)', color: '#8a8a8a' },
    resolved:     { bg: 'rgba(94,94,94,0.10)', color: '#5e5e5e' },
    suppressed:   { bg: 'rgba(94,94,94,0.08)', color: '#5e5e5e' },
  };
  const s = styles[severity] ?? styles.info;
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: s.bg, color: s.color }}>
      {severity.toUpperCase()}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: 'pass' | 'fail' | 'warn' | 'abstain' }) {
  const styles: Record<string, { bg: string; color: string; icon: string }> = {
    pass:    { bg: 'rgba(201,183,135,0.12)', color: '#c9b787', icon: '✓' },
    fail:    { bg: 'rgba(245,245,245,0.10)',  color: '#f5f5f5', icon: '✗' },
    warn:    { bg: 'rgba(138,138,138,0.12)', color: '#8a8a8a', icon: '⚠' },
    abstain: { bg: 'rgba(94,94,94,0.12)',   color: '#5e5e5e', icon: '—' },
  };
  const s = styles[verdict] ?? styles.abstain;
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: s.bg, color: s.color }}>
      {s.icon} {verdict.toUpperCase()}
    </span>
  );
}

export function HashId({ id }: { id: string }) {
  return (
    <span className="font-mono text-xs" style={{ color: 'var(--color-a11oy-text-ghost)' }}>
      {id}
    </span>
  );
}

export function ActionButton({
  children,
  variant = 'primary',
  disabled,
  onClick,
  size = 'md',
}: {
  children: ReactNode;
  variant?: 'primary' | 'ghost' | 'danger' | 'warn';
  disabled?: boolean;
  onClick?: () => void;
  size?: 'sm' | 'md';
}) {
  const styles: Record<string, { bg: string; color: string; border: string }> = {
    primary: { bg: '#c9b787', color: '#0a0a0a', border: 'transparent' },
    ghost:   { bg: 'transparent', color: 'var(--color-a11oy-text-sub)', border: 'var(--color-a11oy-border)' },
    danger:  { bg: 'rgba(245,245,245,0.08)', color: '#f5f5f5', border: 'rgba(245,245,245,0.15)' },
    warn:    { bg: 'rgba(201,183,135,0.1)', color: '#c9b787', border: 'rgba(201,183,135,0.25)' },
  };
  const s = styles[variant];
  const pad = size === 'sm' ? 'px-2 py-1' : 'px-3 py-1.5';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${pad} rounded font-medium border transition-opacity`}
      style={{
        fontSize: size === 'sm' ? '11px' : '12px',
        backgroundColor: s.bg,
        color: s.color,
        borderColor: s.border,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      {children}
    </button>
  );
}

export function VerticalBadge({ vertical, color }: { vertical: string; color: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono"
      style={{ backgroundColor: `${color}18`, color, border: `1px solid ${color}30` }}
    >
      {vertical}
    </span>
  );
}

export function StatusBadge({ status, label }: { status: 'ok' | 'warn' | 'error' | 'info'; label: string }) {
  const colors = {
    ok:    '#c9b787',
    warn:  '#8a8a8a',
    error: '#f5f5f5',
    info:  '#5e5e5e',
  };
  const color = colors[status];
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
      style={{ backgroundColor: `${color}18`, color, border: `1px solid ${color}30` }}
    >
      {label}
    </span>
  );
}

export function CodeBlock({ children, language = 'json' }: { children: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="relative rounded-lg overflow-hidden" style={{ backgroundColor: 'rgba(0,0,0,0.4)', border: '1px solid var(--color-a11oy-border)' }}>
      <div className="flex items-center justify-between px-3 py-1.5 border-b" style={{ borderColor: 'var(--color-a11oy-border)' }}>
        <span className="text-xs font-mono" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{language}</span>
        <button
          onClick={copy}
          className="text-xs font-mono transition-colors"
          style={{ color: copied ? '#c9b787' : 'var(--color-a11oy-text-ghost)', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <pre className="p-3 text-xs overflow-x-auto" style={{ color: '#c9b787', margin: 0 }}>
        <code>{children}</code>
      </pre>
    </div>
  );
}

export function TraceStep({
  step,
  status,
  note,
}: {
  step: string;
  status: 'completed' | 'running' | 'pending' | 'failed' | 'skipped' | string;
  note?: string;
}) {
  const statusColor = status === 'completed' || status === 'ok' ? '#c9b787'
    : status === 'running' ? '#c9b787'
    : status === 'failed' || status === 'error' ? '#f5f5f5'
    : status === 'skipped' ? '#5e5e5e'
    : '#5e5e5e';
  const statusIcon = status === 'completed' || status === 'ok' ? '✓'
    : status === 'running' ? '⟳'
    : status === 'failed' || status === 'error' ? '✗'
    : status === 'skipped' ? '—'
    : '○';
  return (
    <div className="flex gap-3 py-1.5">
      <div className="flex flex-col items-center flex-shrink-0 pt-0.5">
        <div
          className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-mono border flex-shrink-0"
          style={{ backgroundColor: `${statusColor}18`, borderColor: statusColor, color: statusColor }}
        >
          {statusIcon}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium" style={{ color: 'var(--color-a11oy-text)' }}>{step}</div>
        {note && <div className="text-xs mt-0.5" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{note}</div>}
      </div>
      <div className="text-xs font-mono flex-shrink-0" style={{ color: statusColor }}>
        {status}
      </div>
    </div>
  );
}

export function ProgressBar({ value, max = 100, color = '#c9b787' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--color-a11oy-muted)' }}>
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

export function EmptyState({ title, description, icon = '⬡' }: { title: string; description?: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-3xl mb-3" style={{ color: 'var(--color-a11oy-border)' }}>{icon}</div>
      <div className="text-sm font-medium mb-1" style={{ color: 'var(--color-a11oy-text-sub)' }}>{title}</div>
      {description && <div className="text-xs" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{description}</div>}
    </div>
  );
}

export function InfoRow({ label, value, mono = false }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b" style={{ borderColor: 'var(--color-a11oy-border)' }}>
      <span className="text-xs w-36 flex-shrink-0" style={{ color: 'var(--color-a11oy-text-ghost)' }}>{label}</span>
      <span className={`text-xs flex-1 ${mono ? 'font-mono' : ''}`} style={{ color: 'var(--color-a11oy-text)' }}>
        {value}
      </span>
    </div>
  );
}

