import { Link } from 'wouter';

const T = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.08)',
  text: '#f5f5f5',
  dim: '#8a8a8a',
  muted: '#5e5e5e',
  accent: '#c9b787',
};

function stripTrailingSlash(path: string) {
  return path.endsWith('/') && path.length > 1 ? path.slice(0, -1) : path;
}

const base = stripTrailingSlash((import.meta.env.BASE_URL ?? '/').replace(/\/$/, '') || '');

export type DefensePageId =
  | 'precision-ai'
  | 'weaponized-intel'
  | 'atlas-shield'
  | 'adversarial'
  | 'supply-chain'
  | 'agent-zero-trust'
  | 'gard-robustness'
  | 'cyber-resilience';

interface DefensePage {
  id: DefensePageId;
  label: string;
  blurb: string;
  group: 'defense' | 'resilience';
}

export const DEFENSE_PAGES: DefensePage[] = [
  { id: 'precision-ai', label: 'Precision AI', blurb: 'SmartScore triage', group: 'defense' },
  { id: 'weaponized-intel', label: 'Weaponized Intel', blurb: 'Adversary kill-chain', group: 'defense' },
  { id: 'atlas-shield', label: 'ATLAS Shield', blurb: 'MITRE coverage', group: 'defense' },
  { id: 'adversarial', label: 'Adversarial Resilience', blurb: 'Attack simulations', group: 'defense' },
  { id: 'supply-chain', label: 'Supply Chain Attestation', blurb: 'SBOM + vendor risk', group: 'defense' },
  { id: 'agent-zero-trust', label: 'Agent Zero Trust', blurb: 'Ephemeral identity', group: 'defense' },
  { id: 'gard-robustness', label: 'GARD Robustness', blurb: 'Adversarial robustness', group: 'resilience' },
  { id: 'cyber-resilience', label: 'Cyber Resilience', blurb: 'DARPA hub', group: 'resilience' },
];

export function defensePath(id: DefensePageId) {
  return `${base}/${id}`;
}

interface RelatedItem {
  id: DefensePageId;
  reason?: string;
}

export function DefenseCrossNav({
  currentId,
  related,
}: {
  currentId: DefensePageId;
  related?: RelatedItem[];
}) {
  const reasonMap = new Map((related ?? []).map(r => [r.id, r.reason]));
  const relatedIds = new Set((related ?? []).map(r => r.id));

  return (
    <div className="mt-8 mb-2">
      <div className="text-[9px] font-mono uppercase tracking-widest mb-3" style={{ color: T.muted }}>
        Defense Suite — Related Pages
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {DEFENSE_PAGES.filter(p => p.id !== currentId).map(page => {
          const isRelated = relatedIds.has(page.id);
          const reason = reasonMap.get(page.id);
          return (
            <Link
              key={page.id}
              href={defensePath(page.id)}
              className="block rounded-lg p-3 transition-all"
              style={{
                background: isRelated ? 'rgba(201,183,135,0.06)' : T.surface,
                border: `1px solid ${isRelated ? 'rgba(201,183,135,0.2)' : T.border}`,
                cursor: 'pointer',
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: isRelated ? T.accent : T.dim }}>
                  {page.label}
                </span>
                {isRelated && (
                  <span className="text-[8px] font-mono px-1 py-0.5 rounded" style={{ background: 'rgba(201,183,135,0.12)', color: T.accent }}>
                    related
                  </span>
                )}
              </div>
              <div className="text-[10px]" style={{ color: T.muted }}>
                {reason ?? page.blurb}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function DefenseLink({
  to,
  children,
  title,
}: {
  to: DefensePageId;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <Link
      href={defensePath(to)}
      title={title}
      className="underline-offset-2 hover:underline"
      style={{ color: T.accent, cursor: 'pointer' }}
    >
      {children}
    </Link>
  );
}
