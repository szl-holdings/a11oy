// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/compliance-evidence.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertTriangle,
  CheckCircle,
  ClipboardCheck,
  Download,
  FileText,
  Package,
  RefreshCw,
  Shield,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useState } from 'react';

interface Framework {
  id: string;
  name: string;
  shortName: string;
  overallScore: number;
  controls: number;
  passing: number;
  gaps: number;
  evidenceItems: number;
  lastAudit: string;
  color: string;
}

interface EvidenceItem {
  id: string;
  title: string;
  framework: string;
  control: string;
  type: 'log' | 'screenshot' | 'config' | 'report' | 'attestation';
  collectedAt: string;
  collectedBy: 'auto' | 'manual';
  status: 'collected' | 'pending' | 'expired' | 'gap';
  expiresIn?: string;
}

const FRAMEWORKS: Framework[] = [
  {
    id: 'soc2',
    name: 'SOC 2 Type II',
    shortName: 'SOC 2',
    overallScore: 91,
    controls: 64,
    passing: 58,
    gaps: 6,
    evidenceItems: 342,
    lastAudit: 'Q1 2026',
    color: '#c9b787',
  },
  {
    id: 'iso27001',
    name: 'ISO 27001:2022',
    shortName: 'ISO 27001',
    overallScore: 87,
    controls: 93,
    passing: 81,
    gaps: 12,
    evidenceItems: 289,
    lastAudit: 'Q4 2025',
    color: '#8a8a8a',
  },
  {
    id: 'nist',
    name: 'NIST CSF 2.0',
    shortName: 'NIST CSF',
    overallScore: 84,
    controls: 108,
    passing: 91,
    gaps: 17,
    evidenceItems: 412,
    lastAudit: 'Q1 2026',
    color: '#c9b787',
  },
  {
    id: 'hipaa',
    name: 'HIPAA Security Rule',
    shortName: 'HIPAA',
    overallScore: 96,
    controls: 42,
    passing: 40,
    gaps: 2,
    evidenceItems: 187,
    lastAudit: 'Q2 2025',
    color: '#c9b787',
  },
  {
    id: 'pci',
    name: 'PCI DSS 4.0',
    shortName: 'PCI DSS',
    overallScore: 89,
    controls: 78,
    passing: 69,
    gaps: 9,
    evidenceItems: 256,
    lastAudit: 'Q1 2026',
    color: '#f5f5f5',
  },
];

const EVIDENCE: EvidenceItem[] = [
  {
    id: 'EV-001',
    title: 'Access Control Log — Monthly Review',
    framework: 'SOC 2',
    control: 'CC6.1',
    type: 'log',
    collectedAt: 'Today 00:01',
    collectedBy: 'auto',
    status: 'collected',
  },
  {
    id: 'EV-002',
    title: 'MFA Enforcement Configuration',
    framework: 'SOC 2',
    control: 'CC6.3',
    type: 'config',
    collectedAt: 'Today 00:01',
    collectedBy: 'auto',
    status: 'collected',
  },
  {
    id: 'EV-003',
    title: 'Penetration Test Report Q1 2026',
    framework: 'ISO 27001',
    control: 'A.8.8',
    type: 'report',
    collectedAt: 'Mar 15, 2026',
    collectedBy: 'manual',
    status: 'collected',
  },
  {
    id: 'EV-004',
    title: 'Data Encryption Key Management Policy',
    framework: 'NIST CSF',
    control: 'PR.DS-1',
    type: 'attestation',
    collectedAt: 'Jan 1, 2026',
    collectedBy: 'auto',
    status: 'expired',
    expiresIn: 'Expired',
  },
  {
    id: 'EV-005',
    title: 'Vendor Risk Assessment — Salesforce',
    framework: 'SOC 2',
    control: 'CC9.2',
    type: 'report',
    collectedAt: '—',
    collectedBy: 'auto',
    status: 'gap',
  },
  {
    id: 'EV-006',
    title: 'Incident Response Test Evidence',
    framework: 'HIPAA',
    control: '§164.308(a)(6)',
    type: 'screenshot',
    collectedAt: 'Feb 28, 2026',
    collectedBy: 'manual',
    status: 'collected',
  },
  {
    id: 'EV-007',
    title: 'Audit Log Integrity Verification',
    framework: 'PCI DSS',
    control: 'Req 10.3',
    type: 'log',
    collectedAt: 'Today 00:01',
    collectedBy: 'auto',
    status: 'collected',
  },
  {
    id: 'EV-008',
    title: 'Privileged Access Review',
    framework: 'SOC 2',
    control: 'CC6.2',
    type: 'attestation',
    collectedAt: 'Apr 1, 2026',
    collectedBy: 'auto',
    status: 'collected',
    expiresIn: '89 days',
  },
];

const typeIcon: Record<string, typeof FileText> = {
  log: FileText,
  screenshot: FileText,
  config: Package,
  report: FileText,
  attestation: ClipboardCheck,
};
const typeColor: Record<string, string> = {
  log: '#c9b787',
  screenshot: '#8a8a8a',
  config: '#c9b787',
  report: '#c9b787',
  attestation: '#8a8a8a',
};

const statusConfig: Record<string, string> = {
  collected: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  pending: 'text-[#c9b787] bg-[#c9b787]/10 border-[#c9b787]/30',
  expired: 'text-[#f5f5f5] bg-[#f5f5f5]/10 border-[#f5f5f5]/30',
  gap: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30',
};

export default function ComplianceEvidence() {
  const [selectedFramework, setSelectedFramework] = useState<Framework>(FRAMEWORKS[0]);
  const [generating, setGenerating] = useState(false);
  const [collecting, setCollecting] = useState(false);

  const handleGeneratePackage = () => {
    setGenerating(true);
    setTimeout(() => {
      setGenerating(false);
      toast.success(
        `${selectedFramework.shortName} audit package generated — 342 evidence items bundled into ZIP`,
      );
    }, 2500);
  };

  const handleCollectAll = () => {
    setCollecting(true);
    setTimeout(() => {
      setCollecting(false);
      toast.success(
        'Automated evidence collection complete — 47 new items collected from 12 data sources',
      );
    }, 2000);
  };

  const totalEvidence = FRAMEWORKS.reduce((s, f) => s + f.evidenceItems, 0);
  const totalGaps = FRAMEWORKS.reduce((s, f) => s + f.gaps, 0);

  return (
    <div className="p-6 space-y-6 max-w-full">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ClipboardCheck className="w-5 h-5 text-[#c9b787]" />
            <h1 className="text-lg font-semibold text-white">Compliance Evidence Engine</h1>
          </div>
          <p className="text-xs text-zinc-500">
            Automated evidence collection mapped to SOC 2, ISO 27001, NIST CSF, HIPAA, and PCI DSS.
            Audit packages generated on demand.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCollectAll}
            disabled={collecting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300 text-xs hover:bg-white/8 transition-colors"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', collecting && 'animate-spin')} /> Collect
            Evidence
          </button>
          <button
            onClick={handleGeneratePackage}
            disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#c9b787]/15 border border-[#c9b787]/30 text-[#c9b787] text-xs font-medium hover:bg-[#c9b787]/25 transition-colors"
          >
            {generating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Generating...
              </>
            ) : (
              <>
                <Download className="w-3.5 h-3.5" /> Generate Audit Package
              </>
            )}
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: 'Frameworks Monitored',
            value: FRAMEWORKS.length,
            sub: 'continuous compliance',
            color: '#c9b787',
            icon: Shield,
          },
          {
            label: 'Total Evidence Items',
            value: totalEvidence.toLocaleString(),
            sub: 'auto-collected',
            color: '#c9b787',
            icon: Package,
          },
          {
            label: 'Compliance Gaps',
            value: totalGaps,
            sub: 'requiring remediation',
            color: '#f5f5f5',
            icon: AlertTriangle,
          },
          {
            label: 'Avg Readiness',
            value: `${Math.round(FRAMEWORKS.reduce((s, f) => s + f.overallScore, 0) / FRAMEWORKS.length)}%`,
            sub: 'across all frameworks',
            color: '#8a8a8a',
            icon: TrendingUp,
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
              <div className="text-xs text-zinc-500 mt-0.5">{m.sub}</div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Framework Scores */}
        <div>
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            Framework Compliance
          </h2>
          <div className="space-y-2">
            {FRAMEWORKS.map((fw) => (
              <button
                key={fw.id}
                onClick={() => setSelectedFramework(fw)}
                className={cn(
                  'w-full rounded-xl border p-3 text-left transition-all',
                  selectedFramework.id === fw.id
                    ? 'border-[#c9b787]/30 bg-[#c9b787]/5'
                    : 'border-white/8 bg-white/3 hover:bg-white/5',
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div>
                    <div className="text-xs font-medium text-white">{fw.name}</div>
                    <div className="text-[10px] text-zinc-500 mt-0.5">
                      Last audit: {fw.lastAudit}
                    </div>
                  </div>
                  <span className="text-xl font-bold" style={{ color: fw.color }}>
                    {fw.overallScore}%
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-white/8 mb-1.5">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${fw.overallScore}%`, background: `${fw.color}80` }}
                  />
                </div>
                <div className="flex items-center gap-4 text-[10px] text-zinc-500">
                  <span className="text-[#c9b787]">{fw.passing} passing</span>
                  <span className="text-[#f5f5f5]">{fw.gaps} gaps</span>
                  <span className="ml-auto">{fw.evidenceItems} items</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Evidence Items */}
        <div className="xl:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Evidence Library
            </h2>
            <div className="flex items-center gap-2 text-[10px] text-zinc-500">
              <span className="text-[#c9b787]">●</span> Collected
              <span className="text-[#f5f5f5]">●</span> Gap
              <span className="text-[#c9b787]">●</span> Expired
            </div>
          </div>
          <div className="space-y-2">
            {EVIDENCE.map((item) => {
              const Icon = typeIcon[item.type] ?? FileText;
              return (
                <div
                  key={item.id}
                  className={cn(
                    'rounded-xl border p-3',
                    item.status === 'gap'
                      ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/5'
                      : item.status === 'expired'
                        ? 'border-[#c9b787]/20 bg-[#c9b787]/5'
                        : 'border-white/8 bg-white/3',
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ background: `${typeColor[item.type]}15` }}
                    >
                      <Icon className="w-3.5 h-3.5" style={{ color: typeColor[item.type] }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-medium text-white leading-snug">
                          {item.title}
                        </span>
                        <span
                          className={cn(
                            'text-[10px] px-1.5 py-0.5 rounded border shrink-0 capitalize',
                            statusConfig[item.status],
                          )}
                        >
                          {item.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-[10px] text-zinc-500">
                        <span>{item.framework}</span>
                        <span>·</span>
                        <span>{item.control}</span>
                        <span>·</span>
                        <span>{item.collectedBy === 'auto' ? '⚡ Auto-collected' : 'Manual'}</span>
                        {item.collectedAt !== '—' && <span>· {item.collectedAt}</span>}
                      </div>
                      {item.expiresIn && (
                        <div
                          className={cn(
                            'text-[10px] mt-1',
                            item.status === 'expired' ? 'text-[#f5f5f5]' : 'text-zinc-500',
                          )}
                        >
                          Expires: {item.expiresIn}
                        </div>
                      )}
                      {item.status === 'gap' && (
                        <button
                          onClick={() =>
                            toast.success('Evidence collection task created and assigned')
                          }
                          className="mt-1.5 text-[10px] text-[#f5f5f5] hover:text-[#f5f5f5]"
                        >
                          + Assign collection task →
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Collection Coverage */}
          <div className="rounded-xl border border-[#c9b787]/20 bg-[#c9b787]/5 p-4 mt-3">
            <div className="text-xs font-semibold text-[#c9b787] mb-3 flex items-center gap-2">
              <Zap className="w-3.5 h-3.5" />
              Automated Collection Sources ({12} active)
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
              {[
                'SIEM Event Logs',
                'EDR Telemetry',
                'Cloud Config (AWS/Azure)',
                'IAM Access Reviews',
                'Vulnerability Scans',
                'Network Flow Logs',
                'Change Management DB',
                'HR Offboarding Records',
                'MFA Compliance Reports',
                'Firewall Rule Export',
                'Patch Status Reports',
                'Encryption Key Audits',
              ].map((src) => (
                <div key={src} className="flex items-center gap-1.5 text-[10px] text-zinc-400">
                  <CheckCircle className="w-3 h-3 text-[#c9b787] shrink-0" />
                  {src}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
