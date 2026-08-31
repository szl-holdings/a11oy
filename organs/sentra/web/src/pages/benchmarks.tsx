/**
 * Sentra — Benchmarks & Leaderboards
 * Domain: Cyber Resilience
 * Benchmarks: Threat Detection Accuracy, Mean Time to Triage (MTTT)
 */

import {
  BenchmarkCard,
  EvalBadge,
  LeaderboardTable,
  type LeaderboardEntry,
  ResultDetailDrawer,
  type EvalResultDetail,
  SubmitScoreForm,
  type SubmitScorePayload,
} from '@szl-holdings/design-system';
import {
  Shield,
  Trophy,
} from 'lucide-react';
import { useState } from 'react';

const BG = 'hsl(214,16%,4%)';
const SURFACE = 'hsla(0,0%,100%,0.035)';
const BORDER = 'hsla(0,0%,100%,0.07)';
const TEXT = 'hsl(38,8%,92%)';
const TEXT_SEC = 'hsl(214,7%,55%)';
const ACCENT = '#ef4444';

const BENCHMARKS = [
  {
    benchmarkId: 'szl-cyber-threat-detection-v1',
    name: 'Threat Detection Accuracy',
    description:
      'Evaluates agent ability to classify adversary TTPs, identify lateral movement, and surface true-positive alerts with low false-positive rates across a synthetic enterprise environment.',
    domain: 'cyber',
    evaluationFramework: 'szl-native',
    tags: ['classification', 'triage', 'SOC', 'MITRE ATT&CK'],
    tasks: [
      { taskId: 'tda-ttp', name: 'TTP Classification', primaryMetric: 'f1', higherIsBetter: true, baseline: 0.72 },
      { taskId: 'tda-fp-rate', name: 'False Positive Rate', primaryMetric: 'fpr', higherIsBetter: false, baseline: 0.18 },
      { taskId: 'tda-lateral', name: 'Lateral Movement Detection', primaryMetric: 'recall', higherIsBetter: true, baseline: 0.68 },
    ],
  },
  {
    benchmarkId: 'szl-cyber-mttt-v1',
    name: 'Mean Time to Triage (MTTT)',
    description:
      'Measures end-to-end elapsed time from first alert ingest to fully classified and prioritised incident, across 200 curated incident scenarios of varying severity.',
    domain: 'cyber',
    evaluationFramework: 'szl-native',
    tags: ['latency', 'SOC', 'incident-response', 'agentic'],
    tasks: [
      { taskId: 'mttt-p50', name: 'Median Triage Time', primaryMetric: 'latency_p50_s', higherIsBetter: false, baseline: 420 },
      { taskId: 'mttt-p95', name: 'P95 Triage Time', primaryMetric: 'latency_p95_s', higherIsBetter: false, baseline: 1800 },
      { taskId: 'mttt-accuracy', name: 'Priority Accuracy', primaryMetric: 'accuracy', higherIsBetter: true, baseline: 0.81 },
    ],
  },
];

const LEADERBOARDS: Record<string, LeaderboardEntry[]> = {
  'tda-ttp': [
    { rank: 1, resultId: 'res-001', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'f1', value: 0.947, numericValue: '0.947', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-002', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'f1', value: 0.921, numericValue: '0.921', badgeState: 'verified', evalDate: '2026-03-28', sourceUrl: '#' },
    { rank: 3, resultId: 'res-003', entityId: 'sentra-sentinel-v1', entityLabel: 'Sentinel Behavioral Agent', entityType: 'agent', domain: 'cyber', metric: 'f1', value: 0.883, numericValue: '0.883', badgeState: 'leaderboard', evalDate: '2026-03-10', sourceUrl: '#' },
    { rank: 4, resultId: 'res-004', entityId: 'community-soc-gpt', entityLabel: 'Community SOC-GPT', entityType: 'model', domain: 'cyber', metric: 'f1', value: 0.851, numericValue: '0.851', badgeState: 'community', evalDate: '2026-02-22', sourceUrl: '#' },
  ],
  'tda-fp-rate': [
    { rank: 1, resultId: 'res-005', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'fpr', value: 0.031, numericValue: '0.031', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-006', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'fpr', value: 0.048, numericValue: '0.048', badgeState: 'verified', evalDate: '2026-03-28', sourceUrl: '#' },
  ],
  'tda-lateral': [
    { rank: 1, resultId: 'res-007', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'recall', value: 0.938, numericValue: '0.938', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-008', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'recall', value: 0.904, numericValue: '0.904', badgeState: 'leaderboard', evalDate: '2026-03-28', sourceUrl: '#' },
  ],
  'mttt-p50': [
    { rank: 1, resultId: 'res-009', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'latency_p50_s', value: 38, numericValue: '38', unit: 's', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-010', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'latency_p50_s', value: 54, numericValue: '54', unit: 's', badgeState: 'leaderboard', evalDate: '2026-03-28', sourceUrl: '#' },
    { rank: 3, resultId: 'res-011', entityId: 'sentra-sentinel-v1', entityLabel: 'Sentinel Behavioral Agent', entityType: 'agent', domain: 'cyber', metric: 'latency_p50_s', value: 91, numericValue: '91', unit: 's', badgeState: 'leaderboard', evalDate: '2026-03-10', sourceUrl: '#' },
  ],
  'mttt-p95': [
    { rank: 1, resultId: 'res-012', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'latency_p95_s', value: 187, numericValue: '187', unit: 's', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-013', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'latency_p95_s', value: 243, numericValue: '243', unit: 's', badgeState: 'leaderboard', evalDate: '2026-03-28', sourceUrl: '#' },
  ],
  'mttt-accuracy': [
    { rank: 1, resultId: 'res-014', entityId: 'sentra-agentic-soc-v3', entityLabel: 'Sentra Agentic SOC v3', entityType: 'agent', domain: 'cyber', metric: 'accuracy', value: 0.962, numericValue: '0.962', badgeState: 'verified', evalDate: '2026-04-15', sourceUrl: '#' },
    { rank: 2, resultId: 'res-015', entityId: 'sentra-autonomous-v2', entityLabel: 'Sentra Autonomous SOC v2', entityType: 'agent', domain: 'cyber', metric: 'accuracy', value: 0.934, numericValue: '0.934', badgeState: 'verified', evalDate: '2026-03-28', sourceUrl: '#' },
  ],
};

function toDetail(entry: LeaderboardEntry): EvalResultDetail {
  return {
    resultId: entry.resultId,
    benchmarkId: 'sentra-benchmark',
    benchmarkName: 'Sentra Cyber Benchmark',
    taskId: entry.metric,
    entityId: entry.entityId,
    entityLabel: entry.entityLabel,
    entityType: entry.entityType,
    domain: entry.domain,
    metric: entry.metric,
    value: entry.value,
    numericValue: entry.numericValue,
    unit: entry.unit,
    higherIsBetter: entry.metric !== 'latency_p50_s' && entry.metric !== 'latency_p95_s' && entry.metric !== 'fpr',
    badgeState: entry.badgeState,
    evalDate: entry.evalDate,
    sourceUrl: entry.sourceUrl,
  };
}

type Tab = 'leaderboards' | 'benchmarks' | 'submit';

export default function SentraBenchmarks() {
  const [activeTab, setActiveTab] = useState<Tab>('leaderboards');
  const [selectedTaskId, setSelectedTaskId] = useState<string>('tda-ttp');
  const [selectedBenchmark, setSelectedBenchmark] = useState<string | null>(null);
  const [drawerResult, setDrawerResult] = useState<EvalResultDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  function openDrawer(entry: LeaderboardEntry) {
    setDrawerResult(toDetail(entry));
    setDrawerOpen(true);
  }

  const allTasks = BENCHMARKS.flatMap((b) => b.tasks.map((t) => ({ ...t, benchmarkId: b.benchmarkId, benchmarkName: b.name })));
  const currentTask = allTasks.find((t) => t.taskId === selectedTaskId) ?? allTasks[0];
  const currentEntries = LEADERBOARDS[selectedTaskId] ?? [];

  return (
    <div style={{ minHeight: '100vh', backgroundColor: BG, color: TEXT, fontFamily: 'inherit' }}>
      {/* Header */}
      <div style={{ borderBottom: `1px solid ${BORDER}`, padding: '1.5rem 2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
          <Shield style={{ width: '1.25rem', height: '1.25rem', color: ACCENT }} />
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Benchmarks &amp; Leaderboards</h1>
          <EvalBadge state="verified" label="Open Eval Layer" />
        </div>
        <p style={{ color: TEXT_SEC, fontSize: '0.875rem', margin: 0 }}>
          Verified performance scores for Sentra agents, workflows, and threat-detection models — powered by the SZL Open Evaluation Layer.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', padding: '1rem 2rem 0', borderBottom: `1px solid ${BORDER}` }}>
        {(['leaderboards', 'benchmarks', 'submit'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '6px 6px 0 0',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.8125rem',
              fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? TEXT : TEXT_SEC,
              backgroundColor: activeTab === tab ? SURFACE : 'transparent',
              borderBottom: activeTab === tab ? `2px solid ${ACCENT}` : '2px solid transparent',
            }}
          >
            {tab === 'leaderboards' ? 'Leaderboards' : tab === 'benchmarks' ? 'Benchmark Specs' : 'Submit Score'}
          </button>
        ))}
      </div>

      <div style={{ padding: '1.5rem 2rem', maxWidth: '1100px' }}>
        {/* Leaderboards tab */}
        {activeTab === 'leaderboards' && (
          <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '1.5rem', alignItems: 'start' }}>
            {/* Task selector */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: TEXT_SEC, marginBottom: '0.25rem' }}>Benchmark Tasks</span>
              {BENCHMARKS.map((bm) => (
                <div key={bm.benchmarkId}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: ACCENT, padding: '0.25rem 0.5rem', marginBottom: '0.25rem' }}>
                    {bm.name}
                  </div>
                  {bm.tasks.map((task) => (
                    <button
                      key={task.taskId}
                      onClick={() => setSelectedTaskId(task.taskId)}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        padding: '0.375rem 0.75rem',
                        borderRadius: '6px',
                        border: selectedTaskId === task.taskId ? `1px solid ${ACCENT}40` : `1px solid transparent`,
                        background: selectedTaskId === task.taskId ? `${ACCENT}10` : 'transparent',
                        color: selectedTaskId === task.taskId ? TEXT : TEXT_SEC,
                        fontSize: '0.8125rem',
                        cursor: 'pointer',
                        marginBottom: '0.125rem',
                      }}
                    >
                      {task.name}
                    </button>
                  ))}
                </div>
              ))}
            </div>

            {/* Active leaderboard */}
            <div>
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <Trophy style={{ width: '1rem', height: '1rem', color: '#f59e0b' }} />
                  <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{currentTask?.name}</span>
                </div>
                <span style={{ fontSize: '0.8125rem', color: TEXT_SEC }}>Metric: <strong>{currentTask?.primaryMetric}</strong></span>
              </div>
              <LeaderboardTable
                entries={currentEntries}
                title={`${currentTask?.name} Leaderboard`}
                higherIsBetter={currentTask?.higherIsBetter ?? true}
                onRowClick={openDrawer}
              />
              <p style={{ fontSize: '0.75rem', color: TEXT_SEC, marginTop: '0.75rem' }}>
                Click any row to inspect source traces, evaluation metadata, and provenance details.
                Scores link back to the originating benchmark run. <a href="/command/open-eval-hub" style={{ color: ACCENT }}>Open Evaluation Hub →</a>
              </p>
            </div>
          </div>
        )}

        {/* Benchmark specs tab */}
        {activeTab === 'benchmarks' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ color: TEXT_SEC, fontSize: '0.875rem', marginBottom: '0.25rem' }}>
              Benchmark specifications registered for the Cyber domain. Tasks and metrics are immutable after publication; new versions create a new benchmark ID.
            </p>
            {BENCHMARKS.map((bm) => (
              <BenchmarkCard
                key={bm.benchmarkId}
                {...bm}
                onClick={() => setSelectedBenchmark(selectedBenchmark === bm.benchmarkId ? null : bm.benchmarkId)}
                onLeaderboardClick={(taskId) => { setSelectedTaskId(taskId); setActiveTab('leaderboards'); }}
              />
            ))}
          </div>
        )}

        {/* Submit tab */}
        {activeTab === 'submit' && (
          <div style={{ maxWidth: '640px' }}>
            <p style={{ color: TEXT_SEC, fontSize: '0.875rem', marginBottom: '1rem' }}>
              Submit a community eval result for a Sentra agent or workflow. Results enter a verification queue before appearing on the leaderboard.
            </p>
            <SubmitScoreForm
              domain="cyber"
              onSubmit={async (payload: SubmitScorePayload) => {
                await new Promise((r) => setTimeout(r, 600));
                console.info('Sentra eval submission:', payload);
              }}
            />
          </div>
        )}
      </div>

      <ResultDetailDrawer
        result={drawerResult}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
