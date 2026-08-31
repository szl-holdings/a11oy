import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Telescope,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { PageHeader } from '@/lib/data-provenance';
import {
  threatHorizonVectors as fallbackVectors,
  type ThreatHorizonVector,
  type ThreatMaturity,
} from '@/data/quantum-resilience';
import { listThreatHorizonVectors } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

const maturityColor: Record<ThreatMaturity, string> = {
  theoretical: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  lab_demonstrated: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30',
  weaponizable: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/30',
  actively_exploited: 'bg-red-500/10 text-red-400 border-red-500/30',
};

const maturityLabel: Record<ThreatMaturity, string> = {
  theoretical: 'THEORETICAL',
  lab_demonstrated: 'LAB DEMONSTRATED',
  weaponizable: 'WEAPONIZABLE',
  actively_exploited: 'ACTIVELY EXPLOITED',
};

const impactColor: Record<string, string> = {
  catastrophic: 'text-red-400',
  critical: 'text-[#f5f5f5]',
  high: 'text-[#c9b787]',
  medium: 'text-[#c9b787]',
  low: 'text-slate-400',
};

const categoryLabel: Record<string, string> = {
  quantum_decryption: 'Quantum Decryption',
  photonic_side_channel: 'Photonic Side-Channel',
  bio_exploit: 'Bio-System Exploit',
  microsystem_supply_chain: 'Microsystem Supply Chain',
  cryogenic_attack: 'Cryogenic Attack',
  ai_hardware_poisoning: 'AI Hardware Poisoning',
};

const categoryIcon: Record<string, string> = {
  quantum_decryption: '⚛',
  photonic_side_channel: '〰',
  bio_exploit: '🧬',
  microsystem_supply_chain: '⊡',
  cryogenic_attack: '❄',
  ai_hardware_poisoning: '⬡',
};

function CountdownBadge({ years }: { years: number | null }) {
  if (years === null) {
    return (
      <div className="flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#f5f5f5]" />
        <span className="text-sm font-display font-bold text-[#f5f5f5]">NOW</span>
        <span className="text-[9px] text-slate-500 font-mono">ACTIVE THREAT</span>
      </div>
    );
  }

  const color = years <= 3 ? '#f5f5f5' : years <= 7 ? '#c9b787' : '#8a8a8a';

  return (
    <div className="flex items-center gap-2">
      <Clock className="w-3.5 h-3.5" style={{ color }} />
      <span className="text-2xl font-display font-bold" style={{ color }}>
        {years}
      </span>
      <span className="text-[10px] text-slate-500 font-mono">YEARS</span>
    </div>
  );
}

function VectorCard({ vector }: { vector: ThreatHorizonVector }) {
  const [expanded, setExpanded] = useState(false);
  const daysAgo = Math.round(
    (Date.now() - new Date(vector.lastUpdatedAt).getTime()) / 86_400_000
  );

  return (
    <div
      className={`sentra-card p-5 space-y-4 cursor-pointer transition-colors hover:bg-slate-800/20 ${vector.maturity === 'actively_exploited' ? 'ring-1 ring-red-500/30' : vector.maturity === 'weaponizable' ? 'ring-1 ring-[#f5f5f5]/20' : ''}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">{categoryIcon[vector.category]}</span>
            <span className="text-[10px] text-slate-500 font-mono uppercase">
              {categoryLabel[vector.category]}
            </span>
          </div>
          <div className="text-sm font-bold text-slate-200">{vector.title}</div>
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold border shrink-0 ${maturityColor[vector.maturity]}`}
        >
          {maturityLabel[vector.maturity]}
        </span>
      </div>

      <div className="flex items-center justify-between">
        <CountdownBadge years={vector.yearsToWeaponization} />
        <div className="text-right">
          <div className="text-[10px] text-slate-500 font-mono uppercase">Impact</div>
          <div className={`text-xs font-mono font-bold ${impactColor[vector.impactSeverity]}`}>
            {vector.impactSeverity.toUpperCase()}
          </div>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">{vector.description}</p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {vector.mitigationAvailable ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-2.5 h-2.5" />
              MITIGATION AVAILABLE
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-[#f5f5f5]/10 text-[#f5f5f5] border border-[#f5f5f5]/20">
              <XCircle className="w-2.5 h-2.5" />
              NO MITIGATION
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-600 font-mono">Updated {daysAgo}d ago</span>
      </div>

      {vector.darpaProgram && (
        <div className="px-3 py-2 rounded bg-sky-500/5 border border-sky-500/15">
          <div className="text-[10px] font-mono text-sky-400">{vector.darpaProgram}</div>
        </div>
      )}

      {expanded && (
        <div className="pt-3 border-t border-slate-800 space-y-3">
          <div>
            <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">
              Affected Sectors
            </div>
            <div className="flex flex-wrap gap-1">
              {vector.affectedSectors.map((s) => (
                <span
                  key={s}
                  className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-800 text-slate-400 border border-slate-700"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Sources</div>
            <div className="space-y-1">
              {vector.sources.map((s) => (
                <div key={s} className="text-[10px] text-slate-400 font-mono">
                  {s}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DarpaThreatHorizon() {
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  const fetcher = useCallback(() => listThreatHorizonVectors(), []);
  const { data: threatHorizonVectors, source } = useApiQuery<ThreatHorizonVector[]>(fetcher, 'vectors', fallbackVectors);

  const activelyExploited = threatHorizonVectors.filter(
    (v) => v.maturity === 'actively_exploited'
  ).length;
  const weaponizable = threatHorizonVectors.filter(
    (v) => v.maturity === 'weaponizable'
  ).length;
  const noMitigation = threatHorizonVectors.filter((v) => !v.mitigationAvailable).length;

  const categories = Array.from(new Set(threatHorizonVectors.map((v) => v.category)));

  const filtered =
    categoryFilter === 'all'
      ? threatHorizonVectors
      : threatHorizonVectors.filter((v) => v.category === categoryFilter);

  const sorted = [...filtered].sort((a, b) => {
    const maturityOrder: Record<ThreatMaturity, number> = {
      actively_exploited: 0,
      weaponizable: 1,
      lab_demonstrated: 2,
      theoretical: 3,
    };
    return maturityOrder[a.maturity] - maturityOrder[b.maturity];
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="DARPA Threat Horizon"
        subtitle="Strategic intelligence on emerging threat vectors from advanced R&D programs"
        provenance={source}
        provenanceLabel={source === 'live' ? 'Live API' : 'Seed Data'}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Tracked Vectors</div>
          <div className="text-2xl font-display font-bold text-slate-200">
            {threatHorizonVectors.length}
          </div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Active Exploits</div>
          <div className="text-2xl font-display font-bold text-red-400">{activelyExploited}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Weaponizable</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{weaponizable}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">No Mitigation</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{noMitigation}</div>
        </div>
      </div>

      <div className="sentra-panel p-5 space-y-3">
        <h2 className="text-sm font-display font-bold flex items-center gap-2">
          <Telescope className="w-4 h-4 text-[#c9b787]" />
          Threat Maturity Timeline
        </h2>
        <div className="relative">
          <div className="absolute top-4 left-0 right-0 h-0.5 bg-slate-800" />
          <div className="flex justify-between relative">
            {(['theoretical', 'lab_demonstrated', 'weaponizable', 'actively_exploited'] as ThreatMaturity[]).map(
              (stage) => {
                const count = threatHorizonVectors.filter((v) => v.maturity === stage).length;
                return (
                  <div key={stage} className="flex flex-col items-center text-center z-10">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-display font-bold border-2 ${maturityColor[stage]}`}
                    >
                      {count}
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono mt-2 max-w-[80px]">
                      {maturityLabel[stage]}
                    </div>
                  </div>
                );
              }
            )}
          </div>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setCategoryFilter('all')}
          className={`px-3 py-1.5 rounded text-[10px] font-mono border transition-colors ${categoryFilter === 'all' ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30' : 'bg-slate-900 text-slate-500 border-slate-800 hover:text-slate-300'}`}
        >
          ALL ({threatHorizonVectors.length})
        </button>
        {categories.map((cat) => {
          const count = threatHorizonVectors.filter((v) => v.category === cat).length;
          return (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded text-[10px] font-mono border transition-colors ${categoryFilter === cat ? 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30' : 'bg-slate-900 text-slate-500 border-slate-800 hover:text-slate-300'}`}
            >
              {categoryIcon[cat]} {categoryLabel[cat]} ({count})
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sorted.map((vector) => (
          <VectorCard key={vector.id} vector={vector} />
        ))}
      </div>

      <div className="text-[10px] text-slate-600 font-mono text-center">
        Intelligence sourced from DARPA MTO SPARK Tank priorities · NIST · NSA CNSA 2.0 · Academic research
      </div>
    </div>
  );
}
