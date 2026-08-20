import { AMARU_ROADMAP } from '@/data/fabric';
import { FabricHeader } from '@/components/fabric/primitives';
import { Badge } from '@/components/ui';

export default function RoadmapPage() {
  return (
    <div>
      <FabricHeader
        eyebrow="ACTIVATION FABRIC · 09"
        title="Roadmap"
        blurb="Six phases from discover to federate. Phases 1–2 complete, 3–4 active, 5–6 planned. Each phase carries explicit capabilities, vertical impact, and the evidence the Codex Kernel ledger has already captured."
      />
      <div className="space-y-4">
        {AMARU_ROADMAP.map((p) => (
          <div key={p.id} className="conduit-card p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[10px] tracking-[0.2em] text-[#c9b787]">PHASE {p.phase.toString().padStart(2, '0')}</span>
                  <Badge variant={p.status === 'complete' ? 'success' : p.status === 'active' ? 'active' : 'draft'}>{p.status}</Badge>
                </div>
                <h2 className="text-2xl font-light text-[#f5f5f5] mt-1">{p.title} <span className="text-[#666] text-base font-normal italic">— {p.tagline}</span></h2>
              </div>
            </div>
            <p className="text-[13px] text-[#8a8a8a] leading-relaxed mb-4 max-w-3xl">{p.description}</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
              <div>
                <div className="label-mono mb-1 text-[#c9b787]">CAPABILITIES</div>
                <ul className="space-y-0.5 text-[#8a8a8a]">{p.capabilities.map((c, i) => <li key={i}>· {c}</li>)}</ul>
              </div>
              <div>
                <div className="label-mono mb-1 text-[#c9b787]">VERTICAL IMPACT</div>
                <div className="flex flex-wrap gap-1">{p.verticalImpact.map((v) => <Badge key={v} variant="default">{v}</Badge>)}</div>
              </div>
              <div>
                <div className="label-mono mb-1 text-[#c9b787]">EVIDENCE</div>
                <ul className="space-y-0.5 font-mono text-[#666]">{p.evidence.map((e, i) => <li key={i}>· {e}</li>)}</ul>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
