// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
// a11oy.code — 7-tier organ-mapped LLM router UI (Doctrine v11 §14). ADDITIVE page at /code.
import { useEffect, useState } from "react";

type Tier = {
  tier: string;
  rank: number;
  organ: string;
  model_id: string;
  role: string;
  cost_per_1k_usd: number;
};

type RouteResult = {
  organ_routed: string;
  tier_used: string;
  llm_model_id: string;
  response: string;
  lambda_signal: number;
  latency_ms: number;
  cost_estimate_usd: number;
  traceparent_propagated: string | null;
  λ_receipt?: { signature_status: string };
};

const API = "/api/a11oy/v1/code";

export default function A11oyCode() {
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [query, setQuery] = useState("prove the lambda boundedness lemma in Lean");
  const [organ, setOrgan] = useState("");
  const [auto, setAuto] = useState(true);
  const [result, setResult] = useState<RouteResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API}/tiers`)
      .then((r) => r.json())
      .then((d) => setTiers(d.tiers || []))
      .catch(() => setTiers([]));
  }, []);

  async function runRoute() {
    setBusy(true);
    const endpoint = auto ? `${API}/auto` : `${API}/route`;
    const body: Record<string, unknown> = {
      query,
      axis_scores: Array(13).fill(0.96),
      require_λ_receipt: true,
      traceparent: "00-a11oycode-localspan-01",
    };
    if (!auto) body.organ_context = organ;
    try {
      const r = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setResult(await r.json());
    } catch {
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: "2rem 1.25rem", color: "#e8eef6" }}>
      <h1 style={{ fontSize: "1.9rem", fontWeight: 800 }}>a11oy.code</h1>
      <p style={{ opacity: 0.8 }}>
        7-tier organ-mapped LLM router baked into the anatomy. Doctrine v11 §14. The
        response is an honest stub (no model key wired); tier selection, organ routing,
        Λ-signal and the Λ-receipt are real deterministic math. Λ-receipt signature is a{" "}
        <strong>PLACEHOLDER</strong> (Sigstore not wired); traceparent is in-process only
        (Wire D not yet implemented).
      </p>

      <section style={{ margin: "1.5rem 0" }}>
        <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>7 tiers → 7 organs</h2>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: ".9rem" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #2a3a4f" }}>
              <th>Tier</th><th>Organ</th><th>Model</th><th>Role</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map((t) => (
              <tr key={t.tier} style={{ borderBottom: "1px solid #1a2536" }}>
                <td><strong>{t.tier}</strong></td>
                <td>{t.organ}</td>
                <td style={{ fontFamily: "monospace" }}>{t.model_id}</td>
                <td>{t.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ margin: "1.5rem 0" }}>
        <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Route a query</h2>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          style={{ width: "100%", background: "#0d1726", color: "#e8eef6", padding: ".6rem", borderRadius: 8 }}
        />
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", margin: ".6rem 0" }}>
          <label>
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> auto-route
          </label>
          {!auto && (
            <input
              placeholder="organ_context (e.g. SUMAQ, SENTRA, YUYAY)"
              value={organ}
              onChange={(e) => setOrgan(e.target.value)}
              style={{ flex: 1, background: "#0d1726", color: "#e8eef6", padding: ".4rem", borderRadius: 6 }}
            />
          )}
          <button onClick={runRoute} disabled={busy} style={{ padding: ".5rem 1rem", borderRadius: 8 }}>
            {busy ? "routing…" : "route"}
          </button>
        </div>
      </section>

      {result && (
        <section style={{ background: "#0d1726", padding: "1rem", borderRadius: 10 }}>
          <p>
            <strong>Organ:</strong> {result.organ_routed} · <strong>Tier:</strong> {result.tier_used} ·{" "}
            <strong>Model:</strong> <code>{result.llm_model_id}</code>
          </p>
          <p>
            <strong>Λ-signal:</strong> {result.lambda_signal} · <strong>latency:</strong>{" "}
            {result.latency_ms} ms · <strong>est. cost:</strong> ${result.cost_estimate_usd}
          </p>
          <p style={{ opacity: 0.85 }}>{result.response}</p>
          {result.λ_receipt && (
            <p style={{ fontSize: ".8rem", opacity: 0.65 }}>{result.λ_receipt.signature_status}</p>
          )}
        </section>
      )}
    </main>
  );
}
