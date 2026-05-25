import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Sparkles, TrendingUp } from 'lucide-react';

interface CapabilityProposal {
  id: string;
  title: string;
  description: string;
  targetAgent: string;
  priority: string;
  status: string;
  impactArea?: string;
  estimatedEffort?: string;
}

interface ProposalsResponse {
  proposals: CapabilityProposal[];
  total: number;
}

const PRIORITY_COLOR: Record<string, string> = {
  P0: '#ef4444',
  P1: '#f59e0b',
  P2: '#3b82f6',
  P3: '#6b7280',
};

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  in_progress: 'In Review',
  approved: 'Approved',
  deployed: 'Live',
  rejected: 'Rejected',
};

async function fetchProposals(): Promise<CapabilityProposal[]> {
  const res = await fetch('/api/helios/proposals?status=new,in_progress&limit=4');
  if (!res.ok) return [];
  const data: ProposalsResponse = await res.json();
  return data.proposals ?? [];
}

export function HeliosProposalsInbox() {
  const { data: proposals = [], isLoading } = useQuery({
    queryKey: ['helios-proposals-inbox'],
    queryFn: fetchProposals,
    staleTime: 60_000,
    retry: false,
  });

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-surface-border)',
        padding: '24px',
      }}
    >
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4" style={{ color: '#f59e0b' }} />
          <span
            className="text-xs font-bold uppercase tracking-widest"
            style={{ color: 'var(--color-fg-muted)' }}
          >
            HELIOS Capability Proposals
          </span>
        </div>
        <a
          href="/helios/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded"
          style={{
            color: '#f59e0b',
            backgroundColor: 'color-mix(in srgb, #f59e0b 10%, transparent)',
            border: '1px solid color-mix(in srgb, #f59e0b 25%, transparent)',
            textDecoration: 'none',
          }}
        >
          Open HELIOS <ArrowRight className="w-2.5 h-2.5" />
        </a>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-16 rounded-lg animate-pulse"
              style={{ backgroundColor: 'var(--color-surface-border)' }}
            />
          ))}
        </div>
      ) : proposals.length === 0 ? (
        <p className="text-xs text-center py-8" style={{ color: 'var(--color-fg-muted)' }}>
          No pending proposals from HELIOS
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {proposals.map((p) => {
            const color = PRIORITY_COLOR[p.priority] ?? '#6b7280';
            return (
              <div
                key={p.id}
                className="rounded-lg p-3 flex items-start gap-3"
                style={{
                  backgroundColor: 'var(--color-bg-base)',
                  border: '1px solid var(--color-surface-border)',
                  borderLeftWidth: '3px',
                  borderLeftColor: color,
                }}
              >
                <TrendingUp
                  className="w-4 h-4 mt-0.5 shrink-0"
                  style={{ color }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p
                      className="text-xs font-semibold leading-snug truncate"
                      style={{ color: 'var(--color-fg-primary)' }}
                    >
                      {p.title}
                    </p>
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                      style={{
                        color,
                        backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
                      }}
                    >
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className="text-[10px]"
                      style={{ color: 'var(--color-fg-muted)' }}
                    >
                      {p.targetAgent}
                    </span>
                    {p.impactArea && (
                      <>
                        <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                          ·
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                          {p.impactArea}
                        </span>
                      </>
                    )}
                    {p.estimatedEffort && (
                      <>
                        <span className="text-[10px]" style={{ color: 'var(--color-fg-muted)' }}>
                          ·
                        </span>
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: 'var(--color-fg-muted)' }}
                        >
                          {p.estimatedEffort}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <span
                  className="text-[11px] font-bold font-mono shrink-0"
                  style={{ color }}
                >
                  {p.priority}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
