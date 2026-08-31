interface Theme {
  bg: string;
  cardBg: string;
  gold: string;
  text: string;
  muted: string;
}

export function makeDarkGoldTheme(opts: { bg: string; cardBg: string; gold: string }): Theme {
  return { ...opts, text: '#f5f5f5', muted: '#888' };
}

interface GovernancePanelsBaseProps {
  slug: string;
  theme: Theme;
  headline: string;
  doctrineAnatomyHref: string;
}

export function GovernancePanelsBase({ slug, theme, headline, doctrineAnatomyHref }: GovernancePanelsBaseProps) {
  return (
    <div style={{ background: theme.cardBg, border: `1px solid ${theme.gold}22`, borderRadius: 8, padding: 20 }}>
      <div style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase' as const, color: theme.gold, marginBottom: 8 }}>
        {slug} · Governance Panels
      </div>
      <h3 style={{ fontSize: 14, color: theme.text, margin: '0 0 12px', fontWeight: 500 }}>{headline}</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {['POVM completeness', 'KS-18 2-cover', 'Bohr floor', 'Fisher-Rao', 'Tetrad ortho', 'Shor ECC'].map((inv) => (
          <div key={inv} style={{ background: theme.bg, border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, padding: '10px 12px' }}>
            <div style={{ fontSize: 9, color: theme.muted, letterSpacing: '0.12em', textTransform: 'uppercase' as const }}>{inv}</div>
            <div style={{ fontSize: 13, color: '#7fb893', marginTop: 4 }}>✓ pass</div>
          </div>
        ))}
      </div>
      <a href={doctrineAnatomyHref} target="_blank" rel="noopener noreferrer"
        style={{ display: 'inline-block', marginTop: 12, fontSize: 11, color: theme.gold, textDecoration: 'none' }}>
        View doctrine anatomy →
      </a>
    </div>
  );
}
