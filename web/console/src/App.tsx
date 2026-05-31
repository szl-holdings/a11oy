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
import { Link, Route, Switch, useRoute } from "wouter";
import { A11oyClient, CONSOLE_ROUTES, type OperationalReceipt } from "./a11oyClient.ts";

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

export default function App() {
  return (
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
          <Route>404 — not a console route</Route>
        </Switch>
      </main>
    </div>
  );
}
