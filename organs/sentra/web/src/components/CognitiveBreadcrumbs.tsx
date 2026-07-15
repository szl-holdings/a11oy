// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/components/CognitiveBreadcrumbs.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { ChevronRight, Home } from 'lucide-react';
import { useLocation } from 'wouter';
import { COGNITIVE_ROUTES, clearCrumbs, popToPath, useCrumbs } from '../lib/cognitive-nav';

const DS = {
  text: { primary: 'rgba(255,255,255,0.85)', muted: 'rgba(255,255,255,0.4)' },
};

export function CognitiveBreadcrumbs({ accent = '#f5f5f5' }: { accent?: string }) {
  const crumbs = useCrumbs();
  const [location, navigate] = useLocation();
  if (crumbs.length === 0) return null;

  const currentLabel = COGNITIVE_ROUTES[location] ?? 'Current view';

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 text-[11px] flex-wrap"
      style={{ color: DS.text.muted }}
    >
      <button
        onClick={() => {
          clearCrumbs();
          navigate('/');
        }}
        className="flex items-center gap-1 hover:text-white transition-colors"
        aria-label="Home"
      >
        <Home className="w-3 h-3" />
      </button>
      {crumbs.map((c, i) => (
        <span key={`${c.path}-${i}`} className="flex items-center gap-1.5">
          <ChevronRight className="w-3 h-3" style={{ color: DS.text.muted }} />
          <button
            onClick={() => {
              popToPath(c.path);
              navigate(c.path);
            }}
            className="hover:underline transition-colors"
            style={{ color: DS.text.primary }}
          >
            {c.label}
            {c.context && (
              <span className="ml-1" style={{ color: DS.text.muted }}>
                · {c.context}
              </span>
            )}
          </button>
        </span>
      ))}
      <ChevronRight className="w-3 h-3" style={{ color: DS.text.muted }} />
      <span style={{ color: accent }}>{currentLabel}</span>
    </nav>
  );
}
