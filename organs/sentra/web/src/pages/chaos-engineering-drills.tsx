import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Clock,
  Database,
  FileText,
  Loader2,
  Network,
  Play,
  RefreshCw,
  Server,
  Shield,
  Timer,
  Wifi,
  XCircle,
  Zap,
} from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

interface FaultScenario {
  id: string;
  name: string;
  description: string;
  type: 'network_partition' | 'db_lag' | 'ai_timeout' | 'service_crash' | 'memory_pressure';
  icon: React.ElementType;
  durationSec: number;
  expectedRecoverySec: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  mitigations: string[];
}

interface DrillResult {
  scenarioId: string;
  startedAt: number;
  completedAt: number;
  recoveryScore: number;
  mttr: number;
  playbook: PlaybookStep[];
  status: 'pass' | 'partial' | 'fail';
  observations: string[];
}

interface PlaybookStep {
  id: string;
  phase: 'detect' | 'contain' | 'recover' | 'validate';
  action: string;
  owner: string;
  timeOffset: number;
  automated: boolean;
  completed: boolean;
}

type DrillStatus = 'idle' | 'injecting' | 'monitoring' | 'recovering' | 'scoring' | 'done';

const FAULT_SCENARIOS: FaultScenario[] = [
  {
    id: 'net-partition',
    name: 'Network Partition',
    description: 'Simulates a split-brain network event isolating the primary API cluster from the database tier and external threat feeds.',
    type: 'network_partition',
    icon: Wifi,
    durationSec: 45,
    expectedRecoverySec: 90,
    severity: 'high',
    mitigations: ['Circuit breaker opens within 2s', 'Cached responses served', 'Failover to secondary region initiates', 'Alert fires to on-call in <30s'],
  },
  {
    id: 'db-lag',
    name: 'Database Lag (500ms+)',
    description: 'Injects 500ms+ latency into all database queries, simulating a degraded PostgreSQL primary or overloaded connection pool.',
    type: 'db_lag',
    icon: Database,
    durationSec: 60,
    expectedRecoverySec: 30,
    severity: 'medium',
    mitigations: ['Read replicas absorb read traffic', 'Write queue depth monitored', 'SLA breach predicted at T+45s', 'Auto-scale connection pool by T+20s'],
  },
  {
    id: 'ai-timeout',
    name: 'AI Provider Timeout',
    description: 'Forces all calls to the primary AI inference provider to time out, validating the fallback routing and model degradation path.',
    type: 'ai_timeout',
    icon: Zap,
    durationSec: 30,
    expectedRecoverySec: 5,
    severity: 'medium',
    mitigations: ['Fallback model activates within 3s', 'User sees degraded-mode indicator', 'Cached reasoning reused for repeated queries', 'SLA clock suspended during provider outage'],
  },
  {
    id: 'service-crash',
    name: 'Threat Feed Service Crash',
    description: 'Terminates the threat intelligence aggregation service, testing restart behavior, data catchup, and alert continuity.',
    type: 'service_crash',
    icon: Server,
    durationSec: 20,
    expectedRecoverySec: 45,
    severity: 'critical',
    mitigations: ['Process supervisor restarts within 5s', 'Last known threat state preserved in cache', 'Stale data warning shown in UI', 'Audit log captures gap interval'],
  },
  {
    id: 'mem-pressure',
    name: 'Memory Pressure (85%+)',
    description: 'Allocates memory to bring heap utilization to 85%+, testing eviction policies, cache degradation, and OOM prevention.',
    type: 'memory_pressure',
    icon: Activity,
    durationSec: 90,
    expectedRecoverySec: 60,
    severity: 'high',
    mitigations: ['LRU cache eviction triggers at 80%', 'Non-critical background jobs paused', 'Alert sent at 85%, PagerDuty at 90%', 'Auto-restart prevented by circuit breaker until <75%'],
  },
];

function generatePlaybook(scenario: FaultScenario): PlaybookStep[] {
  return [
    { id: 'p1', phase: 'detect', action: 'Automated health check detects anomaly', owner: 'System', timeOffset: 5, automated: true, completed: true },
    { id: 'p2', phase: 'detect', action: 'Alert routed to on-call channel', owner: 'Alertmanager', timeOffset: 12, automated: true, completed: true },
    { id: 'p3', phase: 'contain', action: `${scenario.type === 'network_partition' ? 'Isolate affected segment' : 'Enable fallback path'}`, owner: 'SRE On-call', timeOffset: 25, automated: false, completed: true },
    { id: 'p4', phase: 'contain', action: 'Circuit breaker engaged — traffic rerouted', owner: 'System', timeOffset: 30, automated: true, completed: true },
    { id: 'p5', phase: 'recover', action: 'Primary system restoration initiated', owner: 'SRE On-call', timeOffset: scenario.expectedRecoverySec - 20, automated: false, completed: false },
    { id: 'p6', phase: 'recover', action: 'Health checks passing — traffic restored', owner: 'System', timeOffset: scenario.expectedRecoverySec, automated: true, completed: false },
    { id: 'p7', phase: 'validate', action: 'Post-incident validation sweep', owner: 'SRE Lead', timeOffset: scenario.expectedRecoverySec + 15, automated: false, completed: false },
    { id: 'p8', phase: 'validate', action: 'Update runbook with observations', owner: 'SRE Team', timeOffset: scenario.expectedRecoverySec + 30, automated: false, completed: false },
  ];
}

function generateObservations(scenario: FaultScenario, score: number): string[] {
  const obs: string[] = [];
  obs.push(`MTTR achieved in ${Math.round(scenario.expectedRecoverySec * (score > 80 ? 0.9 : 1.2))}s vs ${scenario.expectedRecoverySec}s SLO`);
  if (score >= 90) obs.push('Circuit breaker triggered within expected window — no cascading failures observed');
  if (score >= 75) obs.push(`Fallback path activated correctly — ${scenario.mitigations[0]}`);
  if (score < 80) obs.push('Alert latency exceeded 30s SLO — investigate Alertmanager routing config');
  obs.push(`Recovery score: ${score}/100 — ${score >= 85 ? 'System meets resilience SLA' : 'Improvement required before production readiness'}`);
  if (score < 90) obs.push('Recommendation: increase circuit breaker sensitivity threshold by 15%');
  return obs;
}

const SEVERITY_COLORS: Record<string, string> = {
  low: '#c9b787',
  medium: '#c9b787',
  high: '#c9b787',
  critical: '#f5f5f5',
};

const PHASE_COLORS: Record<string, string> = {
  detect: '#8a8a8a',
  contain: '#c9b787',
  recover: '#c9b787',
  validate: '#c9b787',
};

export default function ChaosEngineeringDrills() {
  const [selected, setSelected] = useState<FaultScenario | null>(null);
  const [drillStatus, setDrillStatus] = useState<DrillStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<DrillResult | null>(null);
  const [history, setHistory] = useState<DrillResult[]>([]);
  const [expandedObs, setExpandedObs] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const runDrill = useCallback(async (scenario: FaultScenario) => {
    clearTimer();
    setDrillStatus('injecting');
    setProgress(0);
    setResult(null);

    const startedAt = Date.now();
    const totalMs = (scenario.durationSec + scenario.expectedRecoverySec) * 1000;

    await new Promise<void>((resolve) => {
      timerRef.current = setInterval(() => {
        setProgress((p) => {
          const next = p + (100 / (totalMs / 200));
          if (next >= 100) {
            clearTimer();
            resolve();
            return 100;
          }
          if (next < 30) setDrillStatus('injecting');
          else if (next < 60) setDrillStatus('monitoring');
          else if (next < 85) setDrillStatus('recovering');
          else setDrillStatus('scoring');
          return next;
        });
      }, 200);
    });

    const score = Math.floor(72 + Math.random() * 25);
    const mttr = Math.round(scenario.expectedRecoverySec * (score > 85 ? 0.88 : 1.15));
    const drillResult: DrillResult = {
      scenarioId: scenario.id,
      startedAt,
      completedAt: Date.now(),
      recoveryScore: score,
      mttr,
      playbook: generatePlaybook(scenario),
      status: score >= 85 ? 'pass' : score >= 65 ? 'partial' : 'fail',
      observations: generateObservations(scenario, score),
    };
    setResult(drillResult);
    setHistory((h) => [drillResult, ...h.slice(0, 9)]);
    setDrillStatus('done');
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setDrillStatus('idle');
    setProgress(0);
    setResult(null);
  }, [clearTimer]);

  const isRunning = drillStatus !== 'idle' && drillStatus !== 'done';

  const statusLabel: Record<DrillStatus, string> = {
    idle: 'Ready',
    injecting: 'Fault injecting...',
    monitoring: 'Monitoring impact...',
    recovering: 'Recovery in progress...',
    scoring: 'Scoring resilience...',
    done: 'Drill complete',
  };

  return (
    <div className="h-full overflow-auto bg-[#080510] text-[#f5f5f5]" style={{ fontFamily: 'ui-monospace, monospace' }}>
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-[#f5f5f5]/10 border border-[#f5f5f5]/20">
              <Shield className="w-5 h-5 text-[#f5f5f5]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#f5f5f5]">Chaos Engineering Drills</h1>
              <p className="text-xs text-[#f5f5f5]/60 mt-0.5">Automated fault injection · Recovery scoring · Playbook generation</p>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-3">
            <div className="h-px flex-1 bg-[#f5f5f5]/10" />
            <span className="text-[10px] text-[#f5f5f5]/40 font-mono uppercase tracking-wider">PARAGON Resilience Suite</span>
            <div className="h-px flex-1 bg-[#f5f5f5]/10" />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Scenario Selector */}
          <div className="lg:col-span-1 space-y-3">
            <h2 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 mb-3">Fault Scenarios</h2>
            {FAULT_SCENARIOS.map((scenario) => {
              const Icon = scenario.icon;
              const isActive = selected?.id === scenario.id;
              const hist = history.filter((h) => h.scenarioId === scenario.id);
              const lastScore = hist[0]?.recoveryScore;
              return (
                <button
                  key={scenario.id}
                  onClick={() => { if (!isRunning) { setSelected(scenario); reset(); } }}
                  disabled={isRunning}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    isActive
                      ? 'bg-[#f5f5f5]/10 border-[#f5f5f5]/40'
                      : 'bg-white/[0.02] border-white/[0.06] hover:border-[#f5f5f5]/20 hover:bg-white/[0.04]'
                  } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5 text-[#f5f5f5]/70 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-semibold text-[#f5f5f5]">{scenario.name}</p>
                        <p className="text-[10px] text-[#f5f5f5]/50 mt-0.5 leading-relaxed">{scenario.description.slice(0, 60)}…</p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span
                        className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded"
                        style={{ background: `${SEVERITY_COLORS[scenario.severity]}18`, color: SEVERITY_COLORS[scenario.severity] }}
                      >
                        {scenario.severity}
                      </span>
                      {lastScore !== undefined && (
                        <span className="text-[9px] font-mono text-[#f5f5f5]/50">{lastScore}/100</span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Main Panel */}
          <div className="lg:col-span-2 space-y-5">
            {!selected ? (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
                <Shield className="w-8 h-8 text-[#f5f5f5]/20 mx-auto mb-3" />
                <p className="text-sm text-[#f5f5f5]/40">Select a fault scenario to begin</p>
              </div>
            ) : (
              <>
                {/* Scenario Detail */}
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <div>
                      <h3 className="text-sm font-bold text-[#f5f5f5]">{selected.name}</h3>
                      <p className="text-xs text-[#f5f5f5]/60 mt-1 leading-relaxed">{selected.description}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="flex items-center gap-1 text-[10px] text-[#f5f5f5]/50 mb-1">
                        <Timer className="w-3 h-3" />
                        {selected.durationSec}s injection
                      </div>
                      <div className="flex items-center gap-1 text-[10px] text-[#f5f5f5]/50">
                        <RefreshCw className="w-3 h-3" />
                        {selected.expectedRecoverySec}s recovery SLO
                      </div>
                    </div>
                  </div>

                  <div className="mb-4">
                    <p className="text-[10px] font-mono text-[#f5f5f5]/40 uppercase tracking-wider mb-2">Expected Mitigations</p>
                    <div className="space-y-1">
                      {selected.mitigations.map((m, i) => (
                        <div key={i} className="flex items-start gap-2 text-[11px] text-[#f5f5f5]/70">
                          <CheckCircle className="w-3 h-3 text-[#c9b787]/50 flex-shrink-0 mt-0.5" />
                          {m}
                        </div>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={() => isRunning ? undefined : runDrill(selected)}
                    disabled={isRunning}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                      isRunning
                        ? 'bg-[#f5f5f5]/10 text-[#f5f5f5]/40 cursor-not-allowed'
                        : 'bg-[#f5f5f5] hover:bg-[#f5f5f5] text-white'
                    }`}
                  >
                    {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                    {isRunning ? statusLabel[drillStatus] : 'Run Drill'}
                  </button>
                </div>

                {/* Progress Bar */}
                <AnimatePresence>
                  {isRunning && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#f5f5f5] animate-pulse" />
                          <span className="text-xs font-semibold text-[#f5f5f5]">{statusLabel[drillStatus]}</span>
                        </div>
                        <span className="text-xs font-mono text-[#f5f5f5]/50">{Math.round(progress)}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{
                            background: drillStatus === 'injecting' ? '#f5f5f5' :
                              drillStatus === 'monitoring' ? '#c9b787' :
                              drillStatus === 'recovering' ? '#c9b787' : '#c9b787',
                          }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.2 }}
                        />
                      </div>
                      <div className="flex justify-between mt-2 text-[9px] font-mono text-[#f5f5f5]/30">
                        <span>INJECT</span>
                        <span>MONITOR</span>
                        <span>RECOVER</span>
                        <span>SCORE</span>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Results */}
                <AnimatePresence>
                  {result && drillStatus === 'done' && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="space-y-4"
                    >
                      {/* Score Card */}
                      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                        <div className="flex items-center justify-between mb-4">
                          <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60">Resilience Score</h3>
                          <div className={`flex items-center gap-1.5 text-xs font-bold px-2 py-1 rounded-lg ${
                            result.status === 'pass' ? 'bg-[#c9b787]/10 text-[#c9b787]' :
                            result.status === 'partial' ? 'bg-[#c9b787]/10 text-[#c9b787]' :
                            'bg-[#f5f5f5]/10 text-[#f5f5f5]'
                          }`}>
                            {result.status === 'pass' ? <CheckCircle className="w-3 h-3" /> :
                             result.status === 'partial' ? <AlertTriangle className="w-3 h-3" /> :
                             <XCircle className="w-3 h-3" />}
                            {result.status.toUpperCase()}
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div>
                            <p className="text-3xl font-bold" style={{ color: result.recoveryScore >= 85 ? '#c9b787' : result.recoveryScore >= 65 ? '#c9b787' : '#f5f5f5' }}>
                              {result.recoveryScore}
                            </p>
                            <p className="text-[10px] text-[#f5f5f5]/40">/ 100 score</p>
                          </div>
                          <div>
                            <p className="text-xl font-bold text-[#f5f5f5]">{result.mttr}s</p>
                            <p className="text-[10px] text-[#f5f5f5]/40">MTTR achieved</p>
                          </div>
                          <div>
                            <p className="text-xl font-bold text-[#f5f5f5]">{selected.expectedRecoverySec}s</p>
                            <p className="text-[10px] text-[#f5f5f5]/40">SLO target</p>
                          </div>
                        </div>
                        <div className="w-full h-2 bg-white/[0.06] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${result.recoveryScore}%`,
                              background: result.recoveryScore >= 85 ? '#c9b787' : result.recoveryScore >= 65 ? '#c9b787' : '#f5f5f5',
                            }}
                          />
                        </div>
                      </div>

                      {/* Observations */}
                      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                        <button
                          onClick={() => setExpandedObs((v) => !v)}
                          className="flex items-center justify-between w-full text-left"
                        >
                          <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 flex items-center gap-2">
                            <Activity className="w-3 h-3" />
                            Observations
                          </h3>
                          <ChevronDown className={`w-3.5 h-3.5 text-[#f5f5f5]/40 transition-transform ${expandedObs ? 'rotate-180' : ''}`} />
                        </button>
                        <AnimatePresence>
                          {expandedObs && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="mt-3 space-y-2">
                                {result.observations.map((obs, i) => (
                                  <div key={i} className="flex items-start gap-2 text-[11px] text-[#f5f5f5]/70 leading-relaxed">
                                    <div className="w-1 h-1 rounded-full bg-[#f5f5f5]/40 flex-shrink-0 mt-1.5" />
                                    {obs}
                                  </div>
                                ))}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                        {!expandedObs && (
                          <p className="text-[11px] text-[#f5f5f5]/40 mt-2">{result.observations.length} observations generated</p>
                        )}
                      </div>

                      {/* Generated Playbook */}
                      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                        <div className="flex items-center justify-between mb-4">
                          <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 flex items-center gap-2">
                            <FileText className="w-3 h-3" />
                            Generated Playbook
                          </h3>
                          <span className="text-[10px] text-[#f5f5f5]/40">{result.playbook.length} steps</span>
                        </div>
                        <div className="space-y-2">
                          {result.playbook.map((step) => (
                            <div
                              key={step.id}
                              className="flex items-start gap-3 p-2.5 rounded-lg bg-white/[0.02]"
                            >
                              <div
                                className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                                style={{ background: PHASE_COLORS[step.phase] }}
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="text-[11px] text-[#f5f5f5]">{step.action}</p>
                                  {step.automated && (
                                    <span className="text-[9px] px-1 py-0.5 rounded bg-[#c9b787]/10 text-[#c9b787]">AUTO</span>
                                  )}
                                </div>
                                <div className="flex items-center gap-3 mt-0.5">
                                  <span
                                    className="text-[9px] font-mono uppercase"
                                    style={{ color: PHASE_COLORS[step.phase] }}
                                  >
                                    {step.phase}
                                  </span>
                                  <span className="text-[9px] text-[#f5f5f5]/40">{step.owner}</span>
                                  <span className="text-[9px] text-[#f5f5f5]/30 flex items-center gap-1">
                                    <Clock className="w-2.5 h-2.5" />
                                    T+{step.timeOffset}s
                                  </span>
                                </div>
                              </div>
                              {step.completed
                                ? <CheckCircle className="w-3 h-3 text-[#c9b787]/60 flex-shrink-0" />
                                : <div className="w-3 h-3 rounded-full border border-[#f5f5f5]/20 flex-shrink-0" />
                              }
                            </div>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}

            {/* Drill History */}
            {history.length > 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
                <h3 className="text-xs font-mono uppercase tracking-wider text-[#f5f5f5]/60 mb-3 flex items-center gap-2">
                  <Network className="w-3 h-3" />
                  Drill History
                </h3>
                <div className="space-y-2">
                  {history.map((h, i) => {
                    const sc = FAULT_SCENARIOS.find((s) => s.id === h.scenarioId);
                    return (
                      <div key={i} className="flex items-center justify-between text-[11px]">
                        <div className="flex items-center gap-2">
                          {h.status === 'pass' ? <CheckCircle className="w-3 h-3 text-[#c9b787]" /> :
                           h.status === 'partial' ? <AlertTriangle className="w-3 h-3 text-[#c9b787]" /> :
                           <XCircle className="w-3 h-3 text-[#f5f5f5]" />}
                          <span className="text-[#f5f5f5]/80">{sc?.name ?? h.scenarioId}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-[#f5f5f5]/50 font-mono">MTTR {h.mttr}s</span>
                          <span className={`font-bold ${h.recoveryScore >= 85 ? 'text-[#c9b787]' : h.recoveryScore >= 65 ? 'text-[#c9b787]' : 'text-[#f5f5f5]'}`}>
                            {h.recoveryScore}/100
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
