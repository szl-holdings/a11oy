// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { Badge } from '@szl-holdings/shared-ui/ui/badge';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Database,
  Eye,
  Globe,
  Play,
  RefreshCw,
  Server,
  Target,
  XCircle,
  Zap,
} from 'lucide-react';
import { useCallback, useState } from 'react';

const DS = {
  surface: 'rgba(255,255,255,0.025)',
  border: 'rgba(255,255,255,0.06)',
  elevated: 'rgba(255,255,255,0.04)',
  text: {
    primary: 'rgba(255,255,255,0.88)',
    secondary: 'rgba(255,255,255,0.5)',
    tertiary: 'rgba(255,255,255,0.28)',
  },
  accent: {
    red: '#f5f5f5',
    orange: '#c9b787',
    amber: '#c9b787',
    green: '#c9b787',
    blue: '#c9b787',
    purple: '#c9b787',
    cyan: '#22d3ee',
  },
};

type APTGroup = 'APT28' | 'APT41' | 'Lazarus' | 'Sandworm' | 'VoltTyphoon' | 'APT29';
type SimPhase =
  | 'idle'
  | 'recon'
  | 'initial_access'
  | 'execution'
  | 'persistence'
  | 'lateral'
  | 'exfil'
  | 'impact'
  | 'complete';
type DefenseResult = 'blocked' | 'detected' | 'missed';

interface TTP {
  id: string;
  name: string;
  technique: string;
  tactic: string;
  description: string;
  impact: string;
}

interface APTProfile {
  id: APTGroup;
  name: string;
  nation: string;
  flag: string;
  color: string;
  aliases: string[];
  motivation: string[];
  targetSectors: string[];
  sophistication: number;
  ttps: TTP[];
  szlRelevance: string;
}

interface SimulationStep {
  phase: SimPhase;
  label: string;
  ttp: string;
  technique: string;
  result: DefenseResult;
  timeMs: number;
  detail: string;
}

const APT_PROFILES: APTProfile[] = [
  {
    id: 'APT28',
    name: 'APT28 / Fancy Bear',
    nation: 'Russia',
    flag: '🇷🇺',
    color: '#f5f5f5',
    aliases: ['Fancy Bear', 'Sofacy', 'Strontium', 'Forest Blizzard'],
    motivation: ['espionage', 'disruption', 'influence_ops'],
    targetSectors: ['government', 'military', 'maritime', 'finance'],
    sophistication: 92,
    szlRelevance:
      'Maritime route intelligence, executive spear-phishing, sanctions evasion support',
    ttps: [
      {
        id: 'AP28-1',
        name: 'Spear-Phishing (Executive)',
        technique: 'T1566.001',
        tactic: 'Initial Access',
        description:
          'Highly targeted spear-phishing against C-suite with weaponized Office documents',
        impact: 'Credential harvest → email compromise → lateral movement',
      },
      {
        id: 'AP28-2',
        name: 'Pass-the-Hash',
        technique: 'T1550.002',
        tactic: 'Lateral Movement',
        description: 'Use of pass-the-hash to move laterally without plaintext credentials',
        impact: 'Admin-level access to internal systems',
      },
      {
        id: 'AP28-3',
        name: 'X-Agent Implant',
        technique: 'T1027',
        tactic: 'Defense Evasion',
        description: 'Custom obfuscated backdoor with C2 over HTTPS/HTTP',
        impact: 'Long-term persistent access, data staging',
      },
      {
        id: 'AP28-4',
        name: 'DCSync Attack',
        technique: 'T1003.006',
        tactic: 'Credential Access',
        description: 'Abuse AD replication to dump all domain hashes',
        impact: 'Full domain compromise',
      },
    ],
  },
  {
    id: 'APT41',
    name: 'APT41 / Volt Typhoon',
    nation: 'China',
    flag: '🇨🇳',
    color: '#c9b787',
    aliases: ['Volt Typhoon', 'Double Dragon', 'Barium', 'Winnti'],
    motivation: ['espionage', 'financial_crime', 'critical_infrastructure'],
    targetSectors: ['maritime', 'logistics', 'financial', 'technology'],
    sophistication: 96,
    szlRelevance:
      'Fleet tracking intelligence, port operations disruption, supply chain infiltration',
    ttps: [
      {
        id: 'AP41-1',
        name: 'Living-off-the-Land (LOL)',
        technique: 'T1218',
        tactic: 'Defense Evasion',
        description: 'Abuse of native system tools (LOLBins) to avoid AV detection',
        impact: 'Near-zero detection rate, persistent access',
      },
      {
        id: 'AP41-2',
        name: 'Supply Chain Compromise',
        technique: 'T1195.002',
        tactic: 'Initial Access',
        description: 'Backdoored software updates to maritime management systems',
        impact: 'Fleet-wide compromise via trusted update channel',
      },
      {
        id: 'AP41-3',
        name: 'AIS Spoofing Integration',
        technique: 'T1562',
        tactic: 'Impact',
        description: 'Manipulation of vessel tracking data to obscure sanctioned routes',
        impact: 'Compliance blind spots, route intelligence denial',
      },
      {
        id: 'AP41-4',
        name: 'Rootkit Deployment',
        technique: 'T1014',
        tactic: 'Persistence',
        description: 'Kernel-level rootkit for maximum stealth and persistence',
        impact: 'Invisible to standard security tools, survives reboots',
      },
    ],
  },
  {
    id: 'Lazarus',
    name: 'Lazarus Group',
    nation: 'North Korea',
    flag: '🇰🇵',
    color: '#c9b787',
    aliases: ['HIDDEN COBRA', 'Guardians of Peace', 'Zinc'],
    motivation: ['financial_crime', 'sanctions_evasion', 'espionage'],
    targetSectors: ['financial', 'crypto', 'maritime_finance', 'investments'],
    sophistication: 88,
    szlRelevance:
      'Portfolio asset targeting, crypto conversion of stolen funds, financial system disruption',
    ttps: [
      {
        id: 'LAZ-1',
        name: 'Watering Hole (Financial Sites)',
        technique: 'T1189',
        tactic: 'Initial Access',
        description: 'Compromise financial industry websites to deliver drive-by malware',
        impact: 'Wide net against financial professionals',
      },
      {
        id: 'LAZ-2',
        name: 'DeFi Protocol Exploitation',
        technique: 'T1657',
        tactic: 'Impact',
        description: 'Smart contract vulnerabilities exploited to drain crypto assets',
        impact: 'Immediate financial loss, irreversible',
      },
      {
        id: 'LAZ-3',
        name: 'Custom RAT (BLINDINGCAN)',
        technique: 'T1059',
        tactic: 'Execution',
        description: 'Custom remote access trojan with full file system and command execution',
        impact: 'Complete system control, data exfiltration',
      },
      {
        id: 'LAZ-4',
        name: 'SWIFT Network Targeting',
        technique: 'T1565.002',
        tactic: 'Impact',
        description: 'Intercept and manipulate SWIFT financial messages',
        impact: 'Fraudulent transfers, transaction manipulation',
      },
    ],
  },
  {
    id: 'Sandworm',
    name: 'Sandworm / Voodoo Bear',
    nation: 'Russia (GRU)',
    flag: '🇷🇺',
    color: '#f5f5f5',
    aliases: ['Sandworm', 'Voodoo Bear', 'Seashell Blizzard'],
    motivation: ['disruption', 'destruction', 'critical_infrastructure'],
    targetSectors: ['energy', 'maritime_infrastructure', 'government', 'logistics'],
    sophistication: 95,
    szlRelevance: 'Port infrastructure attacks, logistics disruption, NotPetya-style propagation',
    ttps: [
      {
        id: 'SW-1',
        name: 'NotPetya-style Worm',
        technique: 'T1210',
        tactic: 'Lateral Movement',
        description: 'Self-propagating destructive malware leveraging EternalBlue + Mimikatz',
        impact: 'Network-wide destruction, OT/ICS systems at risk',
      },
      {
        id: 'SW-2',
        name: 'Industroyer2 (OT Attack)',
        technique: 'T1562.001',
        tactic: 'Impact',
        description: 'ICS-specific malware targeting industrial control system protocols',
        impact: 'Physical infrastructure damage, safety system override',
      },
      {
        id: 'SW-3',
        name: 'Email Exfiltration (OT Data)',
        technique: 'T1048',
        tactic: 'Exfiltration',
        description: 'Exfil operational technology data via encrypted email channels',
        impact: 'Strategic intelligence on physical infrastructure',
      },
    ],
  },
  {
    id: 'VoltTyphoon',
    name: 'Volt Typhoon (Maritime)',
    nation: 'China',
    flag: '🇨🇳',
    color: '#22d3ee',
    aliases: ['Volt Typhoon', 'Bronze Silhouette', 'Vanguard Panda'],
    motivation: ['pre-positioning', 'critical_infrastructure', 'maritime'],
    targetSectors: ['maritime_ports', 'shipping', 'logistics', 'defense'],
    sophistication: 93,
    szlRelevance: 'Pre-positioned access to port operations systems, fleet management disruption',
    ttps: [
      {
        id: 'VT-1',
        name: 'SOHO Router Compromise',
        technique: 'T1584.008',
        tactic: 'Resource Development',
        description:
          'Compromise small office routers as C2 relay nodes — blends in with legitimate traffic',
        impact: 'Untraceable C2 infrastructure, persistent foothold',
      },
      {
        id: 'VT-2',
        name: 'LOL-Bins Exclusively',
        technique: 'T1569',
        tactic: 'Execution',
        description: 'Zero custom malware — only native OS tools (wmic, powershell, certutil)',
        impact: 'Near-zero AV detection, maximum stealth',
      },
      {
        id: 'VT-3',
        name: 'Credential Cache Dump',
        technique: 'T1003.001',
        tactic: 'Credential Access',
        description: 'LSASS memory dump via ntdsutil or Task Manager',
        impact: 'Privileged credentials for OT systems',
      },
    ],
  },
  {
    id: 'APT29',
    name: 'APT29 / Cozy Bear',
    nation: 'Russia (SVR)',
    flag: '🇷🇺',
    color: '#c9b787',
    aliases: ['Cozy Bear', 'Midnight Blizzard', 'The Dukes'],
    motivation: ['espionage', 'long_term_persistence'],
    targetSectors: ['government', 'finance', 'think_tanks', 'consulting'],
    sophistication: 97,
    szlRelevance:
      'Long-term advisory intelligence theft, client relationship exfiltration, Carlota Jo email compromise',
    ttps: [
      {
        id: 'AP29-1',
        name: 'SolarWinds-style Supply Chain',
        technique: 'T1195.002',
        tactic: 'Initial Access',
        description: 'Backdoored trusted software update mechanism — months of dwell time',
        impact: 'Deep persistent access to all downstream clients',
      },
      {
        id: 'AP29-2',
        name: 'MagicWeb / ADCS Abuse',
        technique: 'T1649',
        tactic: 'Credential Access',
        description: 'AD Certificate Services abuse to forge authentication certificates',
        impact: 'Identity persistence that survives password resets',
      },
      {
        id: 'AP29-3',
        name: 'Minimal Footprint Ops',
        technique: 'T1070',
        tactic: 'Defense Evasion',
        description: 'Aggressive log clearing, timestomping, and in-memory execution only',
        impact: 'Dwell time measured in months before detection',
      },
    ],
  },
];

const ATTACK_PHASES: Array<{
  phase: SimPhase;
  label: string;
  icon: React.FC<{ size?: number; color?: string }>;
}> = [
  { phase: 'recon', label: 'Reconnaissance', icon: Eye },
  { phase: 'initial_access', label: 'Initial Access', icon: Globe },
  { phase: 'execution', label: 'Execution', icon: Zap },
  { phase: 'persistence', label: 'Persistence', icon: Server },
  { phase: 'lateral', label: 'Lateral Movement', icon: ArrowRight },
  { phase: 'exfil', label: 'Exfiltration', icon: Database },
  { phase: 'impact', label: 'Impact', icon: AlertTriangle },
];

function generateSimulationSteps(apt: APTProfile, defenseLevel: number): SimulationStep[] {
  const steps: SimulationStep[] = [];
  const ttpQueue = [...apt.ttps];

  const phaseMap: Record<string, { phase: SimPhase; technique: string }> = {
    'Initial Access': {
      phase: 'initial_access',
      technique: apt.ttps.find((t) => t.tactic === 'Initial Access')?.technique ?? 'T1566',
    },
    'Defense Evasion': {
      phase: 'execution',
      technique: apt.ttps.find((t) => t.tactic === 'Defense Evasion')?.technique ?? 'T1027',
    },
    'Lateral Movement': {
      phase: 'lateral',
      technique: apt.ttps.find((t) => t.tactic === 'Lateral Movement')?.technique ?? 'T1550',
    },
    'Credential Access': {
      phase: 'persistence',
      technique: apt.ttps.find((t) => t.tactic === 'Credential Access')?.technique ?? 'T1003',
    },
    Persistence: {
      phase: 'persistence',
      technique: apt.ttps.find((t) => t.tactic === 'Persistence')?.technique ?? 'T1053',
    },
    Impact: {
      phase: 'impact',
      technique: apt.ttps.find((t) => t.tactic === 'Impact')?.technique ?? 'T1485',
    },
    Exfiltration: { phase: 'exfil', technique: 'T1041' },
    Execution: { phase: 'execution', technique: 'T1059' },
    'Resource Development': { phase: 'recon', technique: 'T1588' },
  };

  steps.push({
    phase: 'recon',
    label: 'OSINT Reconnaissance',
    ttp: 'T1592',
    technique: 'Gather Victim Host Information',
    result: 'missed',
    timeMs: 3200 + Math.random() * 1000,
    detail: `${apt.name} conducting passive OSINT — LinkedIn profiling, DNS enumeration, shodan.io asset discovery targeting SZL infrastructure`,
  });

  for (const ttp of ttpQueue.slice(0, 4)) {
    const phaseData = phaseMap[ttp.tactic] ?? {
      phase: 'execution' as SimPhase,
      technique: ttp.technique,
    };
    const rollSuccess = Math.random() * 100;
    const blockChance = defenseLevel * 0.85 - apt.sophistication * 0.4;
    const result: DefenseResult =
      rollSuccess < blockChance
        ? 'blocked'
        : rollSuccess < blockChance + 20
          ? 'detected'
          : 'missed';

    steps.push({
      phase: phaseData.phase,
      label: ttp.name,
      ttp: ttp.technique,
      technique: ttp.description.slice(0, 60),
      result,
      timeMs: 800 + Math.random() * 2400,
      detail: `${ttp.description}. Impact: ${ttp.impact}`,
    });
  }

  const _hasDetected = steps.some((s) => s.result === 'detected');
  const hasMissed = steps.some((s) => s.result === 'missed');

  if (hasMissed) {
    steps.push({
      phase: 'impact',
      label: `${apt.name} TTP Impact Realized`,
      ttp: 'T1485',
      technique: 'Impact / Data Manipulation',
      result: 'missed',
      timeMs: 5200,
      detail: apt.szlRelevance,
    });
  }

  return steps;
}

export default function APTEmulationPage() {
  const [selectedAPT, setSelectedAPT] = useState<APTProfile>(APT_PROFILES[0]!);
  const [defenseLevel, setDefenseLevel] = useState(65);
  const [simSteps, setSimSteps] = useState<SimulationStep[]>([]);
  const [currentPhaseIdx, setCurrentPhaseIdx] = useState(-1);
  const [simStatus, setSimStatus] = useState<'idle' | 'running' | 'complete'>('idle');
  const [_visibleStepCount, setVisibleStepCount] = useState(0);

  const runSimulation = useCallback(async () => {
    setSimStatus('running');
    setSimSteps([]);
    setVisibleStepCount(0);
    setCurrentPhaseIdx(0);

    const steps = generateSimulationSteps(selectedAPT, defenseLevel);

    for (let i = 0; i < steps.length; i++) {
      await new Promise((r) => setTimeout(r, steps[i]?.timeMs));
      setSimSteps((prev) => [...prev, steps[i]!]);
      setVisibleStepCount(i + 1);
      setCurrentPhaseIdx(Math.floor((i / steps.length) * ATTACK_PHASES.length));
    }

    setSimStatus('complete');
  }, [selectedAPT, defenseLevel]);

  const blockedCount = simSteps.filter((s) => s.result === 'blocked').length;
  const detectedCount = simSteps.filter((s) => s.result === 'detected').length;
  const missedCount = simSteps.filter((s) => s.result === 'missed').length;

  const _radarData = [
    { axis: 'Email', score: defenseLevel - 10 + Math.random() * 15 },
    { axis: 'Endpoint', score: defenseLevel + Math.random() * 10 },
    { axis: 'Network', score: defenseLevel - 15 + Math.random() * 20 },
    { axis: 'Identity', score: defenseLevel - 20 + Math.random() * 15 },
    { axis: 'Data', score: defenseLevel - 5 + Math.random() * 10 },
    { axis: 'Detection', score: defenseLevel + 5 + Math.random() * 10 },
  ].map((d) => ({ ...d, score: Math.min(100, Math.max(0, d.score)) }));

  return (
    <div style={{ padding: '28px', maxWidth: '1400px', margin: '0 auto', color: DS.text.primary }}>
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '8px',
              background: 'rgba(245,245,245,0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Target size={18} color={DS.accent.red} />
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0 }}>
            Adversary Emulation Engine
          </h1>
          <Badge
            style={{
              background: 'rgba(245,245,245,0.15)',
              color: DS.accent.red,
              border: '1px solid rgba(245,245,245,0.3)',
              fontSize: '10px',
            }}
          >
            PURPLE TEAM
          </Badge>
          <Badge
            style={{
              background: 'rgba(167,139,250,0.1)',
              color: DS.accent.purple,
              border: '1px solid rgba(167,139,250,0.3)',
              fontSize: '10px',
            }}
          >
            MITRE ATT&CK MAPPED
          </Badge>
        </div>
        <p style={{ color: DS.text.secondary, fontSize: '14px', margin: 0 }}>
          Simulate real-world APT campaigns against SZL's digital twin posture. Identify detection
          gaps before adversaries exploit them.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              padding: '16px',
            }}
          >
            <p
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: DS.text.tertiary,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                margin: '0 0 12px',
              }}
            >
              Threat Actor
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {APT_PROFILES.map((apt) => (
                <button
                  key={apt.id}
                  onClick={() => {
                    setSelectedAPT(apt);
                    setSimStatus('idle');
                    setSimSteps([]);
                  }}
                  style={{
                    background: selectedAPT.id === apt.id ? `${apt.color}18` : 'transparent',
                    border: `1px solid ${selectedAPT.id === apt.id ? `${apt.color}60` : DS.border}`,
                    borderRadius: '8px',
                    padding: '10px 12px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '18px' }}>{apt.flag}</span>
                    <div>
                      <p
                        style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: selectedAPT.id === apt.id ? apt.color : DS.text.primary,
                          margin: 0,
                        }}
                      >
                        {apt.name}
                      </p>
                      <p style={{ fontSize: '10px', color: DS.text.tertiary, margin: 0 }}>
                        {apt.aliases.slice(0, 2).join(' · ')}
                      </p>
                    </div>
                    <div style={{ marginLeft: 'auto' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: apt.color }}>
                        {apt.sophistication}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              padding: '16px',
            }}
          >
            <p
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: DS.text.tertiary,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                margin: '0 0 12px',
              }}
            >
              Defense Posture
            </p>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '8px',
              }}
            >
              <span style={{ fontSize: '13px', color: DS.text.secondary }}>Posture Level</span>
              <span
                style={{
                  fontSize: '20px',
                  fontWeight: 700,
                  color:
                    defenseLevel > 70
                      ? DS.accent.green
                      : defenseLevel > 50
                        ? DS.accent.amber
                        : DS.accent.red,
                }}
              >
                {defenseLevel}
              </span>
            </div>
            <input
              type="range"
              min={10}
              max={95}
              value={defenseLevel}
              onChange={(e) => setDefenseLevel(Number(e.target.value))}
              style={{
                width: '100%',
                accentColor:
                  defenseLevel > 70
                    ? DS.accent.green
                    : defenseLevel > 50
                      ? DS.accent.amber
                      : DS.accent.red,
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
              <span style={{ fontSize: '10px', color: DS.accent.red }}>10 — Critical</span>
              <span style={{ fontSize: '10px', color: DS.accent.green }}>95 — Hardened</span>
            </div>
            <div
              style={{
                marginTop: '12px',
                padding: '8px',
                background: DS.elevated,
                borderRadius: '6px',
              }}
            >
              <p style={{ fontSize: '11px', color: DS.text.secondary, margin: 0 }}>
                Posture sourced from <strong style={{ color: DS.text.primary }}>PostureTwin</strong>
                : {defenseLevel}/100. Adversary sophistication:{' '}
                <strong style={{ color: selectedAPT.color }}>
                  {selectedAPT.sophistication}/100
                </strong>
                .
              </p>
            </div>
          </div>

          <div
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              padding: '16px',
            }}
          >
            <p
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: DS.text.tertiary,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                margin: '0 0 12px',
              }}
            >
              SZL Relevance
            </p>
            <p
              style={{
                fontSize: '12px',
                color: DS.text.secondary,
                margin: '0 0 12px',
                lineHeight: 1.6,
              }}
            >
              {selectedAPT.szlRelevance}
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {selectedAPT.targetSectors.map((s) => (
                <Badge
                  key={s}
                  style={{
                    background: `${selectedAPT.color}18`,
                    color: selectedAPT.color,
                    border: `1px solid ${selectedAPT.color}40`,
                    fontSize: '10px',
                  }}
                >
                  {s}
                </Badge>
              ))}
            </div>
          </div>

          <button
            onClick={runSimulation}
            disabled={simStatus === 'running'}
            style={{
              background:
                simStatus === 'running' ? 'rgba(255,255,255,0.05)' : `${selectedAPT.color}20`,
              border: `1px solid ${simStatus === 'running' ? DS.border : `${selectedAPT.color}60`}`,
              borderRadius: '10px',
              padding: '14px',
              cursor: simStatus === 'running' ? 'not-allowed' : 'pointer',
              color: simStatus === 'running' ? DS.text.tertiary : selectedAPT.color,
              fontWeight: 700,
              fontSize: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            {simStatus === 'running' ? (
              <>
                <RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />{' '}
                Simulating...
              </>
            ) : (
              <>
                <Play size={16} /> Run {selectedAPT.name.split(' ')[0]} Emulation
              </>
            )}
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              background: DS.surface,
              border: `1px solid ${DS.border}`,
              borderRadius: '12px',
              padding: '16px',
            }}
          >
            <p
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: DS.text.tertiary,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                margin: '0 0 16px',
              }}
            >
              Attack Kill Chain
            </p>
            <div style={{ display: 'flex', gap: '0px', overflowX: 'auto' }}>
              {ATTACK_PHASES.map((ph, idx) => {
                const Icon = ph.icon;
                const isActive = idx <= currentPhaseIdx && simStatus !== 'idle';
                return (
                  <div key={ph.phase} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                    <div style={{ textAlign: 'center', flex: 1 }}>
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: '50%',
                          background: isActive ? `${selectedAPT.color}20` : DS.elevated,
                          border: `1px solid ${isActive ? `${selectedAPT.color}60` : DS.border}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          margin: '0 auto 6px',
                          transition: 'all 0.3s',
                        }}
                      >
                        <Icon size={14} color={isActive ? selectedAPT.color : DS.text.tertiary} />
                      </div>
                      <p
                        style={{
                          fontSize: '9px',
                          color: isActive ? DS.text.primary : DS.text.tertiary,
                          margin: 0,
                          fontWeight: isActive ? 600 : 400,
                        }}
                      >
                        {ph.label}
                      </p>
                    </div>
                    {idx < ATTACK_PHASES.length - 1 && (
                      <div
                        style={{
                          width: '20px',
                          height: '1px',
                          background: isActive ? `${selectedAPT.color}60` : DS.border,
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {selectedAPT.ttps.length > 0 && (
            <div
              style={{
                background: DS.surface,
                border: `1px solid ${DS.border}`,
                borderRadius: '12px',
                padding: '16px',
              }}
            >
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: DS.text.tertiary,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  margin: '0 0 12px',
                }}
              >
                TTP Profile — {selectedAPT.name}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                {selectedAPT.ttps.map((ttp) => (
                  <div
                    key={ttp.id}
                    style={{
                      background: DS.elevated,
                      border: `1px solid ${DS.border}`,
                      borderRadius: '8px',
                      padding: '10px',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        marginBottom: '4px',
                      }}
                    >
                      <Badge
                        style={{
                          background: `${selectedAPT.color}18`,
                          color: selectedAPT.color,
                          border: 'none',
                          fontSize: '9px',
                          padding: '2px 6px',
                        }}
                      >
                        {ttp.technique}
                      </Badge>
                      <span style={{ fontSize: '10px', color: DS.text.tertiary }}>
                        {ttp.tactic}
                      </span>
                    </div>
                    <p
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: DS.text.primary,
                        margin: '0 0 4px',
                      }}
                    >
                      {ttp.name}
                    </p>
                    <p
                      style={{
                        fontSize: '11px',
                        color: DS.text.secondary,
                        margin: 0,
                        lineHeight: 1.5,
                      }}
                    >
                      {ttp.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {simSteps.length > 0 && (
            <div
              style={{
                background: DS.surface,
                border: `1px solid ${DS.border}`,
                borderRadius: '12px',
                padding: '16px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px',
                }}
              >
                <p
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: DS.text.tertiary,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    margin: 0,
                  }}
                >
                  Simulation Log
                </p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: DS.accent.green }}>
                    {blockedCount} blocked
                  </span>
                  <span style={{ fontSize: '11px', color: DS.accent.amber }}>
                    {detectedCount} detected
                  </span>
                  <span style={{ fontSize: '11px', color: DS.accent.red }}>
                    {missedCount} missed
                  </span>
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  maxHeight: '300px',
                  overflowY: 'auto',
                }}
              >
                {simSteps.map((step, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      gap: '10px',
                      padding: '8px 10px',
                      background: DS.elevated,
                      borderRadius: '6px',
                      borderLeft: `3px solid ${step.result === 'blocked' ? DS.accent.green : step.result === 'detected' ? DS.accent.amber : DS.accent.red}`,
                    }}
                  >
                    <div style={{ flexShrink: 0, marginTop: '2px' }}>
                      {step.result === 'blocked' ? (
                        <CheckCircle size={12} color={DS.accent.green} />
                      ) : step.result === 'detected' ? (
                        <Eye size={12} color={DS.accent.amber} />
                      ) : (
                        <XCircle size={12} color={DS.accent.red} />
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginBottom: '2px',
                        }}
                      >
                        <span style={{ fontSize: '12px', fontWeight: 600, color: DS.text.primary }}>
                          {step.label}
                        </span>
                        <Badge
                          style={{
                            background: 'rgba(255,255,255,0.05)',
                            color: DS.text.tertiary,
                            border: 'none',
                            fontSize: '9px',
                          }}
                        >
                          {step.ttp}
                        </Badge>
                        <span
                          style={{
                            fontSize: '10px',
                            color:
                              step.result === 'blocked'
                                ? DS.accent.green
                                : step.result === 'detected'
                                  ? DS.accent.amber
                                  : DS.accent.red,
                            fontWeight: 600,
                            marginLeft: 'auto',
                          }}
                        >
                          {step.result.toUpperCase()}
                        </span>
                      </div>
                      <p style={{ fontSize: '11px', color: DS.text.secondary, margin: 0 }}>
                        {step.detail}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {simStatus === 'complete' && (
            <div
              style={{
                background: `${missedCount > 2 ? DS.accent.red : DS.accent.amber}10`,
                border: `1px solid ${missedCount > 2 ? DS.accent.red : DS.accent.amber}40`,
                borderRadius: '12px',
                padding: '16px',
              }}
            >
              <p
                style={{
                  fontSize: '13px',
                  fontWeight: 700,
                  color: missedCount > 2 ? DS.accent.red : DS.accent.amber,
                  margin: '0 0 8px',
                }}
              >
                {missedCount > 2
                  ? '⚠ CRITICAL GAPS DETECTED'
                  : missedCount > 0
                    ? '△ DETECTION GAPS IDENTIFIED'
                    : '✓ POSTURE HELD — REVIEW DETECTIONS'}
              </p>
              <p style={{ fontSize: '12px', color: DS.text.secondary, margin: '0 0 12px' }}>
                {missedCount} out of {simSteps.length} {selectedAPT.name} techniques evaded defenses
                at current posture level ({defenseLevel}/100).
                {missedCount > 0 && ' Hardening recommendations:'}
              </p>
              {missedCount > 0 && (
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: '16px',
                    fontSize: '12px',
                    color: DS.text.secondary,
                    lineHeight: 2,
                  }}
                >
                  {defenseLevel < 70 && (
                    <li>Enable EDR full script blocking (CrowdStrike Falcon ASR rules)</li>
                  )}
                  {defenseLevel < 80 && (
                    <li>Enforce MFA on all privileged accounts — block legacy auth</li>
                  )}
                  {defenseLevel < 75 && (
                    <li>Deploy DMARC p=reject on all organizational domains</li>
                  )}
                  <li>Review MITRE ATT&CK Navigator for {selectedAPT.name} detection coverage</li>
                  <li>Schedule purple team exercise focusing on missed TTPs within 30 days</li>
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
