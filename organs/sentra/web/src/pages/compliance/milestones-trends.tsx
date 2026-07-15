// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/pages/compliance/milestones-trends.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { motion } from 'framer-motion';
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  PlayCircle,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const milestones = [
  {
    id: 1,
    title: 'Zero Trust Architecture Assessment',
    description: 'Evaluate current network perimeter and design zero-trust migration roadmap.',
    status: 'completed' as const,
    dueDate: '2025-12-31',
    owner: 'CISO',
  },
  {
    id: 2,
    title: 'EDR Deployment — Full Coverage',
    description:
      'Deploy endpoint detection and response across all production and development machines.',
    status: 'in_progress' as const,
    dueDate: '2026-03-31',
    owner: 'VP Security',
  },
  {
    id: 3,
    title: 'GDPR Privacy Program Launch',
    description:
      'Establish data subject request processes, consent management, and DPO appointment.',
    status: 'in_progress' as const,
    dueDate: '2026-04-30',
    owner: 'DPO',
  },
  {
    id: 4,
    title: 'Vendor Security Assessment Program',
    description:
      'Complete tier-1 and tier-2 vendor assessments and establish continuous monitoring.',
    status: 'pending' as const,
    dueDate: '2026-06-30',
    owner: 'CISO',
  },
  {
    id: 5,
    title: 'SOC 2 Type II Readiness',
    description: 'Prepare and complete all controls required for SOC 2 Type II certification.',
    status: 'pending' as const,
    dueDate: '2026-09-30',
    owner: 'CISO',
  },
  {
    id: 6,
    title: 'CMMC Level 2 Certification',
    description:
      'Complete CMMC Level 2 certification process for government contracting eligibility.',
    status: 'pending' as const,
    dueDate: '2026-12-31',
    owner: 'Compliance Team',
  },
];

const trendData = [
  { month: 'Jan', readiness: 62, projected: null },
  { month: 'Feb', readiness: 65, projected: null },
  { month: 'Mar', readiness: 71, projected: null },
  { month: 'Apr', readiness: 74, projected: null },
  { month: 'May', readiness: 78, projected: null },
  { month: 'Jun', readiness: null, projected: 81 },
  { month: 'Jul', readiness: null, projected: 83 },
  { month: 'Aug', readiness: null, projected: 85 },
  { month: 'Sep', readiness: null, projected: 87 },
];

const StatusIcon = {
  pending: Clock,
  in_progress: PlayCircle,
  completed: CheckCircle2,
  overdue: AlertCircle,
  canceled: XCircle,
};
const StatusColor = {
  pending: 'text-[#c9b787]/40',
  in_progress: 'text-[#c9b787]',
  completed: 'text-[#c9b787]',
  overdue: 'text-[#f5f5f5]',
  canceled: 'text-[#c9b787]/20',
};
const StatusBorder = {
  pending: 'border-l-orange-500/30',
  in_progress: 'border-l-orange-400',
  completed: 'border-l-emerald-500',
  overdue: 'border-l-red-500',
  canceled: 'border-l-orange-500/10',
};

export default function MilestonesTrends() {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="font-display text-lg font-bold text-[#c9b787]">Milestones & Trends</h1>
        <p className="text-xs text-[#c9b787]/50 mt-0.5">
          Program delivery timeline and historical readiness trajectory.
        </p>
      </header>

      <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[#c9b787]" /> Readiness Score Trajectory
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(201,183,135,0.1)" vertical={false} />
              <XAxis
                dataKey="month"
                stroke="rgba(201,183,135,0.3)"
                tick={{ fill: 'rgba(251,146,60,0.5)', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="rgba(201,183,135,0.3)"
                tick={{ fill: 'rgba(251,146,60,0.5)', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                domain={[50, 100]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#09080f',
                  border: '1px solid rgba(201,183,135,0.2)',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="readiness"
                name="Actual"
                stroke="#f5f5f5"
                strokeWidth={2.5}
                dot={{ fill: '#f5f5f5', r: 3 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="projected"
                name="AI Projected"
                stroke="rgba(251,146,60,0.6)"
                strokeWidth={2}
                strokeDasharray="6 3"
                dot={{ fill: 'rgba(251,146,60,0.6)', r: 3 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5 relative overflow-hidden">
        <div className="absolute top-0 bottom-0 left-[31px] w-[2px] bg-[#c9b787]/10 z-0" />
        <h3 className="text-sm font-semibold text-[#c9b787] mb-4 relative z-10">
          Program Milestones
        </h3>
        <div className="space-y-4 relative z-10">
          {milestones.map((milestone, i) => {
            const Icon = StatusIcon[milestone.status];
            const isLate =
              milestone.status !== 'completed' && new Date(milestone.dueDate) < new Date();
            return (
              <motion.div
                key={milestone.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className="flex gap-4 relative group"
              >
                <div className="mt-1 flex-shrink-0 relative">
                  <div className="w-10 h-10 rounded-full bg-[#09080f] border border-[#c9b787]/20 flex items-center justify-center shadow-lg group-hover:border-[#c9b787]/40 transition-colors">
                    <Icon className={`w-4 h-4 ${StatusColor[milestone.status]}`} />
                  </div>
                </div>
                <div
                  className={`flex-1 bg-[#c9b787]/5 hover:bg-[#c9b787]/10 border border-[#c9b787]/10 border-l-4 ${StatusBorder[milestone.status]} p-4 rounded-xl transition-all duration-300`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-2">
                    <div>
                      <h3 className="text-xs font-bold text-[#c9b787] font-display mb-0.5">
                        {milestone.title}
                      </h3>
                      <p className="text-[10px] text-[#c9b787]/40 leading-relaxed">
                        {milestone.description}
                      </p>
                    </div>
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md whitespace-nowrap ${
                        milestone.status === 'completed'
                          ? 'bg-[#c9b787]/10 text-[#c9b787]'
                          : milestone.status === 'in_progress'
                            ? 'bg-[#c9b787]/10 text-[#c9b787]'
                            : 'bg-[#c9b787]/5 text-[#c9b787]/40'
                      }`}
                    >
                      {milestone.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex items-center gap-5 pt-2.5 border-t border-[#c9b787]/10 text-[10px]">
                    <span className="text-[#c9b787]/40">{milestone.owner}</span>
                    <span className={isLate ? 'text-[#f5f5f5]' : 'text-[#c9b787]/40'}>
                      <Calendar className="w-3 h-3 inline mr-1" />
                      {new Date(milestone.dueDate).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                      {isLate && <span className="ml-1 text-[#f5f5f5]">LATE</span>}
                    </span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
