// R7 minimalistic redesign (Series-A blocker, 2026-05-18T16:03:41Z):
// surface tokens realigned with a11oy/amaru palette in src/lib/theme.ts.
// No data wiring, no API calls, no copy were modified — visual texture only.

import { useStandardQuery } from '@szl-holdings/api-client-react';
import { AgentInsightsWidget } from '@szl-holdings/shared-ui/agent-insights-widget';
import { MicroFeedbackWidget } from '@szl-holdings/shared-ui/micro-feedback-widget';
import { Brain, Radio, ShieldAlert, Zap } from 'lucide-react';
import { AlloyKernelPanel } from '@/components/AlloyKernelPanel';

const ACCENT = '#f5f5f5';

function GlobalFeedStats() {
  const { data } = useStandardQuery<{
    stats: {
      knowledge: { byDomain?: Record<string, number> };
      eventBus: { totalPublished?: number };
    };
    globalFeed: { correlations: unknown[] };
  }>({
    queryKey: ['agent-os-global-feed-aegis'],
    queryFn: async () => {
      const r = await fetch('/api/agent-os/feed?limit=20');
      return r.json();
    },
    refetchInterval: 60000,
  });

  const knowledge = data?.stats?.knowledge;
  const eventBus = data?.stats?.eventBus;
  const globalFeed = data?.globalFeed;

  return (
    <div className="grid grid-cols-3 gap-4 mb-6">
      {[
        {
          label: 'Security Findings',
          value: knowledge?.byDomain?.aegis ?? 0,
          icon: ShieldAlert,
          color: 'text-[#c9b787]',
          bg: 'bg-[#c9b787]/10',
        },
        {
          label: 'Cross-Domain Signals',
          value: globalFeed?.correlations?.length ?? 0,
          icon: Zap,
          color: 'text-[#8a8a8a]',
          bg: 'bg-[#8a8a8a]/10',
        },
        {
          label: 'Events Published',
          value: eventBus?.totalPublished ?? 0,
          icon: Radio,
          color: 'text-[#c9b787]',
          bg: 'bg-[#c9b787]/10',
        },
      ].map(({ label, value, icon: Icon, color, bg }) => (
        <div
          key={label}
          className="bg-[#09080f]/80 border border-[#c9b787]/10 rounded-xl p-4 flex items-center gap-3"
        >
          <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center shrink-0`}>
            <Icon className={`w-4 h-4 ${color}`} />
          </div>
          <div>
            <div className="text-lg font-bold text-[#c9b787]">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </div>
            <div className="text-[10px] text-[#c9b787]/50">{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AgentInsightsPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-[#c9b787]/10 flex items-center justify-center">
          <Brain className="w-5 h-5 text-[#c9b787]" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-[#c9b787]">Autonomous Threat Intelligence</h1>
          <p className="text-xs text-[#c9b787]/50">
            Security insights gathered autonomously while you were away
          </p>
        </div>
      </div>

      <GlobalFeedStats />

      <AgentInsightsWidget
        domain="aegis"
        apiBase="/api"
        accentColor={ACCENT}
        compact={false}
        className="border-[#c9b787]/20 bg-[#09080f]/60"
      />

      <AgentInsightsWidget
        domain="vessels"
        apiBase="/api"
        accentColor="#c9b787"
        compact={false}
        className="border-[#c9b787]/10 bg-[#09080f]/60"
      />

      <div className="flex justify-end pt-1">
        <MicroFeedbackWidget
          featureId="aegis-agent-insights"
          featureName="PARAGON Autonomous Threat Intelligence"
          app="aegis"
          compact
          prompt="Were these threat insights useful?"
        />
      </div>

      <div className="text-[10px] text-[#c9b787]/30 text-center pt-2">
        Powered by SZL Agent OS — autonomous security intelligence running 24/7
      </div>

      <AlloyKernelPanel />
    </div>
  );
}
