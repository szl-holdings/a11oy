import { useEffect, useState } from 'react';
import { Anchor, Sigma } from 'lucide-react';
import { emitProof, crossProductHandoff } from '@workspace/a11oy-orchestration/client';

const API_BASE = '/api/sigil';

interface SigilReport {
        sigma: number;
        axes: { provenance: number; containment: number; coherence: number; convergence: number };
        weights: Record<string, { value: number; rendered: string }>;
        proof: { weightsExact: boolean; minAxis: number; maxAxis: number; formula: string; law: string };
}

const AXES = [
        { key: 'provenance', label: 'Provenance', sym: 'P', blurb: 'Pipeline lineage verified end-to-end · shift-add accumulator over leaf hashes' },
        { key: 'containment', label: 'Containment', sym: 'K', blurb: 'Sync-batch release rate inside boundary capacity · bounded saturation' },
        { key: 'coherence', label: 'Coherence', sym: 'Φ', blurb: 'Worker-fleet phase-lock across regions · order parameter r' },
        { key: 'convergence', label: 'Convergence', sym: 'C', blurb: 'Multi-witness reconciliation across mirrors · Jaccard intersection-over-union' },
] as const;

export default function ConduitSigil() {
        const [axes, setAxes] = useState({ provenance: 0.97, containment: 0.74, coherence: 0.89, convergence: 0.95 });
        const [report, setReport] = useState<SigilReport | null>(null);
        const [anchored, setAnchored] = useState(false);

        const anchorToA11oy = async () => {
                if (!report) return;
                setAnchored(true);
                const sigmaPctVal = (report.sigma * 100).toFixed(1);
                await emitProof({
                        product: 'amaru',
                        kind: 'action_executed',
                        summary: `Amaru anchored Σ=${sigmaPctVal}% trust envelope to the A11oy ledger`,
                        deepLink: '/conduit/sigil',
                        payload: {
                                sigma: report.sigma,
                                axes: report.axes,
                                formula: report.proof.formula,
                        },
                });
                if (report.sigma < 0.6) {
                        await crossProductHandoff({
                                fromProduct: 'amaru',
                                toProduct: 'sentra',
                                refId: `sigil-${Date.now().toString(36)}`,
                                reason: `Σ=${sigmaPctVal}% below trust floor — request cyber-resilience review`,
                                deepLink: '/conduit/sigil',
                        });
                }
        };

        const compose = async (next: typeof axes) => {
                try {
                        const r = await fetch(`${API_BASE}/compose`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ axes: next }),
                        });
                        if (r.ok) setReport((await r.json()) as SigilReport);
                } catch {
                        /* ignore */
                }
        };

        useEffect(() => {
                void compose(axes);
                // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);

        const sigmaPct = report ? (report.sigma * 100).toFixed(1) : '—';

        return (
                <div className="p-8 space-y-8 max-w-5xl mx-auto">
                        <div>
                                <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-ink mb-2">
                                        SIGIL · SZL Integrated Governance &amp; Invariant Layer
                                </div>
                                <h1 className="text-4xl font-semibold tracking-tight text-ink">Σ — pipeline trust envelope.</h1>
                                <p className="mt-3 text-ink-sub max-w-2xl text-sm leading-relaxed">
                                        Amaru exposes runtime trust as four independent axes and a single composed scalar Σ. The composition is a
                                        weighted geometric mean over rational unit-fraction weights — bit-exact reproducible, monotone in every
                                        axis, and pinned to zero whenever any axis collapses.
                                </p>
                        </div>

                        <div className="rounded-lg border border-line-subtle bg-ground-deep p-8 flex items-center gap-8 backdrop-blur">
                                <Sigma className="h-12 w-12 text-ink" />
                                <div>
                                        <div className="text-7xl font-extralight tabular-nums text-ink">
                                                {sigmaPct}
                                                <span className="text-3xl text-ink-sub">%</span>
                                        </div>
                                        <div className="text-xs font-mono uppercase tracking-widest text-ink-sub mt-1">
                                                {report ? `min ≤ Σ ≤ max · floor ${(report.proof.minAxis * 100).toFixed(1)}% · ceil ${(report.proof.maxAxis * 100).toFixed(1)}%` : 'composing…'}
                                        </div>
                                </div>
                        </div>

                        <div className="grid sm:grid-cols-2 gap-4">
                                {AXES.map(({ key, label, sym, blurb }) => {
                                        const v = axes[key];
                                        return (
                                                <div key={key} className="rounded-lg border border-line bg-ground-deep p-5 backdrop-blur">
                                                        <div className="flex items-center justify-between mb-2">
                                                                <span className="font-medium text-ink">
                                                                        {label} <span className="font-mono text-ink-sub">({sym})</span>
                                                                </span>
                                                                <span className="font-mono text-sm tabular-nums text-ink">{(v * 100).toFixed(1)}%</span>
                                                        </div>
                                                        <input
                                                                type="range"
                                                                min={0}
                                                                max={1}
                                                                step={0.01}
                                                                value={v}
                                                                onChange={(e) => {
                                                                        const next = { ...axes, [key]: Number(e.target.value) };
                                                                        setAxes(next);
                                                                        void compose(next);
                                                                }}
                                                                className="w-full accent-ink"
                                                        />
                                                        <div className="mt-2 text-xs text-ink-sub">{blurb}</div>
                                                </div>
                                        );
                                })}
                        </div>

                        {report && (
                                <div className="rounded-lg border border-line bg-ground-deep p-5 backdrop-blur">
                                        <div className="text-[10px] font-mono uppercase tracking-widest text-ink-sub mb-2">composition law</div>
                                        <div className="font-mono text-sm break-all text-ink">{report.proof.formula}</div>
                                        <div className="mt-2 text-xs text-ink-sub">{report.proof.law}</div>
                                </div>
                        )}

                        {report && (
                                <button
                                        type="button"
                                        onClick={() => { void anchorToA11oy(); }}
                                        disabled={anchored}
                                        className="flex items-center gap-2 px-4 py-2 rounded-md bg-wash/8 border border-line text-ink hover:bg-wash/16 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
                                >
                                        <Anchor className="w-4 h-4" />
                                        {anchored ? 'Anchored to A11oy ledger' : 'Anchor Σ to A11oy ledger'}
                                </button>
                        )}
                </div>
        );
}
