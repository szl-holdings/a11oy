import { useState, useEffect, useRef } from 'react';
import { createSpaceRun, streamRunOutput, validateProof } from '../lib/atelier-runtime';

const T = {
  bg: '#0a0a0a', border: 'rgba(255,255,255,0.08)', text: '#f5f5f5',
  textDim: '#8a8a8a', textMuted: '#5e5e5e', accent: '#c9b787',
  mono: 'var(--font-mono,ui-monospace,monospace)',
};

export interface AtelierEmbedProps {
  spaceSlug: string;
  tenantId?: string;
  height?: number;
  compact?: boolean;
  allowedOrigins?: string[];
}

export const ALLOWED_EMBED_ORIGINS: string[] = [
  'https://szl-holdings.com',
  'https://www.szl-holdings.com',
  'https://app.szl-holdings.com',
  'https://*.szl-holdings.com',
  'https://a11oy.szl-holdings.com',
  'http://localhost:3000',
  'http://localhost:4099',
  'http://localhost:4110',
  'http://localhost:4199',
  'http://localhost:5173',
  'http://localhost:5000',
  'http://localhost:8099',
  'http://localhost:80',
  'http://127.0.0.1:3000',
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5000',
];

function isOriginAllowed(origin: string, allowlist: string[]): boolean {
  if (!origin) return false;
  for (const pattern of allowlist) {
    if (pattern === origin) return true;
    if (pattern.includes('*')) {
      try {
        const url = new URL(origin);
        const patternUrl = new URL(pattern.replace('*.', ''));
        if (url.protocol !== patternUrl.protocol) continue;
        const patternHost = patternUrl.hostname;
        if (url.hostname === patternHost || url.hostname.endsWith('.' + patternHost)) {
          return true;
        }
      } catch {
        continue;
      }
    }
  }
  return false;
}

const EMBED_SPACES: Record<string, { name: string; vertical: string; color: string; description: string; runtime: string }> = {
  'maritime-routing': {
    name: 'Maritime Routing Agent',
    vertical: 'Maritime',
    color: '#7ab8d9',
    description: 'AIS-fed route optimization and ETA monitoring for SZL maritime operations.',
    runtime: 'agent-loop',
  },
  're-underwriting': {
    name: 'Real Estate Underwriting Agent',
    vertical: 'Real Estate',
    color: '#c9b787',
    description: 'Governed underwriting analysis for acquisition, covenant risk, and lease-up.',
    runtime: 'agent-loop',
  },
  'legal-discovery': {
    name: 'Legal Discovery Intelligence',
    vertical: 'Legal',
    color: '#8a8a8a',
    description: 'Privilege-preserving discovery analysis and deadline tracking.',
    runtime: 'agent-loop',
  },
  'cyber-triage': {
    name: 'Cyber Threat Triage Agent',
    vertical: 'Cyber',
    color: '#10b981',
    description: 'CVE enrichment, SIEM correlation, and containment brief generation.',
    runtime: 'agent-loop',
  },
  'platform-health': {
    name: 'A11oy Platform Health',
    vertical: 'Platform',
    color: '#5e5e5e',
    description: 'Fabric layer health, proof ledger integrity, and SLO tracking.',
    runtime: 'chat',
  },
};

const AGENT_LOOP_OUTPUTS: Record<string, string[]> = {
  'maritime-routing': [
    '⟳ Connecting to AIS Live Feed…',
    '✓ Vessel data received — VLCC Everest',
    '⟳ Calculating ETA deviation…',
    '⚠ ETA +31h delay detected at Port Rotterdam',
    '⟳ Running port standby cost model…',
    '✓ Standby cost: $2.4M/day',
    '⟳ Evaluating 3 alternative routes…',
    '✓ Route via Port Antwerp: saves $1.2M demurrage',
    '⟳ Generating proof packet…',
    '✓ Proof: sha256:c9f2e5b8a1d3e6f9…\n\nRecommendation: Reroute to Port Antwerp. Estimated saving: $1.2M. Awaiting VP Operations approval.',
  ],
  're-underwriting': [
    '⟳ Loading CoStar comparable data…',
    '✓ 6 comps loaded for 45 Park Ave',
    '⟳ Checking lender covenant thresholds…',
    '✓ Covenant check: COMPLIANT (occupancy 89% vs 85% threshold)',
    '⟳ Running cap rate compression model…',
    '⚠ Cap rate compressed 28bps since Q4 2025',
    '⟳ Updating valuation model…',
    '✓ Portfolio value: +$4.2M vs last assessment',
    '⟳ Generating proof packet…',
    '✓ Proof: sha256:a1b2c3d4e5f6a7b8…\n\nUnderwriting complete. Risk score: 0.22 (LOW). Recommendation: Proceed with acquisition. Human approval required.',
  ],
};

const EMBED_VERTICAL_MAP: Record<string, string> = {
  Maritime: 'maritime',
  'Real Estate': 'real-estate',
  Legal: 'legal',
  Platform: 'platform',
  Cyber: 'cyber',
  Defense: 'defense',
  Executive: 'executive',
};

const EMBED_CONNECTORS: Record<string, string[]> = {
  'maritime-routing': ['AIS Live Feed', 'Port Standby Cost Model'],
  're-underwriting': ['CoStar', 'Lender Covenant API'],
  'legal-discovery': ['Docket Search', 'Document Repository'],
  'cyber-triage': ['Threat Intelligence Feed', 'CVE Database', 'SIEM Events'],
  'platform-health': ['Fabric Telemetry'],
};

function EmbedRunner({ slug, vertical }: { slug: string; vertical: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  async function run() {
    setLines([]);
    setDone(false);
    setRunning(true);
    try {
      const connectors = EMBED_CONNECTORS[slug] ?? [];
      const v = EMBED_VERTICAL_MAP[vertical] ?? 'cross-vertical';
      const state = await createSpaceRun({
        spaceSlug: slug,
        vertical: v,
        connectors,
        constitutionRef: 'embed-default',
        modelPolicy: 'governed-default',
      });
      const finalState = await streamRunOutput(
        state.workcellId,
        (line) => setLines((prev) => [...prev, line]),
        { vertical: v, connectors, spaceSlug: slug },
      );
      const proof = await validateProof(finalState.workcellId, finalState.pceContractId);
      if (proof.proofRef) setLines((prev) => [...prev, `✓ Proof ref: ${proof.proofRef}`]);
    } catch (e) {
      setLines((prev) => [...prev, `✗ Run error: ${e instanceof Error ? e.message : String(e)}`]);
    } finally {
      setRunning(false);
      setDone(true);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.875rem', fontFamily: T.mono, fontSize: '0.6875rem', lineHeight: 1.7, color: T.textDim }}>
        {lines.length === 0 && !running && (
          <div style={{ color: T.textMuted, textAlign: 'center', paddingTop: '1.5rem', fontSize: '0.75rem' }}>
            Click Run to execute in governed runtime.
          </div>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{ color: l.startsWith('✓') ? '#c9b787' : l.startsWith('⚠') ? '#8a8a8a' : l.startsWith('⟳') ? '#5e5e5e' : T.text }}>
            {l}
          </div>
        ))}
        {running && <span style={{ display: 'inline-block', animation: 'pulse 1s infinite', color: T.accent }}>▌</span>}
        <div ref={bottomRef} />
      </div>
      <div style={{ padding: '0.625rem 0.875rem', borderTop: `1px solid ${T.border}`, display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button onClick={run} disabled={running}
          style={{ padding: '0.375rem 0.875rem', borderRadius: 5, fontSize: '0.6875rem', fontWeight: 500, cursor: running ? 'not-allowed' : 'pointer', background: 'rgba(201,183,135,0.1)', border: `1px solid rgba(201,183,135,0.25)`, color: T.accent, opacity: running ? 0.5 : 1 }}>
          {running ? '⟳ Running…' : '▶ Run'}
        </button>
        {done && <span style={{ fontSize: '0.5625rem', fontFamily: T.mono, color: '#c9b787' }}>✓ Proof generated</span>}
      </div>
    </div>
  );
}

export function AtelierEmbed({ spaceSlug, tenantId = 'szl', height = 340, compact = false, allowedOrigins }: AtelierEmbedProps) {
  const spaceInfo = EMBED_SPACES[spaceSlug] ?? {
    name: spaceSlug, vertical: 'Unknown', color: '#5e5e5e',
    description: 'A governed Atelier Space.', runtime: 'agent-loop',
  };

  useEffect(() => {
    const allowlist = [...ALLOWED_EMBED_ORIGINS, ...(allowedOrigins ?? [])];
    function handleMessage(e: MessageEvent) {
      if (e.data?.type === 'a11oy-space-handshake') {
        if (!isOriginAllowed(e.origin, allowlist)) {
          return;
        }
        e.source?.postMessage({ type: 'a11oy-space-ack', spaceSlug, tenantId, ready: true }, { targetOrigin: e.origin });
      }
    }
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [spaceSlug, tenantId, allowedOrigins]);

  const BASE = (import.meta.env.BASE_URL ?? '/a11oy/').replace(/\/$/, '');

  return (
    <div style={{
      background: T.bg, border: `1px solid ${T.border}`, borderRadius: 10,
      overflow: 'hidden', fontFamily: 'var(--font-sans,Inter,sans-serif)',
      height: compact ? 'auto' : height, display: 'flex', flexDirection: 'column',
      borderTop: `2px solid ${spaceInfo.color}`,
    }}>
      <div style={{ padding: compact ? '0.625rem 0.875rem' : '0.875rem 1.125rem', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0, background: 'rgba(255,255,255,0.01)' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: compact ? '0.75rem' : '0.875rem', fontWeight: 600, color: T.text, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {spaceInfo.name}
          </div>
          {!compact && (
            <div style={{ fontSize: '0.5625rem', fontFamily: T.mono, color: spaceInfo.color, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '0.125rem' }}>
              {spaceInfo.vertical} · Atelier Space
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: spaceInfo.color, boxShadow: `0 0 5px ${spaceInfo.color}` }} />
          <span style={{ fontSize: '0.5rem', fontFamily: T.mono, color: T.textMuted }}>Governed</span>
        </div>
        <a href={`${BASE}/atelier/s/${spaceSlug}`} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: '0.5rem', fontFamily: T.mono, color: T.textMuted, textDecoration: 'none', padding: '0.2rem 0.375rem', borderRadius: 3, border: `1px solid ${T.border}` }}>
          ↗ Open
        </a>
      </div>

      {!compact && (
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <EmbedRunner slug={spaceSlug} vertical={spaceInfo.vertical} />
        </div>
      )}

      {compact && (
        <div style={{ padding: '0.625rem 0.875rem' }}>
          <p style={{ fontSize: '0.75rem', color: T.textDim, margin: 0, lineHeight: 1.5 }}>{spaceInfo.description}</p>
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
            <a href={`${BASE}/atelier/s/${spaceSlug}`} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: '0.6875rem', color: spaceInfo.color, textDecoration: 'none', fontFamily: T.mono }}>
              Open in Atelier →
            </a>
          </div>
        </div>
      )}

      <div style={{ padding: '0.375rem 0.875rem', borderTop: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, background: 'rgba(255,255,255,0.01)' }}>
        <span style={{ fontSize: '0.5rem', fontFamily: T.mono, color: T.textMuted }}>Powered by</span>
        <span style={{ fontSize: '0.5rem', fontFamily: T.mono, color: T.accent, fontWeight: 600 }}>A11oy Atelier</span>
        <span style={{ fontSize: '0.5rem', fontFamily: T.mono, color: T.textMuted }}>· tenant: {tenantId}</span>
      </div>
    </div>
  );
}
