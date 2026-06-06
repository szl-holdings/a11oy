import {
  Activity,
  AlertTriangle,
  Dna,
  Thermometer,
} from 'lucide-react';
import { useCallback } from 'react';
import { PageHeader } from '@/lib/data-provenance';
import {
  bioSubstrateAssets as fallbackAssets,
  type BioIntegrity,
  type BioSubstrateAsset,
} from '@/data/quantum-resilience';
import { listBioSubstrateAssets } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

const integrityColor: Record<BioIntegrity, string> = {
  nominal: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  degraded: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30',
  contaminated: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
  expired: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  compromised: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/30',
};

function LifespanBar({ current, max }: { current: number; max: number }) {
  const pct = Math.min(100, (current / max) * 100);
  const remaining = max - current;
  const remainingDays = Math.round(remaining / 24);
  const color = pct > 80 ? '#f5f5f5' : pct > 60 ? '#c9b787' : '#34d399';

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] font-mono">
        <span className="text-slate-500">{Math.round(pct)}% consumed</span>
        <span style={{ color }}>{remainingDays}d remaining</span>
      </div>
      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function SubstrateCard({ asset }: { asset: BioSubstrateAsset }) {
  const tempInRange =
    asset.temperatureCelsius >= asset.temperatureRange[0] &&
    asset.temperatureCelsius <= asset.temperatureRange[1];

  return (
    <div
      className={`sentra-card p-5 space-y-4 ${asset.integrity === 'compromised' ? 'ring-1 ring-[#f5f5f5]/30' : ''}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <Dna className="w-4 h-4 text-[#c9b787]" />
            {asset.name}
          </div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">
            {asset.type.replace(/_/g, ' ').toUpperCase()}
          </div>
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${integrityColor[asset.integrity]}`}
        >
          {asset.integrity.toUpperCase()}
        </span>
      </div>

      <div>
        <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Substrate</div>
        <div className="text-xs text-slate-300">{asset.substrate}</div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Temperature</div>
          <div className="flex items-center gap-2">
            <Thermometer
              className={`w-3.5 h-3.5 ${tempInRange ? 'text-emerald-400' : 'text-[#f5f5f5]'}`}
            />
            <span
              className={`text-sm font-mono font-bold ${tempInRange ? 'text-emerald-400' : 'text-[#f5f5f5]'}`}
            >
              {asset.temperatureCelsius}°C
            </span>
            <span className="text-[9px] text-slate-600 font-mono">
              [{asset.temperatureRange[0]}–{asset.temperatureRange[1]}]
            </span>
          </div>
        </div>
        <div>
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Contamination</div>
          <div className="flex items-center gap-2">
            <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${asset.contaminationRisk}%`,
                  background:
                    asset.contaminationRisk > 50
                      ? '#f5f5f5'
                      : asset.contaminationRisk > 20
                        ? '#c9b787'
                        : '#34d399',
                }}
              />
            </div>
            <span className="text-xs font-mono text-slate-300">{asset.contaminationRisk}%</span>
          </div>
        </div>
      </div>

      <LifespanBar current={asset.operationalHours} max={asset.maxLifespanHours} />

      <div>
        <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Encryption</div>
        <div className="text-[10px] text-slate-400 font-mono">{asset.encryptionMethod}</div>
      </div>

      {asset.dataExfiltrationVector && (
        <div className="flex items-start gap-2 px-3 py-2 rounded bg-[#f5f5f5]/5 border border-[#f5f5f5]/15">
          <AlertTriangle className="w-3.5 h-3.5 text-[#c9b787] mt-0.5 shrink-0" />
          <div>
            <div className="text-[10px] font-mono font-bold text-[#c9b787]">
              BIO-DATA EXFILTRATION VECTOR
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {asset.dataExfiltrationVector}
            </div>
          </div>
        </div>
      )}

      <div className="text-[10px] text-slate-600 font-mono">{asset.location}</div>
    </div>
  );
}

export default function BioCyberConvergence() {
  const fetcher = useCallback(() => listBioSubstrateAssets(), []);
  const { data: bioSubstrateAssets, source } = useApiQuery<BioSubstrateAsset[]>(fetcher, 'assets', fallbackAssets);

  const nominal = bioSubstrateAssets.filter((a) => a.integrity === 'nominal').length;
  const compromised = bioSubstrateAssets.filter((a) => a.integrity === 'compromised').length;
  const exfilVectors = bioSubstrateAssets.filter((a) => a.dataExfiltrationVector).length;
  const avgContamination = bioSubstrateAssets.length > 0 ? Math.round(
    bioSubstrateAssets.reduce((a, b) => a + b.contaminationRisk, 0) / bioSubstrateAssets.length
  ) : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Bio-Cyber Convergence Console"
        subtitle="Security monitoring for bio-electronic hybrid systems and organic circuits"
        provenance={source}
        provenanceLabel={source === 'live' ? 'Live API' : 'Seed Data'}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Nominal</div>
          <div className="text-2xl font-display font-bold text-emerald-400">{nominal}</div>
          <div className="text-[10px] text-slate-500 font-mono">
            of {bioSubstrateAssets.length}
          </div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Compromised</div>
          <div className="text-2xl font-display font-bold text-[#f5f5f5]">{compromised}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Exfil Vectors</div>
          <div className="text-2xl font-display font-bold text-[#c9b787]">{exfilVectors}</div>
        </div>
        <div className="sentra-panel p-4 text-center">
          <div className="text-[10px] text-slate-500 font-mono uppercase mb-1">Avg Contamination</div>
          <div
            className="text-2xl font-display font-bold"
            style={{
              color:
                avgContamination > 50
                  ? '#f5f5f5'
                  : avgContamination > 20
                    ? '#c9b787'
                    : '#34d399',
            }}
          >
            {avgContamination}%
          </div>
        </div>
      </div>

      <div className="sentra-panel p-5 space-y-3">
        <h2 className="text-sm font-display font-bold flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#c9b787]" />
          Substrate Type Distribution
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            'dna_storage',
            'protein_compute',
            'biosensor_array',
            'organic_circuit',
            'neural_interface',
            'molecular_switch',
          ].map((t) => {
            const count = bioSubstrateAssets.filter((a) => a.type === t).length;
            const compromisedCount = bioSubstrateAssets.filter(
              (a) => a.type === t && a.integrity === 'compromised'
            ).length;
            return (
              <div key={t} className="sentra-card p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-mono">
                    {t.replace(/_/g, ' ').toUpperCase()}
                  </span>
                  <span className="text-sm font-display font-bold text-slate-200">{count}</span>
                </div>
                {compromisedCount > 0 && (
                  <div className="text-[9px] text-[#f5f5f5] font-mono mt-1">
                    {compromisedCount} COMPROMISED
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {bioSubstrateAssets.map((asset) => (
          <SubstrateCard key={asset.id} asset={asset} />
        ))}
      </div>

      <div className="text-[10px] text-slate-600 font-mono text-center">
        Bio-cyber monitoring aligned with DARPA Safe Genes program · Substrate health per ISO 20387 biobanking standards
      </div>
    </div>
  );
}
