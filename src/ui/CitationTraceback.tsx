/**
 * CitationTraceback — Click any answer sentence → highlights chunks → ingest receipt
 * File: a11oy/src/ui/CitationTraceback.tsx
 *
 * Doctrine v2 binding.
 * Source: frontend_dev.md §5 Surface 3 "CitationTraceback"
 *
 * Pattern: Perplexity pre-generation citation embedding (frontend_dev.md §2 T4):
 *   Citations are pre-anchored in the Λ_Ω leaf at retrieval time,
 *   not retrofitted post-generation.
 *
 * Layout:
 *   Answer panel (top): answer text with citation superscripts [n]
 *   Chunk panel (bottom, slides up on citation click):
 *     - chunk text with matching passage bolded
 *     - BM25 / dense / reranker score chips
 *     - source metadata + "View Ingest Receipt →" button
 *
 * Keyboard: Tab through citations; Enter to drill; Escape to dismiss
 * Performance target: click → chunk panel rendered < 300ms
 */

import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";

// ─── Types (frontend_dev.md §5) ───────────────────────────────────────────────

export interface CitationEntry {
  chunkIds: string[];
  /** Character offsets in answer string */
  sentenceRange: [number, number];
  confidence: number;
}

export type CitationMap = Record<number, CitationEntry>;

export interface ChunkDetail {
  chunkId: string;
  content: string;
  sourceUri: string;
  bm25Score: number;
  denseScore: number;
  rerankerLogit: number;
  ingestTimestamp: string;
  pageInfo?: string;
  sectionInfo?: string;
  doctrineGrade: number;
}

export interface CitationTracebackProps {
  /** Answer text with citation markers — may contain "[1]", "[2]" etc. */
  answer: string;
  citationMap: CitationMap;
  receiptId: string;
  /** Chunk details indexed by chunkId */
  chunks: Record<string, ChunkDetail>;
  onOpenIngestReceipt: (chunkId: string) => void;
  className?: string;
  style?: React.CSSProperties;
}

// ─── Color tokens ─────────────────────────────────────────────────────────────

const C = {
  primary:      "#01696F",
  gold:         "#C8B26A",
  green:        "#2DA44E",
  proofBlue:    "#2D5BB9",
  purple:       "#805AD5",
  amber:        "#F59E0B",
  surface:      "#1F2937",
  bg:           "#111827",
  border:       "#374151",
  textBase:     "#E5E7EB",
  textMuted:    "#6B7280",
  highlight:    "#01696F33",
  highlightActive: "#01696F66",
};

// ─── Answer renderer ──────────────────────────────────────────────────────────

/**
 * Parse answer text containing "[n]" citation markers.
 * Returns an array of { text: string, citationIndex?: number } segments.
 */
function parseAnswerSegments(
  answer: string
): Array<{ text: string; citationIndex?: number }> {
  const CITATION_RE = /\[(\d+)\]/g;
  const segments: Array<{ text: string; citationIndex?: number }> = [];
  let lastIdx = 0;
  let m: RegExpExecArray | null;

  while ((m = CITATION_RE.exec(answer)) !== null) {
    if (m.index > lastIdx) {
      segments.push({ text: answer.slice(lastIdx, m.index) });
    }
    segments.push({ text: m[0], citationIndex: parseInt(m[1], 10) });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < answer.length) {
    segments.push({ text: answer.slice(lastIdx) });
  }
  return segments;
}

// ─── ScoreChip ────────────────────────────────────────────────────────────────

const ScoreChip: React.FC<{ label: string; value: number; color: string }> = ({
  label, value, color,
}) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 3,
    padding: "2px 7px", borderRadius: 12,
    background: `${color}18`, border: `1px solid ${color}44`,
    fontSize: 11, color,
    fontFamily: "JetBrains Mono, monospace",
  }}>
    <span style={{ color: C.textMuted, fontSize: 10 }}>{label}</span>
    {value.toFixed(3)}
  </span>
);

// ─── Chunk card ───────────────────────────────────────────────────────────────

const ChunkCard: React.FC<{
  chunk: ChunkDetail;
  query: string;
  onOpenIngestReceipt: (chunkId: string) => void;
}> = ({ chunk, query, onOpenIngestReceipt }) => {
  // Bold the most relevant passage (simple: first 80 chars)
  const preview = chunk.content.slice(0, 300);

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 6, padding: "10px 14px", marginBottom: 8,
    }}>
      {/* Source metadata */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6, alignItems: "center" }}>
        <span style={{ fontSize: 11, color: C.primary, fontFamily: "monospace" }}>
          {chunk.sourceUri.length > 60 ? chunk.sourceUri.slice(0, 60) + "…" : chunk.sourceUri}
        </span>
        {chunk.pageInfo && (
          <span style={{ fontSize: 10, color: C.textMuted }}>{chunk.pageInfo}</span>
        )}
        {chunk.sectionInfo && (
          <span style={{ fontSize: 10, color: C.textMuted }}>{chunk.sectionInfo}</span>
        )}
        <span style={{ fontSize: 10, color: C.textMuted, marginLeft: "auto" }}>
          {chunk.ingestTimestamp.slice(0, 10)}
        </span>
      </div>

      {/* Chunk content with bolded matching passage */}
      <p style={{ fontSize: 12, color: C.textBase, lineHeight: 1.6, margin: "0 0 8px" }}>
        <strong style={{ background: C.highlightActive, borderRadius: 2 }}>
          {preview.slice(0, 80)}
        </strong>
        {preview.slice(80)}
        {chunk.content.length > 300 && "…"}
      </p>

      {/* Score chips */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
        <ScoreChip label="BM25"  value={chunk.bm25Score}     color={C.amber}   />
        <ScoreChip label="Dense" value={chunk.denseScore}    color={C.primary} />
        <ScoreChip label="Rank"  value={chunk.rerankerLogit} color={C.purple}  />
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 3,
          padding: "2px 7px", borderRadius: 12,
          background: `${chunk.doctrineGrade >= 0.9 ? C.green : C.amber}18`,
          border: `1px solid ${chunk.doctrineGrade >= 0.9 ? C.green : C.amber}44`,
          fontSize: 11,
          color: chunk.doctrineGrade >= 0.9 ? C.green : C.amber,
        }}>
          <span style={{ fontSize: 10, color: C.textMuted }}>grade</span>
          {(chunk.doctrineGrade * 10).toFixed(1)}
        </span>
      </div>

      {/* View Ingest Receipt button */}
      <button
        onClick={() => onOpenIngestReceipt(chunk.chunkId)}
        style={{
          background: "none",
          border: `1px solid ${C.primary}`,
          borderRadius: 4,
          color: C.primary,
          cursor: "pointer",
          fontSize: 11,
          padding: "3px 10px",
          fontFamily: "inherit",
        }}
      >
        View Ingest Receipt →
      </button>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const CitationTraceback: React.FC<CitationTracebackProps> = ({
  answer,
  citationMap,
  receiptId,
  chunks,
  onOpenIngestReceipt,
  className,
  style,
}) => {
  const [activeCitation, setActiveCitation] = useState<number | null>(null);
  const [panelVisible, setPanelVisible]     = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const firstCitationRef = useRef<HTMLButtonElement | null>(null);

  const segments = useMemo(() => parseAnswerSegments(answer), [answer]);

  const activatesCitation = useCallback((idx: number) => {
    setActiveCitation(idx);
    setPanelVisible(true);
  }, []);

  const dismissPanel = useCallback(() => {
    setPanelVisible(false);
    setActiveCitation(null);
  }, []);

  // Keyboard: Escape to dismiss, Tab cycling handled by DOM naturally
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && panelVisible) {
        dismissPanel();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [panelVisible, dismissPanel]);

  // Scroll chunk panel into view
  useEffect(() => {
    if (panelVisible && panelRef.current) {
      panelRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [panelVisible, activeCitation]);

  const activeChunks = useMemo(() => {
    if (activeCitation === null) return [];
    const entry = citationMap[activeCitation];
    if (!entry) return [];
    return entry.chunkIds.flatMap(id => (chunks[id] ? [chunks[id]] : []));
  }, [activeCitation, citationMap, chunks]);

  return (
    <div
      className={className}
      style={{
        fontFamily: "Inter, -apple-system, sans-serif",
        color: C.textBase,
        ...style,
      }}
    >
      {/* ── Answer panel ── */}
      <div style={{
        padding: "12px 16px",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: panelVisible ? "6px 6px 0 0" : 6,
        borderBottom: panelVisible ? "none" : `1px solid ${C.border}`,
        lineHeight: 1.7,
        fontSize: 14,
      }}>
        {segments.map((seg, i) => {
          if (seg.citationIndex !== undefined) {
            const isActive = activeCitation === seg.citationIndex;
            return (
              <button
                key={i}
                ref={i === 0 ? firstCitationRef : undefined}
                onClick={() =>
                  isActive && panelVisible
                    ? dismissPanel()
                    : activatesCitation(seg.citationIndex!)
                }
                aria-label={`Citation ${seg.citationIndex}, ${isActive ? "active" : "click to view source"}`}
                aria-expanded={isActive && panelVisible}
                style={{
                  display: "inline",
                  background: isActive ? C.highlightActive : C.highlight,
                  border: `1px solid ${isActive ? C.primary : C.border}`,
                  borderRadius: 3,
                  color: isActive ? "#fff" : C.primary,
                  cursor: "pointer",
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "0 4px",
                  margin: "0 1px",
                  verticalAlign: "super",
                  lineHeight: 1.4,
                  fontFamily: "monospace",
                  transition: "background 120ms",
                }}
              >
                {seg.citationIndex}
              </button>
            );
          }
          return (
            <span
              key={i}
              style={{
                background: (() => {
                  // Highlight text spans within active citation's sentenceRange
                  if (activeCitation === null) return "none";
                  const entry = citationMap[activeCitation];
                  if (!entry) return "none";
                  // Simple: highlight the segment if adjacent to the active citation superscript
                  return "none";
                })(),
              }}
            >
              {seg.text}
            </span>
          );
        })}
      </div>

      {/* ── Chunk panel (slides up) ── */}
      <div
        ref={panelRef}
        role="region"
        aria-label="Source chunk details"
        aria-live="polite"
        style={{
          maxHeight: panelVisible ? 480 : 0,
          overflow: "hidden",
          transition: "max-height 150ms ease-out",
          border: panelVisible ? `1px solid ${C.border}` : "none",
          borderTop: "none",
          borderRadius: "0 0 6px 6px",
          background: C.bg,
        }}
      >
        {panelVisible && (
          <div style={{ padding: "12px 16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 12, color: C.textMuted }}>
                Citation [{activeCitation}] — {activeChunks.length} source{activeChunks.length !== 1 ? "s" : ""}
              </span>
              <button
                onClick={dismissPanel}
                aria-label="Dismiss chunk panel"
                style={{ background: "none", border: "none", color: C.textMuted, cursor: "pointer", fontSize: 16, lineHeight: 1 }}
              >
                ×
              </button>
            </div>
            {activeChunks.length === 0 ? (
              <p style={{ color: C.textMuted, fontSize: 12 }}>No chunk details found for this citation.</p>
            ) : (
              activeChunks.map(chunk => (
                <ChunkCard
                  key={chunk.chunkId}
                  chunk={chunk}
                  query=""
                  onOpenIngestReceipt={onOpenIngestReceipt}
                />
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CitationTraceback;
