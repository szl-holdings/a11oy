import { Link } from 'wouter';
import {
  Brain,
  Eye,
  FlaskConical,
  Layers,
  Database,
  Shield,
  Sparkles,
  ArrowRight,
  Cpu,
  Activity,
  Zap,
} from 'lucide-react';

const A11OY_GOLD = '#c9b787';
const A11OY_GOLD_SUB = '#a89868';

const HUB_SECTIONS = [
  {
    key: 'model-fleet',
    name: 'Model Fleet Console',
    description: 'Browsable model cards with routing lanes, failover chains, cost/latency metrics, and lifecycle stages.',
    icon: Layers,
    href: '/sovereign-ai-hub/model-fleet',
    color: A11OY_GOLD,
    stats: ['Multi-provider', 'Lifecycle governance', 'Cost tracking'],
  },
  {
    key: 'inference',
    name: 'Inference Observatory',
    description: 'Live routing decisions, failover events, provider health, and cost optimization dashboard.',
    icon: Eye,
    href: '/sovereign-ai-hub/inference',
    color: A11OY_GOLD,
    stats: ['Real-time routing', 'Provider health', 'Cost efficiency'],
  },
  {
    key: 'distillery',
    name: 'Domain Distillery',
    description: 'Fine-tuning jobs, canary deployments, data quality gates, and model version comparisons.',
    icon: FlaskConical,
    href: '/sovereign-ai-hub/distillery',
    color: A11OY_GOLD_SUB,
    stats: ['Governed fine-tuning', 'Canary testing', 'Quality gates'],
  },
  {
    key: 'praxis',
    name: 'PRAXIS Playground',
    description: 'Cross-domain intelligence workspace — entity resolution, fusion queries, evidence threading.',
    icon: Sparkles,
    href: '/sovereign-ai-hub/praxis',
    color: A11OY_GOLD,
    stats: ['Fusion cortex', 'Graph RAG', 'Evidence chains'],
  },
  {
    key: 'data-estate',
    name: 'Data Estate Catalog',
    description: 'Domain datasets with freshness, record counts, cross-domain relationships, and feature store.',
    icon: Database,
    href: '/sovereign-ai-hub/data-estate',
    color: A11OY_GOLD_SUB,
    stats: ['6 domains', 'Feature store', 'Quality scoring'],
  },
  {
    key: 'cognitive',
    name: 'Cognitive Insights',
    description: 'Agent reasoning traces, cognitive loop visualization, skill heatmaps, and drift detection.',
    icon: Brain,
    href: '/sovereign-ai-hub/cognitive',
    color: A11OY_GOLD,
    stats: ['8-phase loops', 'Skill utilization', 'Self-improvement'],
  },
];

export default function SovereignAiHub() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <p className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground mb-1">
          COMMAND · SOVEREIGN AI HUB
        </p>
        <h1 className="text-2xl font-display font-bold tracking-tight flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[rgba(201,183,135,0.1)] flex items-center justify-center border border-[rgba(201,183,135,0.3)]">
            <Shield className="w-5 h-5 text-[#c9b787]" />
          </div>
          Sovereign AI Hub
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Governed intelligence operations — browsable, transparent, and auditable.
          Your AI infrastructure made visible: model registry, inference routing,
          fine-tuning, fusion intelligence, and cognitive observability.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[rgba(201,183,135,0.08)] flex items-center justify-center">
            <Activity className="w-5 h-5 text-[#c9b787]" />
          </div>
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">System Status</p>
            <p className="text-lg font-mono font-bold text-[#c9b787]">OPERATIONAL</p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[rgba(201,183,135,0.08)] flex items-center justify-center">
            <Cpu className="w-5 h-5 text-[#c9b787]" />
          </div>
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">AI Primitives</p>
            <p className="text-lg font-mono font-bold">6 Active</p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-[rgba(201,183,135,0.08)] flex items-center justify-center">
            <Zap className="w-5 h-5 text-[#c9b787]" />
          </div>
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Governance</p>
            <p className="text-lg font-mono font-bold">Proof Chains Active</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {HUB_SECTIONS.map((section) => (
          <Link key={section.key} href={section.href}>
            <div className="group rounded-lg border border-border bg-card hover:bg-card/80 hover:border-primary/30 transition-all duration-200 p-5 cursor-pointer h-full flex flex-col">
              <div className="flex items-start justify-between mb-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center border"
                  style={{
                    backgroundColor: `${section.color}15`,
                    borderColor: `${section.color}40`,
                  }}
                >
                  <section.icon className="w-5 h-5" style={{ color: section.color }} />
                </div>
                <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <h3 className="text-sm font-semibold mb-1">{section.name}</h3>
              <p className="text-xs text-muted-foreground mb-3 flex-1">{section.description}</p>
              <div className="flex flex-wrap gap-1.5">
                {section.stats.map((stat) => (
                  <span
                    key={stat}
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-border text-muted-foreground"
                  >
                    {stat}
                  </span>
                ))}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
