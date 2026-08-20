// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// App.tsx — the a11oy operator console SPA. Five working routes, each backed by
// a real a11oy `serve` HTTP endpoint via A11oyClient. Self-contained: the only
// dependencies are react, react-dom, and wouter. It does not import the legacy
// 471-import surface (web/src/App.tsx); that surface is tracked separately as
// engineering debt and is left in place per Operating Principle #10 (annotate,
// do not silently delete).
//
// The a11oy base URL is read from VITE_A11OY_BASE_URL (default same origin).
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import { useEffect, useState } from "react";
import { Link, Route, Router, Switch, useRoute } from "wouter";
import { A11oyClient, CONSOLE_ROUTES, type OperationalReceipt, type KhipuTrace } from "./a11oyClient.ts";

// The SPA is deployed at /console/ (Vite base=/console/). Wouter must strip
// that prefix from browser pathnames before matching routes.
const ROUTER_BASE = "/console";

const BASE = (import.meta.env?.VITE_A11OY_BASE_URL as string | undefined) ?? "";
const client = new A11oyClient(BASE || window.location.origin);

function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): { data: T | null; error: string | null; loading: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    setLoading(true);
    fn()
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live) setError(String(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

function HealthRoute() {
  const health = useAsync(() => client.health(), []);
  const ready = useAsync(() => client.readiness(), []);
  return (
    <section>
      <h2>Health</h2>
      {health.loading ? <p>loading…</p> : health.error ? <p className="err">{health.error}</p> : (
        <pre>{JSON.stringify(health.data, null, 2)}</pre>
      )}
      <h3>Readiness</h3>
      {ready.loading ? <p>loading…</p> : ready.error ? <p className="err">{ready.error}</p> : (
        <pre>{JSON.stringify(ready.data, null, 2)}</pre>
      )}
    </section>
  );
}

function LedgerRoute() {
  const page = useAsync(() => client.ledger(20), []);
  return (
    <section>
      <h2>Proof Ledger</h2>
      {page.loading ? <p>loading…</p> : page.error ? <p className="err">{page.error}</p> : (
        <>
          <p>{page.data?.count} of {page.data?.total} receipts</p>
          <ul>
            {page.data?.receipts.map((r: OperationalReceipt, i) => (
              <li key={i}>
                <Link href={`/receipt/${encodeURIComponent(String(r.merkle_root ?? r.receipt_id ?? i))}`}>
                  {String(r.receipt_id ?? r.merkle_root ?? `#${i}`)}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function ReceiptRoute() {
  const [, params] = useRoute("/receipt/:hash");
  const hash = params?.hash ?? "";
  const out = useAsync(() => client.receipt(hash), [hash]);
  return (
    <section>
      <h2>Receipt {hash}</h2>
      {out.loading ? <p>loading…</p> : out.error ? <p className="err">{out.error}</p> : (
        <pre>{JSON.stringify(out.data?.receipt, null, 2)}</pre>
      )}
    </section>
  );
}

function VerifyRoute() {
  const [text, setText] = useState("[]");
  const [result, setResult] = useState<string>("");
  const run = async () => {
    try {
      const ledger = JSON.parse(text);
      const r = await client.verify(ledger);
      setResult(JSON.stringify(r, null, 2));
    } catch (e) {
      setResult(String(e));
    }
  };
  return (
    <section>
      <h2>Verify</h2>
      <p>Paste a receipt ledger array; POSTs to <code>/v1/verify</code>.</p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} cols={60} />
      <div><button onClick={run}>Verify chain</button></div>
      <pre>{result}</pre>
    </section>
  );
}

function PolicyRoute() {
  const [severity, setSeverity] = useState("medium");
  const [result, setResult] = useState<string>("");
  const run = async () => {
    const r = await client.evaluatePolicy({ actionId: "console-action", severity: severity as never, confidence: 0.8 });
    setResult(JSON.stringify(r, null, 2));
  };
  return (
    <section>
      <h2>Policy</h2>
      <p>Evaluate a severity against the real threshold gate (<code>/v1/policy/evaluate</code>).</p>
      <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
        {["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <button onClick={run}>Evaluate</button>
      <pre>{result}</pre>
    </section>
  );
}

// Gold honesty banner colour from the existing card badge palette.
const GOLD = "#d7b96b";

function CopyButton({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button onClick={copy} style={{ marginRight: 8 }}>
      {copied ? "copied ✓" : label}
    </button>
  );
}

function TraceCard({ trace, localRun }: { trace: KhipuTrace; localRun?: string }) {
  const inputStr = JSON.stringify(trace.inputJson, null, 2);
  // Pretty-print the model output if it parses; otherwise show the raw string.
  let outputStr = trace.outputJson;
  try {
    outputStr = JSON.stringify(JSON.parse(trace.outputJson), null, 2);
  } catch {
    /* raw output is not JSON — show verbatim */
  }
  return (
    <article style={{ border: "1px solid #2a2a2a", borderRadius: 6, padding: 12, marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>
        {trace.caseId}{" "}
        <span style={{ fontSize: "0.7em", color: GOLD, textTransform: "uppercase" }}>[{trace.category}]</span>
      </h3>
      <p style={{ fontSize: "0.85em" }}>
        source <code>{trace.sourceFile}</code> · decision <code>{String(trace.decision)}</code> ·
        schema-valid <code>{String(trace.schemaValid)}</code> · seed <code>{trace.seed}</code>
      </p>
      <p style={{ fontSize: "0.9em" }}>{trace.verdict}</p>
      <div style={{ margin: "8px 0" }}>
        <CopyButton label="Copy input JSON" text={inputStr} />
        <CopyButton label="Copy output JSON" text={outputStr} />
        {localRun ? <CopyButton label="Copy local run command" text={localRun} /> : null}
      </div>
      <details>
        <summary>Input JSON (prompt)</summary>
        <pre>{inputStr}</pre>
      </details>
      <details>
        <summary>Output JSON (model plan)</summary>
        <pre>{outputStr}</pre>
      </details>
    </article>
  );
}

function KhipuDemoRoute() {
  const demo = useAsync(() => client.khipuDemo(), []);
  const localRun = demo.data?.provenance?.localRunCommand;
  return (
    <section>
      <h2>Khipu Demo</h2>
      <div
        style={{
          border: `2px solid ${GOLD}`,
          borderRadius: 6,
          padding: 12,
          marginBottom: 16,
          color: GOLD,
        }}
      >
        <strong>RECORDED · AGENT-RUN.</strong>{" "}
        {demo.data?.provenance?.label ??
          "RECORDED 2026-07-16, AGENT-RUN, llama.cpp CPU, Q4_K_M quant — not live inference, not the signed-receipt artifact"}
        {demo.data?.provenance?.harnessSource ? (
          <div style={{ fontSize: "0.8em", marginTop: 6 }}>
            harness: <code>{demo.data.provenance.harnessSource}</code>
          </div>
        ) : null}
        {localRun ? (
          <div style={{ fontSize: "0.8em", marginTop: 6 }}>
            local run (quant): <code>{localRun}</code>{" "}
            <CopyButton label="Copy" text={localRun} />
          </div>
        ) : null}
      </div>
      {demo.loading ? (
        <p>loading…</p>
      ) : demo.error ? (
        <p className="err">{demo.error}</p>
      ) : demo.data?.ok === false ? (
        <p className="err">{demo.data.error ?? "demo unavailable"}</p>
      ) : (
        (demo.data?.traces ?? []).map((t) => <TraceCard key={t.caseId} trace={t} localRun={localRun} />)
      )}
    </section>
  );
}

export default function App() {
  return (
    <Router base={ROUTER_BASE}>
      <div className="console">
        <header>
          <h1>a11oy operator console</h1>
          <nav>
            {CONSOLE_ROUTES.map((r) => (
              <Link key={r.path} href={r.path.replace(":hash", "")}>{r.label}</Link>
            ))}
          </nav>
        </header>
        <main>
          <Switch>
            <Route path="/" component={HealthRoute} />
            <Route path="/ledger" component={LedgerRoute} />
            <Route path="/receipt/:hash" component={ReceiptRoute} />
            <Route path="/verify" component={VerifyRoute} />
            <Route path="/policy" component={PolicyRoute} />
            <Route path="/khipu-demo" component={KhipuDemoRoute} />
            <Route>404 — not a console route</Route>
          </Switch>
        </main>
      </div>
    </Router>
  );
}
