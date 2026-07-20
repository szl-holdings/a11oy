// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/compliance/readiness-dashboard.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardQuery } from '@szl-holdings/api-client-react';
import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import { motion } from 'framer-motion';
import { Activity, ArrowUpRight, BellRing, Loader2, ShieldAlert, Target } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface ReadinessDimension {
  id: number;
  name: string;
  category?: string;
  currentScore: number;
  targetScore: number;
  assessorName?: string;
  lastAssessedAt?: string;
}

interface ReadinessProgram {
  id: number;
  name: string;
  overallScore: number;
  targetScore: number;
  status: string;
}

interface ExecutiveRollup {
  programCount: number;
  activeProgramCount: number;
  dimensionCount: number;
  overdueMilestoneCount: number;
  openRiskCount: number;
  criticalRiskCount: number;
  unreadAlertCount: number;
  programs: ReadinessProgram[];
  recentAlerts: { id: number; isRead: boolean }[];
}

function useAnimatedCounter(target: number, duration = 1200, decimals = 0) {
  const [count, setCount] = useState(0);
  const frameRef = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      const value = eased * target;
      setCount(decimals > 0 ? parseFloat(value.toFixed(decimals)) : Math.round(value));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration, decimals]);
  return count;
}

const cohesivePalette = ['#f5f5f5', '#c9b787', '#c9b787', '#8a8a8a', '#c9b787'];

function DimensionBar({
  name,
  score,
  target,
  index,
}: {
  name: string;
  score: number;
  target: number;
  index: number;
}) {
  const animatedScore = useAnimatedCounter(score, 1000 + index * 100);
  const gap = target - score;
  const pct = (score / 100) * 100;
  const color = cohesivePalette[Math.min(index, cohesivePalette.length - 1)];
  const statusText = gap <= 0 ? 'On Target' : gap <= 15 ? 'Near Target' : 'Below Target';
  const statusColor =
    gap <= 0 ? 'text-[#c9b787]' : gap <= 15 ? 'text-[#c9b787]' : 'text-[#c9b787]/60';
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="space-y-1.5"
    >
      <div className="flex items-center justify-between text-sm">
        <span className="text-[#c9b787]/80 font-medium text-xs">{name}</span>
        <div className="flex items-center gap-3">
          <span className={`text-[10px] ${statusColor}`}>{statusText}</span>
          <span className="font-bold text-[#c9b787] w-8 text-right text-xs">{animatedScore}</span>
        </div>
      </div>
      <div className="relative h-1.5 bg-[#c9b787]/10 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay: index * 0.06, ease: 'easeOut' }}
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ backgroundColor: color }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-[#c9b787]/20" style={{ left: `${target}%` }} />
      </div>
    </motion.div>
  );
}

export default function ReadinessDashboard() {
  const { data: rollup, isLoading } = useStandardQuery<ExecutiveRollup>({
    queryKey: ['readiness', 'executive-rollup'],
    queryFn: () => apiFetch<ExecutiveRollup>('/readiness/executive-rollup'),
    retry: 1,
    staleTime: 60000,
  });

  const { data: dimensionsRaw = [] } = useStandardQuery<ReadinessDimension[]>({
    queryKey: ['readiness', 'dimensions'],
    queryFn: async () => {
      if (!rollup?.programs?.[0]?.id) return [];
      return apiFetch<ReadinessDimension[]>(
        `/readiness/programs/${rollup.programs[0].id}/dimensions`,
      );
    },
    enabled: !!rollup?.programs?.[0],
    staleTime: 60000,
  });

  const activeProgram = rollup?.programs?.[0] ?? null;
  const overallScore = useAnimatedCounter(activeProgram?.overallScore ?? 0, 1400, 1);
  const sortedDimensions = [...dimensionsRaw].sort((a, b) => b.currentScore - a.currentScore);
  const chartData = sortedDimensions.map((d) => ({
    name: d.name.slice(0, 8),
    score: d.currentScore,
    target: d.targetScore,
  }));

  if (isLoading) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-lg font-bold text-[#c9b787]">Readiness Posture</h1>
          <p className="text-[#c9b787]/50 text-xs mt-0.5">
            NIST CSF · ISO 27001 · CMMC frameworks
          </p>
        </header>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-[#c9b787]/50 animate-spin" />
        </div>
      </div>
    );
  }

  if (!activeProgram) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-lg font-bold text-[#c9b787]">Readiness Posture</h1>
          <p className="text-[#c9b787]/50 text-xs mt-0.5">
            NIST CSF · ISO 27001 · CMMC frameworks
          </p>
        </header>
        <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-10 flex flex-col items-center justify-center text-center gap-3">
          <Target className="w-8 h-8 text-[#c9b787]/40" />
          <p className="text-[#c9b787]/70 text-sm font-medium">No readiness program configured</p>
          <p className="text-[#c9b787]/40 text-xs max-w-sm">
            Create a readiness program and add dimensions to start tracking your compliance posture
            across NIST CSF, ISO 27001, and CMMC frameworks.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="font-display text-lg font-bold text-[#c9b787]">Readiness Posture</h1>
          <p className="text-[#c9b787]/50 text-xs mt-0.5">
            NIST CSF · ISO 27001 · CMMC frameworks
          </p>
        </motion.div>
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
          <div className="bg-[#c9b787]/10 border border-[#c9b787]/20 px-4 py-2 rounded-xl text-[#c9b787] font-medium flex items-center gap-2 text-xs">
            <Activity className="w-3.5 h-3.5 text-[#c9b787]" />
            <span>{activeProgram.name}</span>
          </div>
        </motion.div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-4 bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-6 flex flex-col items-center justify-center"
        >
          <div className="text-xs font-medium text-[#c9b787]/50 flex items-center gap-2 mb-4 self-start">
            <Target className="w-3.5 h-3.5" /> Overall Readiness Score
          </div>
          <div className="text-7xl font-display font-bold text-[#c9b787] my-4">{overallScore}</div>
          <p className="text-xs text-[#c9b787]/50">out of {activeProgram.targetScore} target</p>
          <div className="w-full grid grid-cols-2 gap-4 mt-6 pt-5 border-t border-[#c9b787]/10">
            <div>
              <div className="text-xs text-[#c9b787]/40 mb-1">Target</div>
              <div className="text-xl font-bold text-[#c9b787]">{activeProgram.targetScore}</div>
            </div>
            <div>
              <div className="text-xs text-[#c9b787]/40 mb-1">Status</div>
              <div className="text-xs font-bold flex items-center gap-1 bg-[#c9b787]/10 text-[#c9b787] w-max px-2.5 py-1 rounded-lg">
                <ArrowUpRight className="w-3.5 h-3.5" />{' '}
                {activeProgram.status === 'active' ? 'On Track' : activeProgram.status}
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="lg:col-span-8 bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-6"
        >
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-semibold text-[#c9b787] font-display">
              Dimension Performance
            </h3>
            <div className="flex items-center gap-4 text-[10px] text-[#c9b787]/40">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-1.5 rounded-full bg-[#f5f5f5] inline-block" /> Score
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-0.5 h-3 bg-[#c9b787]/20 inline-block" /> Target
              </span>
            </div>
          </div>
          {sortedDimensions.length === 0 ? (
            <div className="flex items-center justify-center py-10 text-[#c9b787]/40 text-xs">
              No dimensions configured for this program
            </div>
          ) : (
            <div className="space-y-3">
              {sortedDimensions.slice(0, 6).map((d, i) => (
                <DimensionBar
                  key={d.id}
                  name={d.name}
                  score={d.currentScore}
                  target={d.targetScore}
                  index={i}
                />
              ))}
            </div>
          )}
        </motion.div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            delay: 0.25,
            value: rollup?.dimensionCount ?? 0,
            label: 'Assessed Dimensions',
            icon: Target,
            color: 'text-[#c9b787]',
            bg: 'bg-[#c9b787]/10',
          },
          {
            delay: 0.35,
            value: rollup?.criticalRiskCount ?? 0,
            label: 'Critical Open Risks',
            icon: ShieldAlert,
            color: 'text-[#f5f5f5]',
            bg: 'bg-[#f5f5f5]/10',
          },
          {
            delay: 0.45,
            value: rollup?.unreadAlertCount ?? 0,
            label: 'Unread Alerts',
            icon: BellRing,
            color: 'text-[#c9b787]',
            bg: 'bg-[#c9b787]/10',
          },
        ].map(({ delay, value, label, icon: Icon, color, bg }) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay }}
            className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5"
          >
            <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center mb-4`}>
              <Icon className={`w-4.5 h-4.5 ${color}`} />
            </div>
            <div className="text-3xl font-display font-bold text-[#c9b787]">{value}</div>
            <p className="text-xs text-[#c9b787]/50 mt-1">{label}</p>
          </motion.div>
        ))}
      </div>

      {chartData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5"
        >
          <h3 className="text-sm font-semibold text-[#c9b787] mb-4">
            Score Distribution by Control Domain
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barGap={4}>
                <XAxis
                  dataKey="name"
                  stroke="#c9b787"
                  fontSize={9}
                  tick={{ fill: 'rgba(251,146,60,0.5)' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="#c9b787"
                  fontSize={9}
                  tick={{ fill: 'rgba(251,146,60,0.5)' }}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 100]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#09080f',
                    border: '1px solid rgba(201,183,135,0.2)',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Bar
                  dataKey="score"
                  fill="rgba(245,245,245,0.7)"
                  radius={[3, 3, 0, 0]}
                  name="Score"
                />
                <Bar
                  dataKey="target"
                  fill="rgba(201,183,135,0.2)"
                  radius={[3, 3, 0, 0]}
                  name="Target"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}
    </div>
  );
}
