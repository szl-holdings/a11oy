import React from 'react';
import { cn } from '@/lib/utils';
import type { GovernanceState, SeverityLevel } from '@/data/fabric/types';

/* Founder KANCHAY v1.1.0 operator components (szl-console.css): .page-head, .stat +
   .metric, .card, .toolbar, .scrim/.drawer, .sev, .dot, .meter, .spark, .heat.
   Identity stays neutral; status pairs a status ink or mark with a word. The legacy
   'gold' tone renders neutral (gold is reserved for premium moments). */

type Tone = 'good' | 'warn' | 'bad' | 'gold';

const DATA_TONE: Record<Tone | 'neutral', string | undefined> = {
  good: 'good',
  warn: 'warn',
  bad: 'bad',
  gold: undefined,
  neutral: undefined,
};

export function FabricHeader({
  eyebrow,
  title,
  blurb,
  trailing,
}: {
  eyebrow: string;
  title: string;
  blurb: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-head__title">{title}</h1>
        <p className="page-head__lead">{blurb}</p>
      </div>
      {trailing}
    </div>
  );
}

export function FabricStat({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tone?: 'neutral' | Tone;
}) {
  return (
    <div className="stat" data-tone={DATA_TONE[tone]}>
      {/* labels/subs at 12px use --text-sub: founder --text-ghost is 4.27:1 on --surface */}
      <div className="metric__label text-ink-sub">{label}</div>
      <div className="metric__value">{value}</div>
      {sub && <div className="stat__sub text-ink-sub">{sub}</div>}
    </div>
  );
}

const DOT: Record<GovernanceState, string> = {
  green: 'dot--ok',
  amber: 'dot--warn',
  red: 'dot--err',
};

export function GovernanceDot({ state }: { state: GovernanceState }) {
  return <span className={cn('dot', DOT[state] ?? 'dot--err')} title={state} />;
}

const SEV: Record<SeverityLevel, { cls: string; label: string }> = {
  critical: { cls: 'sev--critical', label: 'CRITICAL' },
  high: { cls: 'sev--high', label: 'HIGH' },
  medium: { cls: 'sev--medium', label: 'MED' },
  low: { cls: 'sev--low text-ink-sub', label: 'LOW' },
  info: { cls: 'sev--info', label: 'INFO' },
};

export function SeverityChip({ level }: { level: SeverityLevel }) {
  const t = SEV[level];
  return <span className={cn('sev', t.cls)}>{t.label}</span>;
}

export function FabricCard({
  children,
  className,
  title,
  trailing,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className={cn('conduit-card p-5', className)}>
      {(title || trailing) && (
        <div className="flex items-center justify-between gap-3 mb-4">
          {title && <div className="label-mono">{title}</div>}
          {trailing}
        </div>
      )}
      {children}
    </div>
  );
}

export function FabricToolbar({ children }: { children: React.ReactNode }) {
  return <div className="toolbar">{children}</div>;
}

export function FabricDrawer({
  open,
  onClose,
  title,
  subtitle,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const titleId = React.useId();
  if (!open) return null;
  return (
    <>
      <button type="button" className="scrim border-0 p-0 cursor-pointer" onClick={onClose} aria-label="Close" />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="drawer__head">
          <div>
            <div className="label-mono">Detail</div>
            <h3 id={titleId} className="drawer__title">{title}</h3>
            {subtitle && <div className="drawer__sub text-ink-sub">{subtitle}</div>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close detail" className="close-btn">
            ✕
          </button>
        </div>
        <div className="drawer__body">{children}</div>
      </aside>
    </>
  );
}

export function MicroBar({ value, max, tone = 'gold' }: { value: number; max: number; tone?: Tone }) {
  const pct = Math.max(0, Math.min(100, (value / Math.max(1, max)) * 100));
  return (
    <div className="meter" data-tone={DATA_TONE[tone]}>
      <div className="meter__fill" style={{ inlineSize: `${pct}%` }} />
    </div>
  );
}

export function Sparkline({ values, width = 120, height = 28, tone = 'gold' }: { values: readonly number[]; width?: number; height?: number; tone?: Tone }) {
  if (values.length === 0) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / Math.max(1, values.length - 1);
  const path = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / range) * height;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg className="spark" data-tone={DATA_TONE[tone]} width={width} height={height} aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

export function HeatCell({ value, max }: { value: number; max: number }) {
  const intensity = Math.max(0, Math.min(1, value / Math.max(1, max)));
  const heat = `${Math.round((0.08 + intensity * 0.5) * 100)}%`;
  return (
    <div className="heat" style={{ '--heat': heat } as React.CSSProperties} title={String(value)}>
      {value > 0 ? value : ''}
    </div>
  );
}
