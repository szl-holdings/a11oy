import { useEffect, useRef, useState } from 'react';

interface Props {
  spaceSlug: string;
  height?: number;
  title?: string;
  // Tenant context propagated to the iframe via the handshake. Defaults
  // to VITE_A11OY_TENANT (build-time) or 'szl'. The iframe echoes this
  // value into recordAtelierRun() so persisted runs carry the host's
  // tenant; the host's X-Tenant-Id header (not this value) remains the
  // authorization source of truth on /api/atelier/proofs/:id.
  tenantId?: string;
}

// Live embed of an A11oy Atelier Space inside conduit. Loads the Atelier
// embed host via iframe and records telemetry via /api/atelier/embed-events
// so leaderboards reflect real cross-artifact usage.
export function AtelierEmbedFrame({ spaceSlug, height = 380, title, tenantId }: Props) {
  const resolvedTenantId = tenantId
    ?? (import.meta.env.VITE_A11OY_TENANT as string | undefined)
    ?? 'szl';
  const ref = useRef<HTMLIFrameElement>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [proofRef, setProofRef] = useState<string | null>(null);

  // A11oy origin is configurable via VITE_A11OY_ORIGIN so the embed
  // works when the host artifact and A11oy are deployed on different
  // origins. Defaults to same-origin (preview pane shares a hostname
  // and routes by path prefix, so /embed/* hits the A11oy artifact).
  const atelierOrigin = (import.meta.env.VITE_A11OY_ORIGIN as string | undefined) ?? window.location.origin;
  const embedSrc = `${atelierOrigin}/embed/${spaceSlug}`;
  const [proofPacketId, setProofPacketId] = useState<string | null>(null);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.spaceSlug !== spaceSlug) return;
      if (e.data.type === 'a11oy-space-line') {
        setLines((p) => [...p, String(e.data.line)]);
      } else if (e.data.type === 'a11oy-space-done') {
        setDone(true);
        if (e.data.proofRef) setProofRef(String(e.data.proofRef));
        if (e.data.proofPacketId) setProofPacketId(String(e.data.proofPacketId));
        void fetch('/api/atelier/embed-events', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ spaceSlug, origin: window.location.origin, event: 'completed' }),
        }).catch(() => {});
      }
    }
    window.addEventListener('message', onMessage);

    void fetch('/api/atelier/embed-events', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spaceSlug, origin: window.location.origin, event: 'handshake' }),
    }).catch(() => {});

    return () => window.removeEventListener('message', onMessage);
  }, [spaceSlug]);

  function runSpace() {
    setLines([]); setDone(false); setProofRef(null);
    ref.current?.contentWindow?.postMessage(
      { type: 'a11oy-space-handshake', spaceSlug, tenantId: resolvedTenantId },
      atelierOrigin,
    );
    setTimeout(() => {
      ref.current?.contentWindow?.postMessage(
        { type: 'a11oy-space-run', spaceSlug, tenantId: resolvedTenantId },
        atelierOrigin,
      );
      void fetch('/api/atelier/embed-events', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spaceSlug, origin: window.location.origin, event: 'run' }),
      }).catch(() => {});
    }, 250);
  }

  return (
    <div style={{
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 10, overflow: 'hidden', background: '#0a0a0a',
      borderTop: '2px solid #c9b787',
    }}>
      <div style={{
        padding: '0.625rem 0.875rem',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(255,255,255,0.02)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#c9b787', boxShadow: '0 0 6px #c9b787' }} />
          <span style={{ fontSize: '0.6875rem', color: '#f5f5f5', fontWeight: 600 }}>
            {title ?? `Atelier Space · ${spaceSlug}`}
          </span>
          <span style={{ fontSize: '0.5rem', fontFamily: 'ui-monospace, monospace', color: '#8a8a8a', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Live embed
          </span>
        </div>
        <button onClick={runSpace} disabled={!done && lines.length > 0}
          style={{
            padding: '0.25rem 0.75rem', borderRadius: 4, cursor: 'pointer',
            background: 'rgba(201,183,135,0.1)', color: '#c9b787',
            border: '1px solid rgba(201,183,135,0.25)',
            fontSize: '0.625rem', fontFamily: 'ui-monospace, monospace',
          }}>
          {lines.length === 0 ? '▶ Run governed' : done ? '↻ Run again' : '⟳ Running…'}
        </button>
      </div>
      <iframe ref={ref} src={embedSrc} title={`Atelier ${spaceSlug}`}
        style={{ width: '100%', height: 90, border: 'none', display: 'block', background: '#0a0a0a' }} />
      <div style={{
        height, overflowY: 'auto', padding: '0.875rem',
        fontFamily: 'ui-monospace, monospace', fontSize: '0.6875rem',
        lineHeight: 1.7, color: '#8a8a8a',
      }}>
        {lines.length === 0 && (
          <div style={{ color: '#5e5e5e' }}>Click Run to execute this Atelier Space in the governed runtime.</div>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{ color: l.startsWith('✓') ? '#c9b787' : l.startsWith('⚠') ? '#e8b04f' : l.startsWith('⟳') ? '#5e5e5e' : '#f5f5f5' }}>
            {l}
          </div>
        ))}
        {proofRef && (
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.05)', color: '#c9b787' }}>
            ✓ Proof ref:{' '}
            {proofPacketId ? (
              <a href={`${atelierOrigin}/atelier/proof/${proofPacketId}`} target="_blank" rel="noreferrer" style={{ color: '#c9b787' }}>{proofRef}</a>
            ) : (
              <span style={{ color: '#c9b787' }}>{proofRef}</span>
            )}
          </div>
        )}
      </div>
      <div style={{
        padding: '0.375rem 0.875rem',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(255,255,255,0.01)',
        display: 'flex', alignItems: 'center', gap: '0.5rem',
        fontFamily: 'ui-monospace, monospace', fontSize: '0.5rem', color: '#5e5e5e',
      }}>
        <span>Powered by</span>
        <a href={`${atelierOrigin}/atelier/s/${spaceSlug}`} target="_blank" rel="noreferrer" style={{ color: '#c9b787', fontWeight: 600 }}>A11oy Atelier</a>
        <span>· cross-Space composition · constitutionally bound</span>
      </div>
    </div>
  );
}
