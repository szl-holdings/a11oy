
import {
  AlertTriangle,
  Brain,
  Building2,
  CheckCircle,
  ChevronRight,
  Clock,
  Download,
  FileText,
  Lock,
  Scale,
  Share2,
  Shield,
  Target,
  TrendingDown,
  Users,
  Zap,
} from 'lucide-react';
import { useState } from 'react';

const DS = {
  bg: '#070b12',
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    muted: 'rgba(255,255,255,0.25)',
  },
};

const AAR = {
  crisisId: 'CRS-2024-001',
  crisisName: 'APT29 Enterprise Infiltration',
  type: 'CYBERATTACK',
  severity: 'critical',
  declaredAt: '2024-01-15 14:22 UTC',
  resolvedAt: '2024-01-16 09:14 UTC',
  durationH: 18.9,
  reportGeneratedAt: '2024-01-17 10:00 UTC',
  commanderName: 'J. Chen',
  reportVersion: 'v1.0 — Final',
  executiveSummary:
    'On January 15, 2024 at 14:22 UTC, PARAGON SIEM detected APT29-attributed lateral movement on production asset DC-PROD-03. Incident Command was declared at ICS Level 3 within 2 minutes. Through coordinated containment, the active threat was severed within 28 minutes of the initial host isolation decision. Forensic evidence was preserved, managed clients were proactively notified, and external IR (CrowdStrike) was engaged for deep attribution. No data exfiltration was confirmed. The Northgate migration SLA was temporarily suspended. Regulatory breach notification review determined notification obligations were not triggered (no PII accessed). Full remediation was completed in 18.9 hours.',
};

const METRICS = [
  {
    label: 'Time to Detection',
    value: '0m',
    sublabel: 'SIEM alerted within 30s of lateral movement',
    icon: Target,
    trend: 'good',
    benchmark: 'Industry avg: 197 days',
  },
  {
    label: 'Time to IC Declaration',
    value: '2m',
    sublabel: 'Crisis declared at T+2m by J. Chen',
    icon: Clock,
    trend: 'good',
    benchmark: 'Target: <5m',
  },
  {
    label: 'Time to First Containment',
    value: '28m',
    sublabel: 'DC-PROD-03 isolated at T+28m',
    icon: Shield,
    trend: 'good',
    benchmark: 'Target: <60m',
  },
  {
    label: 'Time to C2 Severance',
    value: '30m',
    sublabel: 'Beacon severed at T+30m',
    icon: Zap,
    trend: 'good',
    benchmark: 'Target: <45m',
  },
  {
    label: 'Full Containment',
    value: '47m',
    sublabel: 'All lateral paths blocked at T+47m',
    icon: Shield,
    trend: 'good',
    benchmark: 'Target: <90m',
  },
  {
    label: 'Total Duration',
    value: '18.9h',
    sublabel: 'Declared to resolution',
    icon: Clock,
    trend: 'neutral',
    benchmark: 'APT avg: 72h',
  },
  {
    label: 'Assets Impacted',
    value: '4',
    sublabel: 'DC-PROD-03 + 3 adjacent hosts swept',
    icon: Building2,
    trend: 'neutral',
    benchmark: '',
  },
  {
    label: 'Clients Notified',
    value: '1',
    sublabel: 'Northgate CISO · proactive notification',
    icon: Users,
    trend: 'good',
    benchmark: '',
  },
  {
    label: 'Confirmed Exfil',
    value: 'None',
    sublabel: 'S3 staging blocked before data left perimeter',
    icon: Lock,
    trend: 'good',
    benchmark: '',
  },
  {
    label: 'Regulatory Notifications',
    value: '0 Required',
    sublabel: 'Legal review: threshold not met',
    icon: Scale,
    trend: 'good',
    benchmark: '',
  },
  {
    label: 'Decisions Logged',
    value: '5',
    sublabel: 'All with rationale and approver',
    icon: FileText,
    trend: 'good',
    benchmark: '',
  },
  {
    label: 'Breach Exposure Mitigated',
    value: '$17.4M',
    sublabel: 'Potential exposure contained',
    icon: TrendingDown,
    trend: 'good',
    benchmark: '',
  },
];

const TIMELINE_SUMMARY = [
  { time: 'T+0m', event: 'SIEM detection · APT29 lateral movement on DC-PROD-03', type: 'detect' },
  {
    time: 'T+2m',
    event: 'ICS Level 3 declared · Crisis response activated · PB-APT-001 initiated',
    type: 'escalate',
  },
  {
    time: 'T+4m',
    event: 'Labs pre-detection confirmed (8m ahead of SIEM) · INC-2846 C2 beacon linked',
    type: 'intel',
  },
  {
    time: 'T+7m',
    event: 'Northgate CISO notified · TKT-4827 placed on security hold',
    type: 'notify',
  },
  {
    time: 'T+9m',
    event: 'Forensic evidence preservation initiated · Memory dump ordered',
    type: 'action',
  },
  {
    time: 'T+13m',
    event: 'CVE-2024-3400 (PA FW) identified as initial access vector · Correlated to campaign',
    type: 'intel',
  },
  {
    time: 'T+16m',
    event: 'Decision: Hold EDR isolation for 15m evidence window · Rationale logged',
    type: 'decision',
  },
  {
    time: 'T+25m',
    event: 'S3 exfil pattern (ALT-5821) detected and blocked at edge',
    type: 'action',
  },
  {
    time: 'T+28m',
    event: 'EDR isolation executed on DC-PROD-03 (dual-approval: J. Chen + S. Park)',
    type: 'action',
  },
  {
    time: 'T+30m',
    event: 'C2 beacon severed by network defense · Re-establishment attempts blocked',
    type: 'action',
  },
  {
    time: 'T+41m',
    event: 'Primary containment complete · Attribution confidence 94% · Exec brief delivered',
    type: 'complete',
  },
  {
    time: 'T+60m',
    event: 'Adjacent host sweep complete · No implants found · CrowdStrike IR engaged',
    type: 'action',
  },
  {
    time: 'T+18.9h',
    event:
      'Full remediation complete · Firewall patched · Credentials rotated · Post-incident hardening verified',
    type: 'complete',
  },
];

const EVENT_COLORS: Record<string, string> = {
  detect: '#f5f5f5',
  escalate: '#c9b787',
  intel: '#8a8a8a',
  notify: '#22d3ee',
  action: '#c9b787',
  decision: '#c9b787',
  complete: '#c9b787',
};

const WHAT_WENT_WELL = [
  'Labs Neural Explorer pre-detected APT29 pattern 8 minutes before SIEM alert — accelerating total response by ~12 minutes.',
  'Evidence preservation decision (hold EDR isolation for 15-minute forensic window) resulted in complete memory dump enabling full kill chain reconstruction.',
  'S3 exfiltration pattern (ALT-5821) detected and blocked before data left the perimeter — preventing double-extortion leverage.',
  'Northgate CISO was notified proactively at T+7m, exceeding contractual notification SLA and preserving client trust.',
  'All 5 decisions were logged with explicit rationale, approver, and outcome — creating a clean audit trail for regulatory review.',
  'Incident Commander declared crisis at T+2m, well within the 5-minute target threshold. Crisis response coordination was efficient.',
  'Legal (PRISM) confirmed no regulatory breach notification required — regulatory risk was proactively assessed and closed within 48h.',
];

const IMPROVEMENT_AREAS = [
  'CVE-2024-3400 on FW-EDGE-01 was unpatched at time of incident. Patch management cadence for perimeter devices needs a 48-hour SLA for critical CVEs.',
  'EDR isolation required dual-approval from IC + Analyst, creating a 12-minute gap between detection and isolation decision. Explore pre-authorized isolation thresholds for confirmed P1 APT scenarios.',
  'CrowdStrike IR engagement was delayed to T+41m due to procurement hold. Pre-approved IR retainer should be executed — eliminates approval latency.',
  "Northgate's migration ticket #4827 was blocked for 18.9 hours, creating an unplanned SLA breach. Client incident communication protocol needs a 'migration hold' clause in MSA.",
  'Labs neural explorer alert was surfaced in the intel workspace, not auto-promoted to Defense SOC. Signal routing from Labs to SOC should be automated for high-confidence APT patterns.',
];

const AI_RECOMMENDATIONS = [
  {
    priority: 'critical',
    title: 'Emergency Patch Protocol for Perimeter Devices',
    detail:
      'Implement automated critical CVE patching within 48 hours for perimeter devices. CVE-2024-3400 was publicly known for 6 days before exploitation. Tooling: integrate CVE feed with EDR + patch management auto-deployment pipeline.',
    effort: 'Medium',
    impact: 'High',
  },
  {
    priority: 'high',
    title: 'Pre-Authorized Isolation Thresholds',
    detail:
      'Define automated isolation triggers for confirmed APT lateral movement at Confidence ≥ 90% + P1 classification — no HITL required. Estimated time savings: 12-15 minutes per future incident. Legal sign-off required.',
    effort: 'Low',
    impact: 'High',
  },
  {
    priority: 'high',
    title: 'IR Retainer — Immediate Execution',
    detail:
      'Execute CrowdStrike/Mandiant IR retainer before next fiscal quarter. Pre-positioned retainer eliminates procurement lag (estimated 18-30 min savings in future activations).',
    effort: 'Low',
    impact: 'Medium',
  },
  {
    priority: 'high',
    title: 'Labs → SOC Automated Signal Routing',
    detail:
      'Implement automated escalation from Labs neural explorer to SOC Defense when APT confidence ≥ 85%. Currently requires manual bridge. This gap cost ~8 minutes in this incident.',
    effort: 'Medium',
    impact: 'High',
  },
  {
    priority: 'medium',
    title: 'MSA Amendment — Security Incident Hold Clause',
    detail:
      "Amend managed services agreements to include a 'Security Incident Migration Hold' provision. Eliminates SLA ambiguity during concurrent security events and managed client work.",
    effort: 'Low',
    impact: 'Medium',
  },
  {
    priority: 'medium',
    title: 'Network Micro-Segmentation Review',
    detail:
      "DC-PROD-03's lateral reachability to adjacent hosts was a compounding factor. Implement east-west traffic micro-segmentation for production infrastructure. 90-day project estimate.",
    effort: 'High',
    impact: 'High',
  },
];

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#c9b787',
};

type AARSection = 'executive' | 'metrics' | 'timeline' | 'analysis' | 'recommendations';

export default function CitadelAfterAction() {
  const [activeSection, setActiveSection] = useState<AARSection>('executive');
  const [expandedRec, setExpandedRec] = useState<number | null>(null);

  return (
    <div
      className="flex h-full overflow-hidden"
      style={{ background: DS.bg, color: DS.text.primary }}
    >
      <div
        className="w-52 shrink-0 border-r overflow-y-auto"
        style={{ borderColor: DS.border, background: 'rgba(5,10,20,0.95)' }}
      >
        <div className="px-4 py-3 border-b" style={{ borderColor: DS.border }}>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded flex items-center justify-center"
              style={{
                background: 'rgba(245,245,245,0.15)',
                border: '1px solid rgba(245,245,245,0.25)',
              }}
            >
              <FileText className="w-3.5 h-3.5 text-[#f5f5f5]" />
            </div>
            <div>
              <p className="text-[11px] font-bold" style={{ color: DS.text.primary }}>
                After-Action Report
              </p>
              <p className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
                {AAR.reportVersion}
              </p>
            </div>
          </div>
        </div>
        <div className="p-2 space-y-0.5">
          {(
            [
              { id: 'executive', label: 'Executive Summary' },
              { id: 'metrics', label: 'Response Metrics' },
              { id: 'timeline', label: 'Crisis Timeline' },
              { id: 'analysis', label: 'Lessons Learned' },
              { id: 'recommendations', label: 'AI Recommendations' },
            ] as { id: AARSection; label: string }[]
          ).map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveSection(id)}
              className="w-full text-left px-3 py-2 rounded-lg text-[10px] font-medium transition-all"
              style={{
                background: activeSection === id ? 'rgba(245,245,245,0.12)' : 'transparent',
                color: activeSection === id ? '#f5f5f5' : DS.text.muted,
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="p-3 border-t space-y-1.5" style={{ borderColor: DS.border }}>
          <button
            className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all"
            style={{
              background: 'rgba(255,255,255,0.05)',
              color: DS.text.secondary,
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <Download className="w-3 h-3" />
            Export PDF
          </button>
          <button
            className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all"
            style={{
              background: 'rgba(255,255,255,0.03)',
              color: DS.text.muted,
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            <Share2 className="w-3 h-3" />
            Share Report
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl px-6 py-5">
          {activeSection === 'executive' && (
            <div className="space-y-5">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold"
                    style={{ background: 'rgba(245,245,245,0.15)', color: '#f5f5f5' }}
                  >
                    AFTER-ACTION REPORT
                  </span>
                  <span className="text-[9px] font-mono" style={{ color: DS.text.muted }}>
                    {AAR.crisisId}
                  </span>
                </div>
                <h1 className="text-xl font-bold mb-1" style={{ color: DS.text.primary }}>
                  {AAR.crisisName}
                </h1>
                <div
                  className="flex items-center gap-4 text-[10px] font-mono flex-wrap"
                  style={{ color: DS.text.muted }}
                >
                  <span>Declared: {AAR.declaredAt}</span>
                  <span>Resolved: {AAR.resolvedAt}</span>
                  <span>Duration: {AAR.durationH}h</span>
                  <span>IC: {AAR.commanderName}</span>
                  <span>Generated: {AAR.reportGeneratedAt}</span>
                </div>
              </div>

              <div
                className="rounded-xl p-4"
                style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
              >
                <p
                  className="text-[10px] font-bold uppercase tracking-wider mb-3"
                  style={{ color: DS.text.muted }}
                >
                  Executive Summary
                </p>
                <p className="text-[11px] leading-relaxed" style={{ color: DS.text.secondary }}>
                  {AAR.executiveSummary}
                </p>
              </div>

              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Total Duration', value: `${AAR.durationH}h`, color: '#c9b787' },
                  { label: 'Containment', value: '47m', color: '#c9b787' },
                  { label: 'Exfil Confirmed', value: 'None', color: '#c9b787' },
                  { label: 'Breach Exposure', value: '$17.4M\nMitigated', color: '#c9b787' },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-xl p-3 text-center"
                    style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                  >
                    <p
                      className="text-[8px] uppercase tracking-wider mb-1"
                      style={{ color: DS.text.muted }}
                    >
                      {item.label}
                    </p>
                    <p
                      className="text-[14px] font-bold whitespace-pre-line leading-tight"
                      style={{ color: item.color }}
                    >
                      {item.value}
                    </p>
                  </div>
                ))}
              </div>

              <div
                className="rounded-xl p-4"
                style={{
                  background: 'rgba(201,183,135,0.04)',
                  border: '1px solid rgba(201,183,135,0.15)',
                }}
              >
                <p
                  className="text-[10px] font-bold uppercase tracking-wider mb-2"
                  style={{ color: 'rgba(201,183,135,0.6)' }}
                >
                  Outcome: Successful Containment
                </p>
                <p className="text-[10px] leading-relaxed" style={{ color: DS.text.secondary }}>
                  The incident was contained within 47 minutes of declaration with no confirmed data
                  exfiltration, no regulatory breach notification required, and client impact
                  limited to a planned migration delay. Post-incident attribution confirmed APT29
                  and all persistence mechanisms were removed. The PARAGON platform's pre-detection
                  capability (Labs neural explorer) provided critical early warning and is credited
                  with materially accelerating response time.
                </p>
              </div>
            </div>
          )}

          {activeSection === 'metrics' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-[13px] font-bold mb-0.5" style={{ color: DS.text.primary }}>
                  Response Metrics
                </h2>
                <p className="text-[10px]" style={{ color: DS.text.muted }}>
                  Performance against targets and industry benchmarks
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {METRICS.map((m, i) => {
                  const Icon = m.icon;
                  const trendColor =
                    m.trend === 'good' ? '#c9b787' : m.trend === 'bad' ? '#f5f5f5' : DS.text.muted;
                  return (
                    <div
                      key={i}
                      className="rounded-xl p-3"
                      style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-3.5 h-3.5 shrink-0" style={{ color: trendColor }} />
                        <span
                          className="text-[9px] uppercase tracking-wider font-semibold"
                          style={{ color: DS.text.muted }}
                        >
                          {m.label}
                        </span>
                        {m.trend === 'good' && (
                          <CheckCircle className="w-3 h-3 ml-auto" style={{ color: '#c9b787' }} />
                        )}
                      </div>
                      <p className="text-[16px] font-bold" style={{ color: trendColor }}>
                        {m.value}
                      </p>
                      <p className="text-[9px] leading-snug" style={{ color: DS.text.muted }}>
                        {m.sublabel}
                      </p>
                      {m.benchmark && (
                        <p className="text-[8px] mt-1 font-mono" style={{ color: DS.text.muted }}>
                          Benchmark: {m.benchmark}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeSection === 'timeline' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-[13px] font-bold mb-0.5" style={{ color: DS.text.primary }}>
                  Crisis Timeline
                </h2>
                <p className="text-[10px]" style={{ color: DS.text.muted }}>
                  Complete chronological record — {TIMELINE_SUMMARY.length} key events
                </p>
              </div>
              <div className="space-y-0">
                {TIMELINE_SUMMARY.map((e, i) => (
                  <div key={i} className="flex gap-3 relative">
                    {i < TIMELINE_SUMMARY.length - 1 && (
                      <div
                        className="absolute left-[14px] top-7 w-px"
                        style={{
                          height: 'calc(100% - 8px)',
                          background: `${EVENT_COLORS[e.type]}20`,
                        }}
                      />
                    )}
                    <div className="flex flex-col items-center shrink-0 pt-1">
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center"
                        style={{
                          background: `${EVENT_COLORS[e.type]}15`,
                          border: `1px solid ${EVENT_COLORS[e.type]}30`,
                        }}
                      >
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ background: EVENT_COLORS[e.type] }}
                        />
                      </div>
                    </div>
                    <div className="flex-1 pb-3">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span
                          className="text-[10px] font-mono font-bold"
                          style={{ color: EVENT_COLORS[e.type] }}
                        >
                          {e.time}
                        </span>
                      </div>
                      <p className="text-[10px] leading-snug" style={{ color: DS.text.secondary }}>
                        {e.event}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'analysis' && (
            <div className="space-y-5">
              <div>
                <h2 className="text-[13px] font-bold mb-0.5" style={{ color: DS.text.primary }}>
                  Lessons Learned
                </h2>
                <p className="text-[10px]" style={{ color: DS.text.muted }}>
                  What worked, what didn't, and what changes are needed
                </p>
              </div>

              <div
                className="rounded-xl overflow-hidden"
                style={{ border: '1px solid rgba(201,183,135,0.2)' }}
              >
                <div
                  className="px-4 py-2 border-b"
                  style={{
                    background: 'rgba(201,183,135,0.05)',
                    borderColor: 'rgba(201,183,135,0.12)',
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    <CheckCircle className="w-3.5 h-3.5 text-[#c9b787]" />
                    <span
                      className="text-[10px] font-bold uppercase tracking-wider"
                      style={{ color: 'rgba(201,183,135,0.7)' }}
                    >
                      What Went Well — {WHAT_WENT_WELL.length} items
                    </span>
                  </div>
                </div>
                <div className="divide-y" style={{ borderColor: 'rgba(201,183,135,0.08)' }}>
                  {WHAT_WENT_WELL.map((item, i) => (
                    <div key={i} className="flex gap-3 px-4 py-3">
                      <span
                        className="text-[9px] font-bold font-mono mt-0.5 shrink-0"
                        style={{ color: 'rgba(201,183,135,0.5)' }}
                      >
                        W{i + 1}
                      </span>
                      <p
                        className="text-[10px] leading-relaxed"
                        style={{ color: DS.text.secondary }}
                      >
                        {item}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div
                className="rounded-xl overflow-hidden"
                style={{ border: '1px solid rgba(201,183,135,0.2)' }}
              >
                <div
                  className="px-4 py-2 border-b"
                  style={{
                    background: 'rgba(201,183,135,0.05)',
                    borderColor: 'rgba(201,183,135,0.12)',
                  }}
                >
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-[#c9b787]" />
                    <span
                      className="text-[10px] font-bold uppercase tracking-wider"
                      style={{ color: 'rgba(201,183,135,0.7)' }}
                    >
                      Areas for Improvement — {IMPROVEMENT_AREAS.length} items
                    </span>
                  </div>
                </div>
                <div className="divide-y" style={{ borderColor: 'rgba(201,183,135,0.08)' }}>
                  {IMPROVEMENT_AREAS.map((item, i) => (
                    <div key={i} className="flex gap-3 px-4 py-3">
                      <span
                        className="text-[9px] font-bold font-mono mt-0.5 shrink-0"
                        style={{ color: 'rgba(201,183,135,0.5)' }}
                      >
                        I{i + 1}
                      </span>
                      <p
                        className="text-[10px] leading-relaxed"
                        style={{ color: DS.text.secondary }}
                      >
                        {item}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'recommendations' && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="flex items-center gap-1.5">
                  <Brain className="w-4 h-4 text-[#8a8a8a]" />
                  <h2 className="text-[13px] font-bold" style={{ color: DS.text.primary }}>
                    AI-Generated Recommendations
                  </h2>
                </div>
                <span
                  className="text-[8px] px-1.5 py-0.5 rounded uppercase font-bold"
                  style={{ background: 'rgba(138,138,138,0.15)', color: '#c9b787' }}
                >
                  Counsel INTELLIGENCE
                </span>
              </div>
              <p className="text-[10px]" style={{ color: DS.text.muted }}>
                Recommendations generated by Counsel based on incident timeline, root cause analysis,
                and cross-incident pattern matching across platform history.
              </p>
              <div className="space-y-2">
                {AI_RECOMMENDATIONS.map((rec, i) => {
                  const isExpanded = expandedRec === i;
                  const color = PRIORITY_COLORS[rec.priority] ?? '#4a6070';
                  return (
                    <div
                      key={i}
                      className="rounded-xl overflow-hidden"
                      style={{ border: `1px solid ${isExpanded ? `${color}30` : DS.border}` }}
                    >
                      <button
                        onClick={() => setExpandedRec(isExpanded ? null : i)}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-all"
                        style={{ background: isExpanded ? `${color}06` : DS.surface }}
                      >
                        <div
                          className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold"
                          style={{ background: `${color}15`, color }}
                        >
                          R{i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <span
                              className="text-[11px] font-semibold"
                              style={{ color: DS.text.primary }}
                            >
                              {rec.title}
                            </span>
                            <span
                              className="text-[7px] px-1.5 py-0.5 rounded uppercase font-bold shrink-0"
                              style={{ background: `${color}15`, color }}
                            >
                              {rec.priority}
                            </span>
                          </div>
                          <div className="flex gap-3">
                            <span className="text-[9px]" style={{ color: DS.text.muted }}>
                              Effort: <span style={{ color: DS.text.secondary }}>{rec.effort}</span>
                            </span>
                            <span className="text-[9px]" style={{ color: DS.text.muted }}>
                              Impact: <span style={{ color: DS.text.secondary }}>{rec.impact}</span>
                            </span>
                          </div>
                        </div>
                        <ChevronRight
                          className="w-3.5 h-3.5 shrink-0 transition-transform"
                          style={{
                            color: DS.text.muted,
                            transform: isExpanded ? 'rotate(90deg)' : 'none',
                          }}
                        />
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-4 border-t" style={{ borderColor: `${color}15` }}>
                          <p
                            className="text-[10px] leading-relaxed pt-3"
                            style={{ color: DS.text.secondary }}
                          >
                            {rec.detail}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div
                className="rounded-xl p-4 mt-4"
                style={{
                  background: 'rgba(138,138,138,0.05)',
                  border: '1px solid rgba(138,138,138,0.15)',
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="w-3.5 h-3.5 text-[#8a8a8a]" />
                  <span className="text-[10px] font-bold" style={{ color: '#c9b787' }}>
                    Counsel Analysis Methodology
                  </span>
                </div>
                <p className="text-[10px] leading-relaxed" style={{ color: DS.text.muted }}>
                  Recommendations generated by cross-referencing: (1) incident timeline and decision
                  log, (2) root cause analysis from forensic artifacts, (3) pattern matching against
                  847 similar incidents in training corpus, (4) industry benchmark data (Verizon
                  DBIR, IBM Cost of a Data Breach 2024), (5) regulatory requirement mapping for
                  applicable jurisdictions. All recommendations require human review and approval
                  before implementation.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
