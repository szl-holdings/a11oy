import { motion } from 'framer-motion';
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Brain,
  Lightbulb,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const benchmarks = [
  { dimension: 'Cybersecurity', szlScore: 82, industryAvg: 68, topQuartile: 85 },
  { dimension: 'Cloud Infra', szlScore: 78, industryAvg: 65, topQuartile: 82 },
  { dimension: 'Data Gov', szlScore: 64, industryAvg: 58, topQuartile: 78 },
  { dimension: 'AI/ML', szlScore: 71, industryAvg: 52, topQuartile: 80 },
  { dimension: 'Compliance', szlScore: 76, industryAvg: 70, topQuartile: 88 },
  { dimension: 'Operations', szlScore: 80, industryAvg: 72, topQuartile: 86 },
];

const riskPredictions = [
  {
    factor: 'Supply Chain Disruption',
    current: 0.22,
    projected30d: 0.25,
    projected90d: 0.18,
    trend: 'decreasing',
  },
  {
    factor: 'Regulatory Compliance Gap',
    current: 0.15,
    projected30d: 0.12,
    projected90d: 0.08,
    trend: 'decreasing',
  },
  {
    factor: 'Talent Shortage Risk',
    current: 0.35,
    projected30d: 0.38,
    projected90d: 0.42,
    trend: 'increasing',
  },
  {
    factor: 'Cyber Threat Exposure',
    current: 0.18,
    projected30d: 0.16,
    projected90d: 0.14,
    trend: 'decreasing',
  },
];

const recommendations = [
  {
    title: 'Accelerate Zero Trust implementation',
    priority: 'high',
    impact: '+8 points',
    dimension: 'Cybersecurity',
    confidence: 92,
  },
  {
    title: 'Expand AI/ML training programs for engineering teams',
    priority: 'high',
    impact: '+12 points',
    dimension: 'AI/ML Maturity',
    confidence: 87,
  },
  {
    title: 'Implement automated compliance scanning pipeline',
    priority: 'medium',
    impact: '+6 points',
    dimension: 'Compliance',
    confidence: 84,
  },
  {
    title: 'Deploy edge computing nodes in APAC region',
    priority: 'medium',
    impact: '+5 points',
    dimension: 'Cloud Infrastructure',
    confidence: 79,
  },
  {
    title: 'Establish data lineage tracking across all systems',
    priority: 'low',
    impact: '+3 points',
    dimension: 'Data Governance',
    confidence: 75,
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
];

export default function ReadinessAIInsights() {
  const [summaryText, setSummaryText] = useState('');

  const radarData = benchmarks.map((b) => ({
    dimension: b.dimension,
    szl: b.szlScore,
    industry: b.industryAvg,
    topQuartile: b.topQuartile,
  }));

  return (
    <div className="space-y-5">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-lg font-bold text-[#c9b787] flex items-center gap-2">
            <Brain className="w-5 h-5 text-[#c9b787]" /> AI-Powered Readiness Insights
          </h1>
          <p className="text-xs text-[#c9b787]/50 mt-0.5">
            Risk predictions, industry benchmarks, and intelligent recommendations.
          </p>
        </div>
        <button
          onClick={() =>
            setSummaryText(
              'Based on current readiness metrics, PARAGON demonstrates strong positioning across cybersecurity (82%) and cloud infrastructure (78%) dimensions. Key areas for improvement include AI/ML maturity (+12 potential points) and data governance frameworks. Recommended actions: 1) Accelerate Zero Trust implementation, 2) Expand AI training programs, 3) Implement automated compliance scanning.',
            )
          }
          className="text-xs px-4 py-2 rounded-lg bg-[#c9b787]/10 text-[#c9b787] border border-[#c9b787]/20 hover:bg-[#c9b787]/20 transition-all flex items-center gap-2"
        >
          <Zap className="w-3.5 h-3.5" /> Generate Summary
        </button>
      </header>

      {summaryText && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5"
        >
          <h3 className="text-xs font-semibold text-[#c9b787] mb-3 flex items-center gap-2">
            <Brain className="w-3.5 h-3.5 text-[#c9b787]" /> AI Executive Summary
          </h3>
          <div className="bg-black/20 rounded-lg p-4 border border-[#c9b787]/10">
            <p className="text-xs text-[#c9b787]/80 leading-relaxed">{summaryText}</p>
          </div>
        </motion.div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {benchmarks.slice(0, 6).map((b, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-4"
          >
            <div className="text-[10px] text-[#c9b787]/40 uppercase tracking-wider mb-2">
              {b.dimension}
            </div>
            <div className="text-3xl font-display font-bold text-[#c9b787] mb-1">{b.szlScore}</div>
            <div className="text-[10px] text-[#c9b787]/40">
              Industry avg: <span className="text-[#c9b787]/70">{b.industryAvg}</span> · Top
              quartile: <span className="text-[#c9b787]">{b.topQuartile}</span>
            </div>
            <div className="mt-2 h-1 bg-[#c9b787]/10 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${b.szlScore >= b.topQuartile ? 'bg-[#c9b787]' : b.szlScore >= b.industryAvg ? 'bg-[#c9b787]' : 'bg-[#f5f5f5]'}`}
                style={{ width: `${b.szlScore}%` }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
            <BarChart3 className="w-3.5 h-3.5 text-[#c9b787]" /> Industry Benchmark Comparison
          </h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="rgba(201,183,135,0.15)" />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fill: 'rgba(251,146,60,0.5)', fontSize: 9 }}
                />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar
                  name="Industry Avg"
                  dataKey="industry"
                  stroke="rgba(148,163,184,0.4)"
                  fill="rgba(148,163,184,0.05)"
                />
                <Radar
                  name="Top Quartile"
                  dataKey="topQuartile"
                  stroke="rgba(201,183,135,0.4)"
                  fill="rgba(201,183,135,0.05)"
                />
                <Radar
                  name="SZL Score"
                  dataKey="szl"
                  stroke="rgba(245,245,245,0.8)"
                  fill="rgba(245,245,245,0.15)"
                  strokeWidth={2}
                />
                <Legend />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#09080f',
                    border: '1px solid rgba(201,183,135,0.2)',
                    borderRadius: '8px',
                    fontSize: '10px',
                    color: '#fff',
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-[#c9b787]" /> Readiness Trajectory
          </h3>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(201,183,135,0.1)"
                  vertical={false}
                />
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
                  name="Projected"
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
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-[#c9b787]" /> AI Risk Predictions
          </h3>
          <div className="space-y-3">
            {riskPredictions.map((p, i) => (
              <div key={i} className="bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-[#c9b787]">{p.factor}</span>
                  <span
                    className={`text-[10px] flex items-center gap-1 ${p.trend === 'increasing' ? 'text-[#f5f5f5]' : 'text-[#c9b787]'}`}
                  >
                    {p.trend === 'increasing' ? (
                      <ArrowUpRight className="w-3 h-3" />
                    ) : (
                      <ArrowDownRight className="w-3 h-3" />
                    )}
                    {p.trend}
                  </span>
                </div>
                <div className="flex gap-3 text-[10px]">
                  <div>
                    <span className="block text-[#c9b787]/40">Current</span>
                    <span className="font-bold text-[#c9b787]">
                      {(p.current * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-[#c9b787]/40">30-day</span>
                    <span className="font-bold text-[#c9b787]">
                      {(p.projected30d * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-[#c9b787]/40">90-day</span>
                    <span className="font-bold text-[#c9b787]">
                      {(p.projected90d * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-7 bg-[#c9b787]/5 border border-[#c9b787]/10 rounded-xl p-5">
          <h3 className="text-xs font-semibold text-[#c9b787] mb-4 flex items-center gap-2">
            <Lightbulb className="w-3.5 h-3.5 text-[#c9b787]" /> AI Recommendations
          </h3>
          <div className="space-y-2.5">
            {recommendations.map((rec, i) => (
              <div
                key={i}
                className={`p-3.5 rounded-lg border transition-all hover:bg-[#c9b787]/10 cursor-pointer ${rec.priority === 'high' ? 'border-[#f5f5f5]/20 bg-[#f5f5f5]/5' : 'border-[#c9b787]/10 bg-[#c9b787]/5'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium text-[#c9b787]">{rec.title}</p>
                    <p className="text-[10px] text-[#c9b787]/40 mt-0.5">{rec.dimension}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-[10px] font-bold text-[#c9b787]">{rec.impact}</span>
                    <p className="text-[10px] text-[#c9b787]/40 mt-0.5">
                      {rec.confidence}% confidence
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
