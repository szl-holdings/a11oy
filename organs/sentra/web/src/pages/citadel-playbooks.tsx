
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Brain,
  Building2,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  FileText,
  Flame,
  Lock,
  Play,
  Radio,
  Scale,
  Shield,
  Target,
  TrendingDown,
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

const SEV: Record<string, string> = {
  critical: '#f5f5f5',
  high: '#c9b787',
  medium: '#c9b787',
  low: '#c9b787',
};

interface PlaybookStep {
  id: string;
  seq: number;
  name: string;
  type:
    | 'action'
    | 'decision'
    | 'notify'
    | 'escalate'
    | 'assess'
    | 'contain'
    | 'eradicate'
    | 'recover'
    | 'review';
  auto: boolean;
  assignee?: string;
  sla?: string;
  detail: string;
  dependsOn?: string[];
  status?: 'completed' | 'active' | 'pending' | 'skipped';
  timeWindow?: string;
}

interface EscalationRule {
  trigger: string;
  condition: string;
  action: string;
  level: string;
  notifyList: string[];
}

interface Playbook {
  id: string;
  name: string;
  scenario: string;
  category: string;
  severity: 'critical' | 'high' | 'medium';
  icon: typeof Shield;
  color: string;
  description: string;
  executions: number;
  successRate: number;
  avgContainmentMin: number;
  lastUsed?: string;
  active?: boolean;
  steps: PlaybookStep[];
  escalationRules: EscalationRule[];
  roleAssignments: { role: string; responsibilities: string }[];
}

const STEP_COLORS: Record<string, string> = {
  action: '#c9b787',
  decision: '#c9b787',
  notify: '#22d3ee',
  escalate: '#c9b787',
  assess: '#8a8a8a',
  contain: '#f5f5f5',
  eradicate: '#f5f5f5',
  recover: '#c9b787',
  review: '#4a6070',
};

const STEP_ICONS: Record<string, typeof Shield> = {
  action: Zap,
  decision: Brain,
  notify: Radio,
  escalate: AlertTriangle,
  assess: Target,
  contain: Shield,
  eradicate: Flame,
  recover: Activity,
  review: FileText,
};

const PLAYBOOKS: Playbook[] = [
  {
    id: 'PB-APT-001',
    name: 'APT Infiltration Response',
    scenario: 'Advanced Persistent Threat',
    category: 'Cyberattack',
    severity: 'critical',
    icon: Shield,
    color: '#f5f5f5',
    description:
      'Full-spectrum response to confirmed APT intrusion — covering initial triage, forensic preservation, containment, eradication, attribution, and post-incident hardening.',
    executions: 3,
    successRate: 100,
    avgContainmentMin: 47,
    lastUsed: 'Active now',
    active: true,
    steps: [
      {
        id: 'S001',
        seq: 1,
        name: 'Alert Validation & Triage',
        type: 'assess',
        auto: true,
        sla: '5m',
        detail:
          'Validate SIEM alert. Cross-reference with threat intel feeds. Determine confidence score and affected assets. Open incident ticket.',
        status: 'completed',
      },
      {
        id: 'S002',
        seq: 2,
        name: 'Crisis Declaration',
        type: 'escalate',
        auto: false,
        assignee: 'SOC Lead',
        sla: '10m',
        detail:
          'If confidence ≥ 85% and production assets affected: declare a crisis. Set ICS level. Activate crisis response. Page incident commander.',
        status: 'completed',
      },
      {
        id: 'S003',
        seq: 3,
        name: 'Evidence Preservation Window',
        type: 'contain',
        auto: false,
        assignee: 'Forensics Lead',
        sla: '15m',
        detail:
          'Order memory dump on affected hosts. Preserve logs on adjacent systems. Initiate chain of custody. Do NOT isolate yet.',
        status: 'completed',
      },
      {
        id: 'S004',
        seq: 4,
        name: 'Threat Actor Attribution',
        type: 'assess',
        auto: true,
        sla: '20m',
        detail:
          'Run TTP matching against MITRE ATT&CK. Cross-reference C2 infrastructure. Query threat intel for actor profile. Confidence scoring.',
        status: 'completed',
      },
      {
        id: 'S005',
        seq: 5,
        name: 'Client Impact Assessment',
        type: 'assess',
        auto: false,
        assignee: 'MSP Lead',
        sla: '15m',
        detail:
          'Identify managed client assets in blast radius. Notify client CISOs. Assess SLA implications. Activate client communication protocol.',
        status: 'completed',
      },
      {
        id: 'S006',
        seq: 6,
        name: 'EDR Isolation — HITL Approval',
        type: 'decision',
        auto: false,
        assignee: 'Incident Commander',
        sla: '20m after evidence',
        detail:
          'Post evidence-window: isolate affected hosts via EDR. Requires IC + analyst dual-approval. Document decision rationale.',
        status: 'active',
      },
      {
        id: 'S007',
        seq: 7,
        name: 'C2 Beacon Severing',
        type: 'contain',
        auto: false,
        assignee: 'Network Defense',
        sla: '30m',
        detail:
          'Identify and block all C2 IP/domain infrastructure. Deploy firewall rules. Monitor for re-establishment attempts.',
        status: 'pending',
      },
      {
        id: 'S008',
        seq: 8,
        name: 'Lateral Movement Sweep',
        type: 'eradicate',
        auto: true,
        sla: '60m',
        detail:
          'Automated sweep of all adjacent hosts. Check for implants, scheduled tasks, persistence mechanisms. Generate affected asset list.',
        status: 'pending',
      },
      {
        id: 'S009',
        seq: 9,
        name: 'External IR Engagement',
        type: 'escalate',
        auto: false,
        assignee: 'Incident Commander',
        detail:
          'If campaign complexity warrants: engage approved IR firm (CrowdStrike/Mandiant). Provide evidence packages. Transfer chain of custody.',
        status: 'pending',
      },
      {
        id: 'S010',
        seq: 10,
        name: 'Breach Notification Assessment',
        type: 'notify',
        auto: false,
        assignee: 'Legal (PRISM)',
        sla: '72h from detection',
        detail:
          'Legal review of breach notification obligations (GDPR, state breach laws, SEC). Draft regulatory notifications. Client notification.',
        status: 'pending',
      },
      {
        id: 'S011',
        seq: 11,
        name: 'Root Cause Remediation',
        type: 'recover',
        auto: false,
        sla: '7 days',
        detail:
          'Patch initial access vectors. Rotate all credentials on affected systems. Implement additional network segmentation. Harden identified gaps.',
        status: 'pending',
      },
      {
        id: 'S012',
        seq: 12,
        name: 'After-Action Report',
        type: 'review',
        auto: false,
        sla: '14 days',
        detail:
          'Compile full timeline, decisions, metrics, and improvement recommendations. Exec briefing. Lessons learned integrated into playbook.',
        status: 'pending',
      },
    ],
    escalationRules: [
      {
        trigger: '15m window',
        condition: 'No IC response after 15m',
        action: 'Auto-escalate to CISO',
        level: 'L4',
        notifyList: ['CISO', 'VP Engineering'],
      },
      {
        trigger: 'Client impact confirmed',
        condition: 'Managed client assets in blast radius',
        action: 'Activate client crisis protocol',
        level: 'L3',
        notifyList: ['MSP Lead', 'Account Manager', 'Client CISO'],
      },
      {
        trigger: 'Exfiltration confirmed',
        condition: 'Data exfil detected or suspected',
        action: 'Legal hold + breach notification review',
        level: 'L4',
        notifyList: ['Legal (PRISM)', 'CISO', 'CEO'],
      },
    ],
    roleAssignments: [
      {
        role: 'Incident Commander',
        responsibilities: 'Overall crisis direction, HITL decisions, executive comms',
      },
      {
        role: 'Lead Threat Analyst',
        responsibilities: 'Technical investigation, TTP mapping, attribution',
      },
      {
        role: 'Forensics Lead',
        responsibilities: 'Evidence preservation, memory analysis, chain of custody',
      },
      {
        role: 'MSP Client Lead',
        responsibilities: 'Client communication, SLA management, account impact',
      },
      {
        role: 'Network Defense',
        responsibilities: 'Perimeter hardening, C2 severing, firewall rules',
      },
      {
        role: 'Legal Counsel (PRISM)',
        responsibilities: 'Breach notification, regulatory obligations, evidence requirements',
      },
    ],
  },
  {
    id: 'PB-RAN-001',
    name: 'Ransomware Containment & Recovery',
    scenario: 'Ransomware Attack',
    category: 'Cyberattack',
    severity: 'critical',
    icon: Lock,
    color: '#f5f5f5',
    description:
      'Rapid ransomware response — isolate, preserve, recover from clean backups. Includes negotiation decision framework and regulatory notification protocol.',
    executions: 7,
    successRate: 86,
    avgContainmentMin: 28,
    lastUsed: '14 days ago',
    steps: [
      {
        id: 'R001',
        seq: 1,
        name: 'Ransomware Confirmation',
        type: 'assess',
        auto: true,
        sla: '5m',
        detail:
          'Confirm ransom note, encrypted file patterns, affected host count. Check for data exfil pre-encryption (double extortion).',
        status: 'pending',
      },
      {
        id: 'R002',
        seq: 2,
        name: 'Network Segmentation — Emergency',
        type: 'contain',
        auto: false,
        assignee: 'Network Defense',
        sla: '10m',
        detail:
          'Immediately segment affected network zones. Kill all cross-domain authentication. Disable VPN access for affected subnets.',
        status: 'pending',
      },
      {
        id: 'R003',
        seq: 3,
        name: 'Identify Patient Zero',
        type: 'assess',
        auto: false,
        sla: '30m',
        detail:
          'Trace initial infection vector. Check email, web, RDP, supply chain. Critical for variant identification and reinfection prevention.',
        status: 'pending',
      },
      {
        id: 'R004',
        seq: 4,
        name: 'Pay/No-Pay Decision Framework',
        type: 'decision',
        auto: false,
        assignee: 'Incident Commander + Legal',
        sla: '4h',
        detail:
          'Evaluate: backup viability, data exfil risk, regulatory implications, negotiation firm engagement. Document decision with legal counsel.',
        status: 'pending',
      },
      {
        id: 'R005',
        seq: 5,
        name: 'Clean Restore from Backup',
        type: 'recover',
        auto: false,
        sla: '48h',
        detail:
          'Validate backup integrity (pre-infection timestamp). Restore priority systems in clean environment. Verify before reconnection.',
        status: 'pending',
      },
    ],
    escalationRules: [
      {
        trigger: 'OT/ICS affected',
        condition: 'Operational technology systems encrypted',
        action: 'Physical security incident protocol',
        level: 'L5',
        notifyList: ['CEO', 'Board', 'CISA'],
      },
    ],
    roleAssignments: [
      { role: 'Incident Commander', responsibilities: 'Pay/no-pay decision, executive escalation' },
      {
        role: 'Backup Recovery Lead',
        responsibilities: 'Backup validation, clean restore orchestration',
      },
    ],
  },
  {
    id: 'PB-DB-001',
    name: 'Data Breach Response',
    scenario: 'Data Breach',
    category: 'Data Security',
    severity: 'critical',
    icon: AlertOctagon,
    color: '#c9b787',
    description:
      'Structured data breach response covering breach scoping, regulatory notification timelines (GDPR 72h, state laws), credit monitoring, and stakeholder communication.',
    executions: 2,
    successRate: 100,
    avgContainmentMin: 180,
    lastUsed: '47 days ago',
    steps: [
      {
        id: 'DB001',
        seq: 1,
        name: 'Breach Scoping & PII Inventory',
        type: 'assess',
        auto: false,
        sla: '4h',
        detail:
          'Identify what data was accessed/exfiltrated. Map to PII inventory. Determine regulatory jurisdiction (GDPR, CCPA, HIPAA, etc.).',
        status: 'pending',
      },
      {
        id: 'DB002',
        seq: 2,
        name: 'Legal Hold Activation',
        type: 'action',
        auto: false,
        assignee: 'Legal (PRISM)',
        sla: '2h',
        detail:
          'Issue legal hold notice. Preserve all evidence. Engage external legal counsel if needed.',
        status: 'pending',
      },
      {
        id: 'DB003',
        seq: 3,
        name: '72-Hour Regulatory Notification',
        type: 'notify',
        auto: false,
        assignee: 'Legal + CISO',
        sla: '72h from detection',
        detail:
          'GDPR: notify DPA within 72h if individuals at risk. US states: 30-90 day windows vary. SEC: 4 business days for material incidents.',
        status: 'pending',
      },
      {
        id: 'DB004',
        seq: 4,
        name: 'Affected Individual Notification',
        type: 'notify',
        auto: false,
        sla: '30 days',
        detail:
          'Draft and send notification letters. Provide credit monitoring. Stand up dedicated support line. Document all notifications.',
        status: 'pending',
      },
    ],
    escalationRules: [
      {
        trigger: 'GDPR scope confirmed',
        condition: 'EU resident data involved',
        action: 'DPA notification within 72h',
        level: 'L4',
        notifyList: ['Legal', 'CISO', 'DPO'],
      },
    ],
    roleAssignments: [
      {
        role: 'Legal Counsel (PRISM)',
        responsibilities: 'Regulatory notifications, individual notice drafting',
      },
      { role: 'CISO', responsibilities: 'Technical breach scope, remediation oversight' },
    ],
  },
  {
    id: 'PB-PHY-001',
    name: 'Physical Security Incident',
    scenario: 'Physical Security',
    category: 'Operational Security',
    severity: 'high',
    icon: Building2,
    color: '#c9b787',
    description:
      'Physical security incident response covering unauthorized access, theft, facility lockdown, and law enforcement coordination.',
    executions: 1,
    successRate: 100,
    avgContainmentMin: 15,
    lastUsed: '3 months ago',
    steps: [
      {
        id: 'P001',
        seq: 1,
        name: 'Facility Lockdown Assessment',
        type: 'assess',
        auto: false,
        sla: '2m',
        detail:
          'Assess threat level. Determine if lockdown required. Contact building security and facilities management.',
        status: 'pending',
      },
      {
        id: 'P002',
        seq: 2,
        name: 'Law Enforcement Notification',
        type: 'notify',
        auto: false,
        sla: '5m',
        detail:
          'Contact local law enforcement if criminal activity suspected. Preserve physical evidence. Activate badge/CCTV preservation.',
        status: 'pending',
      },
      {
        id: 'P003',
        seq: 3,
        name: 'Personnel Accountability',
        type: 'action',
        auto: false,
        assignee: 'HR + Facilities',
        sla: '15m',
        detail: 'Account for all personnel. Activate muster protocol. Check visitor logs.',
        status: 'pending',
      },
    ],
    escalationRules: [],
    roleAssignments: [
      { role: 'Facilities Manager', responsibilities: 'Lockdown, law enforcement coordination' },
    ],
  },
  {
    id: 'PB-REG-001',
    name: 'Regulatory Action Response',
    scenario: 'Regulatory Investigation',
    category: 'Compliance',
    severity: 'high',
    icon: Scale,
    color: '#c9b787',
    description:
      'Response framework for SEC investigations, subpoenas, regulatory examinations, and enforcement actions. Counsel integrated.',
    executions: 5,
    successRate: 100,
    avgContainmentMin: 0,
    lastUsed: '18 days ago',
    steps: [
      {
        id: 'REG001',
        seq: 1,
        name: 'Subpoena / Notice Review',
        type: 'assess',
        auto: false,
        assignee: 'Legal (PRISM)',
        sla: '2h from receipt',
        detail:
          'Review scope and deadlines. Identify responsive documents. Do NOT destroy or alter any potentially responsive materials.',
        status: 'pending',
      },
      {
        id: 'REG002',
        seq: 2,
        name: 'Legal Hold — Broad Scope',
        type: 'action',
        auto: false,
        assignee: 'Legal (PRISM)',
        sla: '24h',
        detail:
          'Issue litigation hold notice to all custodians. Suspend routine data deletion. Notify IT for preservation of electronic systems.',
        status: 'pending',
      },
      {
        id: 'REG003',
        seq: 3,
        name: 'Regulatory Response Coordination',
        type: 'action',
        auto: false,
        sla: '5 business days',
        detail:
          'Coordinate response with outside counsel. Prepare document productions. Schedule key personnel interviews.',
        status: 'pending',
      },
    ],
    escalationRules: [
      {
        trigger: 'Criminal referral',
        condition: 'DOJ referral or criminal subpoena received',
        action: 'Immediate engagement of criminal defense counsel',
        level: 'L5',
        notifyList: ['CEO', 'Board', 'General Counsel'],
      },
    ],
    roleAssignments: [
      {
        role: 'Legal Counsel (PRISM)',
        responsibilities: 'All regulatory engagement, privilege review, productions',
      },
    ],
  },
  {
    id: 'PB-MKT-001',
    name: 'Market / Liquidity Crisis',
    scenario: 'Financial Crisis',
    category: 'Financial',
    severity: 'high',
    icon: TrendingDown,
    color: '#c9b787',
    description:
      'Financial market shock response — portfolio re-evaluation, capital deployment pause, LP communication, and hedge activation.',
    executions: 0,
    successRate: 0,
    avgContainmentMin: 0,
    steps: [
      {
        id: 'M001',
        seq: 1,
        name: 'Portfolio Exposure Assessment',
        type: 'assess',
        auto: true,
        sla: '30m',
        detail:
          'Run stress test on all portfolio positions. Mark to market. Calculate VaR under shock scenario. Identify most exposed holdings.',
        status: 'pending',
      },
      {
        id: 'M002',
        seq: 2,
        name: 'Capital Deployment Pause',
        type: 'decision',
        auto: false,
        assignee: 'CIO',
        sla: '1h',
        detail:
          'Pause all new capital deployments pending market clarity. Review existing deal pipeline for material adverse change clauses.',
        status: 'pending',
      },
      {
        id: 'M003',
        seq: 3,
        name: 'LP Communication',
        type: 'notify',
        auto: false,
        assignee: 'Investor Relations',
        sla: '24h',
        detail:
          'Proactive LP communication on portfolio positioning. Address likely liquidity concerns. No speculation on outcomes.',
        status: 'pending',
      },
    ],
    escalationRules: [],
    roleAssignments: [
      { role: 'CIO', responsibilities: 'Investment decision authority, portfolio direction' },
    ],
  },
];

const STEP_TYPE_LABELS: Record<string, string> = {
  action: 'Action',
  decision: 'Decision',
  notify: 'Notify',
  escalate: 'Escalate',
  assess: 'Assess',
  contain: 'Contain',
  eradicate: 'Eradicate',
  recover: 'Recover',
  review: 'Review',
};

const STATUS_COLORS: Record<string, string> = {
  completed: '#c9b787',
  active: '#8a8a8a',
  pending: '#4a6070',
  skipped: '#374151',
};

function PlaybookCard({
  pb,
  selected,
  onClick,
}: {
  pb: Playbook;
  selected: boolean;
  onClick: () => void;
}) {
  const Icon = pb.icon;
  const completedSteps = pb.steps.filter((s) => s.status === 'completed').length;
  const progress = pb.steps.length > 0 ? (completedSteps / pb.steps.length) * 100 : 0;
  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-xl p-3 transition-all"
      style={{
        background: selected ? `${pb.color}12` : DS.surface,
        border: `1px solid ${selected ? `${pb.color}35` : DS.border}`,
      }}
    >
      <div className="flex items-start gap-2 mb-2">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${pb.color}20` }}
        >
          <Icon className="w-4 h-4" style={{ color: pb.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span
              className="text-[11px] font-bold leading-tight"
              style={{ color: DS.text.primary }}
            >
              {pb.name}
            </span>
            {pb.active && (
              <span
                className="text-[7px] px-1.5 py-0.5 rounded-full font-bold uppercase animate-pulse shrink-0"
                style={{ background: 'rgba(201,183,135,0.15)', color: '#c9b787' }}
              >
                ACTIVE
              </span>
            )}
          </div>
          <span
            className="text-[8px] px-1.5 py-0.5 rounded uppercase font-semibold"
            style={{ background: `${SEV[pb.severity]}15`, color: SEV[pb.severity] }}
          >
            {pb.scenario}
          </span>
        </div>
      </div>
      {pb.active && (
        <div className="mb-2">
          <div
            className="flex items-center justify-between text-[8px] font-mono mb-1"
            style={{ color: DS.text.muted }}
          >
            <span>
              {completedSteps}/{pb.steps.length} steps
            </span>
            <span>{progress.toFixed(0)}%</span>
          </div>
          <div
            className="h-1 rounded-full overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.06)' }}
          >
            <div
              className="h-full rounded-full"
              style={{ width: `${progress}%`, background: pb.color }}
            />
          </div>
        </div>
      )}
      <div className="flex items-center gap-3 text-[9px]" style={{ color: DS.text.muted }}>
        {pb.executions > 0 && (
          <span>
            {pb.executions} runs · {pb.successRate}% success
          </span>
        )}
        {pb.avgContainmentMin > 0 && <span>~{pb.avgContainmentMin}m contain</span>}
        {pb.lastUsed && (
          <span style={{ color: pb.active ? '#c9b787' : undefined }}>{pb.lastUsed}</span>
        )}
      </div>
    </button>
  );
}

export default function CitadelPlaybooks() {
  const [selected, setSelected] = useState<Playbook>(PLAYBOOKS[0]!);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'steps' | 'escalation' | 'roles'>('steps');

  return (
    <div
      className="flex h-full overflow-hidden"
      style={{ background: DS.bg, color: DS.text.primary }}
    >
      <div
        className="w-72 shrink-0 flex flex-col border-r overflow-y-auto"
        style={{ borderColor: DS.border, background: 'rgba(5,10,20,0.95)' }}
      >
        <div className="px-4 py-3 border-b" style={{ borderColor: DS.border }}>
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{
                background: 'rgba(245,245,245,0.15)',
                border: '1px solid rgba(245,245,245,0.25)',
              }}
            >
              <Zap className="w-4 h-4 text-[#f5f5f5]" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight" style={{ color: DS.text.primary }}>
                Crisis Playbooks
              </h1>
              <p
                className="text-[9px] font-mono uppercase tracking-wider"
                style={{ color: 'rgba(245,245,245,0.5)' }}
              >
                CITADEL Response Engine
              </p>
            </div>
          </div>
        </div>
        <div className="p-3 space-y-2">
          {PLAYBOOKS.map((pb) => (
            <PlaybookCard
              key={pb.id}
              pb={pb}
              selected={selected.id === pb.id}
              onClick={() => setSelected(pb)}
            />
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <div
          className="shrink-0 px-5 py-3 border-b"
          style={{
            borderColor: selected.active
              ? `rgba(${selected.color === '#f5f5f5' ? '239,68,68' : '249,115,22'},0.2)`
              : DS.border,
            background: selected.active ? `rgba(245,245,245,0.03)` : 'transparent',
          }}
        >
          <div className="flex items-center gap-3 mb-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: `${selected.color}20`, border: `1px solid ${selected.color}30` }}
            >
              {(() => {
                const Icon = selected.icon;
                return <Icon className="w-4 h-4" style={{ color: selected.color }} />;
              })()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold" style={{ color: DS.text.primary }}>
                  {selected.name}
                </h2>
                {selected.active && (
                  <span
                    className="text-[8px] px-1.5 py-0.5 rounded-full font-bold uppercase animate-pulse"
                    style={{ background: 'rgba(201,183,135,0.12)', color: '#c9b787' }}
                  >
                    ACTIVE
                  </span>
                )}
                <span
                  className="text-[8px] px-1.5 py-0.5 rounded uppercase font-bold"
                  style={{
                    background: `${SEV[selected.severity]}15`,
                    color: SEV[selected.severity],
                  }}
                >
                  {selected.severity}
                </span>
              </div>
              <p className="text-[10px]" style={{ color: DS.text.muted }}>
                {selected.description}
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              {!selected.active && (
                <button
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all"
                  style={{
                    background: `${selected.color}20`,
                    color: selected.color,
                    border: `1px solid ${selected.color}30`,
                  }}
                >
                  <Play className="w-3 h-3" />
                  Activate Playbook
                </button>
              )}
              <button
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  color: DS.text.secondary,
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <Copy className="w-3 h-3" />
                Clone
              </button>
            </div>
          </div>

          <div className="flex gap-3">
            {selected.executions > 0 && (
              <div
                className="rounded-lg px-3 py-1.5"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <p className="text-[8px] font-mono uppercase" style={{ color: DS.text.muted }}>
                  Executions
                </p>
                <p className="text-[12px] font-bold" style={{ color: DS.text.primary }}>
                  {selected.executions}
                </p>
              </div>
            )}
            {selected.successRate > 0 && (
              <div
                className="rounded-lg px-3 py-1.5"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <p className="text-[8px] font-mono uppercase" style={{ color: DS.text.muted }}>
                  Success Rate
                </p>
                <p className="text-[12px] font-bold" style={{ color: '#c9b787' }}>
                  {selected.successRate}%
                </p>
              </div>
            )}
            {selected.avgContainmentMin > 0 && (
              <div
                className="rounded-lg px-3 py-1.5"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <p className="text-[8px] font-mono uppercase" style={{ color: DS.text.muted }}>
                  Avg Containment
                </p>
                <p className="text-[12px] font-bold" style={{ color: DS.text.primary }}>
                  {selected.avgContainmentMin}m
                </p>
              </div>
            )}
            <div
              className="rounded-lg px-3 py-1.5"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <p className="text-[8px] font-mono uppercase" style={{ color: DS.text.muted }}>
                Steps
              </p>
              <p className="text-[12px] font-bold" style={{ color: DS.text.primary }}>
                {selected.steps.length}
              </p>
            </div>
          </div>
        </div>

        <div
          className="shrink-0 flex items-center gap-0 px-5 border-b"
          style={{ borderColor: DS.border }}
        >
          {(
            [
              { id: 'steps', label: 'Response Steps' },
              { id: 'escalation', label: 'Escalation Rules' },
              { id: 'roles', label: 'Role Assignments' },
            ] as { id: typeof activeView; label: string }[]
          ).map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveView(id)}
              className="px-4 py-2.5 text-[11px] font-semibold border-b-2 transition-all"
              style={{
                borderColor: activeView === id ? selected.color : 'transparent',
                color: activeView === id ? selected.color : DS.text.muted,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {activeView === 'steps' && (
            <div className="space-y-1.5 max-w-2xl">
              {selected.steps.map((step, i) => {
                const Icon = STEP_ICONS[step.type] ?? Zap;
                const color = STEP_COLORS[step.type] ?? '#4a6070';
                const isExpanded = expandedStep === step.id;
                const statusColor = step.status ? STATUS_COLORS[step.status] : DS.text.muted;

                return (
                  <div key={step.id} className="relative">
                    {i < selected.steps.length - 1 && (
                      <div
                        className="absolute left-[13px] top-8 w-px"
                        style={{ height: 'calc(100% - 8px)', background: `${color}15`, zIndex: 0 }}
                      />
                    )}
                    <div
                      className="rounded-xl overflow-hidden"
                      style={{
                        border: `1px solid ${isExpanded ? `${color}30` : DS.border}`,
                        background: isExpanded ? `${color}06` : DS.surface,
                        position: 'relative',
                        zIndex: 1,
                      }}
                    >
                      <button
                        onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left"
                      >
                        <div
                          className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                          style={{ background: `${color}15`, border: `1px solid ${color}25` }}
                        >
                          {step.status === 'completed' ? (
                            <CheckCircle className="w-3.5 h-3.5" style={{ color: '#c9b787' }} />
                          ) : step.status === 'active' ? (
                            <Icon className="w-3.5 h-3.5 animate-pulse" style={{ color }} />
                          ) : (
                            <span className="text-[9px] font-bold" style={{ color: DS.text.muted }}>
                              {step.seq}
                            </span>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className="text-[11px] font-semibold"
                              style={{
                                color:
                                  step.status === 'completed' ? DS.text.muted : DS.text.primary,
                              }}
                            >
                              {step.name}
                            </span>
                            <span
                              className="text-[8px] px-1.5 py-0.5 rounded uppercase font-bold shrink-0"
                              style={{ background: `${color}15`, color }}
                            >
                              {STEP_TYPE_LABELS[step.type]}
                            </span>
                            {!step.auto && (
                              <span
                                className="text-[7px] px-1.5 py-0.5 rounded uppercase shrink-0"
                                style={{
                                  background: 'rgba(255,255,255,0.05)',
                                  color: DS.text.muted,
                                }}
                              >
                                HITL
                              </span>
                            )}
                            {step.status && (
                              <span
                                className="text-[7px] px-1.5 py-0.5 rounded uppercase font-bold shrink-0 animate-[pulse_2s_ease-in-out_infinite]"
                                style={{ background: `${statusColor}12`, color: statusColor }}
                              >
                                {step.status}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-0.5">
                            {step.assignee && (
                              <span className="text-[9px]" style={{ color: DS.text.muted }}>
                                → {step.assignee}
                              </span>
                            )}
                            {step.sla && (
                              <span className="text-[9px] font-mono" style={{ color: '#c9b787' }}>
                                SLA: {step.sla}
                              </span>
                            )}
                          </div>
                        </div>
                        {isExpanded ? (
                          <ChevronDown
                            className="w-3.5 h-3.5 shrink-0"
                            style={{ color: DS.text.muted }}
                          />
                        ) : (
                          <ChevronRight
                            className="w-3.5 h-3.5 shrink-0"
                            style={{ color: DS.text.muted }}
                          />
                        )}
                      </button>
                      {isExpanded && (
                        <div className="px-4 pb-3 border-t" style={{ borderColor: `${color}15` }}>
                          <p
                            className="text-[10px] leading-relaxed pt-2"
                            style={{ color: DS.text.secondary }}
                          >
                            {step.detail}
                          </p>
                          {step.timeWindow && (
                            <div
                              className="mt-2 flex items-center gap-1.5 text-[9px]"
                              style={{ color: '#c9b787' }}
                            >
                              <Clock className="w-3 h-3" />
                              Time window: {step.timeWindow}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activeView === 'escalation' && (
            <div className="space-y-3 max-w-2xl">
              {selected.escalationRules.length === 0 && (
                <p className="text-[11px]" style={{ color: DS.text.muted }}>
                  No escalation rules configured for this playbook.
                </p>
              )}
              {selected.escalationRules.map((rule, i) => (
                <div
                  key={i}
                  className="rounded-xl p-4"
                  style={{
                    background: 'rgba(201,183,135,0.05)',
                    border: '1px solid rgba(201,183,135,0.15)',
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-[#c9b787]" />
                    <span className="text-[11px] font-bold" style={{ color: DS.text.primary }}>
                      Trigger: {rule.trigger}
                    </span>
                    <span
                      className="ml-auto text-[9px] px-1.5 py-0.5 rounded font-mono font-bold"
                      style={{ background: 'rgba(201,183,135,0.15)', color: '#c9b787' }}
                    >
                      {rule.level}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p
                        className="text-[9px] font-bold uppercase tracking-wider mb-1"
                        style={{ color: DS.text.muted }}
                      >
                        Condition
                      </p>
                      <p className="text-[10px]" style={{ color: DS.text.secondary }}>
                        {rule.condition}
                      </p>
                    </div>
                    <div>
                      <p
                        className="text-[9px] font-bold uppercase tracking-wider mb-1"
                        style={{ color: DS.text.muted }}
                      >
                        Action
                      </p>
                      <p className="text-[10px]" style={{ color: DS.text.secondary }}>
                        {rule.action}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2">
                    <p
                      className="text-[9px] font-bold uppercase tracking-wider mb-1"
                      style={{ color: DS.text.muted }}
                    >
                      Notify
                    </p>
                    <div className="flex gap-1.5 flex-wrap">
                      {rule.notifyList.map((n) => (
                        <span
                          key={n}
                          className="text-[9px] px-1.5 py-0.5 rounded"
                          style={{ background: 'rgba(255,255,255,0.05)', color: DS.text.secondary }}
                        >
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeView === 'roles' && (
            <div className="space-y-2 max-w-2xl">
              {selected.roleAssignments.map((r, i) => (
                <div
                  key={i}
                  className="rounded-xl px-4 py-3 flex items-start gap-3"
                  style={{ background: DS.surface, border: `1px solid ${DS.border}` }}
                >
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold mt-0.5"
                    style={{ background: `${selected.color}15`, color: selected.color }}
                  >
                    {i + 1}
                  </div>
                  <div>
                    <p className="text-[11px] font-bold mb-0.5" style={{ color: DS.text.primary }}>
                      {r.role}
                    </p>
                    <p className="text-[10px]" style={{ color: DS.text.secondary }}>
                      {r.responsibilities}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
