import { useStandardQuery } from '@szl-holdings/api-client-react';
import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@szl-holdings/shared-ui/ui/card';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Cloud,
  DollarSign,
  Download,
  Eye,
  Factory,
  FileLock2,
  Globe2,
  type LucideIcon,
  Mail,
  Shield,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Link } from 'wouter';
import { api } from '@/lib/api';

type Module = {
  key: string;
  name: string;
  short: string;
  icon: LucideIcon;
  route: string;
  metricLabel: string;
  metricValue: string;
  delta: string;
  deltaTrend: 'up' | 'down' | 'flat';
  deltaIsGood: boolean;
  status: 'Healthy' | 'Watch' | 'Action';
  caseCount: number;
  summary: string;
};

const modules: Module[] = [
  {
    key: 'asm',
    name: 'Attack Surface Management',
    short: 'ASM',
    icon: Globe2,
    route: '/asset-inventory',
    metricLabel: 'Exposed Assets',
    metricValue: '184',
    delta: '-23% QoQ',
    deltaTrend: 'down',
    deltaIsGood: true,
    status: 'Watch',
    caseCount: 12,
    summary:
      '8,412 internet-facing assets discovered. 184 still exposed; 12 critical CVEs awaiting patch.',
  },
  {
    key: 'cspm',
    name: 'Cloud Security Posture',
    short: 'CSPM',
    icon: Cloud,
    route: '/hardening-controls',
    metricLabel: 'Misconfigurations',
    metricValue: '47',
    delta: '-38% QoQ',
    deltaTrend: 'down',
    deltaIsGood: true,
    status: 'Healthy',
    caseCount: 6,
    summary:
      'AWS, Azure, GCP scored against CIS benchmarks. 47 high-severity drifts open across 11 accounts.',
  },
  {
    key: 'itdr',
    name: 'Identity Threat Detection',
    short: 'ITDR',
    icon: Users,
    route: '/identity-threat',
    metricLabel: 'Identity Threats',
    metricValue: '9',
    delta: '+2 vs last Q',
    deltaTrend: 'up',
    deltaIsGood: false,
    status: 'Action',
    caseCount: 9,
    summary:
      'Token theft, OAuth abuse, and Tier 0 lateral movement attempts detected on 3 service principals.',
  },
  {
    key: 'dlp',
    name: 'Data Loss Prevention',
    short: 'DLP',
    icon: FileLock2,
    route: '/findings',
    metricLabel: 'Sensitive Egress Blocks',
    metricValue: '1,284',
    delta: '+12% QoQ',
    deltaTrend: 'up',
    deltaIsGood: true,
    status: 'Healthy',
    caseCount: 4,
    summary:
      'PII, PHI, and regulated IP exfiltration attempts blocked across email, SaaS, and endpoint.',
  },
  {
    key: 'ztna',
    name: 'Zero Trust Maturity',
    short: 'ZTMM',
    icon: ShieldCheck,
    route: '/zero-trust-scorecard',
    metricLabel: 'NSA ZT Score',
    metricValue: '78 / 100',
    delta: '+11 pts QoQ',
    deltaTrend: 'up',
    deltaIsGood: true,
    status: 'Watch',
    caseCount: 3,
    summary:
      'Identity & Device pillars at Advanced. Network and Automation pillars still in Initial tier.',
  },
  {
    key: 'phish',
    name: 'Phishing Simulation',
    short: 'Phish Sim',
    icon: Mail,
    route: '/purple-team',
    metricLabel: 'Click Rate',
    metricValue: '3.4%',
    delta: '-1.8 pts QoQ',
    deltaTrend: 'down',
    deltaIsGood: true,
    status: 'Healthy',
    caseCount: 0,
    summary:
      '21,840 simulations sent this quarter. 738 clicks, 41 credential entries, 92% report rate.',
  },
  {
    key: 'deception',
    name: 'Deception Grid',
    short: 'Decoys',
    icon: Eye,
    route: '/deception-grid',
    metricLabel: 'Adversary Engagements',
    metricValue: '27',
    delta: '+9 vs last Q',
    deltaTrend: 'up',
    deltaIsGood: true,
    status: 'Watch',
    caseCount: 5,
    summary:
      '27 confirmed adversary touches on honey-tokens and decoy services. Avg dwell time 14 minutes.',
  },
  {
    key: 'ot',
    name: 'OT / ICS Security',
    short: 'OT/ICS',
    icon: Factory,
    route: '/adaptive-defense-shield',
    metricLabel: 'ICS Risk Score',
    metricValue: '62 / 100',
    delta: '-6 pts QoQ',
    deltaTrend: 'down',
    deltaIsGood: true,
    status: 'Action',
    caseCount: 7,
    summary:
      'Purdue Levels 1–3 monitored across 4 plants. 7 unauthorized PLC programming attempts blocked.',
  },
];

const trendData = [
  { week: 'W1', current: 78, previous: 64 },
  { week: 'W2', current: 75, previous: 66 },
  { week: 'W3', current: 71, previous: 68 },
  { week: 'W4', current: 73, previous: 70 },
  { week: 'W5', current: 69, previous: 71 },
  { week: 'W6', current: 66, previous: 73 },
  { week: 'W7', current: 64, previous: 74 },
  { week: 'W8', current: 62, previous: 72 },
  { week: 'W9', current: 60, previous: 70 },
  { week: 'W10', current: 58, previous: 71 },
  { week: 'W11', current: 55, previous: 69 },
  { week: 'W12', current: 53, previous: 70 },
];

const domainCompare = [
  { domain: 'ASM', current: 18, previous: 41 },
  { domain: 'CSPM', current: 47, previous: 76 },
  { domain: 'ITDR', current: 9, previous: 7 },
  { domain: 'DLP', current: 12, previous: 19 },
  { domain: 'Zero Trust', current: 22, previous: 38 },
  { domain: 'Phish', current: 34, previous: 52 },
  { domain: 'Decoys', current: 27, previous: 18 },
  { domain: 'OT/ICS', current: 62, previous: 68 },
];

const compliance = [
  { framework: 'SOC 2 Type II', score: 91, status: 'Compliant', route: '/cr/scorecards' },
  { framework: 'NIST CSF 2.0', score: 84, status: 'Mature', route: '/cr/scorecards' },
  { framework: 'ISO 27001:2022', score: 82, status: 'Compliant', route: '/cr/scorecards' },
  { framework: 'CMMC 2.0 L2', score: 76, status: 'In Progress', route: '/cr/scorecards' },
  { framework: 'StateRAMP Moderate', score: 74, status: 'Assessment', route: '/cr/scorecards' },
  { framework: 'NIS2 / DORA', score: 71, status: 'Remediation', route: '/cr/scorecards' },
  { framework: 'PCI DSS 4.0', score: 88, status: 'Compliant', route: '/cr/scorecards' },
  { framework: 'HIPAA Security', score: 86, status: 'Compliant', route: '/cr/scorecards' },
];

const roiPanel = [
  {
    module: 'Attack Surface Management',
    intervention: '204 critical exposures remediated < 24h SLA',
    avoided: 8.4,
    icon: Globe2,
    route: '/asset-inventory',
  },
  {
    module: 'Cloud Security Posture',
    intervention: 'Public S3 bucket auto-quarantine + IAM drift recovery',
    avoided: 6.1,
    icon: Cloud,
    route: '/hardening-controls',
  },
  {
    module: 'Identity Threat Detection',
    intervention: 'Token theft response + Tier 0 isolation playbook',
    avoided: 11.7,
    icon: Users,
    route: '/identity-threat',
  },
  {
    module: 'Data Loss Prevention',
    intervention: '1,284 sensitive egress blocks across email/SaaS/endpoint',
    avoided: 4.9,
    icon: FileLock2,
    route: '/findings',
  },
  {
    module: 'Zero Trust Program',
    intervention: 'ZT score +11 pts; lateral movement reduction modeled',
    avoided: 3.6,
    icon: ShieldCheck,
    route: '/zero-trust-scorecard',
  },
  {
    module: 'Phishing Simulation',
    intervention: 'Click rate 5.2% → 3.4%; BEC risk reduction',
    avoided: 2.8,
    icon: Mail,
    route: '/purple-team',
  },
  {
    module: 'Deception Grid',
    intervention: 'Early detection on 27 adversary engagements',
    avoided: 5.3,
    icon: Eye,
    route: '/deception-grid',
  },
  {
    module: 'OT / ICS Security',
    intervention: '7 unauthorized PLC programming attempts blocked',
    avoided: 18.2,
    icon: Factory,
    route: '/adaptive-defense-shield',
  },
];

const totalAvoided = roiPanel.reduce((s, r) => s + r.avoided, 0);
const programSpend = 14.2;
const roiMultiple = (totalAvoided / programSpend).toFixed(1);

const STATIC_HEADLINE_KPIS = [
  {
    label: 'Aggregate Risk Score',
    value: '53',
    suffix: '/ 100',
    trend: '-19 QoQ',
    good: true,
    icon: Shield,
  },
  {
    label: 'Open Critical Findings',
    value: '46',
    suffix: '',
    trend: '-31% QoQ',
    good: true,
    icon: AlertTriangle,
  },
  {
    label: 'Mean Time to Contain',
    value: '18',
    suffix: 'min',
    trend: '-42% QoQ',
    good: true,
    icon: TrendingDown,
  },
  {
    label: 'Breach Cost Avoided',
    value: `$${totalAvoided.toFixed(1)}M`,
    suffix: 'QTD',
    trend: `${roiMultiple}× ROI`,
    good: true,
    icon: DollarSign,
  },
];

function statusBadge(status: Module['status']) {
  const map = {
    Healthy: 'bg-[#c9b787]/15 text-[#c9b787] border-[#c9b787]/30',
    Watch: 'bg-[#c9b787]/15 text-[#c9b787] border-[#c9b787]/30',
    Action: 'bg-[#f5f5f5]/15 text-[#f5f5f5] border-rose-500/30',
  } as const;
  return (
    <Badge variant="outline" className={map[status]}>
      {status}
    </Badge>
  );
}

interface ThreatSummaryData {
  activeThreats?: number;
  criticalAlerts?: number;
  incidentsOpenLast24h?: number;
  meanTimeToDetect?: string;
  meanTimeToRespond?: string;
}
interface ComplianceSummaryData {
  overallScore?: number;
  dbControls?: { total?: number; passing?: number; failing?: number; inProgress?: number };
}
interface AssetRiskItem {
  entity?: string;
  type?: string;
  risk?: number;
  status?: string;
}
interface AssetRiskData {
  dbAssets?: AssetRiskItem[];
  aptEntities?: AssetRiskItem[];
}
interface CisoKpiData {
  aggregateRisk?: number | null;
  activeThreats?: number | null;
  openCriticals?: number | null;
  meanTimeToRespondMin?: number | null;
  compliancePct?: number | null;
}
export default function CisoDashboard() {
  const radial = [{ name: 'ZT', uv: 78, fill: '#22d3ee' }];

  // Single-call aggregator — preferred source for the four headline tiles.
  // Falls back gracefully (per-tile) to the existing live-data queries when
  // a sub-metric is null or the endpoint itself is unavailable.
  const cisoKpis = useStandardQuery<CisoKpiData>({
    queryKey: ['ciso', 'ciso-kpis'],
    queryFn: () => api.liveData.cisoKpis() as Promise<CisoKpiData>,
    staleTime: 60_000,
    retry: false,
  });
  const threatSummary = useStandardQuery<ThreatSummaryData>({
    queryKey: ['ciso', 'threat-summary'],
    queryFn: () => api.liveData.threatSummary() as Promise<ThreatSummaryData>,
    staleTime: 60_000,
    retry: false,
  });
  const complianceQuery = useStandardQuery<ComplianceSummaryData>({
    queryKey: ['ciso', 'compliance-summary'],
    queryFn: () => api.liveData.complianceSummary() as Promise<ComplianceSummaryData>,
    staleTime: 60_000,
    retry: false,
  });
  const assetRisk = useStandardQuery<AssetRiskData>({
    queryKey: ['ciso', 'asset-risk'],
    queryFn: () => api.liveData.assetRisk() as Promise<AssetRiskData>,
    staleTime: 60_000,
    retry: false,
  });

  const ts = threatSummary.data;
  const cp = complianceQuery.data;
  const ar = assetRisk.data;
  const ciso = cisoKpis.data;
  const liveLoaded = !!(ts || cp || ar || ciso);

  // Prefer the single-call aggregator's value for each headline tile, then
  // fall back to the per-source queries, then to the static panel value.
  const dbAssets = ar?.dbAssets ?? [];
  const fallbackRisk =
    dbAssets.length > 0
      ? Math.round(dbAssets.reduce((s, a) => s + (a.risk ?? 0), 0) / dbAssets.length)
      : null;
  const aggregateRisk = ciso?.aggregateRisk ?? fallbackRisk;
  const openCriticals =
    ciso?.openCriticals ?? (ts ? (ts.criticalAlerts ?? 0) + (ts.incidentsOpenLast24h ?? 0) : null);
  const mttr = ciso?.meanTimeToRespondMin != null
    ? `${ciso.meanTimeToRespondMin}m`
    : (ts?.meanTimeToRespond ?? null);
  const overallCompliance = ciso?.compliancePct ?? cp?.overallScore ?? null;

  const headlineKpis = liveLoaded
    ? [
        aggregateRisk != null
          ? {
              label: 'Aggregate Risk Score',
              value: String(aggregateRisk),
              suffix: '/ 100',
              trend: 'Live · /firestorm/live/asset-risk',
              good: aggregateRisk < 60,
              icon: Shield,
            }
          : STATIC_HEADLINE_KPIS[0],
        openCriticals != null
          ? {
              label: 'Open Critical Findings',
              value: String(openCriticals),
              suffix: '',
              trend: `${ts?.activeThreats ?? 0} active threats live`,
              good: openCriticals < 10,
              icon: AlertTriangle,
            }
          : STATIC_HEADLINE_KPIS[1],
        mttr
          ? {
              label: 'Mean Time to Respond',
              value: mttr,
              suffix: '',
              trend: `MTTD ${ts?.meanTimeToDetect ?? '—'}`,
              good: true,
              icon: TrendingDown,
            }
          : STATIC_HEADLINE_KPIS[2],
        overallCompliance != null
          ? {
              label: 'Compliance Posture',
              value: `${overallCompliance}`,
              suffix: '%',
              trend: `${cp?.dbControls?.passing ?? 0}/${cp?.dbControls?.total ?? 0} controls passing`,
              good: overallCompliance >= 75,
              icon: DollarSign,
            }
          : STATIC_HEADLINE_KPIS[3],
      ]
    : STATIC_HEADLINE_KPIS;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-[1500px] space-y-6 p-6" data-testid="ciso-dashboard">
        {/* Header */}
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-[#8a8a8a]/80">
              <Shield className="h-3.5 w-3.5" /> CISO Executive Dashboard
            </div>
            <h1
              className="mt-1 text-3xl font-semibold tracking-tight"
              data-testid="text-page-title"
            >
              Unified Security Posture — Q1 vs Q4
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-400">
              Single pane-of-glass aggregating ASM, CSPM, ITDR, DLP, Zero Trust, Phishing
              Simulation, Deception Grid, and OT/ICS into board-ready KPIs, trend charts, and
              breach-cost-avoided ROI.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="border-[#8a8a8a]/30 bg-[#8a8a8a]/10 text-[#8a8a8a]">
              Reporting period: Apr 2026
            </Badge>
            <Button size="sm" variant="outline" data-testid="button-export-board-pack">
              <Download className="mr-2 h-4 w-4" /> Export board pack
            </Button>
          </div>
        </header>

        {/* Headline KPIs */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="headline-kpis">
          {headlineKpis.map((k) => {
            const Icon = k.icon;
            return (
              <Card key={k.label} className="border-slate-800 bg-slate-900/60">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-wider text-slate-400">
                      {k.label}
                    </span>
                    <Icon className="h-4 w-4 text-[#8a8a8a]" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-3xl font-semibold text-white">{k.value}</span>
                    <span className="text-sm text-slate-400">{k.suffix}</span>
                  </div>
                  <div
                    className={`mt-2 flex items-center gap-1 text-xs ${k.good ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}
                  >
                    {k.good ? (
                      <TrendingDown className="h-3 w-3" />
                    ) : (
                      <TrendingUp className="h-3 w-3" />
                    )}
                    <span>{k.trend}</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Module cards */}
        <section>
          <div className="mb-3 flex items-end justify-between">
            <h2 className="text-lg font-semibold">Eight Security Domains — Critical Metrics</h2>
            <span className="text-xs text-slate-500">Click any card to drill into the module</span>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="module-grid">
            {modules.map((m) => {
              const Icon = m.icon;
              return (
                <Link key={m.key} href={m.route}>
                  <Card
                    className="cursor-pointer border-slate-800 bg-slate-900/60 transition hover:border-[#8a8a8a]/40 hover:bg-slate-900"
                    data-testid={`module-card-${m.key}`}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="rounded-md bg-[#8a8a8a]/10 p-1.5 text-[#8a8a8a]">
                            <Icon className="h-4 w-4" />
                          </span>
                          <span className="text-xs uppercase tracking-wider text-slate-400">
                            {m.short}
                          </span>
                        </div>
                        {statusBadge(m.status)}
                      </div>
                      <CardTitle className="mt-2 text-base text-white">{m.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-end justify-between">
                        <div>
                          <div className="text-xs text-slate-500">{m.metricLabel}</div>
                          <div className="text-2xl font-semibold text-white">{m.metricValue}</div>
                        </div>
                        <div
                          className={`flex items-center gap-1 text-xs ${
                            m.deltaIsGood ? 'text-[#c9b787]' : 'text-[#f5f5f5]'
                          }`}
                        >
                          {m.deltaTrend === 'down' ? (
                            <TrendingDown className="h-3 w-3" />
                          ) : (
                            <TrendingUp className="h-3 w-3" />
                          )}
                          {m.delta}
                        </div>
                      </div>
                      <p className="text-xs leading-relaxed text-slate-400">{m.summary}</p>
                      <div className="flex items-center justify-between border-t border-slate-800 pt-2 text-xs text-slate-400">
                        <span>
                          {m.caseCount} open case{m.caseCount === 1 ? '' : 's'}
                        </span>
                        <span className="flex items-center gap-1 text-[#8a8a8a]">
                          Open module <ArrowUpRight className="h-3 w-3" />
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        </section>

        {/* Risk trend + domain compare */}
        <section className="grid gap-4 lg:grid-cols-3">
          <Card
            className="border-slate-800 bg-slate-900/60 lg:col-span-2"
            data-testid="risk-trend-chart"
          >
            <CardHeader>
              <CardTitle className="text-base">
                Aggregate Risk Trend — This Quarter vs Last Quarter
              </CardTitle>
              <p className="text-xs text-slate-400">
                Composite of ASM exposure, CSPM drift, ITDR signal, DLP egress, ZT maturity, phish
                risk, decoy engagements, and OT/ICS posture (lower is better).
              </p>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid stroke="var(--gi-border-subtle)" strokeDasharray="3 3" />
                  <XAxis dataKey="week" stroke="var(--gi-text-muted)" fontSize={11} />
                  <YAxis stroke="var(--gi-text-muted)" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--gi-bg-base)',
                      border: '1px solid var(--gi-border-subtle)',
                      borderRadius: 8,
                    }}
                    labelStyle={{ color: 'var(--gi-text-primary)' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="previous"
                    name="Last Quarter"
                    stroke="var(--gi-text-muted)"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="current"
                    name="This Quarter"
                    stroke="#22d3ee"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-slate-900/60" data-testid="zt-radial">
            <CardHeader>
              <CardTitle className="text-base">Zero Trust Maturity</CardTitle>
              <p className="text-xs text-slate-400">
                NSA ZT Maturity Model rollup across 5 pillars.
              </p>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                  innerRadius="60%"
                  outerRadius="100%"
                  data={radial}
                  startAngle={90}
                  endAngle={-270}
                >
                  <RadialBar background dataKey="uv" cornerRadius={12} fill="#22d3ee" />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--gi-bg-base)',
                      border: '1px solid var(--gi-border-subtle)',
                      borderRadius: 8,
                    }}
                  />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="-mt-44 text-center">
                <div className="text-4xl font-semibold text-white">78</div>
                <div className="text-xs text-slate-400">Advanced tier</div>
              </div>
            </CardContent>
          </Card>
        </section>

        <Card className="border-slate-800 bg-slate-900/60" data-testid="domain-compare-chart">
          <CardHeader>
            <CardTitle className="text-base">Open Critical Findings by Domain — Q1 vs Q4</CardTitle>
            <p className="text-xs text-slate-400">
              Count of high/critical findings per domain at quarter close.
            </p>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={domainCompare}>
                <CartesianGrid stroke="var(--gi-border-subtle)" strokeDasharray="3 3" />
                <XAxis dataKey="domain" stroke="var(--gi-text-muted)" fontSize={11} />
                <YAxis stroke="var(--gi-text-muted)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--gi-bg-base)',
                    border: '1px solid var(--gi-border-subtle)',
                    borderRadius: 8,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="previous" name="Last Quarter" fill="#475569" radius={[4, 4, 0, 0]} />
                <Bar dataKey="current" name="This Quarter" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Regulatory readiness */}
        <Card className="border-slate-800 bg-slate-900/60" data-testid="regulatory-readiness">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Regulatory Readiness Summary</CardTitle>
              <p className="text-xs text-slate-400">
                Linked to existing compliance framework scorecards. Click a row to open detailed
                evidence.
              </p>
            </div>
            <Link href="/compliance">
              <Button size="sm" variant="outline" data-testid="button-open-compliance">
                Open compliance center <ArrowUpRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {compliance.map((c) => (
                <Link key={c.framework} href={c.route}>
                  <div
                    className="cursor-pointer rounded-lg border border-slate-800 bg-slate-950/40 p-3 transition hover:border-[#8a8a8a]/40"
                    data-testid={`compliance-${c.framework.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-white">{c.framework}</span>
                      {c.score >= 85 ? (
                        <CheckCircle2 className="h-4 w-4 text-[#c9b787]" />
                      ) : c.score >= 75 ? (
                        <Target className="h-4 w-4 text-[#c9b787]" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-[#f5f5f5]" />
                      )}
                    </div>
                    <div className="mt-2 flex items-end justify-between">
                      <span className="text-2xl font-semibold text-white">{c.score}</span>
                      <span className="text-xs text-slate-400">{c.status}</span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-full ${
                          c.score >= 85
                            ? 'bg-[#c9b787]'
                            : c.score >= 75
                              ? 'bg-[#c9b787]'
                              : 'bg-[#f5f5f5]'
                        }`}
                        style={{ width: `${c.score}%` }}
                      />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ROI Panel */}
        <Card className="border-slate-800 bg-slate-900/60" data-testid="security-roi-panel">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">Security Investment ROI</CardTitle>
                <p className="text-xs text-slate-400">
                  Breach cost avoided this quarter, attributed to specific module interventions.
                  Methodology aligned to IBM Cost of a Data Breach 2024.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="rounded-md border border-[#c9b787]/30 bg-[#c9b787]/10 px-3 py-1.5 text-[#c9b787]">
                  <div className="text-[10px] uppercase tracking-wider">Avoided</div>
                  <div className="text-lg font-semibold">${totalAvoided.toFixed(1)}M</div>
                </div>
                <div className="rounded-md border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-slate-200">
                  <div className="text-[10px] uppercase tracking-wider">Program spend</div>
                  <div className="text-lg font-semibold">${programSpend}M</div>
                </div>
                <div className="rounded-md border border-[#8a8a8a]/30 bg-[#8a8a8a]/10 px-3 py-1.5 text-[#8a8a8a]">
                  <div className="text-[10px] uppercase tracking-wider">Net ROI</div>
                  <div className="text-lg font-semibold">{roiMultiple}×</div>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-hidden rounded-lg border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/80 text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-2 text-left">Module</th>
                    <th className="px-4 py-2 text-left">Intervention</th>
                    <th className="px-4 py-2 text-right">Cost avoided</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {roiPanel.map((r) => {
                    const Icon = r.icon;
                    return (
                      <tr
                        key={r.module}
                        className="border-t border-slate-800 hover:bg-slate-900/60"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Icon className="h-4 w-4 text-[#8a8a8a]" />
                            <span className="font-medium text-white">{r.module}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{r.intervention}</td>
                        <td className="px-4 py-3 text-right font-mono text-[#c9b787]">
                          ${r.avoided.toFixed(1)}M
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link href={r.route}>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-[#8a8a8a] hover:text-[#8a8a8a]"
                            >
                              Drill in <ArrowUpRight className="ml-1 h-3 w-3" />
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
