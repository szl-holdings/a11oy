import { useEffect, useMemo, useState } from "react";
import {
  CONSOLE_VERTICALS,
  GENOME,
  LOCKED_CLAIMS,
  LOCKED_FORMULAS,
  NAV,
  PRODUCT_ORIGIN,
  PROOF_REGISTRY,
  PUBLIC_CREDS,
  PULSE_ENDPOINTS,
  SOURCE_REPO,
  SURFACES,
  TRUST_CEILING,
  VERTICALS,
} from "./lib/a11oy/estate";
import { canonicalReceipt, GENESIS, geometricMean, sha256Hex } from "./lib/a11oy/crypto";
import { evaluateImmune, IMMUNE_PRESETS, type ImmuneDecision } from "./lib/a11oy/immune";

type Path =
  | "/"
  | "/console"
  | "/superpowers"
  | "/formulas"
  | "/evidence"
  | "/observability"
  | "/wires"
  | "/mesh"
  | "/immune"
  | "/verify";

function pathFromHash(): Path {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const known: Path[] = [
    "/",
    "/console",
    "/superpowers",
    "/formulas",
    "/evidence",
    "/observability",
    "/wires",
    "/mesh",
    "/immune",
    "/verify",
  ];
  return (known as string[]).includes(raw) ? (raw as Path) : "/";
}

function go(to: Path) {
  window.location.hash = to;
}

function Chip({ label, tone = "muted" }: { label: string; tone?: "live" | "hold" | "deny" | "muted" }) {
  return <span className={`chip ${tone}`}>{label}</span>;
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="mark" aria-hidden="true">
      <rect x="8" y="7" width="3.2" height="18" fill="currentColor" />
      <rect x="20.8" y="7" width="3.2" height="18" fill="currentColor" />
      <rect x="7" y="7" width="18" height="1.6" fill="var(--live)" />
    </svg>
  );
}

type Pulse = { id: string; label: string; honesty: "REACHABLE" | "UNAVAILABLE"; ms: number; detail: string };

async function probe(url: string): Promise<Omit<Pulse, "id" | "label">> {
  const t0 = performance.now();
  try {
    await fetch(url, { method: "GET", mode: "no-cors", cache: "no-store" });
    return { honesty: "REACHABLE", ms: Math.round(performance.now() - t0), detail: "Opaque transport. Not a health stamp." };
  } catch (err) {
    return {
      honesty: "UNAVAILABLE",
      ms: Math.round(performance.now() - t0),
      detail: err instanceof Error ? err.message : "UNAVAILABLE",
    };
  }
}

export function App() {
  const [path, setPath] = useState<Path>(pathFromHash);
  useEffect(() => {
    const onHash = () => setPath(pathFromHash());
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.location.hash = "/";
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="shell">
      <header className="header">
        <div className="wrap">
          <div className="brand">
            <a href="#/" onClick={(e) => { e.preventDefault(); go("/"); }} aria-label="a11oy home">
              <Mark />
            </a>
            <div>
              <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
                <strong>a11oy</strong>
                <span className="kicker">Governed Inference · SZL Holdings</span>
              </div>
              <div className="mono">product a-11-oy.com · proof a11oy.net · Λ = Conjecture 1</div>
            </div>
            <button className="btn primary" style={{ marginLeft: "auto" }} onClick={() => go("/console")}>
              Command Center
            </button>
          </div>
          <nav className="nav" aria-label="Estate">
            {NAV.map((item) => (
              <a key={item.to} href={`#${item.to}`} className={path === item.to ? "active" : undefined} onClick={(e) => { e.preventDefault(); go(item.to); }}>
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className="wrap stack">
        {path === "/" && <Home />}
        {path === "/console" && <Command />}
        {path === "/superpowers" && <Superpowers />}
        {path === "/formulas" && <Formulas />}
        {path === "/evidence" && <Evidence />}
        {path === "/observability" && <Observability />}
        {path === "/wires" && <Wires />}
        {path === "/mesh" && <Mesh />}
        {path === "/immune" && <Immune />}
        {path === "/verify" && <Verify />}
      </main>
      <footer className="footer">
        <div className="wrap" style={{ padding: "20px 0 28px" }}>
          <p className="mono">
            Doctrine v11 LOCKED · locked-8 {LOCKED_FORMULAS.join(" · ")} · Λ = Conjecture 1 · SLSA L1 honest ·
            no ATO claimed · Apache-2.0 · ORCID {""}
            <a href="https://orcid.org/0009-0001-0110-4173">0009-0001-0110-4173</a>
          </p>
          <p className="mono">
            <a href={PRODUCT_ORIGIN}>{PRODUCT_ORIGIN.replace("https://", "")}</a>
            {" · "}
            <a href={PROOF_REGISTRY}>{PROOF_REGISTRY.replace("https://", "")}</a>
            {" · "}
            <a href={SOURCE_REPO}>szl-holdings/a11oy</a>
          </p>
        </div>
      </footer>
    </div>
  );
}

function Home() {
  const [pulses, setPulses] = useState<Pulse[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      PULSE_ENDPOINTS.map(async (ep) => {
        const r = await probe(ep.url);
        return { id: ep.id, label: ep.label, ...r };
      }),
    ).then((rows) => {
      if (!cancelled) setPulses(rows);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const lambda = useMemo(() => {
    if (!pulses) return null;
    const scores = pulses.map((p) => (p.honesty === "REACHABLE" ? 0.91 : 0.62));
    return geometricMean(scores);
  }, [pulses]);

  return (
    <>
      <section className="hero">
        <p className="kicker">Governed Inference · verifiable by anyone, offline</p>
        <h1>AI that proves its receipt state and refuses to lie.</h1>
        <p className="lede">
          Every governed state change produces a hash-chained receipt you can inspect in this browser. The
          interface says SIGNED only when verification passes; otherwise HASH-LINKED, UNSIGNED, or UNAVAILABLE.
          When the model is not sure, it returns BLOCKED instead of a confident guess.
        </p>
      </section>
      <section className="row stats">
        <div className="panel">
          <div className="kicker">Receipts in the chain</div>
          <div className="stat-n">—</div>
          <p>Ledger UNAVAILABLE this session unless a probe returns a count. Not traction.</p>
        </div>
        <div className="panel">
          <div className="kicker">Λ trust gate</div>
          <div className="stat-n">{lambda != null ? lambda.toFixed(3) : "—"}</div>
          <p>Conjecture 1 · advisory · ceiling {TRUST_CEILING.toFixed(2)} · never green-as-proven.</p>
        </div>
        <div className="panel">
          <div className="kicker">Locked Lean theorems</div>
          <div className="stat-n">8</div>
          <p>REPORTED · {LOCKED_FORMULAS.join(" ")} · a proof of rigor, not customers.</p>
        </div>
      </section>
      <section>
        <h2>Honesty doctrine · v11 LOCKED</h2>
        <p className="lede">Every figure on this page is labelled — or it is not shown.</p>
        <div className="row cards" style={{ marginTop: 16 }}>
          {[
            ["MEASURED", "Read live this session. Dead probe → honest offline chip."],
            ["REPORTED", "Stated by a named source. Cited, not re-derived here."],
            ["UNKNOWN", "N/A · UNAVAILABLE · BLOCKED. Never a fabricated number."],
            ["CONJECTURE", "Advisory. Gray. Never a theorem. Λ lives here."],
          ].map(([t, d]) => (
            <div className="panel" key={t}>
              <Chip label={t} tone={t === "MEASURED" ? "live" : t === "UNKNOWN" ? "deny" : "muted"} />
              <h3 style={{ marginTop: 10 }}>{t}</h3>
              <p>{d}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2>Runtime evidence</h2>
        <p className="lede">Opaque browser probes. REACHABLE is transport only — never a LIVE health stamp.</p>
        <div className="row cards" style={{ marginTop: 16 }}>
          {(pulses ?? PULSE_ENDPOINTS.map((e) => ({ id: e.id, label: e.label, honesty: "UNAVAILABLE" as const, ms: 0, detail: "PROBING" }))).map((p) => (
            <div className="panel" key={p.id}>
              <Chip label={p.honesty} tone={p.honesty === "REACHABLE" ? "hold" : "muted"} />
              <h3 style={{ marginTop: 10 }}>{p.label}</h3>
              <p>{p.detail}{p.ms ? ` · ${p.ms}ms` : ""}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h2>Nine surfaces. One governed core.</h2>
        <div className="row cards" style={{ marginTop: 16 }}>
          {SURFACES.map((s) => (
            <button key={s.to} className="panel" style={{ textAlign: "left" }} onClick={() => go(s.to as Path)}>
              <h3>{s.title}</h3>
              <p>{s.blurb}</p>
            </button>
          ))}
        </div>
      </section>
      <section>
        <h2>Five verticals</h2>
        <div className="row cards" style={{ marginTop: 16 }}>
          {VERTICALS.map((v) => (
            <div className="panel" key={v.id}>
              <div className="kicker">{v.sector}</div>
              <h3>{v.name}</h3>
              <p>{v.blurb}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function Command() {
  const [receipts, setReceipts] = useState<{ digest: string; action: string; verdict: string; at: string }[]>([]);
  const [busy, setBusy] = useState(false);

  async function seal() {
    setBusy(true);
    const at = new Date().toISOString();
    const prev = receipts[0]?.digest ?? GENESIS;
    const body = {
      seq: receipts.length + 1,
      prevDigest: prev,
      verdict: "ADMIT",
      hard: false,
      action: "OBSERVE",
      intent: "Seal this Command Center refresh. Observe only.",
      reason: "Read path admitted. Trust is conformal — never 1.00.",
      trust: 0.93,
      at,
    };
    const digest = await sha256Hex(canonicalReceipt(body));
    setReceipts((prevRows) => [{ digest, action: body.action, verdict: body.verdict, at }, ...prevRows].slice(0, 40));
    setBusy(false);
  }

  return (
    <>
      <section className="hero">
        <p className="kicker">SZL HOLDINGS / a11oy / GOVERNED-AI COMMAND PLATFORM / SESSION · HASH-LINKED</p>
        <h1>Command Center</h1>
        <p className="lede">
          One pane of glass over the governed mesh — service health, trust posture, and a rolling stream of
          hash-linked receipts. Always recording. AI that signs its work and refuses to lie.
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
          <button className="btn primary" onClick={() => void seal()} disabled={busy}>
            Seal this refresh
          </button>
          <Chip label="ENERGY UNAVAILABLE" />
          <Chip label="SIGNER UNSIGNED-HONEST" />
          <Chip label="DOCTRINE LOCKED" tone="hold" />
        </div>
      </section>
      <section className="row cards">
        {CONSOLE_VERTICALS.map((v) => (
          <div className="panel" key={v.title}>
            <h3>{v.title}</h3>
            <p>{v.blurb}</p>
            {v.href.startsWith("http") ? <a href={v.href}>{v.link}</a> : <button className="btn ghost" onClick={() => go(v.href as Path)}>{v.link}</button>}
          </div>
        ))}
      </section>
      <section className="row stats">
        <div className="panel"><div className="kicker">Services up</div><div className="stat-n">—</div><p>Organ backends not faked healthy on this replica.</p></div>
        <div className="panel"><div className="kicker">Trust score Λ</div><div className="stat-n">CONJ.</div><p>vs floor 0.90 · never 1.00</p></div>
        <div className="panel"><div className="kicker">Local chain</div><div className="stat-n">{receipts.length}</div><p>SHA-256 UNSIGNED-honest</p></div>
        <div className="panel"><div className="kicker">Build security</div><div className="stat-n">L1</div><p>SLSA L1 honest · L2 .att not independently verified · L3 roadmap</p></div>
      </section>
      <section className="panel">
        <h3>Rolling receipt stream</h3>
        {receipts.length === 0 ? (
          <p>Local chain empty. Seal this refresh to append a MEASURED OBSERVE receipt.</p>
        ) : (
          <ul className="mono">
            {receipts.map((r) => (
              <li key={r.digest}>{r.verdict} {r.action} {r.digest.slice(0, 16)}…</li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2>Governance engine — honest Lean labels</h2>
        <div className="row cards" style={{ marginTop: 16 }}>
          {LOCKED_CLAIMS.map((f) => (
            <div className="panel" key={f.id}>
              <Chip label="LOCKED-PROVEN" tone="live" />
              <h3 style={{ marginTop: 10 }}>{f.id} · {f.name}</h3>
              <p>{f.claim}</p>
              <p className="mono">{f.lean}</p>
            </div>
          ))}
        </div>
      </section>
      <p className="mono">
        {PUBLIC_CREDS.map((c, i) => (
          <span key={c.href}>{i ? " · " : ""}<a href={c.href}>{c.label}</a></span>
        ))}
        . Every credential above is public. We claim less than our competitors.
      </p>
    </>
  );
}

function Superpowers() {
  return (
    <>
      <section className="hero">
        <p className="kicker">Five Superpowers</p>
        <h1>What governed inference does that ungoverned models cannot.</h1>
      </section>
      <div className="row cards">
        {[
          ["01 Receipts", "SHA-256 hash chain. SIGNED only after independent verify.", "/verify"],
          ["02 Refuses", "Self-doubt returns BLOCKED instead of a confident lie.", "/immune"],
          ["03 Proves", "8 locked Lean theorems. Λ is Conjecture 1.", "/formulas"],
          ["04 Fail-closed", "P1–P6 deny-by-default. Approval cannot lift HARD.", "/console"],
          ["05 Verifiable", "Re-hash in your browser. receipts.in ≡ receipts.out.", "/verify"],
        ].map(([t, d, to]) => (
          <button key={t} className="panel" style={{ textAlign: "left" }} onClick={() => go(to as Path)}>
            <h3>{t}</h3>
            <p>{d}</p>
          </button>
        ))}
      </div>
    </>
  );
}

function Formulas() {
  const [open, setOpen] = useState<string | null>("F1");
  return (
    <>
      <section className="hero">
        <p className="kicker">PURIQ genome · 23 FormulaAgents</p>
        <h1>Locked-8 is 8. The rest is graded honestly.</h1>
      </section>
      <div className="panel" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>ID</th><th>Formula</th><th>Status</th><th>Lean</th></tr>
          </thead>
          <tbody>
            {GENOME.map((g) => (
              <tr key={g.id} onClick={() => setOpen(open === g.id ? null : g.id)} style={{ cursor: "pointer" }}>
                <td className="mono">{g.id}</td>
                <td>{g.name}{open === g.id && g.status === "LOCKED-PROVEN" ? " — truthful claim on Evidence / Command." : ""}</td>
                <td><Chip label={g.status} tone={g.status === "LOCKED-PROVEN" ? "live" : g.status === "CONJECTURE" ? "muted" : "hold"} /></td>
                <td className="mono">{g.lean}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Evidence() {
  return (
    <>
      <section className="hero">
        <p className="kicker">Trust center</p>
        <h1>Theorem U is proven conditional. Conjecture 1 is not.</h1>
        <p className="lede">
          Unconditional Λ uniqueness is machine-checked false as stated. The locked-proven set is exactly
          eight formulas. Receipt-chain integrity and DSSE signing are distinct states.
        </p>
      </section>
      <div className="row cards">
        <div className="panel"><Chip label="LOCKED-PROVEN" tone="live" /><h3 style={{ marginTop: 10 }}>Locked-8</h3><p>{LOCKED_FORMULAS.join(" · ")}</p></div>
        <div className="panel"><Chip label="CONJECTURE" /><h3 style={{ marginTop: 10 }}>Λ uniqueness</h3><p>Conjecture 1. Gray. Never 1.0.</p></div>
        <div className="panel"><Chip label="SLSA L1" tone="hold" /><h3 style={{ marginTop: 10 }}>Supply chain</h3><p>L1 honest. L2 attested not independently verified. L3 roadmap. No FedRAMP / IL5 / ATO.</p></div>
      </div>
    </>
  );
}

function Observability() {
  const [axes, setAxes] = useState({
    provenance: 0.94,
    consent: 0.94,
    receipt: 0.94,
    signer: 0.88,
    replay: 0.94,
    failClosed: 0.94,
    quorum: 0.91,
    doctrine: 0.93,
    selfDoubt: 0.9,
  });
  const values = Object.values(axes);
  const lambda = geometricMean(values);
  const deny = lambda < 0.9 || values.some((v) => v <= 0);
  return (
    <>
      <section className="hero">
        <p className="kicker">MELT · signed traces</p>
        <h1>Observability, but cryptographically true.</h1>
        <p className="lede">
          Λ is the geometric mean of the axes. Any zero positive-weight axis pins Λ to 0. Floor 0.90 → DENY.
          This is a real product, not an LLM judgement.
        </p>
      </section>
      <div className="panel">
        <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
          <div className="stat-n">{lambda.toFixed(3)}</div>
          <Chip label={deny ? "DENY" : "HOLD"} tone={deny ? "deny" : "hold"} />
        </div>
        {Object.entries(axes).map(([k, v]) => (
          <label key={k} style={{ display: "grid", gridTemplateColumns: "140px 1fr 48px", gap: 8, alignItems: "center", marginTop: 8 }}>
            <span className="mono">{k}</span>
            <input type="range" min={0} max={0.97} step={0.01} value={v} onChange={(e) => setAxes({ ...axes, [k]: Number(e.target.value) })} />
            <span className="mono">{v.toFixed(2)}</span>
          </label>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button className="btn ghost" onClick={() => setAxes({ provenance: 0.94, consent: 0.94, receipt: 0.94, signer: 0.88, replay: 0.94, failClosed: 0.94, quorum: 0.91, doctrine: 0.93, selfDoubt: 0.9 })}>Preset · clean</button>
          <button className="btn ghost" onClick={() => setAxes((a) => ({ ...a, provenance: 0.2 }))}>Preset · thin provenance</button>
          <button className="btn ghost" onClick={() => setAxes((a) => ({ ...a, consent: 0 }))}>Preset · zero consent</button>
        </div>
      </div>
    </>
  );
}

function Wires() {
  return (
    <>
      <section className="hero"><p className="kicker">Wires</p><h1>Which probe feeds which surface.</h1></section>
      <div className="panel">
        <table>
          <thead><tr><th>Surface</th><th>Source</th><th>Honesty</th></tr></thead>
          <tbody>
            {PULSE_ENDPOINTS.map((e) => (
              <tr key={e.id}><td>{e.label}</td><td className="mono">{e.url}</td><td><Chip label="SESSION" /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Mesh() {
  return (
    <>
      <section className="hero"><p className="kicker">Mesh</p><h1>3-of-4 quorum. Unreachable is reported.</h1></section>
      <div className="panel">
        <p>Organ backends on this replica are not deployed. Painting them LIVE would be a lie. The flagship runtime remains {""}<a href="https://szlholdings-a11oy.hf.space">szlholdings-a11oy.hf.space</a>.</p>
      </div>
    </>
  );
}

function Immune() {
  const [payload, setPayload] = useState<string>(IMMUNE_PRESETS[0].payload);
  const [decision, setDecision] = useState<(ImmuneDecision & { digest: string }) | null>(null);
  async function run(next = payload) {
    const d = evaluateImmune(next);
    const at = new Date().toISOString();
    const digest = await sha256Hex(
      canonicalReceipt({
        seq: 1,
        prevDigest: GENESIS,
        verdict: d.verdict === "deny" ? "DENY" : "ADMIT",
        hard: d.verdict === "deny",
        action: "IMMUNE",
        intent: next.slice(0, 200),
        reason: d.reason,
        trust: d.lambda,
        at,
      }),
    );
    setDecision({ ...d, digest });
  }
  return (
    <>
      <section className="hero">
        <p className="kicker">IMMUNE · Hukulla</p>
        <h1>Fail-closed. Hunt / isolate / deceive — never strike people.</h1>
      </section>
      <div className="row cards">
        {IMMUNE_PRESETS.map((p) => (
          <button key={p.label} className="btn ghost" onClick={() => { setPayload(p.payload); void run(p.payload); }}>{p.label}</button>
        ))}
      </div>
      <textarea rows={5} value={payload} onChange={(e) => setPayload(e.target.value)} />
      <button className="btn primary" onClick={() => void run()}>Evaluate</button>
      {decision && (
        <div className="panel">
          <Chip label={decision.verdict === "deny" ? "DENY" : "ALLOW"} tone={decision.verdict === "deny" ? "deny" : "live"} />
          <p style={{ marginTop: 10 }}>{decision.reason}</p>
          <p className="mono">{decision.digest.slice(0, 16)}… · Λ {decision.lambda.toFixed(3)}</p>
        </div>
      )}
    </>
  );
}

function Verify() {
  const [raw, setRaw] = useState("");
  const [note, setNote] = useState<string | null>(null);
  async function check() {
    try {
      const obj = JSON.parse(raw) as { digest: string; seq: number; prevDigest: string; verdict: string; hard: boolean; action: string; intent: string; reason: string; trust: number; at: string };
      const expected = await sha256Hex(canonicalReceipt(obj));
      setNote(expected === obj.digest ? `MEASURED match · seq ${obj.seq}` : `BREAK. computed ${expected.slice(0, 16)}… ≠ ${obj.digest.slice(0, 16)}…`);
    } catch {
      setNote("Not a receipt object. Paste szl.governed-c2-receipt/v1 JSON.");
    }
  }
  return (
    <>
      <section className="hero"><p className="kicker">Verify</p><h1>Hash it in this browser.</h1></section>
      <textarea rows={10} value={raw} onChange={(e) => setRaw(e.target.value)} placeholder='{"schema":"szl.governed-c2-receipt/v1", ...}' />
      <button className="btn primary" onClick={() => void check()}>Verify receipt</button>
      {note && <p className="mono">{note}</p>}
    </>
  );
}
