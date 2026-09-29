interface Theme {
  bg: string;
  cardBg: string;
  gold: string;
  text: string;
  muted: string;
}

export function makeDarkGoldTheme(opts: { bg: string; cardBg: string; gold: string }): Theme {
  return { ...opts, text: 'var(--text)', muted: 'var(--text-sub)' };
}

interface GovernancePanelsBaseProps {
  slug: string;
  theme: Theme;
  headline: string;
  doctrineAnatomyHref: string;
}

export function GovernancePanelsBase({ slug, theme, headline, doctrineAnatomyHref }: GovernancePanelsBaseProps) {
  return (
    <div style={{ background: theme.cardBg, border: `1px solid color-mix(in srgb, ${theme.gold} 13%, transparent)`, borderRadius: 'var(--radius-md)', padding: 20 }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase' as const, color: theme.gold, marginBottom: 8 }}>
        {slug} · Governance Panels
      </div>
      <h3 style={{ fontSize: 14, color: theme.text, margin: '0 0 12px', fontWeight: 500 }}>{headline}</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {['POVM completeness', 'KS-18 2-cover', 'Bohr floor', 'Fisher-Rao', 'Tetrad ortho', 'Shor ECC'].map((inv) => (
          <div key={inv} style={{ background: theme.bg, border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '10px 12px' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: theme.muted, letterSpacing: '0.12em', textTransform: 'uppercase' as const }}>{inv}</div>
            <div style={{ fontSize: 13, color: 'var(--ink-good)', marginTop: 4 }}>✓ pass</div>
          </div>
        ))}
      </div>
      <a href={doctrineAnatomyHref} target="_blank" rel="noopener noreferrer"
        style={{ display: 'inline-block', marginTop: 12, fontSize: 11, color: 'var(--link)' }}>
        View doctrine anatomy →
      </a>
    </div>
  );
}
