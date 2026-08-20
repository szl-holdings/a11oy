import { useState, useEffect, useRef } from 'react';

const SPACE_SLUG = 'cyber-triage';
const SPACE_NAME = 'Cyber Threat Triage Agent';
const VERTICAL_LABEL = 'Cyber · Atelier Space';
const ACCENT = '#10b981';
const A11OY_ATELIER_URL = '/a11oy/atelier/s/cyber-triage';
const A11OY_EMBED_TARGET = window.location.origin;

interface EmbedMessage {
  type: string;
  spaceSlug?: string;
  tenantId?: string;
  ready?: boolean;
  phase?: string;
  line?: string;
  proofRef?: string;
  done?: boolean;
  error?: string;
}

type RunMode = 'governed' | 'demo-preview' | null;

export function AtelierSpaceEmbed({ compact = false }: { compact?: boolean }) {
  const [lines, setLines] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [_connected, setConnected] = useState(false);
  const [runMode, setRunMode] = useState<RunMode>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const connectedRef = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (e.origin !== A11OY_EMBED_TARGET) return;
      const data = e.data as EmbedMessage;
      if (!data?.type) return;

      if (data.type === 'a11oy-space-ack' && data.spaceSlug === SPACE_SLUG) {
        setConnected(true);
        connectedRef.current = true;
      }

      if (data.type === 'a11oy-space-line' && data.line) {
        setRunMode('governed');
        setLines(prev => [...prev, data.line!]);
      }

      if (data.type === 'a11oy-space-done') {
        setRunning(false);
        setDone(true);
        if (data.proofRef) {
          setLines(prev => [...prev, `✓ Proof ref: ${data.proofRef}`]);
        }
        if (data.error) {
          setLines(prev => [...prev, `⚠ ${data.error}`]);
        }
      }
    }
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    function onLoad() {
      iframe!.contentWindow?.postMessage(
        { type: 'a11oy-space-handshake', spaceSlug: SPACE_SLUG },
        A11OY_EMBED_TARGET
      );
    }
    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, []);

  function run() {
    setLines([]);
    setDone(false);
    setRunning(true);
    setRunMode(null);
    setConnected(false);
    connectedRef.current = false;

    const iframe = iframeRef.current;
    if (iframe?.contentWindow) {
      iframe.contentWindow.postMessage(
        { type: 'a11oy-space-handshake', spaceSlug: SPACE_SLUG },
        A11OY_EMBED_TARGET
      );
      iframe.contentWindow.postMessage(
        { type: 'a11oy-space-run', spaceSlug: SPACE_SLUG },
        A11OY_EMBED_TARGET
      );
    }

    const fallbackOutputs = [
      '[DEMO] ⟳ Connecting to Threat Intelligence Feed…',
      '[DEMO] ✓ CVE enrichment complete — CVE-2025-4471 (CVSS 9.8)',
      '[DEMO] ⟳ Correlating SIEM events across 14 endpoints…',
      '[DEMO] ⚠ Lateral movement signature observed in prod-finance-vpc',
      '[DEMO] ⟳ Running containment simulation against deception grid…',
      '[DEMO] ✓ Containment plan: isolate 4 hosts, revoke 2 sessions',
      '[DEMO] ⟳ Validating against zero-trust policy…',
      '[DEMO] ✓ Policy match: SOC-PB-017 · GC + SOC-Lead approval required',
      '[DEMO] ⟳ Generating proof packet…',
      '[DEMO] ✓ Proof: sha256:7d3a91c2f8e6b4a5d1c9… (simulated)\n\n[DEMO] Recommendation: Execute SOAR playbook SOC-PB-017. Connect A11oy runtime for governed execution.',
    ];

    setTimeout(() => {
      if (!connectedRef.current) {
        setRunMode('demo-preview');
        setLines(prev => [...prev, '⚠ A11oy Atelier runtime unavailable — showing demo preview']);
        let i = 0;
        const iv = setInterval(() => {
          if (i < fallbackOutputs.length) { setLines(p => [...p, fallbackOutputs[i]]); i++; }
          else { clearInterval(iv); setRunning(false); setDone(true); }
        }, 370);
      }
    }, 1200);
  }

  return (
    <div style={{
      background: '#0a0a0a',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 10,
      overflow: 'hidden',
      fontFamily: 'var(--font-sans, Inter, sans-serif)',
      borderTop: `2px solid ${ACCENT}`,
      position: 'relative',
    }}>
      <iframe
        ref={iframeRef}
        src={`/a11oy/embed/${SPACE_SLUG}?tenant=szl`}
        style={{ display: 'none' }}
        title="A11oy Atelier Embed Channel"
      />

      <div style={{
        padding: compact ? '0.625rem 0.875rem' : '0.875rem 1.125rem',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', alignItems: 'center', gap: '0.75rem',
        background: 'rgba(255,255,255,0.01)',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f5f5f5', letterSpacing: '-0.01em' }}>
            {SPACE_NAME}
          </div>
          {!compact && (
            <div style={{ fontSize: '0.5625rem', fontFamily: 'ui-monospace,monospace', color: ACCENT, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '0.125rem' }}>
              {VERTICAL_LABEL}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: runMode === 'demo-preview' ? '#fbbf24' : ACCENT,
            boxShadow: `0 0 5px ${runMode === 'demo-preview' ? '#fbbf24' : ACCENT}`,
          }} />
          <span style={{ fontSize: '0.5rem', fontFamily: 'ui-monospace,monospace', color: '#5e5e5e' }}>
            {runMode === 'demo-preview' ? 'Demo Preview' : 'Governed'}
          </span>
        </div>
        <a
          href={A11OY_ATELIER_URL}
          style={{ fontSize: '0.5rem', fontFamily: 'ui-monospace,monospace', color: '#5e5e5e', textDecoration: 'none', padding: '0.2rem 0.375rem', borderRadius: 3, border: '1px solid rgba(255,255,255,0.08)' }}
        >
          ↗ Open
        </a>
      </div>

      <div style={{ background: 'rgba(0,0,0,0.3)', minHeight: compact ? 120 : 200, maxHeight: compact ? 160 : 260, overflowY: 'auto', padding: '0.875rem', fontFamily: 'ui-monospace,monospace', fontSize: '0.6875rem', lineHeight: 1.7 }}>
        {lines.length === 0 && !running && (
          <div style={{ color: '#5e5e5e', textAlign: 'center', paddingTop: compact ? '1.25rem' : '2rem' }}>
            Click Run to execute the {SPACE_NAME} in the governed runtime.
          </div>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{
            color: l.startsWith('[DEMO]') ? '#fbbf24' : l.startsWith('✓') ? ACCENT : l.startsWith('⚠') ? '#fbbf24' : l.startsWith('⟳') ? '#5e5e5e' : '#f5f5f5',
            whiteSpace: 'pre-line',
          }}>
            {l}
          </div>
        ))}
        {running && <span style={{ color: ACCENT }}>▌</span>}
        <div ref={bottomRef} />
      </div>

      <div style={{ padding: '0.625rem 0.875rem', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: '0.5rem', alignItems: 'center', background: 'rgba(255,255,255,0.01)' }}>
        <button onClick={run} disabled={running}
          style={{ padding: '0.375rem 0.875rem', borderRadius: 5, fontSize: '0.6875rem', fontWeight: 500, cursor: running ? 'not-allowed' : 'pointer', background: `rgba(16,185,129,0.1)`, border: `1px solid ${ACCENT}40`, color: ACCENT, opacity: running ? 0.5 : 1 }}>
          {running ? '⟳ Running…' : '▶ Run'}
        </button>
        {done && (
          <span style={{ fontSize: '0.5625rem', fontFamily: 'ui-monospace,monospace', color: runMode === 'demo-preview' ? '#fbbf24' : ACCENT }}>
            {runMode === 'demo-preview' ? '⚠ Demo preview — connect runtime for proof' : '✓ Proof generated'}
          </span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
          <span style={{ fontSize: '0.5rem', fontFamily: 'ui-monospace,monospace', color: '#5e5e5e' }}>Powered by</span>
          <span style={{ fontSize: '0.5rem', fontFamily: 'ui-monospace,monospace', color: '#c9b787', fontWeight: 600 }}>A11oy Atelier</span>
        </div>
      </div>
    </div>
  );
}
