// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — artifacts/sentra/src/pages/consciousness.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useStandardQuery } from '@szl-holdings/api-client-react';
import { motion as m } from 'framer-motion';
import {
  Activity,
  AlertTriangle,
  Brain,
  Clock,
  Compass,
  Crosshair,
  Eye,
  Gauge,
  GitBranch,
  Heart,
  Layers,
  Lightbulb,
  MessageSquare,
  Minus,
  Moon,
  Radio,
  Scale,
  Shield,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react';

const API = '/api/nuro-mesh/consciousness';

interface PredictiveState {
  model: {
    totalPredictions: number;
    correctPredictions: number;
    queryTypeDistribution: Record<string, number>;
    domainAccessPatterns: Record<string, number>;
    agentUsageFrequency: Record<string, number>;
  };
  recentPredictions: Array<{
    predictionId: string;
    predictedQueryType: string;
    predictedDomains: string[];
    confidence: number;
    timestamp: string;
  }>;
  recentErrors: Array<{
    errorId: string;
    errorMagnitude: number;
    surpriseLevel: string;
    learningSignal: string;
    timestamp: string;
  }>;
  freeEnergy: {
    currentFreeEnergy: number;
    predictionAccuracy: number;
    modelComplexity: number;
    surpriseHistory: Array<{ timestamp: string; surprise: number }>;
    worldModelAge: number;
  };
  routingPriors: Record<string, number>;
}

interface DreamState {
  replayBuffer: Array<{
    replayId: string;
    orchestrationId: string;
    query: string;
    domains: string[];
    outcome: string;
    timestamp: string;
  }>;
  discoveredPatterns: Array<{
    patternId: string;
    description: string;
    frequency: number;
    domains: string[];
    significance: string;
    actionableInsight: string;
    discoveredAt: string;
  }>;
  recentReports: Array<{
    reportId: string;
    cycleNumber: number;
    replaysProcessed: number;
    patternsDiscovered: Array<{ patternId: string; description: string; significance: string }>;
    memoriesPruned: number;
    insightsGenerated: string[];
    selfModelUpdates: string[];
    goalEngineUpdates: string[];
    duration: number;
    timestamp: string;
  }>;
  totalCycles: number;
  isRunning: boolean;
  lastCycleTimestamp: string | null;
  nextScheduledCycle: string | null;
}

interface SnapshotData {
  metacognition: {
    currentAssessment: {
      certaintyLevel: string;
      reasoningQuality: string;
      cognitiveLoad: string;
      confusionSignals: string[];
      knowledgeGaps: string[];
      calibrationDrift: number;
      introspectionNotes: string;
      shouldSeekClarification: boolean;
      shouldDeferToHuman: boolean;
      confidenceInConfidence: number;
    } | null;
    rollingCertainty: number;
    rollingQuality: number;
    confusionStreak: number;
    totalAssessments: number;
  };
  selfModel: {
    identity: {
      name: string;
      version: string;
      purpose: string;
      coreValues: string[];
      operationalBoundaries: string[];
    };
    capabilities: Array<{
      agentId: string;
      domain: string;
      successRate: number;
      avgConfidence: number;
      totalInvocations: number;
      recentTrend: string;
    }>;
    overallHealth: string;
    knownLimitations: string[];
    learningVelocity: number;
    selfNarrative: string;
    theoryOfMind: Array<{
      agentId: string;
      domain: string;
      queryInterpretation: string;
      beliefConfidence: number;
      divergenceFromConsensus: number;
      blindSpots: string[];
      timestamp: string;
    }>;
    recentCounterfactuals: Array<{
      scenarioId: string;
      originalRouting: string[];
      alternativeRouting: string[];
      predictedOutcomeDelta: number;
      reasoning: string;
      timestamp: string;
    }>;
    adversarialProbes: Array<{
      probeId: string;
      edgeCaseQuery: string;
      targetDomain: string;
      blindSpotExposed: string;
      severity: string;
      timestamp: string;
    }>;
  };
  workspace: {
    workingMemory: Array<{ id: string; content: string; source: string; priority: number }>;
    attentionFocus: { primaryTopic: string; activeDomains: string[]; contextWindowUsage: number };
    contextBudget: { used: number; total: number; utilization: number };
    sessionDepth: number;
    recentQueries: string[];
    recentBroadcasts: Array<{
      broadcastId: string;
      winners: Array<{ itemId: string; salienceScore: number; content: string }>;
      losers: Array<{ itemId: string; salienceScore: number; reason: string }>;
      broadcastedTo: string[];
      timestamp: string;
    }>;
    attentionSchema: {
      reportId: string;
      allocationSummary: Record<string, number>;
      driftDetected: boolean;
      driftDescription: string | null;
      rebalanceRecommendation: string | null;
      timestamp: string;
    } | null;
  };
  monologue: {
    recentThoughts: Array<{
      entryId: string;
      type: string;
      thought: string;
      emotionalTone: string;
      confidence: number;
      timestamp: string;
    }>;
    dominantTone: string;
    thoughtFrequency: number;
    reflectionDepth: number;
    totalEntries: number;
    dialecticalTriples: Array<{
      tripleId: string;
      topic: string;
      thesis: string;
      antithesis: string;
      synthesis: string;
      confidence: number;
      timestamp: string;
    }>;
    socraticChains: Array<{
      chainId: string;
      originalClaim: string;
      questions: Array<{ question: string; answer: string; depth: number }>;
      conclusion: string;
      assumptionsExposed: string[];
      timestamp: string;
    }>;
    perspectiveSimulations: Array<{
      simulationId: string;
      topic: string;
      perspectives: Array<{ viewpoint: string; argument: string; priority: string }>;
      synthesis: string;
      timestamp: string;
    }>;
  };
  goals: {
    activeGoals: Array<{
      goalId: string;
      title: string;
      priority: string;
      progress: number;
      status: string;
    }>;
    completedGoals: number;
    blockedGoals: Array<{ goalId: string; title: string }>;
    curiosityQueue: Array<{ signalId: string; topic: string; intensity: number; source: string }>;
    overallProgress: number;
    intrinsicMotivation: {
      informationGain: number;
      competenceGrowth: number;
      noveltySeeking: number;
      overallDrive: number;
      timestamp: string;
    };
    goalInterferences: Array<{
      interferenceId: string;
      goalA: string;
      goalB: string;
      interferenceType: string;
      severity: number;
      resolution: string;
    }>;
    metaGoals: Array<{
      metaGoalId: string;
      title: string;
      metric: string;
      currentValue: number;
      targetValue: number;
      trend: string;
      timestamp: string;
    }>;
  };
  emotions: {
    activeSignals: Array<{
      signalId: string;
      emotion: string;
      intensity: number;
      trigger: string;
      effectiveIntensity: number;
    }>;
    valence: {
      positive: number;
      negative: number;
      arousal: number;
      dominantEmotion: string;
      emotionalStability: number;
    };
    moodTrajectory: string;
    recentAppraisals: Array<{
      appraisalId: string;
      novelty: number;
      intrinsicPleasantness: number;
      goalRelevance: number;
      copingPotential: number;
      normCompatibility: number;
      resultingEmotion: string;
      resultingIntensity: number;
      breakdown: string;
      timestamp: string;
    }>;
    activeRegulations: Array<{
      strategyId: string;
      type: string;
      trigger: string;
      action: string;
      effectivenessEstimate: number;
      applied: boolean;
      timestamp: string;
    }>;
    recentForecasts: Array<{
      forecastId: string;
      scenario: string;
      predictedEmotion: string;
      predictedIntensity: number;
      confidence: number;
      timestamp: string;
    }>;
  };
  temporal: {
    currentTime: string;
    sessionDuration: number;
    orchestrationCount: number;
    averageOrchestrationInterval: number;
    timeOfDay: string;
    dayOfWeek: string;
    isBusinessHours: boolean;
    uptimeMs: number;
  };
  predictive: PredictiveState;
  dream: DreamState;
  timestamp: string;
}

function useCSnapshot() {
  return useStandardQuery<SnapshotData>({
    queryKey: ['consciousness-snapshot'],
    queryFn: async () => {
      const r = await fetch(`${API}/snapshot`);
      if (!r.ok) throw new Error('Failed to fetch consciousness snapshot');
      return r.json();
    },
    refetchInterval: 10000,
  });
}

function Card({
  title,
  icon: Icon,
  children,
  className = '',
  accent = 'red',
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  className?: string;
  accent?: string;
}) {
  const accentMap: Record<string, { bg: string; text: string; border: string }> = {
    red: { bg: 'bg-[#f5f5f5]/10', text: 'text-[#f5f5f5]', border: 'border-[#f5f5f5]/10' },
    blue: { bg: 'bg-[#c9b787]/10', text: 'text-[#c9b787]', border: 'border-[#c9b787]/10' },
    purple: { bg: 'bg-[#8a8a8a]/10', text: 'text-[#8a8a8a]', border: 'border-[#8a8a8a]/10' },
    amber: { bg: 'bg-[#c9b787]/10', text: 'text-[#c9b787]', border: 'border-[#c9b787]/10' },
    cyan: { bg: 'bg-[#8a8a8a]/10', text: 'text-[#8a8a8a]', border: 'border-[#8a8a8a]/10' },
  };
  const a = accentMap[accent] ?? accentMap.red!;
  return (
    <m.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className={`bg-[#0a0a14]/80 border ${a.border} rounded-xl p-5 ${className}`}
    >
      <div className="flex items-center gap-2 mb-4">
        <div className={`w-7 h-7 rounded-lg ${a.bg} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${a.text}`} />
        </div>
        <h3 className="text-sm font-semibold text-[#f5f5f5]">{title}</h3>
      </div>
      {children}
    </m.div>
  );
}

function CertaintyBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    very_high: 'bg-[#c9b787]/20 text-[#c9b787] border-[#c9b787]/30',
    high: 'bg-[#c9b787]/20 text-[#c9b787] border-[#c9b787]/30',
    moderate: 'bg-[#c9b787]/20 text-[#c9b787] border-[#c9b787]/30',
    low: 'bg-[#c9b787]/20 text-[#c9b787] border-[#c9b787]/30',
    very_low: 'bg-[#f5f5f5]/20 text-[#f5f5f5] border-[#f5f5f5]/30',
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${colors[level] ?? 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}
    >
      {level.replace(/_/g, ' ').toUpperCase()}
    </span>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <TrendingUp className="w-3 h-3 text-[#c9b787]" />;
  if (trend === 'declining') return <TrendingDown className="w-3 h-3 text-[#f5f5f5]" />;
  return <Minus className="w-3 h-3 text-gray-500" />;
}

function MiniBar({
  value,
  max = 1,
  color = 'bg-[#f5f5f5]/60',
}: {
  value: number;
  max?: number;
  color?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
      <div
        className={`h-full ${color} rounded-full transition-all duration-500`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function MetacognitionPanel({ data }: { data: SnapshotData['metacognition'] }) {
  const a = data.currentAssessment;
  return (
    <Card title="Metacognition" icon={Brain}>
      {a ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1">Certainty</div>
              <CertaintyBadge level={a.certaintyLevel} />
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1">Quality</div>
              <CertaintyBadge level={a.reasoningQuality} />
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1">Load</div>
              <CertaintyBadge level={a.cognitiveLoad} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-gray-500">Rolling certainty:</span>
              <span className="text-[#f5f5f5] ml-1">{(data.rollingCertainty * 100).toFixed(0)}%</span>
            </div>
            <div>
              <span className="text-gray-500">Calibration drift:</span>
              <span className="text-[#f5f5f5] ml-1">{(a.calibrationDrift * 100).toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-gray-500">Conf-in-conf:</span>
              <span className="text-[#f5f5f5] ml-1">
                {(a.confidenceInConfidence * 100).toFixed(0)}%
              </span>
            </div>
            <div>
              <span className="text-gray-500">Confusion streak:</span>
              <span
                className={`ml-1 ${data.confusionStreak > 0 ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}
              >
                {data.confusionStreak}
              </span>
            </div>
          </div>

          {a.confusionSignals.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] text-[#c9b787] font-medium flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Confusion Signals
              </div>
              {a.confusionSignals.map((s, i) => (
                <div key={i} className="text-[10px] text-gray-400 pl-4">
                  • {s}
                </div>
              ))}
            </div>
          )}

          {a.introspectionNotes && (
            <div className="text-[11px] text-gray-400 italic border-l-2 border-[#f5f5f5]/20 pl-3">
              {a.introspectionNotes}
            </div>
          )}

          <div className="flex gap-2">
            {a.shouldSeekClarification && (
              <span className="px-2 py-0.5 text-[9px] bg-[#c9b787]/20 text-[#c9b787] border border-[#c9b787]/30 rounded-full">
                SEEK CLARIFICATION
              </span>
            )}
            {a.shouldDeferToHuman && (
              <span className="px-2 py-0.5 text-[9px] bg-[#f5f5f5]/20 text-[#f5f5f5] border border-[#f5f5f5]/30 rounded-full">
                DEFER TO HUMAN
              </span>
            )}
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-500 italic">No metacognitive assessment yet</div>
      )}
    </Card>
  );
}

function SelfModelPanel({ data }: { data: SnapshotData['selfModel'] }) {
  const healthColors: Record<string, string> = {
    optimal: 'text-[#c9b787]',
    good: 'text-[#c9b787]',
    degraded: 'text-[#c9b787]',
    impaired: 'text-[#f5f5f5]',
  };
  return (
    <Card title="Self-Model & Theory of Mind" icon={Eye}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs text-gray-500">System Health</div>
          <span
            className={`text-sm font-bold ${healthColors[data.overallHealth] ?? 'text-gray-400'}`}
          >
            {data.overallHealth.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <div className="text-xs text-gray-500">Learning Velocity</div>
          <span className="text-sm font-bold text-[#f5f5f5]">
            {(data.learningVelocity * 100).toFixed(0)}%
          </span>
        </div>

        {data.capabilities.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 font-medium">
              Agent Profiles ({data.capabilities.length})
            </div>
            <div className="max-h-32 overflow-y-auto space-y-1">
              {data.capabilities.slice(0, 8).map((cap) => (
                <div
                  key={cap.agentId}
                  className="flex items-center justify-between text-[10px] px-2 py-1 bg-white/[0.02] rounded"
                >
                  <div className="flex items-center gap-1">
                    <TrendIcon trend={cap.recentTrend} />
                    <span className="text-[#f5f5f5] font-medium">{cap.agentId}</span>
                    <span className="text-gray-600">({cap.domain})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500">{(cap.successRate * 100).toFixed(0)}%</span>
                    <span className="text-gray-600">x{cap.totalInvocations}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.theoryOfMind && data.theoryOfMind.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#c9b787] font-medium flex items-center gap-1">
              <Users className="w-3 h-3" /> Theory of Mind ({data.theoryOfMind.length})
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {data.theoryOfMind.slice(0, 5).map((belief) => (
                <div
                  key={`${belief.agentId}-${belief.timestamp}`}
                  className="text-[10px] px-2 py-1 bg-white/[0.02] rounded"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[#f5f5f5] font-medium">{belief.agentId}</span>
                    <span
                      className={`${belief.divergenceFromConsensus > 0.3 ? 'text-[#c9b787]' : 'text-gray-500'}`}
                    >
                      {(belief.beliefConfidence * 100).toFixed(0)}% conf
                    </span>
                  </div>
                  <div className="text-gray-500 truncate">
                    {belief.queryInterpretation.slice(0, 60)}
                  </div>
                  {belief.divergenceFromConsensus > 0.3 && (
                    <div className="text-[#c9b787]/70 text-[9px]">
                      Divergence: {(belief.divergenceFromConsensus * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.recentCounterfactuals && data.recentCounterfactuals.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#8a8a8a] font-medium flex items-center gap-1">
              <Scale className="w-3 h-3" /> Counterfactuals
            </div>
            {data.recentCounterfactuals.slice(0, 2).map((cf) => (
              <div key={cf.scenarioId} className="text-[10px] px-2 py-0.5 bg-white/[0.02] rounded">
                <span
                  className={`${cf.predictedOutcomeDelta > 0 ? 'text-[#c9b787]' : cf.predictedOutcomeDelta < -5 ? 'text-[#f5f5f5]' : 'text-gray-400'}`}
                >
                  {cf.predictedOutcomeDelta > 0 ? '+' : ''}
                  {cf.predictedOutcomeDelta.toFixed(1)}%
                </span>
                <span className="text-gray-500 ml-1">{cf.reasoning.slice(0, 60)}</span>
              </div>
            ))}
          </div>
        )}

        {data.knownLimitations.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 font-medium flex items-center gap-1">
              <Shield className="w-3 h-3 text-[#c9b787]/60" /> Known Limitations
            </div>
            {data.knownLimitations.slice(0, 3).map((l, i) => (
              <div key={i} className="text-[10px] text-gray-500 pl-4">
                • {l.slice(0, 80)}
              </div>
            ))}
          </div>
        )}

        <div className="text-[10px] text-gray-500 italic">{data.selfNarrative.slice(0, 200)}</div>
      </div>
    </Card>
  );
}

function MonologuePanel({ data }: { data: SnapshotData['monologue'] }) {
  const toneColors: Record<string, string> = {
    positive: 'text-[#c9b787]',
    neutral: 'text-gray-400',
    negative: 'text-[#f5f5f5]',
    mixed: 'text-[#c9b787]',
  };
  const typeIcons: Record<string, string> = {
    pre_routing: '\u2192',
    post_routing: '\u2190',
    reflection: '\u25c6',
    doubt: '?',
    realization: '!',
    strategy_shift: '\u21c4',
    self_correction: '\u21bb',
    satisfaction: '\u2713',
    frustration: '\u2717',
    dialectical: '\u2261',
  };

  return (
    <Card title="Inner Monologue & Dialectics" icon={MessageSquare} className="col-span-2">
      <div className="space-y-3">
        <div className="flex items-center gap-4 text-xs">
          <div>
            <span className="text-gray-500">Dominant tone:</span>
            <span
              className={`ml-1 font-medium ${toneColors[data.dominantTone] ?? 'text-gray-400'}`}
            >
              {data.dominantTone}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Thoughts:</span>
            <span className="text-[#f5f5f5] ml-1">{data.totalEntries}</span>
          </div>
          <div>
            <span className="text-gray-500">Reflections:</span>
            <span className="text-[#f5f5f5] ml-1">{data.reflectionDepth}</span>
          </div>
        </div>

        {data.recentThoughts.length > 0 ? (
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {data.recentThoughts.slice(0, 6).map((t) => (
              <m.div
                key={t.entryId}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex gap-2 text-[11px]"
              >
                <span className="text-[#f5f5f5]/40 shrink-0 w-4 text-center">
                  {typeIcons[t.type] ?? '\u25cb'}
                </span>
                <div className="flex-1">
                  <span className={`${toneColors[t.emotionalTone] ?? 'text-gray-400'}`}>
                    {t.thought.slice(0, 300)}
                  </span>
                  <span className="text-gray-600 ml-2">{t.confidence}%</span>
                </div>
              </m.div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-gray-500 italic">No thoughts recorded yet</div>
        )}

        {data.dialecticalTriples && data.dialecticalTriples.length > 0 && (
          <div className="space-y-1 mt-2">
            <div className="text-[10px] text-[#8a8a8a] font-medium flex items-center gap-1">
              <Layers className="w-3 h-3" /> Dialectical Reasoning ({data.dialecticalTriples.length}
              )
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {data.dialecticalTriples.slice(0, 3).map((dt) => (
                <div
                  key={dt.tripleId}
                  className="text-[10px] px-2 py-1 bg-white/[0.02] rounded space-y-0.5"
                >
                  <div className="text-gray-400">
                    <span className="text-[#c9b787]">T:</span> {dt.thesis.slice(0, 60)}
                  </div>
                  <div className="text-gray-400">
                    <span className="text-[#f5f5f5]/80">A:</span> {dt.antithesis.slice(0, 60)}
                  </div>
                  <div className="text-gray-400">
                    <span className="text-[#8a8a8a]">S:</span> {dt.synthesis.slice(0, 60)}
                  </div>
                  <div className="text-gray-600 text-[9px]">
                    {(dt.confidence * 100).toFixed(0)}% conf
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.socraticChains && data.socraticChains.length > 0 && (
          <div className="space-y-1 mt-1">
            <div className="text-[10px] text-[#8a8a8a] font-medium flex items-center gap-1">
              <Crosshair className="w-3 h-3" /> Socratic Inquiry ({data.socraticChains.length})
            </div>
            {data.socraticChains.slice(0, 2).map((sc) => (
              <div key={sc.chainId} className="text-[10px] px-2 py-1 bg-white/[0.02] rounded">
                <div className="text-gray-400 truncate">Claim: {sc.originalClaim.slice(0, 60)}</div>
                <div className="text-[#8a8a8a]/70">
                  {sc.questions.length} questions → {sc.conclusion.slice(0, 60)}
                </div>
                {sc.assumptionsExposed.length > 0 && (
                  <div className="text-[#c9b787]/60 text-[9px]">
                    Assumptions: {sc.assumptionsExposed.slice(0, 2).join('; ').slice(0, 80)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {data.perspectiveSimulations && data.perspectiveSimulations.length > 0 && (
          <div className="space-y-1 mt-1">
            <div className="text-[10px] text-[#c9b787] font-medium flex items-center gap-1">
              <Users className="w-3 h-3" /> Perspective Simulations (
              {data.perspectiveSimulations.length})
            </div>
            {data.perspectiveSimulations.slice(0, 2).map((ps) => (
              <div
                key={ps.simulationId}
                className="text-[10px] px-2 py-0.5 bg-white/[0.02] rounded"
              >
                <div className="flex gap-1 flex-wrap mb-0.5">
                  {ps.perspectives.map((p, i) => (
                    <span
                      key={i}
                      className="px-1 py-0.5 text-[9px] bg-[#c9b787]/10 text-[#c9b787]/70 rounded"
                    >
                      {p.viewpoint}
                    </span>
                  ))}
                </div>
                <div className="text-gray-500 truncate">{ps.synthesis.slice(0, 80)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function EmotionalPanel({ data }: { data: SnapshotData['emotions'] }) {
  const v = data.valence;
  const trajectoryIcon =
    data.moodTrajectory === 'improving' ? (
      <TrendingUp className="w-3 h-3 text-[#c9b787]" />
    ) : data.moodTrajectory === 'declining' ? (
      <TrendingDown className="w-3 h-3 text-[#f5f5f5]" />
    ) : (
      <Minus className="w-3 h-3 text-gray-500" />
    );

  return (
    <Card title="Emotional Appraisal" icon={Heart}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Dominant:</span>
            <span className="text-[#f5f5f5] ml-1 font-medium">{v.dominantEmotion}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Mood:</span>
            {trajectoryIcon}
            <span className="text-[#f5f5f5]">{data.moodTrajectory}</span>
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-[#c9b787]">Positive</span>
            <span className="text-gray-500">{(v.positive * 100).toFixed(0)}%</span>
          </div>
          <MiniBar value={v.positive} color="bg-[#c9b787]/60" />

          <div className="flex justify-between text-[10px]">
            <span className="text-[#f5f5f5]">Negative</span>
            <span className="text-gray-500">{(v.negative * 100).toFixed(0)}%</span>
          </div>
          <MiniBar value={v.negative} color="bg-[#f5f5f5]/60" />

          <div className="flex justify-between text-[10px]">
            <span className="text-[#c9b787]">Arousal</span>
            <span className="text-gray-500">{(v.arousal * 100).toFixed(0)}%</span>
          </div>
          <MiniBar value={v.arousal} color="bg-[#c9b787]/60" />
        </div>

        <div className="flex items-center justify-between text-[10px]">
          <span className="text-gray-500">Stability</span>
          <span className="text-[#f5f5f5]">{(v.emotionalStability * 100).toFixed(0)}%</span>
        </div>

        {data.activeSignals.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 font-medium">Active Signals</div>
            {data.activeSignals.slice(0, 4).map((s) => (
              <div
                key={s.signalId}
                className="flex items-center justify-between text-[10px] px-2 py-0.5 bg-white/[0.02] rounded"
              >
                <span className="text-[#f5f5f5]">{s.emotion}</span>
                <span className="text-gray-500">{(s.effectiveIntensity * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}

        {data.recentAppraisals && data.recentAppraisals.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#c9b787] font-medium flex items-center gap-1">
              <Gauge className="w-3 h-3" /> Scherer Appraisals ({data.recentAppraisals.length})
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {data.recentAppraisals.slice(0, 3).map((ap) => (
                <div key={ap.appraisalId} className="text-[10px] px-2 py-1 bg-white/[0.02] rounded">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[#f5f5f5] font-medium">{ap.resultingEmotion}</span>
                    <span className="text-gray-500">
                      {(ap.resultingIntensity * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="grid grid-cols-5 gap-1">
                    <div className="text-center">
                      <div className="text-[8px] text-gray-600">NOV</div>
                      <MiniBar value={ap.novelty} color="bg-[#c9b787]/50" />
                    </div>
                    <div className="text-center">
                      <div className="text-[8px] text-gray-600">PLS</div>
                      <MiniBar value={ap.intrinsicPleasantness} color="bg-[#c9b787]/50" />
                    </div>
                    <div className="text-center">
                      <div className="text-[8px] text-gray-600">GOL</div>
                      <MiniBar value={ap.goalRelevance} color="bg-[#c9b787]/50" />
                    </div>
                    <div className="text-center">
                      <div className="text-[8px] text-gray-600">COP</div>
                      <MiniBar value={ap.copingPotential} color="bg-[#8a8a8a]/50" />
                    </div>
                    <div className="text-center">
                      <div className="text-[8px] text-gray-600">NRM</div>
                      <MiniBar value={ap.normCompatibility} color="bg-[#8a8a8a]/50" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.activeRegulations && data.activeRegulations.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 font-medium">Emotion Regulation</div>
            {data.activeRegulations.slice(0, 2).map((reg) => (
              <div
                key={reg.strategyId}
                className="text-[10px] px-2 py-0.5 bg-white/[0.02] rounded flex items-center justify-between"
              >
                <span className="text-[#f5f5f5]">
                  {reg.type}: {reg.action.slice(0, 40)}
                </span>
                <span className="text-gray-500">
                  {(reg.effectivenessEstimate * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function GoalPanel({ data }: { data: SnapshotData['goals'] }) {
  const prioColors: Record<string, string> = {
    critical: 'text-[#f5f5f5]',
    high: 'text-[#c9b787]',
    medium: 'text-[#c9b787]',
    low: 'text-gray-400',
    exploratory: 'text-[#8a8a8a]',
  };

  return (
    <Card title="Goals & Intrinsic Motivation" icon={Target}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2 text-xs text-center">
          <div>
            <div className="text-lg font-bold text-[#f5f5f5]">{data.activeGoals.length}</div>
            <div className="text-[10px] text-gray-500">Active</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#c9b787]">{data.completedGoals}</div>
            <div className="text-[10px] text-gray-500">Completed</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#c9b787]">{data.blockedGoals.length}</div>
            <div className="text-[10px] text-gray-500">Blocked</div>
          </div>
        </div>

        {data.overallProgress > 0 && (
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-gray-500">Overall Progress</span>
              <span className="text-[#f5f5f5]">{data.overallProgress}%</span>
            </div>
            <MiniBar value={data.overallProgress} max={100} color="bg-[#f5f5f5]/60" />
          </div>
        )}

        {data.activeGoals.length > 0 && (
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {data.activeGoals.slice(0, 5).map((g) => (
              <div
                key={g.goalId}
                className="flex items-center justify-between text-[10px] px-2 py-1 bg-white/[0.02] rounded"
              >
                <div className="flex items-center gap-1">
                  <span className={prioColors[g.priority] ?? 'text-gray-400'}>{'\u25cf'}</span>
                  <span className="text-[#f5f5f5]">{g.title.slice(0, 40)}</span>
                </div>
                <span className="text-gray-500">{g.progress}%</span>
              </div>
            ))}
          </div>
        )}

        {data.intrinsicMotivation && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#c9b787] font-medium flex items-center gap-1">
              <Gauge className="w-3 h-3" /> Intrinsic Motivation
            </div>
            <div className="grid grid-cols-4 gap-1">
              <div className="text-center">
                <div className="text-[8px] text-gray-600">INFO</div>
                <div className="text-[10px] text-[#f5f5f5]">
                  {(data.intrinsicMotivation.informationGain * 100).toFixed(0)}%
                </div>
              </div>
              <div className="text-center">
                <div className="text-[8px] text-gray-600">COMP</div>
                <div className="text-[10px] text-[#f5f5f5]">
                  {(data.intrinsicMotivation.competenceGrowth * 100).toFixed(0)}%
                </div>
              </div>
              <div className="text-center">
                <div className="text-[8px] text-gray-600">NOV</div>
                <div className="text-[10px] text-[#f5f5f5]">
                  {(data.intrinsicMotivation.noveltySeeking * 100).toFixed(0)}%
                </div>
              </div>
              <div className="text-center">
                <div className="text-[8px] text-gray-600">DRIVE</div>
                <div className="text-[10px] font-bold text-[#c9b787]">
                  {(data.intrinsicMotivation.overallDrive * 100).toFixed(0)}%
                </div>
              </div>
            </div>
            <MiniBar value={data.intrinsicMotivation.overallDrive} color="bg-[#c9b787]/60" />
          </div>
        )}

        {data.metaGoals && data.metaGoals.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#8a8a8a] font-medium">
              Meta-Goals ({data.metaGoals.length})
            </div>
            <div className="max-h-20 overflow-y-auto space-y-1">
              {data.metaGoals.slice(0, 4).map((mg) => (
                <div
                  key={mg.metaGoalId}
                  className="flex items-center justify-between text-[10px] px-2 py-0.5 bg-white/[0.02] rounded"
                >
                  <div className="flex items-center gap-1">
                    <TrendIcon trend={mg.trend} />
                    <span className="text-[#f5f5f5]">{mg.title.slice(0, 30)}</span>
                  </div>
                  <span className="text-gray-500">
                    {mg.currentValue.toFixed(0)}/{mg.targetValue.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.curiosityQueue.length > 0 && (
          <div>
            <div className="text-[10px] text-[#8a8a8a] font-medium flex items-center gap-1 mb-1">
              <Lightbulb className="w-3 h-3" /> Curiosity Queue ({data.curiosityQueue.length})
            </div>
            {data.curiosityQueue.slice(0, 3).map((c) => (
              <div key={c.signalId} className="text-[10px] text-gray-400 pl-4">
                {'\u2022'} {c.topic} ({(c.intensity * 100).toFixed(0)}%)
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function TemporalPanel({ data }: { data: SnapshotData['temporal'] }) {
  const uptimeHrs = (data.uptimeMs / 3600000).toFixed(1);
  const avgIntervalMin =
    data.averageOrchestrationInterval > 0
      ? (data.averageOrchestrationInterval / 60000).toFixed(1)
      : '\u2014';

  return (
    <Card title="Temporal Awareness" icon={Clock}>
      <div className="space-y-2 text-xs">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-gray-500">Time:</span>
            <span className="text-[#f5f5f5] ml-1">
              {data.dayOfWeek} {data.timeOfDay}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Business hrs:</span>
            <span className={`ml-1 ${data.isBusinessHours ? 'text-[#c9b787]' : 'text-gray-500'}`}>
              {data.isBusinessHours ? 'Yes' : 'No'}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Uptime:</span>
            <span className="text-[#f5f5f5] ml-1">{uptimeHrs}h</span>
          </div>
          <div>
            <span className="text-gray-500">Orchestrations:</span>
            <span className="text-[#f5f5f5] ml-1">{data.orchestrationCount}</span>
          </div>
        </div>
        <div>
          <span className="text-gray-500">Avg interval:</span>
          <span className="text-[#f5f5f5] ml-1">{avgIntervalMin} min</span>
        </div>
      </div>
    </Card>
  );
}

function WorkspacePanel({ data }: { data: SnapshotData['workspace'] }) {
  return (
    <Card title="GWT Workspace" icon={Compass} accent="cyan">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Session depth:</span>
            <span className="text-[#f5f5f5] ml-1">{data.sessionDepth}</span>
          </div>
          <div>
            <span className="text-gray-500">Context usage:</span>
            <span className="text-[#f5f5f5] ml-1">
              {(data.contextBudget.utilization * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-gray-500">Context Budget</span>
            <span className="text-[#8a8a8a]">
              {data.contextBudget.used}/{data.contextBudget.total}
            </span>
          </div>
          <MiniBar value={data.contextBudget.utilization} color="bg-[#8a8a8a]/60" />
        </div>

        <div>
          <div className="text-[10px] text-gray-500 mb-1">Attention Focus</div>
          <div className="text-[11px] text-[#f5f5f5]">Primary: {data.attentionFocus.primaryTopic}</div>
          {data.attentionFocus.activeDomains.length > 0 && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {data.attentionFocus.activeDomains.slice(0, 5).map((d) => (
                <span
                  key={d}
                  className="px-1.5 py-0.5 text-[9px] bg-[#8a8a8a]/10 text-[#8a8a8a]/70 rounded"
                >
                  {d}
                </span>
              ))}
            </div>
          )}
        </div>

        {data.workingMemory.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 mb-1">
              Working Memory ({data.workingMemory.length} items)
            </div>
            <div className="max-h-20 overflow-y-auto space-y-1">
              {data.workingMemory.slice(0, 4).map((wm) => (
                <div key={wm.id} className="text-[10px] text-gray-400 truncate">
                  [{wm.source}] {wm.content.slice(0, 80)}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function PredictivePanel({ data }: { data: PredictiveState }) {
  const accuracy =
    data.model.totalPredictions > 0
      ? ((data.model.correctPredictions / data.model.totalPredictions) * 100).toFixed(1)
      : '0.0';
  const fe = data.freeEnergy;

  const topDomains = Object.entries(data.routingPriors)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  const surpriseLevelColors: Record<string, string> = {
    expected: 'text-[#c9b787]',
    mild_surprise: 'text-[#c9b787]',
    strong_surprise: 'text-[#c9b787]',
    anomalous: 'text-[#f5f5f5]',
  };

  return (
    <Card title="Predictive Processing" icon={Zap} accent="blue">
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2 text-xs text-center">
          <div>
            <div className="text-lg font-bold text-[#c9b787]">{accuracy}%</div>
            <div className="text-[10px] text-gray-500">Accuracy</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#f5f5f5]">{data.model.totalPredictions}</div>
            <div className="text-[10px] text-gray-500">Predictions</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#c9b787]">
              {fe.currentFreeEnergy.toFixed(2)}
            </div>
            <div className="text-[10px] text-gray-500">Free Energy</div>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-gray-500">Model Complexity</span>
            <span className="text-[#c9b787]">{fe.modelComplexity} params</span>
          </div>
          <MiniBar value={fe.predictionAccuracy} color="bg-[#c9b787]/60" />
        </div>

        {topDomains.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 font-medium mb-1">Routing Priors</div>
            <div className="space-y-1">
              {topDomains.map(([domain, prior]) => (
                <div key={domain} className="flex items-center gap-2 text-[10px]">
                  <span className="text-[#f5f5f5] w-20 truncate">{domain}</span>
                  <div className="flex-1">
                    <MiniBar value={prior} color="bg-[#c9b787]/40" />
                  </div>
                  <span className="text-gray-500 w-8 text-right">{(prior * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.recentErrors.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 font-medium mb-1">
              Recent Prediction Errors
            </div>
            <div className="max-h-20 overflow-y-auto space-y-1">
              {data.recentErrors.slice(0, 4).map((e) => (
                <div
                  key={e.errorId}
                  className="text-[10px] px-2 py-0.5 bg-white/[0.02] rounded flex items-center justify-between"
                >
                  <span className={surpriseLevelColors[e.surpriseLevel] ?? 'text-gray-400'}>
                    {e.surpriseLevel.replace(/_/g, ' ')}
                  </span>
                  <span className="text-gray-500">{(e.errorMagnitude * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function DreamPanel({ data }: { data: DreamState }) {
  const outcomeColors: Record<string, string> = {
    positive: 'text-[#c9b787]',
    negative: 'text-[#f5f5f5]',
    neutral: 'text-gray-400',
  };

  return (
    <Card title="Dream Consolidation" icon={Moon} accent="purple">
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2 text-xs text-center">
          <div>
            <div className="text-lg font-bold text-[#8a8a8a]">{data.totalCycles}</div>
            <div className="text-[10px] text-gray-500">Cycles</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#f5f5f5]">{data.replayBuffer.length}</div>
            <div className="text-[10px] text-gray-500">Replays</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[#c9b787]">{data.discoveredPatterns.length}</div>
            <div className="text-[10px] text-gray-500">Patterns</div>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Status</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[9px] font-medium border ${data.isRunning ? 'bg-[#8a8a8a]/20 text-[#8a8a8a] border-[#8a8a8a]/30' : 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}
          >
            {data.isRunning ? 'DREAMING' : 'AWAKE'}
          </span>
        </div>

        {data.lastCycleTimestamp && (
          <div className="text-[10px] text-gray-500">
            Last cycle: {new Date(data.lastCycleTimestamp).toLocaleTimeString()}
          </div>
        )}

        {data.discoveredPatterns.length > 0 && (
          <div>
            <div className="text-[10px] text-[#8a8a8a] font-medium flex items-center gap-1 mb-1">
              <GitBranch className="w-3 h-3" /> Discovered Patterns
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {data.discoveredPatterns.slice(0, 5).map((p) => {
                const sigColors: Record<string, string> = {
                  high: 'text-[#f5f5f5]',
                  medium: 'text-[#c9b787]',
                  low: 'text-gray-400',
                };
                return (
                  <div key={p.patternId} className="text-[10px] px-2 py-1 bg-white/[0.02] rounded">
                    <div className="flex items-center justify-between">
                      <span className="text-[#f5f5f5] truncate max-w-[120px]">
                        {p.description.slice(0, 50)}
                      </span>
                      <span className={sigColors[p.significance] ?? 'text-gray-400'}>
                        {p.significance}
                      </span>
                    </div>
                    <div className="text-gray-500 truncate">{p.actionableInsight.slice(0, 80)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {data.recentReports.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 font-medium mb-1">Latest Report</div>
            {(() => {
              const r = data.recentReports[0]!;
              return (
                <div className="text-[10px] px-2 py-1 bg-white/[0.02] rounded space-y-0.5">
                  <div className="flex justify-between text-gray-400">
                    <span>Cycle #{r.cycleNumber}</span>
                    <span>
                      {r.replaysProcessed} replays, {r.patternsDiscovered.length} patterns,{' '}
                      {r.memoriesPruned} pruned
                    </span>
                  </div>
                  {r.insightsGenerated.slice(0, 2).map((insight, i) => (
                    <div key={i} className="text-[#8a8a8a]/70 truncate">
                      {'\u2022'} {insight}
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        )}

        {data.replayBuffer.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 font-medium mb-1">Recent Replays</div>
            <div className="max-h-16 overflow-y-auto space-y-0.5">
              {data.replayBuffer
                .slice(-4)
                .reverse()
                .map((r) => (
                  <div
                    key={r.replayId}
                    className="flex items-center justify-between text-[10px] px-2 py-0.5 bg-white/[0.01] rounded"
                  >
                    <span className="text-gray-400 truncate max-w-[160px]">
                      {r.query.slice(0, 40)}
                    </span>
                    <span className={outcomeColors[r.outcome] ?? 'text-gray-400'}>{r.outcome}</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function GWTBroadcastPanel({ data }: { data: SnapshotData['workspace'] }) {
  return (
    <Card title="GWT Broadcast & Attention" icon={Radio} accent="cyan">
      <div className="space-y-2 text-xs">
        <div>
          <span className="text-gray-500">Context Window:</span>
          <span className="text-[#f5f5f5] ml-1">
            {(data.attentionFocus.contextWindowUsage * 100).toFixed(0)}% used
          </span>
        </div>
        <MiniBar value={data.attentionFocus.contextWindowUsage} color="bg-[#8a8a8a]/60" />

        {data.attentionSchema && (
          <div className="space-y-1">
            <div className="text-[10px] text-[#8a8a8a] font-medium">Attention Schema</div>
            {Object.entries(data.attentionSchema.allocationSummary)
              .slice(0, 5)
              .map(([key, val]) => (
                <div key={key} className="flex items-center gap-2 text-[10px]">
                  <span className="text-[#f5f5f5] w-16 truncate">{key}</span>
                  <div className="flex-1">
                    <MiniBar value={val} color="bg-[#8a8a8a]/40" />
                  </div>
                  <span className="text-gray-500 w-8 text-right">{(val * 100).toFixed(0)}%</span>
                </div>
              ))}
            {data.attentionSchema.driftDetected && (
              <div className="text-[9px] text-[#c9b787] flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />{' '}
                {data.attentionSchema.driftDescription ?? 'Drift detected'}
              </div>
            )}
            {data.attentionSchema.rebalanceRecommendation && (
              <div className="text-[9px] text-[#8a8a8a]/70">
                {data.attentionSchema.rebalanceRecommendation.slice(0, 80)}
              </div>
            )}
          </div>
        )}

        {data.recentBroadcasts && data.recentBroadcasts.length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 font-medium">
              Recent Broadcasts ({data.recentBroadcasts.length})
            </div>
            <div className="max-h-24 overflow-y-auto space-y-1">
              {data.recentBroadcasts.slice(0, 3).map((b) => (
                <div key={b.broadcastId} className="text-[10px] px-2 py-1 bg-white/[0.02] rounded">
                  <div className="flex gap-1 mb-0.5">
                    {b.winners.slice(0, 2).map((w) => (
                      <span
                        key={w.itemId}
                        className="px-1 py-0.5 text-[9px] bg-[#c9b787]/10 text-[#c9b787]/80 rounded truncate max-w-[100px]"
                      >
                        {w.content.slice(0, 30)}
                      </span>
                    ))}
                  </div>
                  {b.losers.length > 0 && (
                    <div className="text-[9px] text-gray-600">
                      {b.losers.length} items below threshold
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.attentionFocus.activeDomains.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 mb-1">Active Domains</div>
            <div className="flex gap-1 flex-wrap">
              {data.attentionFocus.activeDomains.map((d) => (
                <span
                  key={d}
                  className="px-1.5 py-0.5 text-[9px] bg-[#8a8a8a]/15 text-[#8a8a8a] border border-[#8a8a8a]/20 rounded"
                >
                  {d}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

export default function ConsciousnessPage() {
  const { data, isLoading, error } = useCSnapshot();

  return (
    <div className="space-y-6">
      <m.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-500/20 to-purple-500/20 flex items-center justify-center border border-[#f5f5f5]/20">
            <Sparkles className="w-5 h-5 text-[#f5f5f5]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#f5f5f5]">Consciousness Layer v2</h1>
            <p className="text-xs text-gray-500">
              GWT, Predictive Processing, Dialectical Reasoning, Appraisal Theory, Dream
              Consolidation
            </p>
          </div>
        </div>
        {data?.timestamp && (
          <div className="text-[10px] text-gray-600">
            Last snapshot: {new Date(data.timestamp).toLocaleTimeString()}
          </div>
        )}
      </m.div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Activity className="w-6 h-6 text-[#f5f5f5]/40 animate-pulse" />
        </div>
      )}

      {error && (
        <div className="text-center py-10 text-[#f5f5f5]/60 text-sm">
          Unable to connect to consciousness layer
        </div>
      )}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <MetacognitionPanel data={data.metacognition} />
            <SelfModelPanel data={data.selfModel} />
            <EmotionalPanel data={data.emotions} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <PredictivePanel data={data.predictive} />
            <DreamPanel data={data.dream} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <MonologuePanel data={data.monologue} />
            <GoalPanel data={data.goals} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <WorkspacePanel data={data.workspace} />
            <GWTBroadcastPanel data={data.workspace} />
            <TemporalPanel data={data.temporal} />
          </div>
        </div>
      )}
    </div>
  );
}
