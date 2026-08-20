/**
 * Sentra theme tokens — aligned with a11oy + amaru/conduit "minimal dark" palette.
 *
 * Round 7 (Series-A blocker). Extracted from artifacts/a11oy/src/pages/Ecosystem.tsx
 * and artifacts/a11oy/src/pages/OrgRepoDeepDive.tsx so all SZL artifacts share the
 * same calm, low-chroma surface vocabulary.
 *
 * Pages should prefer the `T` object below over ad-hoc hex values. The
 * <SectionHead /> helper replaces the heavy emoji + gradient page headers
 * Sentra accumulated through earlier rounds.
 */

import type { CSSProperties, ReactNode } from 'react';

export const T = {
  bg: '#0b0d12',
  surface: '#12151c',
  surfaceHi: '#1a1f2a',
  border: '#2a313e',
  text: '#e6e9ef',
  dim: '#8b94a6',

  // Status palette — same hues as a11oy so cross-app cards stay coherent.
  green: '#4ade80',
  amber: '#fbbf24',
  red: '#f87171',
  blue: '#60a5fa',
  purple: '#c4b5fd',

  // Sentra signature accent — kept (a11oy uses the same gold/c9b787 on its
  // loader and Sentra brand). Use sparingly: focus ring, primary CTA, brand chip.
  accent: '#c9b787',
} as const;

export type ThemeTokens = typeof T;

export function pageStyle(extra: CSSProperties = {}): CSSProperties {
  return {
    background: T.bg,
    color: T.text,
    minHeight: '100vh',
    padding: '24px',
    ...extra,
  };
}

export function surfaceStyle(extra: CSSProperties = {}): CSSProperties {
  return {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    padding: 16,
    ...extra,
  };
}

/**
 * a11oy-style flat panel header. Replaces the ornate gradient + emoji blocks
 * that drift across older Sentra pages.
 */
export function SectionHead({
  title,
  subtitle,
  eyebrow,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      {eyebrow ? (
        <div
          style={{
            fontSize: 10,
            color: T.accent,
            textTransform: 'uppercase',
            letterSpacing: 1,
            fontFamily: 'JetBrains Mono, monospace',
            marginBottom: 4,
          }}
        >
          {eyebrow}
        </div>
      ) : null}
      <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{title}</div>
      {subtitle ? (
        <div style={{ fontSize: 12, color: T.dim, marginTop: 2 }}>{subtitle}</div>
      ) : null}
    </div>
  );
}

export function Stat({
  label,
  value,
  accent,
}: {
  label: ReactNode;
  value: ReactNode;
  accent?: string;
}) {
  const a = accent ?? T.accent;
  return (
    <div
      style={{
        background: T.surface,
        border: `1px solid ${T.border}`,
        borderLeft: `3px solid ${a}`,
        borderRadius: 6,
        padding: '12px 16px',
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: T.dim,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 600, color: a }}>{value}</div>
    </div>
  );
}
