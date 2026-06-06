import { MicroFeedbackWidget } from '@szl-holdings/shared-ui/micro-feedback-widget';
import {
  Activity,
  DollarSign,
  FileText,
  Shield,
  Users,
} from 'lucide-react';
import { useState } from 'react';

const ACCENT = '#f5f5f5';
const DS = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    muted: 'rgba(255,255,255,0.25)',
  },
};

interface SecurityBusinessImpact {
  id: string;
  timestamp: number;
  incidentTitle: string;
  incidentType: 'breach' | 'ransomware' | 'data_exfil' | 'compliance' | 'availability';
  breachCostExposure: number;
  complianceFineExposure: number;
  affectedClients: string[];
  slaAtRisk: number;
  operationalCost: number;
  regulatoryFrameworks: string[];
  mitigationSavings: number;
  status: 'active' | 'contained' | 'resolved';
}

interface ComplianceCost {
  framework: string;
  maxFineUsd: number;
  currentExposurePct: number;
  dueDate: string;
  status: 'compliant' | 'at_risk' | 'breached';
}

const SEED_IMPACTS: SecurityBusinessImpact[] = [
  {
    id: 'si1',
    timestamp: Date.now() - 180000,
    incidentTitle: 'APT29 Lateral Movement — DC-PROD-03',
    incidentType: 'breach',
    breachCostExposure: 340000,
    complianceFineExposure: 125000,
    affectedClients: ['Northgate Corp', 'Meridian Fund', 'Pacific Logistics', '+9'],
    slaAtRisk: 12,
    operationalCost: 18500,
    regulatoryFrameworks: ['SOC 2 Type II', 'ISO 27001', 'GDPR'],
    mitigationSavings: 210000,
    status: 'active',
  },
  {
    id: 'si2',
    timestamp: Date.now() - 360000,
    incidentTitle: 'Ransomware Precursor — Shadow Copy Deletion',
    incidentType: 'ransomware',
    breachCostExposure: 890000,
    complianceFineExposure: 350000,
    affectedClients: ['All managed clients'],
    slaAtRisk: 24,
    operationalCost: 45000,
    regulatoryFrameworks: ['HIPAA', 'SOC 2', 'NIST CSF'],
    mitigationSavings: 620000,
    status: 'active',
  },
  {
    id: 'si3',
    timestamp: Date.now() - 900000,
    incidentTitle: 'Azure AD Credential Spray — 847 Attempts',
    incidentType: 'breach',
    breachCostExposure: 95000,
    complianceFineExposure: 40000,
    affectedClients: ['TechBridge Inc', 'BlueSky Ventures'],
    slaAtRisk: 3,
    operationalCost: 5200,
    regulatoryFrameworks: ['SOC 2'],
    mitigationSavings: 62000,
    status: 'contained',
  },
];

const COMPLIANCE_COSTS: ComplianceCost[] = [
  {
    framework: 'GDPR',
    maxFineUsd: 20000000,
    currentExposurePct: 12,
    dueDate: 'Q2 2026 Audit',
    status: 'at_risk',
  },
  {
    framework: 'SOC 2 Type II',
    maxFineUsd: 0,
    currentExposurePct: 8,
    dueDate: 'Annual Renewal',
    status: 'compliant',
  },
  {
    framework: 'ISO 27001',
    maxFineUsd: 0,
    currentExposurePct: 5,
    dueDate: 'Surveillance Audit',
    status: 'compliant',
  },
  {
    framework: 'HIPAA',
    maxFineUsd: 1900000,
    currentExposurePct: 22,
    dueDate: 'Q3 2026',
    status: 'at_risk',
  },
  {
    framework: 'NIST CSF',
    maxFineUsd: 0,
    currentExposurePct: 15,
    dueDate: 'Internal Review',
    status: 'at_risk',
  },
];

function formatUSD(v: number): string {
  if (v >= 1000000) return `$${(v / 1000000).toFixed(2)}M`;
  if (v >= 1000) return `$${(v / 1000).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}

function ImpactCard({ impact }: { impact: SecurityBusinessImpact }) {
  const typeColors: Record<SecurityBusinessImpact['incidentType'], string> = {
    breach: '#f5f5f5',
    ransomware: '#f5f5f5',
    data_exfil: '#c9b787',
    compliance: '#c9b787',
    availability: '#c9b787',
  };
  const tc = typeColors[impact.incidentType];
  const statusColor =
    impact.status === 'active' ? '#f5f5f5' : impact.status === 'contained' ? '#c9b787' : '#6b8f71';

  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ borderColor: `${tc}20`, background: `${tc}04` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase"
              style={{ background: `${tc}15`, color: tc }}
            >
              {impact.incidentType.replace(/_/g, ' ')}
            </span>
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{
                background: statusColor,
                boxShadow: impact.status === 'active' ? `0 0 6px ${statusColor}` : 'none',
              }}
            />
            <span className="text-[9px]" style={{ color: statusColor }}>
              {impact.status}
            </span>
          </div>
          <div className="text-[11px] font-bold text-white">{impact.incidentTitle}</div>
          <div className="text-[9px] mt-0.5 font-mono" style={{ color: DS.text.muted }}>
            {Math.round((Date.now() - impact.timestamp) / 60000)}m ago
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[8px] mb-0.5" style={{ color: DS.text.muted }}>
            breach exposure
          </div>
          <div className="text-lg font-bold font-mono" style={{ color: tc }}>
            {formatUSD(impact.breachCostExposure)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {[
          {
            label: 'Compliance Fine',
            value: formatUSD(impact.complianceFineExposure),
            color: '#c9b787',
          },
          { label: 'SLA Contracts at Risk', value: impact.slaAtRisk.toString(), color: tc },
          { label: 'Ops Cost', value: formatUSD(impact.operationalCost), color: '#d4a054' },
          {
            label: 'Mitigation Saved',
            value: formatUSD(impact.mitigationSavings),
            color: '#6b8f71',
          },
        ].map((m) => (
          <div
            key={m.label}
            className="text-center p-2 rounded-lg"
            style={{ background: 'rgba(255,255,255,0.03)' }}
          >
            <div className="text-[10px] font-bold font-mono" style={{ color: m.color }}>
              {m.value}
            </div>
            <div className="text-[8px]" style={{ color: DS.text.muted }}>
              {m.label}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-1">
        {impact.regulatoryFrameworks.map((f) => (
          <span
            key={f}
            className="text-[8px] px-1.5 py-0.5 rounded"
            style={{ background: '#c9b78712', color: '#c9b787', border: '1px solid #c9b78720' }}
          >
            {f}
          </span>
        ))}
        {impact.affectedClients.map((c) => (
          <span
            key={c}
            className="text-[8px] px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(255,255,255,0.04)',
              color: 'rgba(255,255,255,0.4)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            {c}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function BusinessSignalIntelligence() {
  const [impacts, _setImpacts] = useState<SecurityBusinessImpact[]>(SEED_IMPACTS);
  const [compliance, _setCompliance] = useState<ComplianceCost[]>(COMPLIANCE_COSTS);

  const activeImpacts = impacts.filter((i) => i.status === 'active');
  const totalBreachExposure = activeImpacts.reduce((s, i) => s + i.breachCostExposure, 0);
  const totalFineExposure = activeImpacts.reduce((s, i) => s + i.complianceFineExposure, 0);
  const totalMitigationSaved = impacts.reduce((s, i) => s + i.mitigationSavings, 0);
  const atRiskClients = new Set(activeImpacts.flatMap((i) => i.affectedClients)).size;

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <DollarSign className="w-3.5 h-3.5" style={{ color: ACCENT }} />
          <span
            className="text-[10px] font-bold uppercase tracking-widest font-mono"
            style={{ color: ACCENT }}
          >
            PARAGON · Business Signal Intelligence
          </span>
        </div>
        <h1 className="text-xl font-bold text-white">Security Business Signal Intelligence</h1>
        <p className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Every incident shows its business cost — breach exposure, compliance fine risk, SLA
          impact, and revenue correlation in a single pane.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          {
            label: 'Breach Cost Exposure',
            value: formatUSD(totalBreachExposure),
            color: ACCENT,
            pulse: true,
            icon: Shield,
          },
          {
            label: 'Compliance Fine Risk',
            value: formatUSD(totalFineExposure),
            color: '#c9b787',
            icon: FileText,
          },
          {
            label: 'At-Risk Client Accounts',
            value: atRiskClients.toString(),
            color: '#c9b787',
            icon: Users,
          },
          {
            label: 'Mitigation Value Saved',
            value: formatUSD(totalMitigationSaved),
            color: '#6b8f71',
            icon: Activity,
          },
        ].map((c) => {
          const Icon = c.icon;
          return (
            <div
              key={c.label}
              className="rounded-xl border p-4"
              style={{ borderColor: `${c.color}20`, background: `${c.color}06` }}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon className="w-3.5 h-3.5" style={{ color: c.color }} />
                <span className="text-[10px]" style={{ color: DS.text.muted }}>
                  {c.label}
                </span>
                {(c as { pulse?: boolean }).pulse && (
                  <span
                    className="w-1.5 h-1.5 rounded-full animate-pulse ml-auto"
                    style={{ background: c.color }}
                  />
                )}
              </div>
              <div className="text-xl font-bold font-mono" style={{ color: c.color }}>
                {c.value}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-3">
          <div
            className="text-[10px] font-bold uppercase tracking-wider"
            style={{ color: DS.text.muted }}
          >
            Security-to-Business Impact Correlation
          </div>
          {impacts.map((i) => (
            <ImpactCard key={i.id} impact={i} />
          ))}
        </div>

        <div className="space-y-4">
          <div
            className="rounded-xl border p-4"
            style={{ borderColor: DS.border, background: DS.surface }}
          >
            <div className="text-[10px] font-bold text-white mb-3">Compliance Cost Exposure</div>
            <div className="space-y-3">
              {compliance.map((c) => {
                const statusColor =
                  c.status === 'compliant'
                    ? '#6b8f71'
                    : c.status === 'at_risk'
                      ? '#c9b787'
                      : ACCENT;
                const potentialFine =
                  c.maxFineUsd > 0 ? formatUSD((c.maxFineUsd * c.currentExposurePct) / 100) : 'N/A';
                return (
                  <div
                    key={c.framework}
                    className="p-2 rounded-lg"
                    style={{ background: `${statusColor}08`, border: `1px solid ${statusColor}15` }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-bold text-white/80">{c.framework}</span>
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded font-bold"
                        style={{ background: `${statusColor}15`, color: statusColor }}
                      >
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div
                      className="flex items-center justify-between text-[9px]"
                      style={{ color: DS.text.muted }}
                    >
                      <span>{c.dueDate}</span>
                      {c.maxFineUsd > 0 && (
                        <span className="font-mono" style={{ color: '#c9b787' }}>
                          Max: {formatUSD(c.maxFineUsd)}
                        </span>
                      )}
                    </div>
                    <div
                      className="mt-1.5 h-1 rounded-full"
                      style={{ background: 'rgba(255,255,255,0.06)' }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${c.currentExposurePct}%`, background: statusColor }}
                      />
                    </div>
                    <div className="mt-1 text-[8px]" style={{ color: DS.text.muted }}>
                      Exposure: {c.currentExposurePct}%{' '}
                      {c.maxFineUsd > 0 ? `· Potential fine: ${potentialFine}` : ''}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            className="rounded-xl border p-4"
            style={{ borderColor: DS.border, background: DS.surface }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="text-[10px] font-bold text-white">Executive Brief</div>
              <MicroFeedbackWidget
                featureId="aegis-business-signal-brief"
                featureName="Business Signal Executive Brief"
                app="aegis"
                compact
                prompt="Useful?"
              />
            </div>
            <div className="space-y-2 text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>
              <p>
                🔴 Active incidents carry{' '}
                <strong className="text-white/80">{formatUSD(totalBreachExposure)}</strong> breach
                cost exposure and{' '}
                <strong className="text-white/80">{formatUSD(totalFineExposure)}</strong> in
                compliance fines
              </p>
              <p>
                🟡 <strong className="text-white/80">GDPR</strong> and{' '}
                <strong className="text-white/80">HIPAA</strong> require immediate attention —
                exposure above acceptable thresholds
              </p>
              <p>
                🟢 Autonomous containment has already saved{' '}
                <strong className="text-white/80">{formatUSD(totalMitigationSaved)}</strong> in
                projected breach costs
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
