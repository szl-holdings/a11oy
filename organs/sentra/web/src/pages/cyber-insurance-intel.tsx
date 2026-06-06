import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  AlertTriangle,
  DollarSign,
  FileText,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useState } from 'react';

interface RiskFactor {
  id: string;
  name: string;
  score: number;
  trend: 'improving' | 'worsening' | 'stable';
  premiumImpact: number;
  description: string;
}

interface PolicyRecommendation {
  id: string;
  title: string;
  currentValue: string;
  recommendedValue: string;
  annualSaving: number;
  rationale: string;
  priority: 'critical' | 'high' | 'medium';
}

const RISK_FACTORS: RiskFactor[] = [
  {
    id: 'rf-1',
    name: 'MFA Coverage',
    score: 94,
    trend: 'improving',
    premiumImpact: -8,
    description: '94% of privileged accounts enforcing MFA. Industry benchmark: 85%.',
  },
  {
    id: 'rf-2',
    name: 'Patch Cadence',
    score: 72,
    trend: 'stable',
    premiumImpact: 4,
    description: 'Average patch lag of 18 days for critical CVEs. Benchmark: <7 days.',
  },
  {
    id: 'rf-3',
    name: 'Incident Response Maturity',
    score: 88,
    trend: 'improving',
    premiumImpact: -5,
    description: 'Tabletop exercises completed quarterly. IR plan tested and documented.',
  },
  {
    id: 'rf-4',
    name: 'Data Encryption Coverage',
    score: 96,
    trend: 'stable',
    premiumImpact: -6,
    description: 'AES-256 at rest, TLS 1.3 in transit across 96% of data stores.',
  },
  {
    id: 'rf-5',
    name: 'Third-Party Risk',
    score: 61,
    trend: 'worsening',
    premiumImpact: 12,
    description:
      '34% of vendors lack SOC 2 attestation. 2 critical vendors missing security assessments.',
  },
  {
    id: 'rf-6',
    name: 'Employee Security Training',
    score: 82,
    trend: 'improving',
    premiumImpact: -3,
    description:
      'Phishing simulation pass rate: 89%. Annual security awareness training 97% complete.',
  },
  {
    id: 'rf-7',
    name: 'Backup & Recovery',
    score: 91,
    trend: 'stable',
    premiumImpact: -7,
    description: 'Immutable backups with air-gap. RTO: 4h. RPO: 15min. Tested quarterly.',
  },
  {
    id: 'rf-8',
    name: 'Endpoint Detection',
    score: 78,
    trend: 'improving',
    premiumImpact: -2,
    description: 'EDR deployed on 92% of endpoints. 47 workstations pending agent install.',
  },
];

const RECOMMENDATIONS: PolicyRecommendation[] = [
  {
    id: 'rec-1',
    title: 'Increase Ransomware Sublimit',
    currentValue: '$2M',
    recommendedValue: '$5M',
    annualSaving: 0,
    rationale:
      'Current sublimit below industry norm for organization size. Risk exposure from double-extortion attacks growing.',
    priority: 'critical',
  },
  {
    id: 'rec-2',
    title: 'Add Business Interruption Coverage',
    currentValue: 'None',
    recommendedValue: '$10M / 90-day waiting',
    annualSaving: 0,
    rationale:
      'Current policy excludes BI losses from cyber events. Potential exposure: $2.4M/day in downtime.',
    priority: 'high',
  },
  {
    id: 'rec-3',
    title: 'Third-Party Liability Rider',
    currentValue: '$1M',
    recommendedValue: '$5M',
    annualSaving: 0,
    rationale: 'MSP and SAAS exposure creates downstream liability risk. Increase sublimit.',
    priority: 'high',
  },
  {
    id: 'rec-4',
    title: 'Vendor Risk Program Credit',
    currentValue: 'Not claimed',
    recommendedValue: 'Claim VRM Credit',
    annualSaving: 18400,
    rationale:
      'Carrier offers 8% premium discount for documented vendor risk management programs. Currently unclaimed.',
    priority: 'medium',
  },
  {
    id: 'rec-5',
    title: 'Patch Management Credit',
    currentValue: 'Not claimed',
    recommendedValue: 'Claim after <7d lag',
    annualSaving: 12200,
    rationale: 'Reducing average patch lag from 18 to 7 days qualifies for 5% carrier credit.',
    priority: 'medium',
  },
];

const CURRENT_PREMIUM = 284000;
const ESTIMATED_PREMIUM = 247600;
const TOTAL_SAVINGS = CURRENT_PREMIUM - ESTIMATED_PREMIUM;

export default function CyberInsuranceIntel() {
  const [generating, setGenerating] = useState(false);

  const handleGenerateClaims = () => {
    setGenerating(true);
    setTimeout(() => {
      setGenerating(false);
      toast.success(
        'Claims documentation package generated — incident timeline, financial impact, and forensic evidence bundled',
      );
    }, 2500);
  };

  const avgRiskScore = Math.round(
    RISK_FACTORS.reduce((s, r) => s + r.score, 0) / RISK_FACTORS.length,
  );
  const improvingFactors = RISK_FACTORS.filter((r) => r.trend === 'improving').length;
  const totalCredits = RECOMMENDATIONS.filter((r) => r.annualSaving > 0).reduce(
    (s, r) => s + r.annualSaving,
    0,
  );

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-5 h-5 text-[#c9b787]" />
            <h1 className="text-lg font-semibold text-white">Cyber Insurance Intelligence</h1>
          </div>
          <p className="text-xs text-zinc-500">
            Automated cyber risk quantification in dollar terms, policy optimization
            recommendations, and claims documentation generation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateClaims}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#c9b787]/15 border border-[#c9b787]/30 text-[#c9b787] text-xs font-medium hover:bg-[#c9b787]/25 transition-colors"
          >
            {generating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Generating...
              </>
            ) : (
              <>
                <FileText className="w-3.5 h-3.5" /> Generate Claims Docs
              </>
            )}
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Current Annual Premium',
            value: `$${(CURRENT_PREMIUM / 1000).toFixed(0)}K`,
            sub: 'Renewal: Jun 2026',
            color: '#c9b787',
            icon: DollarSign,
          },
          {
            label: 'Estimated Optimized',
            value: `$${(ESTIMATED_PREMIUM / 1000).toFixed(0)}K`,
            sub: `Save $${(TOTAL_SAVINGS / 1000).toFixed(0)}K/yr`,
            color: '#c9b787',
            icon: TrendingDown,
          },
          {
            label: 'Risk Posture Score',
            value: `${avgRiskScore}/100`,
            sub: `${improvingFactors} factors improving`,
            color: '#8a8a8a',
            icon: Shield,
          },
          {
            label: 'Unclaimed Credits',
            value: `$${(totalCredits / 1000).toFixed(0)}K`,
            sub: 'available immediately',
            color: '#c9b787',
            icon: AlertTriangle,
          },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="rounded-xl border border-white/8 bg-white/3 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-zinc-500">{m.label}</span>
                <Icon className="w-3.5 h-3.5" style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold text-white">{m.value}</div>
              <div className="text-xs mt-0.5" style={{ color: m.color }}>
                {m.sub}
              </div>
            </div>
          );
        })}
      </div>

      {/* Premium Waterfall */}
      <div className="rounded-xl border border-white/8 bg-white/3 p-4">
        <div className="text-xs font-semibold text-zinc-300 mb-3">Premium Impact Waterfall</div>
        <div className="flex items-end gap-2 h-24">
          <div className="flex-1 flex flex-col items-center gap-1">
            <div className="w-full rounded-t bg-[#c9b787]/40" style={{ height: '100%' }} />
            <span className="text-[10px] text-zinc-500">Current</span>
            <span className="text-[10px] text-white font-medium">$284K</span>
          </div>
          {RISK_FACTORS.filter((r) => r.premiumImpact !== 0)
            .slice(0, 6)
            .map((r) => (
              <div key={r.id} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className="w-full rounded-t"
                  style={{
                    height: `${Math.abs(r.premiumImpact) * 6}%`,
                    background: r.premiumImpact < 0 ? '#c9b78740' : '#f5f5f540',
                    border: `1px solid ${r.premiumImpact < 0 ? '#c9b78760' : '#f5f5f560'}`,
                    minHeight: 8,
                  }}
                />
                <span className="text-[9px] text-zinc-500 truncate w-full text-center">
                  {r.name.split(' ')[0]}
                </span>
                <span
                  className={cn(
                    'text-[9px] font-medium',
                    r.premiumImpact < 0 ? 'text-[#c9b787]' : 'text-[#f5f5f5]',
                  )}
                >
                  {r.premiumImpact > 0 ? '+' : ''}
                  {r.premiumImpact}%
                </span>
              </div>
            ))}
          <div className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-[#c9b787]/40"
              style={{ height: `${(ESTIMATED_PREMIUM / CURRENT_PREMIUM) * 100}%` }}
            />
            <span className="text-[10px] text-zinc-500">Optimized</span>
            <span className="text-[10px] text-[#c9b787] font-medium">$248K</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Risk Factors */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Risk Posture Factors
          </h2>
          <div className="space-y-2">
            {RISK_FACTORS.map((factor) => (
              <div key={factor.id} className="rounded-xl border border-white/8 bg-white/3 p-3">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    {factor.trend === 'improving' ? (
                      <TrendingDown className="w-3.5 h-3.5 text-[#c9b787] shrink-0" />
                    ) : factor.trend === 'worsening' ? (
                      <TrendingUp className="w-3.5 h-3.5 text-[#f5f5f5] shrink-0" />
                    ) : (
                      <Activity className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                    )}
                    <span className="text-xs font-medium text-white">{factor.name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={cn(
                        'text-[10px]',
                        factor.premiumImpact < 0 ? 'text-[#c9b787]' : 'text-[#f5f5f5]',
                      )}
                    >
                      {factor.premiumImpact > 0 ? '+' : ''}
                      {factor.premiumImpact}% premium
                    </span>
                    <span className="text-xs font-bold text-white">{factor.score}</span>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-white/8 mb-1.5">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${factor.score}%`,
                      background:
                        factor.score >= 85 ? '#c9b787' : factor.score >= 70 ? '#c9b787' : '#f5f5f5',
                    }}
                  />
                </div>
                <div className="text-[10px] text-zinc-500 leading-relaxed">
                  {factor.description}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Policy Recommendations */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Policy Optimization
          </h2>
          <div className="space-y-2">
            {RECOMMENDATIONS.map((rec) => (
              <div
                key={rec.id}
                className={cn(
                  'rounded-xl border p-3',
                  rec.priority === 'critical'
                    ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/5'
                    : rec.priority === 'high'
                      ? 'border-[#c9b787]/20 bg-[#c9b787]/5'
                      : 'border-white/8 bg-white/3',
                )}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-xs font-medium text-white">{rec.title}</span>
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded border shrink-0 capitalize',
                      rec.priority === 'critical'
                        ? 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30'
                        : rec.priority === 'high'
                          ? 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30'
                          : 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30',
                    )}
                  >
                    {rec.priority}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px] mb-2">
                  <div>
                    <div className="text-zinc-500 mb-0.5">Current</div>
                    <div className="text-[#f5f5f5]">{rec.currentValue}</div>
                  </div>
                  <div>
                    <div className="text-zinc-500 mb-0.5">Recommended</div>
                    <div className="text-[#c9b787]">{rec.recommendedValue}</div>
                  </div>
                </div>
                {rec.annualSaving > 0 && (
                  <div className="text-[10px] text-[#c9b787] font-medium mb-1">
                    💰 Save ${rec.annualSaving.toLocaleString()}/year
                  </div>
                )}
                <div className="text-[10px] text-zinc-500 leading-relaxed">{rec.rationale}</div>
                <button
                  onClick={() =>
                    toast.success(`Recommendation flagged for renewal discussion with broker`)
                  }
                  className="mt-2 text-[10px] text-[#c9b787] hover:text-[#c9b787]"
                >
                  Flag for broker →
                </button>
              </div>
            ))}
          </div>

          {/* Risk Quantification */}
          <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-4 mt-3">
            <div className="text-xs font-semibold text-[#c9b787] mb-3">
              Annual Loss Expectancy (ALE) Estimate
            </div>
            <div className="space-y-2">
              {[
                { scenario: 'Ransomware Attack', ale: '$1.2M', probability: '18%' },
                { scenario: 'Business Email Compromise', ale: '$340K', probability: '34%' },
                { scenario: 'Data Breach (PII)', ale: '$2.8M', probability: '8%' },
                { scenario: 'DDoS / Business Interruption', ale: '$180K', probability: '22%' },
                { scenario: 'Insider Threat', ale: '$640K', probability: '6%' },
              ].map((item) => (
                <div key={item.scenario} className="flex items-center justify-between text-[11px]">
                  <span className="text-zinc-400">{item.scenario}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-zinc-500">{item.probability} prob.</span>
                    <span className="text-white font-medium">{item.ale}</span>
                  </div>
                </div>
              ))}
              <div className="border-t border-white/8 pt-2 flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Total ALE</span>
                <span className="text-[#f5f5f5] font-bold">$5.16M</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
