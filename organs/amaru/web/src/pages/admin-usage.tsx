import React from 'react';
import { useAdminUsage, useOrgQuotaViolations } from '@/lib/api-hooks';
import { Badge, Input } from '@/components/ui';
import { formatDate } from '@/lib/utils';
import { AlertTriangle, BellRing, ChevronDown, ChevronRight } from 'lucide-react';

function overageBadge(state: 'none' | 'warn' | 'over') {
  if (state === 'over') return <Badge variant="error">Over</Badge>;
  if (state === 'warn') return <Badge variant="partial">Warn</Badge>;
  return <span className="text-[#666] text-xs font-mono">—</span>;
}

function AlertSentBadge({
  lastAlertSentAt,
  alertThresholdsFired,
}: {
  lastAlertSentAt: string | null;
  alertThresholdsFired: { meterKey: string; threshold: number; notifiedAt: string }[];
}) {
  if (!lastAlertSentAt) {
    return <span className="text-[#666] text-xs font-mono">No alerts</span>;
  }

  const thresholds = Array.from(new Set(alertThresholdsFired.map((a) => a.threshold))).sort(
    (a, b) => b - a,
  );
  const visibleThresholds = thresholds.filter((t) => t >= 80);
  const labelThresholds = visibleThresholds.length > 0 ? visibleThresholds : thresholds;

  const tooltip = alertThresholdsFired
    .map((a) => `${a.threshold}% on ${a.meterKey} — ${formatDate(a.notifiedAt)}`)
    .join('\n');

  return (
    <div
      className="flex flex-col gap-1"
      title={tooltip}
    >
      <div className="inline-flex items-center gap-1.5 text-xs">
        <BellRing className="w-3.5 h-3.5 text-[#d4a853]" aria-hidden="true" />
        <span className="font-mono text-[#d4a853]">Alert sent</span>
      </div>
      <div className="text-[11px] font-mono text-[#8a8a8a]">
        {labelThresholds.map((t) => `${t}%`).join(' · ')} · {formatDate(lastAlertSentAt)}
      </div>
    </div>
  );
}

function QuotaViolationsPanel({ orgId }: { orgId: number }) {
  const { data, isLoading, error } = useOrgQuotaViolations(orgId, { limit: 50 });

  if (isLoading) {
    return (
      <div className="px-4 py-4 text-xs text-[#8a8a8a] font-mono">Loading violations…</div>
    );
  }

  if (error) {
    return (
      <div className="px-4 py-4 text-xs text-[#b85450] font-mono">
        Failed to load violations: {(error as Error).message}
      </div>
    );
  }

  if (!data || data.rows.length === 0) {
    return (
      <div className="px-4 py-4 text-xs text-[#8a8a8a] font-mono">
        No quota violations recorded for this tenant.
      </div>
    );
  }

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[11px] uppercase tracking-widest text-[#8a8a8a] font-medium">
          Quota Violations
        </h4>
        <span className="text-[11px] font-mono text-[#666]">
          {data.rows.length} of {data.pagination.total}
        </span>
      </div>
      <div className="border border-[rgba(255,255,255,0.06)] rounded">
        <table className="w-full text-xs">
          <thead className="bg-[#0c0c0c] text-[10px] uppercase tracking-widest text-[#666]">
            <tr>
              <th className="text-left px-3 py-2 font-medium">When</th>
              <th className="text-left px-3 py-2 font-medium">Type</th>
              <th className="text-left px-3 py-2 font-medium">Feature</th>
              <th className="text-right px-3 py-2 font-medium">Usage</th>
              <th className="text-right px-3 py-2 font-medium">Limit</th>
              <th className="text-left px-3 py-2 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((v) => (
              <tr key={v.id} className="border-t border-[rgba(255,255,255,0.04)]">
                <td className="px-3 py-2 font-mono text-[#c9c9c9] whitespace-nowrap">
                  {formatDate(v.occurredAt)}
                </td>
                <td className="px-3 py-2">
                  {v.violationType === 'hard' ? (
                    <Badge variant="error">Hard</Badge>
                  ) : (
                    <Badge variant="partial">Soft</Badge>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-[#f5f5f5]">{v.featureKey}</td>
                <td className="px-3 py-2 text-right font-mono text-[#f5f5f5]">
                  {v.currentUsage != null ? v.currentUsage.toLocaleString() : '—'}
                </td>
                <td className="px-3 py-2 text-right font-mono text-[#c9b787]">
                  {v.limitValue != null ? v.limitValue.toLocaleString() : '—'}
                </td>
                <td className="px-3 py-2 font-mono text-[#8a8a8a]">{v.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function AdminUsagePage() {
  const [orgSearch, setOrgSearch] = React.useState('');
  const [plan, setPlan] = React.useState<string>('');
  const [expandedOrg, setExpandedOrg] = React.useState<number | null>(null);

  const { data, isLoading, error } = useAdminUsage({
    org: orgSearch || undefined,
    plan: plan || undefined,
    limit: 100,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold tracking-tight text-[#f5f5f5]">
            Admin · Cross-Tenant Usage
          </h1>
          <p className="text-sm text-[#8a8a8a] mt-1">
            Per-org usage, quota status, and overage alert history for the current billing period.
          </p>
        </div>
        {data?.totals ? (
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-[#8a8a8a]">
              Orgs: <span className="text-[#f5f5f5]">{data.totals.orgs}</span>
            </span>
            <span className="text-[#8a8a8a]">
              Over: <span className="text-[#b85450]">{data.totals.overageCount}</span>
            </span>
            <span className="text-[#8a8a8a]">
              Warn: <span className="text-[#d4a853]">{data.totals.warnCount}</span>
            </span>
          </div>
        ) : null}
      </div>

      <div className="flex gap-3">
        <Input
          placeholder="Filter by org name or slug…"
          value={orgSearch}
          onChange={(e) => setOrgSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          value={plan}
          onChange={(e) => setPlan(e.target.value)}
          className="h-9 rounded-md border border-input bg-transparent px-3 text-sm text-[#f5f5f5]"
        >
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="starter">Starter</option>
          <option value="professional">Professional</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>

      {error ? (
        <div className="flex items-center gap-2 p-4 rounded-md border border-[#b85450]/30 bg-[#b85450]/5 text-sm text-[#b85450]">
          <AlertTriangle className="w-4 h-4" />
          Failed to load usage data: {(error as Error).message}
        </div>
      ) : null}

      <div className="border border-[rgba(255,255,255,0.06)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#111] text-[11px] uppercase tracking-widest text-[#8a8a8a]">
            <tr>
              <th className="w-8 px-2 py-3" />
              <th className="text-left px-4 py-3 font-medium">Org</th>
              <th className="text-left px-4 py-3 font-medium">Plan</th>
              <th className="text-right px-4 py-3 font-medium">API calls</th>
              <th className="text-right px-4 py-3 font-medium">Members</th>
              <th className="text-right px-4 py-3 font-medium">Storage (MB)</th>
              <th className="text-left px-4 py-3 font-medium">Overage</th>
              <th className="text-left px-4 py-3 font-medium">Alert status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} className="text-center py-8 text-[#8a8a8a] text-xs">
                  Loading…
                </td>
              </tr>
            ) : data?.rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-8 text-[#8a8a8a] text-xs">
                  No orgs match the current filters.
                </td>
              </tr>
            ) : (
              data?.rows.map((row) => {
                const isExpanded = expandedOrg === row.orgId;
                return (
                  <React.Fragment key={row.orgId}>
                    <tr
                      className="border-t border-[rgba(255,255,255,0.04)] hover:bg-[#111] cursor-pointer"
                      onClick={() => setExpandedOrg(isExpanded ? null : row.orgId)}
                    >
                      <td className="px-2 py-3 text-[#8a8a8a]">
                        <button
                          type="button"
                          aria-label={isExpanded ? 'Hide quota violations' : 'Show quota violations'}
                          aria-expanded={isExpanded}
                          className="flex items-center justify-center w-6 h-6 rounded hover:bg-[rgba(255,255,255,0.06)]"
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedOrg(isExpanded ? null : row.orgId);
                          }}
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-[#f5f5f5]">{row.orgName}</div>
                        <div className="text-[11px] font-mono text-[#666]">{row.orgSlug}</div>
                      </td>
                      <td className="px-4 py-3 text-[#c9b787] text-xs font-mono uppercase">{row.plan}</td>
                      <td className="px-4 py-3 text-right font-mono text-[#f5f5f5]">
                        {row.apiCalls.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[#f5f5f5]">{row.members}</td>
                      <td className="px-4 py-3 text-right font-mono text-[#f5f5f5]">
                        {row.storageMB.toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {overageBadge(row.overages.apiCalls)}
                          {overageBadge(row.overages.members)}
                          {overageBadge(row.overages.storage)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <AlertSentBadge
                          lastAlertSentAt={row.lastAlertSentAt}
                          alertThresholdsFired={row.alertThresholdsFired}
                        />
                      </td>
                    </tr>
                    {isExpanded ? (
                      <tr className="bg-[#0a0a0a] border-t border-[rgba(255,255,255,0.04)]">
                        <td colSpan={8} className="p-0">
                          <QuotaViolationsPanel orgId={row.orgId} />
                        </td>
                      </tr>
                    ) : null}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
