import React from 'react';
import { cn } from '@/lib/utils';
import type { GovernanceState, SeverityLevel } from '@/data/fabric/types';

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
    <div className="flex items-end justify-between gap-6 mb-6">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-[#c9b787] mb-2">{eyebrow}</div>
        <h1 className="text-3xl font-light tracking-tight text-[#f5f5f5]">{title}</h1>
        <p className="mt-2 text-sm text-[#8a8a8a] max-w-3xl leading-relaxed">{blurb}</p>
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
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'gold';
}) {
  const toneClass =
    tone === 'good' ? 'text-[#5a8a6e]' : tone === 'warn' ? 'text-[#d4a853]' : tone === 'bad' ? 'text-[#b85450]' : tone === 'gold' ? 'text-[#c9b787]' : 'text-[#f5f5f5]';
  return (
    <div className="conduit-stat p-4">
      <div className="label-mono mb-2">{label}</div>
      <div className={cn('text-2xl font-light tabular-nums', toneClass)}>{value}</div>
      {sub && <div className="text-[11px] text-[#666] mt-1">{sub}</div>}
    </div>
  );
}

export function GovernanceDot({ state }: { state: GovernanceState }) {
  const color = state === 'green' ? '#5a8a6e' : state === 'amber' ? '#d4a853' : '#b85450';
  return (
    <span
      className="inline-block w-1.5 h-1.5 rounded-full"
      title={state}
      style={{ background: color, boxShadow: `0 0 6px ${color}55` }}
    />
  );
}

export function SeverityChip({ level }: { level: SeverityLevel }) {
  const map: Record<SeverityLevel, { bg: string; fg: string; bd: string; label: string }> = {
    critical: { bg: 'rgba(184,84,80,0.18)', fg: '#b85450', bd: 'rgba(184,84,80,0.3)', label: 'CRITICAL' },
    high: { bg: 'rgba(212,168,83,0.16)', fg: '#d4a853', bd: 'rgba(212,168,83,0.3)', label: 'HIGH' },
    medium: { bg: 'rgba(201,183,135,0.12)', fg: '#c9b787', bd: 'rgba(201,183,135,0.22)', label: 'MED' },
    low: { bg: 'rgba(138,138,138,0.12)', fg: '#8a8a8a', bd: 'rgba(138,138,138,0.18)', label: 'LOW' },
    info: { bg: 'rgba(120,170,200,0.12)', fg: '#78aac8', bd: 'rgba(120,170,200,0.2)', label: 'INFO' },
  };
  const t = map[level];
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono tracking-wider font-medium"
      style={{ background: t.bg, color: t.fg, border: `1px solid ${t.bd}` }}
    >
      {t.label}
    </span>
  );
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
        <div className="flex items-center justify-between mb-4">
          {title && <div className="label-mono text-[#c9b787]">{title}</div>}
          {trailing}
        </div>
      )}
      {children}
    </div>
  );
}

export function FabricToolbar({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-4 p-3 rounded-lg border border-[rgba(255,255,255,0.06)]" style={{ background: '#0e0e0e' }}>
      {children}
    </div>
  );
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
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true">
      <button
        className="flex-1 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close"
      />
      <aside className="w-[480px] max-w-full overflow-y-auto border-l border-[rgba(255,255,255,0.06)] animate-slide-in-right" style={{ background: '#0e0e0e' }}>
        <div className="sticky top-0 z-10 px-5 py-4 border-b border-[rgba(255,255,255,0.06)] flex items-start justify-between glass-panel">
          <div>
            <div className="label-mono text-[#c9b787]">DETAIL</div>
            <h3 className="text-lg font-medium text-[#f5f5f5] mt-1">{title}</h3>
            {subtitle && <div className="text-[12px] text-[#8a8a8a] mt-0.5">{subtitle}</div>}
          </div>
          <button onClick={onClose} className="text-[#8a8a8a] hover:text-[#f5f5f5] text-sm">
            ✕
          </button>
        </div>
        <div className="p-5 space-y-4">{children}</div>
      </aside>
    </div>
  );
}

export function MicroBar({ value, max, tone = 'gold' }: { value: number; max: number; tone?: 'gold' | 'good' | 'warn' | 'bad' }) {
  const pct = Math.max(0, Math.min(100, (value / Math.max(1, max)) * 100));
  const color = tone === 'good' ? '#5a8a6e' : tone === 'warn' ? '#d4a853' : tone === 'bad' ? '#b85450' : '#c9b787';
  return (
    <div className="w-full h-1.5 rounded-full overflow-hidden bg-[rgba(255,255,255,0.04)]">
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export function Sparkline({ values, width = 120, height = 28, tone = 'gold' }: { values: readonly number[]; width?: number; height?: number; tone?: 'gold' | 'good' | 'warn' | 'bad' }) {
  if (values.length === 0) return <svg width={width} height={height} />;
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
  const color = tone === 'good' ? '#5a8a6e' : tone === 'warn' ? '#d4a853' : tone === 'bad' ? '#b85450' : '#c9b787';
  return (
    <svg width={width} height={height}>
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

export function HeatCell({ value, max }: { value: number; max: number }) {
  const intensity = Math.max(0, Math.min(1, value / Math.max(1, max)));
  const bg = `rgba(184,84,80,${0.08 + intensity * 0.5})`;
  return (
    <div
      className="aspect-square rounded flex items-center justify-center text-[10px] font-mono tabular-nums text-[#f5f5f5]"
      style={{ background: bg, border: '1px solid rgba(255,255,255,0.04)' }}
      title={String(value)}
    >
      {value > 0 ? value : ''}
    </div>
  );
}
