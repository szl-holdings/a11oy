// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/sentra/src/pages/cyber-insurance-score.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import {
  AlertTriangle,
  Award,
  CheckCircle,
  Clock,
  Shield,
  Target,
  TrendingDown,
  Users,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import {
  Area,
  AreaChart,
  RadialBar,
  RadialBarChart,
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

const OVERALL_SCORE = 68;

const DIMENSIONS = [
  {
    id: 'posture',
    label: 'Defensive Posture',
    score: 72,
    weight: 30,
    icon: Shield,
    color: '#c9b787',
    trend: '+4',
    items: [
      {
        label: 'EDR Coverage',
        status: 'pass',
        note: '98.4% endpoint coverage — CrowdStrike Falcon',
      },
      {
        label: 'Email Security (DMARC/DKIM)',
        status: 'pass',
        note: 'DMARC enforcement p=quarantine',
      },
      {
        label: 'Network Segmentation',
        status: 'warn',
        note: 'Micro-segmentation incomplete — 3 VLAN gaps',
      },
      {
        label: 'Firewall Rule Audit',
        status: 'fail',
        note: 'Last audit: 14 months ago (SLA: 6 months)',
      },
      { label: 'Backup & Recovery', status: 'pass', note: '3-2-1 backup policy — RTO 4h, RPO 1h' },
      { label: 'WAF / DDoS Protection', status: 'pass', note: 'Cloudflare Enterprise active' },
    ],
  },
  {
    id: 'patching',
    label: 'Patch Cadence',
    score: 61,
    weight: 25,
    icon: Clock,
    color: '#c9b787',
    trend: '-2',
    items: [
      {
        label: 'Critical Patch SLA (≤72h)',
        status: 'fail',
        note: 'Current avg: 8.3 days — 12 overdue',
      },
      {
        label: 'High Patch SLA (≤7d)',
        status: 'warn',
        note: 'Current avg: 11.2 days — 34 overdue',
      },
      { label: 'OS Patch Coverage', status: 'warn', note: '87% of servers — 13% running EOL OS' },
      { label: 'Application Patching', status: 'pass', note: 'SCCM automated — 94% compliance' },
      {
        label: 'Third-Party Libraries',
        status: 'fail',
        note: 'SBOM incomplete — no automated SCA',
      },
    ],
  },
  {
    id: 'identity',
    label: 'Identity Hygiene',
    score: 74,
    weight: 25,
    icon: Users,
    color: '#8a8a8a',
    trend: '+7',
    items: [
      { label: 'MFA Coverage', status: 'pass', note: '94% of users — Microsoft Authenticator' },
      {
        label: 'Privileged Access Management',
        status: 'warn',
        note: 'PAM deployed, 18 stale admin accounts',
      },
      { label: 'SSO Enforcement', status: 'pass', note: 'Azure AD SSO — 99% application coverage' },
      {
        label: 'Service Account Hygiene',
        status: 'warn',
        note: '47 service accounts lack rotation policy',
      },
      {
        label: 'Identity Threat Detection',
        status: 'pass',
        note: 'Entra ID Protection — High risk policy active',
      },
      {
        label: 'Zero Trust Maturity',
        status: 'warn',
        note: 'Phase 2 of 4 — conditional access gaps',
      },
    ],
  },
  {
    id: 'history',
    label: 'Incident History',
    score: 58,
    weight: 20,
    icon: Target,
    color: '#f5f5f5',
    trend: '-8',
    items: [
      {
        label: 'Material Incidents (12mo)',
        status: 'fail',
        note: '3 P1 incidents — exceeds 1 threshold',
      },
      {
        label: 'Mean Time to Detect (MTTD)',
        status: 'warn',
        note: '5.1 hours — industry benchmark: 3.2h',
      },
      { label: 'Mean Time to Respond (MTTR)', status: 'warn', note: '24 hours — target: 12 hours' },
      {
        label: 'Breach Disclosure Timeliness',
        status: 'pass',
        note: 'All disclosures within regulatory windows',
      },
      {
        label: 'Ransom/Extortion Events',
        status: 'pass',
        note: '0 ransomware payments in past 24 months',
      },
    ],
  },
];

const SCORE_TREND = [
  { month: 'Oct', score: 61 },
  { month: 'Nov', score: 63 },
  { month: 'Dec', score: 59 },
  { month: 'Jan', score: 64 },
  { month: 'Feb', score: 67 },
  { month: 'Mar', score: 71 },
  { month: 'Apr', score: 68 },
];

const RECOMMENDATIONS = [
  {
    priority: 'critical',
    action: 'Implement emergency critical patch SLA program',
    impact: '+8 pts',
    effort: 'High',
    dimension: 'Patch Cadence',
  },
  {
    priority: 'critical',
    action: 'Complete firewall rule audit and remediate stale rules',
    impact: '+5 pts',
    effort: 'Medium',
    dimension: 'Defensive Posture',
  },
  {
    priority: 'high',
    action: 'Deploy Software Composition Analysis (SCA) for SBOM',
    impact: '+6 pts',
    effort: 'Medium',
    dimension: 'Patch Cadence',
  },
  {
    priority: 'high',
    action: 'Purge 18 stale privileged accounts and enforce quarterly reviews',
    impact: '+4 pts',
    effort: 'Low',
    dimension: 'Identity Hygiene',
  },
  {
    priority: 'high',
    action: 'Deploy PAM solution for 47 service accounts with rotation policy',
    impact: '+4 pts',
    effort: 'High',
    dimension: 'Identity Hygiene',
  },
  {
    priority: 'medium',
    action: 'Achieve Zero Trust Phase 3 — complete conditional access policies',
    impact: '+3 pts',
    effort: 'High',
    dimension: 'Identity Hygiene',
  },
  {
    priority: 'medium',
    action: 'Reduce MTTD to ≤3.5h via tuning SIEM detection rules',
    impact: '+3 pts',
    effort: 'Medium',
    dimension: 'Incident History',
  },
];

const INSURER_BENCHMARKS = [
  {
    insurer: 'Coalition',
    min: 70,
    premium: 'Standard Rate',
    status: OVERALL_SCORE >= 70 ? 'eligible' : 'upgrade',
  },
  {
    insurer: 'Corvus',
    min: 65,
    premium: 'Preferred Rate',
    status: OVERALL_SCORE >= 65 ? 'eligible' : 'upgrade',
  },
  {
    insurer: 'Beazley',
    min: 75,
    premium: 'Top Tier Rate',
    status: OVERALL_SCORE >= 75 ? 'eligible' : 'upgrade',
  },
  {
    insurer: 'AXA XL',
    min: 60,
    premium: 'Base Rate',
    status: OVERALL_SCORE >= 60 ? 'eligible' : 'upgrade',
  },
];

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 75 ? '#c9b787' : score >= 60 ? '#8a8a8a' : '#f5f5f5';
  const label = score >= 75 ? 'Strong' : score >= 60 ? 'Moderate' : 'At Risk';
  const data = [{ score, fill: color }];

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-44 h-24">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="60%"
            outerRadius="100%"
            data={data}
            startAngle={180}
            endAngle={0}
          >
            <RadialBar
              dataKey="score"
              background={{ fill: 'rgba(255,255,255,0.04)' }}
              cornerRadius={4}
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className="text-3xl font-bold font-mono" style={{ color }}>
            {score}
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color }}>
            {label}
          </span>
        </div>
      </div>
      <span className="text-[10px] mt-1" style={{ color: DS.text.tertiary }}>
        Cyber Insurance Score
      </span>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'pass') return <CheckCircle className="w-3.5 h-3.5 text-[#c9b787] shrink-0" />;
  if (status === 'warn') return <AlertTriangle className="w-3.5 h-3.5 text-[#c9b787] shrink-0" />;
  return <XCircle className="w-3.5 h-3.5 text-[#f5f5f5] shrink-0" />;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#8a8a8a',
};

export default function CyberInsuranceScore() {
  const [activeDim, setActiveDim] = useState(DIMENSIONS[0]);

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
              style={{ background: 'rgba(201,183,135,0.15)' }}
            >
              <Award className="w-4 h-4 text-[#c9b787]" />
            </div>
            <h1 className="text-lg font-bold tracking-tight">Cyber Insurance Score</h1>
          </div>
          <p className="text-sm" style={{ color: DS.text.secondary }}>
            Proprietary insurability rating — defensive posture, patch cadence, identity hygiene,
            incident history
          </p>
        </div>
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
          style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${DS.border}` }}
        >
          <span className="text-[10px]" style={{ color: DS.text.tertiary }}>
            Last calculated
          </span>
          <span className="text-[10px] font-mono" style={{ color: DS.text.secondary }}>
            Apr 14, 2026 · 09:31 UTC
          </span>
        </div>
      </div>

      {/* Score + trend */}
      <div className="grid grid-cols-3 gap-4">
        <div
          className="rounded-xl p-5 flex flex-col items-center justify-center"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <ScoreGauge score={OVERALL_SCORE} />
          <div
            className="mt-3 flex items-center gap-2 text-[10px]"
            style={{ color: DS.text.tertiary }}
          >
            <TrendingDown className="w-3.5 h-3.5 text-[#f5f5f5]" />
            <span>
              -3 pts from last month · <span className="text-[#c9b787]">Needs improvement</span>
            </span>
          </div>
        </div>

        <div
          className="rounded-xl p-5"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: DS.text.tertiary }}
          >
            Score Trend (7 months)
          </h3>
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={SCORE_TREND}>
                <defs>
                  <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#c9b787" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#c9b787" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="month"
                  tick={{ fill: DS.text.muted, fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={[50, 80]}
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
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#c9b787"
                  fill="url(#scoreGrad)"
                  strokeWidth={2}
                  dot={{ fill: '#c9b787', r: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div
          className="rounded-xl p-5"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: DS.text.tertiary }}
          >
            Insurer Eligibility
          </h3>
          <div className="space-y-2.5">
            {INSURER_BENCHMARKS.map((ins) => (
              <div key={ins.insurer} className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium">{ins.insurer}</p>
                  <p className="text-[10px]" style={{ color: DS.text.tertiary }}>
                    Min score: {ins.min} · {ins.premium}
                  </p>
                </div>
                <Badge
                  className="text-[9px] px-1.5 py-0"
                  style={{
                    background:
                      ins.status === 'eligible' ? 'rgba(201,183,135,0.1)' : 'rgba(245,245,245,0.1)',
                    color: ins.status === 'eligible' ? '#c9b787' : '#f5f5f5',
                    border: `1px solid ${ins.status === 'eligible' ? 'rgba(201,183,135,0.2)' : 'rgba(245,245,245,0.2)'}`,
                  }}
                >
                  {ins.status === 'eligible' ? 'Eligible' : `Need +${ins.min - OVERALL_SCORE} pts`}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Dimension cards */}
      <div className="grid grid-cols-4 gap-3">
        {DIMENSIONS.map((dim) => {
          const Icon = dim.icon;
          const isActive = activeDim.id === dim.id;
          const passCount = dim.items.filter((i) => i.status === 'pass').length;
          return (
            <button
              key={dim.id}
              onClick={() => setActiveDim(dim)}
              className="text-left rounded-xl p-4 transition-all"
              style={{
                background: isActive ? `${dim.color}08` : DS.surface,
                border: `1px solid ${isActive ? `${dim.color}30` : DS.border}`,
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <div
                  className="w-6 h-6 rounded-md flex items-center justify-center"
                  style={{ background: `${dim.color}18` }}
                >
                  <Icon className="w-3.5 h-3.5" style={{ color: dim.color }} />
                </div>
                <span className="text-[10px] font-medium">{dim.label}</span>
              </div>
              <div className="flex items-end justify-between mb-2">
                <span className="text-2xl font-bold font-mono" style={{ color: dim.color }}>
                  {dim.score}
                </span>
                <span
                  className="text-[10px] font-mono"
                  style={{ color: parseFloat(dim.trend) > 0 ? '#c9b787' : '#f5f5f5' }}
                >
                  {dim.trend} pts
                </span>
              </div>
              <div className="text-[9px]" style={{ color: DS.text.muted }}>
                {passCount}/{dim.items.length} controls passing · {dim.weight}% weight
              </div>
              <div
                className="mt-2 h-1 rounded-full overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.06)' }}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${dim.score}%`, background: dim.color, opacity: 0.7 }}
                />
              </div>
            </button>
          );
        })}
      </div>

      {/* Dimension detail */}
      <div className="grid grid-cols-5 gap-4">
        <div
          className="col-span-3 rounded-xl p-5"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <div className="flex items-center gap-2 mb-4">
            <activeDim.icon className="w-4 h-4" style={{ color: activeDim.color }} />
            <h3 className="text-sm font-semibold">{activeDim.label} — Control Assessment</h3>
            <Badge
              className="text-[9px] px-1.5"
              style={{ background: `${activeDim.color}15`, color: activeDim.color, border: 'none' }}
            >
              {activeDim.score}/100
            </Badge>
          </div>
          <div className="space-y-2">
            {activeDim.items.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 p-2.5 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${DS.border}` }}
              >
                <StatusIcon status={item.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium">{item.label}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: DS.text.secondary }}>
                    {item.note}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="col-span-2 rounded-xl p-5"
          style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
        >
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-4"
            style={{ color: DS.text.tertiary }}
          >
            Improvement Recommendations
          </h3>
          <div className="space-y-2.5">
            {RECOMMENDATIONS.map((rec, i) => (
              <div
                key={i}
                className="p-2.5 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.02)', border: `1px solid ${DS.border}` }}
              >
                <div className="flex items-center justify-between mb-1">
                  <Badge
                    className="text-[9px] px-1.5 py-0"
                    style={{
                      background: `${PRIORITY_COLORS[rec.priority]}12`,
                      color: PRIORITY_COLORS[rec.priority],
                      border: 'none',
                    }}
                  >
                    {rec.priority.toUpperCase()}
                  </Badge>
                  <span className="text-[9px] font-mono font-bold text-[#c9b787]">
                    {rec.impact}
                  </span>
                </div>
                <p className="text-[10px] leading-snug" style={{ color: DS.text.secondary }}>
                  {rec.action}
                </p>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[9px]" style={{ color: DS.text.muted }}>
                    {rec.dimension}
                  </span>
                  <span className="text-[9px]" style={{ color: DS.text.muted }}>
                    Effort: {rec.effort}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
