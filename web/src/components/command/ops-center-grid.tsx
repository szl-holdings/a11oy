import {
  AlertTriangle,
  BarChart2,
  Bell,
  DollarSign,
  GitCommit,
  Rocket,
  Shield,
  Target,
  Users,
  Zap,
} from 'lucide-react';
import { useLocation } from 'wouter';
import { useOpsBadgeCounts } from '../../hooks/use-ops-badge-counts';

type BadgeKey = 'alerts' | 'slaBreaches' | 'governancePending' | 'costOverBudget';

interface OpsItem {
  path: string;
  label: string;
  description: string;
  icon: typeof Bell;
  color: string;
  badge?: number;
  badgeKey?: BadgeKey;
  badgeLabel?: string;
  badgeColor?: string;
}

const OPS_ITEMS: OpsItem[] = [
  {
    path: '/alerts',
    label: 'Alert Inbox',
    description: 'Unified alert inbox with priority ranking, snooze, acknowledge & escalate',
    icon: Bell,
    color: '#ef4444',
    badgeKey: 'alerts',
    badgeLabel: 'active',
  },
  {
    path: '/team',
    label: 'Team & Users',
    description: 'User directory, role-based access, team grouping, SSO configuration',
    icon: Users,
    color: '#8b7ac8',
  },
  {
    path: '/costs',
    label: 'Cost Analytics',
    description: 'Resource consumption, API volumes, budget allocation, overage alerts',
    icon: DollarSign,
    color: '#22c55e',
    badgeKey: 'costOverBudget',
    badgeLabel: 'over budget',
    badgeColor: 'var(--color-high)',
  },
  {
    path: '/changelog',
    label: 'Release Feed',
    description: 'Auto-generated change log for all apps — deployments, features, fixes',
    icon: GitCommit,
    color: 'var(--gi-accent-blue)',
  },
  {
    path: '/operations/deployments',
    label: 'Deployments',
    description: 'Active versions per app, full deployment history, guarded rollback controls',
    icon: Rocket,
    color: '#8b7ac8',
  },
  {
    path: '/sla',
    label: 'SLA Dashboard',
    description: 'Cross-domain SLA compliance tracking with breach alerting',
    icon: Target,
    color: '#f97316',
    badgeKey: 'slaBreaches',
    badgeLabel: 'breaching',
    badgeColor: 'var(--color-critical)',
  },
  {
    path: '/governance',
    label: 'Governance',
    description: 'Policy creation, approval chains, enforcement tracking, audit trail',
    icon: Shield,
    color: '#a855f7',
    badgeKey: 'governancePending',
    badgeLabel: 'needs approval',
    badgeColor: 'var(--color-medium)',
  },
  {
    path: '/health',
    label: 'Health Score',
    description: 'Composite ecosystem health score with dimension breakdown',
    icon: BarChart2,
    color: '#8b7ac8',
  },
  {
    path: '/digest',
    label: 'Daily Digest',
    description: 'AI-personalized briefing with role-aware prioritization and quick actions',
    icon: Zap,
    color: '#f59e0b',
  },
];

export function OpsCenterGrid() {
  const [, navigate] = useLocation();
  const counts = useOpsBadgeCounts();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2
          className="text-xs font-bold tracking-widest uppercase"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Ops Center
        </h2>
        <span className="text-[10px] font-mono" style={{ color: 'var(--color-fg-muted)' }}>
          8 workspaces
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {OPS_ITEMS.map((item) => {
          const Icon = item.icon;
          const liveBadge = item.badgeKey ? counts[item.badgeKey] : null;
          const badgeValue = typeof liveBadge === 'number' ? liveBadge : item.badge;
          const showBadge = typeof badgeValue === 'number' && badgeValue > 0;
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className="relative flex flex-col gap-3 p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
              style={{
                backgroundColor: 'var(--color-surface-base)',
                border: '1px solid var(--color-surface-border)',
              }}
            >
              {showBadge && (
                <div
                  className="absolute top-3 right-3 flex items-center gap-1 px-1.5 py-0.5 rounded-full"
                  style={{
                    backgroundColor: `color-mix(in srgb, ${item.badgeColor ?? 'var(--color-critical)'} 15%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${item.badgeColor ?? 'var(--color-critical)'} 30%, transparent)`,
                  }}
                >
                  <AlertTriangle
                    className="w-2.5 h-2.5"
                    style={{ color: item.badgeColor ?? 'var(--color-critical)' }}
                  />
                  <span
                    className="text-[9px] font-bold"
                    style={{ color: item.badgeColor ?? 'var(--color-critical)' }}
                  >
                    {badgeValue} {item.badgeLabel}
                  </span>
                </div>
              )}
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{
                  backgroundColor: `color-mix(in srgb, ${item.color} 12%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${item.color} 25%, transparent)`,
                }}
              >
                <Icon className="w-4 h-4" style={{ color: item.color }} />
              </div>
              <div>
                <div
                  className="text-sm font-bold mb-0.5"
                  style={{ color: 'var(--color-fg-primary)' }}
                >
                  {item.label}
                </div>
                <div
                  className="text-[10px] leading-relaxed"
                  style={{ color: 'var(--color-fg-muted)' }}
                >
                  {item.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
