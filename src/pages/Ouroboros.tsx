// ADDITIVE: Ouroboros Runner UI — /ouroboros
// Doctrine v10/v11 — 32-module self-test runner
// Shows live progress bar + per-module result table + "Run again" button
// Fetches from /api/a11oy/v1/ouroboros/run-all (POST {})

import { useState, useCallback } from 'react';

const MODULES = [
  'v14_lutar_calculus.py',
  'v15_knot_calculus.py',
  'v16_feynman_gates.py',
  'v17_wheeler_shannon_qec.py',
  'v17_the_four.py',
  'gnn_substrate.py',
  'mathonto_substrate.py',
  'a11oy_code_blueprint.py',
  'uds_airgap_drone.py',
  'eng_substrate.py',
  'mila_substrate.py',
  'founder_substrate.py',
  'production_substrate.py',
  'agent_tooling.py',
  'quantum_substrate.py',
  'community_substrate.py',
  'observability_substrate.py',
  'ai_observability_substrate.py',
  'apm_substrate.py',
  'palantir_substrate.py',
  'pyg_substrate.py',
  'dsa_substrate.py',
  'cedric_mo_substrate.py',
  'cursor_claude_substrate.py',
  'iqt_substrate.py',
  'turbovec_substrate.py',
  'nvidia_rtr_substrate.py',
  'openmdw_substrate.py',
  'scientistone_coe_substrate.py',
  'uds_v18_24_substrate.py',
  'mythos_substrate.py',
  'a11oy_v19_opus48_substrate.py',
];

type ModuleResult = {
  module: string;
  status: 'GREEN' | 'RED' | 'ERROR' | 'pending' | 'running';
  duration_ms: number;
  doi?: string;
  error?: string;
};

type RunResult = {
  tests_run: number;
  tests_pass: number;
  tests_fail: number;
  duration_ms: number;
  receipts: ModuleResult[];
};

type RunState = 'idle' | 'running' | 'done' | 'error';

export function Ouroboros() {
  const [runState, setRunState] = useState<RunState>('idle');
  const [result, setResult] = useState<RunResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const runTests = useCallback(async () => {
    setRunState('running');
    setResult(null);
    setErrorMsg(null);
    setProgress(0);

    // Simulate progressive progress while waiting
    const interval = setInterval(() => {
      setProgress((p) => Math.min(p + 2, 90));
    }, 600);

    try {
      const resp = await fetch('/api/a11oy/v1/ouroboros/run-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      clearInterval(interval);
      setProgress(100);
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      const data: RunResult = await resp.json();
      setResult(data);
      setRunState('done');
    } catch (e: unknown) {
      clearInterval(interval);
      setProgress(0);
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setRunState('error');
    }
  }, []);

  const statusColor = (s: string) => {
    if (s === 'GREEN') return '#4ade80';
    if (s === 'RED') return '#f87171';
    if (s === 'ERROR') return '#f59e0b';
    if (s === 'running') return '#60a5fa';
    return '#6a5a8a';
  };

  const statusBg = (s: string) => {
    if (s === 'GREEN') return 'rgba(74,222,128,0.1)';
    if (s === 'RED') return 'rgba(248,113,113,0.1)';
    if (s === 'ERROR') return 'rgba(245,158,11,0.1)';
    if (s === 'running') return 'rgba(96,165,250,0.1)';
    return 'rgba(106,90,138,0.1)';
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0a0a0a',
        color: '#e8e0f0',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        padding: '2rem 1.5rem',
      }}
    >
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '0.5rem' }}>
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '0.7rem',
              color: '#c9b787',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}
          >
            a11oy · ouroboros runner
          </span>
        </div>
        <h1
          style={{
            fontFamily: 'Georgia, serif',
            fontSize: '2rem',
            fontWeight: 700,
            color: '#c9b787',
            margin: '0 0 0.5rem 0',
            letterSpacing: '-0.01em',
          }}
        >
          Ouroboros Run-All
        </h1>
        <p style={{ color: '#a090c0', fontSize: '0.9rem', margin: '0 0 0.25rem 0' }}>
          32-module self-test suite · Ouroboros Thesis v14 through v19.0
        </p>
        <p style={{ color: '#6a5a8a', fontSize: '0.8rem', margin: '0 0 2rem 0' }}>
          Source:{' '}
          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#c9b787' }}>
            OUROBOROS_RUN_ALL.py
          </span>{' '}
          · Author: Lutar, Stephen P. — ORCID 0009-0001-0110-4173 · DOI: 10.5281/zenodo.19944926
        </p>

        {/* Module count chips */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
          {[
            { label: '32', desc: 'Modules', color: '#c9b787' },
            { label: 'v14–v19.0', desc: 'Thesis versions', color: '#60a5fa' },
            { label: 'stdlib only', desc: 'No pip installs', color: '#4ade80' },
          ].map((chip) => (
            <div
              key={chip.label}
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(201,183,135,0.2)',
                borderRadius: 10,
                padding: '0.65rem 1.1rem',
              }}
            >
              <div
                style={{
                  fontSize: '1.1rem',
                  fontWeight: 700,
                  color: chip.color,
                  fontFamily: 'JetBrains Mono, monospace',
                }}
              >
                {chip.label}
              </div>
              <div style={{ fontSize: '0.72rem', color: '#a090c0' }}>{chip.desc}</div>
            </div>
          ))}
        </div>

        {/* Run button */}
        <div style={{ marginBottom: '2rem' }}>
          <button
            onClick={runTests}
            disabled={runState === 'running'}
            style={{
              background: runState === 'running' ? 'rgba(201,183,135,0.15)' : '#c9b787',
              color: runState === 'running' ? '#c9b787' : '#0a0a0a',
              border: '1px solid rgba(201,183,135,0.4)',
              borderRadius: 8,
              padding: '0.65rem 1.75rem',
              fontSize: '0.9rem',
              fontWeight: 700,
              cursor: runState === 'running' ? 'not-allowed' : 'pointer',
              fontFamily: 'Inter, sans-serif',
              transition: 'all 0.15s',
            }}
          >
            {runState === 'running' ? '⏳ Running…' : runState === 'done' ? '🔄 Run Again' : '▶ Run All 32 Modules'}
          </button>
        </div>

        {/* Progress bar */}
        {runState === 'running' && (
          <div style={{ marginBottom: '2rem' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '0.4rem',
                fontSize: '0.78rem',
                color: '#a090c0',
              }}
            >
              <span>Running self-tests…</span>
              <span>{progress}%</span>
            </div>
            <div
              style={{
                height: 6,
                background: 'rgba(255,255,255,0.08)',
                borderRadius: 999,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progress}%`,
                  background: 'linear-gradient(90deg, #c9b787, #60a5fa)',
                  borderRadius: 999,
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        )}

        {/* Error state */}
        {runState === 'error' && errorMsg && (
          <div
            style={{
              background: 'rgba(248,113,113,0.08)',
              border: '1px solid rgba(248,113,113,0.3)',
              borderRadius: 10,
              padding: '1rem 1.25rem',
              marginBottom: '2rem',
            }}
          >
            <div style={{ color: '#f87171', fontWeight: 600, marginBottom: '0.5rem' }}>
              ❌ Run failed
            </div>
            <pre
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.78rem',
                color: '#e8e0f0',
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {errorMsg}
            </pre>
          </div>
        )}

        {/* Results summary */}
        {runState === 'done' && result && (
          <>
            <div
              style={{
                display: 'flex',
                gap: '1rem',
                flexWrap: 'wrap',
                marginBottom: '2rem',
              }}
            >
              {[
                { label: 'Tests Run', value: result.tests_run, color: '#e8e0f0' },
                { label: 'Pass', value: result.tests_pass, color: '#4ade80' },
                { label: 'Fail', value: result.tests_fail, color: result.tests_fail > 0 ? '#f87171' : '#4ade80' },
                { label: 'Duration', value: `${result.duration_ms}ms`, color: '#60a5fa' },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(201,183,135,0.2)',
                    borderRadius: 10,
                    padding: '0.75rem 1.25rem',
                    minWidth: 120,
                  }}
                >
                  <div
                    style={{
                      fontSize: '1.4rem',
                      fontWeight: 700,
                      color: item.color,
                      fontFamily: 'JetBrains Mono, monospace',
                      lineHeight: 1,
                    }}
                  >
                    {item.value}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#a090c0', marginTop: '0.3rem' }}>
                    {item.label}
                  </div>
                </div>
              ))}
              {/* Overall verdict */}
              <div
                style={{
                  background:
                    result.tests_fail === 0
                      ? 'rgba(74,222,128,0.08)'
                      : 'rgba(248,113,113,0.08)',
                  border: `1px solid ${result.tests_fail === 0 ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)'}`,
                  borderRadius: 10,
                  padding: '0.75rem 1.25rem',
                  minWidth: 120,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: '1.1rem',
                      fontWeight: 700,
                      color: result.tests_fail === 0 ? '#4ade80' : '#f87171',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}
                  >
                    {result.tests_fail === 0 ? '✅ GREEN' : `❌ RED`}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#a090c0', marginTop: '0.3rem' }}>
                    Overall verdict
                  </div>
                </div>
              </div>
            </div>

            {/* Per-module result table */}
            <div
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(201,183,135,0.12)',
                borderRadius: 12,
                overflow: 'hidden',
                marginBottom: '2rem',
              }}
            >
              <div
                style={{
                  padding: '1rem 1.5rem',
                  borderBottom: '1px solid rgba(201,183,135,0.1)',
                  background: 'rgba(255,255,255,0.02)',
                }}
              >
                <h2
                  style={{
                    fontFamily: 'Georgia, serif',
                    fontSize: '1rem',
                    color: '#c9b787',
                    margin: 0,
                  }}
                >
                  Per-Module Results
                </h2>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                      {['#', 'Module', 'Status', 'Duration', 'DOI'].map((h) => (
                        <th
                          key={h}
                          style={{
                            textAlign: 'left',
                            padding: '0.6rem 0.85rem',
                            color: '#a090c0',
                            fontWeight: 600,
                            fontSize: '0.72rem',
                            letterSpacing: '0.05em',
                            textTransform: 'uppercase',
                            borderBottom: '1px solid rgba(201,183,135,0.12)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.receipts.map((r, idx) => (
                      <tr
                        key={r.module}
                        style={{
                          borderBottom: '1px solid rgba(255,255,255,0.04)',
                          background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                        }}
                      >
                        <td
                          style={{
                            padding: '0.5rem 0.85rem',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontSize: '0.72rem',
                            color: '#6a5a8a',
                          }}
                        >
                          {idx + 1}
                        </td>
                        <td style={{ padding: '0.5rem 0.85rem' }}>
                          <span
                            style={{
                              fontFamily: 'JetBrains Mono, monospace',
                              fontSize: '0.78rem',
                              color: '#c9b787',
                            }}
                          >
                            {r.module}
                          </span>
                          {r.error && (
                            <div
                              style={{
                                fontSize: '0.7rem',
                                color: '#f59e0b',
                                marginTop: '0.1rem',
                              }}
                            >
                              {r.error}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '0.5rem 0.85rem', whiteSpace: 'nowrap' }}>
                          <span
                            style={{
                              fontFamily: 'JetBrains Mono, monospace',
                              fontSize: '0.7rem',
                              color: statusColor(r.status),
                              background: statusBg(r.status),
                              padding: '0.2rem 0.55rem',
                              borderRadius: 999,
                              border: `1px solid ${statusColor(r.status)}40`,
                            }}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: '0.5rem 0.85rem',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontSize: '0.72rem',
                            color: '#a090c0',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.duration_ms > 0 ? `${r.duration_ms}ms` : '—'}
                        </td>
                        <td
                          style={{
                            padding: '0.5rem 0.85rem',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontSize: '0.68rem',
                            color: '#6a5a8a',
                          }}
                        >
                          {r.doi ? (
                            <a
                              href={`https://doi.org/${r.doi}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: '#60a5fa', textDecoration: 'none' }}
                            >
                              {r.doi}
                            </a>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* Idle state: show module list */}
        {runState === 'idle' && (
          <div
            style={{
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(201,183,135,0.12)',
              borderRadius: 12,
              overflow: 'hidden',
              marginBottom: '2rem',
            }}
          >
            <div
              style={{
                padding: '1rem 1.5rem',
                borderBottom: '1px solid rgba(201,183,135,0.1)',
              }}
            >
              <h2
                style={{
                  fontFamily: 'Georgia, serif',
                  fontSize: '1rem',
                  color: '#c9b787',
                  margin: 0,
                }}
              >
                32 Modules (click Run to execute)
              </h2>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '0.5rem',
                padding: '1rem 1.5rem',
              }}
            >
              {MODULES.map((m, idx) => (
                <div
                  key={m}
                  style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: '0.75rem',
                    color: '#a090c0',
                    padding: '0.35rem 0.6rem',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: 6,
                    border: '1px solid rgba(255,255,255,0.05)',
                  }}
                >
                  <span style={{ color: '#6a5a8a', marginRight: '0.4rem' }}>
                    {String(idx + 1).padStart(2, '0')}.
                  </span>
                  {m}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            borderTop: '1px solid rgba(255,255,255,0.06)',
            paddingTop: '1rem',
            display: 'flex',
            gap: '1.5rem',
            flexWrap: 'wrap',
          }}
        >
          <a
            href="/api/a11oy/v1/ouroboros/run-all"
            style={{ fontSize: '0.75rem', color: '#c9b787', textDecoration: 'none' }}
          >
            POST /api/a11oy/v1/ouroboros/run-all
          </a>
          <span style={{ fontSize: '0.75rem', color: '#6a5a8a' }}>
            Apache-2.0 · Lutar, Stephen P. — ORCID 0009-0001-0110-4173
          </span>
        </div>
      </div>
    </div>
  );
}
