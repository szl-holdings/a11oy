// VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — artifacts/sentra/src/lib/cognitive-nav.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'wouter';

export type Crumb = {
  path: string;
  label: string;
  context?: string;
};

const KEY = 'aegis.cognitive.breadcrumbs';
const MAX = 6;

export const COGNITIVE_ROUTES: Record<string, string> = {
  '/cognitive-attack-path': 'Cognitive Attack Path',
  '/identity-blast-radius': 'Identity Blast Radius',
  '/compliance/incident-proof': 'Incident Proof Chain',
  '/business-impact': 'Business Impact Map',
};

function readStore(): Crumb[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Crumb[]) : [];
  } catch {
    return [];
  }
}

function writeStore(crumbs: Crumb[]) {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(crumbs.slice(-MAX)));
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent('aegis:crumbs-changed'));
}

export function pushCrumb(crumb: Crumb) {
  const crumbs = readStore();
  const last = crumbs[crumbs.length - 1];
  if (last && last.path === crumb.path && last.context === crumb.context) return;
  crumbs.push(crumb);
  writeStore(crumbs);
}

export function clearCrumbs() {
  writeStore([]);
}

export function popToPath(path: string) {
  const crumbs = readStore();
  const idx = crumbs.findIndex((c) => c.path === path);
  if (idx >= 0) writeStore(crumbs.slice(0, idx));
  else writeStore([]);
}

export function useCrumbs(): Crumb[] {
  const [crumbs, setCrumbs] = useState<Crumb[]>(() => readStore());
  useEffect(() => {
    const handler = () => setCrumbs(readStore());
    window.addEventListener('aegis:crumbs-changed', handler);
    window.addEventListener('storage', handler);
    return () => {
      window.removeEventListener('aegis:crumbs-changed', handler);
      window.removeEventListener('storage', handler);
    };
  }, []);
  return crumbs;
}

/** Navigate helper that records the source page as a breadcrumb. */
export function useDrilldown() {
  const [location, navigate] = useLocation();
  return useCallback(
    (target: string, opts?: { fromLabel?: string; fromContext?: string }) => {
      const fromLabel = opts?.fromLabel ?? COGNITIVE_ROUTES[location] ?? location;
      const crumb: Crumb = { path: location, label: fromLabel };
      if (opts?.fromContext) crumb.context = opts.fromContext;
      pushCrumb(crumb);
      navigate(target);
    },
    [location, navigate],
  );
}
