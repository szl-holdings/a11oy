import type { AppPage } from '../App';
import { useA11oyConstitution } from '../hooks/useA11oyConstitution';

interface NavBarProps {
  current: AppPage;
  onNavigate: (p: AppPage) => void;
}

const NAV_ITEMS: Array<{ id: AppPage; label: string; glyph: string }> = [
  { id: 'identity',  label: 'Identity',         glyph: '◎' },
  { id: 'optimizer', label: 'Optimizer',         glyph: '⬡' },
  { id: 'fabric',    label: 'Ecosystem Fabric',  glyph: '✦' },
  { id: 'research',  label: 'Research Library',  glyph: '◆' },
  { id: 'proof',     label: 'Proof Ledger',      glyph: '◉' },
  { id: 'bench',     label: 'Evidence Bench',    glyph: '◈' },
];

export function NavBar({ current, onNavigate }: NavBarProps) {
  const { status, constitutionVersion } = useA11oyConstitution();

  const statusColor = status === 'live' ? '#10b981' : status === 'fallback' ? '#f59e0b' : '#64748b';
  const statusLabel =
    status === 'live'     ? `A11oy Constitution v${constitutionVersion} active (live)` :
    status === 'fallback' ? `A11oy Constitution v${constitutionVersion} active (seed)` :
                            'A11oy Constitution loading…';

  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 100,
      background: 'rgba(3, 7, 18, 0.92)',
      backdropFilter: 'blur(12px)',
      borderBottom: '1px solid rgba(6, 182, 212, 0.12)',
      padding: '0 1.5rem',
    }}>
      <div style={{
        maxWidth: 1280, margin: '0 auto',
        display: 'flex', alignItems: 'center', gap: '1rem',
        height: 56,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginRight: '1rem' }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'linear-gradient(135deg, #06b6d4, #7c3aed)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 800, color: '#fff',
            boxShadow: '0 0 16px rgba(6,182,212,0.4)',
          }}>R</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', lineHeight: 1 }}>ROSIE</div>
            <div style={{ fontSize: 9, color: 'rgba(6,182,212,0.7)', letterSpacing: '0.12em', fontWeight: 600 }}>r0513</div>
          </div>
        </div>

        {/* Nav Items — rendered as anchor links so the URL hash updates on click */}
        <div style={{ display: 'flex', gap: '0.25rem', flex: 1 }}>
          {NAV_ITEMS.map(item => (
            <a
              key={item.id}
              href={`#${item.id}`}
              onClick={e => { e.preventDefault(); onNavigate(item.id); }}
              style={{
                textDecoration: 'none',
                background: current === item.id
                  ? 'rgba(6, 182, 212, 0.1)'
                  : 'transparent',
                border: current === item.id
                  ? '1px solid rgba(6, 182, 212, 0.3)'
                  : '1px solid transparent',
                borderRadius: 6,
                padding: '0.35rem 0.75rem',
                color: current === item.id ? '#06b6d4' : '#64748b',
                fontSize: 13,
                fontWeight: current === item.id ? 600 : 400,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={e => {
                if (current !== item.id) {
                  (e.currentTarget as HTMLAnchorElement).style.color = '#94a3b8';
                }
              }}
              onMouseLeave={e => {
                if (current !== item.id) {
                  (e.currentTarget as HTMLAnchorElement).style.color = '#64748b';
                }
              }}
            >
              <span style={{ fontSize: 11 }}>{item.glyph}</span>
              {item.label}
            </a>
          ))}
        </div>

        {/* Constitution status chip — reflects live / seed / loading state */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.25rem 0.75rem',
          background: 'rgba(6, 182, 212, 0.05)',
          border: '1px solid rgba(6, 182, 212, 0.15)',
          borderRadius: 20,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 6px ${statusColor}`,
            transition: 'background 0.3s',
          }} />
          <span style={{ fontSize: 11, color: '#64748b', fontWeight: 500 }}>{statusLabel}</span>
        </div>
      </div>
    </nav>
  );
}
