import { Crown, ExternalLink, Globe, Workflow, Zap } from 'lucide-react';

export const ECOSYSTEM_APPS = [
  {
    href: '/conduit/',
    label: 'Conduit — Reverse ETL',
    description:
      'Visual no-code Reverse ETL — map SZL data to Salesforce, HubSpot, Slack, Sheets, Notion, and more',
    icon: Workflow,
    color: '#22c55e',
  },
  {
    href: '/imperium/',
    label: 'IMPERIUM',
    description:
      'Infrastructure command center — resource orchestration, governance, and security perimeter',
    icon: Crown,
    color: '#d4a054',
  },
  {
    href: '/governance/lexicon',
    label: 'LEXICON — License Intelligence',
    description:
      'Operator-curated license catalog backing the inference governance gate',
    icon: Zap,
    color: '#c9b787',
  },
  {
    href: '/stephen-site/',
    label: 'Stephen Site',
    description: 'Personal portfolio and thought-leadership platform for executive communications',
    icon: Globe,
    color: 'var(--gi-accent-blue)',
  },
];

export function EcosystemAppsGrid() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2
          className="text-xs font-bold tracking-widest uppercase"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Ecosystem Apps
        </h2>
        <span className="text-[10px] font-mono" style={{ color: 'var(--color-fg-muted)' }}>
          {ECOSYSTEM_APPS.length} apps
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {ECOSYSTEM_APPS.map((app) => {
          const Icon = app.icon;
          return (
            <a
              key={app.href}
              href={app.href}
              target="_blank"
              rel="noopener noreferrer"
              className="relative flex flex-col gap-3 p-4 rounded-xl text-left transition-all hover:scale-[1.02] no-underline"
              style={{
                backgroundColor: 'var(--color-surface-base)',
                border: '1px solid var(--color-surface-border)',
              }}
            >
              <div className="flex items-center justify-between">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center"
                  style={{
                    backgroundColor: `color-mix(in srgb, ${app.color} 12%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${app.color} 25%, transparent)`,
                  }}
                >
                  <Icon className="w-4 h-4" style={{ color: app.color }} />
                </div>
                <ExternalLink
                  className="w-3 h-3"
                  style={{ color: 'var(--color-fg-muted)', opacity: 0.5 }}
                />
              </div>
              <div>
                <div
                  className="text-sm font-bold mb-0.5"
                  style={{ color: 'var(--color-fg-primary)' }}
                >
                  {app.label}
                </div>
                <div
                  className="text-[10px] leading-relaxed"
                  style={{ color: 'var(--color-fg-muted)' }}
                >
                  {app.description}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}
