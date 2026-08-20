import { cn } from '@szl-holdings/shared-ui/utils';
import {
  AlertTriangle,
  Bot,
  ChevronRight,
  Clock,
  Download,
  Flame,
  Globe,
  Loader2,
  Radio,
  Shield,
  Swords,
  Trophy,
  Users,
  X,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'wouter';
import {
  calculateLetterGrade,
  CRISIS_SCENARIOS as fallbackScenarios,
  type CrisisScenario,
  getGradeColor,
  SCENARIO_CATEGORY_LABELS,
  THREAT_ACTOR_LABELS,
  type DecisionOption,
  type DecisionPoint,
  type DecisionQuality,
  type Phase,
  type SimulationRecord,
} from '@/data/crisis-scenarios';
import { listCrisisScenarios } from '@/lib/sentra-api';
import { useApiQuery } from '@/lib/use-api-query';

type SimState = 'briefing' | 'running' | 'decision' | 'inject' | 'complete';

interface DecisionResult {
  decisionPointId: string;
  selectedOption: DecisionOption;
  timestampSec: number;
  quality: DecisionQuality;
}

function GradeDisplay({ grade }: { grade: SimulationRecord['letterGrade'] }) {
  const color = getGradeColor(grade);
  return (
    <span className="text-4xl font-display font-bold" style={{ color }}>
      {grade}
    </span>
  );
}

function PressureBar({ pct, label }: { pct: number; label: string }) {
  const color = pct > 0.7 ? '#ef4444' : pct > 0.4 ? '#c9b787' : '#4ade80';
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] font-mono text-slate-500 uppercase w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct * 100}%`, background: color }} />
      </div>
      <span className="text-[9px] font-mono text-slate-400 w-8 text-right">{Math.round(pct * 100)}%</span>
    </div>
  );
}

export default function CrisisSimulatorRun() {
  const params = useParams();
  const scenarioId = params.id as string;
  const scenarioFetcher = useCallback(() => listCrisisScenarios(), []);
  const { data: apiScenarios } = useApiQuery<CrisisScenario[]>(scenarioFetcher, 'scenarios', fallbackScenarios);
  const apiMatch = apiScenarios.find((s) => s.id === scenarioId);
  const hasFullPhases = apiMatch?.phases?.[0] && 'decisionPoints' in apiMatch.phases[0];
  const scenario = (hasFullPhases ? apiMatch : null) ?? fallbackScenarios.find((s) => s.id === scenarioId);

  const [simState, setSimState] = useState<SimState>('briefing');
  const [currentPhaseIdx, setCurrentPhaseIdx] = useState(0);
  const [currentDecisionIdx, setCurrentDecisionIdx] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [phaseStartSec, setPhaseStartSec] = useState(0);
  const [decisionTimerSec, setDecisionTimerSec] = useState(0);
  const [results, setResults] = useState<DecisionResult[]>([]);
  const [totalScore, setTotalScore] = useState(0);
  const [activeInjectIdx, setActiveInjectIdx] = useState<number | null>(null);
  const [pendingInjectIdx, setPendingInjectIdx] = useState<number | null>(null);
  const [shownInjectIds, setShownInjectIds] = useState<Set<string>>(new Set());
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [aiCoaching, setAiCoaching] = useState<string | null>(null);
  const [showCoaching, setShowCoaching] = useState(false);
  const [lastSelectedOption, setLastSelectedOption] = useState<DecisionOption | null>(null);
  const [preInjectState, setPreInjectState] = useState<SimState>('running');

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const decisionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const savedRecordRef = useRef(false);

  const currentPhase: Phase | undefined = scenario?.phases[currentPhaseIdx];
  const currentDecision: DecisionPoint | undefined = currentPhase?.decisionPoints[currentDecisionIdx];

  const maxScore = scenario?.phases.reduce((acc, ph) =>
    acc + ph.decisionPoints.reduce((a, dp) =>
      a + Math.max(...dp.options.map((o) => o.scoreDelta)), 0), 0) ?? 0;

  const letterGrade = calculateLetterGrade(totalScore, maxScore);

  useEffect(() => {
    if (simState === 'running' || simState === 'decision') {
      timerRef.current = setInterval(() => {
        setElapsedSec((s) => s + 1);
      }, 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [simState]);

  useEffect(() => {
    if ((simState !== 'running' && simState !== 'decision') || !currentPhase) return;
    const phaseElapsed = elapsedSec - phaseStartSec;
    const injects = currentPhase.injects;
    injects.forEach((inj, idx) => {
      if (phaseElapsed >= inj.at_second && !shownInjectIds.has(inj.id)) {
        setPendingInjectIdx(idx);
      }
    });
    if (simState === 'running') {
      const dps = currentPhase.decisionPoints;
      if (dps.length > 0 && currentDecisionIdx < dps.length) {
        const dp = dps[currentDecisionIdx];
        if (phaseElapsed > 10) {
          setSimState('decision');
          setDecisionTimerSec(dp.timeLimitSec);
        }
      }
    }
  }, [elapsedSec, phaseStartSec, simState, currentPhase, currentDecisionIdx, shownInjectIds]);

  useEffect(() => {
    if (pendingInjectIdx !== null && (simState === 'running' || simState === 'decision')) {
      const inj = currentPhase?.injects[pendingInjectIdx];
      if (inj) {
        setShownInjectIds((prev) => new Set([...prev, inj.id]));
        setPendingInjectIdx(null);
        setActiveInjectIdx(pendingInjectIdx);
        setPreInjectState(simState);
        setSimState('inject');
        if (timerRef.current) clearInterval(timerRef.current);
        if (decisionTimerRef.current) clearInterval(decisionTimerRef.current);
      }
    }
  }, [pendingInjectIdx, simState, currentPhase]);

  useEffect(() => {
    if (simState !== 'decision' || !currentDecision) return;
    if (decisionTimerSec <= 0) {
      handleAutoTimeout();
      return;
    }
    decisionTimerRef.current = setInterval(() => {
      setDecisionTimerSec((t) => t - 1);
    }, 1000);
    return () => { if (decisionTimerRef.current) clearInterval(decisionTimerRef.current); };
  }, [simState, decisionTimerSec, currentDecision]);

  useEffect(() => {
    if (simState !== 'complete' || savedRecordRef.current || !scenario) return;
    savedRecordRef.current = true;
    const grade = calculateLetterGrade(totalScore, maxScore);
    try {
      const stored: SimulationRecord[] = JSON.parse(localStorage.getItem('sentra_sim_records') ?? '[]');
      stored.push({
        scenarioId: scenario.id,
        startedAt: new Date(Date.now() - elapsedSec * 1000).toISOString(),
        completedAt: new Date().toISOString(),
        decisions: results.map((r) => ({
          decisionPointId: r.decisionPointId,
          selectedOptionId: r.selectedOption.id,
          timestampSec: r.timestampSec,
          quality: r.quality,
          scoreDelta: r.selectedOption.scoreDelta,
        })),
        totalScore,
        maxScore,
        letterGrade: grade,
        completed: true,
      });
      localStorage.setItem('sentra_sim_records', JSON.stringify(stored.slice(-50)));
    } catch {}
  }, [simState, scenario, totalScore, maxScore, elapsedSec, results]);

  function handleAutoTimeout() {
    if (!currentDecision) return;
    const worst = currentDecision.options.reduce((min, o) =>
      o.scoreDelta < min.scoreDelta ? o : min, currentDecision.options[0]);
    submitDecision(worst.id, true);
  }

  function startSimulation() {
    setSimState('running');
    setElapsedSec(0);
    setSelectedRole(scenario?.roles[0] ?? null);
  }

  function dismissInject() {
    setActiveInjectIdx(null);
    setSimState(preInjectState);
  }

  function submitDecision(optionId: string, isTimeout = false) {
    if (!currentDecision || !currentPhase) return;
    if (decisionTimerRef.current) clearInterval(decisionTimerRef.current);
    const opt = currentDecision.options.find((o) => o.id === optionId)!;
    const result: DecisionResult = {
      decisionPointId: currentDecision.id,
      selectedOption: opt,
      timestampSec: elapsedSec,
      quality: isTimeout ? 'harmful' : opt.quality,
    };
    setResults((r) => [...r, result]);
    setTotalScore((s) => s + (isTimeout ? Math.min(...currentDecision.options.map((o) => o.scoreDelta)) : opt.scoreDelta));
    setSelectedOption(optionId);
    setLastSelectedOption(opt);

    const coaching = isTimeout
      ? `⏱ Time expired. Delayed decisions in real crises create compounding damage. The optimal response was: "${currentDecision.options.find(o => o.quality === 'optimal')?.label}".`
      : opt.quality === 'optimal'
        ? `✓ Optimal decision. ${opt.consequence}`
        : opt.quality === 'suboptimal'
          ? `⚠ Suboptimal. ${opt.consequence} The optimal path: "${currentDecision.options.find(o => o.quality === 'optimal')?.label}"`
          : `✗ Harmful decision. ${opt.consequence} This choice significantly degrades your resilience score.`;
    setAiCoaching(coaching);
    setShowCoaching(true);
  }

  function advanceAfterDecision() {
    if (!currentPhase || !scenario) return;
    setShowCoaching(false);
    setSelectedOption(null);
    const nextDecisionIdx = currentDecisionIdx + 1;
    if (nextDecisionIdx < currentPhase.decisionPoints.length) {
      setCurrentDecisionIdx(nextDecisionIdx);
      setSimState('running');
    } else {
      let nextPhaseIdx = currentPhaseIdx + 1;
      if (lastSelectedOption?.nextPhaseId) {
        const branchIdx = scenario.phases.findIndex((p) => p.id === lastSelectedOption.nextPhaseId);
        if (branchIdx !== -1) nextPhaseIdx = branchIdx;
      }
      if (nextPhaseIdx < scenario.phases.length) {
        setCurrentPhaseIdx(nextPhaseIdx);
        setCurrentDecisionIdx(0);
        setPhaseStartSec(elapsedSec);
        setSimState('running');
      } else {
        setSimState('complete');
        if (timerRef.current) clearInterval(timerRef.current);
      }
    }
  }

  if (!scenario) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-10 text-center">
        <AlertTriangle className="w-10 h-10 text-red-400 mb-4" />
        <h2 className="text-xl font-bold text-slate-100 mb-2">Scenario Not Found</h2>
        <Link href="/crisis-simulator">
          <button className="text-xs text-slate-400 underline">Back to Simulator</button>
        </Link>
      </div>
    );
  }

  const formatTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  const pressureLevel = Math.min(1, elapsedSec / (scenario.estimatedMinutes * 60));

  if (simState === 'complete') {
    const grade = calculateLetterGrade(totalScore, maxScore);
    const gradeColor = getGradeColor(grade);
    const optimalCount = results.filter((r) => r.quality === 'optimal').length;
    const harmfulCount = results.filter((r) => r.quality === 'harmful').length;
    const complianceGaps = results.flatMap((r) => r.selectedOption.regComplianceImpact ? [r.selectedOption.regComplianceImpact] : []);
    const mttrMinutes = Math.max(1, Math.round(elapsedSec / 60));
    const industryMttrMinutes = 45;
    const mttrDelta = mttrMinutes - industryMttrMinutes;

    const tacticGroups: Record<string, typeof scenario.mitreTags> = {};
    scenario.mitreTags.forEach((tag) => {
      if (!tacticGroups[tag.tactic]) tacticGroups[tag.tactic] = [];
      tacticGroups[tag.tactic].push(tag);
    });

    function downloadReport() {
      const report = {
        scenario: { id: scenario.id, title: scenario.title, subtitle: scenario.subtitle, threatActor: scenario.threatActor },
        completedAt: new Date().toISOString(),
        grade,
        totalScore,
        maxScore,
        mttrMinutes,
        decisionSummary: {
          total: results.length,
          optimal: optimalCount,
          suboptimal: results.filter((r) => r.quality === 'suboptimal').length,
          harmful: harmfulCount,
        },
        decisions: results.map((r) => ({
          decisionPointId: r.decisionPointId,
          decision: r.selectedOption.label,
          quality: r.quality,
          consequence: r.selectedOption.consequence,
          regComplianceImpact: r.selectedOption.regComplianceImpact ?? null,
          scoreDelta: r.selectedOption.scoreDelta,
          timestampSec: r.timestampSec,
        })),
        complianceGaps,
        mitreTechniques: scenario.mitreTags,
        aiCoachSummary: grade === 'AAA' || grade === 'AA' || grade === 'A'
          ? 'Exceptional performance — 84th percentile or above.'
          : grade === 'BBB' || grade === 'BB'
          ? 'Solid response with decision latency improvement opportunities.'
          : 'Significant gaps — immediate tabletop follow-up recommended.',
        sourceRef: scenario.sourceRef,
      };
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sentra-exercise-${scenario.id}-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }

    return (
      <div className="space-y-6 animate-fade-in">
        <header className="flex items-center justify-between gap-3">
          <Link href="/crisis-simulator">
            <button className="text-xs text-slate-500 hover:text-slate-300 transition-colors">← Back to Simulator</button>
          </Link>
          <button
            onClick={downloadReport}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Download Report
          </button>
        </header>

        <div className="sentra-panel p-8 text-center space-y-6">
          <Trophy className="w-12 h-12 mx-auto" style={{ color: gradeColor }} />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Post-Exercise Scorecard</div>
            <h1 className="text-2xl font-display font-bold text-slate-100 mb-1">{scenario.title}</h1>
            <p className="text-slate-400 text-sm">{scenario.subtitle}</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="text-center">
              <GradeDisplay grade={grade} />
              <div className="text-[10px] font-mono text-slate-500 mt-1">Resilience Grade</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-display font-bold text-slate-100">{totalScore >= 0 ? '+' : ''}{totalScore}</div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">Score / {maxScore} pts</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-display font-bold text-slate-100">{formatTime(elapsedSec)}</div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">Total Time</div>
            </div>
            <div className="text-center">
              <div className={cn('text-3xl font-display font-bold', mttrDelta <= 0 ? 'text-emerald-400' : 'text-amber-400')}>
                {mttrMinutes}m
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">
                MTTR ({mttrDelta <= 0 ? `${Math.abs(mttrDelta)}m better` : `${mttrDelta}m vs avg`})
              </div>
            </div>
          </div>
          <div className="flex justify-center gap-6 pt-2">
            {[
              { label: 'Optimal', count: optimalCount, color: '#4ade80' },
              { label: 'Suboptimal', count: results.filter(r => r.quality === 'suboptimal').length, color: '#c9b787' },
              { label: 'Harmful', count: harmfulCount, color: '#ef4444' },
            ].map((item) => (
              <div key={item.label} className="text-center">
                <div className="text-xl font-mono font-bold" style={{ color: item.color }}>{item.count}</div>
                <div className="text-[9px] font-mono text-slate-500 uppercase">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {complianceGaps.length > 0 && (
          <div className="sentra-panel p-5 border-amber-500/20" style={{ borderColor: 'rgba(251,191,36,0.15)' }}>
            <h2 className="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-400" />
              Compliance Gap Synthesis
            </h2>
            <div className="space-y-2">
              {complianceGaps.map((gap, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-amber-300 leading-relaxed">
                  <span className="text-amber-500 font-mono mt-0.5">⚖</span>
                  <span>{gap}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-3">
          <h2 className="text-sm font-bold text-slate-200">Decision Timeline</h2>
          {results.map((r, i) => {
            const qualColor = r.quality === 'optimal' ? '#4ade80' : r.quality === 'suboptimal' ? '#c9b787' : '#ef4444';
            return (
              <div key={i} className="sentra-panel p-4">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{ background: qualColor }} />
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-xs font-bold text-slate-200">{r.selectedOption.label}</span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase" style={{ color: qualColor, borderColor: qualColor + '40', background: qualColor + '15' }}>
                        {r.quality}
                      </span>
                      <span className="text-[9px] font-mono text-slate-500 ml-auto">T+{formatTime(r.timestampSec)}</span>
                    </div>
                    <p className="text-[11px] text-slate-500">{r.selectedOption.consequence}</p>
                    {r.selectedOption.regComplianceImpact && (
                      <div className="mt-2 px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-[10px] text-amber-400 font-mono">
                        ⚖ {r.selectedOption.regComplianceImpact}
                      </div>
                    )}
                    <div className="text-[9px] font-mono text-slate-600 mt-1">
                      Score: {r.selectedOption.scoreDelta >= 0 ? '+' : ''}{r.selectedOption.scoreDelta} pts
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="sentra-panel p-5">
          <h2 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
            <Swords className="w-4 h-4 text-red-400" />
            MITRE ATT&CK Coverage Heatmap
          </h2>
          <div className="space-y-4">
            {Object.entries(tacticGroups).map(([tactic, tags]) => (
              <div key={tactic}>
                <div className="text-[9px] font-mono uppercase text-slate-500 mb-2 tracking-wider">{tactic}</div>
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <div key={tag.id} className="px-3 py-2 rounded-lg border"
                      style={{ background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.25)' }}>
                      <div className="text-[10px] font-mono text-red-400 font-bold">{tag.id}</div>
                      <div className="text-[10px] text-slate-300">{tag.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="sentra-panel p-5 border-[#c9b787]/20" style={{ borderColor: 'rgba(201,183,135,0.15)' }}>
          <div className="flex items-start gap-3">
            <Bot className="w-5 h-5 text-[#c9b787] shrink-0 mt-0.5" />
            <div>
              <div className="text-[10px] font-mono uppercase text-[#c9b787] mb-2">Sentient Layer · AI Coach Recommendations</div>
              <div className="space-y-2 text-xs text-slate-400 leading-relaxed">
                {grade === 'AAA' || grade === 'AA' || grade === 'A' ? (
                  <p>Exceptional performance. Your decision speed and quality exceeded the 84th percentile benchmark. MTTR of {mttrMinutes} minutes is {mttrDelta <= 0 ? `${Math.abs(mttrDelta)} minutes better than` : `${mttrDelta} minutes above`} the industry average of {industryMttrMinutes} minutes. Key strength: regulatory compliance integration in crisis decisions.</p>
                ) : grade === 'BBB' || grade === 'BB' ? (
                  <p>Solid operational response with room for improvement. Focus area: reduce decision latency in the first 90 seconds — industry data shows each minute of delay in initial containment increases breach cost by $7,500 on average. MTTR of {mttrMinutes} minutes versus {industryMttrMinutes} minute industry average. Consider tabletop drills focused on the escalation phase.</p>
                ) : (
                  <p>Significant gaps identified. Critical failure points were in initial containment decisions and regulatory notification timing. MTTR of {mttrMinutes} minutes is {mttrDelta > 0 ? `${mttrDelta} minutes above` : 'at'} industry average. Recommend immediate tabletop exercises focusing on the first 30-minute response window. {complianceGaps.length > 0 ? `${complianceGaps.length} compliance gap${complianceGaps.length > 1 ? 's' : ''} identified — engage outside counsel before next exercise.` : ''}</p>
                )}
                <p className="text-slate-600">Source: CISA Tabletop Exercise Package recommendations · IBM Cost of a Data Breach Report 2024 · Ponemon Institute breach timing analysis</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <Link href="/crisis-simulator">
            <button className="px-4 py-2 rounded-lg text-xs font-semibold border border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300 transition-colors">
              Back to Scenario Library
            </button>
          </Link>
          <Link href="/resilience-leaderboard">
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors"
              style={{ background: 'rgba(201,183,135,0.08)', border: '1px solid rgba(201,183,135,0.20)', color: '#c9b787' }}>
              <Trophy className="w-3.5 h-3.5" />
              View Resilience Leaderboard
            </button>
          </Link>
        </div>
      </div>
    );
  }

  if (simState === 'briefing') {
    return (
      <div className="space-y-6 animate-fade-in max-w-3xl">
        <Link href="/crisis-simulator">
          <button className="text-xs text-slate-500 hover:text-slate-300 transition-colors">← Back to Simulator</button>
        </Link>

        <div className="sentra-panel p-6 border-red-500/20" style={{ borderColor: 'rgba(239,68,68,0.15)' }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-red-400">MISSION BRIEFING · CLASSIFIED</span>
          </div>
          <h1 className="text-2xl font-display font-bold text-slate-100 mb-1">{scenario.title}</h1>
          <p className="text-slate-400 text-sm mb-6">{scenario.subtitle}</p>

          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Threat Actor Profile</div>
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-700/60">
                <div className="flex items-center gap-2 mb-2">
                  <Flame className="w-4 h-4 text-red-400" />
                  <span className="text-xs font-bold text-red-400">{THREAT_ACTOR_LABELS[scenario.threatActor]}</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{scenario.adversaryProfile}</p>
              </div>
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Situation Brief</div>
              <p className="text-sm text-slate-300 leading-relaxed">{scenario.background}</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Category', value: SCENARIO_CATEGORY_LABELS[scenario.category] },
                { label: 'Difficulty', value: scenario.difficulty },
                { label: 'Est. Duration', value: `${scenario.estimatedMinutes} min` },
                { label: 'Phases', value: `${scenario.phases.length}` },
              ].map((item) => (
                <div key={item.label} className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 text-center">
                  <div className="text-[9px] font-mono uppercase text-slate-500 mb-1">{item.label}</div>
                  <div className="text-sm font-bold text-slate-200">{item.value}</div>
                </div>
              ))}
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Your Roles</div>
              <div className="flex gap-2 flex-wrap">
                {scenario.roles.map((role) => (
                  <span key={role} className="px-3 py-1 rounded text-xs font-bold"
                    style={{ background: 'rgba(245,245,245,0.08)', border: '1px solid rgba(245,245,245,0.15)', color: '#f5f5f5' }}>
                    {role}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Source References</div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                <Globe className="w-3 h-3" />
                {scenario.sourceRef}
              </div>
            </div>
          </div>
        </div>

        <div className="sentra-panel p-4 border-[#c9b787]/20" style={{ borderColor: 'rgba(201,183,135,0.15)' }}>
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-[#c9b787]" />
            <span className="text-[10px] font-mono text-[#c9b787] uppercase">Sentient Layer · AI Coaching enabled for this simulation</span>
          </div>
        </div>

        <button
          onClick={startSimulation}
          className="flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-bold transition-colors"
          style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.30)', color: '#ef4444' }}
        >
          <Zap className="w-4 h-4" />
          Begin Simulation
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  if (simState === 'inject' && activeInjectIdx !== null && currentPhase) {
    const inject = currentPhase.injects[activeInjectIdx];
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
        <div className="w-full max-w-lg rounded-xl border shadow-2xl animate-fade-in"
          style={{ background: '#0a0a0f', borderColor: 'rgba(239,68,68,0.40)' }}>
          <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'rgba(239,68,68,0.20)' }}>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-[10px] font-mono uppercase tracking-widest text-red-400">INCOMING INTEL INJECT</span>
            </div>
            {inject.role && (
              <span className="text-[9px] font-mono px-2 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10">
                {inject.role}
              </span>
            )}
          </div>
          <div className="p-6 space-y-3">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-red-400" />
              <h3 className="text-sm font-bold text-red-400">{inject.title}</h3>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">{inject.body}</p>
          </div>
          <div className="p-4 border-t flex justify-end" style={{ borderColor: 'rgba(239,68,68,0.20)' }}>
            <button
              onClick={dismissInject}
              className="flex items-center gap-2 px-4 py-2 rounded text-xs font-bold transition-colors"
              style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.30)', color: '#ef4444' }}
            >
              Acknowledged <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between gap-4 p-4 rounded-lg border" style={{ background: 'rgba(10,10,15,0.8)', borderColor: 'rgba(239,68,68,0.20)' }}>
        <div className="flex items-center gap-4">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <div>
            <div className="text-[9px] font-mono uppercase text-red-400">SIMULATION ACTIVE</div>
            <div className="text-xs font-bold text-slate-200">{scenario.title}</div>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="text-xl font-display font-mono text-red-400">{formatTime(elapsedSec)}</div>
            <div className="text-[8px] font-mono text-slate-500 uppercase">Elapsed</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-display font-mono text-slate-100">
              {totalScore >= 0 ? '+' : ''}{totalScore}
            </div>
            <div className="text-[8px] font-mono text-slate-500 uppercase">Score</div>
          </div>
          <div className="text-center">
            <GradeDisplay grade={letterGrade} />
            <div className="text-[8px] font-mono text-slate-500 uppercase">Grade</div>
          </div>
        </div>
        <Link href="/crisis-simulator">
          <button className="text-slate-600 hover:text-slate-400 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </Link>
      </div>

      <div className="sentra-panel p-4">
        <div className="text-[9px] font-mono uppercase text-slate-500 mb-3">Pressure Indicators</div>
        <div className="space-y-2">
          <PressureBar pct={pressureLevel} label="Time Pressure" />
          <PressureBar pct={Math.min(1, elapsedSec / 300)} label="Threat Escalation" />
          <PressureBar pct={results.filter((r) => r.quality === 'harmful').length / Math.max(1, results.length)} label="Error Rate" />
        </div>
      </div>

      <div className="sentra-panel p-4">
        <div className="flex items-center gap-2 mb-2">
          <Users className="w-3 h-3 text-slate-500" />
          <div className="text-[9px] font-mono uppercase text-slate-500">Active Role</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {scenario.roles.map((role) => (
            <button
              key={role}
              onClick={() => setSelectedRole(role)}
              className={cn(
                'px-3 py-1.5 rounded text-xs font-bold border transition-all',
                selectedRole === role
                  ? 'border-[#c9b787]/50 bg-[#c9b787]/15 text-[#c9b787]'
                  : 'border-slate-700 bg-slate-800/40 text-slate-500 hover:border-slate-600 hover:text-slate-400'
              )}
            >
              {role}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {scenario.phases.map((ph, i) => (
          <div
            key={ph.id}
            className={cn('p-2 rounded border text-center', i < currentPhaseIdx ? 'border-emerald-500/30 bg-emerald-500/10' : i === currentPhaseIdx ? 'border-red-500/40 bg-red-500/10' : 'border-slate-700 bg-slate-800/30')}
          >
            <div className={cn('text-[9px] font-mono uppercase', i < currentPhaseIdx ? 'text-emerald-400' : i === currentPhaseIdx ? 'text-red-400' : 'text-slate-600')}>
              Phase {ph.order}
            </div>
            <div className="text-[10px] text-slate-400 truncate">{ph.title.split(' ')[0]}</div>
          </div>
        ))}
      </div>

      {currentPhase && (
        <div className="sentra-panel p-5">
          <div className="flex items-center gap-2 mb-3">
            <Radio className="w-4 h-4 text-red-400" />
            <span className="text-[10px] font-mono uppercase text-red-400 font-bold">Phase {currentPhase.order}: {currentPhase.title}</span>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">{currentPhase.description}</p>
        </div>
      )}

      {simState === 'decision' && currentDecision && (
        <div className="sentra-panel p-6 border-[#c9b787]/30" style={{ borderColor: 'rgba(201,183,135,0.25)' }}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[9px] font-mono px-2 py-0.5 rounded border text-[#c9b787] border-[#c9b787]/30 bg-[#c9b787]/10 uppercase font-bold">
                  {currentDecision.role}
                </span>
                <span className="text-[9px] font-mono text-slate-500">Decision Point</span>
              </div>
              <h3 className="text-sm font-bold text-slate-100 leading-relaxed">{currentDecision.question}</h3>
            </div>
            <div className="shrink-0 text-center">
              <div className={cn('text-2xl font-display font-mono font-bold', decisionTimerSec < 15 ? 'text-red-400' : 'text-[#c9b787]')}>
                {formatTime(decisionTimerSec)}
              </div>
              <div className="text-[8px] font-mono text-slate-500 uppercase">
                <Clock className="w-2.5 h-2.5 inline mr-0.5" />
                Time Limit
              </div>
            </div>
          </div>
          <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 mb-5">
            <p className="text-xs text-slate-400 leading-relaxed">{currentDecision.context}</p>
          </div>
          <div className="space-y-3">
            {currentDecision.options.map((opt) => (
              <button
                key={opt.id}
                disabled={selectedOption !== null}
                onClick={() => submitDecision(opt.id)}
                className={cn(
                  'w-full text-left p-4 rounded-lg border transition-all',
                  selectedOption === opt.id
                    ? opt.quality === 'optimal' ? 'border-emerald-500/50 bg-emerald-500/10' : opt.quality === 'suboptimal' ? 'border-[#c9b787]/50 bg-[#c9b787]/10' : 'border-red-500/50 bg-red-500/10'
                    : selectedOption !== null ? 'border-slate-700/50 bg-slate-800/20 opacity-40' : 'border-slate-700 bg-slate-800/40 hover:border-slate-500 hover:bg-slate-700/50',
                )}
              >
                <div className="text-xs font-bold text-slate-200 mb-1">{opt.label}</div>
                <div className="text-[11px] text-slate-500">{opt.description}</div>
              </button>
            ))}
          </div>

          {showCoaching && aiCoaching && (
            <div className="mt-5 p-4 rounded-lg border" style={{ background: 'rgba(201,183,135,0.05)', borderColor: 'rgba(201,183,135,0.20)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-3.5 h-3.5 text-[#c9b787]" />
                <span className="text-[9px] font-mono uppercase text-[#c9b787]">Sentient Layer · AI Coach</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{aiCoaching}</p>
              <button
                onClick={advanceAfterDecision}
                className="mt-3 flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-bold transition-colors"
                style={{ background: 'rgba(245,245,245,0.08)', border: '1px solid rgba(245,245,245,0.15)', color: '#f5f5f5' }}
              >
                Continue <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>
      )}

      {simState === 'running' && (
        <div className="sentra-panel p-5 flex items-center gap-4">
          <Loader2 className="w-4 h-4 text-red-400 animate-spin" />
          <div>
            <div className="text-xs text-slate-300 font-bold">Simulation in progress…</div>
            <div className="text-[10px] text-slate-500">Monitoring for threat escalation and incoming intelligence injects.</div>
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className="sentra-panel p-4">
          <div className="text-[10px] font-mono uppercase text-slate-500 mb-3">Decisions Made So Far</div>
          <div className="space-y-2">
            {results.map((r, i) => {
              const qualColor = r.quality === 'optimal' ? '#4ade80' : r.quality === 'suboptimal' ? '#c9b787' : '#ef4444';
              return (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: qualColor }} />
                  <span className="text-slate-400 flex-1 truncate">{r.selectedOption.label}</span>
                  <span className="font-mono text-[10px]" style={{ color: qualColor }}>
                    {r.quality}
                  </span>
                  <span className="font-mono text-[10px] text-slate-500">
                    {r.selectedOption.scoreDelta >= 0 ? '+' : ''}{r.selectedOption.scoreDelta}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
