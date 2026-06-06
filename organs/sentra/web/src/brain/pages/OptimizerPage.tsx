import { useState, useCallback, useRef, useEffect } from 'react';
import type { AppPage } from '../App';
import { PROBLEM_TEMPLATES } from '../data/optimizerTemplates';
import type { ProblemTemplate, Variable, Constraint, ObjectiveWeight } from '../data/optimizerTemplates';
import type { AssignmentSolution } from '../lib/isingOptimizer';
import { ACTIVE_PLAYBOOKS } from '../data/a11oyConstitution';
import { useA11oyConstitution } from '../hooks/useA11oyConstitution';
import { appendProofEntry } from '../data/proofLedger';
import { SpinLattice } from '../components/SpinLattice';

interface Props { onNavigate: (p: AppPage) => void; }

type SolveState = 'idle' | 'solving' | 'done' | 'blocked';
type ActiveTab = 'allocation' | 'alternatives' | 'trace' | 'constraints';

// ─── Custom problem builder state ──────────────────────────────────────────
interface CustomProblemState {
  label: string;
  domain: string;
  description: string;
  variables: Variable[];
  constraints: Constraint[];
  objectives: ObjectiveWeight[];
}

function buildCustomTemplate(state: CustomProblemState): ProblemTemplate {
  return {
    id: 'custom',
    label: state.label || 'Custom Problem',
    domain: state.domain || 'Custom',
    description: state.description || 'Operator-defined allocation problem.',
    icon: '◉',
    accentColor: '#06b6d4',
    variables: state.variables,
    constraints: state.constraints,
    objectives: state.objectives.length > 0 ? state.objectives : [
      { id: 'o1', label: 'Primary objective',   weight: 0.6, direction: 'maximize' as const, kind: 'maximize-coverage'  as const },
      { id: 'o2', label: 'Secondary objective', weight: 0.4, direction: 'minimize' as const, kind: 'minimize-conflicts' as const },
    ],
  };
}

function uid(): string {
  return Math.random().toString(36).slice(2, 8);
}

export function OptimizerPage({ onNavigate }: Props) {
  const {
    clauses: activeConstitution,
    status: constitutionStatus,
    constitutionVersion,
  } = useA11oyConstitution();
  const workerRef = useRef<Worker | null>(null);

  // Terminate solver worker when the component unmounts.
  useEffect(() => () => { workerRef.current?.terminate(); }, []);

  const [selectedId, setSelectedId] = useState<string>(PROBLEM_TEMPLATES[0].id);
  const [customState, setCustomState] = useState<CustomProblemState>({
    label: 'Custom Problem',
    domain: 'Custom',
    description: '',
    variables: [],
    constraints: [],
    objectives: [
      { id: 'o1', label: 'Primary objective',   weight: 0.6, direction: 'maximize' as const, kind: 'maximize-coverage'  as const },
      { id: 'o2', label: 'Secondary objective', weight: 0.4, direction: 'minimize' as const, kind: 'minimize-conflicts' as const },
    ],
  });
  const [solveState, setSolveState] = useState<SolveState>('idle');
  const [result, setResult] = useState<AssignmentSolution | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('allocation');
  const [solveProgress, setSolveProgress] = useState(0);

  // Custom builder sub-states
  const [newVarLabel, setNewVarLabel] = useState('');
  const [newVarDomain, setNewVarDomain] = useState('');
  const [newConLabel, setNewConLabel] = useState('');
  const [newConType, setNewConType] = useState<'hard' | 'soft'>('hard');
  const [newObjLabel, setNewObjLabel] = useState('');
  const [newObjDirection, setNewObjDirection] = useState<'maximize' | 'minimize'>('maximize');

  const isCustom = selectedId === 'custom';
  const seededTemplates = PROBLEM_TEMPLATES;

  const getTemplate = (): ProblemTemplate => {
    if (isCustom) return buildCustomTemplate(customState);
    return PROBLEM_TEMPLATES.find(t => t.id === selectedId) ?? PROBLEM_TEMPLATES[0];
  };

  const selectedTemplate = getTemplate();

  const runSolve = useCallback(() => {
    const template = getTemplate();
    if (template.variables.length === 0) return;

    // Terminate any previous in-flight worker before launching a new one.
    workerRef.current?.terminate();

    setSolveState('solving');
    setSolveProgress(0);
    setResult(null);

    // Smooth progress bar driven by a main-thread interval while the real
    // solve runs inside the web worker, keeping the UI fully responsive.
    let p = 0;
    const progressInterval = setInterval(() => {
      p = Math.min(p + Math.random() * 8 + 2, 94);
      setSolveProgress(p);
    }, 60);

    const worker = new Worker(
      new URL('../workers/solver.worker.ts', import.meta.url),
      { type: 'module' },
    );
    workerRef.current = worker;

    worker.onmessage = (e: MessageEvent<{ type: string; value?: AssignmentSolution; message?: string }>) => {
      const msg = e.data;
      if (msg.type === 'result' && msg.value) {
        clearInterval(progressInterval);
        setSolveProgress(100);
        const solution = msg.value;
        setResult(solution);
        setSolveState(solution.guardrailsPassed ? 'done' : 'blocked');
        // Record constitution provenance from the runtime state used by the solve.
        void appendProofEntry({
          problemId: template.id,
          problemLabel: template.label,
          constitutionVersion: solution.constitutionVersion,
          constitutionSource: solution.constitutionSource,
          outcome: solution.guardrailsPassed ? 'optimal' : 'blocked',
          objectiveScore: solution.objectiveScore,
          guardrailsChecked: activeConstitution.length,
          guardrailsViolated: solution.guardrailViolations.length,
          solveTimeMs: solution.solveTimeMs,
          inputs: {
            templateId: template.id,
            variables: template.variables.map(v => ({ id: v.id, domain: v.domain })),
            constraints: template.constraints.map(c => ({ id: c.id, kind: c.kind, type: c.type })),
            objectives: template.objectives.map(o => ({ id: o.id, kind: o.kind, weight: o.weight })),
            constitutionVersion: solution.constitutionVersion,
          },
          notes: solution.guardrailViolations.length > 0 ? solution.guardrailViolations.join('; ') : undefined,
        });
        worker.terminate();
      } else if (msg.type === 'error') {
        clearInterval(progressInterval);
        setSolveState('idle');
        worker.terminate();
      }
    };

    worker.onerror = () => {
      clearInterval(progressInterval);
      setSolveState('idle');
      worker.terminate();
    };

    // Pass the active constitution (live or fallback) to the worker so
    // guardrails are evaluated against the runtime doctrine set, not a hardcoded constant.
    worker.postMessage({
      type: 'solve',
      payload: template,
      constitution: activeConstitution,
      constitutionVersion: constitutionVersion,
      constitutionSource: constitutionStatus === 'loading' ? 'seed' : constitutionStatus,
    });
  }, [selectedId, customState, activeConstitution, constitutionVersion, constitutionStatus]);

  // Custom builder helpers
  const addVariable = () => {
    if (!newVarLabel.trim() || !newVarDomain.trim()) return;
    const domain = newVarDomain.split(',').map(s => s.trim()).filter(Boolean);
    if (domain.length < 2) return;
    setCustomState(s => ({
      ...s,
      variables: [...s.variables, { id: `v${uid()}`, label: newVarLabel.trim(), type: 'assignment', domain }],
    }));
    setNewVarLabel('');
    setNewVarDomain('');
  };

  const removeVariable = (id: string) => {
    setCustomState(s => ({ ...s, variables: s.variables.filter(v => v.id !== id) }));
  };

  const addConstraint = () => {
    if (!newConLabel.trim()) return;
    setCustomState(s => ({
      ...s,
      constraints: [...s.constraints, {
        id: `c${uid()}`,
        label: newConLabel.trim(),
        type: newConType,
        kind: (newConType === 'hard' ? 'unique-assignment' : 'preference') as 'unique-assignment' | 'preference',
        description: newConLabel.trim(),
      }],
    }));
    setNewConLabel('');
  };

  const removeConstraint = (id: string) => {
    setCustomState(s => ({ ...s, constraints: s.constraints.filter(c => c.id !== id) }));
  };

  const addObjective = () => {
    if (!newObjLabel.trim()) return;
    const remaining = Math.max(0.05, 1 - customState.objectives.reduce((s, o) => s + o.weight, 0));
    const weight = Math.min(remaining, 0.3);
    setCustomState(s => ({
      ...s,
      objectives: [...s.objectives, { id: `o${uid()}`, label: newObjLabel.trim(), weight, direction: newObjDirection, kind: (newObjDirection === 'maximize' ? 'maximize-coverage' : 'minimize-conflicts') as 'maximize-coverage' | 'minimize-conflicts' }],
    }));
    setNewObjLabel('');
  };

  const removeObjective = (id: string) => {
    setCustomState(s => ({ ...s, objectives: s.objectives.filter(o => o.id !== id) }));
  };

  const inputStyle: React.CSSProperties = {
    background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.15)',
    borderRadius: 6, color: '#e2e8f0', fontSize: 12, padding: '0.4rem 0.6rem', outline: 'none',
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle, cursor: 'pointer',
  };

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 6 }}>
          ⬡ ISING-STYLE DECISION OPTIMIZER
        </div>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.5rem' }}>Optimizer</h1>
        <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
          Select a template or build a custom problem, then let ROSIE find the optimal allocation via simulated annealing.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '1.5rem' }}>
        {/* Left panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Template Selection */}
          <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 12, padding: '1.25rem' }}>
            <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              PROBLEM TEMPLATE
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {seededTemplates.map(t => (
                <button key={t.id} onClick={() => { setSelectedId(t.id); setSolveState('idle'); setResult(null); }}
                  style={{
                    background: selectedId === t.id ? 'rgba(6,182,212,0.08)' : 'transparent',
                    border: selectedId === t.id ? `1px solid ${t.accentColor}44` : '1px solid rgba(255,255,255,0.05)',
                    borderRadius: 8, padding: '0.65rem', cursor: 'pointer', textAlign: 'left',
                    display: 'flex', alignItems: 'flex-start', gap: '0.65rem',
                  }}>
                  <span style={{ fontSize: 18, lineHeight: 1 }}>{t.icon}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 1 }}>{t.label}</div>
                    <div style={{ fontSize: 11, color: '#475569' }}>{t.domain}</div>
                  </div>
                </button>
              ))}
              {/* Custom */}
              <button onClick={() => { setSelectedId('custom'); setSolveState('idle'); setResult(null); }}
                style={{
                  background: isCustom ? 'rgba(6,182,212,0.08)' : 'transparent',
                  border: isCustom ? '1px solid rgba(6,182,212,0.35)' : '1px solid rgba(255,255,255,0.05)',
                  borderRadius: 8, padding: '0.65rem', cursor: 'pointer', textAlign: 'left',
                  display: 'flex', alignItems: 'flex-start', gap: '0.65rem',
                }}>
                <span style={{ fontSize: 18, lineHeight: 1 }}>◉</span>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 1 }}>Custom Problem</div>
                  <div style={{ fontSize: 11, color: '#475569' }}>Operator-defined</div>
                </div>
              </button>
            </div>
          </div>

          {/* Seeded template variables */}
          {!isCustom && selectedTemplate.variables.length > 0 && (
            <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 12, padding: '1.25rem' }}>
              <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
                VARIABLES ({selectedTemplate.variables.length})
              </div>
              {selectedTemplate.variables.map(v => (
                <div key={v.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '0.3rem 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <span style={{ color: '#94a3b8' }}>{v.label}</span>
                  <span style={{ color: '#475569', fontSize: 11 }}>{v.domain.length} options</span>
                </div>
              ))}
            </div>
          )}

          {/* Custom problem builder */}
          {isCustom && (
            <div style={{ background: 'rgba(6,182,212,0.03)', border: '1px solid rgba(6,182,212,0.15)', borderRadius: 12, padding: '1.25rem' }}>
              <div style={{ fontSize: 11, color: '#06b6d4', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '1rem' }}>
                ◉ CUSTOM PROBLEM BUILDER
              </div>

              {/* Problem metadata */}
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>Problem Name</div>
                <input style={{ ...inputStyle, width: '100%' }} value={customState.label}
                  onChange={e => setCustomState(s => ({ ...s, label: e.target.value }))}
                  placeholder="e.g. Warehouse Zone Assignment" />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>Domain</div>
                <input style={{ ...inputStyle, width: '100%' }} value={customState.domain}
                  onChange={e => setCustomState(s => ({ ...s, domain: e.target.value }))}
                  placeholder="e.g. Logistics" />
              </div>

              {/* Variables */}
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '0.5rem' }}>
                  VARIABLES ({customState.variables.length})
                </div>
                {customState.variables.map(v => (
                  <div key={v.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.35rem 0.5rem', marginBottom: 4,
                    background: 'rgba(6,182,212,0.04)', border: '1px solid rgba(6,182,212,0.1)', borderRadius: 4,
                  }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>{v.label}</div>
                      <div style={{ fontSize: 10, color: '#475569' }}>[{v.domain.join(', ')}]</div>
                    </div>
                    <button onClick={() => removeVariable(v.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 12 }}>✕</button>
                  </div>
                ))}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.5rem' }}>
                  <input style={{ ...inputStyle, width: '100%' }} value={newVarLabel}
                    onChange={e => setNewVarLabel(e.target.value)}
                    placeholder="Variable name (e.g. Team A)" />
                  <input style={{ ...inputStyle, width: '100%' }} value={newVarDomain}
                    onChange={e => setNewVarDomain(e.target.value)}
                    placeholder="Domain: comma-separated values (min 2)" />
                  <button onClick={addVariable} style={{
                    padding: '0.4rem', background: 'rgba(6,182,212,0.12)',
                    border: '1px solid rgba(6,182,212,0.25)', borderRadius: 6,
                    color: '#06b6d4', fontSize: 12, cursor: 'pointer', fontWeight: 600,
                  }}>
                    + Add Variable
                  </button>
                </div>
              </div>

              {/* Constraints */}
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '0.5rem' }}>
                  CONSTRAINTS ({customState.constraints.length})
                </div>
                {customState.constraints.map(c => (
                  <div key={c.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.35rem 0.5rem', marginBottom: 4,
                    background: c.type === 'hard' ? 'rgba(239,68,68,0.06)' : 'rgba(6,182,212,0.04)',
                    border: `1px solid ${c.type === 'hard' ? 'rgba(239,68,68,0.15)' : 'rgba(6,182,212,0.1)'}`,
                    borderRadius: 4,
                  }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>{c.label}</div>
                      <div style={{ fontSize: 10, color: c.type === 'hard' ? '#f87171' : '#67e8f9' }}>{c.type}</div>
                    </div>
                    <button onClick={() => removeConstraint(c.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 12 }}>✕</button>
                  </div>
                ))}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.5rem' }}>
                  <input style={{ ...inputStyle, width: '100%' }} value={newConLabel}
                    onChange={e => setNewConLabel(e.target.value)}
                    placeholder="Constraint description" />
                  <select style={{ ...selectStyle, width: '100%' }} value={newConType}
                    onChange={e => setNewConType(e.target.value as 'hard' | 'soft')}>
                    <option value="hard">Hard (must satisfy)</option>
                    <option value="soft">Soft (prefer to satisfy)</option>
                  </select>
                  <button onClick={addConstraint} style={{
                    padding: '0.4rem', background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6,
                    color: '#f87171', fontSize: 12, cursor: 'pointer', fontWeight: 600,
                  }}>
                    + Add Constraint
                  </button>
                </div>
              </div>

              {/* Objectives */}
              <div>
                <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '0.5rem' }}>
                  OBJECTIVES ({customState.objectives.length})
                </div>
                {customState.objectives.map(o => (
                  <div key={o.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.35rem 0.5rem', marginBottom: 4,
                    background: 'rgba(6,182,212,0.04)', border: '1px solid rgba(6,182,212,0.1)', borderRadius: 4,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: '#e2e8f0', fontWeight: 600 }}>{o.label}</div>
                      <div style={{ fontSize: 10, color: '#475569' }}>{o.direction} · {(o.weight * 100).toFixed(0)}%</div>
                    </div>
                    <button onClick={() => removeObjective(o.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 12 }}>✕</button>
                  </div>
                ))}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.5rem' }}>
                  <input style={{ ...inputStyle, width: '100%' }} value={newObjLabel}
                    onChange={e => setNewObjLabel(e.target.value)}
                    placeholder="Objective label" />
                  <select style={{ ...selectStyle, width: '100%' }} value={newObjDirection}
                    onChange={e => setNewObjDirection(e.target.value as 'maximize' | 'minimize')}>
                    <option value="maximize">Maximize</option>
                    <option value="minimize">Minimize</option>
                  </select>
                  <button onClick={addObjective} style={{
                    padding: '0.4rem', background: 'rgba(124,58,237,0.08)',
                    border: '1px solid rgba(124,58,237,0.2)', borderRadius: 6,
                    color: '#a78bfa', fontSize: 12, cursor: 'pointer', fontWeight: 600,
                  }}>
                    + Add Objective
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Objective weights (seeded templates) */}
          {!isCustom && (
            <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 12, padding: '1.25rem' }}>
              <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
                OBJECTIVE WEIGHTS
              </div>
              {selectedTemplate.objectives.map(obj => (
                <div key={obj.id} style={{ marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                    <span style={{ color: '#94a3b8' }}>{obj.label}</span>
                    <span style={{ color: '#06b6d4', fontWeight: 600 }}>{(obj.weight * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                    <div style={{
                      width: `${obj.weight * 100}%`, height: '100%',
                      background: obj.direction === 'maximize' ? 'linear-gradient(90deg, #06b6d4, #7c3aed)' : 'linear-gradient(90deg, #c9b787, #ef4444)',
                      borderRadius: 2,
                    }} />
                  </div>
                  <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>{obj.direction === 'maximize' ? '↑ maximize' : '↓ minimize'}</div>
                </div>
              ))}
            </div>
          )}

          {/* A11oy Guardrails */}
          <div style={{ background: 'rgba(201,183,135,0.03)', border: '1px solid rgba(201,183,135,0.12)', borderRadius: 12, padding: '1.25rem' }}>
            <div style={{ fontSize: 11, color: '#c9b787', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              ◆ A11OY GUARDRAILS ACTIVE
            </div>
            {activeConstitution.map((c: (typeof activeConstitution)[number]) => (
              <div key={c.id} style={{
                display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '0.45rem',
                padding: '0.35rem', background: c.binding === 'inviolable' ? 'rgba(239,68,68,0.04)' : 'transparent', borderRadius: 4,
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', marginTop: 4, flexShrink: 0,
                  background: c.binding === 'inviolable' ? '#ef4444' : c.binding === 'strong' ? '#f59e0b' : '#06b6d4',
                }} />
                <div>
                  <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>{c.id}</div>
                  <div style={{ fontSize: 10, color: '#475569', lineHeight: 1.4 }}>{c.optimizerImplication}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Problem description */}
          <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 12, padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1rem' }}>
              <span style={{ fontSize: 28 }}>{selectedTemplate.icon}</span>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.35rem' }}>{selectedTemplate.label}</h2>
                <p style={{ fontSize: 13, color: '#64748b', margin: 0, lineHeight: 1.6 }}>{selectedTemplate.description}</p>
              </div>
            </div>
            {selectedTemplate.constraints.length > 0 && (
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {selectedTemplate.constraints.map(c => (
                  <span key={c.id} style={{
                    padding: '0.2rem 0.6rem',
                    background: c.type === 'hard' ? 'rgba(239,68,68,0.08)' : 'rgba(6,182,212,0.06)',
                    border: `1px solid ${c.type === 'hard' ? 'rgba(239,68,68,0.2)' : 'rgba(6,182,212,0.15)'}`,
                    borderRadius: 20, fontSize: 11,
                    color: c.type === 'hard' ? '#f87171' : '#67e8f9',
                  }}>
                    {c.type === 'hard' ? '⬡ hard' : '◎ soft'}: {c.label}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Solve panel */}
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: `1px solid ${solveState === 'done' ? 'rgba(6,182,212,0.25)' : solveState === 'blocked' ? 'rgba(239,68,68,0.25)' : 'rgba(6,182,212,0.12)'}`,
            borderRadius: 12, overflow: 'hidden',
          }}>
            {/* Lattice viz */}
            <div style={{ position: 'relative', height: 120 }}>
              <SpinLattice width={800} height={120} animated solving={solveState === 'solving'} />
              <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to right, rgba(15,23,42,0.4), transparent, rgba(15,23,42,0.4))' }} />
              {solveState === 'solving' && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ fontSize: 13, color: '#06b6d4', fontWeight: 700, marginBottom: 8 }}>Minimizing Hamiltonian energy...</div>
                  <div style={{ width: 200, height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2 }}>
                    <div style={{ width: `${solveProgress}%`, height: '100%', background: 'linear-gradient(90deg, #06b6d4, #7c3aed)', borderRadius: 2, transition: 'width 0.1s' }} />
                  </div>
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 6 }}>Simulated Annealing · 800 iterations</div>
                </div>
              )}
            </div>

            <div style={{ padding: '1.25rem' }}>
              {solveState === 'idle' && (
                <div>
                  {isCustom && selectedTemplate.variables.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '0.75rem', color: '#475569', fontSize: 13 }}>
                      Add at least 2 variables on the left to enable the solver.
                    </div>
                  ) : (
                    <button onClick={runSolve} style={{
                      width: '100%', padding: '0.85rem',
                      background: 'linear-gradient(135deg, #06b6d4, #7c3aed)',
                      border: 'none', borderRadius: 8, color: '#fff',
                      fontSize: 15, fontWeight: 700, cursor: 'pointer',
                      boxShadow: '0 0 20px rgba(6,182,212,0.2)',
                    }}>
                      ⬡ Run Ising Solve
                    </button>
                  )}
                </div>
              )}

              {solveState === 'solving' && (
                <div style={{ textAlign: 'center', color: '#64748b', fontSize: 13 }}>Solving... checking A11oy constitution...</div>
              )}

              {(solveState === 'done' || solveState === 'blocked') && result && (
                <>
                  {/* Summary bar */}
                  <div style={{
                    display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem',
                    padding: '0.75rem 1rem',
                    background: solveState === 'done' ? 'rgba(6,182,212,0.05)' : 'rgba(239,68,68,0.05)',
                    border: `1px solid ${solveState === 'done' ? 'rgba(6,182,212,0.2)' : 'rgba(239,68,68,0.2)'}`,
                    borderRadius: 8,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>OBJECTIVE SCORE</div>
                      <div style={{ fontSize: 24, fontWeight: 800, color: '#06b6d4' }}>{(result.objectiveScore * 100).toFixed(1)}%</div>
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>SOLVE TIME</div>
                      <div style={{ fontSize: 24, fontWeight: 800, color: '#e2e8f0' }}>{result.solveTimeMs}ms</div>
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>GUARDRAILS</div>
                      <div style={{ fontSize: 24, fontWeight: 800, color: result.guardrailsPassed ? '#10b981' : '#ef4444' }}>
                        {result.guardrailsPassed ? '✓ PASS' : '✗ FAIL'}
                      </div>
                    </div>
                    <div style={{ flex: 1, textAlign: 'right' }}>
                      <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>CONSTITUTION</div>
                      <div style={{ fontSize: 12, color: '#c9b787', fontWeight: 600 }}>v{result.constitutionVersion}</div>
                    </div>
                  </div>

                  {result.guardrailViolations.length > 0 && (
                    <div style={{ padding: '0.75rem', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, marginBottom: '1rem' }}>
                      {result.guardrailViolations.map((v, i) => (
                        <div key={i} style={{ fontSize: 12, color: '#f87171' }}>⬡ {v}</div>
                      ))}
                    </div>
                  )}

                  {/* Result tabs */}
                  <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '0.5rem' }}>
                    {(['allocation', 'alternatives', 'trace', 'constraints'] as ActiveTab[]).map(tab => (
                      <button key={tab} onClick={() => setActiveTab(tab)} style={{
                        padding: '0.35rem 0.75rem',
                        background: activeTab === tab ? 'rgba(6,182,212,0.1)' : 'transparent',
                        border: activeTab === tab ? '1px solid rgba(6,182,212,0.3)' : '1px solid transparent',
                        borderRadius: 6, cursor: 'pointer',
                        fontSize: 12, color: activeTab === tab ? '#06b6d4' : '#64748b',
                        fontWeight: activeTab === tab ? 600 : 400, textTransform: 'capitalize',
                      }}>{tab}</button>
                    ))}
                  </div>

                  {/* Tab content */}
                  {activeTab === 'allocation' && (
                    <div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '1rem' }}>
                        {Object.entries(result.assignments).map(([varId, value]) => {
                          const varDef = selectedTemplate.variables.find(v => v.id === varId);
                          return (
                            <div key={varId} style={{ padding: '0.6rem 0.75rem', background: 'rgba(6,182,212,0.04)', border: '1px solid rgba(6,182,212,0.12)', borderRadius: 6, display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 12, color: '#94a3b8', flex: 1 }}>{varDef?.label ?? varId}</span>
                              <span style={{ fontSize: 12, color: '#06b6d4', fontWeight: 600 }}>→ {value}</span>
                            </div>
                          );
                        })}
                      </div>
                      <div style={{ fontSize: 11, color: '#475569', marginBottom: '0.75rem' }}>OBJECTIVE BREAKDOWN</div>
                      {result.objectiveBreakdown.map(o => (
                        <div key={o.id} style={{ marginBottom: '0.5rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                            <span style={{ color: '#94a3b8' }}>{o.label}</span>
                            <span style={{ color: '#06b6d4', fontWeight: 600 }}>{(o.score * 100).toFixed(0)}%</span>
                          </div>
                          <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                            <div style={{ width: `${o.score * 100}%`, height: '100%', background: 'linear-gradient(90deg, #06b6d4, #7c3aed)', borderRadius: 2 }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'alternatives' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {result.alternatives.map(alt => (
                        <div key={alt.rank} style={{ padding: '0.75rem', background: 'rgba(124,58,237,0.04)', border: '1px solid rgba(124,58,237,0.15)', borderRadius: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: 600, color: '#a78bfa' }}>Alternative #{alt.rank}</span>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                              <span style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>{(alt.objectiveScore * 100).toFixed(1)}%</span>
                              <span style={{ fontSize: 12, color: '#f87171' }}>Δ −{(alt.delta * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                          <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>{alt.description}</div>
                          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            {Object.entries(alt.assignments).slice(0, 4).map(([k, v]) => {
                              const varDef = selectedTemplate.variables.find(vv => vv.id === k);
                              return (
                                <span key={k} style={{ fontSize: 11, padding: '0.15rem 0.5rem', background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.15)', borderRadius: 4, color: '#a78bfa' }}>
                                  {(varDef?.label ?? k).split(' ')[0]} → {v}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'trace' && (
                    <div style={{ maxHeight: 300, overflow: 'auto' }}>
                      {result.reasoningTrace.map(step => (
                        <div key={step.step} style={{
                          padding: '0.5rem 0.75rem', marginBottom: '0.35rem',
                          background: step.accepted && step.energyDelta < 0 ? 'rgba(16,185,129,0.04)' : step.accepted ? 'rgba(245,158,11,0.04)' : 'rgba(239,68,68,0.03)',
                          border: `1px solid ${step.accepted && step.energyDelta < 0 ? 'rgba(16,185,129,0.15)' : step.accepted ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.1)'}`,
                          borderRadius: 6,
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                            <span style={{ fontSize: 11, color: '#64748b' }}>Step {step.step}</span>
                            <span style={{ fontSize: 11, color: step.accepted ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                              {step.accepted ? '✓ ACCEPTED' : '✗ REJECTED'}
                            </span>
                          </div>
                          {step.variable && (
                            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 2 }}>
                              {step.variable}: {step.fromValue} → {step.toValue}
                            </div>
                          )}
                          <div style={{ fontSize: 11, color: '#475569' }}>{step.reason}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'constraints' && (
                    <div>
                      {result.constraintResults.map(cr => (
                        <div key={cr.id} style={{
                          display: 'flex', alignItems: 'center', gap: '0.75rem',
                          padding: '0.5rem', marginBottom: '0.4rem',
                          background: cr.satisfied ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)',
                          border: `1px solid ${cr.satisfied ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}`,
                          borderRadius: 6,
                        }}>
                          <div style={{
                            fontSize: 12, width: 20, height: 20, borderRadius: '50%',
                            background: cr.satisfied ? '#10b981' : '#ef4444',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: '#fff', fontWeight: 700, flexShrink: 0,
                          }}>{cr.satisfied ? '✓' : '✗'}</div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600 }}>{cr.label}</div>
                            <div style={{ fontSize: 11, color: '#64748b' }}>
                              {cr.type === 'hard' ? 'Hard constraint' : 'Soft constraint'} · Violation: {(cr.violationScore * 100).toFixed(0)}%
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                    <button onClick={runSolve} style={{
                      flex: 1, padding: '0.6rem',
                      background: 'linear-gradient(135deg, #06b6d4, #7c3aed)',
                      border: 'none', borderRadius: 8, color: '#fff',
                      fontSize: 13, fontWeight: 700, cursor: 'pointer',
                    }}>⬡ Re-solve</button>
                    <button onClick={() => onNavigate('proof')} style={{
                      padding: '0.6rem 1rem', background: 'rgba(201,183,135,0.08)',
                      border: '1px solid rgba(201,183,135,0.2)', borderRadius: 8,
                      color: '#c9b787', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}>View Proof →</button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Active playbooks */}
          <div style={{ background: 'rgba(15,23,42,0.4)', border: '1px solid rgba(245,158,11,0.12)', borderRadius: 12, padding: '1rem 1.25rem' }}>
            <div style={{ fontSize: 11, color: '#f59e0b', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              ◎ ACTIVE PLAYBOOKS
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {ACTIVE_PLAYBOOKS.map(pb => (
                <div key={pb.id} style={{
                  padding: '0.3rem 0.7rem',
                  background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
                  borderRadius: 20, fontSize: 11, color: '#fbbf24',
                }}>{pb.name}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
