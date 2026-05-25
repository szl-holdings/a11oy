import { useStandardQuery } from '@szl-holdings/api-client-react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
} from 'lucide-react';
import { Link } from 'wouter';

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

type Decision = 'allow' | 'require-approval' | 'require-dual-approval' | 'block';

interface RecentRow {
  id: number;
  requestId: string;
  agentId: string | null;
  tier: string;
  action: string;
  toolId: string | null;
  decision: Decision;
  reason: string | null;
  decidedAt: string;
  traceId: string | null;
  traceDomain: string | null;
  approvalStatus: string | null;
  approvalType: string | null;
  approvalExpiresAt: string | null;
}

interface SummaryResponse {
  data: {
    windowMinutes: number;
    since: string;
    counts: {
      allow: number;
      requireApproval: number;
      requireDualApproval: number;
      block: number;
      total: number;
    };
    pendingApprovals: number;
    recent: RecentRow[];
  };
}

function timeAgo(iso?: string | null): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const s = Math.max(1, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function decisionLabel(d: Decision): string {
  switch (d) {
    case 'allow':
      return 'allow';
    case 'require-approval':
      return 'approval';
    case 'require-dual-approval':
      return 'dual approval';
    case 'block':
      return 'denied';
  }
}

const DECISION_STYLE: Record<Decision, { fg: string; bg: string; border: string }> = {
  allow: { fg: '#22c55e', bg: 'rgba(34,197,94,0.10)', border: 'rgba(34,197,94,0.30)' },
  'require-approval': {
    fg: '#d4a054',
    bg: 'rgba(212,160,84,0.10)',
    border: 'rgba(212,160,84,0.30)',
  },
  'require-dual-approval': {
    fg: '#f97316',
    bg: 'rgba(249,115,22,0.10)',
    border: 'rgba(249,115,22,0.30)',
  },
  block: { fg: '#ef4444', bg: 'rgba(239,68,68,0.10)', border: 'rgba(239,68,68,0.30)' },
};

function CountBlock({
  label,
  value,
  Icon,
  color,
}: {
  label: string;
  value: number;
  Icon: typeof ShieldCheck;
  color: string;
}) {
  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded-lg flex-1 min-w-[120px]"
      style={{
        background: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-surface-border)',
      }}
    >
      <div
        className="w-8 h-8 rounded flex items-center justify-center"
        style={{ background: `${color}14`, border: `1px solid ${color}30` }}
      >
        <Icon className="w-4 h-4" style={{ color }} />
      </div>
      <div className="flex flex-col min-w-0">
        <span
          className="text-[18px] font-bold leading-tight"
          style={{ color: 'var(--color-fg-primary)' }}
        >
          {value.toLocaleString()}
        </span>
        <span
          className="text-[9px] font-mono uppercase tracking-wider truncate"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          {label}
        </span>
      </div>
    </div>
  );
}

export function GuardianDecisionsTile() {
  const q = useStandardQuery<SummaryResponse>({
    queryKey: ['guardian', 'decisions-summary', '1h'],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/guardian/decisions/summary?windowMinutes=60&limit=8`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
      }
      return res.json() as Promise<SummaryResponse>;
    },
    refetchInterval: 30_000,
  });

  const data = q.data?.data;
  const counts = data?.counts ?? {
    allow: 0,
    requireApproval: 0,
    requireDualApproval: 0,
    block: 0,
    total: 0,
  };
  const pending = data?.pendingApprovals ?? 0;
  const recent = data?.recent ?? [];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-surface-border)',
        padding: '20px',
      }}
    >
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" style={{ color: '#d4a054' }} />
          <span
            className="text-xs font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Guardian Decisions
          </span>
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded"
            style={{
              color: 'var(--color-fg-muted)',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--color-surface-border)',
            }}
          >
            last 60m
          </span>
        </div>
        <Link
          href={`${BASE}/operations/guardian/approvals`}
          className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded inline-flex items-center gap-1"
          style={{
            color: '#d4a054',
            backgroundColor: 'rgba(212,160,84,0.10)',
            border: '1px solid rgba(212,160,84,0.30)',
          }}
        >
          Open Console <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {q.isLoading ? (
        <div
          className="text-[11px] font-mono py-6 text-center"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Loading…
        </div>
      ) : q.error ? (
        <div
          className="rounded p-3 text-[11px] font-mono flex items-start gap-2"
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.25)',
            color: '#ef4444',
          }}
        >
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">Failed to load Guardian decisions</div>
            <div className="opacity-80 mt-0.5">{(q.error as Error).message}</div>
          </div>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 mb-4">
            <CountBlock label="Allowed" value={counts.allow} Icon={CheckCircle2} color="#22c55e" />
            <CountBlock
              label="Approval"
              value={counts.requireApproval + counts.requireDualApproval}
              Icon={ShieldAlert}
              color="#d4a054"
            />
            <CountBlock label="Blocked" value={counts.block} Icon={ShieldX} color="#ef4444" />
            <CountBlock label="Awaiting you" value={pending} Icon={Clock} color="#8b7ac8" />
          </div>

          <div
            className="text-[9px] font-mono uppercase tracking-widest mb-2"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            Recent denials & pending approvals
          </div>

          {recent.length === 0 ? (
            <div
              className="text-[11px] font-mono py-4 text-center rounded"
              style={{
                color: 'var(--color-fg-muted)',
                border: '1px dashed var(--color-surface-border)',
              }}
            >
              No blocked or pending-approval decisions in the last hour.
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {recent.map((row) => {
                const ds = DECISION_STYLE[row.decision];
                const traceHref = row.traceId
                  ? `${BASE}/cognitive/traces?trace=${encodeURIComponent(row.traceId)}`
                  : null;
                return (
                  <div
                    key={row.id}
                    className="flex items-start gap-2 px-2.5 py-1.5 rounded"
                    style={{
                      background: 'rgba(255,255,255,0.015)',
                      border: '1px solid var(--color-surface-border)',
                    }}
                  >
                    <span
                      className="text-[8px] font-mono font-semibold tracking-wider px-1.5 py-px rounded uppercase shrink-0 mt-0.5"
                      style={{ color: ds.fg, background: ds.bg, border: `1px solid ${ds.border}` }}
                    >
                      {decisionLabel(row.decision)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-[11px] font-semibold truncate"
                        style={{ color: 'var(--color-fg-primary)' }}
                        title={row.action}
                      >
                        {row.action}
                      </div>
                      <div
                        className="text-[10px] font-mono truncate"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        {row.agentId ?? 'anon-agent'}
                        {row.toolId ? ` · ${row.toolId}` : ''}
                        {row.traceDomain ? ` · ${row.traceDomain}` : ''}
                        {' · '}
                        <span style={{ opacity: 0.7 }}>{timeAgo(row.decidedAt)}</span>
                      </div>
                      {row.reason && (
                        <div
                          className="text-[10px] mt-0.5 truncate"
                          style={{ color: 'var(--color-fg-muted)' }}
                          title={row.reason}
                        >
                          {row.reason}
                        </div>
                      )}
                    </div>
                    {traceHref ? (
                      <Link
                        href={traceHref}
                        className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded inline-flex items-center gap-1 shrink-0"
                        style={{
                          color: '#8b7ac8',
                          background: 'rgba(139,122,200,0.10)',
                          border: '1px solid rgba(139,122,200,0.30)',
                        }}
                        title={`Trace ${row.traceId}`}
                      >
                        Trace <ExternalLink className="w-2.5 h-2.5" />
                      </Link>
                    ) : (
                      <span
                        className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0"
                        style={{
                          color: 'var(--color-fg-muted)',
                          border: '1px solid var(--color-surface-border)',
                        }}
                        title="No trace recorded for this decision"
                      >
                        no trace
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default GuardianDecisionsTile;
