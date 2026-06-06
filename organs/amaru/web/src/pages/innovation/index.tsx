import { useState } from 'react';
import { Link } from 'wouter';
import { COMPETITIVE_PROJECTS, INNOVATION_CAPABILITIES } from '@/data/innovation/competitive';
import { FabricHeader, FabricCard, FabricStat } from '@/components/fabric/primitives';
import { Badge } from '@/components/ui';
import { ExternalLink, Star, GitBranch, Lightbulb, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';

const MATURITY_BADGE: Record<string, { label: string; color: string }> = {
  pioneer: { label: 'Pioneer', color: '#d4a853' },
  maturing: { label: 'Maturing', color: '#78aac8' },
  established: { label: 'Established', color: '#5a8a6e' },
  canonical: { label: 'Canonical', color: '#c9b787' },
};

export default function InnovationPage() {
  const [expandedProject, setExpandedProject] = useState<string | null>(null);

  return (
    <div>
      <div className="hero-glow -mx-6 -mt-6 px-6 pt-8 pb-6 mb-6 border-b border-[rgba(255,255,255,0.04)]">
        <div className="flex items-end justify-between gap-6">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.32em] text-[#c9b787] mb-2">AMARU · ONE-OF-ONE · INNOVATION BRIEF</div>
            <h1 className="text-4xl font-light tracking-tight text-[#f5f5f5]">
              <span className="gradient-text">Amaru — One-of-One</span>
            </h1>
            <p className="text-sm text-[#8a8a8a] mt-3 max-w-3xl leading-relaxed">
              A research survey of the leading open-source reverse ETL, activation, and data-movement projects on GitHub — distilled into the 10 original innovations that make Amaru genuinely one-of-one. Leaders are sync engines with dashboards. Amaru is an agentic activation layer.
            </p>
          </div>
          <div className="conduit-card p-4 min-w-[220px] shrink-0">
            <div className="label-mono text-[#c9b787] mb-3">SURVEY SCOPE</div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div><div className="label-mono">Projects</div><div className="font-mono text-[#f5f5f5] text-xl font-light">{COMPETITIVE_PROJECTS.length}</div></div>
              <div><div className="label-mono">Patterns</div><div className="font-mono text-[#f5f5f5] text-xl font-light">{COMPETITIVE_PROJECTS.reduce((s, p) => s + p.patternsAbsorbed.length, 0)}</div></div>
              <div><div className="label-mono">Innovations</div><div className="font-mono text-[#f5f5f5] text-xl font-light">{INNOVATION_CAPABILITIES.length}</div></div>
              <div><div className="label-mono">Status</div><div className="font-mono text-[#5a8a6e] text-sm mt-0.5">All shipped</div></div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <FabricStat label="OSS projects surveyed" value={COMPETITIVE_PROJECTS.length} tone="gold" />
        <FabricStat label="Patterns absorbed" value={COMPETITIVE_PROJECTS.reduce((s, p) => s + p.patternsAbsorbed.length, 0)} />
        <FabricStat label="Original innovations" value={INNOVATION_CAPABILITIES.length} tone="good" />
        <FabricStat label="Agents involved" value={8} />
      </div>

      <FabricCard
        title="THESIS"
        className="mb-6"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 text-[13px]">
          {[
            { label: 'What they are', body: 'Sync engines with dashboards. Point-to-point connectors. Transformation layers that stop at the warehouse edge. Observability tools that alert but don\'t act. Policy engines too general to know what PII is.' },
            { label: 'What Amaru adds', body: 'An agentic activation layer. A coalition of eight specialized agents that plan, map, deliver, govern, verify, forecast, fix, and record — end-to-end, in one proof chain. Replay-grade from the first byte.' },
            { label: 'What makes it one-of-one', body: 'Ten innovations assembled from the best of public patterns, re-implemented as A11oy-native, governed, proof-anchored primitives that no single project in the field has combined. Each innovation links to the relevant Amaru surface.' },
          ].map((item) => (
            <div key={item.label} className="p-4 rounded-lg" style={{ background: 'rgba(201,183,135,0.04)', border: '1px solid rgba(201,183,135,0.1)' }}>
              <div className="label-mono text-[#c9b787] mb-2">{item.label.toUpperCase()}</div>
              <p className="text-[#8a8a8a] leading-relaxed text-[12px]">{item.body}</p>
            </div>
          ))}
        </div>
      </FabricCard>

      <div className="mb-2 flex items-center justify-between">
        <div className="label-mono text-[#c9b787]">COMPETITIVE INTELLIGENCE — {COMPETITIVE_PROJECTS.length} PROJECTS</div>
        <div className="text-[11px] text-[#666]">Click any project to expand patterns</div>
      </div>

      <div className="space-y-3 mb-8">
        {COMPETITIVE_PROJECTS.map((proj) => {
          const isExpanded = expandedProject === proj.id;
          const maturity = MATURITY_BADGE[proj.maturitySignal];
          return (
            <div key={proj.id} className="conduit-card overflow-hidden">
              <button
                className="w-full p-4 text-left"
                onClick={() => setExpandedProject(isExpanded ? null : proj.id)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-[#f5f5f5] font-medium text-sm">{proj.name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ background: `${maturity.color}18`, color: maturity.color }}>{maturity.label}</span>
                      <span className="text-[10px] font-mono text-[#666] border border-[rgba(255,255,255,0.08)] px-1.5 py-0.5 rounded">{proj.license}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-[#666]">
                      <span className="flex items-center gap-1"><Star className="w-3 h-3" /> {proj.githubStars.toLocaleString()}</span>
                      <span className="text-[#444]">·</span>
                      <span>{proj.category}</span>
                      <span className="text-[#444]">·</span>
                      <span className="text-[#c9b787]">{proj.patternsAbsorbed.length} pattern{proj.patternsAbsorbed.length !== 1 ? 's' : ''} absorbed</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="flex gap-1">
                      {proj.innovationLinks.map((link) => {
                        const cap = INNOVATION_CAPABILITIES.find((c) => c.id === link);
                        return cap ? (
                          <span key={link} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[rgba(201,183,135,0.08)] text-[#c9b787] border border-[rgba(201,183,135,0.15)]">#{cap.number}</span>
                        ) : null;
                      })}
                    </div>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-[#666]" /> : <ChevronDown className="w-4 h-4 text-[#666]" />}
                  </div>
                </div>
                <p className="text-[12px] text-[#8a8a8a] mt-2 leading-relaxed">{proj.shortDescription}</p>
              </button>

              {isExpanded && (
                <div className="border-t border-[rgba(255,255,255,0.06)] p-4 space-y-4 animate-fade-in">
                  <div className="space-y-3">
                    {proj.patternsAbsorbed.map((pat, i) => (
                      <div key={i} className="rounded-lg p-3" style={{ background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <div className="flex items-start gap-3">
                          <div className="w-5 h-5 rounded flex items-center justify-center shrink-0 mt-0.5" style={{ background: 'rgba(201,183,135,0.1)' }}>
                            <GitBranch className="w-3 h-3 text-[#c9b787]" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-[#f5f5f5] text-[12px] font-medium mb-1">{pat.pattern}</div>
                            <div className="text-[11px] text-[#666] mb-2">{pat.detail}</div>
                            <div className="flex items-start gap-1.5 mt-2 pt-2 border-t border-[rgba(255,255,255,0.04)]">
                              <Lightbulb className="w-3 h-3 text-[#c9b787] mt-0.5 shrink-0" />
                              <div className="text-[11px] text-[#c9b787] leading-relaxed">{pat.amaruReinterpretation}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-lg p-3" style={{ background: 'rgba(184,84,80,0.06)', border: '1px solid rgba(184,84,80,0.12)' }}>
                    <div className="label-mono text-[#b85450] mb-1">FIELD GAP</div>
                    <p className="text-[11px] text-[#8a8a8a]">{proj.gap}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="label-mono">INNOVATIONS SEEDED</div>
                    {proj.innovationLinks.map((link) => {
                      const cap = INNOVATION_CAPABILITIES.find((c) => c.id === link);
                      return cap ? (
                        <Link key={link} href={cap.route} className="flex items-center gap-1 text-[11px] font-mono text-[#c9b787] hover:underline">
                          #{cap.number} {cap.title} →
                        </Link>
                      ) : null;
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mb-2 label-mono text-[#c9b787]">ONE-OF-ONE CAPABILITY SURFACE — 10 INNOVATIONS</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
        {INNOVATION_CAPABILITIES.map((cap) => (
          <Link key={cap.id} href={cap.route} className="conduit-card p-4 block">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 font-mono font-bold text-[11px] text-[#c9b787]" style={{ background: 'rgba(201,183,135,0.1)', border: '1px solid rgba(201,183,135,0.2)' }}>
                  {String(cap.number).padStart(2, '0')}
                </div>
                <div>
                  <div className="text-[#f5f5f5] text-sm font-medium">{cap.title}</div>
                  <div className="text-[11px] text-[#8a8a8a] mt-0.5">{cap.tagline}</div>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-[#c9b787] shrink-0 mt-1" />
            </div>
            <div className="flex items-center gap-2 mt-3">
              {cap.agents.map((a) => <Badge key={a} variant="default">{a}</Badge>)}
              {cap.crossLink.map((cl) => (
                <span key={cl.route} className="text-[10px] font-mono text-[#666]">↔ {cl.label}</span>
              ))}
            </div>
          </Link>
        ))}
      </div>

      <FabricCard title="DEPLOYMENT READINESS NOTE" className="mb-6">
        <div className="space-y-3 text-[12px] text-[#8a8a8a] leading-relaxed">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3 rounded-lg" style={{ background: 'rgba(90,138,110,0.06)', border: '1px solid rgba(90,138,110,0.12)' }}>
              <div className="label-mono text-[#5a8a6e] mb-2">SEEDED (deterministic)</div>
              <ul className="space-y-1 text-[11px]">
                <li>· Competitive intelligence brief data</li>
                <li>· Schema drift proposals with diff/blast radius</li>
                <li>· Golden record candidate clusters</li>
                <li>· Cost/carbon estimates (model-based)</li>
                <li>· Simulation Theater failure scenarios</li>
                <li>· Mapper recommendation history</li>
                <li>· Policy DSL version history</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg" style={{ background: 'rgba(201,183,135,0.06)', border: '1px solid rgba(201,183,135,0.12)' }}>
              <div className="label-mono text-[#c9b787] mb-2">ADAPTER-BACKED (simulation)</div>
              <ul className="space-y-1 text-[11px]">
                <li>· Destination Contract Auto-Discovery probe</li>
                <li>· Reverse-Reverse ETL mutation capture</li>
                <li>· Activation Simulation Theater replay</li>
                <li>· Audience SQL row-count preview</li>
                <li>· Mapper accuracy accept/reject actions</li>
              </ul>
            </div>
            <div className="p-3 rounded-lg" style={{ background: 'rgba(120,170,200,0.06)', border: '1px solid rgba(120,170,200,0.12)' }}>
              <div className="label-mono text-[#78aac8] mb-2">PERSISTED (local state)</div>
              <ul className="space-y-1 text-[11px]">
                <li>· Audience records created in Studio</li>
                <li>· Drift repair proposal approvals</li>
                <li>· Golden record merges</li>
                <li>· Destination discovery syntheses</li>
                <li>· Policy DSL rule edits + versions</li>
                <li>· Reverse-Reverse ETL outcome injections</li>
              </ul>
            </div>
          </div>
          <p className="text-[11px] text-[#555] pt-2">
            All seed data is deterministic across restarts (no Math.random() or Date.now() at module load). No real external writes. No real credentials captured. No PII in seed data. API contract with artifacts/api-server remains backward-compatible.
          </p>
        </div>
      </FabricCard>

      <div className="flex items-center justify-between py-4 px-4 rounded-lg" style={{ background: 'rgba(201,183,135,0.04)', border: '1px solid rgba(201,183,135,0.08)' }}>
        <div className="text-[12px] text-[#666]">Amaru · One-of-One Innovation Brief · May 2026</div>
        <a href="/" className="flex items-center gap-1.5 text-[12px] text-[#c9b787] hover:underline">
          <ExternalLink className="w-3 h-3" />
          Back to Cockpit
        </a>
      </div>
    </div>
  );
}
