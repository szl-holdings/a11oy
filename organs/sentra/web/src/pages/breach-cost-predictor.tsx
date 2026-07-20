// VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — artifacts/sentra/src/pages/breach-cost-predictor.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import {
  Building2,
  ChevronRight,
  Clock,
  DollarSign,
  Users,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const DS = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    tertiary: 'rgba(255,255,255,0.28)',
    muted: 'rgba(255,255,255,0.14)',
  },
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

function AnimatedCounter({
  value,
  prefix = '$',
  suffix = '',
}: {
  value: number;
  prefix?: string;
  suffix?: string;
}) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(0);
  useEffect(() => {
    const start = ref.current;
    const diff = value - start;
    if (Math.abs(diff) < 0.01) return;
    let cancelled = false;
    const t0 = performance.now();
    const step = (now: number) => {
      if (cancelled) return;
      const p = Math.min((now - t0) / 1400, 1);
      const e = 1 - (1 - p) ** 3;
      setDisplay(Math.round(start + diff * e));
      if (p < 1) requestAnimationFrame(step);
      else ref.current = value;
    };
    requestAnimationFrame(step);
    return () => {
      cancelled = true;
    };
  }, [value]);
  if (display >= 1_000_000)
    return (
      <>
        {prefix}
        {(display / 1_000_000).toFixed(1)}M{suffix}
      </>
    );
  if (display >= 1_000)
    return (
      <>
        {prefix}
        {(display / 1_000).toFixed(0)}K{suffix}
      </>
    );
  return (
    <>
      {prefix}
      {display}
      {suffix}
    </>
  );
}

const THREATS = [
  {
    id: 'T-001',
    name: 'APT29 Lateral Movement — DC-PROD-03',
    severity: 'critical',
    mitre: 'T1021.002',
    asset: 'Domain Controller',
    probability: 87,
    components: {
      regulatory: 3_200_000,
      interruption: 4_800_000,
      dataLoss: 6_100_000,
      ir: 850_000,
      reputational: 2_400_000,
    },
    trend: [
      { d: 'Apr 8', v: 9_200_000 },
      { d: 'Apr 9', v: 11_400_000 },
      { d: 'Apr 10', v: 13_800_000 },
      { d: 'Apr 11', v: 15_200_000 },
      { d: 'Apr 12', v: 16_800_000 },
      { d: 'Apr 13', v: 17_350_000 },
      { d: 'Apr 14', v: 17_350_000 },
    ],
  },
  {
    id: 'T-002',
    name: 'CVE-2024-3400 — Palo Alto FW-EDGE-01',
    severity: 'critical',
    mitre: 'T1190',
    asset: 'Network Edge Firewall',
    probability: 94,
    components: {
      regulatory: 1_800_000,
      interruption: 3_200_000,
      dataLoss: 2_900_000,
      ir: 620_000,
      reputational: 1_100_000,
    },
    trend: [
      { d: 'Apr 8', v: 5_000_000 },
      { d: 'Apr 9', v: 6_100_000 },
      { d: 'Apr 10', v: 7_800_000 },
      { d: 'Apr 11', v: 8_500_000 },
      { d: 'Apr 12', v: 9_000_000 },
      { d: 'Apr 13', v: 9_620_000 },
      { d: 'Apr 14', v: 9_620_000 },
    ],
  },
  {
    id: 'T-003',
    name: 'C2 Beacon — APT29 Infrastructure',
    severity: 'high',
    mitre: 'T1071.001',
    asset: 'Multiple Endpoints',
    probability: 72,
    components: {
      regulatory: 900_000,
      interruption: 1_800_000,
      dataLoss: 2_100_000,
      ir: 410_000,
      reputational: 780_000,
    },
    trend: [
      { d: 'Apr 8', v: 2_800_000 },
      { d: 'Apr 9', v: 3_400_000 },
      { d: 'Apr 10', v: 4_200_000 },
      { d: 'Apr 11', v: 4_700_000 },
      { d: 'Apr 12', v: 5_600_000 },
      { d: 'Apr 13', v: 5_990_000 },
      { d: 'Apr 14', v: 5_990_000 },
    ],
  },
  {
    id: 'T-004',
    name: 'Brute Force — 847 Failed Logins',
    severity: 'high',
    mitre: 'T1110.001',
    asset: 'Auth Infrastructure',
    probability: 58,
    components: {
      regulatory: 420_000,
      interruption: 680_000,
      dataLoss: 900_000,
      ir: 180_000,
      reputational: 320_000,
    },
    trend: [
      { d: 'Apr 8', v: 1_200_000 },
      { d: 'Apr 9', v: 1_500_000 },
      { d: 'Apr 10', v: 1_800_000 },
      { d: 'Apr 11', v: 2_000_000 },
      { d: 'Apr 12', v: 2_200_000 },
      { d: 'Apr 13', v: 2_500_000 },
      { d: 'Apr 14', v: 2_500_000 },
    ],
  },
];

const REGULATORY_BREAKDOWN = [
  { reg: 'GDPR', exposure: 8_200_000, icon: '🇪🇺', trigger: 'PII exfiltration > 10K records' },
  { reg: 'HIPAA', exposure: 4_100_000, icon: '🏥', trigger: 'PHI exposure — 47K patient records' },
  {
    reg: 'SEC (Cyber)',
    exposure: 2_800_000,
    icon: '📋',
    trigger: 'Material incident disclosure delay',
  },
  { reg: 'CCPA', exposure: 1_600_000, icon: '🇺🇸', trigger: 'CA resident data exposure' },
  { reg: 'PCI DSS', exposure: 890_000, icon: '💳', trigger: 'Cardholder data in scope' },
];

const EXPOSURE_HISTORY = [
  { month: 'Oct', total: 12_400_000 },
  { month: 'Nov', total: 10_800_000 },
  { month: 'Dec', total: 14_200_000 },
  { month: 'Jan', total: 11_600_000 },
  { month: 'Feb', total: 9_800_000 },
  { month: 'Mar', total: 22_100_000 },
  { month: 'Apr', total: 35_460_000 },
];

const SEV_COLORS: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#8a8a8a',
  low: '#c9b787',
};

function ExposureMeter({ value, max = 50_000_000 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  const color = pct > 70 ? '#f5f5f5' : pct > 40 ? '#c9b787' : '#8a8a8a';
  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1.5">
        <span
          className="text-[10px] font-mono uppercase tracking-wider"
          style={{ color: DS.text.tertiary }}
        >
          Total Breach Exposure
        </span>
        <span className="text-[10px] font-mono" style={{ color }}>
          {pct.toFixed(0)}% of max insurable
        </span>
      </div>
      <div
        className="h-3 rounded-full overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.06)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, #c9b787, ${color})`,
            boxShadow: `0 0 12px ${color}60`,
          }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[9px]" style={{ color: DS.text.muted }}>
          $0
        </span>
        <span className="text-[9px]" style={{ color: DS.text.muted }}>
          $50M
        </span>
      </div>
    </div>
  );
}

function ComponentBar({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const pct = (value / total) * 100;
  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] w-28 shrink-0" style={{ color: DS.text.secondary }}>
        {label}
      </span>
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.06)' }}
      >
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span
        className="text-[10px] font-mono w-16 text-right shrink-0"
        style={{ color: DS.text.primary }}
      >
        {fmt(value)}
      </span>
    </div>
  );
}

export default function BreachCostPredictor() {
  const [selected, setSelected] = useState(THREATS[0]);
  const totalExposure = THREATS.reduce((s, t) => {
    const total = Object.values(t.components).reduce((a, b) => a + b, 0);
    return s + total;
  }, 0);
  const selectedTotal = Object.values(selected.components).reduce((a, b) => a + b, 0);

  const _compData = [
    { name: 'Regulatory', value: selected.components.regulatory, color: '#f5f5f5' },
    { name: 'Business Int.', value: selected.components.interruption, color: '#c9b787' },
    { name: 'Data Liability', value: selected.components.dataLoss, color: '#8a8a8a' },
    { name: 'IR Expense', value: selected.components.ir, color: '#c9b787' },
    { name: 'Reputational', value: selected.components.reputational, color: '#8a8a8a' },
  ];

  return (
    <div
      className="min-h-screen p-6 space-y-5"
      style={{ background: '#080B12', color: DS.text.primary }}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: 'rgba(245,245,245,0.15)' }}
            >
              <DollarSign className="w-4 h-4 text-[#f5f5f5]" />
            </div>
            <h1 className="text-lg font-bold tracking-tight">Breach Cost Predictor</h1>
          </div>
          <p className="text-sm" style={{ color: DS.text.secondary }}>
            Real-time financial exposure modeling across regulatory, operational, and reputational
            dimensions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md"
            style={{ background: 'rgba(245,245,245,0.08)', border: '1px solid rgba(245,245,245,0.15)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#f5f5f5] animate-pulse" />
            <span className="text-[10px] font-mono text-[#f5f5f5] uppercase tracking-wider">
              Live Modeling
            </span>
          </div>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: 'Total Breach Exposure',
            value: totalExposure,
            icon: DollarSign,
            color: '#f5f5f5',
            sub: 'across 4 active threats',
          },
          {
            label: 'Regulatory Fines at Risk',
            value: THREATS.reduce((s, t) => s + t.components.regulatory, 0),
            icon: Building2,
            color: '#c9b787',
            sub: 'GDPR, HIPAA, SEC, PCI',
          },
          {
            label: 'Business Interruption',
            value: THREATS.reduce((s, t) => s + t.components.interruption, 0),
            icon: Clock,
            color: '#8a8a8a',
            sub: 'revenue loss projection',
          },
          {
            label: 'Reputational Damage',
            value: THREATS.reduce((s, t) => s + t.components.reputational, 0),
            icon: Users,
            color: '#8a8a8a',
            sub: 'brand & market impact',
          },
        ].map(({ label, value, icon: Icon, color, sub }) => (
          <div
            key={label}
            className="rounded-xl p-4"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <div className="flex items-center gap-2 mb-3">
              <div
                className="w-6 h-6 rounded-md flex items-center justify-center"
                style={{ background: `${color}18` }}
              >
                <Icon className="w-3.5 h-3.5" style={{ color }} />
              </div>
              <span className="text-[10px]" style={{ color: DS.text.tertiary }}>
                {label}
              </span>
            </div>
            <div className="text-2xl font-bold font-mono mb-1" style={{ color }}>
              <AnimatedCounter value={value} />
            </div>
            <p className="text-[10px]" style={{ color: DS.text.muted }}>
              {sub}
            </p>
          </div>
        ))}
      </div>

      {/* Exposure Meter */}
      <div
        className="rounded-xl p-5"
        style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
      >
        <ExposureMeter value={totalExposure} />
      </div>

      <div className="grid grid-cols-5 gap-4">
        {/* Threat List */}
        <div className="col-span-2 space-y-2">
          <h2
            className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: DS.text.tertiary }}
          >
            Active Threats — Financial Exposure
          </h2>
          {THREATS.map((t) => {
            const total = Object.values(t.components).reduce((a, b) => a + b, 0);
            const isSelected = selected.id === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setSelected(t)}
                className="w-full text-left rounded-xl p-4 transition-all"
                style={{
                  background: isSelected ? 'rgba(245,245,245,0.06)' : DS.surface,
                  border: `1px solid ${isSelected ? 'rgba(245,245,245,0.25)' : DS.border}`,
                }}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
                        {t.id}
                      </span>
                      <Badge
                        className="text-[9px] px-1.5 py-0"
                        style={{
                          background: `${SEV_COLORS[t.severity]}15`,
                          color: SEV_COLORS[t.severity],
                          border: `1px solid ${SEV_COLORS[t.severity]}25`,
                        }}
                      >
                        {t.severity.toUpperCase()}
                      </Badge>
                    </div>
                    <p className="text-xs font-medium truncate" style={{ color: DS.text.primary }}>
                      {t.name}
                    </p>
                    <p className="text-[10px] mt-0.5" style={{ color: DS.text.secondary }}>
                      {t.mitre} · {t.asset}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span
                    className="text-lg font-bold font-mono"
                    style={{ color: SEV_COLORS[t.severity] }}
                  >
                    {fmt(total)}
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] font-mono" style={{ color: DS.text.tertiary }}>
                      {t.probability}% probability
                    </span>
                    <ChevronRight className="w-3 h-3" style={{ color: DS.text.muted }} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Detail Panel */}
        <div className="col-span-3 space-y-4">
          <div
            className="rounded-xl p-5"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold">{selected.name}</h3>
                <p className="text-[10px] mt-0.5" style={{ color: DS.text.secondary }}>
                  MITRE {selected.mitre} · {selected.asset}
                </p>
              </div>
              <div className="text-right">
                <div
                  className="text-2xl font-bold font-mono"
                  style={{ color: SEV_COLORS[selected.severity] }}
                >
                  <AnimatedCounter value={selectedTotal} />
                </div>
                <p className="text-[10px]" style={{ color: DS.text.muted }}>
                  projected breach cost
                </p>
              </div>
            </div>

            <div className="space-y-2.5 mb-4">
              <p
                className="text-[10px] font-medium uppercase tracking-wider mb-2"
                style={{ color: DS.text.tertiary }}
              >
                Cost Breakdown
              </p>
              <ComponentBar
                label="Regulatory Fines"
                value={selected.components.regulatory}
                total={selectedTotal}
                color="#f5f5f5"
              />
              <ComponentBar
                label="Business Interrupt."
                value={selected.components.interruption}
                total={selectedTotal}
                color="#c9b787"
              />
              <ComponentBar
                label="Data Liability"
                value={selected.components.dataLoss}
                total={selectedTotal}
                color="#8a8a8a"
              />
              <ComponentBar
                label="IR Expense"
                value={selected.components.ir}
                total={selectedTotal}
                color="#c9b787"
              />
              <ComponentBar
                label="Reputational"
                value={selected.components.reputational}
                total={selectedTotal}
                color="#8a8a8a"
              />
            </div>

            <div className="h-32">
              <p
                className="text-[10px] font-medium uppercase tracking-wider mb-2"
                style={{ color: DS.text.tertiary }}
              >
                7-Day Exposure Trend
              </p>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={selected.trend}>
                  <defs>
                    <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={SEV_COLORS[selected.severity]}
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor={SEV_COLORS[selected.severity]}
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="d"
                    tick={{ fill: DS.text.muted, fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v) => fmt(v)}
                    tick={{ fill: DS.text.muted, fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#0F1319',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 8,
                      fontSize: 11,
                    }}
                    formatter={(v: number) => [fmt(v), 'Exposure']}
                  />
                  <Area
                    type="monotone"
                    dataKey="v"
                    stroke={SEV_COLORS[selected.severity]}
                    fill="url(#expGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Regulatory breakdown */}
          <div
            className="rounded-xl p-5"
            style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
          >
            <h3
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: DS.text.tertiary }}
            >
              Regulatory Exposure Breakdown
            </h3>
            <div className="space-y-2.5">
              {REGULATORY_BREAKDOWN.map((r) => (
                <div key={r.reg} className="flex items-center gap-3">
                  <span className="text-sm">{r.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-medium">{r.reg}</span>
                      <span className="text-xs font-mono font-bold" style={{ color: '#f5f5f5' }}>
                        {fmt(r.exposure)}
                      </span>
                    </div>
                    <p className="text-[10px]" style={{ color: DS.text.tertiary }}>
                      {r.trigger}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Historical exposure chart */}
      <div
        className="rounded-xl p-5"
        style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
      >
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-4"
          style={{ color: DS.text.tertiary }}
        >
          Monthly Breach Exposure History
        </h3>
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={EXPOSURE_HISTORY}>
              <XAxis
                dataKey="month"
                tick={{ fill: DS.text.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v) => fmt(v)}
                tick={{ fill: DS.text.muted, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#0F1319',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8,
                  fontSize: 11,
                }}
                formatter={(v: number) => [fmt(v), 'Exposure']}
              />
              <Bar dataKey="total" radius={[3, 3, 0, 0]}>
                {EXPOSURE_HISTORY.map((e, idx) => (
                  <Cell
                    key={e.month}
                    fill={idx === EXPOSURE_HISTORY.length - 1 ? '#f5f5f5' : '#c9b787'}
                    fillOpacity={idx === EXPOSURE_HISTORY.length - 1 ? 0.8 : 0.4}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
