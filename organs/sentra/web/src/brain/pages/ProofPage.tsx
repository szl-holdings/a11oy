import { useState } from 'react';
import { loadProofEntries, clearProofLedger } from '../data/proofLedger';
import type { ProofEntry } from '../data/proofLedger';
import { CONSTITUTION_VERSION, ACTIVE_CONSTITUTION } from '../data/a11oyConstitution';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

export function ProofPage() {
  const [entries, setEntries] = useState<ProofEntry[]>(() => loadProofEntries());
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const refresh = () => setEntries(loadProofEntries());

  const OUTCOME_CONFIG: Record<ProofEntry['outcome'], { color: string; label: string; glyph: string }> = {
    optimal: { color: '#10b981', label: 'Optimal', glyph: '✓' },
    'sub-optimal': { color: '#f59e0b', label: 'Sub-optimal', glyph: '◎' },
    infeasible: { color: '#ef4444', label: 'Infeasible', glyph: '✗' },
    blocked: { color: '#ef4444', label: 'Blocked', glyph: '⬡' },
  };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 6 }}>
          ◉ PROOF LEDGER
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.5rem' }}>Proof Ledger</h1>
            <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
              Every ROSIE optimizer run produces a signed proof entry. {entries.length} entries recorded.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={refresh}
              style={{
                padding: '0.5rem 1rem',
                background: 'rgba(6,182,212,0.06)',
                border: '1px solid rgba(6,182,212,0.2)',
                borderRadius: 8, color: '#06b6d4',
                fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Refresh
            </button>
            {entries.length > 0 && (
              <button
                onClick={() => { clearProofLedger(); refresh(); }}
                style={{
                  padding: '0.5rem 1rem',
                  background: 'rgba(239,68,68,0.06)',
                  border: '1px solid rgba(239,68,68,0.15)',
                  borderRadius: 8, color: '#f87171',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >
                Clear Ledger
              </button>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '1.5rem' }}>
        {/* Entries */}
        <div>
          {entries.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '4rem',
              background: 'rgba(15,23,42,0.4)',
              border: '1px solid rgba(6,182,212,0.08)',
              borderRadius: 12,
            }}>
              <div style={{ fontSize: 32, marginBottom: '1rem' }}>◉</div>
              <h3 style={{ fontSize: 16, color: '#94a3b8', fontWeight: 600, marginBottom: '0.5rem' }}>
                No proof entries yet
              </h3>
              <p style={{ fontSize: 13, color: '#475569', margin: 0 }}>
                Run the Optimizer to generate proof entries. Each solve writes a signed entry to this ledger.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {entries.map(entry => {
                const oc = OUTCOME_CONFIG[entry.outcome];
                const isExpanded = expandedId === entry.id;
                return (
                  <div key={entry.id} style={{
                    background: 'rgba(15,23,42,0.6)',
                    border: `1px solid ${isExpanded ? `${oc.color}33` : 'rgba(6,182,212,0.1)'}`,
                    borderRadius: 12, overflow: 'hidden',
                  }}>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      style={{
                        width: '100%', padding: '1rem 1.25rem',
                        background: 'transparent', border: 'none',
                        cursor: 'pointer', textAlign: 'left',
                        display: 'flex', alignItems: 'center', gap: '1rem',
                      }}
                    >
                      {/* Outcome badge */}
                      <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: `${oc.color}15`,
                        border: `1.5px solid ${oc.color}44`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 16, color: oc.color, flexShrink: 0,
                      }}>
                        {oc.glyph}
                      </div>

                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0' }}>
                            {entry.problemLabel}
                          </span>
                          <span style={{ fontSize: 12, color: '#475569' }}>{timeAgo(entry.timestamp)}</span>
                        </div>
                        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 12, color: oc.color, fontWeight: 600 }}>{oc.label}</span>
                          <span style={{ fontSize: 12, color: '#475569' }}>
                            Score: {(entry.objectiveScore * 100).toFixed(1)}%
                          </span>
                          <span style={{ fontSize: 12, color: entry.guardrailsViolated > 0 ? '#f87171' : '#10b981' }}>
                            Guardrails: {entry.guardrailsChecked - entry.guardrailsViolated}/{entry.guardrailsChecked} passed
                          </span>
                          <span style={{ fontSize: 12, color: '#475569' }}>{entry.solveTimeMs}ms</span>
                        </div>
                      </div>

                      <span style={{ color: '#475569', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>
                        ↓
                      </span>
                    </button>

                    {isExpanded && (
                      <div style={{
                        padding: '1rem 1.25rem 1.25rem',
                        borderTop: '1px solid rgba(6,182,212,0.08)',
                      }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                          <div>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>PROOF ID</div>
                            <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                              {entry.id}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>INPUTS HASH</div>
                            <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                              {entry.inputsHash}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>CONSTITUTION VERSION</div>
                            <div style={{ fontSize: 12, color: '#c9b787', fontWeight: 600 }}>v{entry.constitutionVersion}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>CONSTITUTION SOURCE</div>
                            <div style={{ fontSize: 12, fontWeight: 600,
                              color: entry.constitutionSource === 'live' ? '#10b981' : entry.constitutionSource === 'fallback' ? '#f59e0b' : '#64748b',
                            }}>
                              {entry.constitutionSource ?? 'seed'}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>TIMESTAMP</div>
                            <div style={{ fontSize: 12, color: '#94a3b8' }}>
                              {new Date(entry.timestamp).toLocaleString()}
                            </div>
                          </div>
                        </div>
                        {entry.notes && (
                          <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 6 }}>
                            <div style={{ fontSize: 11, color: '#475569', marginBottom: 3 }}>NOTES / VIOLATIONS</div>
                            <div style={{ fontSize: 12, color: '#f87171' }}>{entry.notes}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Sidebar: Constitution Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Constitution Status */}
          <div style={{
            background: 'rgba(201, 183, 135, 0.04)',
            border: '1px solid rgba(201, 183, 135, 0.15)',
            borderRadius: 12, padding: '1.25rem',
          }}>
            <div style={{ fontSize: 11, color: '#c9b787', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              ◆ ACTIVE CONSTITUTION
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#c9b787', marginBottom: '0.25rem' }}>
              v{CONSTITUTION_VERSION}
            </div>
            <div style={{ fontSize: 12, color: '#475569', marginBottom: '1rem' }}>
              {ACTIVE_CONSTITUTION.length} clauses active
            </div>
            {ACTIVE_CONSTITUTION.map(c => (
              <div key={c.id} style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.35rem 0',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                  background: c.binding === 'inviolable' ? '#ef4444'
                    : c.binding === 'strong' ? '#f59e0b' : '#06b6d4',
                }} />
                <span style={{ fontSize: 11, color: '#64748b', flex: 1 }}>{c.id}</span>
                <span style={{
                  fontSize: 10,
                  padding: '0.1rem 0.35rem',
                  background: c.binding === 'inviolable' ? 'rgba(239,68,68,0.08)'
                    : c.binding === 'strong' ? 'rgba(245,158,11,0.08)' : 'rgba(6,182,212,0.08)',
                  border: `1px solid ${c.binding === 'inviolable' ? 'rgba(239,68,68,0.2)' : c.binding === 'strong' ? 'rgba(245,158,11,0.2)' : 'rgba(6,182,212,0.15)'}`,
                  borderRadius: 10,
                  color: c.binding === 'inviolable' ? '#f87171' : c.binding === 'strong' ? '#fbbf24' : '#67e8f9',
                }}>{c.binding}</span>
              </div>
            ))}
          </div>

          {/* Stats */}
          {entries.length > 0 && (
            <div style={{
              background: 'rgba(15,23,42,0.6)',
              border: '1px solid rgba(6,182,212,0.12)',
              borderRadius: 12, padding: '1.25rem',
            }}>
              <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
                LEDGER STATS
              </div>
              {[
                { label: 'Total solves', value: entries.length },
                { label: 'Optimal results', value: entries.filter(e => e.outcome === 'optimal').length },
                { label: 'Blocked (guardrail)', value: entries.filter(e => e.outcome === 'blocked').length },
                { label: 'Avg objective score', value: `${(entries.reduce((s, e) => s + e.objectiveScore, 0) / entries.length * 100).toFixed(1)}%` },
                { label: 'Avg solve time', value: `${Math.round(entries.reduce((s, e) => s + e.solveTimeMs, 0) / entries.length)}ms` },
              ].map(s => (
                <div key={s.label} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '0.35rem 0',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  fontSize: 12,
                }}>
                  <span style={{ color: '#475569' }}>{s.label}</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{s.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
