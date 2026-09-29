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
      // Only accept postMessage from the embedded A11oy origin (missing-origin-check / CWE-346 / CWE-940).
      if (e.origin !== atelierOrigin) return;
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
  }, [spaceSlug, atelierOrigin]);

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
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--bg)',
    }}>
      <div style={{
        padding: '0.625rem 0.875rem',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'color-mix(in srgb, var(--surface-raised) 50%, transparent)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-silver-300)', boxShadow: '0 0 6px var(--color-silver-300)' }} />
          <span style={{ fontSize: '0.6875rem', color: 'var(--text)', fontWeight: 600 }}>
            {title ?? `Atelier Space · ${spaceSlug}`}
          </span>
          <span style={{ fontSize: '0.5rem', fontFamily: 'var(--font-mono)', color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Live embed
          </span>
        </div>
        <button onClick={runSpace} disabled={!done && lines.length > 0}
          style={{
            padding: '0.25rem 0.75rem', borderRadius: 4, cursor: 'pointer',
            background: 'color-mix(in srgb, var(--text) 10%, transparent)', color: 'var(--text)',
            border: '1px solid color-mix(in srgb, var(--text) 25%, transparent)',
            fontSize: '0.625rem', fontFamily: 'var(--font-mono)',
          }}>
          {lines.length === 0 ? 'Run governed' : done ? 'Run again' : 'Running…'}
        </button>
      </div>
      <iframe ref={ref} src={embedSrc} title={`Atelier ${spaceSlug}`}
        style={{ width: '100%', height: 90, border: 'none', display: 'block', background: 'var(--bg)' }} />
      <div style={{
        height, overflowY: 'auto', padding: '0.875rem',
        fontFamily: 'var(--font-mono)', fontSize: '0.6875rem',
        lineHeight: 1.7, color: 'var(--text-sub)',
      }}>
        {lines.length === 0 && (
          <div style={{ color: 'var(--text-sub)' }}>Click Run to execute this Atelier Space in the governed runtime.</div>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{ color: l.startsWith('✓') ? 'var(--ink-good)' : l.startsWith('⚠') ? 'var(--ink-warn)' : l.startsWith('⟳') ? 'var(--text-sub)' : 'var(--text)' }}>
            {l}
          </div>
        ))}
        {proofRef && (
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', color: 'var(--ink-good)' }}>
            ✓ Proof ref:{' '}
            {proofPacketId ? (
              <a href={`${atelierOrigin}/atelier/proof/${proofPacketId}`} target="_blank" rel="noreferrer" style={{ color: 'var(--link)' }}>{proofRef}</a>
            ) : (
              <span style={{ color: 'var(--ink-good)' }}>{proofRef}</span>
            )}
          </div>
        )}
      </div>
      <div style={{
        padding: '0.375rem 0.875rem',
        borderTop: '1px solid var(--border)',
        background: 'color-mix(in srgb, var(--surface-raised) 50%, transparent)',
        display: 'flex', alignItems: 'center', gap: '0.5rem',
        fontFamily: 'var(--font-mono)', fontSize: '0.5rem', color: 'var(--text-sub)',
      }}>
        <span>Powered by</span>
        <a href={`${atelierOrigin}/atelier/s/${spaceSlug}`} target="_blank" rel="noreferrer" style={{ color: 'var(--link)', fontWeight: 600 }}>A11oy Atelier</a>
        <span>· cross-Space composition · constitutionally bound</span>
      </div>
    </div>
  );
}
