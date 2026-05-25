// Live editor + terminal panel that drives the same plan/tool/reflection loop
// the @szl/a11oy-code CLI runs. The scripted demo block was previously a
// marketing surface; this panel is real — every keystroke flows through
// Ouroboros, Lutar, MirrorEval and writes to the in-browser proof ledger.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'wouter';
import {
  proof, runTurn, startSession,
  type ProofEntry, type Session, type Turn, type VirtualFS,
} from '../lib/a11oy-code-engine';

const T = {
  bg: '#0a0a0a', surface: 'rgba(255,255,255,0.025)', border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.12)', text: '#f5f5f5', dim: '#8a8a8a',
  muted: '#5e5e5e', accent: '#c9b787', good: '#28c840', bad: '#ef4444',
  mono: "var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace)",
};

const SEED_FILES: Record<string, string> = {
  'README.md': '# scratch workspace\n\nThis is the in-browser sandbox the /code panel hands to a11oy-code.\nTry: "read README.md", "edit README.md", "lookup formula lutar", "show proof ledger".\n',
  'src/eta-calculator.ts': "// ETA calculator — refactor target.\nexport function eta(distanceKm: number, knots: number) {\n  return distanceKm / (knots * 1.852);\n}\n",
  'package.json': '{\n  "name": "scratch",\n  "version": "0.0.0"\n}\n',
};

interface LineOut {
  kind: 'sys' | 'usr' | 'agt' | 'gate' | 'div' | 'err';
  text: string;
}

function turnToLines(turn: Turn): LineOut[] {
  const lines: LineOut[] = [];
  lines.push({ kind: 'usr', text: `→ ${turn.user}` });
  const planSteps = turn.plan.steps.map(s => s.tool).join(' › ');
  lines.push({ kind: 'agt', text: `  ▶ Plan (${turn.plan.steps.length} step${turn.plan.steps.length === 1 ? '' : 's'}): ${planSteps}` });
  if (turn.plan.revised_by) {
    lines.push({ kind: 'agt', text: `  ▶ Ouroboros revised plan @ ${turn.plan.revised_at?.slice(11, 19)}` });
  }
  lines.push({
    kind: 'agt',
    text: `  ▶ Lutar pick: ${turn.tool.name}  score=${turn.tool.score.toFixed(3)}${turn.tool.why ? `  · ${turn.tool.why}` : ''}`,
  });
  if (turn.result.ok === false) {
    lines.push({ kind: 'err', text: `  ✗ ${turn.tool.name} failed: ${String(turn.result.error ?? 'error')}` });
  } else {
    const r = turn.result;
    if (r.kind === 'file' && typeof r.content === 'string') {
      const preview = (r.content as string).split('\n').slice(0, 6).join('\n');
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → file (${(r.content as string).length} bytes)` });
      for (const ln of preview.split('\n')) lines.push({ kind: 'agt', text: `    │ ${ln}` });
    } else if (r.kind === 'dir' && Array.isArray(r.entries)) {
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → dir (${(r.entries as string[]).length} entries)` });
      for (const e of (r.entries as string[]).slice(0, 8)) lines.push({ kind: 'agt', text: `    · ${e}` });
    } else if (typeof r.stdout === 'string') {
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → ${(r.stdout as string).slice(0, 200)}` });
    } else if (Array.isArray(r.hits)) {
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → ${(r.hits as unknown[]).map(h => typeof h === 'string' ? h : JSON.stringify(h)).join(', ')}` });
    } else if (Array.isArray(r.entries)) {
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → ${(r.entries as unknown[]).length} ledger entries` });
    } else {
      lines.push({ kind: 'agt', text: `  ✓ ${turn.tool.name} → ok` });
    }
  }
  lines.push({ kind: 'gate', text: `  ⨡ MirrorEval score=${turn.score.toFixed(3)}  ·  proof appended` });
  lines.push({ kind: 'div', text: '─'.repeat(72) });
  return lines;
}

const KIND_COLOR: Record<LineOut['kind'], string> = {
  sys: T.muted, usr: T.text, agt: T.dim, gate: T.accent, div: 'rgba(255,255,255,0.06)', err: T.bad,
};

interface Props { chatPath: string }

export function A11oyCodeLivePanel({ chatPath }: Props) {
  const [session, setSession] = useState<Session | null>(null);
  const [activePath, setActivePath] = useState<string>('README.md');
  const [editorBuf, setEditorBuf] = useState<string>(SEED_FILES['README.md']);
  const [input, setInput] = useState<string>('');
  const [lines, setLines] = useState<LineOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [ledger, setLedger] = useState<ProofEntry[]>([]);
  const fsRef = useRef<VirtualFS>({ files: { ...SEED_FILES } });
  const termRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const s = await startSession({ provider: 'local-stub', model: 'a11oy-code-web', autonomy: false });
      if (cancelled) return;
      setSession(s);
      setLines([
        { kind: 'sys', text: `a11oy-code web v1.0 — same engine as @szl/a11oy-code CLI` },
        { kind: 'sys', text: `session ${s.id}  ·  provider: local-stub  ·  model: a11oy-code-web` },
        { kind: 'sys', text: `tools: read, write, edit, shell, git, web_search, hf_search, thesis_lookup, formula_lookup, proof_query, subagent, finish` },
        { kind: 'div', text: '─'.repeat(72) },
      ]);
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => proof.subscribe(setLedger), []);

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [lines]);

  const sessionLedger = useMemo(
    () => session ? ledger.filter(e => !e.session || e.session === session.id) : ledger,
    [ledger, session],
  );

  const onSelectFile = useCallback((p: string) => {
    fsRef.current.files[activePath] = editorBuf;
    setActivePath(p);
    setEditorBuf(fsRef.current.files[p] ?? '');
  }, [activePath, editorBuf]);

  const onSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!session || !input.trim() || busy) return;
    fsRef.current.files[activePath] = editorBuf;
    const text = input.trim();
    setInput('');
    setBusy(true);
    try {
      const turn = await runTurn(session, text, { fs: fsRef.current });
      setLines(prev => [...prev, ...turnToLines(turn)]);
      // If the engine edited the active file, reflect changes in the editor.
      const refreshed = fsRef.current.files[activePath];
      if (refreshed !== undefined && refreshed !== editorBuf) setEditorBuf(refreshed);
      // Surface unknown new files in the picker
      setSession({ ...session });
    } catch (err) {
      setLines(prev => [...prev, { kind: 'err', text: `[turn-error] ${(err as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }, [session, input, busy, activePath, editorBuf]);

  const handoffHref = session
    ? `${chatPath}?session=${encodeURIComponent(session.id)}&from=code`
    : chatPath;

  const fileNames = useMemo(() => Object.keys(fsRef.current.files).sort(), [session, lines]);

  return (
    <div style={{
      borderRadius: 10, overflow: 'hidden', border: `1px solid ${T.border}`,
      background: '#050505', display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.1fr)', gap: 1, backgroundColor: T.border,
    }}>
      {/* Editor pane */}
      <div style={{ background: '#050505', display: 'flex', flexDirection: 'column', minHeight: 480 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 0.875rem', borderBottom: `1px solid ${T.border}`, background: 'rgba(255,255,255,0.02)' }}>
          <span style={{ fontSize: '0.625rem', fontFamily: T.mono, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.14em' }}>Editor</span>
          <select
            value={activePath}
            onChange={(ev) => onSelectFile(ev.target.value)}
            style={{
              marginLeft: 'auto', background: 'transparent', color: T.text, fontFamily: T.mono,
              fontSize: '0.6875rem', border: `1px solid ${T.border}`, borderRadius: 4, padding: '0.2rem 0.4rem',
            }}
          >
            {fileNames.map(f => <option key={f} value={f} style={{ background: T.bg }}>{f}</option>)}
          </select>
        </div>
        <textarea
          value={editorBuf}
          onChange={(ev) => setEditorBuf(ev.target.value)}
          spellCheck={false}
          style={{
            flex: 1, background: '#050505', color: T.text, border: 'none', outline: 'none',
            resize: 'none', padding: '1rem', fontFamily: T.mono, fontSize: '0.75rem',
            lineHeight: 1.6, minHeight: 360,
          }}
        />
      </div>

      {/* Terminal pane */}
      <div style={{ background: '#050505', display: 'flex', flexDirection: 'column', minHeight: 480 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 0.875rem', borderBottom: `1px solid ${T.border}`, background: 'rgba(255,255,255,0.02)' }}>
          <div style={{ display: 'flex', gap: '0.375rem' }}>
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#ff5f57' }} />
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#ffbd2e' }} />
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#28c840' }} />
          </div>
          <span style={{ fontSize: '0.6875rem', fontFamily: T.mono, color: T.dim, marginLeft: '0.5rem' }}>
            a11oy-code · live session
          </span>
          <span style={{ marginLeft: 'auto', fontSize: '0.5625rem', fontFamily: T.mono, padding: '0.15rem 0.5rem', borderRadius: 3, background: 'rgba(201,183,135,0.1)', color: T.accent, border: '1px solid rgba(201,183,135,0.15)' }}>GOVERNED</span>
          <Link
            href={handoffHref}
            style={{
              fontSize: '0.5625rem', fontFamily: T.mono, padding: '0.2rem 0.55rem', borderRadius: 3,
              background: 'rgba(127,179,255,0.08)', color: '#7fb3ff',
              border: '1px solid rgba(127,179,255,0.18)', textDecoration: 'none',
            }}
            title="Hand this session off to /chat"
          >Hand off → /chat</Link>
        </div>
        <div ref={termRef} style={{
          flex: 1, padding: '1rem 1rem 0.5rem', fontFamily: T.mono, fontSize: '0.6875rem',
          lineHeight: 1.7, overflowY: 'auto', maxHeight: 420,
        }}>
          {lines.map((line, i) => (
            <div key={i} style={{ color: KIND_COLOR[line.kind], fontWeight: line.kind === 'usr' ? 600 : 400, whiteSpace: 'pre-wrap' }}>
              {line.text}
            </div>
          ))}
          {busy && (
            <div style={{ color: T.accent, marginTop: '0.25rem' }}>… running turn through Ouroboros · Lutar · MirrorEval</div>
          )}
        </div>
        <form onSubmit={onSubmit} style={{ display: 'flex', gap: '0.5rem', padding: '0.625rem 0.875rem', borderTop: `1px solid ${T.border}`, background: 'rgba(255,255,255,0.02)' }}>
          <span style={{ color: T.accent, fontFamily: T.mono, fontSize: '0.75rem' }}>▸</span>
          <input
            value={input}
            onChange={(ev) => setInput(ev.target.value)}
            disabled={!session || busy}
            placeholder='try: "read README.md", "edit src/eta-calculator.ts", "lookup formula lutar"'
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: T.text, fontFamily: T.mono, fontSize: '0.75rem',
            }}
          />
          <button type="submit" disabled={!session || busy || !input.trim()} style={{
            padding: '0.3rem 0.85rem', borderRadius: 4, fontFamily: T.mono, fontSize: '0.6875rem',
            background: busy ? 'rgba(255,255,255,0.04)' : T.text, color: busy ? T.dim : T.bg,
            border: `1px solid ${T.borderStrong}`, cursor: busy || !input.trim() ? 'not-allowed' : 'pointer',
          }}>{busy ? '…' : 'run'}</button>
        </form>
      </div>

      {/* Proof ledger */}
      <div style={{ gridColumn: '1 / -1', background: '#050505', borderTop: `1px solid ${T.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 0.875rem', borderBottom: `1px solid ${T.border}`, background: 'rgba(255,255,255,0.02)' }}>
          <span style={{ fontSize: '0.625rem', fontFamily: T.mono, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.14em' }}>Proof Ledger</span>
          <span style={{ fontSize: '0.5625rem', fontFamily: T.mono, color: T.dim, marginLeft: '0.5rem' }}>
            {sessionLedger.length} entr{sessionLedger.length === 1 ? 'y' : 'ies'} · same chain the CLI writes
          </span>
        </div>
        <div style={{ maxHeight: 220, overflowY: 'auto', padding: '0.5rem 0.875rem' }}>
          {sessionLedger.length === 0 && (
            <div style={{ color: T.muted, fontFamily: T.mono, fontSize: '0.6875rem', padding: '0.5rem 0' }}>
              No entries yet — issue a command to populate the chain.
            </div>
          )}
          {sessionLedger.slice(-30).reverse().map(e => (
            <div key={e.hash} style={{ display: 'grid', gridTemplateColumns: '88px 130px 1fr 130px', gap: '0.75rem', padding: '0.25rem 0', fontFamily: T.mono, fontSize: '0.625rem', color: T.dim, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <span style={{ color: T.muted }}>{e.ts.slice(11, 19)}</span>
              <span style={{ color: T.accent }}>{e.kind}</span>
              <span style={{ color: T.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {summarize(e)}
              </span>
              <span style={{ color: T.muted, textAlign: 'right' }}>0x{e.hash}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function summarize(e: ProofEntry): string {
  const parts: string[] = [];
  if (typeof e.tool === 'string') parts.push(`tool=${e.tool}`);
  if (typeof e.score === 'number') parts.push(`score=${(e.score as number).toFixed(3)}`);
  if (typeof e.ok === 'boolean') parts.push(`ok=${e.ok}`);
  if (e.kind === 'plan' || e.kind === 'plan_revised') {
    const steps = (e.plan as { steps?: { tool: string }[] } | undefined)?.steps;
    if (steps) parts.push(`steps=${steps.map(s => s.tool).join('›')}`);
  }
  if (e.kind === 'session_start') parts.push('opened');
  return parts.join('  ');
}
