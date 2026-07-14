// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/sentra/src/pages/cyber-innovation-roadmap.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Brain,
  Cpu,
  FlaskConical,
  Lock,
  Microscope,
  Radio,
  Rocket,
  Shield,
} from 'lucide-react';
import { useState } from 'react';

type Phase = {
  id: string;
  label: string;
  quarter: string;
  status: 'complete' | 'active' | 'planned' | 'future';
  color: string;
  objectives: {
    id: string;
    title: string;
    description: string;
    darpaInspiration: string;
    trl: number;
    progress: number;
    deliverables: string[];
  }[];
};

type ResearchThread = {
  id: string;
  name: string;
  icon: typeof Shield;
  darpaPrograms: string[];
  description: string;
  impact: 'transformative' | 'significant' | 'incremental';
  timelineMonths: number;
  a11oyIntegration: string;
  keyInnovation: string;
};

const PHASES: Phase[] = [
  {
    id: 'phase-1',
    label: 'Foundation',
    quarter: 'Q1 2026',
    status: 'complete',
    color: '#10b981',
    objectives: [
      { id: 'F-001', title: 'Adversarial Defense Layer', description: 'IBM ART-integrated adversarial attack taxonomy with 10 attack classes and 6 defense modules.', darpaInspiration: 'GARD', trl: 7, progress: 100, deliverables: ['Attack taxonomy (4 classes, 10 techniques)', 'Defense evaluation harness', 'Armory scoring integration'] },
      { id: 'F-002', title: 'Formal Verification Engine', description: 'Mathematical proofs of agent safety properties using reachability analysis and SMT solving.', darpaInspiration: 'Assured Autonomy', trl: 6, progress: 100, deliverables: ['5 verification methods', 'Property specification DSL', 'Automated proof generation'] },
      { id: 'F-003', title: 'Supply Chain Attestation', description: 'SBOM-compliant dependency integrity graph with multi-signatory attestation.', darpaInspiration: 'SocialCyber', trl: 7, progress: 100, deliverables: ['Component attestation pipeline', 'Vulnerability correlation', 'Signatory management'] },
    ],
  },
  {
    id: 'phase-2',
    label: 'Evolution',
    quarter: 'Q2 2026',
    status: 'active',
    color: '#3b82f6',
    objectives: [
      { id: 'E-001', title: 'Post-Quantum Cryptography Migration', description: 'NIST FIPS 203/204/205/206 integration across all a11oy cryptographic subsystems.', darpaInspiration: 'PQC Standards', trl: 5, progress: 68, deliverables: ['ML-KEM-1024 key encapsulation', 'ML-DSA-87 digital signatures', 'SLH-DSA stateless hash signatures', 'Hybrid classical/PQ transition'] },
      { id: 'E-002', title: 'DARPA MTO Innovation Integration', description: 'Mapping 15 incubation programs to a11oy capability surfaces.', darpaInspiration: 'MTO Incubation Portfolio', trl: 4, progress: 45, deliverables: ['THz inspection concepts', '3DHI chiplet architecture', 'Skyrmion memory primitives', 'NGMM fab integration paths'] },
      { id: 'E-003', title: 'Hardware Root of Trust', description: 'CHERI capability compartments and SHIELD dielet attestation for hardware-enforced agent isolation.', darpaInspiration: 'SSITH/CHERI/SHIELD', trl: 5, progress: 55, deliverables: ['Trust anchor framework', 'CHERI compartment mapping', 'Supply chain THz inspection', 'PUF identity binding'] },
    ],
  },
  {
    id: 'phase-3',
    label: 'Convergence',
    quarter: 'Q3 2026',
    status: 'planned',
    color: '#8b5cf6',
    objectives: [
      { id: 'C-001', title: 'Neuromorphic Anomaly Detection', description: 'Spiking neural network concepts for ultra-low-latency network anomaly detection at edge.', darpaInspiration: 'NeuPLASM / GrADE', trl: 3, progress: 15, deliverables: ['SNN anomaly classifier concept', 'Energy-proportional alerting', 'Edge deployment pattern'] },
      { id: 'C-002', title: 'Autonomous Cyber Reasoning', description: 'Full-stack automated vulnerability discovery and patching without human intervention.', darpaInspiration: 'AIxCC / BORDEAUX', trl: 4, progress: 25, deliverables: ['Cyber Reasoning System v2', 'Automated patch generation', 'Fuzzing-to-fix pipeline'] },
      { id: 'C-003', title: 'RF Spectrum Defense', description: 'EW/RF monitoring and cognitive spectrum allocation for contested electromagnetic environments.', darpaInspiration: 'DSRC / SLICE / ARC', trl: 3, progress: 10, deliverables: ['Spectrum anomaly detection', 'Cognitive resource allocation', 'Interference classification'] },
    ],
  },
  {
    id: 'phase-4',
    label: 'Horizon',
    quarter: 'Q4 2026+',
    status: 'future',
    color: '#f59e0b',
    objectives: [
      { id: 'H-001', title: 'Quantum-Resistant Agent Mesh', description: 'Fully post-quantum agent communication with lattice-based key exchange and hash-based signatures.', darpaInspiration: 'PQC + AISS', trl: 2, progress: 5, deliverables: ['PQ agent handshake protocol', 'Quantum-safe proof chains', 'Lattice key management'] },
      { id: 'H-002', title: 'Heterogeneous 3D Compute Trust', description: 'Hardware trust verification across chiplet-based heterogeneous compute stacks.', darpaInspiration: '3DHI / NGMM / TIE', trl: 2, progress: 5, deliverables: ['Chiplet attestation protocol', 'Cross-die verification', 'Heterogeneous trust mesh'] },
      { id: 'H-003', title: 'AGI Safety Convergence Layer', description: 'Constitutional AI governance extended to multi-agent general intelligence scenarios.', darpaInspiration: 'TIAMAT + Novel', trl: 2, progress: 0, deliverables: ['Multi-agent safety proofs', 'Constitutional generalization', 'Sim-to-real governance transfer'] },
    ],
  },
];

const RESEARCH_THREADS: ResearchThread[] = [
  { id: 'rt-pqc', name: 'Post-Quantum Cryptography', icon: Lock, darpaPrograms: ['NIST PQC', 'AISS'], description: 'Migrate all cryptographic primitives to quantum-resistant algorithms before harvest-now-decrypt-later attacks become viable.', impact: 'transformative', timelineMonths: 18, a11oyIntegration: 'Proof Chain signatures, Agent mesh key exchange, Evidence ledger encryption', keyInnovation: 'Hybrid classical/PQ transition with zero downtime' },
  { id: 'rt-hwt', name: 'Hardware Trust Chain', icon: Cpu, darpaPrograms: ['SSITH', 'CHERI', 'SHIELD', 'AISS'], description: 'Hardware-enforced isolation for agent workcells with capability-based memory safety and supply chain authenticity verification.', impact: 'transformative', timelineMonths: 24, a11oyIntegration: 'Agent compartmentalization, Trust anchor attestation, Component provenance', keyInnovation: 'CHERI capability bounds for agent memory isolation' },
  { id: 'rt-adv', name: 'Adversarial Resilience', icon: Shield, darpaPrograms: ['GARD', 'AIxCC', 'BORDEAUX'], description: 'Multi-layer defense against adversarial ML attacks with continuous evaluation and automated response.', impact: 'significant', timelineMonths: 12, a11oyIntegration: 'Constitutional Enforcer, Behavioral Anomaly Detector, Input Sanitizer', keyInnovation: 'Certified defenses with formal guarantees via interval-bound propagation' },
  { id: 'rt-neuro', name: 'Neuromorphic Processing', icon: Brain, darpaPrograms: ['NeuPLASM', 'GrADE'], description: 'Spiking neural network concepts for edge anomaly detection with orders-of-magnitude energy reduction.', impact: 'incremental', timelineMonths: 36, a11oyIntegration: 'Edge signal processing, Ultra-low-latency alerting, Energy-proportional compute', keyInnovation: 'Event-driven anomaly detection without continuous inference' },
  { id: 'rt-rf', name: 'RF / Spectrum Intelligence', icon: Radio, darpaPrograms: ['DSRC', 'SLICE', 'ARC'], description: 'Cognitive spectrum awareness and RF anomaly detection for contested electromagnetic environments.', impact: 'significant', timelineMonths: 24, a11oyIntegration: 'Spectrum monitoring feeds, RF anomaly classification, EW threat correlation', keyInnovation: 'AI-driven spectrum allocation in congested/contested bands' },
  { id: 'rt-fab', name: 'Advanced Fabrication Trust', icon: Microscope, darpaPrograms: ['NGMM', 'TIE', '3DHI'], description: 'Trusted fabrication verification for next-gen semiconductor architectures including 3D heterogeneous integration.', impact: 'incremental', timelineMonths: 36, a11oyIntegration: 'Fab provenance tracking, Chiplet attestation, Die-level verification', keyInnovation: 'Cross-chiplet trust establishment in 3DHI stacks' },
];

const IMPACT_COLORS: Record<string, string> = {
  transformative: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  significant: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  incremental: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
};

export default function CyberInnovationRoadmap() {
  const [expandedPhase, setExpandedPhase] = useState<string>('phase-2');
  const [selectedThread, setSelectedThread] = useState<string | null>(null);

  const thread = RESEARCH_THREADS.find((t) => t.id === selectedThread);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-semibold text-white">Cyber Innovation Roadmap</h1>
            <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border bg-blue-500/10 border-blue-500/20 text-blue-400">
              DARPA-Aligned
            </span>
          </div>
          <p className="text-[13px] text-white/35">
            Strategic evolution of a11oy's cybersecurity vertical — DARPA MTO research threads mapped to product capabilities
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-white/20" aria-hidden="true">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-[10px] text-white/20">a11oy orchestrated</span>
        </div>
      </div>

      <div role="tablist" aria-label="Roadmap phases" className="flex gap-2 overflow-x-auto">
        {PHASES.map((phase) => (
          <button
            type="button"
            role="tab"
            aria-selected={expandedPhase === phase.id}
            aria-pressed={expandedPhase === phase.id}
            aria-label={`Show details for ${phase.label} phase, ${phase.quarter}, status ${phase.status}`}
            key={phase.id}
            onClick={() => setExpandedPhase(phase.id)}
            className={cn(
              'flex-1 min-w-[200px] rounded-xl border p-4 text-left transition-all',
              expandedPhase === phase.id
                ? 'bg-white/[0.04] border-white/[0.12]'
                : 'bg-white/[0.015] border-white/[0.06] hover:bg-white/[0.03]',
            )}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: phase.color }} />
                <span className="text-[10px] font-mono uppercase tracking-wider text-white/25">{phase.quarter}</span>
              </div>
              <span className={cn(
                'text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border',
                phase.status === 'complete' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : phase.status === 'active' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                  : phase.status === 'planned' ? 'bg-purple-500/10 border-purple-500/20 text-purple-400'
                  : 'bg-amber-500/10 border-amber-500/20 text-amber-400',
              )}>
                {phase.status}
              </span>
            </div>
            <h3 className="text-[14px] font-medium text-white">{phase.label}</h3>
            <p className="text-[10px] text-white/20 mt-1">{phase.objectives.length} objectives</p>
          </button>
        ))}
      </div>

      {PHASES.filter((p) => p.id === expandedPhase).map((phase) => (
        <div key={phase.id} className="space-y-3">
          <h2 className="text-[13px] font-medium text-white flex items-center gap-2">
            <Rocket className="w-3.5 h-3.5" style={{ color: phase.color }} />
            {phase.label} — {phase.quarter}
          </h2>
          {phase.objectives.map((obj) => (
            <div key={obj.id} className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-[14px] font-medium text-white mb-0.5">{obj.title}</h3>
                  <p className="text-[11px] text-white/30">{obj.description}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-[9px] font-mono text-white/20 px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.06]">
                    DARPA: {obj.darpaInspiration}
                  </span>
                  <span className="text-[9px] font-mono text-white/20 px-2 py-0.5 rounded bg-white/[0.03] border border-white/[0.06]">
                    TRL {obj.trl}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-3 mb-3">
                <div className="flex-1 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${obj.progress}%`, backgroundColor: phase.color }} />
                </div>
                <span className="text-[11px] font-mono text-white/30 shrink-0">{obj.progress}%</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {obj.deliverables.map((d) => (
                  <span key={d} className="text-[9px] px-2 py-0.5 rounded bg-white/[0.03] text-white/25 border border-white/[0.04]">{d}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div>
        <h2 className="text-[13px] font-medium text-white mb-3 flex items-center gap-2">
          <FlaskConical className="w-3.5 h-3.5 text-white/30" /> Research Threads
        </h2>
        {!thread && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {RESEARCH_THREADS.map((rt) => {
              const Icon = rt.icon;
              return (
                <button
                  type="button"
                  key={rt.id}
                  onClick={() => setSelectedThread(rt.id)}
                  className="text-left bg-white/[0.02] border border-white/[0.06] rounded-xl p-5 hover:bg-white/[0.04] hover:border-white/[0.10] transition-all group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <Icon className="w-4 h-4 text-white/25 group-hover:text-white/50 transition-colors" />
                    <span className={cn('text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border', IMPACT_COLORS[rt.impact])}>
                      {rt.impact}
                    </span>
                  </div>
                  <h3 className="text-[13px] font-medium text-white mb-1">{rt.name}</h3>
                  <p className="text-[11px] text-white/25 mb-3 line-clamp-2">{rt.description}</p>
                  <div className="flex items-center justify-between text-[10px] text-white/15">
                    <span>{rt.darpaPrograms.join(' · ')}</span>
                    <span>{rt.timelineMonths}mo</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
        {thread && (
          <div className="space-y-3">
            <button type="button" onClick={() => setSelectedThread(null)} className="text-[12px] text-white/40 hover:text-white/60 transition-colors">← Back to threads</button>
            <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <thread.icon className="w-5 h-5 text-white/30" />
                  <div>
                    <h3 className="text-lg font-medium text-white">{thread.name}</h3>
                    <p className="text-[11px] text-white/20">{thread.darpaPrograms.join(' · ')} · {thread.timelineMonths} month horizon</p>
                  </div>
                </div>
                <span className={cn('text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border', IMPACT_COLORS[thread.impact])}>
                  {thread.impact}
                </span>
              </div>
              <p className="text-[13px] text-white/40 leading-relaxed mb-4">{thread.description}</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-4">
                  <p className="text-[10px] font-mono uppercase text-white/20 mb-2">a11oy Integration Points</p>
                  <p className="text-[12px] text-white/50 leading-relaxed">{thread.a11oyIntegration}</p>
                </div>
                <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-4">
                  <p className="text-[10px] font-mono uppercase text-white/20 mb-2">Key Innovation</p>
                  <p className="text-[12px] text-white/50 leading-relaxed">{thread.keyInnovation}</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
