import { useState, useMemo, useEffect } from 'react';
import { LEARNING_LOOP_STATS } from '../data/researchLibrary';
import type { ResearchOrg, ResearchTag } from '../data/researchLibrary';
import { getMergedResearchLibrary } from '../data/mergedResearch';

const _ALL_ORGS: ResearchOrg[] = ['Anthropic', 'OpenAI', 'DeepMind', 'NIST', 'DARPA', 'NSA', 'Hugging Face', 'MIT', 'Stanford', 'MITRE', 'Oxford', 'NVIDIA'];
const ALL_TAGS: ResearchTag[] = ['alignment', 'safety', 'governance', 'optimization', 'robustness', 'interpretability', 'multi-agent', 'constitutional-ai', 'red-teaming', 'rl', 'evaluation', 'autonomy', 'ising', 'quantum'];

const ORG_COLORS: Record<ResearchOrg, string> = {
  'Anthropic': '#d97706',
  'OpenAI': '#10b981',
  'DeepMind': '#06b6d4',
  'NIST': '#8b5cf6',
  'DARPA': '#ef4444',
  'NSA': '#64748b',
  'Hugging Face': '#f59e0b',
  'MIT': '#ec4899',
  'Stanford': '#dc2626',
  'MITRE': '#0ea5e9',
  'Oxford': '#a78bfa',
  'NVIDIA': '#76b900',
};

export function ResearchPage() {
  const [selectedOrgs, setSelectedOrgs] = useState<Set<ResearchOrg>>(new Set());
  const [selectedTags, setSelectedTags] = useState<Set<ResearchTag>>(new Set());
  const [selectedYears, setSelectedYears] = useState<Set<number>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showLearningLoop, setShowLearningLoop] = useState(false);
  // Merged view (static seed + mutable evolved entries) is computed in
  // component state, refreshed when the incident pipeline writes a new
  // entry or when storage changes from another tab.
  const [RESEARCH_LIBRARY, setLibrary] = useState(() => getMergedResearchLibrary());
  useEffect(() => {
    const refresh = () => setLibrary(getMergedResearchLibrary());
    window.addEventListener('storage', refresh);
    window.addEventListener('sentra-brain-updated', refresh);
    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener('sentra-brain-updated', refresh);
    };
  }, []);

  const allYears = useMemo(() =>
    [...new Set(RESEARCH_LIBRARY.map(e => e.year))].sort((a, b) => b - a),
  [RESEARCH_LIBRARY]);

  const filteredEntries = useMemo(() => {
    return RESEARCH_LIBRARY.filter(e => {
      if (selectedOrgs.size > 0 && !selectedOrgs.has(e.org)) return false;
      if (selectedTags.size > 0 && !e.tags.some(t => selectedTags.has(t))) return false;
      if (selectedYears.size > 0 && !selectedYears.has(e.year)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!e.title.toLowerCase().includes(q) && !e.distillation.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [selectedOrgs, selectedTags, selectedYears, searchQuery]);

  const topInfluenced = RESEARCH_LIBRARY
    .filter(e => LEARNING_LOOP_STATS.topInfluenced.includes(e.id))
    .sort((a, b) => (b.influencedSolves ?? 0) - (a.influencedSolves ?? 0));

  const toggleOrg = (org: ResearchOrg) => {
    setSelectedOrgs(prev => {
      const s = new Set(prev);
      s.has(org) ? s.delete(org) : s.add(org);
      return s;
    });
  };

  const toggleTag = (tag: ResearchTag) => {
    setSelectedTags(prev => {
      const s = new Set(prev);
      s.has(tag) ? s.delete(tag) : s.add(tag);
      return s;
    });
  };

  const toggleYear = (year: number) => {
    setSelectedYears(prev => {
      const s = new Set(prev);
      s.has(year) ? s.delete(year) : s.add(year);
      return s;
    });
  };

  const activeOrgs = Array.from(new Set(RESEARCH_LIBRARY.map(e => e.org))) as ResearchOrg[];

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '2rem 1.5rem 4rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.12em', fontWeight: 600, marginBottom: 6 }}>
          ◆ RESEARCH LIBRARY
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#e2e8f0', margin: '0 0 0.5rem' }}>
              What ROSIE Has Learned
            </h1>
            <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>
              {RESEARCH_LIBRARY.length} curated research entries · filtered to {filteredEntries.length} results
            </p>
          </div>
          <button
            onClick={() => setShowLearningLoop(v => !v)}
            style={{
              padding: '0.5rem 1rem',
              background: showLearningLoop ? 'rgba(6,182,212,0.1)' : 'rgba(15,23,42,0.6)',
              border: `1px solid ${showLearningLoop ? 'rgba(6,182,212,0.3)' : 'rgba(6,182,212,0.12)'}`,
              borderRadius: 8, color: '#06b6d4',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            ◉ {showLearningLoop ? 'Hide' : 'Show'} Learning Loop
          </button>
        </div>
      </div>

      {/* Learning Loop Panel */}
      {showLearningLoop && (
        <div style={{
          background: 'rgba(6, 182, 212, 0.04)',
          border: '1px solid rgba(6, 182, 212, 0.2)',
          borderRadius: 12, padding: '1.5rem',
          marginBottom: '1.5rem',
        }}>
          <div style={{ fontSize: 11, color: '#06b6d4', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '1rem' }}>
            ◉ LEARNING LOOP — INGEST STATUS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
            {[
              { label: 'Total Entries', value: LEARNING_LOOP_STATS.totalEntries.toString() },
              { label: 'Last Ingested', value: '2026-05-04' },
              { label: 'Next Ingest', value: '2026-06-04' },
              { label: 'Cadence', value: LEARNING_LOOP_STATS.ingestCadence },
            ].map(m => (
              <div key={m.label} style={{
                padding: '0.75rem 1rem',
                background: 'rgba(6,182,212,0.06)',
                border: '1px solid rgba(6,182,212,0.12)',
                borderRadius: 8,
              }}>
                <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#06b6d4' }}>{m.value}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '0.75rem' }}>
            TOP ENTRIES THAT INFLUENCED RECENT SOLVES
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {topInfluenced.map((e, i) => (
              <div key={e.id} style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                padding: '0.4rem 0.75rem',
                background: 'rgba(6,182,212,0.04)',
                border: '1px solid rgba(6,182,212,0.08)',
                borderRadius: 6,
              }}>
                <span style={{ fontSize: 11, color: '#06b6d4', fontWeight: 700, width: 16 }}>#{i + 1}</span>
                <span style={{ fontSize: 12, color: '#94a3b8', flex: 1 }}>{e.title}</span>
                <span style={{
                  fontSize: 11,
                  padding: '0.15rem 0.5rem',
                  background: `${ORG_COLORS[e.org]}18`,
                  border: `1px solid ${ORG_COLORS[e.org]}33`,
                  borderRadius: 20, color: ORG_COLORS[e.org],
                }}>{e.org}</span>
                <span style={{ fontSize: 11, color: '#64748b' }}>{e.influencedSolves} solves</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '1.5rem' }}>
        {/* Filters */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Search */}
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: '1px solid rgba(6,182,212,0.12)',
            borderRadius: 12, padding: '1rem',
          }}>
            <input
              type="text"
              placeholder="Search entries..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%', padding: '0.5rem 0.75rem',
                background: 'rgba(6,182,212,0.06)',
                border: '1px solid rgba(6,182,212,0.15)',
                borderRadius: 6, color: '#e2e8f0', fontSize: 13,
                outline: 'none',
              }}
            />
          </div>

          {/* Org Filter */}
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: '1px solid rgba(6,182,212,0.12)',
            borderRadius: 12, padding: '1rem',
          }}>
            <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              ORGANIZATION
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {activeOrgs.map(org => {
                const count = RESEARCH_LIBRARY.filter(e => e.org === org).length;
                const isSelected = selectedOrgs.has(org);
                return (
                  <button
                    key={org}
                    onClick={() => toggleOrg(org)}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '0.35rem 0.6rem',
                      background: isSelected ? `${ORG_COLORS[org]}12` : 'transparent',
                      border: isSelected ? `1px solid ${ORG_COLORS[org]}33` : '1px solid transparent',
                      borderRadius: 6, cursor: 'pointer',
                    }}
                  >
                    <span style={{ fontSize: 12, color: isSelected ? ORG_COLORS[org] : '#64748b', fontWeight: isSelected ? 600 : 400 }}>
                      {org}
                    </span>
                    <span style={{
                      fontSize: 11,
                      padding: '0.1rem 0.4rem',
                      background: 'rgba(255,255,255,0.05)',
                      borderRadius: 10, color: '#475569',
                    }}>{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tag Filter */}
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: '1px solid rgba(6,182,212,0.12)',
            borderRadius: 12, padding: '1rem',
          }}>
            <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              TAGS
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
              {ALL_TAGS.filter(tag => RESEARCH_LIBRARY.some(e => e.tags.includes(tag))).map(tag => {
                const isSelected = selectedTags.has(tag);
                return (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    style={{
                      padding: '0.2rem 0.6rem',
                      background: isSelected ? 'rgba(6,182,212,0.15)' : 'rgba(255,255,255,0.04)',
                      border: isSelected ? '1px solid rgba(6,182,212,0.4)' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 20, cursor: 'pointer',
                      fontSize: 11, color: isSelected ? '#06b6d4' : '#64748b',
                      fontWeight: isSelected ? 600 : 400,
                    }}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          {/* Year Filter */}
          <div style={{
            background: 'rgba(15,23,42,0.6)',
            border: '1px solid rgba(6,182,212,0.12)',
            borderRadius: 12, padding: '1rem',
          }}>
            <div style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '0.75rem' }}>
              YEAR
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
              {allYears.map(year => {
                const isSelected = selectedYears.has(year);
                const count = RESEARCH_LIBRARY.filter(e => e.year === year).length;
                return (
                  <button
                    key={year}
                    onClick={() => toggleYear(year)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.3rem',
                      padding: '0.2rem 0.6rem',
                      background: isSelected ? 'rgba(124,58,237,0.15)' : 'rgba(255,255,255,0.04)',
                      border: isSelected ? '1px solid rgba(124,58,237,0.4)' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 20, cursor: 'pointer',
                      fontSize: 11, color: isSelected ? '#a78bfa' : '#64748b',
                      fontWeight: isSelected ? 600 : 400,
                    }}
                  >
                    {year}
                    <span style={{ fontSize: 10, color: isSelected ? '#a78bfa' : '#475569' }}>{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

            {(selectedOrgs.size > 0 || selectedTags.size > 0 || selectedYears.size > 0 || searchQuery) && (
              <button
                onClick={() => { setSelectedOrgs(new Set()); setSelectedTags(new Set()); setSelectedYears(new Set()); setSearchQuery(''); }}
                style={{
                  marginTop: '0.75rem', width: '100%', padding: '0.4rem',
                  background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
                  borderRadius: 6, color: '#f87171', fontSize: 12, cursor: 'pointer',
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Entry List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {filteredEntries.map(entry => {
            const isExpanded = expandedId === entry.id;
            return (
              <div
                key={entry.id}
                style={{
                  background: 'rgba(15,23,42,0.6)',
                  border: `1px solid ${isExpanded ? 'rgba(6,182,212,0.25)' : 'rgba(6,182,212,0.1)'}`,
                  borderRadius: 12, overflow: 'hidden',
                  transition: 'border-color 0.15s',
                }}
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  style={{
                    width: '100%', padding: '1rem 1.25rem',
                    background: 'transparent', border: 'none',
                    cursor: 'pointer', textAlign: 'left',
                    display: 'flex', alignItems: 'flex-start', gap: '1rem',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', marginBottom: '0.5rem' }}>
                      <span style={{
                        padding: '0.15rem 0.6rem',
                        background: `${ORG_COLORS[entry.org]}18`,
                        border: `1px solid ${ORG_COLORS[entry.org]}33`,
                        borderRadius: 20, fontSize: 11,
                        color: ORG_COLORS[entry.org], fontWeight: 600,
                        whiteSpace: 'nowrap', flexShrink: 0,
                      }}>{entry.org}</span>
                      <span style={{
                        padding: '0.15rem 0.5rem',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderRadius: 20, fontSize: 11, color: '#475569',
                        whiteSpace: 'nowrap', flexShrink: 0,
                      }}>{entry.year}</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0', marginBottom: '0.4rem', lineHeight: 1.4 }}>
                      {entry.title}
                    </div>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {entry.tags.map(tag => (
                        <span key={tag} style={{
                          padding: '0.1rem 0.45rem',
                          background: 'rgba(6,182,212,0.06)',
                          border: '1px solid rgba(6,182,212,0.12)',
                          borderRadius: 20, fontSize: 10, color: '#67e8f9',
                        }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.35rem', flexShrink: 0 }}>
                    {entry.influencedSolves !== undefined && entry.influencedSolves > 0 && (
                      <span style={{
                        padding: '0.15rem 0.5rem',
                        background: 'rgba(6,182,212,0.08)',
                        border: '1px solid rgba(6,182,212,0.2)',
                        borderRadius: 20, fontSize: 11, color: '#06b6d4',
                        whiteSpace: 'nowrap',
                      }}>↑ {entry.influencedSolves} solves</span>
                    )}
                    <span style={{ fontSize: 18, color: '#475569', transition: 'transform 0.15s', transform: isExpanded ? 'rotate(180deg)' : 'none' }}>
                      ↓
                    </span>
                  </div>
                </button>
                {isExpanded && (
                  <div style={{
                    padding: '0 1.25rem 1.25rem',
                    borderTop: '1px solid rgba(6,182,212,0.08)',
                  }}>
                    <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.75, margin: '1rem 0' }}>
                      {entry.distillation}
                    </p>
                    <a
                      href={entry.link}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
                        padding: '0.4rem 0.9rem',
                        background: 'rgba(6,182,212,0.06)',
                        border: '1px solid rgba(6,182,212,0.2)',
                        borderRadius: 6, fontSize: 12, color: '#06b6d4',
                        textDecoration: 'none', fontWeight: 600,
                      }}
                    >
                      View paper →
                    </a>
                  </div>
                )}
              </div>
            );
          })}
          {filteredEntries.length === 0 && (
            <div style={{
              textAlign: 'center', padding: '3rem',
              background: 'rgba(15,23,42,0.4)',
              border: '1px solid rgba(6,182,212,0.08)',
              borderRadius: 12,
            }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>◆</div>
              <div style={{ fontSize: 14, color: '#64748b' }}>No entries match the current filters.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
