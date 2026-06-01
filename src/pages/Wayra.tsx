// ADDITIVE: WAYRA — the empire's lungs (Doctrine v13, 4th edge organ).
// Quechua *wayra* = "wind, air" (Wiktionary: https://en.wiktionary.org/wiki/wayra).
// Route: /wayra. Always-learning firehose: live feed of last 100 ingested items
// (Yuyay/novelty score badges), search box, per-source dashboard, and a per-item
// "Take it and make it our own" button. Data from /api/a11oy/v1/wayra/*.
// WAYRA(s) = quality(s) · novelty(s) · Yuyay_13(extract(s)) ∈ [0,1].
// Pushed by HfApi DIRECT, never GitHub Actions.
import { useEffect, useState } from 'react';

type Item = {
  source: string; source_detail?: string; title?: string; url?: string;
  wayra_factor?: number; yuyay_score?: number; novelty_score?: number;
  decision?: string; organ_routing?: string[]; content_hash?: string;
  parsed_summary?: string;
};
type SrcStat = {
  source: string; total: number; accepted: number; review: number;
  dropped: number; last_fetch?: string;
};

const API = '/api/a11oy/v1/wayra';

function Badge({ d }: { d?: string }) {
  const map: Record<string, string> = {
    accept: '#2ecc71', review: '#f1c40f', drop: '#e74c3c',
  };
  return (
    <span style={{
      padding: '1px 7px', borderRadius: 999, fontSize: 11, fontWeight: 700,
      color: map[d || 'review'] || '#8aa0b4',
      background: 'rgba(255,255,255,.06)',
    }}>{d}</span>
  );
}

export function Wayra() {
  const [summary, setSummary] = useState<any>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [sources, setSources] = useState<SrcStat[]>([]);
  const [digest, setDigest] = useState<string>('loading…');
  const [q, setQ] = useState('');

  useEffect(() => {
    fetch(`${API}/summary`).then((r) => r.json()).then((s) => {
      setSummary(s); setSources(s.source_stats || []);
    });
    fetch(`${API}/feed?limit=100`).then((r) => r.json()).then((f) => setItems(f.items || []));
    fetch(`${API}/digest`).then((r) => r.json()).then((d) => setDigest(d.transcript || ''));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      const url = q ? `${API}/search?q=${encodeURIComponent(q)}` : `${API}/feed?limit=100`;
      fetch(url).then((r) => r.json()).then((r) => setItems(r.items || []));
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  async function takeIt(hash?: string) {
    if (!hash) return;
    const r = await fetch(`${API}/take-it`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content_hash: hash }),
    }).then((x) => x.json());
    if (r.ok) {
      alert(`Drafted ${r.draft.kind} for ${r.draft.target_organ} — ${r.draft.status}.\n\n${r.draft.title}`);
    } else {
      alert(`Could not draft: ${r.error || 'unknown'}`);
    }
  }

  const t = summary?.totals;
  return (
    <div style={{ padding: 24, color: '#e7eef6', maxWidth: 1180, margin: '0 auto' }}>
      <h1 style={{ marginBottom: 4 }}>WAYRA · the empire's lungs</h1>
      <div style={{ color: '#8aa0b4', marginBottom: 16 }}>
        Quechua <i>wayra</i> = wind, air (
        <a href="https://en.wiktionary.org/wiki/wayra" target="_blank" rel="noopener noreferrer"
          style={{ color: '#48c9ff' }}>Wiktionary</a>) · Doctrine v13, 4th edge organ ·
        always-learning firehose · WAYRA(s) = quality · novelty · Yuyay₁₃ ∈ [0,1]
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '14px 0' }}>
        {t && [
          ['events', t.events], ['receipts', t.receipts],
          ['chain', t.chain_verified ? 'verified' : 'broken'],
          ['sources', sources.length], ['daily cap', summary.thresholds?.daily_cap],
        ].map(([l, n]) => (
          <div key={String(l)} style={{
            background: '#121a24', border: '1px solid #1f2c3a', borderRadius: 10,
            padding: 14, minWidth: 130,
          }}>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{String(n)}</div>
            <div style={{ color: '#8aa0b4', fontSize: 12, textTransform: 'uppercase' }}>{String(l)}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 320 }}>
          <div style={{ background: '#121a24', border: '1px solid #1f2c3a', borderRadius: 10, padding: 14 }}>
            <b>Live feed</b> <span style={{ color: '#8aa0b4' }}>— last 100 ingested items</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search anything WAYRA has seen…"
              style={{
                width: '100%', padding: '9px 12px', margin: '10px 0', background: '#0e1620',
                border: '1px solid #1f2c3a', borderRadius: 8, color: '#e7eef6',
              }} />
            <div style={{ maxHeight: 560, overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ color: '#8aa0b4', fontSize: 11, textAlign: 'left' }}>
                  <th>Source</th><th>Item</th><th>WAYRA</th><th>Yuyay</th><th>Nov</th>
                  <th>Decision</th><th>Route</th><th /></tr></thead>
                <tbody>
                  {items.map((it, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #1f2c3a' }}>
                      <td>{it.source}<br /><span style={{ color: '#8aa0b4' }}>{it.source_detail}</span></td>
                      <td><a href={it.url} target="_blank" rel="noopener noreferrer" style={{ color: '#48c9ff' }}>
                        {(it.title || '').slice(0, 90)}</a></td>
                      <td>{(it.wayra_factor || 0).toFixed(2)}</td>
                      <td>{(it.yuyay_score || 0).toFixed(2)}</td>
                      <td>{(it.novelty_score || 0).toFixed(2)}</td>
                      <td><Badge d={it.decision} /></td>
                      <td style={{ color: '#8aa0b4' }}>{(it.organ_routing || []).join(', ')}</td>
                      <td>{it.decision === 'accept' && (
                        <button onClick={() => takeIt(it.content_hash)} style={{
                          background: '#16314a', border: '1px solid #1f4a6b', color: '#48c9ff',
                          borderRadius: 6, padding: '3px 8px', fontSize: 11, cursor: 'pointer',
                        }}>take it</button>)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 320, maxWidth: 380 }}>
          <div style={{ background: '#121a24', border: '1px solid #1f2c3a', borderRadius: 10, padding: 14, marginBottom: 12 }}>
            <b>Per-source dashboard</b>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginTop: 8 }}>
              <thead><tr style={{ color: '#8aa0b4', fontSize: 11, textAlign: 'left' }}>
                <th>Source</th><th>Total</th><th>Acc</th><th>Rev</th><th>Drop</th></tr></thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source} style={{ borderBottom: '1px solid #1f2c3a' }}>
                    <td>{s.source}</td><td>{s.total}</td><td>{s.accepted}</td>
                    <td>{s.review}</td><td>{s.dropped}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ background: '#121a24', border: '1px solid #1f2c3a', borderRadius: 10, padding: 14 }}>
            <b>Hatun-Willay digest</b> <span style={{ color: '#8aa0b4' }}>— Wallpa-narrated top-5</span>
            <pre style={{
              whiteSpace: 'pre-wrap', background: '#0e1620', border: '1px solid #1f2c3a',
              borderRadius: 8, padding: 12, color: '#8aa0b4', marginTop: 8,
            }}>{digest}</pre>
          </div>
        </div>
      </div>

      <div style={{ color: '#8aa0b4', marginTop: 16, fontSize: 12 }}>
        RECEIVE-ONLY from public sources · Khipu receipt on every event · Yuyay-13 gate
        enforced · daily cap 50 · HfApi direct push, never GitHub Actions.
      </div>
    </div>
  );
}
