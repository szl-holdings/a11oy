import { cn } from '@szl-holdings/shared-ui/utils';
import {
  Activity,
  CheckCircle2,
  Clock,
  Loader2,
  Plus,
  Shield,
  Users,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'wouter';

const BASE = '/api';

type ThreatArchetype =
  | 'ransomware'
  | 'insider'
  | 'supply_chain'
  | 'regulatory'
  | 'cascade'
  | 'black_swan';
type SubmissionStatus = 'pending' | 'accepted' | 'duplicate' | 'out_of_scope' | 'rejected' | 'graduated';

interface Engagement {
  id: string;
  title: string;
  description: string;
  scopedAssets: string[];
  scopedDomains: string[];
  archetypeFilter: ThreatArchetype[];
  payoutPool: number;
  deadline: string;
  status: string;
  submissionCount: number;
  acceptedCount: number;
}

interface KillChainStep {
  phase: string;
  technique: string;
  description: string;
}

interface Submission {
  id: string;
  engagementId: string;
  title: string;
  archetype: ThreatArchetype;
  businessImpactScore: number;
  status: SubmissionStatus;
  reputationAwarded: number;
  payoutAwarded: number;
  triageJustification?: string;
  submittedAt: string;
  updatedAt: string;
  graduatedIncidentId?: string;
  impactEstimate: {
    revenueAtRiskUsd: number;
    rtoBreach: number;
    rpoBreach: number;
    regulatoryExposureUsd: number;
    blastRadiusDomains: string[];
  };
}

interface ScoreResult {
  businessImpactScore: number;
  breakdown: {
    revenueComponent: number;
    rtoComponent: number;
    rpoComponent: number;
    regulatoryComponent: number;
    blastRadiusComponent: number;
  };
  tier: string;
  estimatedReputation: number;
}

const STATUS_STYLE: Record<SubmissionStatus, string> = {
  pending: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30',
  accepted: 'bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30',
  graduated: 'bg-[#8a8a8a]/10 text-[#8a8a8a] border-sky-500/30',
  rejected: 'bg-[#f5f5f5]/10 text-[#f5f5f5] border-[#f5f5f5]/30',
  duplicate: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  out_of_scope: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
};

const ARCHETYPE_COLORS: Record<ThreatArchetype, string> = {
  ransomware: 'text-[#f5f5f5]',
  cascade: 'text-[#c9b787]',
  supply_chain: 'text-[#c9b787]',
  regulatory: 'text-[#8a8a8a]',
  insider: 'text-[#f5f5f5]',
  black_swan: 'text-[#f5f5f5]',
};

function formatUsd(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function daysUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff < 0) return 'Expired';
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return 'Today';
  return `${days}d`;
}

async function readCsrfToken(): Promise<string | null> {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  if (m) return decodeURIComponent(m[1]);
  try {
    await fetch(`${BASE}/csrf-token`, { credentials: 'include' });
    const m2 = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return m2 ? decodeURIComponent(m2[1]) : null;
  } catch {
    return null;
  }
}

async function apiPost<T>(path: string, body: unknown): Promise<T | null> {
  const csrf = await readCsrfToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (csrf) headers['X-CSRF-Token'] = csrf;
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!res.ok) return null;
  return res.json() as Promise<T>;
}

interface SubmitModalProps {
  engagement: Engagement;
  onClose: () => void;
  onSubmit: (sub: Submission) => void;
}

function SubmitModal({ engagement, onClose, onSubmit }: SubmitModalProps) {
  const [form, setForm] = useState({
    title: '',
    narrative: '',
    archetype: 'ransomware' as ThreatArchetype,
    killChain: [{ phase: 'Initial Access', technique: '', description: '' }] as KillChainStep[],
    revenueAtRiskUsd: 0,
    rtoBreach: 0,
    rpoBreach: 0,
    regulatoryExposureUsd: 0,
    blastRadiusDomains: engagement.scopedDomains.join(', '),
    evidenceNotes: '',
  });
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const computeScore = async () => {
    setScoring(true);
    const result = await apiPost<ScoreResult>('/crisis-arena/score', {
      impactEstimate: {
        revenueAtRiskUsd: form.revenueAtRiskUsd,
        rtoBreach: form.rtoBreach,
        rpoBreach: form.rpoBreach,
        regulatoryExposureUsd: form.regulatoryExposureUsd,
        blastRadiusDomains: form.blastRadiusDomains
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      },
      archetype: form.archetype,
    });
    setScoring(false);
    if (result) setScore(result);
  };

  const addStep = () =>
    setForm((f) => ({
      ...f,
      killChain: [...f.killChain, { phase: '', technique: '', description: '' }],
    }));

  const updateStep = (i: number, field: keyof KillChainStep, value: string) =>
    setForm((f) => {
      const kc = [...f.killChain];
      kc[i] = { ...kc[i], [field]: value };
      return { ...f, killChain: kc };
    });

  const removeStep = (i: number) =>
    setForm((f) => ({ ...f, killChain: f.killChain.filter((_, idx) => idx !== i) }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.narrative || form.killChain.some((s) => !s.phase || !s.technique)) {
      setError('Fill in all required fields including kill chain steps.');
      return;
    }
    setSaving(true);
    setError(null);
    const result = await apiPost<Submission>(
      `/crisis-arena/engagements/${engagement.id}/submissions`,
      {
        title: form.title,
        narrative: form.narrative,
        archetype: form.archetype,
        killChain: form.killChain,
        impactEstimate: {
          revenueAtRiskUsd: form.revenueAtRiskUsd,
          rtoBreach: form.rtoBreach,
          rpoBreach: form.rpoBreach,
          regulatoryExposureUsd: form.regulatoryExposureUsd,
          blastRadiusDomains: form.blastRadiusDomains
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
        },
        evidenceNotes: form.evidenceNotes,
      },
    );
    setSaving(false);
    if (!result) {
      setError('Failed to submit. Please try again.');
      return;
    }
    onSubmit(result);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 backdrop-blur-sm overflow-y-auto py-8">
      <div className="w-full max-w-2xl rounded-xl border border-[#f5f5f5]/20 bg-[#0f0808] shadow-2xl mx-4">
        <div className="flex items-center justify-between p-5 border-b border-[#f5f5f5]/10">
          <div>
            <h2 className="text-sm font-bold text-[#f5f5f5]">Submit Scenario</h2>
            <p className="text-[10px] text-[#f5f5f5]/40 mt-0.5">{engagement.title}</p>
          </div>
          <button onClick={onClose} className="text-[#f5f5f5]/50 hover:text-[#f5f5f5]">
            <X className="w-4 h-4" />
          </button>
        </div>
        <form
          onSubmit={(e) => {
            void handleSubmit(e);
          }}
          className="p-5 space-y-5"
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider block mb-1">
                Scenario Title *
              </label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Ransomware on Billing Cluster — Q4 Close Friday 17:00"
                className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/20 rounded-lg px-3 py-2 text-xs text-[#f5f5f5] placeholder:text-[#f5f5f5]/30 outline-none focus:border-[#f5f5f5]/40"
              />
            </div>
            <div>
              <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider block mb-1">
                Archetype
              </label>
              <select
                value={form.archetype}
                onChange={(e) => setForm({ ...form, archetype: e.target.value as ThreatArchetype })}
                className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/20 rounded-lg px-3 py-2 text-xs text-[#f5f5f5] outline-none"
              >
                {(
                  [
                    'ransomware',
                    'insider',
                    'supply_chain',
                    'regulatory',
                    'cascade',
                    'black_swan',
                  ] as ThreatArchetype[]
                ).map((a) => (
                  <option key={a} value={a}>
                    {a.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider block mb-1">
              Crisis Narrative *
            </label>
            <textarea
              value={form.narrative}
              onChange={(e) => setForm({ ...form, narrative: e.target.value })}
              rows={4}
              placeholder="Describe the attack scenario, conditions, and business context in detail. What triggers this? What is the 72-hour blast radius?"
              className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/20 rounded-lg px-3 py-2 text-xs text-[#f5f5f5] placeholder:text-[#f5f5f5]/30 outline-none focus:border-[#f5f5f5]/40 resize-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider">
                Kill Chain *
              </label>
              <button
                type="button"
                onClick={addStep}
                className="text-[10px] text-[#f5f5f5]/50 hover:text-[#f5f5f5] flex items-center gap-1"
              >
                <Plus className="w-3 h-3" /> Add Step
              </button>
            </div>
            <div className="space-y-3">
              {form.killChain.map((step, i) => (
                <div key={i} className="bg-[#f5f5f5]/5 rounded-lg p-3 border border-[#f5f5f5]/10">
                  <div className="grid grid-cols-2 gap-2 mb-2">
                    <input
                      type="text"
                      value={step.phase}
                      onChange={(e) => updateStep(i, 'phase', e.target.value)}
                      placeholder="Phase (e.g. Initial Access)"
                      className="bg-[#1a0d0d] border border-[#f5f5f5]/15 rounded px-2 py-1.5 text-[11px] text-[#f5f5f5] placeholder:text-[#f5f5f5]/25 outline-none"
                    />
                    <input
                      type="text"
                      value={step.technique}
                      onChange={(e) => updateStep(i, 'technique', e.target.value)}
                      placeholder="Technique (e.g. T1566.001)"
                      className="bg-[#1a0d0d] border border-[#f5f5f5]/15 rounded px-2 py-1.5 text-[11px] text-[#f5f5f5] placeholder:text-[#f5f5f5]/25 outline-none"
                    />
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={step.description}
                      onChange={(e) => updateStep(i, 'description', e.target.value)}
                      placeholder="Brief description of this step..."
                      className="flex-1 bg-[#1a0d0d] border border-[#f5f5f5]/15 rounded px-2 py-1.5 text-[11px] text-[#f5f5f5] placeholder:text-[#f5f5f5]/25 outline-none"
                    />
                    {form.killChain.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeStep(i)}
                        className="text-[#f5f5f5]/40 hover:text-[#f5f5f5]"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider block mb-2">
              Business Impact Estimate
            </label>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: 'revenueAtRiskUsd', label: 'Revenue at Risk ($)', placeholder: '5000000' },
                { key: 'rtoBreach', label: 'RTO Breach (minutes)', placeholder: '2880' },
                { key: 'rpoBreach', label: 'RPO Breach (minutes)', placeholder: '1440' },
                { key: 'regulatoryExposureUsd', label: 'Regulatory Exposure ($)', placeholder: '1000000' },
              ].map((field) => (
                <div key={field.key}>
                  <label className="text-[9px] text-[#f5f5f5]/40 font-mono uppercase block mb-1">
                    {field.label}
                  </label>
                  <input
                    type="number"
                    value={form[field.key as keyof typeof form] as number}
                    onChange={(e) =>
                      setForm({ ...form, [field.key]: Number(e.target.value) })
                    }
                    placeholder={field.placeholder}
                    className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/15 rounded px-2 py-1.5 text-[11px] text-[#f5f5f5] outline-none"
                  />
                </div>
              ))}
              <div className="col-span-2">
                <label className="text-[9px] text-[#f5f5f5]/40 font-mono uppercase block mb-1">
                  Blast Radius Domains (comma-separated)
                </label>
                <input
                  type="text"
                  value={form.blastRadiusDomains}
                  onChange={(e) => setForm({ ...form, blastRadiusDomains: e.target.value })}
                  className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/15 rounded px-2 py-1.5 text-[11px] text-[#f5f5f5] outline-none"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={() => void computeScore()}
              disabled={scoring}
              className="mt-3 flex items-center gap-2 px-3 py-1.5 bg-[#f5f5f5]/10 hover:bg-[#f5f5f5]/15 border border-[#f5f5f5]/20 rounded text-[10px] text-[#f5f5f5] font-mono transition-colors"
            >
              {scoring ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Zap className="w-3 h-3" />
              )}
              Compute Business Impact Score
            </button>

            {score && (
              <div className="mt-3 bg-[#f5f5f5]/5 border border-[#f5f5f5]/15 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase">BIS Preview</span>
                  <span
                    className={cn(
                      'text-base font-bold font-mono',
                      score.businessImpactScore >= 80
                        ? 'text-[#f5f5f5]'
                        : score.businessImpactScore >= 60
                          ? 'text-[#c9b787]'
                          : 'text-slate-400',
                    )}
                  >
                    {score.businessImpactScore} / 100
                  </span>
                </div>
                <div className="grid grid-cols-5 gap-1">
                  {Object.entries(score.breakdown).map(([k, v]) => (
                    <div key={k} className="text-center">
                      <div className="text-[10px] font-bold text-[#f5f5f5]">
                        {(v as number).toFixed(1)}
                      </div>
                      <div className="text-[8px] text-[#f5f5f5]/30 leading-tight">
                        {k.replace('Component', '')}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-[9px] text-[#f5f5f5]/40 font-mono">
                  Estimated reputation: +{score.estimatedReputation} · Tier: {score.tier}
                </div>
              </div>
            )}
          </div>

          <div>
            <label className="text-[10px] text-[#f5f5f5]/50 font-mono uppercase tracking-wider block mb-1">
              Evidence Notes
            </label>
            <textarea
              value={form.evidenceNotes}
              onChange={(e) => setForm({ ...form, evidenceNotes: e.target.value })}
              rows={2}
              placeholder="References, precedents, or data sources supporting your impact estimate..."
              className="w-full bg-[#1a0d0d] border border-[#f5f5f5]/20 rounded-lg px-3 py-2 text-xs text-[#f5f5f5] placeholder:text-[#f5f5f5]/30 outline-none focus:border-[#f5f5f5]/40 resize-none"
            />
          </div>

          {error && (
            <div className="text-xs text-[#f5f5f5] bg-[#f5f5f5]/10 border border-[#f5f5f5]/20 rounded px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs text-[#f5f5f5]/60 hover:bg-[#f5f5f5]/5 border border-[#f5f5f5]/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-[#f5f5f5] hover:bg-[#f5f5f5] text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {saving && <Loader2 className="w-3 h-3 animate-spin" />}
              Submit Scenario
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CrisisArenaArchitect() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [mySubmissions, setMySubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitFor, setSubmitFor] = useState<Engagement | null>(null);
  const [activeTab, setActiveTab] = useState<'engagements' | 'submissions'>('engagements');

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [engRes, subRes] = await Promise.all([
        fetch(`${BASE}/crisis-arena/engagements`),
        fetch(`${BASE}/crisis-arena/submissions/mine`, { credentials: 'include' }),
      ]);
      if (engRes.ok) {
        const body = (await engRes.json()) as { engagements: Engagement[] };
        setEngagements(body.engagements.filter((e) => e.status === 'accepting' || e.status === 'open'));
      }
      if (subRes.ok) {
        const body = (await subRes.json()) as { submissions: Submission[] };
        setMySubmissions(body.submissions);
      }
      setLoading(false);
    }
    void load();
  }, []);

  const totalRep = mySubmissions.reduce((s, sub) => s + sub.reputationAwarded, 0);
  const accepted = mySubmissions.filter((s) => ['accepted', 'graduated'].includes(s.status)).length;
  const pending = mySubmissions.filter((s) => s.status === 'pending').length;

  return (
    <div className="space-y-6 animate-fade-in p-6 max-w-6xl mx-auto">
      {submitFor && (
        <SubmitModal
          engagement={submitFor}
          onClose={() => setSubmitFor(null)}
          onSubmit={(sub) => {
            setMySubmissions((prev) => [sub, ...prev]);
            setSubmitFor(null);
            setActiveTab('submissions');
          }}
        />
      )}

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-5 h-5" style={{ color: 'var(--gi-accent-red)' }} />
            <h1 className="text-2xl font-bold" style={{ color: 'var(--gi-text-primary)' }}>Analyst Workspace</h1>
          </div>
          <p className="text-sm" style={{ color: 'var(--gi-text-muted)' }}>
            Browse open engagements, draft and submit adversarial scenarios, track your performance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/crisis-arena/leaderboard">
            <button className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-md transition-colors" style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-default)', color: 'var(--gi-text-secondary)' }}>
              <Users className="w-3.5 h-3.5" /> Rankings
            </button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Performance Score', value: totalRep.toLocaleString(), icon: Activity, accent: 'var(--gi-accent-amber)' },
          { label: 'Accepted', value: String(accepted), icon: CheckCircle2, accent: 'var(--gi-accent-green)' },
          { label: 'Pending', value: String(pending), icon: Clock, accent: 'var(--gi-accent-amber)' },
          { label: 'Total', value: String(mySubmissions.length), icon: Zap, accent: 'var(--gi-accent-red)' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-lg p-4" style={{ background: 'var(--gi-bg-surface)', border: '1px solid var(--gi-border-subtle)' }}>
            <stat.icon className="w-4 h-4 mb-2" style={{ color: stat.accent }} />
            <div className="text-xl font-bold font-mono" style={{ color: 'var(--gi-text-primary)' }}>{stat.value}</div>
            <div className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--gi-text-muted)' }}>{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 border-b border-[#f5f5f5]/10 pb-1">
        {([
          { id: 'engagements', label: `Open Engagements (${engagements.length})` },
          { id: 'submissions', label: `My Submissions (${mySubmissions.length})` },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'text-xs font-medium pb-2 border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-[#f5f5f5] text-[#f5f5f5]'
                : 'border-transparent text-[#f5f5f5]/40 hover:text-[#f5f5f5]/70',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-[#f5f5f5] animate-spin" />
        </div>
      )}

      {!loading && activeTab === 'engagements' && (
        <div className="space-y-4">
          {engagements.length === 0 && (
            <div className="text-center py-12 text-[#f5f5f5]/30 text-xs">
              No open engagements at this time. Check back soon.
            </div>
          )}
          {engagements.map((eng) => (
            <div
              key={eng.id}
              className="bg-[#0f0808]/80 border border-[#f5f5f5]/10 hover:border-[#f5f5f5]/20 rounded-xl p-5 transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className="px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border bg-[#c9b787]/10 text-[#c9b787] border-[#c9b787]/30">
                      {eng.status}
                    </span>
                    {eng.archetypeFilter.slice(0, 3).map((a) => (
                      <span
                        key={a}
                        className={cn('text-[9px] font-mono uppercase', ARCHETYPE_COLORS[a])}
                      >
                        {a.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                  <h3 className="text-sm font-bold text-[#f5f5f5] mb-1">{eng.title}</h3>
                  <p className="text-[11px] text-[#f5f5f5]/50 mb-3 line-clamp-2">{eng.description}</p>
                  <div className="flex items-center gap-4 text-[10px] text-[#f5f5f5]/40 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" /> {daysUntil(eng.deadline)} left
                    </span>
                    <span>Pool: {formatUsd(eng.payoutPool)}</span>
                    <span>{eng.submissionCount} submissions</span>
                    <span>Domains: {eng.scopedDomains.join(', ')}</span>
                  </div>
                </div>
                <button
                  onClick={() => setSubmitFor(eng)}
                  className="flex items-center gap-2 px-4 py-2 bg-[#f5f5f5] hover:bg-[#f5f5f5] text-white rounded-xl text-xs font-bold transition-colors shrink-0"
                >
                  <Plus className="w-3.5 h-3.5" /> Submit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && activeTab === 'submissions' && (
        <div className="space-y-4">
          {mySubmissions.length === 0 && (
            <div className="text-center py-12 text-[#f5f5f5]/30 text-xs">
              No submissions yet. Browse open engagements and submit your first scenario.
            </div>
          )}
          {mySubmissions.map((sub) => (
            <div
              key={sub.id}
              className="bg-[#0f0808]/80 border border-[#f5f5f5]/10 rounded-xl p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span
                      className={cn(
                        'px-1.5 py-0.5 rounded text-[9px] font-mono border uppercase',
                        STATUS_STYLE[sub.status],
                      )}
                    >
                      {sub.status}
                    </span>
                    <span
                      className={cn('text-[9px] font-mono uppercase', ARCHETYPE_COLORS[sub.archetype])}
                    >
                      {sub.archetype.replace('_', ' ')}
                    </span>
                    <span className="text-[9px] text-[#f5f5f5]/30 ml-auto">
                      {relativeTime(sub.submittedAt)}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#f5f5f5] mb-1">{sub.title}</div>
                  <div className="flex items-center gap-4 text-[10px] text-[#f5f5f5]/40 font-mono">
                    <span>BIS: {sub.businessImpactScore}</span>
                    <span>Rev: {formatUsd(sub.impactEstimate.revenueAtRiskUsd)}</span>
                    <span>Blast: {sub.impactEstimate.blastRadiusDomains.join(', ')}</span>
                  </div>
                  {sub.triageJustification && (
                    <p className="text-[10px] text-[#f5f5f5]/40 mt-2 italic">
                      Triage note: {sub.triageJustification}
                    </p>
                  )}
                  {sub.graduatedIncidentId && (
                    <div className="flex items-center gap-1 text-[10px] text-[#8a8a8a] mt-1">
                      <Shield className="w-2.5 h-2.5" /> Graduated →{' '}
                      <Link href="/incident">
                        <span className="underline cursor-pointer">{sub.graduatedIncidentId}</span>
                      </Link>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  {sub.reputationAwarded !== 0 && (
                    <div className="text-center">
                      <div
                        className={cn(
                          'text-base font-bold font-mono',
                          sub.reputationAwarded > 0 ? 'text-[#c9b787]' : 'text-[#f5f5f5]',
                        )}
                      >
                        {sub.reputationAwarded > 0 ? '+' : ''}{sub.reputationAwarded}
                      </div>
                      <div className="text-[8px] text-[#f5f5f5]/30 uppercase">Rep</div>
                    </div>
                  )}
                  <div className="text-center">
                    <div
                      className={cn(
                        'text-base font-bold font-mono',
                        sub.businessImpactScore >= 80
                          ? 'text-[#f5f5f5]'
                          : sub.businessImpactScore >= 60
                            ? 'text-[#c9b787]'
                            : 'text-slate-400',
                      )}
                    >
                      {sub.businessImpactScore}
                    </div>
                    <div className="text-[8px] text-[#f5f5f5]/30 uppercase">BIS</div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
