/**
 * LambdaQLEditor — Syntax-highlighted Λ-QL editor with live receipt preview
 * File: a11oy/src/ui/LambdaQLEditor.tsx
 *
 * Doctrine v2 binding.
 * Source: frontend_dev.md §5 Surface 3 "LambdaQLEditor"
 *
 * Layout:
 *   Left panel (60%): syntax-highlighted editor (textarea-based, no Monaco dep)
 *   Right panel (40%): live receipt preview JSON tree
 *   Bottom bar: Execute button, estimated latency badge, doctrine grade target
 *
 * Performance target: Execute → receipt preview rendered: < 800ms
 * Syntax token colors (frontend_dev.md §5):
 *   ask/ground/shape         → KnowQL primitive (slate blue)
 *   filter/control           → KnowQL constraint (amber)
 *   receipt/EMIT/lambda_receipt → Λ-extension (teal #01696F)
 *   grade/DOCTRINE/doctrine  → Λ-extension (purple #805AD5)
 */

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from "react";
import { parseLambdaQL }  from "../protocol/lambda-ql/parser.js";
import { compileLambdaQL } from "../protocol/lambda-ql/compiler.js";
import type { QueryPlan }  from "../protocol/lambda-ql/types.js";
import DoctrineRadar, { type DoctrineScores, DEFAULT_TARGET_SCORES } from "./DoctrineRadar.js";

// ─── Props ────────────────────────────────────────────────────────────────────

export interface LambdaQLEditorProps {
  initialQuery?: string;
  /** Called on Execute; receives the compiled plan + optional result */
  onExecute?: (
    query: string,
    plan: QueryPlan
  ) => Promise<{ doctrineGrade: DoctrineScores; receiptPreview: unknown }>;
  /** Show receipt preview panel while typing */
  livePreview?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

// ─── Default query (Founder Directive example) ───────────────────────────────

const DEFAULT_QUERY = `SELECT chunks
FROM amaru.corpus
WHERE sentra.faithfulness >= 0.95
  AND doctrine.grade >= 0.9
EMIT lambda_receipt
ANCHORED zenodo;`;

// ─── Color tokens ─────────────────────────────────────────────────────────────

const C = {
  primary:      "#01696F",
  gold:         "#C8B26A",
  green:        "#2DA44E",
  proofBlue:    "#2D5BB9",
  purple:       "#805AD5",
  amber:        "#F59E0B",
  surfaceDark:  "#1F2937",
  bg:           "#111827",
  border:       "#374151",
  textBase:     "#E5E7EB",
  textMuted:    "#6B7280",
  error:        "#EF4444",
};

// ─── Syntax highlighting ──────────────────────────────────────────────────────

interface HighlightToken {
  text: string;
  color: string;
}

function tokenize(source: string): HighlightToken[] {
  // Simple regex-based highlighter — no AST traversal needed
  const patterns: Array<{ re: RegExp; color: string }> = [
    // Comments
    { re: /--[^\n]*/g,                                 color: "#6B7280" },
    // EMIT / lambda_receipt / no_receipt / ANCHORED / zenodo / ipfs → teal
    { re: /\b(EMIT|ANCHORED|lambda_receipt|no_receipt|zenodo|ipfs|receipt)\b/gi, color: C.primary },
    // sentra predicates → teal
    { re: /\b(sentra\.\w+|SENTRA)\b/gi,                color: C.primary },
    // doctrine predicates → purple
    { re: /\b(doctrine\.\w+|DOCTRINE_GRADE|DOCTRINE)\b/gi, color: C.purple },
    // DML keywords → slate blue
    { re: /\b(SELECT|FROM|WHERE|ORDER|BY|LIMIT|BUDGET|WITH|EMIT|AS|JOIN|ON|AND|OR|NOT|IN|EXISTS|EXPLAIN|VERIFY|RECEIPT|AGAINST|CORPUS)\b/g, color: "#60A5FA" },
    // ORDER BY special tokens
    { re: /\b(SCORE|INGEST_TIME|ASC|DESC)\b/g,         color: "#93C5FD" },
    // Numeric literals
    { re: /\b\d+(\.\d+)?\b/g,                          color: "#34D399" },
    // String literals
    { re: /"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g,      color: "#FCA5A5" },
    // amaru namespace → soft green
    { re: /\bamaru\.\S+/g,                             color: "#6EE7B7" },
    // Operators
    { re: />=|<=|<>|!=|[><=]/g,                       color: C.amber },
    // Semicolons / punctuation
    { re: /[;(),\[\]]/g,                               color: "#9CA3AF" },
    // WITH option keywords → amber
    { re: /\b(receipt|explanation|lean_proof|corpus_snapshot|include_chunk_hashes|include_reranker_logits|include_embedding_sha|include_context_window_sha|include_lean_obligation_sha|merkle_algorithm|receipt_version|embedding_model|reranker)\b/gi, color: C.amber },
  ];

  // Build a sorted list of all matches
  type Match = { start: number; end: number; color: string };
  const matches: Match[] = [];

  for (const { re, color } of patterns) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(source)) !== null) {
      matches.push({ start: m.index, end: m.index + m[0].length, color });
    }
  }

  // Sort by start; resolve overlaps by keeping first match (highest-priority pattern wins first)
  matches.sort((a, b) => a.start - b.start);

  const tokens: HighlightToken[] = [];
  let cursor = 0;

  for (const match of matches) {
    if (match.start < cursor) continue; // overlapping — skip
    if (match.start > cursor) {
      tokens.push({ text: source.slice(cursor, match.start), color: C.textBase });
    }
    tokens.push({ text: source.slice(match.start, match.end), color: match.color });
    cursor = match.end;
  }
  if (cursor < source.length) {
    tokens.push({ text: source.slice(cursor), color: C.textBase });
  }
  return tokens;
}

// ─── Live validation ──────────────────────────────────────────────────────────

interface ValidationResult {
  valid: boolean;
  error?: string;
  plan?: QueryPlan;
  estimatedLatencyMs?: number;
}

function validateQuery(query: string): ValidationResult {
  if (!query.trim()) return { valid: false, error: "Query is empty" };
  try {
    parseLambdaQL(query);
    const plan = compileLambdaQL(query);
    const estimatedLatencyMs = plan.budget.latencyMs;
    return { valid: true, plan, estimatedLatencyMs };
  } catch (err) {
    return { valid: false, error: String(err) };
  }
}

// ─── Receipt preview ──────────────────────────────────────────────────────────

const ReceiptPreview: React.FC<{
  plan: QueryPlan | undefined;
  isExecuting: boolean;
  liveResult: unknown;
  doctrineGrade?: DoctrineScores;
}> = ({ plan, isExecuting, liveResult, doctrineGrade }) => {
  const previewData = liveResult ?? (plan
    ? {
        status: "PENDING — click Execute to run",
        planId: plan.planId,
        sourceRef: plan.sourceRef,
        steps: plan.steps.map(s => s.kind),
        budget: plan.budget,
        receiptSpec: plan.receiptSpec,
        anchor: plan.anchorTarget,
        sentraPredicates: plan.sentraPredicates.map(p => `${p.metric}${p.op}${p.value}`),
        doctrinePredicates: plan.doctrinePredicates.map(p => `${p.axis}${p.op}${p.value}`),
      }
    : { status: "Type a valid Λ-QL query to see preview" });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, height: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: C.textMuted }}>Receipt Preview</span>
        {isExecuting && (
          <span style={{ fontSize: 11, color: C.amber }}>● Executing…</span>
        )}
      </div>
      {doctrineGrade && (
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
          <DoctrineRadar
            actual={doctrineGrade}
            target={DEFAULT_TARGET_SCORES}
            size="mini"
          />
        </div>
      )}
      <pre style={{
        flex: 1,
        margin: 0,
        padding: "8px 12px",
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderRadius: 6,
        fontSize: 11,
        fontFamily: "JetBrains Mono, Fira Code, monospace",
        color: C.textBase,
        overflowY: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        opacity: liveResult ? 1 : 0.6,
        position: "relative",
      }}>
        {!liveResult && !plan && (
          <span style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", color: C.textMuted, fontSize: 12, textAlign: "center" }}>
            PENDING
          </span>
        )}
        {JSON.stringify(previewData, null, 2)}
      </pre>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const LambdaQLEditor: React.FC<LambdaQLEditorProps> = ({
  initialQuery = DEFAULT_QUERY,
  onExecute,
  livePreview = true,
  className,
  style,
}) => {
  const [query, setQuery]             = useState(initialQuery);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError]             = useState<string | undefined>();
  const [liveResult, setLiveResult]   = useState<unknown>(null);
  const [doctrineGrade, setDoctrineGrade] = useState<DoctrineScores | undefined>();

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);

  // Sync scroll between textarea and highlight overlay
  const syncScroll = useCallback(() => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop  = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  // Live validation
  const validation = useMemo(() => validateQuery(query), [query]);

  useEffect(() => {
    if (validation.valid) setError(undefined);
    else setError(validation.error);
  }, [validation]);

  const highlightedTokens = useMemo(() => tokenize(query), [query]);

  const handleExecute = useCallback(async () => {
    if (!validation.valid || !validation.plan) {
      setError(validation.error ?? "Invalid query");
      return;
    }
    setIsExecuting(true);
    setLiveResult(null);
    try {
      if (onExecute) {
        const result = await onExecute(query, validation.plan);
        setLiveResult(result.receiptPreview);
        setDoctrineGrade(result.doctrineGrade);
      } else {
        // Default: show plan as result
        setLiveResult({
          planId: validation.plan.planId,
          steps: validation.plan.steps.map(s => ({ kind: s.kind, params: s.params })),
          budget: validation.plan.budget,
          receiptSpec: validation.plan.receiptSpec,
          leanObligationTemplate: validation.plan.leanObligationTemplate.split("\n")[0],
          status: "Plan compiled successfully — wire onExecute to run against amaru",
        });
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setIsExecuting(false);
    }
  }, [query, validation, onExecute]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // ⌘+Enter or Ctrl+Enter to execute
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleExecute();
    }
    // Tab → insert 2 spaces
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = textareaRef.current;
      if (!ta) return;
      const { selectionStart, selectionEnd } = ta;
      const newVal = query.slice(0, selectionStart) + "  " + query.slice(selectionEnd);
      setQuery(newVal);
      requestAnimationFrame(() => {
        ta.selectionStart = ta.selectionEnd = selectionStart + 2;
      });
    }
  }, [handleExecute, query]);

  return (
    <div
      className={className}
      style={{
        display: "flex",
        flexDirection: "column",
        background: C.surfaceDark,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        overflow: "hidden",
        fontFamily: "Inter, -apple-system, sans-serif",
        ...style,
      }}
    >
      {/* ── Header ── */}
      <div style={{ padding: "8px 16px", borderBottom: `1px solid ${C.border}`, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 12, color: C.primary, fontWeight: 600 }}>Λ-QL Editor</span>
        <span style={{ fontSize: 10, color: C.textMuted }}>v0.1</span>
        <div style={{ flex: 1 }} />
        {validation.valid ? (
          <span style={{ fontSize: 11, color: C.green }}>✓ Valid</span>
        ) : (
          <span style={{ fontSize: 11, color: C.error }}>✗ Error</span>
        )}
      </div>

      {/* ── Body: editor + preview ── */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* ── Editor pane (60%) ── */}
        <div style={{ flex: "0 0 60%", position: "relative", borderRight: `1px solid ${C.border}` }}>
          {/* Highlight overlay */}
          <div
            ref={highlightRef}
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              padding: "12px 16px",
              fontFamily: "JetBrains Mono, Fira Code, monospace",
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              overflowY: "auto",
              overflowX: "auto",
              pointerEvents: "none",
              color: "transparent", // actual text is transparent; colors come from spans
            }}
          >
            {highlightedTokens.map((tok, i) => (
              <span key={i} style={{ color: tok.color }}>
                {tok.text}
              </span>
            ))}
          </div>
          {/* Actual textarea — transparent text on top */}
          <textarea
            ref={textareaRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onScroll={syncScroll}
            spellCheck={false}
            autoComplete="off"
            autoCorrect="off"
            aria-label="Λ-QL query editor"
            style={{
              position: "absolute",
              inset: 0,
              padding: "12px 16px",
              fontFamily: "JetBrains Mono, Fira Code, monospace",
              fontSize: 13,
              lineHeight: 1.6,
              background: "transparent",
              color: "transparent",
              caretColor: C.textBase,
              border: "none",
              outline: "none",
              resize: "none",
              overflowY: "auto",
              overflowX: "auto",
              whiteSpace: "pre",
            }}
          />
        </div>

        {/* ── Preview pane (40%) ── */}
        <div style={{ flex: "0 0 40%", padding: 12, overflowY: "auto" }}>
          <ReceiptPreview
            plan={validation.plan}
            isExecuting={isExecuting}
            liveResult={liveResult}
            doctrineGrade={doctrineGrade}
          />
        </div>
      </div>

      {/* ── Error bar ── */}
      {error && (
        <div style={{
          padding: "6px 16px",
          background: `${C.error}11`,
          borderTop: `1px solid ${C.error}44`,
          color: C.error,
          fontSize: 11,
          fontFamily: "JetBrains Mono, monospace",
        }}>
          {error}
        </div>
      )}

      {/* ── Bottom bar ── */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 16px",
        borderTop: `1px solid ${C.border}`,
        background: C.bg,
      }}>
        <button
          onClick={handleExecute}
          disabled={isExecuting || !validation.valid}
          aria-label="Execute Λ-QL query (⌘↵)"
          title="Execute (⌘↵)"
          style={{
            padding: "6px 16px",
            background: validation.valid ? C.primary : C.border,
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: validation.valid ? "pointer" : "not-allowed",
            fontSize: 13,
            fontWeight: 600,
            opacity: isExecuting ? 0.7 : 1,
            transition: "background 150ms",
          }}
        >
          {isExecuting ? "Running…" : "▶ Execute"}
        </button>
        <kbd style={{ fontSize: 10, color: C.textMuted, background: C.surfaceDark, border: `1px solid ${C.border}`, borderRadius: 3, padding: "1px 4px" }}>⌘↵</kbd>
        {validation.estimatedLatencyMs !== undefined && (
          <span style={{ fontSize: 11, color: C.textMuted }}>
            Budget: <span style={{ color: C.amber }}>{validation.estimatedLatencyMs}ms</span>
          </span>
        )}
        {validation.plan && (
          <span style={{ fontSize: 11, color: C.textMuted }}>
            Steps: <span style={{ color: C.textBase }}>{validation.plan.steps.length}</span>
            &nbsp;·&nbsp;
            Chunks: <span style={{ color: C.textBase }}>{validation.plan.budget.maxChunks}</span>
          </span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: C.textMuted }}>Λ-QL v0.1 · amaru.corpus</span>
      </div>
    </div>
  );
};

export default LambdaQLEditor;
