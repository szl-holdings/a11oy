import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Briefcase,
  Building2,
  Scale,
  ShieldAlert,
  Ship,
  User,
  Users,
} from 'lucide-react';
import type { ElementType } from 'react';
import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts';
import type { DomainData } from '../types';

const DOMAIN_ICONS: Record<string, ElementType> = {
  ShieldAlert,
  Ship,
  Briefcase,
  Activity,
  Scale,
  Building2,
  Users,
  User,
};

interface DomainCardProps {
  data: DomainData;
}

export function DomainCard({ data }: DomainCardProps) {
  const Icon = DOMAIN_ICONS[data.icon] ?? Activity;
  const chartData = data.sparkline.map((val, i) => ({ value: val, index: i }));
  const min = Math.min(...data.sparkline);
  const max = Math.max(...data.sparkline);

  const alertColors: Record<string, string> = {
    critical: 'var(--color-critical)',
    high: 'var(--color-high)',
    medium: 'var(--color-medium)',
    low: 'var(--color-low)',
    info: 'var(--color-info)',
  };
  const alertColor = alertColors[data.alerts.severity] ?? 'var(--color-fg-muted)';

  return (
    <a
      href={`${import.meta.env.BASE_URL?.replace(/\/$/, '') || '/a11oy'}/domain/${data.id}`}
      className="block group"
      data-testid={`card-domain-${data.id}`}
    >
      <div
        className="flex flex-col h-full rounded-xl overflow-hidden transition-colors"
        style={{
          backgroundColor: 'var(--color-surface-base)',
          border: '1px solid var(--color-surface-border)',
        }}
      >
        <div className="p-5 flex flex-col gap-4 flex-1">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <Icon className="w-5 h-5" style={{ color: data.color }} />
              <h3 className="font-bold text-sm tracking-wide" style={{ color: data.color }}>
                {data.name}
              </h3>
            </div>
            {data.alerts.count > 0 && (
              <div
                className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded border"
                style={{
                  color: alertColor,
                  borderColor: alertColor,
                  backgroundColor: `color-mix(in srgb, ${alertColor} 10%, transparent)`,
                }}
                data-testid={`badge-alerts-${data.id}`}
              >
                {data.alerts.count} Alert{data.alerts.count > 1 ? 's' : ''}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 mt-1">
            {data.kpis.map((kpi, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span style={{ color: 'var(--color-fg-muted)' }}>{kpi.label}</span>
                <div className="flex items-center gap-1.5 font-mono">
                  <span style={{ color: 'var(--color-fg-primary)' }}>{kpi.value}</span>
                  {kpi.trend === 'up' ? (
                    <ArrowUpRight className="w-3 h-3" style={{ color: 'var(--color-low)' }} />
                  ) : kpi.trend === 'down' ? (
                    <ArrowDownRight
                      className="w-3 h-3"
                      style={{ color: 'var(--color-critical)' }}
                    />
                  ) : (
                    <ArrowRight
                      className="w-3 h-3"
                      style={{ color: 'var(--color-fg-muted)', opacity: 0.5 }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="h-16 w-full"
          style={{
            borderTop: '1px solid var(--color-surface-border)',
            backgroundColor: 'color-mix(in srgb, var(--color-bg-primary) 50%, transparent)',
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 0, left: 0, bottom: 5 }}>
              <YAxis domain={[min - 2, max + 2]} hide />
              <Line
                type="monotone"
                dataKey="value"
                stroke={data.color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </a>
  );
}
