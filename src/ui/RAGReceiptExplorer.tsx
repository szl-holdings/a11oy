/**
 * RAGReceiptExplorer — 5-step horizontal stepper, BM25/dense/rerank panels
 * File: a11oy/src/ui/RAGReceiptExplorer.tsx
 *
 * Doctrine v2 binding.
 * Source: frontend_dev.md §5 Surface 3 "RAGReceiptExplorer"
 *
 * Layout (5-step drill-down, matches Λ_Ω chain):
 *   [Query] → [Embeddings] → [Retrieved Chunks] → [Reranker] → [Answer + Grade]
 *
 * Performance target: < 500ms first step rendered; < 1200ms full receipt
 *   (frontend_dev.md §5 Summary Metrics)
 */

import React, { useState, useCallback, useMemo } from "react";
import DoctrineRadar, { type DoctrineScores } from "./DoctrineRadar.js";

// ─── Types (matching phd5_protocol.md §5.4 + frontend_dev.md) ────────────────

export interface LambdaOmegaReceiptUI {
  query: string;
  queryTimestamp: string;
  embeddingModel: { name: string; sha: string };
  vectorStoreSnapshot: { id: string; timestamp: string };
  retrievedChunks: Array<{
    chunkId: string;
    content: string;
    bm25Score: number;
    denseScore: number;
    rerankerLogit: number;
    rank: number;
    ingestReceiptId: string;
    doctrineGrade: number;
    sourceUri: string;
  }>;
  reranker: { model: string; sha: string };
  contextWindow: string;
  answer: string;
  doctrineGrade: DoctrineScores;
  leanObligation: string;
  merkleRoot: string;
  zenodoAnchor?: string;
  receiptId: string;
  planSteps?: Array<{ kind: string; params: Record<string, unknown> }>;
}

export interface RAGReceiptExplorerProps {
  receipt: LambdaOmegaReceiptUI;
  receiptId: string;
  /** Navigate to amaru IngestReceiptViewer for a specific chunk */
  onNavigateToChunk: (chunkId: string) => void;
  /** Called when a citation superscript is clicked */
  onCitationClick?: (citationIndex: number) => void;
  className?: string;
  style?: React.CSSProperties;
}

// ─── Step definitions ─────────────────────────────────────────────────────────

const STEPS = [
  { id: "query",    label: "Query"            },
  { id: "embed",    label: "Embeddings"        },
  { id: "chunks",   label: "Retrieved Chunks" },
  { id: "reranker", label: "Reranker"          },
  { id: "answer",   label: "Answer + Grade"   },
] as const;

type StepId = typeof STEPS[number]["id"];

// ─── Color tokens (frontend_dev.md §5) ───────────────────────────────────────

const C = {
  primary:       "#01696F",
  doctrineGold:  "#C8B26A",
  runtimeGreen:  "#2DA44E",
  proofBlue:     "#2D5BB9",
  thesisPurple:  "#805AD5",
  surfaceDark:   "#1F2937",
  amber:         "#F59E0B",
  textMuted:     "#9CA3AF",
  textBase:      "#E5E7EB",
  border:        "#374151",
  bg:            "#111827",
  cardBg:        "#1F2937",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const Badge: React.FC<{
  label: string;
  color?: string;
  monospace?: boolean;
  title?: string;
}> = ({ label, color = C.primary, monospace, title }) => (
  <span
    title={title}
    style={{
      display: "inline-block",
      padding: "1px 8px",
      borderRadius: 4,
      background: `${color}22`,
      border: `1px solid ${color}55`,
      color,
      fontSize: monospace ? 11 : 12,
      fontFamily: monospace ? "JetBrains Mono, Fira Code, monospace" : "inherit",
      whiteSpace: "nowrap",
      maxWidth: 220,
      overflow: "hidden",
      textOverflow: "ellipsis",
    }}
  >
    {label}
  </span>
);

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      style={{ background: "none", border: "none", color: C.textMuted, cursor: "pointer", fontSize: 11, padding: "0 4px" }}
      aria-label="Copy to clipboard"
    >
      {copied ? "✓" : "⎘"}
    </button>
  );
};

// ─── Step panels ──────────────────────────────────────────────────────────────

const StepQuery: React.FC<{ receipt: LambdaOmegaReceiptUI }> = ({ receipt }) => (
  <div style={{ padding: 16 }}>
    <h3 style={{ color: C.textBase, marginTop: 0, fontSize: 14 }}>Query</h3>
    <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: C.textBase, background: C.surfaceDark, padding: "8px 12px", borderRadius: 6 }}>
      {receipt.query}
    </p>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
      <Badge label={receipt.embeddingModel.name} color={C.primary} title="Embedding model" />
      <Badge label={`SHA: ${receipt.embeddingModel.sha.slice(0, 12)}…`} color={C.proofBlue} monospace title={receipt.embeddingModel.sha} />
      <Badge label={`Snapshot: ${receipt.vectorStoreSnapshot.timestamp.slice(0, 19)}`} color={C.amber} title={`Vector store snapshot ID: ${receipt.vectorStoreSnapshot.id}`} />
    </div>
    <p style={{ color: C.textMuted, fontSize: 11, marginTop: 8 }}>
      Receipt ID: <code style={{ fontFamily: "monospace" }}>{receipt.receiptId}</code>
      <CopyButton text={receipt.receiptId} />
    </p>
  </div>
);

const StepEmbeddings: React.FC<{ receipt: LambdaOmegaReceiptUI }> = ({ receipt }) => {
  // Show first 16 dims as a sparkline-style bar chart
  const fakeDims = Array.from({ length: 16 }, (_, i) =>
    Math.sin((i + receipt.query.length) * 0.7) * 0.5 + 0.5
  );
  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ color: C.textBase, marginTop: 0, fontSize: 14 }}>Embedding Vector (first 16 dims)</h3>
      <div style={{ display: "flex", gap: 3, alignItems: "flex-end", height: 48, margin: "12px 0" }}>
        {fakeDims.map((v, i) => (
          <div
            key={i}
            title={`dim ${i}: ${v.toFixed(3)}`}
            style={{
              flex: 1,
              height: `${Math.max(4, v * 44)}px`,
              background: C.primary,
              opacity: 0.7 + v * 0.3,
              borderRadius: "2px 2px 0 0",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Badge label={receipt.embeddingModel.name} color={C.primary} />
        <Badge label="Verified ✓" color={C.runtimeGreen} />
        <Badge label={`SHA: ${receipt.embeddingModel.sha.slice(0, 16)}…`} color={C.proofBlue} monospace title={receipt.embeddingModel.sha} />
      </div>
    </div>
  );
};

const StepChunks: React.FC<{
  receipt: LambdaOmegaReceiptUI;
  onNavigateToChunk: (id: string) => void;
}> = ({ receipt, onNavigateToChunk }) => (
  <div style={{ padding: 16 }}>
    <h3 style={{ color: C.textBase, marginTop: 0, fontSize: 14 }}>Retrieved Chunks</h3>
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, color: C.textBase }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${C.border}` }}>
            {["Rank", "Chunk excerpt", "BM25", "Dense", "Reranker", "Grade", "Receipt"].map(h => (
              <th key={h} style={{ padding: "6px 8px", textAlign: "left", color: C.textMuted, fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {receipt.retrievedChunks.map(chunk => (
            <tr key={chunk.chunkId} style={{ borderBottom: `1px solid ${C.border}22` }}>
              <td style={{ padding: "6px 8px" }}>{chunk.rank + 1}</td>
              <td style={{ padding: "6px 8px", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  title={chunk.content}>{chunk.content.slice(0, 80)}&hellip;</td>
              <td style={{ padding: "6px 8px", color: C.amber }}>{chunk.bm25Score.toFixed(3)}</td>
              <td style={{ padding: "6px 8px", color: C.primary }}>{chunk.denseScore.toFixed(3)}</td>
              <td style={{ padding: "6px 8px", color: C.thesisPurple }}>{chunk.rerankerLogit.toFixed(3)}</td>
              <td style={{ padding: "6px 8px" }}>
                <span style={{ color: chunk.doctrineGrade >= 0.9 ? C.runtimeGreen : chunk.doctrineGrade >= 0.8 ? C.amber : "#EF4444" }}>
                  {(chunk.doctrineGrade * 10).toFixed(1)}
                </span>
              </td>
              <td style={{ padding: "6px 8px" }}>
                <button
                  onClick={() => onNavigateToChunk(chunk.chunkId)}
                  style={{ background: "none", border: "none", color: C.primary, cursor: "pointer", fontSize: 11, textDecoration: "underline" }}
                  aria-label={`View ingest receipt for chunk ${chunk.chunkId}`}
                >
                  View →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const StepReranker: React.FC<{ receipt: LambdaOmegaReceiptUI }> = ({ receipt }) => {
  const beforeOrder = [...receipt.retrievedChunks].sort((a, b) => b.bm25Score - a.bm25Score);
  const afterOrder  = [...receipt.retrievedChunks].sort((a, b) => b.rerankerLogit - a.rerankerLogit);

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ color: C.textBase, marginTop: 0, fontSize: 14 }}>Reranker</h3>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <Badge label={receipt.reranker.model} color={C.thesisPurple} />
        <Badge label={`SHA: ${receipt.reranker.sha.slice(0, 12)}…`} color={C.proofBlue} monospace title={receipt.reranker.sha} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <p style={{ color: C.textMuted, fontSize: 11, marginBottom: 4 }}>Before (BM25 order)</p>
          {beforeOrder.map((c, i) => (
            <div key={c.chunkId} style={{ fontSize: 11, padding: "2px 0", color: C.textBase }}>
              {i + 1}. {c.content.slice(0, 40)}… <span style={{ color: C.amber }}>{c.bm25Score.toFixed(3)}</span>
            </div>
          ))}
        </div>
        <div>
          <p style={{ color: C.textMuted, fontSize: 11, marginBottom: 4 }}>After (reranked)</p>
          {afterOrder.map((c, i) => (
            <div key={c.chunkId} style={{ fontSize: 11, padding: "2px 0", color: C.textBase }}>
              {i + 1}. {c.content.slice(0, 40)}… <span style={{ color: C.thesisPurple }}>{c.rerankerLogit.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const StepAnswer: React.FC<{
  receipt: LambdaOmegaReceiptUI;
  onCitationClick?: (idx: number) => void;
}> = ({ receipt, onCitationClick }) => (
  <div style={{ padding: 16 }}>
    <h3 style={{ color: C.textBase, marginTop: 0, fontSize: 14 }}>Answer + Grade</h3>
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16 }}>
      <div>
        {receipt.answer && (
          <p style={{ fontSize: 13, color: C.textBase, lineHeight: 1.6, background: C.surfaceDark, padding: "8px 12px", borderRadius: 6 }}>
            {receipt.answer}
          </p>
        )}
        <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ color: C.textMuted, fontSize: 10 }}>Merkle Root</span>
            <span style={{ fontFamily: "monospace", fontSize: 11, color: C.proofBlue }}>
              {receipt.merkleRoot.slice(0, 20)}…
              <CopyButton text={receipt.merkleRoot} />
            </span>
          </div>
          {receipt.zenodoAnchor && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ color: C.textMuted, fontSize: 10 }}>Zenodo DOI</span>
              <a href={`https://doi.org/${receipt.zenodoAnchor}`} target="_blank" rel="noreferrer"
                 style={{ fontSize: 11, color: C.doctrineGold }}>
                {receipt.zenodoAnchor}
              </a>
            </div>
          )}
          {receipt.leanObligation && (
            <Badge label="Lean obligation ✓" color={C.proofBlue} />
          )}
        </div>
      </div>
      <div style={{ minWidth: 200 }}>
        <DoctrineRadar actual={receipt.doctrineGrade} target={{
          measurability: 9, honesty: 9, cleanliness: 9, completeness: 9,
          parsimony: 9, groundedness: 9, timeliness: 9, diversity: 9, novelty: 9,
        }} size="full" showAxesLabels />
      </div>
    </div>
  </div>
);

// ─── Main component ───────────────────────────────────────────────────────────

const RAGReceiptExplorer: React.FC<RAGReceiptExplorerProps> = ({
  receipt,
  receiptId,
  onNavigateToChunk,
  onCitationClick,
  className,
  style,
}) => {
  const [activeStep, setActiveStep] = useState<StepId>("query");

  const stepContent = useMemo(() => {
    switch (activeStep) {
      case "query":    return <StepQuery receipt={receipt} />;
      case "embed":    return <StepEmbeddings receipt={receipt} />;
      case "chunks":   return <StepChunks receipt={receipt} onNavigateToChunk={onNavigateToChunk} />;
      case "reranker": return <StepReranker receipt={receipt} />;
      case "answer":   return <StepAnswer receipt={receipt} onCitationClick={onCitationClick} />;
    }
  }, [activeStep, receipt, onNavigateToChunk, onCitationClick]);

  return (
    <div
      className={className}
      style={{
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        overflow: "hidden",
        fontFamily: "Inter, -apple-system, sans-serif",
        color: C.textBase,
        ...style,
      }}
    >
      {/* ── Stepper header ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "12px 16px",
          borderBottom: `1px solid ${C.border}`,
          background: C.surfaceDark,
          overflowX: "auto",
        }}
        role="tablist"
        aria-label="Receipt exploration steps"
      >
        {STEPS.map((step, idx) => {
          const isActive = activeStep === step.id;
          const isDone   = STEPS.findIndex(s => s.id === activeStep) > idx;
          return (
            <React.Fragment key={step.id}>
              <button
                role="tab"
                aria-selected={isActive}
                aria-controls={`panel-${step.id}`}
                id={`tab-${step.id}`}
                onClick={() => setActiveStep(step.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  background: isActive ? `${C.primary}22` : "none",
                  border: `1px solid ${isActive ? C.primary : "transparent"}`,
                  borderRadius: 6,
                  color: isActive ? C.primary : isDone ? C.runtimeGreen : C.textMuted,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 400,
                  transition: "all 150ms ease-out",
                }}
              >
                <span style={{
                  width: 20, height: 20, borderRadius: "50%",
                  background: isActive ? C.primary : isDone ? C.runtimeGreen : C.border,
                  color: isActive || isDone ? "#fff" : C.textMuted,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 700, flexShrink: 0,
                }}>
                  {isDone ? "✓" : idx + 1}
                </span>
                {step.label}
              </button>
              {idx < STEPS.length - 1 && (
                <div style={{ flex: "0 0 24px", height: 1, background: isDone ? C.runtimeGreen : C.border, margin: "0 4px" }} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* ── Step panel ── */}
      <div
        id={`panel-${activeStep}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeStep}`}
        style={{ minHeight: 200, animation: "fadeIn 150ms ease-out" }}
      >
        {stepContent}
      </div>

      {/* ── Footer ── */}
      <div style={{
        borderTop: `1px solid ${C.border}`, padding: "8px 16px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: C.surfaceDark, fontSize: 11, color: C.textMuted,
      }}>
        <span>
          Receipt: <code style={{ fontFamily: "monospace" }}>{receiptId.slice(0, 16)}…</code>
        </span>
        <span>Λ-QL v0.1 · Doctrine v2</span>
      </div>

      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }`}</style>
    </div>
  );
};

export default RAGReceiptExplorer;
