/**
 * Amaru (conduit) /thesis — TH1→TH8 lineage ribbon surface.
 *
 * Amaru is the Andean ouroboros artifact; it hosts the only first-class
 * TH1→TH8 lineage ribbon. The other six shipped artifacts surface the
 * lineage as a single panel inside their GovernancePanels; this page is the
 * canonical render.
 *
 * Author: Stephen P. Lutar — SZL Holdings — ORCID 0009-0001-0110-4173
 */
import { Layout } from '@/components/layout';
import { THESIS_LINEAGE, THESIS_PAPERS, thesisPaperSummary } from '@szl-holdings/szl-doctrine';

const GOLD = '#c9b787';
const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';

function StatusDot({ status }: { status: string }) {
  const ok =
    status.includes('published') || status.includes('closed') || status.includes('complete');
  const partial = status.includes('partial') || status.includes('skeleton');
  const color = ok ? '#7fb893' : partial ? GOLD : '#888';
  return (
    <span
      style={{
        display: 'inline-block',
        width: 6,
        height: 6,
        borderRadius: 999,
        background: color,
        marginRight: 6,
      }}
    />
  );
}

function paperAnchor(key: string) {
  return `paper-${key.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
}

function PaperCard({ paperKey }: { paperKey: 'TH1-TH3' | 'TH4-TH7' | 'TH8-GLR' }) {
  const paper = THESIS_PAPERS.find((p) => p.key === paperKey)!;
  const s = thesisPaperSummary(paper);
  return (
    <div
      id={paperAnchor(paper.key)}
      style={{
        border: '1px solid rgba(201,183,135,0.18)',
        background: 'rgba(201,183,135,0.03)',
        padding: 16,
        borderRadius: 4,
        scrollMarginTop: 80,
      }}
    >
      <div
        style={{
          fontFamily: MONO,
          fontSize: 10,
          letterSpacing: '0.18em',
          color: GOLD,
          textTransform: 'uppercase',
          marginBottom: 8,
        }}
      >
        {s.paperKey} · {s.versionText}
      </div>
      <div style={{ color: '#f5f5f5', fontSize: 14, fontWeight: 500, marginBottom: 6 }}>
        {paper.title}
      </div>
      <div style={{ color: '#aaa', fontSize: 11, marginBottom: 10 }}>
        <StatusDot status={paper.status} />
        {s.statusText}
      </div>
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 10 }}>
        {paper.theorems.map((th) => (
          <div
            key={th.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '52px 1fr auto',
              gap: 8,
              fontSize: 11,
              padding: '3px 0',
              fontFamily: MONO,
              color: '#cfcfcf',
            }}
          >
            <span style={{ color: GOLD }}>{th.id}</span>
            <span style={{ color: '#ededed' }}>{th.name}</span>
            <span style={{ color: th.proofStatus.includes('closed') || th.proofStatus.includes('published') ? '#7fb893' : '#d4a853' }}>
              {th.proofStatus}
            </span>
          </div>
        ))}
      </div>
      <a
        href={paper.doiUrl}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'inline-block',
          marginTop: 12,
          color: GOLD,
          fontFamily: MONO,
          fontSize: 10,
          letterSpacing: '0.12em',
          textDecoration: 'none',
          borderBottom: `1px dotted ${GOLD}`,
        }}
      >
        DOI {s.doiText} ↗
      </a>
    </div>
  );
}

export default function AmaruThesisPage() {
  const { audit, arxiv, zenodo } = THESIS_LINEAGE;
  return (
    <Layout>
      <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto', color: '#ededed' }}>
        <header style={{ marginBottom: 28 }}>
          <div
            style={{
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: '0.22em',
              color: GOLD,
              textTransform: 'uppercase',
              marginBottom: 8,
            }}
          >
            Amaru · Thesis lineage
          </div>
          <h1 style={{ fontSize: 28, margin: 0, color: '#f5f5f5', fontWeight: 600 }}>
            TH1 → TH8 — full proof chain
          </h1>
          <p style={{ marginTop: 10, fontSize: 13, color: '#aaa', maxWidth: 720 }}>
            The Andean ouroboros surfaces the canonical paper lineage from the SZL Zenodo
            community. Every theorem listed below resolves to a section in the published PDF,
            an entry in the doctrine evidence ledger, and (for TH8) a Lean 4 file in
            <span style={{ fontFamily: MONO, color: GOLD }}> szl-holdings/lutar-lean</span>.
          </p>
          <nav
            aria-label="TH1→TH8 ribbon"
            style={{
              marginTop: 16,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: '0.12em',
            }}
          >
            {THESIS_PAPERS.flatMap((p) =>
              p.theorems.map((th) => (
                <a
                  key={th.id}
                  href={`#${paperAnchor(p.key)}`}
                  title={`${th.name} — see ${p.key} section`}
                  style={{
                    padding: '4px 8px',
                    border: `1px solid ${GOLD}`,
                    borderRadius: 3,
                    color: GOLD,
                    textDecoration: 'none',
                    background: 'rgba(201,183,135,0.04)',
                  }}
                >
                  {th.id}
                </a>
              )),
            )}
          </nav>
        </header>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: 14,
            marginBottom: 24,
          }}
        >
          <PaperCard paperKey="TH1-TH3" />
          <PaperCard paperKey="TH4-TH7" />
          <PaperCard paperKey="TH8-GLR" />
        </div>

        <section
          style={{
            border: '1px solid rgba(255,255,255,0.06)',
            background: '#0e0e0e',
            padding: 18,
            borderRadius: 4,
          }}
        >
          <div
            style={{
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: '0.18em',
              color: GOLD,
              textTransform: 'uppercase',
              marginBottom: 14,
            }}
          >
            Fly High V6 audit — live counters
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 12,
              fontSize: 12,
              fontFamily: MONO,
              color: '#cfcfcf',
            }}
          >
            <div>Doctrine · <span style={{ color: GOLD }}>{audit.doctrine}</span></div>
            <div>P0 fixes · <span style={{ color: '#7fb893' }}>{audit.p0Fixes}</span></div>
            <div>Beautify avg · <span style={{ color: '#7fb893' }}>{audit.beautifyAvg}</span></div>
            <div>TH8 theorems · <span style={{ color: GOLD }}>{audit.leanTheorems}</span></div>
            <div>TH8 sorries open · <span style={{ color: audit.leanSorriesOpen === 0 ? '#7fb893' : '#d4a853' }}>{audit.leanSorriesOpen}</span></div>
            <div>Closed in mirror · <span style={{ color: '#7fb893' }}>{audit.leanSorriesClosed.length}</span></div>
            <div>Citation hardening · <span style={{ color: '#7fb893' }}>{audit.citationHardening}</span></div>
            <div>Mirror updated · <span style={{ color: '#888' }}>{audit.updatedAt}</span></div>
          </div>
          <div
            style={{
              marginTop: 14,
              paddingTop: 14,
              borderTop: '1px solid rgba(255,255,255,0.04)',
              display: 'flex',
              gap: 16,
              flexWrap: 'wrap',
              fontSize: 11,
              fontFamily: MONO,
              color: '#888',
            }}
          >
            <span>arXiv: <span style={{ color: '#cfcfcf' }}>{arxiv.status}</span> → <a href={arxiv.searchUrl} style={{ color: GOLD }} target="_blank" rel="noopener noreferrer">{arxiv.targetVenue}</a></span>
            <span>Zenodo: <span style={{ color: '#cfcfcf' }}>{zenodo.status}</span> ({zenodo.targetVersion}) → <a href={zenodo.doiUrl} style={{ color: GOLD }} target="_blank" rel="noopener noreferrer">DOI</a></span>
            <span style={{ color: zenodo.oneWayDoor ? '#d4a853' : '#7fb893' }}>
              one-way doors: {zenodo.oneWayDoor || arxiv.oneWayDoor ? 'PENDING' : 'PASSED'}
            </span>
          </div>
        </section>

        <footer style={{ marginTop: 24, fontSize: 11, color: '#666', fontFamily: MONO }}>
          © 2026 Stephen P. Lutar — SZL Holdings — ORCID 0009-0001-0110-4173
        </footer>
      </div>
    </Layout>
  );
}
