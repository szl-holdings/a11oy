import { useEffect } from 'react';
import { Link } from 'wouter';
import {
  Activity, CheckCircle2, Clock, FileText, Flame, FolderLock,
  Lock, Server, ShieldAlert, ShieldCheck, ShieldOff, TrendingUp, XCircle, Zap
} from 'lucide-react';
import { useSentraStore, ensureSeeded, type IncidentStatus, type IncidentSeverity } from '@/lib/sentra-store';

const SENTRA_BRAND = {
  gold: '#c9b787',
  red: '#e05252',
  green: '#4ade80',
  amber: '#f59e0b',
  blue: '#60a5fa',
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.08)',
};

const SEV_COLOR: Record<IncidentSeverity, string> = {
  critical: SENTRA_BRAND.red,
  high: SENTRA_BRAND.amber,
  medium: SENTRA_BRAND.gold,
  low: SENTRA_BRAND.blue,
};

const STATUS_LABEL: Record<IncidentStatus, string> = {
  new: 'NEW',
  triage: 'TRIAGE',
  investigating: 'INVESTIGATING',
  approval_pending: 'APPROVAL PENDING',
  containment_in_progress: 'CONTAINMENT',
  contained: 'CONTAINED',
  recovery: 'RECOVERY',
  reporting: 'REPORTING',
  closed: 'CLOSED',
};

function MetricCard({ label, value, sub, color, icon: Icon, to }: {
  label: string; value: number | string; sub?: string; color?: string; icon?: typeof ShieldAlert; to?: string;
}) {
  const content = (
    <div className="rounded-lg p-4 border flex flex-col gap-2 transition-all hover:border-[#c9b787]/30"
      style={{ background: SENTRA_BRAND.surface, borderColor: SENTRA_BRAND.border }}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</span>
        {Icon && <Icon className="w-3.5 h-3.5" style={{ color: color ?? SENTRA_BRAND.gold }} />}
      </div>
      <div className="font-display text-3xl font-bold" style={{ color: color ?? '#f5f5f5' }}>{value}</div>
      {sub && <div className="text-[10px] text-slate-600 font-mono">{sub}</div>}
    </div>
  );
  return to ? <Link href={to}>{content}</Link> : content;
}

function SeverityBar({ items, total }: { items: { sev: IncidentSeverity; count: number }[]; total: number }) {
  return (
    <div className="flex rounded overflow-hidden h-2 gap-px">
      {items.map(({ sev, count }) => (
        <div key={sev} className="h-full transition-all" style={{ width: `${(count / total) * 100}%`, background: SEV_COLOR[sev] }} title={`${sev}: ${count}`} />
      ))}
    </div>
  );
}

function IncidentRow({ inc }: { inc: ReturnType<typeof useSentraStore>['incidents'][0] }) {
  const statusColors: Record<IncidentStatus, string> = {
    new: '#f59e0b', triage: '#f59e0b', investigating: '#60a5fa',
    approval_pending: '#c9b787', containment_in_progress: '#e05252',
    contained: '#4ade80', recovery: '#c9b787', reporting: '#8a8a8a', closed: '#4a5568',
  };
  return (
    <Link href={`/incidents/${inc.id}`}>
      <div className="flex items-center gap-4 px-4 py-3 border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors cursor-pointer">
        <div className="w-1.5 h-10 rounded-full flex-shrink-0" style={{ background: SEV_COLOR[inc.severity] }} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-slate-200 truncate">{inc.title}</div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-mono text-slate-500">{inc.id}</span>
            <span className="text-[10px] text-slate-600">·</span>
            <span className="text-[10px] font-mono" style={{ color: SEV_COLOR[inc.severity] }}>{inc.severity.toUpperCase()}</span>
            {inc.affected_assets[0] && (
              <>
                <span className="text-[10px] text-slate-600">·</span>
                <span className="text-[10px] font-mono text-slate-500">{inc.affected_assets[0].asset_name}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <span className="px-2 py-0.5 rounded text-[9px] font-mono font-bold border"
            style={{ color: statusColors[inc.status], borderColor: `${statusColors[inc.status]}40`, background: `${statusColors[inc.status]}10` }}>
            {STATUS_LABEL[inc.status]}
          </span>
          <span className="text-[10px] text-slate-600 font-mono">{inc.assigned_analyst}</span>
        </div>
      </div>
    </Link>
  );
}

function SessionDigestPanel() {
  const store = useSentraStore();
  const last10 = [...store.sessionDigest].reverse().slice(0, 8);
  if (last10.length === 0) return null;

  const typeIcon: Record<string, typeof CheckCircle2> = {
    approval: CheckCircle2, evidence: FolderLock, report: FileText, denial: XCircle, containment: Lock,
  };
  const typeColor: Record<string, string> = {
    approval: SENTRA_BRAND.green, evidence: SENTRA_BRAND.gold, report: SENTRA_BRAND.blue, denial: SENTRA_BRAND.red, containment: SENTRA_BRAND.amber,
  };

  return (
    <div className="rounded-lg border p-4" style={{ background: SENTRA_BRAND.surface, borderColor: SENTRA_BRAND.border }}>
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-3.5 h-3.5 text-[#c9b787]" />
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">Session Digest — This Session</span>
      </div>
      <div className="space-y-2">
        {last10.map((entry, i) => {
          const Icon = typeIcon[entry.type] ?? Activity;
          return (
            <div key={i} className="flex items-start gap-2 text-xs">
              <Icon className="w-3 h-3 mt-0.5 flex-shrink-0" style={{ color: typeColor[entry.type] }} />
              <span className="text-slate-300 flex-1 min-w-0">{entry.description}</span>
              <span className="text-slate-600 font-mono text-[10px] flex-shrink-0">{entry.actor}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function CommandCenter() {
  useEffect(() => { ensureSeeded(); }, []);
  const store = useSentraStore();

  const incidents = store.incidents;
  const assets = store.assets;
  const approvals = store.approvals;
  const evidence = store.evidence;

  const activeIncidents = incidents.filter(i => !['closed', 'reporting'].includes(i.status));
  const criticalOpen = incidents.filter(i => i.severity === 'critical' && !['closed'].includes(i.status));
  const pendingApprovals = approvals.filter(a => a.status === 'pending');
  const lockedEvidence = evidence.filter(e => e.locked);
  const ownedAssets = assets.filter(a => ['owned', 'authorized', 'contracted_scope', 'lab'].includes(a.ownership_status));
  const compromisedAssets = assets.filter(a => a.status === 'compromised' || a.status === 'isolated');

  const bySev = (['critical', 'high', 'medium', 'low'] as IncidentSeverity[]).map(sev => ({
    sev, count: activeIncidents.filter(i => i.severity === sev).length,
  })).filter(x => x.count > 0);

  const byStatus = Object.entries(
    activeIncidents.reduce((acc, i) => { acc[i.status] = (acc[i.status] ?? 0) + 1; return acc; }, {} as Record<string, number>)
  ).sort((a, b) => b[1] - a[1]).slice(0, 6);

  const recentIncidents = [...incidents].sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()).slice(0, 8);
  const recentDenials = store.policyLogs.filter(p => p.policy_result === 'deny').slice(-5).reverse();

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-4 h-4 text-[#c9b787]" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">Sentra — Cyber Resilience Command</span>
            <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-green-500/10 text-green-400 border border-green-500/20">
              DEFENSIVE ONLY
            </span>
          </div>
          <h1 className="text-2xl font-display font-bold text-slate-100">Security Operations Command</h1>
          <p className="text-sm text-slate-500 mt-1">Full-loop incident detection, containment, evidence, and reporting. Defensive doctrine enforced.</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-600">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          LIVE · {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard label="Active Incidents" value={activeIncidents.length} sub={`${criticalOpen.length} critical`} color={criticalOpen.length > 0 ? SENTRA_BRAND.red : '#f5f5f5'} icon={ShieldAlert} to="/incidents" />
        <MetricCard label="Pending Approvals" value={pendingApprovals.length} sub="awaiting decision" color={pendingApprovals.length > 0 ? SENTRA_BRAND.amber : '#f5f5f5'} icon={Clock} to="/approval-queue" />
        <MetricCard label="Owned Assets" value={ownedAssets.length} sub={`${compromisedAssets.length} affected`} icon={Server} to="/asset-registry" />
        <MetricCard label="Evidence Items" value={evidence.length} sub={`${lockedEvidence.length} locked`} icon={FolderLock} to="/evidence-vault" />
        <MetricCard label="Audit Entries" value={store.auditEntries.length} sub="tamper-evident" icon={FileText} to="/audit-trail" />
        <MetricCard label="Policy Denials" value={store.policyLogs.filter(p => p.policy_result === 'deny').length} sub="blocked actions" color={SENTRA_BRAND.red} icon={ShieldOff} to="/policy-log" />
      </div>

      {/* Incident breakdown + Session digest */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Active incident breakdown */}
        <div className="lg:col-span-2 rounded-lg border p-4" style={{ background: SENTRA_BRAND.surface, borderColor: SENTRA_BRAND.border }}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">Active Incident Breakdown</span>
            <span className="text-[10px] font-mono text-slate-600">{activeIncidents.length} total</span>
          </div>
          {activeIncidents.length > 0 ? (
            <>
              <SeverityBar items={bySev} total={activeIncidents.length} />
              <div className="flex gap-3 mt-3 flex-wrap">
                {bySev.map(({ sev, count }) => (
                  <div key={sev} className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full" style={{ background: SEV_COLOR[sev] }} />
                    <span className="text-[10px] font-mono text-slate-400">{sev.toUpperCase()}</span>
                    <span className="text-[10px] font-mono font-bold" style={{ color: SEV_COLOR[sev] }}>{count}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {byStatus.map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between px-3 py-2 rounded-md bg-slate-800/40 border border-slate-700/40">
                    <span className="text-[10px] font-mono text-slate-400">{STATUS_LABEL[status as IncidentStatus] ?? status}</span>
                    <span className="text-[10px] font-mono font-bold text-slate-200">{count}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-600 py-4">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              No active incidents
            </div>
          )}
        </div>

        {/* Session digest */}
        <SessionDigestPanel />
      </div>

      {/* Recent incidents */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: SENTRA_BRAND.border }}>
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ background: 'rgba(255,255,255,0.015)', borderColor: SENTRA_BRAND.border }}>
          <div className="flex items-center gap-2">
            <Flame className="w-3.5 h-3.5 text-[#c9b787]" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">Recent Incidents</span>
          </div>
          <Link href="/incidents">
            <span className="text-[10px] font-mono text-slate-500 hover:text-[#c9b787] transition-colors cursor-pointer">View All →</span>
          </Link>
        </div>
        <div>
          {recentIncidents.map(inc => <IncidentRow key={inc.id} inc={inc} />)}
        </div>
      </div>

      {/* Bottom row: Quick actions + Policy denials */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Quick actions */}
        <div className="rounded-lg border p-4" style={{ background: SENTRA_BRAND.surface, borderColor: SENTRA_BRAND.border }}>
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-3.5 h-3.5 text-[#c9b787]" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">Quick Actions</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Approval Queue', icon: Clock, href: '/approval-queue', count: pendingApprovals.length },
              { label: 'Evidence Vault', icon: FolderLock, href: '/evidence-vault', count: evidence.length },
              { label: 'Asset Registry', icon: Server, href: '/asset-registry', count: ownedAssets.length },
              { label: 'Reports', icon: FileText, href: '/reports-generator', count: store.reports.length },
              { label: 'Containment', icon: Lock, href: '/containment-actions', count: undefined },
              { label: 'Integrations', icon: Activity, href: '/integrations-hub', count: undefined },
              { label: 'Policy Log', icon: ShieldOff, href: '/policy-log', count: store.policyLogs.length },
              { label: 'Audit Trail', icon: TrendingUp, href: '/audit-trail', count: store.auditEntries.length },
            ].map(({ label, icon: Icon, href, count }) => (
              <Link key={href} href={href}>
                <div className="flex items-center justify-between px-3 py-2.5 rounded-md border cursor-pointer transition-all hover:border-[#c9b787]/30 hover:bg-slate-800/40"
                  style={{ borderColor: SENTRA_BRAND.border }}>
                  <div className="flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5 text-[#c9b787]" />
                    <span className="text-xs text-slate-300">{label}</span>
                  </div>
                  {count !== undefined && (
                    <span className="text-[10px] font-mono text-slate-500">{count}</span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Policy denials */}
        <div className="rounded-lg border p-4" style={{ background: SENTRA_BRAND.surface, borderColor: SENTRA_BRAND.border }}>
          <div className="flex items-center gap-2 mb-4">
            <ShieldOff className="w-3.5 h-3.5 text-[#e05252]" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">Recent Policy Denials</span>
          </div>
          {recentDenials.length === 0 ? (
            <div className="text-xs text-slate-600 py-4 text-center">No policy denials in this session</div>
          ) : (
            <div className="space-y-2">
              {recentDenials.map(d => (
                <div key={d.id} className="flex items-start gap-2 p-2 rounded-md bg-red-500/5 border border-red-500/10">
                  <XCircle className="w-3 h-3 text-[#e05252] mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-slate-300 font-mono">{d.action_class}</div>
                    <div className="text-[10px] text-slate-500 truncate">{d.reason.substring(0, 80)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Doctrine footer */}
      <div className="rounded-lg border px-4 py-3 flex items-start gap-3" style={{ background: 'rgba(201,183,135,0.04)', borderColor: 'rgba(201,183,135,0.15)' }}>
        <ShieldCheck className="w-4 h-4 text-[#c9b787] mt-0.5 flex-shrink-0" />
        <div className="text-[10px] font-mono text-slate-500 leading-relaxed">
          <span className="text-[#c9b787] font-bold">DEFENSIVE DOCTRINE ENFORCED — </span>
          Sentra executes containment, revocation, rotation, and evidence operations exclusively on tenant-owned, authorized, or contracted-scope assets.
          All offensive, retaliatory, and attacker-side actions are denied by policy. Doctrine citations: NIST SP 800-61r2, NIST CSF 2.0,
          CISA CIRCIA, MITRE D3FEND, NSA Cybersecurity Directorate, FBI IC3, NCSC ACD.
        </div>
      </div>
    </div>
  );
}
