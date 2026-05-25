import type React from 'react';

export interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  style?: React.CSSProperties;
}

export function KpiCard({ label, value, sub, color = '#f5f5f5', style }: KpiCardProps) {
  return (
    <div style={{
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 10,
      background: 'rgba(255,255,255,0.025)',
      padding: '16px 20px',
      flex: 1,
      minWidth: 140,
      ...style,
    }}>
      <div style={{
        fontSize: 9,
        fontFamily: 'var(--font-mono, monospace)',
        color: '#5e5e5e',
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, letterSpacing: '-0.03em', lineHeight: 1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: '#5e5e5e', marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}
