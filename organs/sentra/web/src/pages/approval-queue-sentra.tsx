// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Search, Shield, XCircle } from 'lucide-react';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useSentraStore, ensureSeeded, type Approval, type ApprovalStatus } from '@/lib/sentra-store';

const STATUS_CONFIG: Record<ApprovalStatus, { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: 'PENDING', color: '#f59e0b', icon: Clock },
  approved: { label: 'APPROVED', color: '#4ade80', icon: CheckCircle2 },
  rejected: { label: 'REJECTED', color: '#e05252', icon: XCircle },
  expired: { label: 'EXPIRED', color: '#8a8a8a', icon: XCircle },
  canceled: { label: 'CANCELED', color: '#8a8a8a', icon: XCircle },
};

const ROLLBACK_COLOR = { low: '#4ade80', medium: '#f59e0b', high: '#e05252' };

function ApprovalCard({ approval, onDecide }: {
  approval: Approval;
  onDecide: (id: string, decision: 'approved' | 'rejected', reason?: string) => void;
}) {
  const [expanded, setExpanded] = useState(approval.status === 'pending');
  const [reason, setReason] = useState('');
  const [deciding, setDeciding] = useState(false);

  const statusCfg = STATUS_CONFIG[approval.status];
  const StatusIcon = statusCfg.icon;
  const blast = approval.blast_radius_preview;
  const isExpired = approval.status === 'pending' && new Date(approval.expires_at) < new Date();
  const timeRemaining = new Date(approval.expires_at).getTime() - Date.now();
  const hoursRemaining = Math.max(0, Math.floor(timeRemaining / 3600000));

  async function handleDecide(decision: 'approved' | 'rejected') {
    setDeciding(true);
    onDecide(approval.id, decision, reason || undefined);
    setDeciding(false);
    setExpanded(false);
  }

  return (
    <div className={cn('rounded-lg border transition-all', approval.status === 'pending' && 'border-[#f59e0b]/20', expanded && !['pending'].includes(approval.status) && 'border-[#c9b787]/10')}
      style={{ background: 'rgba(255,255,255,0.025)', borderColor: approval.status === 'pending' ? undefined : 'rgba(255,255,255,0.08)' }}>
      <div className="flex items-center gap-3 p-4 cursor-pointer" onClick={() => setExpanded(x => !x)}>
        <div className="w-1 h-12 rounded-full flex-shrink-0" style={{ background: statusCfg.color }} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-slate-200">{approval.action_description}</div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-mono text-slate-500">{approval.id}</span>
            <span className="text-[10px] text-slate-600">·</span>
            <span className="text-[10px] font-mono text-[#c9b787]">{approval.action_class.replace(/_/g, ' ').toUpperCase()}</span>
            <span className="text-[10px] text-slate-600">·</span>
            <span className="text-[10px] font-mono text-slate-500">{approval.target_asset_name}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold border"
            style={{ color: statusCfg.color, borderColor: `${statusCfg.color}30`, background: `${statusCfg.color}10` }}>
            <StatusIcon className="w-2.5 h-2.5" />
            {isExpired ? 'EXPIRED' : statusCfg.label}
          </span>
          {approval.status === 'pending' && !isExpired && (
            <span className="text-[9px] font-mono text-slate-500">{hoursRemaining}h remaining</span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-slate-700/50 p-4 space-y-4">
          {/* Impact framing */}
          <div className="rounded-md border p-3 space-y-2" style={{ borderColor: 'rgba(245,158,11,0.2)', background: 'rgba(245,158,11,0.04)' }}>
            <div className="text-[10px] font-mono uppercase text-[#f59e0b] mb-2">Blast Radius Preview (Counterfactual)</div>
            <div className="text-[11px] text-slate-300 leading-relaxed">{blast.description}</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
              {[
                { label: 'Unreachable Assets', value: blast.unreachable_assets.length },
                { label: 'Revoked Sessions', value: blast.revoked_sessions },
                { label: 'Downstream Services', value: blast.downstream_services.length },
                { label: 'Recovery (min)', value: blast.estimated_recovery_minutes },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <div className="text-lg font-bold text-slate-200">{value}</div>
                  <div className="text-[9px] font-mono text-slate-500">{label}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-[10px] font-mono text-slate-500">Rollback Cost:</span>
              <span className="text-[10px] font-mono font-bold" style={{ color: ROLLBACK_COLOR[blast.rollback_cost] }}>
                {blast.rollback_cost.toUpperCase()}
              </span>
            </div>
            {blast.unreachable_assets.length > 0 && (
              <div className="text-[10px] font-mono text-slate-500">
                Affected: {blast.unreachable_assets.slice(0, 3).join(', ')}{blast.unreachable_assets.length > 3 && ` +${blast.unreachable_assets.length - 3} more`}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Details */}
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Approval Details</div>
              <div className="space-y-1 text-[11px]">
                {[
                  ['Target Asset', approval.target_asset_name],
                  ['Ownership', approval.target_ownership_status.toUpperCase()],
                  ['Integration', approval.integration_id ?? '—'],
                  ['Requested By', approval.requested_by],
                  ['Requested At', new Date(approval.requested_at).toLocaleString()],
                  ['Expires At', new Date(approval.expires_at).toLocaleString()],
                  ['Incident', approval.incident_id],
                ].map(([label, value]) => (
                  <div key={label} className="flex gap-2">
                    <span className="text-slate-500 w-28 flex-shrink-0">{label}</span>
                    <span className="text-slate-300 font-mono">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Doctrine + rollback */}
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Doctrine Citations</div>
              <div className="space-y-1 mb-3">
                {approval.doctrine_citations.map(c => (
                  <div key={c} className="flex items-center gap-1.5 text-[10px] font-mono text-[#c9b787]">
                    <Shield className="w-2.5 h-2.5 flex-shrink-0" />
                    {c}
                  </div>
                ))}
              </div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">Rollback Path</div>
              <div className="text-[11px] text-slate-400 italic">{approval.rollback_path}</div>

              {approval.status !== 'pending' && (
                <div className="mt-3 p-2 rounded-md bg-slate-800/40 border border-slate-700/50">
                  <div className="text-[10px] font-mono text-slate-500">Decision: <span className="font-bold" style={{ color: STATUS_CONFIG[approval.status].color }}>{approval.status.toUpperCase()}</span></div>
                  {approval.reviewed_by && <div className="text-[10px] font-mono text-slate-500">By: {approval.reviewed_by} at {approval.reviewed_at ? new Date(approval.reviewed_at).toLocaleString() : '—'}</div>}
                  {approval.review_reason && <div className="text-[10px] text-slate-400 italic mt-1">{approval.review_reason}</div>}
                </div>
              )}
            </div>
          </div>

          {/* Decision controls */}
          {approval.status === 'pending' && !isExpired && (
            <div className="space-y-2">
              <div className="text-[10px] font-mono uppercase text-slate-500">Review Decision</div>
              <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2}
                placeholder="Optional: justification or rejection reason…"
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#c9b787]/40 resize-none" />
              <div className="flex items-center gap-2">
                <button onClick={() => handleDecide('approved')} disabled={deciding}
                  className="flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border transition-all hover:bg-green-500/10 disabled:opacity-50"
                  style={{ borderColor: '#4ade80', color: '#4ade80', background: 'rgba(74,222,128,0.05)' }}>
                  <CheckCircle2 className="w-3.5 h-3.5" /> Approve Action
                </button>
                <button onClick={() => handleDecide('rejected')} disabled={deciding}
                  className="flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border transition-all hover:bg-red-500/10 disabled:opacity-50"
                  style={{ borderColor: '#e05252', color: '#e05252', background: 'rgba(224,82,82,0.05)' }}>
                  <XCircle className="w-3.5 h-3.5" /> Reject
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ApprovalQueueSentra() {
  useEffect(() => { ensureSeeded(); }, []);
  const store = useSentraStore();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | 'all'>('all');
  const [classFilter, setClassFilter] = useState('all');

  const approvals = store.approvals;
  const filtered = approvals.filter(a => {
    if (statusFilter !== 'all' && a.status !== statusFilter) return false;
    if (classFilter !== 'all' && a.action_class !== classFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.action_description.toLowerCase().includes(q) || a.id.toLowerCase().includes(q) || a.target_asset_name.toLowerCase().includes(q);
    }
    return true;
  }).sort((a, b) => {
    // Pending first
    if (a.status === 'pending' && b.status !== 'pending') return -1;
    if (b.status === 'pending' && a.status !== 'pending') return 1;
    return new Date(b.requested_at).getTime() - new Date(a.requested_at).getTime();
  });

  function handleDecide(id: string, decision: 'approved' | 'rejected', reason?: string) {
    store.decideApproval(id, decision, 'Analyst (Console)', reason);
  }

  const pendingCount = approvals.filter(a => a.status === 'pending').length;
  const approvedCount = approvals.filter(a => a.status === 'approved').length;
  const rejectedCount = approvals.filter(a => a.status === 'rejected').length;
  const uniqueClasses = [...new Set(approvals.map(a => a.action_class))];

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Clock className="w-4 h-4 text-[#c9b787]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Sentra — Approval Queue</span>
        </div>
        <h1 className="text-2xl font-display font-bold text-slate-100">Approval Queue</h1>
        <p className="text-sm text-slate-500 mt-1">Human-in-the-loop review for high-impact defensive actions. Blast radius preview shown before every decision.</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Approvals', value: approvals.length },
          { label: 'Pending', value: pendingCount, color: '#f59e0b' },
          { label: 'Approved', value: approvedCount, color: '#4ade80' },
          { label: 'Rejected', value: rejectedCount, color: '#e05252' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg border p-4" style={{ background: 'rgba(255,255,255,0.025)', borderColor: 'rgba(255,255,255,0.08)' }}>
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">{label}</div>
            <div className="text-2xl font-display font-bold" style={{ color: color ?? '#f5f5f5' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* HITL doctrine notice */}
      {pendingCount > 0 && (
        <div className="rounded-lg border p-3 flex items-start gap-2" style={{ background: 'rgba(245,158,11,0.05)', borderColor: 'rgba(245,158,11,0.2)' }}>
          <AlertTriangle className="w-4 h-4 text-[#f59e0b] flex-shrink-0 mt-0.5" />
          <div className="text-[11px] font-mono text-[#f59e0b]">
            <strong>{pendingCount} approval(s) pending.</strong> High-impact defensive actions require human review before execution.
            Review blast radius preview carefully before approving. All decisions are audit-logged and tamper-evident.
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-40">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search approvals…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#c9b787]/40" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as ApprovalStatus | 'all')}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none">
          <option value="all">All Status</option>
          {Object.keys(STATUS_CONFIG).map(s => <option key={s} value={s}>{STATUS_CONFIG[s as ApprovalStatus].label}</option>)}
        </select>
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none">
          <option value="all">All Action Classes</option>
          {uniqueClasses.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="text-[10px] font-mono text-slate-600">{filtered.length} records</span>
      </div>

      {/* List */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-slate-600 text-sm">No approvals match your filters</div>
        ) : (
          filtered.map(a => <ApprovalCard key={a.id} approval={a} onDecide={handleDecide} />)
        )}
      </div>
    </div>
  );
}
