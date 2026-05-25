import {
  Activity,
  ChevronDown,
  ChevronRight,
  Minus,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const BG = { surface: 'var(--gi-bg-surface)', elevated: 'var(--gi-bg-raised)' };
const BORDER = { subtle: 'rgba(255,255,255,0.04)', muted: 'rgba(255,255,255,0.07)' };
const TEXT = {
  primary: 'rgba(255,255,255,0.88)',
  secondary: 'rgba(255,255,255,0.55)',
  tertiary: 'rgba(255,255,255,0.28)',
  muted: 'rgba(255,255,255,0.14)',
};

export interface SimulationScenario {
  id: string;
  label: string;
  color: string;
  outputMetric: string;
  outputUnit: string;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  mean: number;
  stdDev: number;
  confidence: number;
}

export interface SensitivityDriver {
  input: string;
  lowValue: number;
  highValue: number;
  baseOutput: number;
  lowOutput: number;
  highOutput: number;
  unit: string;
}

export interface MonteCarloSimPanelProps {
  scenarios: SimulationScenario[];
  sensitivityDrivers: SensitivityDriver[];
  iterations: number;
  compact?: boolean;
}

function formatValue(v: number, unit: string): string {
  if (unit === '$' || unit === 'USD') {
    if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  }
  if (unit === '%') return `${v.toFixed(1)}%`;
  return v.toFixed(1);
}

function DistributionChart({ scenario }: { scenario: SimulationScenario }) {
  const bins = 30;
  const range = scenario.p95 - scenario.p5;
  const binWidth = range / bins;
  const data = Array.from({ length: bins }, (_, i) => {
    const x = scenario.p5 + i * binWidth;
    const z = (x - scenario.mean) / scenario.stdDev;
    const density = Math.exp(-0.5 * z * z) / (scenario.stdDev * Math.sqrt(2 * Math.PI));
    return {
      x: Math.round(x),
      density: density * 1000,
      label: formatValue(x, scenario.outputUnit),
    };
  });

  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
          <defs>
            <linearGradient id={`grad-${scenario.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={scenario.color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={scenario.color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="density"
            stroke={scenario.color}
            fill={`url(#grad-${scenario.id})`}
            strokeWidth={1.5}
          />
          <ReferenceLine
            x={data.reduce(
              (closest, d, i) =>
                Math.abs(d.x - scenario.p50) < Math.abs(data[closest].x - scenario.p50)
                  ? i
                  : closest,
              0,
            )}
            stroke={scenario.color}
            strokeDasharray="3 3"
            strokeOpacity={0.6}
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 8, fill: TEXT.muted }}
            interval={Math.floor(bins / 5)}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: BG.elevated,
              border: `1px solid ${BORDER.muted}`,
              borderRadius: 8,
              fontSize: 10,
            }}
            labelStyle={{ color: TEXT.secondary }}
            formatter={(value: number) => [value.toFixed(2), 'Density']}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function TornadoChart({ drivers, unit }: { drivers: SensitivityDriver[]; unit: string }) {
  const sorted = [...drivers].sort(
    (a, b) => Math.abs(b.highOutput - b.lowOutput) - Math.abs(a.highOutput - a.lowOutput),
  );
  const data = sorted.map((d) => ({
    name: d.input,
    low: d.lowOutput - d.baseOutput,
    high: d.highOutput - d.baseOutput,
    lowLabel: formatValue(d.lowOutput, unit),
    highLabel: formatValue(d.highOutput, unit),
  }));

  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 80 }}>
          <XAxis
            type="number"
            tick={{ fontSize: 8, fill: TEXT.muted }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 9, fill: TEXT.secondary }}
            axisLine={false}
            tickLine={false}
            width={75}
          />
          <Tooltip
            contentStyle={{
              background: BG.elevated,
              border: `1px solid ${BORDER.muted}`,
              borderRadius: 8,
              fontSize: 10,
            }}
            formatter={(value: number) => [formatValue(value, unit), 'Impact']}
          />
          <ReferenceLine x={0} stroke={TEXT.muted} />
          <Bar dataKey="low" fill="#c45a4a" opacity={0.7} radius={[4, 0, 0, 4]} />
          <Bar dataKey="high" fill="#6b8f71" opacity={0.7} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MonteCarloSimPanel({
  scenarios,
  sensitivityDrivers,
  iterations,
  compact,
}: MonteCarloSimPanelProps) {
  const [activeScenario, setActiveScenario] = useState(scenarios[0]?.id);
  const [showTornado, setShowTornado] = useState(false);
  const selected = scenarios.find((s) => s.id === activeScenario) ?? scenarios[0];

  if (compact && selected) {
    const trend =
      selected.p50 > selected.mean ? 'up' : selected.p50 < selected.mean ? 'down' : 'flat';
    const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
    const trendColor = trend === 'up' ? '#6b8f71' : trend === 'down' ? '#c45a4a' : TEXT.tertiary;
    return (
      <div
        className="rounded-xl p-4"
        style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-3.5 h-3.5" style={{ color: '#8b7ac8' }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color: '#8b7ac8' }}
          >
            Monte Carlo Simulation
          </span>
          <span className="ml-auto text-[9px] font-mono" style={{ color: TEXT.tertiary }}>
            {iterations.toLocaleString()} runs
          </span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-bold font-mono" style={{ color: TEXT.primary }}>
              {formatValue(selected.p50, selected.outputUnit)}
            </div>
            <div className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Median ({selected.outputMetric})
            </div>
          </div>
          <div className="flex items-center gap-1 text-[10px]" style={{ color: trendColor }}>
            <TrendIcon className="w-3 h-3" />
            <span className="font-mono">
              {formatValue(selected.p5, selected.outputUnit)} —{' '}
              {formatValue(selected.p95, selected.outputUnit)}
            </span>
          </div>
          <div className="text-right">
            <div
              className="text-sm font-bold font-mono"
              style={{ color: selected.confidence >= 75 ? '#6b8f71' : '#c8953c' }}
            >
              {selected.confidence}%
            </div>
            <div className="text-[9px]" style={{ color: TEXT.tertiary }}>
              Confidence
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: BG.surface, border: `1px solid ${BORDER.muted}` }}
    >
      <div
        className="flex items-center gap-2 px-5 py-3"
        style={{ borderBottom: `1px solid ${BORDER.subtle}` }}
      >
        <Activity className="w-4 h-4" style={{ color: '#8b7ac8' }} />
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: '#8b7ac8' }}>
          Monte Carlo Simulation
        </span>
        <span className="ml-auto text-[10px] font-mono" style={{ color: TEXT.tertiary }}>
          {iterations.toLocaleString()} iterations
        </span>
      </div>

      {scenarios.length > 1 && (
        <div
          className="flex gap-1 px-5 py-2"
          style={{ borderBottom: `1px solid ${BORDER.subtle}` }}
        >
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveScenario(s.id)}
              className="px-3 py-1 rounded-lg text-[10px] font-medium transition-all"
              style={{
                background: activeScenario === s.id ? `${s.color}15` : 'transparent',
                border: `1px solid ${activeScenario === s.id ? `${s.color}40` : 'transparent'}`,
                color: activeScenario === s.id ? s.color : TEXT.tertiary,
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="p-5">
          <div className="grid grid-cols-5 gap-3 mb-4">
            {[
              {
                label: 'P5 (Worst)',
                value: formatValue(selected.p5, selected.outputUnit),
                color: '#c45a4a',
              },
              {
                label: 'P25',
                value: formatValue(selected.p25, selected.outputUnit),
                color: '#c8953c',
              },
              {
                label: 'P50 (Median)',
                value: formatValue(selected.p50, selected.outputUnit),
                color: selected.color,
              },
              {
                label: 'P75',
                value: formatValue(selected.p75, selected.outputUnit),
                color: '#6b8f71',
              },
              {
                label: 'P95 (Best)',
                value: formatValue(selected.p95, selected.outputUnit),
                color: '#6b8f71',
              },
            ].map((p) => (
              <div key={p.label} className="text-center">
                <div
                  className="text-[8px] font-mono uppercase tracking-wider mb-0.5"
                  style={{ color: TEXT.muted }}
                >
                  {p.label}
                </div>
                <div className="text-sm font-bold font-mono" style={{ color: p.color }}>
                  {p.value}
                </div>
              </div>
            ))}
          </div>

          <DistributionChart scenario={selected} />

          <div
            className="flex items-center justify-between mt-3 pt-3"
            style={{ borderTop: `1px solid ${BORDER.subtle}` }}
          >
            <div className="flex items-center gap-4">
              <div>
                <div
                  className="text-[8px] font-mono uppercase tracking-wider"
                  style={{ color: TEXT.muted }}
                >
                  Decision Confidence
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <Target
                    className="w-3 h-3"
                    style={{ color: selected.confidence >= 75 ? '#6b8f71' : '#c8953c' }}
                  />
                  <span
                    className="text-sm font-bold font-mono"
                    style={{ color: selected.confidence >= 75 ? '#6b8f71' : '#c8953c' }}
                  >
                    {selected.confidence}%
                  </span>
                </div>
              </div>
              <div>
                <div
                  className="text-[8px] font-mono uppercase tracking-wider"
                  style={{ color: TEXT.muted }}
                >
                  Std Deviation
                </div>
                <span className="text-xs font-mono" style={{ color: TEXT.secondary }}>
                  {formatValue(selected.stdDev, selected.outputUnit)}
                </span>
              </div>
            </div>
            <button
              onClick={() => setShowTornado(!showTornado)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium"
              style={{
                background: 'rgba(139,122,200,0.08)',
                border: '1px solid rgba(139,122,200,0.2)',
                color: '#8b7ac8',
              }}
              aria-expanded={showTornado}
              aria-label="Toggle sensitivity drivers tornado chart"
            >
              {showTornado ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              Sensitivity Drivers
            </button>
          </div>

          {showTornado && sensitivityDrivers.length > 0 && (
            <div className="mt-3 pt-3" style={{ borderTop: `1px solid ${BORDER.subtle}` }}>
              <div
                className="text-[9px] font-bold uppercase tracking-widest mb-2"
                style={{ color: TEXT.muted }}
              >
                Tornado Chart — Key Sensitivity Drivers
              </div>
              <TornadoChart drivers={sensitivityDrivers} unit={selected.outputUnit} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
