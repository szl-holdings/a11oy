// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useEffect, useState } from 'react';
import {
  CheckCircle2, ChevronDown, ChevronRight, Database, Hash,RefreshCw, Search, ShieldOff, XCircle
} from 'lucide-react';
import { cn } from '@szl-holdings/shared-ui/utils';
import { useSentraStore, ensureSeeded, type AuditEntry } from '@/lib/sentra-store';

function AuditRow({ entry, idx }: { entry: AuditEntry; idx: number }) {
  const [expanded, setExpanded] = useState(false);

  const resultColor = entry.execution_result === 'success' ? '#4ade80' :
    entry.execution_result === 'failure' ? '#e05252' :
    entry.execution_result === 'pending' ? '#f59e0b' : '#8a8a8a';

  return (
    <>
      <tr className={cn('border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors cursor-pointer',
        expanded && 'bg-slate-800/15', entry.policy_decision === 'deny' && 'bg-red-500/5')}
        onClick={() => setExpanded(x => !x)}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
            <span className="text-[10px] font-mono text-slate-500 tabular-nums">{String(idx + 1).padStart(4, '0')}</span>
          </div>
        </td>
        <td className="px-4 py-3 text-[10px] font-mono text-slate-500 whitespace-nowrap">
          {new Date(entry.timestamp).toLocaleString()}
        </td>
        <td className="px-4 py-3 text-[10px] font-mono text-slate-300">{entry.actor}</td>
        <td className="px-4 py-3 text-[10px] font-mono text-[#c9b787] whitespace-nowrap">{entry.action_class}</td>
        <td className="px-4 py-3">
          {entry.policy_decision === 'allow' ? (
            <span className="flex items-center gap-1 text-[9px] font-mono text-green-400"><CheckCircle2 className="w-3 h-3" /> ALLOW</span>
          ) : (
            <span className="flex items-center gap-1 text-[9px] font-mono text-red-400"><ShieldOff className="w-3 h-3" /> DENY</span>
          )}
        </td>
        <td className="px-4 py-3">
          <span className="text-[9px] font-mono" style={{ color: resultColor }}>{entry.execution_result.toUpperCase()}</span>
        </td>
        <td className="px-4 py-3 text-[10px] font-mono text-slate-500">{entry.target_asset_id ?? '—'}</td>
        <td className="px-4 py-3">
          <span className="text-[10px] font-mono text-slate-700" title={entry.entry_hash}>
            {entry.entry_hash.substring(0, 10)}…
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/60">
          <td colSpan={8} className="px-6 py-4 border-b border-slate-800">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[11px]">
              <div className="space-y-1">
                <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Audit Entry Details</div>
                {[
                  ['ID', entry.id],
                  ['Timestamp', new Date(entry.timestamp).toISOString()],
                  ['Actor', entry.actor],
                  ['Action', entry.action],
                  ['Action Class', entry.action_class],
                  ['Target Asset', entry.target_asset_id ?? '—'],
                  ['Integration', entry.integration_id ?? '—'],
                  ['Approval ID', entry.approval_id ?? '—'],
                  ['Rollback Ref', entry.rollback_reference ?? '—'],
                  ['Notes', entry.notes || '—'],
                ].map(([label, value]) => (
                  <div key={label} className="flex gap-2">
                    <span className="text-slate-500 w-28 flex-shrink-0">{label}</span>
                    <span className="text-slate-300 font-mono break-all">{value}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Tamper-Evident Hash Chain</div>
                <div className="p-3 rounded-md bg-slate-800/60 border border-slate-700/50 space-y-2">
                  <div>
                    <div className="text-[9px] font-mono text-slate-500 mb-0.5">PREVIOUS HASH (← prev entry)</div>
                    <div className="text-[10px] font-mono text-slate-400 break-all">{entry.prev_hash}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono text-slate-500 mb-0.5 flex items-center gap-1">
                      <Hash className="w-2.5 h-2.5" /> THIS ENTRY HASH
                    </div>
                    <div className="text-[10px] font-mono text-[#c9b787] break-all">{entry.entry_hash}</div>
                  </div>
                  {entry.evidence_hash && (
                    <div>
                      <div className="text-[9px] font-mono text-slate-500 mb-0.5">EVIDENCE SHA-256</div>
                      <div className="text-[10px] font-mono text-[#60a5fa] break-all">{entry.evidence_hash}</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AuditTrailV2() {
  useEffect(() => { ensureSeeded(); }, []);
  const store = useSentraStore();

  const [search, setSearch] = useState('');
  const [policyFilter, setPolicyFilter] = useState<'all' | 'allow' | 'deny'>('all');
  const [resultFilter, setResultFilter] = useState<'all' | 'success' | 'failure' | 'pending'>('all');
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; checked: number; firstInvalidId?: string } | null>(null);
  const [verifying, setVerifying] = useState(false);

  const entries = [...store.auditEntries].reverse();
  const filtered = entries.filter(e => {
    if (policyFilter !== 'all' && e.policy_decision !== policyFilter) return false;
    if (resultFilter !== 'all' && e.execution_result !== resultFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return e.actor.toLowerCase().includes(q) || e.action.toLowerCase().includes(q) || (e.target_asset_id ?? '').toLowerCase().includes(q);
    }
    return true;
  });

  async function handleVerify() {
    setVerifying(true);
    await new Promise(r => setTimeout(r, 600));
    const result = store.verifyAuditChain();
    setVerifyResult(result);
    setVerifying(false);
    setTimeout(() => setVerifyResult(null), 8000);
  }

  const denyCount = store.auditEntries.filter(e => e.policy_decision === 'deny').length;
  const evidenceCount = store.auditEntries.filter(e => e.evidence_hash).length;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Database className="w-4 h-4 text-[#c9b787]" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Sentra — Audit Trail</span>
        </div>
        <h1 className="text-2xl font-display font-bold text-slate-100">Tamper-Evident Audit Trail</h1>
        <p className="text-sm text-slate-500 mt-1">
          Hash-chained audit log covering every action, policy decision, approval, and evidence event. Verify integrity anytime.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Entries', value: store.auditEntries.length },
          { label: 'Policy Denials', value: denyCount, color: '#e05252' },
          { label: 'Evidence Linked', value: evidenceCount, color: '#c9b787' },
          { label: 'Chain Status', value: 'ACTIVE', color: '#4ade80' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg border p-4" style={{ background: 'rgba(255,255,255,0.025)', borderColor: 'rgba(255,255,255,0.08)' }}>
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1">{label}</div>
            <div className="text-2xl font-display font-bold" style={{ color: color ?? '#f5f5f5' }}>{value}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={handleVerify} disabled={verifying}
          className="flex items-center gap-1.5 px-4 py-2 rounded text-[10px] font-mono font-bold border transition-all disabled:opacity-50"
          style={{ borderColor: '#4ade80', color: '#4ade80', background: 'rgba(74,222,128,0.05)' }}>
          {verifying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Hash className="w-3.5 h-3.5" />}
          {verifying ? 'Verifying chain…' : `Verify Hash Chain (${store.auditEntries.length} entries)`}
        </button>
        {verifyResult && (
          <div className={cn('flex items-center gap-2 text-[10px] font-mono px-3 py-2 rounded border',
            verifyResult.valid ? 'text-green-400 border-green-500/20 bg-green-500/05' : 'text-red-400 border-red-500/20 bg-red-500/05')}>
            {verifyResult.valid ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
            {verifyResult.valid
              ? `✓ Chain intact — all ${verifyResult.checkedEntries} entries verified`
              : `✗ Chain BROKEN at entry ${verifyResult.firstInvalidId ?? 'unknown'}`}
          </div>
        )}
      </div>

      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-40">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search audit log…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#c9b787]/40" />
        </div>
        <select value={policyFilter} onChange={e => setPolicyFilter(e.target.value as 'all' | 'allow' | 'deny')}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none">
          <option value="all">All Policy Decisions</option>
          <option value="allow">Allow</option>
          <option value="deny">Deny</option>
        </select>
        <select value={resultFilter} onChange={e => setResultFilter(e.target.value as 'all' | 'success' | 'failure' | 'pending')}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-2 text-xs text-slate-400 outline-none">
          <option value="all">All Results</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
          <option value="pending">Pending</option>
        </select>
        <span className="text-[10px] font-mono text-slate-600">{filtered.length} of {store.auditEntries.length} entries</span>
      </div>

      <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-800/50 border-b border-slate-700/50 text-[10px] font-mono uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">Timestamp</th>
                <th className="px-4 py-3 font-medium">Actor</th>
                <th className="px-4 py-3 font-medium">Action Class</th>
                <th className="px-4 py-3 font-medium">Policy</th>
                <th className="px-4 py-3 font-medium">Result</th>
                <th className="px-4 py-3 font-medium">Target</th>
                <th className="px-4 py-3 font-medium">Entry Hash</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 200).map((entry, i) => (
                <AuditRow key={entry.id} entry={entry} idx={store.auditEntries.length - 1 - i} />
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 border-t border-slate-800 text-[10px] text-slate-600 font-mono flex items-center justify-between">
          <span>Showing {Math.min(filtered.length, 200)} of {filtered.length} entries · Click row to expand hash chain</span>
          {filtered.length > 200 && <span className="text-[#c9b787]">Showing first 200 — use filters</span>}
        </div>
      </div>
    </div>
  );
}
