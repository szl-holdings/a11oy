// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/sentra/src/components/AccessDeniedNotice.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { ArrowLeft, Lock } from 'lucide-react';
import { useLocation } from 'wouter';
import { popToPath, useCrumbs } from '../lib/cognitive-nav';

const DS = {
  surface: 'rgba(255,255,255,0.03)',
  border: 'rgba(255,255,255,0.07)',
  text: {
    primary: 'rgba(255,255,255,0.9)',
    secondary: 'rgba(255,255,255,0.55)',
    muted: 'rgba(255,255,255,0.4)',
  },
};

export class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'HttpError';
  }
}

export function isAccessDenied(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  const status = (err as { status?: unknown }).status;
  return status === 401 || status === 403;
}

export function AccessDeniedNotice({
  status,
  accent = '#f5f5f5',
  resourceLabel = 'this view',
}: {
  status: 401 | 403 | number;
  accent?: string;
  resourceLabel?: string;
}) {
  const crumbs = useCrumbs();
  const [, navigate] = useLocation();
  const previous = crumbs.length > 0 ? crumbs[crumbs.length - 1] : null;

  const goBack = () => {
    if (previous) {
      popToPath(previous.path);
      navigate(previous.path);
    } else {
      navigate('/');
    }
  };

  const title = status === 401 ? 'Sign-in required' : 'Access denied';
  const detail =
    status === 401
      ? `You need to be signed in to view ${resourceLabel}.`
      : `Your role doesn't have permission to view ${resourceLabel}. Ask an administrator if you need access.`;

  return (
    <div
      className="rounded-xl p-8 flex flex-col items-center text-center gap-4"
      style={{ background: DS.surface, border: `1px solid ${accent}33` }}
      role="alert"
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center"
        style={{ background: `${accent}18`, border: `1px solid ${accent}40` }}
      >
        <Lock className="w-5 h-5" style={{ color: accent }} />
      </div>
      <div className="space-y-1.5 max-w-md">
        <h2 className="text-base font-semibold" style={{ color: DS.text.primary }}>
          {title}
        </h2>
        <p className="text-sm" style={{ color: DS.text.secondary }}>
          {detail}
        </p>
      </div>
      <button
        onClick={goBack}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
        style={{ background: `${accent}10`, color: accent, border: `1px solid ${accent}33` }}
      >
        <ArrowLeft className="w-3 h-3" />
        {previous ? `Back to ${previous.label}` : 'Back to home'}
      </button>
    </div>
  );
}
