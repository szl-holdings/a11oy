import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Brain,
  CircuitBoard,
  Cpu,
  FileText,
  FlaskConical,
  GitBranch,
  Globe,
  Layers,
  Lock,
  Microscope,
  Network,
  Radiation,
  Scan,
  Shield,
  ShieldCheck,
  Sparkles,
  Waves,
  Zap,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { DARPA_MTO_DOMAINS as fallbackDomains, CYBER_AI_REPOS as fallbackRepos, type ResearchDomain } from '@/data/darpa-mto-research';
import { listDarpaMtoDomains, listDarpaMtoCyberAiRepos } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

const STATUS_BADGE: Record<ResearchDomain['status'], { label: string; color: string }> = {
  incubation: { label: 'Incubation', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  active: { label: 'Active', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  reference: { label: 'Reference', color: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
};

const DOMAIN_ICONS: Record<ResearchDomain['id'], typeof Shield> = {
  'photonic-inference': Zap,
  'quantum-resilience': Lock,
  'skyrmion-memory': CircuitBoard,
  'circuits-on-demand': Cpu,
  'nanofluidic-computing': Brain,
  'optical-comms': Waves,
  '3d-microsystems': Layers,
  'flexoelectric-sensors': Scan,
  'molecular-machines': FlaskConical,
  'directed-energy-systems': Radiation,
  'bio-apertures': Microscope,
  'physical-intelligence': Network,
  'lunar-supply-chain': Globe,
};

function TrlBar({ trl }: { trl: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">TRL</span>
      <div className="flex gap-0.5">
        {Array.from({ length: 9 }, (_, i) => (
          <div
            key={i}
            className={cn(
              'w-2.5 h-1.5 rounded-[1px]',
              i < trl
                ? trl >= 7
                  ? 'bg-emerald-500'
                  : trl >= 4
                    ? 'bg-amber-500'
                    : 'bg-red-400'
                : 'bg-white/[0.06]',
            )}
          />
        ))}
      </div>
      <span className="text-[10px] font-mono text-white/40">{trl}/9</span>
    </div>
  );
}

function DomainCard({ domain, onClick }: { domain: ResearchDomain; onClick: () => void }) {
  const status = STATUS_BADGE[domain.status];
  const Icon = DOMAIN_ICONS[domain.id] ?? Shield;
  return (
    <button
      onClick={onClick}
      className="text-left bg-white/[0.02] border border-white/[0.06] rounded-xl p-5 hover:bg-white/[0.04] hover:border-white/[0.10] transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <Icon className="w-5 h-5 text-white/25 group-hover:text-white/50 transition-colors" />
        <span className={cn('text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border', status.color)}>
          {status.label}
        </span>
      </div>
      <h3 className="text-[14px] font-medium text-white mb-1.5 group-hover:text-white transition-colors">
        {domain.title}
      </h3>
      <p className="text-[11px] font-mono text-white/30 mb-2">{domain.darpaProgram}</p>
      <p className="text-[12px] text-white/35 leading-relaxed mb-3">{domain.cyberApplication}</p>
      <TrlBar trl={domain.trl} />
    </button>
  );
}

function DomainDetail({ domain, onBack }: { domain: ResearchDomain; onBack: () => void }) {
  const status = STATUS_BADGE[domain.status];
  const Icon = DOMAIN_ICONS[domain.id] ?? Shield;

  return (
    <div className="space-y-6">
      <button
        onClick={onBack}
        className="text-[12px] text-white/40 hover:text-white/60 transition-colors flex items-center gap-1"
      >
        ← Back to research map
      </button>

      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
          <Icon className="w-6 h-6 text-white/40" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-semibold text-white">{domain.title}</h1>
            <span className={cn('text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border', status.color)}>
              {status.label}
            </span>
          </div>
          <p className="text-[12px] font-mono text-white/30">{domain.darpaProgram}</p>
          {domain.programManager && (
            <p className="text-[11px] text-white/25 mt-0.5">PM: {domain.programManager}</p>
          )}
        </div>
        <TrlBar trl={domain.trl} />
      </div>

      <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
        <h2 className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-3">
          Cyber Application
        </h2>
        <p className="text-[14px] text-white/70 font-medium mb-4">{domain.cyberApplication}</p>
        <p className="text-[13px] text-white/40 leading-relaxed">{domain.description}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-3 flex items-center gap-2">
            <Sparkles className="w-3 h-3" /> Key Breakthroughs
          </h2>
          <ul className="space-y-2.5">
            {domain.keyBreakthroughs.map((b, i) => (
              <li key={i} className="flex gap-2 text-[12px] text-white/45 leading-relaxed">
                <span className="text-emerald-500 mt-0.5 shrink-0">&#x2022;</span>
                {b}
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-3 flex items-center gap-2">
            <Shield className="w-3 h-3" /> a11oy Integration
          </h2>
          <p className="text-[12px] text-white/45 leading-relaxed">{domain.a11oyIntegration}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-3 flex items-center gap-2">
            <GitBranch className="w-3 h-3" /> Top Repositories
          </h2>
          <div className="space-y-2.5">
            {domain.topRepos.map((repo) => (
              <div key={repo.name} className="flex items-center justify-between">
                <div>
                  <span className="text-[12px] text-white/60 font-mono">{repo.org}/{repo.name}</span>
                  <p className="text-[10px] text-white/25">{repo.tech}</p>
                </div>
                {repo.stars && (
                  <span className="text-[10px] font-mono text-white/20">{repo.stars}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-[11px] font-mono uppercase tracking-wider text-white/40 mb-3 flex items-center gap-2">
            <FileText className="w-3 h-3" /> Key Publications
          </h2>
          <div className="space-y-2.5">
            {domain.topPapers.map((paper) => (
              <div key={paper.title}>
                <p className="text-[12px] text-white/50 leading-snug">{paper.title}</p>
                <p className="text-[10px] text-white/25 mt-0.5">{paper.venue} · {paper.year}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DarpaMtoHub() {
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [showRepos, setShowRepos] = useState(false);

  const domainFetcher = useCallback(() => listDarpaMtoDomains(), []);
  const repoFetcher = useCallback(() => listDarpaMtoCyberAiRepos(), []);
  const { data: DARPA_MTO_DOMAINS } = useApiQuery<ResearchDomain[]>(domainFetcher, 'domains', fallbackDomains);
  const { data: CYBER_AI_REPOS } = useApiQuery<typeof fallbackRepos>(repoFetcher, 'repos', fallbackRepos);

  const domain = DARPA_MTO_DOMAINS.find((d) => d.id === selectedDomain);

  const activeDomains = DARPA_MTO_DOMAINS.filter((d) => d.status === 'active');
  const incubationDomains = DARPA_MTO_DOMAINS.filter((d) => d.status === 'incubation');

  const avgTrl = DARPA_MTO_DOMAINS.length > 0 ? Math.round(
    DARPA_MTO_DOMAINS.reduce((sum, d) => sum + d.trl, 0) / DARPA_MTO_DOMAINS.length * 10,
  ) / 10 : 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-semibold text-white">DARPA MTO Innovation Hub</h1>
            <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border bg-white/[0.03] border-white/[0.08] text-white/40">
              Research Intelligence
            </span>
          </div>
          <p className="text-[13px] text-white/35">
            {DARPA_MTO_DOMAINS.length} DARPA Microsystems Technology Office research domains mapped to a11oy cybersecurity applications
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-white/20">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-[10px] text-white/20">a11oy orchestrated</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-white">{DARPA_MTO_DOMAINS.length}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Research Domains</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-emerald-400">{activeDomains.length}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Active Programs</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-amber-400">{incubationDomains.length}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Under Incubation</p>
        </div>
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-4 text-center">
          <p className="text-2xl font-semibold text-white">{avgTrl}</p>
          <p className="text-[10px] uppercase tracking-wider text-white/25 mt-0.5">Avg TRL</p>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => { setSelectedDomain(null); setShowRepos(false); }}
          className={cn(
            'px-3 py-1.5 rounded-lg text-[12px] border transition-colors',
            !selectedDomain && !showRepos
              ? 'bg-white/[0.06] border-white/[0.12] text-white'
              : 'bg-transparent border-white/[0.06] text-white/40 hover:text-white/60',
          )}
        >
          Research Map
        </button>
        <button
          onClick={() => { setSelectedDomain(null); setShowRepos(true); }}
          className={cn(
            'px-3 py-1.5 rounded-lg text-[12px] border transition-colors',
            showRepos
              ? 'bg-white/[0.06] border-white/[0.12] text-white'
              : 'bg-transparent border-white/[0.06] text-white/40 hover:text-white/60',
          )}
        >
          Top GitHub Repos
        </button>
      </div>

      {domain ? (
        <DomainDetail domain={domain} onBack={() => setSelectedDomain(null)} />
      ) : showRepos ? (
        <div className="space-y-4">
          <h2 className="text-[15px] font-medium text-white">
            Reference Open-Source Cybersecurity & PQC Repositories
          </h2>
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl overflow-hidden">
            <div className="grid grid-cols-12 gap-3 px-5 py-2.5 border-b border-white/[0.04] text-[10px] font-mono uppercase tracking-wider text-white/25">
              <div className="col-span-4">Repository</div>
              <div className="col-span-4">Description</div>
              <div className="col-span-2">Stars</div>
              <div className="col-span-2">License</div>
            </div>
            {CYBER_AI_REPOS.map((repo) => (
              <div
                key={repo.name}
                className="grid grid-cols-12 gap-3 items-center px-5 py-3 border-b border-white/[0.03] hover:bg-white/[0.015] transition-colors"
              >
                <div className="col-span-4">
                  <span className="text-[12px] font-mono text-white/60">{repo.org}/</span>
                  <span className="text-[12px] font-mono text-white/80">{repo.name}</span>
                </div>
                <div className="col-span-4 text-[11px] text-white/35">{repo.desc}</div>
                <div className="col-span-2 text-[11px] font-mono text-white/30">{repo.stars}</div>
                <div className="col-span-2 text-[10px] font-mono text-white/20">{repo.license}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <div className="mb-4">
            <h2 className="text-[13px] font-medium text-emerald-400 mb-3 flex items-center gap-2">
              <ShieldCheck className="w-3.5 h-3.5" /> Active Programs
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {activeDomains.map((d) => (
                <DomainCard key={d.id} domain={d} onClick={() => setSelectedDomain(d.id)} />
              ))}
            </div>
          </div>
          <div>
            <h2 className="text-[13px] font-medium text-amber-400 mb-3 mt-6 flex items-center gap-2">
              <FlaskConical className="w-3.5 h-3.5" /> Under Incubation
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {incubationDomains.map((d) => (
                <DomainCard key={d.id} domain={d} onClick={() => setSelectedDomain(d.id)} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
