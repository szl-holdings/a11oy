import { useState, useEffect, useCallback } from 'react';

interface SuiteManifest {
  suite_id: string;
  name: string;
  description: string;
  domain: string;
  case_count: number;
  content_hash: string;
  version: number;
}

interface RunSummary {
  run_id: string;
  suite_id: string;
  model_id: string;
  provider: string;
  status: string;
  pass_rate: number;
  aggregate_score: number;
  total_cases: number;
  passed_cases: number;
  triggered_by: string;
  started_at: number;
  completed_at: number;
  content_hash: string;
}

interface CategoryBreakdown {
  total: number;
  passed: number;
  pass_rate: number;
  weighted_score: number;
}

interface CaseResult {
  case_id: string;
  category: string;
  label: string;
  passed: boolean;
  score: number;
  weight: number;
  latency_ms: number;
  detail: string;
  response_preview: string;
}

interface RunReport {
  run_id: string;
  suite_id: string;
  suite_name: string;
  suite_content_hash: string;
  model_id: string;
  provider: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  pass_rate: number;
  aggregate_score: number;
  categories: Record<string, CategoryBreakdown>;
  case_results: CaseResult[];
  content_hash: string;
  signature: string;
  started_at: number;
  completed_at: number;
  duration_ms: number;
}

interface ReproduceResult {
  hashes_match: boolean;
  original_content_hash: string;
  reproduced_content_hash: string;
  original_signature: string;
  reproduced_signature: string;
  suite_reproduced: boolean;
  suite_content_hash: string;
  original_suite_content_hash: string;
  manifest_hash: string;
  manifest_signature: string;
  cli_invocation: string;
  reproduce_run_id: string;
}

const RUNNER_URL = '/api-server/eval-harness';

const PROVIDER_COLORS: Record<string, string> = {
  openai: '#10b981',
  anthropic: '#f59e0b',
  gemini: '#3b82f6',
  huggingface: '#a78bfa',
  substrate: '#06b6d4',
};

function fmt(n: number | undefined, decimals = 1): string {
  if (n === undefined || n === null) return '—';
  return (n * 100).toFixed(decimals) + '%';
}

function timeAgo(ms: number): string {
  if (!ms) return '—';
  const diff = Date.now() - ms;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

function hashShort(h: string): string {
  return h ? h.slice(0, 12) + '…' : '—';
}

function statusBadge(status: string) {
  const cfg: Record<string, { color: string; bg: string; label: string }> = {
    completed: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', label: 'Completed' },
    failed:    { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',  label: 'Failed' },
    pending:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'Pending' },
  };
  const c = cfg[status] ?? { color: '#64748b', bg: 'rgba(100,116,139,0.1)', label: status };
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
      color: c.color, background: c.bg,
      padding: '2px 8px', borderRadius: 4, border: `1px solid ${c.color}33`,
    }}>
      {c.label}
    </span>
  );
}

export function EvidenceBenchPage() {
  const [suites, setSuites] = useState<SuiteManifest[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [suitesLoading, setSuitesLoading] = useState(true);
  const [runnerHealth, setRunnerHealth] = useState<'ok' | 'error' | 'checking'>('checking');
  const [submitForm, setSubmitForm] = useState({ suiteId: 'standard-v1', modelId: 'gpt-4o-mini', provider: 'openai' });
  const [submitting, setSubmitting] = useState(false);
  const [reproducing, setReproducing] = useState<string | null>(null);
  const [reproduceResult, setReproduceResult] = useState<ReproduceResult | null>(null);
  const [activeTab, setActiveTab] = useState<'runs' | 'suites' | 'submit'>('runs');

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch(`${RUNNER_URL}/health`);
      setRunnerHealth(r.ok ? 'ok' : 'error');
    } catch {
      setRunnerHealth('error');
    }
  }, []);

  const fetchSuites = useCallback(async () => {
    setSuitesLoading(true);
    try {
      const r = await fetch(`${RUNNER_URL}/suites`);
      if (r.ok) {
        const data = await r.json() as { suites: SuiteManifest[] };
        setSuites(data.suites ?? []);
      }
    } catch {
      // ignore — runner may not be started yet
    } finally {
      setSuitesLoading(false);
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${RUNNER_URL}/runs?limit=30`);
      if (r.ok) {
        const data = await r.json() as { runs: RunSummary[] };
        setRuns(data.runs ?? []);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const openRun = useCallback(async (runId: string) => {
    try {
      const r = await fetch(`${RUNNER_URL}/runs/${runId}`);
      if (r.ok) {
        const data = await r.json() as RunReport;
        setSelectedRun(data);
        setReproduceResult(null);
      }
    } catch {
      // ignore
    }
  }, []);

  const submitRun = useCallback(async () => {
    setSubmitting(true);
    try {
      const r = await fetch(`${RUNNER_URL}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          suite_id: submitForm.suiteId,
          model_id: submitForm.modelId,
          provider: submitForm.provider,
          triggered_by: 'evidence-bench-ui',
        }),
      });
      if (r.ok) {
        setActiveTab('runs');
        setTimeout(fetchRuns, 2000);
        setTimeout(fetchRuns, 6000);
      }
    } catch {
      // ignore
    } finally {
      setSubmitting(false);
    }
  }, [submitForm, fetchRuns]);

  const reproduce = useCallback(async (runId: string) => {
    setReproducing(runId);
    setReproduceResult(null);
    try {
      const r = await fetch(`${RUNNER_URL}/runs/${runId}/reproduce`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (r.ok) {
        const data = await r.json() as ReproduceResult;
        setReproduceResult(data);
      }
    } catch {
      // ignore
    } finally {
      setReproducing(null);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    fetchSuites();
    fetchRuns();
    const iv = setInterval(fetchRuns, 15_000);
    return () => clearInterval(iv);
  }, [checkHealth, fetchSuites, fetchRuns]);

  const healthColor = runnerHealth === 'ok' ? '#10b981' : runnerHealth === 'error' ? '#ef4444' : '#f59e0b';
  const healthLabel = runnerHealth === 'ok' ? 'Runner Online' : runnerHealth === 'error' ? 'Runner Offline' : 'Checking…';

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 6 }}>
          ◈ EVIDENCE BENCH
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.4rem' }}>
              Evidence Bench
            </h1>
            <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
              Reproducible OSS-benchmark evidence gating every model promotion. All runs are HMAC-signed and verifiable.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.4rem 0.75rem',
              background: 'rgba(3,7,18,0.6)', border: '1px solid rgba(100,116,139,0.2)',
              borderRadius: 8, fontSize: 12,
            }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: healthColor, boxShadow: `0 0 6px ${healthColor}` }} />
              <span style={{ color: '#94a3b8' }}>{healthLabel}</span>
            </div>
            <button
              onClick={() => { checkHealth(); fetchRuns(); }}
              style={{
                padding: '0.4rem 1rem', fontSize: 12, fontWeight: 600,
                background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.2)',
                borderRadius: 6, color: '#67e8f9', cursor: 'pointer',
              }}
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(100,116,139,0.15)', paddingBottom: '0.25rem' }}>
        {(['runs', 'suites', 'submit'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '0.5rem 1.25rem', fontSize: 13, fontWeight: 600,
              borderRadius: '6px 6px 0 0', border: 'none', cursor: 'pointer',
              background: activeTab === tab ? 'rgba(6,182,212,0.1)' : 'transparent',
              color: activeTab === tab ? '#67e8f9' : '#64748b',
              borderBottom: activeTab === tab ? '2px solid #06b6d4' : '2px solid transparent',
            }}
          >
            {tab === 'runs' ? 'Run History' : tab === 'suites' ? 'Suite Registry' : 'Submit Run'}
          </button>
        ))}
      </div>

      {/* Run History tab */}
      {activeTab === 'runs' && (
        <div style={{ display: 'grid', gridTemplateColumns: selectedRun ? '1fr 1fr' : '1fr', gap: '1.5rem' }}>
          {/* Left: runs list */}
          <div>
            {loading && runs.length === 0 ? (
              <div style={{ color: '#475569', textAlign: 'center', padding: '3rem', fontSize: 14 }}>
                Loading runs…
              </div>
            ) : runs.length === 0 ? (
              <div style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(100,116,139,0.15)',
                borderRadius: 12, padding: '3rem', textAlign: 'center',
              }}>
                <div style={{ fontSize: 32, marginBottom: '0.75rem', opacity: 0.5 }}>◈</div>
                <div style={{ color: '#475569', fontSize: 14 }}>No runs yet — submit your first evaluation</div>
                <button
                  onClick={() => setActiveTab('submit')}
                  style={{
                    marginTop: '1rem', padding: '0.5rem 1.25rem', fontSize: 13, fontWeight: 600,
                    background: 'rgba(6,182,212,0.1)', border: '1px solid rgba(6,182,212,0.25)',
                    borderRadius: 6, color: '#67e8f9', cursor: 'pointer',
                  }}
                >
                  Submit a Run
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {runs.map(run => (
                  <button
                    key={run.run_id}
                    onClick={() => openRun(run.run_id)}
                    style={{
                      background: selectedRun?.run_id === run.run_id
                        ? 'rgba(6,182,212,0.08)' : 'rgba(255,255,255,0.02)',
                      border: `1px solid ${selectedRun?.run_id === run.run_id ? 'rgba(6,182,212,0.3)' : 'rgba(100,116,139,0.15)'}`,
                      borderRadius: 10, padding: '0.875rem 1rem',
                      cursor: 'pointer', textAlign: 'left', width: '100%',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{
                          fontSize: 11, fontWeight: 700,
                          color: PROVIDER_COLORS[run.provider] ?? '#64748b',
                          background: `${PROVIDER_COLORS[run.provider] ?? '#64748b'}15`,
                          padding: '2px 7px', borderRadius: 4,
                        }}>
                          {run.provider}
                        </span>
                        {statusBadge(run.status)}
                      </div>
                      <span style={{ fontSize: 11, color: '#475569' }}>{timeAgo(run.started_at)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{run.model_id}</div>
                        <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{run.suite_id}</div>
                      </div>
                      {run.status === 'completed' && (
                        <div style={{ textAlign: 'right' }}>
                          <div style={{
                            fontSize: 20, fontWeight: 800,
                            color: (run.pass_rate ?? 0) >= 0.75 ? '#10b981' : (run.pass_rate ?? 0) >= 0.5 ? '#f59e0b' : '#ef4444',
                          }}>
                            {fmt(run.pass_rate)}
                          </div>
                          <div style={{ fontSize: 10, color: '#475569' }}>pass rate</div>
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Right: run detail */}
          {selectedRun && (
            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(100,116,139,0.15)',
              borderRadius: 12, padding: '1.25rem', overflowY: 'auto', maxHeight: '80vh',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div>
                  <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 4 }}>RUN REPORT</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{selectedRun.model_id}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>{selectedRun.suite_name}</div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => reproduce(selectedRun.run_id)}
                    disabled={reproducing === selectedRun.run_id}
                    style={{
                      padding: '0.35rem 0.75rem', fontSize: 11, fontWeight: 600,
                      background: 'rgba(124,58,237,0.1)', border: '1px solid rgba(124,58,237,0.3)',
                      borderRadius: 6, color: '#a78bfa', cursor: 'pointer',
                    }}
                  >
                    {reproducing === selectedRun.run_id ? 'Verifying…' : 'Reproduce'}
                  </button>
                  <button
                    onClick={() => setSelectedRun(null)}
                    style={{
                      padding: '0.35rem 0.75rem', fontSize: 11, fontWeight: 600,
                      background: 'rgba(100,116,139,0.1)', border: '1px solid rgba(100,116,139,0.2)',
                      borderRadius: 6, color: '#64748b', cursor: 'pointer',
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>

              {/* Score summary */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.5rem', marginBottom: '1rem' }}>
                {[
                  { label: 'Pass Rate', value: fmt(selectedRun.pass_rate), color: (selectedRun.pass_rate ?? 0) >= 0.75 ? '#10b981' : '#ef4444' },
                  { label: 'Cases Passed', value: `${selectedRun.passed_cases}/${selectedRun.total_cases}`, color: '#e2e8f0' },
                  { label: 'Duration', value: `${((selectedRun.duration_ms ?? 0) / 1000).toFixed(1)}s`, color: '#94a3b8' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(100,116,139,0.12)',
                    borderRadius: 8, padding: '0.75rem', textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color }}>{value}</div>
                    <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>{label}</div>
                  </div>
                ))}
              </div>

              {/* Reproduce result */}
              {reproduceResult && (
                <div style={{ marginBottom: '1rem' }}>
                  {/* Suite reproducibility verdict */}
                  <div style={{
                    background: reproduceResult.suite_reproduced ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${reproduceResult.suite_reproduced ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                    borderRadius: 8, padding: '0.75rem', marginBottom: '0.5rem',
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: reproduceResult.suite_reproduced ? '#10b981' : '#ef4444', marginBottom: 6 }}>
                      {reproduceResult.suite_reproduced
                        ? '✓ Suite Reproduced — Pinned benchmark inputs unchanged'
                        : '✗ Suite Drift Detected — Benchmark inputs changed since original run'}
                    </div>
                    <div style={{ fontSize: 10, color: '#475569', fontFamily: 'monospace', lineHeight: 1.9 }}>
                      <div>Original suite hash:   <span style={{ color: '#94a3b8' }}>{hashShort(reproduceResult.original_suite_content_hash)}</span></div>
                      <div>Reproduced suite hash: <span style={{ color: reproduceResult.suite_reproduced ? '#10b981' : '#ef4444' }}>{hashShort(reproduceResult.suite_content_hash)}</span></div>
                    </div>
                  </div>

                  {/* Signed manifest — the durable evidence artifact */}
                  <div style={{
                    background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.2)',
                    borderRadius: 8, padding: '0.625rem 0.875rem', marginBottom: '0.5rem',
                  }}>
                    <div style={{ fontSize: 10, color: '#7c3aed', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 6 }}>
                      SIGNED REPRODUCE MANIFEST
                    </div>
                    <div style={{ fontSize: 10, color: '#94a3b8', fontFamily: 'monospace', lineHeight: 1.9 }}>
                      <div>Manifest hash: <span style={{ color: '#c4b5fd' }}>{hashShort(reproduceResult.manifest_hash)}</span></div>
                      <div>HMAC sig:      <span style={{ color: '#c4b5fd' }}>{hashShort(reproduceResult.manifest_signature)}</span></div>
                      <div>New run ID:    <span style={{ color: '#a5b4fc' }}>{reproduceResult.reproduce_run_id?.slice(0, 18)}…</span></div>
                    </div>
                  </div>

                  {/* CLI invocation for external auditors */}
                  <div style={{
                    background: 'rgba(3,7,18,0.7)', border: '1px solid rgba(100,116,139,0.2)',
                    borderRadius: 8, padding: '0.625rem 0.875rem',
                  }}>
                    <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 6 }}>
                      AUDITOR CLI — run this to reproduce externally
                    </div>
                    <div style={{ fontSize: 10, color: '#67e8f9', fontFamily: 'monospace', wordBreak: 'break-all', lineHeight: 1.6 }}>
                      {reproduceResult.cli_invocation}
                    </div>
                  </div>
                </div>
              )}

              {/* Content hash */}
              <div style={{
                background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.15)',
                borderRadius: 8, padding: '0.625rem 0.875rem', marginBottom: '1rem',
              }}>
                <div style={{ fontSize: 10, color: '#7c3aed', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4 }}>EVIDENCE HASH (HMAC-SHA256)</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem', fontSize: 10, fontFamily: 'monospace', color: '#94a3b8' }}>
                  <div>Content: <span style={{ color: '#c4b5fd' }}>{hashShort(selectedRun.content_hash)}</span></div>
                  <div>Signature: <span style={{ color: '#c4b5fd' }}>{hashShort(selectedRun.signature)}</span></div>
                </div>
              </div>

              {/* Category breakdown */}
              {Object.entries(selectedRun.categories).length > 0 && (
                <div style={{ marginBottom: '1rem' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>CATEGORIES</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                    {Object.entries(selectedRun.categories).map(([cat, data]) => (
                      <div key={cat} style={{
                        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(100,116,139,0.1)',
                        borderRadius: 6, padding: '0.5rem 0.75rem',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: 12, color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>{cat}</span>
                          <span style={{ fontSize: 11, color: '#475569' }}>{data.passed}/{data.total}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <div style={{ width: 80, height: 6, background: 'rgba(100,116,139,0.2)', borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{
                              width: `${(data.pass_rate ?? 0) * 100}%`, height: '100%',
                              background: (data.pass_rate ?? 0) >= 0.75 ? '#10b981' : (data.pass_rate ?? 0) >= 0.5 ? '#f59e0b' : '#ef4444',
                              borderRadius: 3,
                            }} />
                          </div>
                          <span style={{
                            fontSize: 12, fontWeight: 700,
                            color: (data.pass_rate ?? 0) >= 0.75 ? '#10b981' : (data.pass_rate ?? 0) >= 0.5 ? '#f59e0b' : '#ef4444',
                          }}>
                            {fmt(data.pass_rate)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Case results */}
              {selectedRun.case_results && selectedRun.case_results.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>CASE RESULTS</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    {selectedRun.case_results.map(r => (
                      <div key={r.case_id} style={{
                        background: r.passed ? 'rgba(16,185,129,0.04)' : 'rgba(239,68,68,0.04)',
                        border: `1px solid ${r.passed ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'}`,
                        borderRadius: 6, padding: '0.5rem 0.75rem',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontSize: 14, color: r.passed ? '#10b981' : '#ef4444' }}>
                              {r.passed ? '✓' : '✗'}
                            </span>
                            <div>
                              <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>{r.label}</div>
                              <div style={{ fontSize: 10, color: '#475569' }}>{r.case_id} · {r.latency_ms}ms</div>
                            </div>
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 700, color: r.passed ? '#10b981' : '#ef4444' }}>
                            {(r.score * 100).toFixed(0)}
                          </span>
                        </div>
                        {!r.passed && r.detail && (
                          <div style={{ fontSize: 10, color: '#64748b', marginTop: 4, fontFamily: 'monospace' }}>
                            {r.detail.slice(0, 120)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Suite Registry tab */}
      {activeTab === 'suites' && (
        <div>
          {suitesLoading ? (
            <div style={{ color: '#475569', textAlign: 'center', padding: '3rem', fontSize: 14 }}>
              Loading suites…
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem' }}>
              {suites.map(suite => (
                <div key={suite.suite_id} style={{
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(100,116,139,0.15)',
                  borderRadius: 12, padding: '1.25rem',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>{suite.name}</div>
                      <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                        {suite.domain} · v{suite.version} · {suite.case_count} cases
                      </div>
                    </div>
                    <span style={{
                      fontSize: 10, fontWeight: 700, color: '#06b6d4',
                      background: 'rgba(6,182,212,0.1)', padding: '2px 7px', borderRadius: 4,
                    }}>
                      {suite.suite_id}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: '#64748b', margin: '0.5rem 0 0.75rem', lineHeight: 1.6 }}>
                    {suite.description}
                  </p>
                  <div style={{
                    background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: '0.5rem 0.75rem',
                    fontSize: 10, fontFamily: 'monospace', color: '#94a3b8',
                  }}>
                    SHA-256: <span style={{ color: '#c4b5fd' }}>{suite.content_hash.slice(0, 24)}…</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Submit Run tab */}
      {activeTab === 'submit' && (
        <div style={{ maxWidth: 520 }}>
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(100,116,139,0.15)',
            borderRadius: 12, padding: '1.5rem',
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0', marginBottom: '1.25rem' }}>
              Submit Evaluation Run
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 6 }}>Suite</label>
                <select
                  value={submitForm.suiteId}
                  onChange={e => setSubmitForm(f => ({ ...f, suiteId: e.target.value }))}
                  style={{
                    width: '100%', padding: '0.5rem 0.75rem', fontSize: 13,
                    background: 'rgba(3,7,18,0.6)', border: '1px solid rgba(100,116,139,0.3)',
                    borderRadius: 6, color: '#e2e8f0',
                  }}
                >
                  <option value="standard-v1">Standard Benchmark Suite (standard-v1)</option>
                  <option value="vessels-domain-v1">Vessels Domain Suite</option>
                  <option value="terra-domain-v1">Terra Domain Suite</option>
                  <option value="sentra-domain-v1">Sentra Domain Suite</option>
                  <option value="counsel-domain-v1">Counsel Domain Suite</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 6 }}>Provider</label>
                <select
                  value={submitForm.provider}
                  onChange={e => setSubmitForm(f => ({ ...f, provider: e.target.value }))}
                  style={{
                    width: '100%', padding: '0.5rem 0.75rem', fontSize: 13,
                    background: 'rgba(3,7,18,0.6)', border: '1px solid rgba(100,116,139,0.3)',
                    borderRadius: 6, color: '#e2e8f0',
                  }}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="gemini">Gemini</option>
                  <option value="huggingface">HuggingFace</option>
                  <option value="substrate">Substrate (internal)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', display: 'block', marginBottom: 6 }}>Model ID</label>
                <input
                  value={submitForm.modelId}
                  onChange={e => setSubmitForm(f => ({ ...f, modelId: e.target.value }))}
                  placeholder="e.g. gpt-4o-mini, claude-3-haiku-20240307"
                  style={{
                    width: '100%', padding: '0.5rem 0.75rem', fontSize: 13,
                    background: 'rgba(3,7,18,0.6)', border: '1px solid rgba(100,116,139,0.3)',
                    borderRadius: 6, color: '#e2e8f0', boxSizing: 'border-box',
                  }}
                />
              </div>

              <button
                onClick={submitRun}
                disabled={submitting || runnerHealth !== 'ok'}
                style={{
                  padding: '0.75rem 1.5rem', fontSize: 14, fontWeight: 700,
                  background: (submitting || runnerHealth !== 'ok') ? 'rgba(6,182,212,0.05)' : 'rgba(6,182,212,0.12)',
                  border: '1px solid rgba(6,182,212,0.3)',
                  borderRadius: 8, color: '#67e8f9', cursor: submitting ? 'not-allowed' : 'pointer',
                  opacity: (submitting || runnerHealth !== 'ok') ? 0.5 : 1,
                }}
              >
                {submitting ? 'Submitting…' : 'Submit Evaluation Run'}
              </button>

              {runnerHealth === 'error' && (
                <div style={{ fontSize: 12, color: '#f59e0b', padding: '0.625rem 0.75rem', background: 'rgba(245,158,11,0.08)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.2)' }}>
                  Eval runner is offline. Ensure the eval-runner workflow is started.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
