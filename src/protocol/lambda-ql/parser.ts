/**
 * Λ-QL Parser — Recursive descent producing typed AST
 * File: a11oy/src/protocol/lambda-ql/parser.ts
 *
 * Doctrine v2 binding. Zero dependencies (imports lexer.ts + types.ts only).
 * Runs in Node.js, Deno, and browser environments.
 *
 * Grammar: phd5_protocol.md §5.1 EBNF
 * Reference stubs: phd5_protocol.md §5.7
 *
 * Accepts the canonical Founder Directive example:
 *   SELECT chunks FROM amaru.corpus
 *   WHERE sentra.faithfulness >= 0.95 AND doctrine.grade >= 0.9
 *   EMIT lambda_receipt ANCHORED zenodo;
 */

import { tokenize } from "./lexer.js";
import type {
  Token,
  TokenKind,
  LambdaQLStatement,
  SelectStatement,
  ExplainStatement,
  VerifyStatement,
  ProjectionClause,
  ProjectionItem,
  SourceClause,
  JoinClause,
  Predicate,
  CompOp,
  Expr,
  OrderingItem,
  BudgetClause,
  WithOption,
  EmitClause,
  EmitOption,
  AnchorClause,
} from "./types.js";
import { LambdaQLCompileError } from "./types.js";

// ─── Parser ───────────────────────────────────────────────────────────────────

export class LambdaQLParser {
  private readonly tokens: Token[];
  private pos: number = 0;

  constructor(input: string) {
    this.tokens = tokenize(input);
  }

  // ── Token navigation ─────────────────────────────────────────────────────────

  private peek(offset = 0): Token {
    const idx = Math.min(this.pos + offset, this.tokens.length - 1);
    return this.tokens[idx];
  }

  private advance(): Token {
    const t = this.tokens[this.pos];
    if (this.pos < this.tokens.length - 1) this.pos++;
    return t;
  }

  private check(kind: TokenKind, value?: string): boolean {
    const t = this.peek();
    if (t.kind !== kind) return false;
    if (value === undefined) return true;
    return t.value === value || t.value.toUpperCase() === value.toUpperCase();
  }

  private match(kind: TokenKind, value?: string): boolean {
    if (this.check(kind, value)) { this.advance(); return true; }
    return false;
  }

  private expect(kind: TokenKind, value?: string): Token {
    const t = this.peek();
    if (!this.check(kind, value)) {
      const expected = value ? `${kind} '${value}'` : kind;
      throw new LambdaQLCompileError(
        `Expected ${expected} at line ${t.line}:${t.col}, got ${t.kind} '${t.value}'`,
        "PARSER",
        t.pos
      );
    }
    return this.advance();
  }

  private isKeyword(...values: string[]): boolean {
    const t = this.peek();
    if (t.kind !== "KEYWORD") return false;
    const up = t.value.toUpperCase();
    return values.some(v => v.toUpperCase() === up);
  }

  private expectKeyword(value: string): Token {
    return this.expect("KEYWORD", value);
  }

  // ── Top-level parse ──────────────────────────────────────────────────────────

  parse(): LambdaQLStatement {
    if (this.isKeyword("EXPLAIN")) {
      this.advance();
      return { kind: "EXPLAIN", inner: this.parseSelect() } satisfies ExplainStatement;
    }
    if (this.isKeyword("VERIFY")) {
      return this.parseVerify();
    }
    const stmt = this.parseSelect();
    if (!this.check("EOF")) {
      const t = this.peek();
      throw new LambdaQLCompileError(
        `Unexpected token after statement end: ${t.kind} '${t.value}' at line ${t.line}:${t.col}`,
        "PARSER",
        t.pos
      );
    }
    return stmt;
  }

  // ── SELECT ───────────────────────────────────────────────────────────────────

  private parseSelect(): SelectStatement {
    this.expectKeyword("SELECT");
    const projection = this.parseProjection();
    this.expectKeyword("FROM");
    const source = this.parseSource();

    let where: Predicate | undefined;
    if (this.isKeyword("WHERE")) {
      this.advance();
      where = this.parsePredicate();
    }

    let orderBy: OrderingItem[] | undefined;
    if (this.isKeyword("ORDER")) {
      this.advance();
      this.expectKeyword("BY");
      orderBy = this.parseOrderBy();
    }

    let limit: number | undefined;
    if (this.isKeyword("LIMIT")) {
      this.advance();
      const tok = this.expect("NUMBER");
      limit = parseInt(tok.value, 10);
    }

    let budget: BudgetClause | undefined;
    if (this.isKeyword("BUDGET")) {
      this.advance();
      budget = this.parseBudget();
    }

    let withOptions: WithOption[] | undefined;
    if (this.isKeyword("WITH")) {
      this.advance();
      withOptions = this.parseWithOptions();
    }

    this.expectKeyword("EMIT");
    const emit = this.parseEmit();

    let anchor: AnchorClause | undefined;
    if (this.isKeyword("ANCHORED")) {
      this.advance();
      anchor = this.parseAnchor();
    }

    this.expect("SEMI");

    return {
      kind: "SELECT",
      projection,
      source,
      where,
      orderBy,
      limit,
      budget,
      withOptions,
      emit,
      anchor,
    };
  }

  // ── VERIFY ───────────────────────────────────────────────────────────────────

  private parseVerify(): VerifyStatement {
    this.expectKeyword("VERIFY");
    this.expectKeyword("RECEIPT");
    const receiptId = this.expect("STRING").value;
    let corpusRef: string | undefined;
    if (this.isKeyword("AGAINST")) {
      this.advance();
      this.expectKeyword("CORPUS");
      corpusRef = this.parseQualifiedName();
    }
    this.expect("SEMI");
    return { kind: "VERIFY", receiptId, corpusRef };
  }

  // ── PROJECTION ───────────────────────────────────────────────────────────────

  private parseProjection(): ProjectionClause {
    if (this.check("STAR")) {
      this.advance();
      return { kind: "STAR" };
    }
    const items: ProjectionItem[] = [this.parseProjectionItem()];
    while (this.check("COMMA")) {
      this.advance();
      items.push(this.parseProjectionItem());
    }
    return { kind: "ITEMS", items };
  }

  private parseProjectionItem(): ProjectionItem {
    const path = this.parseQualifiedName();
    let alias: string | undefined;
    if (this.isKeyword("AS")) {
      this.advance();
      alias = this.expect("IDENT").value;
    }
    return { path, alias };
  }

  // ── SOURCE ───────────────────────────────────────────────────────────────────

  private parseSource(): SourceClause {
    const ref = this.parseQualifiedName();
    let alias: string | undefined;
    if (this.isKeyword("AS")) {
      this.advance();
      alias = this.expect("IDENT").value;
    }
    let join: JoinClause | undefined;
    if (this.isKeyword("JOIN")) {
      this.advance();
      const jRef = this.parseQualifiedName();
      let jAlias: string | undefined;
      if (this.isKeyword("AS")) { this.advance(); jAlias = this.expect("IDENT").value; }
      this.expectKeyword("ON");
      const on = this.parsePredicate();
      join = { ref: jRef, alias: jAlias, on };
    }
    return { ref, alias, join };
  }

  // ── QUALIFIED NAME ───────────────────────────────────────────────────────────

  /**
   * Parses qualified names like:
   *   amaru.corpus
   *   amaru.corpus@v2
   *   amaru.corpus["legal_docs"]
   *   sentra.faithfulness
   *   doctrine.grade
   *   chunks.text
   */
  private parseQualifiedName(): string {
    // Accept either IDENT or reserved KEYWORD as first segment
    const t = this.peek();
    if (t.kind !== "IDENT" && t.kind !== "KEYWORD") {
      throw new LambdaQLCompileError(
        `Expected identifier at line ${t.line}:${t.col}, got ${t.kind} '${t.value}'`,
        "PARSER",
        t.pos
      );
    }
    let name = this.advance().value;

    while (
      this.check("DOT") ||
      this.check("AT") ||
      this.check("LBRACKET")
    ) {
      if (this.check("DOT")) {
        this.advance();
        const next = this.peek();
        if (next.kind !== "IDENT" && next.kind !== "KEYWORD") {
          throw new LambdaQLCompileError(
            `Expected identifier after '.' at line ${next.line}:${next.col}`,
            "PARSER",
            next.pos
          );
        }
        name += "." + this.advance().value;
      } else if (this.check("AT")) {
        this.advance();
        const seg = this.peek();
        if (seg.kind !== "IDENT" && seg.kind !== "KEYWORD") {
          throw new LambdaQLCompileError(
            `Expected identifier after '@' at line ${seg.line}:${seg.col}`,
            "PARSER",
            seg.pos
          );
        }
        name += "@" + this.advance().value;
      } else {
        this.advance(); // [
        const str = this.expect("STRING").value;
        this.expect("RBRACKET");
        name += `["${str}"]`;
      }
    }
    return name;
  }

  // ── PREDICATE ────────────────────────────────────────────────────────────────

  private parsePredicate(): Predicate {
    return this.parseOrPredicate();
  }

  private parseOrPredicate(): Predicate {
    let left = this.parseAndPredicate();
    while (this.isKeyword("OR")) {
      this.advance();
      left = { kind: "OR", left, right: this.parseAndPredicate() };
    }
    return left;
  }

  private parseAndPredicate(): Predicate {
    let left = this.parseUnaryPredicate();
    while (this.isKeyword("AND")) {
      this.advance();
      left = { kind: "AND", left, right: this.parseUnaryPredicate() };
    }
    return left;
  }

  private parseUnaryPredicate(): Predicate {
    if (this.isKeyword("NOT")) {
      this.advance();
      return { kind: "NOT", inner: this.parseAtomPredicate() };
    }
    return this.parseAtomPredicate();
  }

  private parseAtomPredicate(): Predicate {
    // Parenthesized predicate
    if (this.check("LPAREN")) {
      this.advance();
      const p = this.parsePredicate();
      this.expect("RPAREN");
      return p;
    }

    // SIMILAR_TO(expr [, threshold])
    if (this.isKeyword("SIMILAR_TO")) {
      this.advance();
      this.expect("LPAREN");
      const expr = this.parseExpr();
      let threshold: number | undefined;
      if (this.check("COMMA")) {
        this.advance();
        threshold = parseFloat(this.expect("NUMBER").value);
      }
      this.expect("RPAREN");
      return { kind: "SIMILAR_TO", expr, threshold };
    }

    // EXISTS(subquery)
    if (this.isKeyword("EXISTS")) {
      this.advance();
      this.expect("LPAREN");
      const sub = this.parseSelect();
      this.expect("RPAREN");
      return { kind: "EXISTS", subquery: sub };
    }

    // sentra.metric op value
    if (this.isKeyword("SENTRA")) {
      this.advance();
      this.expect("DOT");
      const metricTok = this.peek();
      if (metricTok.kind !== "IDENT" && metricTok.kind !== "KEYWORD") {
        throw new LambdaQLCompileError(`Expected sentra metric name at line ${metricTok.line}:${metricTok.col}`, "PARSER", metricTok.pos);
      }
      const metric = this.advance().value;
      // Named policy: sentra.policy("name")
      if (metric.toLowerCase() === "policy" && this.check("LPAREN")) {
        this.advance();
        const policyName = this.expect("STRING").value;
        this.expect("RPAREN");
        // Represent as SENTRA with special metric name
        return { kind: "SENTRA", metric: `policy:${policyName}`, op: "=", value: 1 };
      }
      const op = this.parseCompOp();
      const value = parseFloat(this.expect("NUMBER").value);
      return { kind: "SENTRA", metric, op, value };
    }

    // doctrine.axis op value
    if (this.isKeyword("DOCTRINE")) {
      this.advance();
      this.expect("DOT");
      const axisTok = this.peek();
      if (axisTok.kind !== "IDENT" && axisTok.kind !== "KEYWORD") {
        throw new LambdaQLCompileError(`Expected doctrine axis name at line ${axisTok.line}:${axisTok.col}`, "PARSER", axisTok.pos);
      }
      const axis = this.advance().value;
      const op = this.parseCompOp();
      const value = parseFloat(this.expect("NUMBER").value);
      return { kind: "DOCTRINE", axis, op, value };
    }

    // General: expr op expr  or  expr IN (...)
    const left = this.parseExpr();
    if (this.isKeyword("IN")) {
      this.advance();
      this.expect("LPAREN");
      const values: Expr[] = [this.parseExpr()];
      while (this.check("COMMA")) { this.advance(); values.push(this.parseExpr()); }
      this.expect("RPAREN");
      return { kind: "IN", expr: left, values };
    }
    const op = this.parseCompOp();
    const right = this.parseExpr();
    return { kind: "COMPARISON", left, op, right };
  }

  private parseCompOp(): CompOp {
    const t = this.peek();
    const opMap: Partial<Record<TokenKind, CompOp>> = {
      GTE: ">=", LTE: "<=", GT: ">", LT: "<", EQ: "=", NEQ: "!=",
    };
    const op = opMap[t.kind];
    if (op === undefined) {
      // Handle <> represented as NEQ with value "<>"
      if (t.kind === "NEQ" && t.value === "<>") { this.advance(); return "<>"; }
      throw new LambdaQLCompileError(
        `Expected comparison operator at line ${t.line}:${t.col}, got ${t.kind} '${t.value}'`,
        "PARSER",
        t.pos
      );
    }
    this.advance();
    return op;
  }

  // ── EXPRESSIONS ──────────────────────────────────────────────────────────────

  private parseExpr(): Expr {
    return this.parseAddExpr();
  }

  private parseAddExpr(): Expr {
    let left = this.parseMulExpr();
    while (this.check("PLUS") || this.check("MINUS")) {
      const op = this.advance().value as "+" | "-";
      left = { kind: "BINOP", op, left, right: this.parseMulExpr() };
    }
    return left;
  }

  private parseMulExpr(): Expr {
    let left = this.parsePrimaryExpr();
    while (this.check("STAR") || this.check("SLASH")) {
      const op = this.advance().value as "*" | "/";
      left = { kind: "BINOP", op, left, right: this.parsePrimaryExpr() };
    }
    return left;
  }

  private parsePrimaryExpr(): Expr {
    const t = this.peek();

    if (t.kind === "NUMBER") {
      this.advance();
      return { kind: "LITERAL", value: parseFloat(t.value) };
    }
    if (t.kind === "STRING") {
      this.advance();
      return { kind: "LITERAL", value: t.value };
    }
    if (t.kind === "BOOLEAN") {
      this.advance();
      return { kind: "LITERAL", value: t.value.toUpperCase() === "TRUE" };
    }
    if (t.kind === "NULL") {
      this.advance();
      return { kind: "LITERAL", value: null };
    }
    if (t.kind === "LPAREN") {
      this.advance();
      const e = this.parseExpr();
      this.expect("RPAREN");
      return e;
    }
    if (t.kind === "MINUS") {
      // Unary minus
      this.advance();
      const inner = this.parsePrimaryExpr();
      return { kind: "BINOP", op: "-", left: { kind: "LITERAL", value: 0 }, right: inner };
    }
    // Qualified name or function call
    const name = this.parseQualifiedName();
    if (this.check("LPAREN")) {
      this.advance();
      const args: Expr[] = [];
      if (!this.check("RPAREN")) {
        args.push(this.parseExpr());
        while (this.check("COMMA")) { this.advance(); args.push(this.parseExpr()); }
      }
      this.expect("RPAREN");
      return { kind: "CALL", fn: name, args };
    }
    return { kind: "REF", path: name };
  }

  // ── ORDER BY ─────────────────────────────────────────────────────────────────

  private parseOrderBy(): OrderingItem[] {
    const items: OrderingItem[] = [];
    do {
      if (items.length > 0) this.advance(); // consume comma

      if (this.isKeyword("SCORE")) {
        this.advance();
        items.push({ kind: "SCORE" });
        continue;
      }
      if (this.isKeyword("DOCTRINE_GRADE")) {
        this.advance();
        items.push({ kind: "DOCTRINE_GRADE" });
        continue;
      }
      if (this.isKeyword("INGEST_TIME")) {
        this.advance();
        const dir = this.isKeyword("DESC")
          ? (this.advance(), "DESC" as const)
          : this.isKeyword("ASC")
            ? (this.advance(), "ASC" as const)
            : "ASC" as const;
        items.push({ kind: "INGEST_TIME", dir });
        continue;
      }
      const expr = this.parseExpr();
      const dir = this.isKeyword("DESC")
        ? (this.advance(), "DESC" as const)
        : this.isKeyword("ASC")
          ? (this.advance(), "ASC" as const)
          : "ASC" as const;
      items.push({ kind: "EXPR", expr, dir });
    } while (this.check("COMMA"));
    return items;
  }

  // ── BUDGET ───────────────────────────────────────────────────────────────────

  private parseBudget(): BudgetClause {
    this.expect("LPAREN");
    const b: BudgetClause = {};
    let first = true;
    while (!this.check("RPAREN") && !this.check("EOF")) {
      if (!first) this.expect("COMMA");
      first = false;
      const keyTok = this.peek();
      const key = this.advance().value.toLowerCase();
      this.expect("COLON");
      const val = parseFloat(this.expect("NUMBER").value);
      switch (key) {
        case "latency_ms":  b.latencyMs  = val; break;
        case "max_chunks":  b.maxChunks  = val; break;
        case "max_tokens":  b.maxTokens  = val; break;
        case "max_hops":    b.maxHops    = val; break;
        case "cost_cents":  b.costCents  = val; break;
        default:
          throw new LambdaQLCompileError(
            `Unknown budget key '${key}' at line ${keyTok.line}:${keyTok.col}. Valid keys: latency_ms, max_chunks, max_tokens, max_hops, cost_cents`,
            "PARSER",
            keyTok.pos
          );
      }
    }
    this.expect("RPAREN");
    return b;
  }

  // ── WITH OPTIONS ─────────────────────────────────────────────────────────────

  private static readonly SIMPLE_WITH: ReadonlySet<string> = new Set([
    "RECEIPT", "EXPLANATION", "LEAN_PROOF", "CORPUS_SNAPSHOT",
  ]);

  private parseWithOptions(): WithOption[] {
    const opts: WithOption[] = [];
    let first = true;
    while (!this.isKeyword("EMIT") && !this.check("SEMI") && !this.check("EOF")) {
      if (!first) this.expect("COMMA");
      first = false;

      const t = this.peek();
      const upper = t.value.toUpperCase();

      if (LambdaQLParser.SIMPLE_WITH.has(upper)) {
        this.advance();
        const normalized = upper.toLowerCase() as WithOption;
        opts.push(normalized);
        continue;
      }
      // key = "value"
      const key = this.advance().value;
      this.expect("EQ");
      const v = this.expect("STRING").value;
      opts.push({ key, value: v });
    }
    return opts;
  }

  // ── EMIT ─────────────────────────────────────────────────────────────────────

  private static readonly SIMPLE_EMIT_OPTS: ReadonlySet<string> = new Set([
    "INCLUDE_CHUNK_HASHES",
    "INCLUDE_RERANKER_LOGITS",
    "INCLUDE_EMBEDDING_SHA",
    "INCLUDE_CONTEXT_WINDOW_SHA",
    "INCLUDE_LEAN_OBLIGATION_SHA",
  ]);

  private parseEmit(): EmitClause {
    const t = this.peek();
    const upper = t.value.toUpperCase();
    const isNoReceipt = upper === "NO_RECEIPT";
    this.advance();
    const kind = isNoReceipt ? "no_receipt" : "lambda_receipt";

    if (kind === "lambda_receipt" && this.check("LPAREN")) {
      this.advance();
      const options: EmitOption[] = [];
      let first = true;
      while (!this.check("RPAREN") && !this.check("EOF")) {
        if (!first) this.expect("COMMA");
        first = false;

        const ot = this.peek();
        const oUp = ot.value.toUpperCase();
        if (LambdaQLParser.SIMPLE_EMIT_OPTS.has(oUp)) {
          this.advance();
          options.push(oUp.toLowerCase() as EmitOption);
        } else {
          const key = this.advance().value;
          this.expect("EQ");
          const val = this.expect("STRING").value;
          options.push({ key: key as "merkle_algorithm" | "receipt_version", value: val });
        }
      }
      this.expect("RPAREN");
      return { kind, options };
    }
    return { kind };
  }

  // ── ANCHOR ───────────────────────────────────────────────────────────────────

  private parseAnchor(): AnchorClause {
    const t = this.peek();
    const upper = t.value.toUpperCase();
    // Accept ZENODO, IPFS, or a string literal (custom endpoint URI)
    let target: string;
    if (upper === "ZENODO" || upper === "IPFS") {
      this.advance();
      target = upper.toLowerCase();
    } else if (t.kind === "STRING") {
      this.advance();
      target = t.value;
    } else {
      throw new LambdaQLCompileError(
        `Expected anchor target ('zenodo', 'ipfs', or string URI) at line ${t.line}:${t.col}`,
        "PARSER",
        t.pos
      );
    }

    if (this.check("LPAREN")) {
      this.advance();
      const options: Record<string, string | boolean> = {};
      let first = true;
      while (!this.check("RPAREN") && !this.check("EOF")) {
        if (!first) this.expect("COMMA");
        first = false;
        const k = this.advance().value;
        this.expect("EQ");
        const vt = this.peek();
        if (vt.kind === "BOOLEAN") {
          this.advance();
          options[k] = vt.value.toUpperCase() === "TRUE";
        } else {
          options[k] = this.expect("STRING").value;
        }
      }
      this.expect("RPAREN");
      return { target, options };
    }
    return { target };
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Parse a Λ-QL query string into a typed AST.
 *
 * @param query - Raw Λ-QL query text
 * @returns LambdaQLStatement (SELECT, EXPLAIN, or VERIFY)
 * @throws LambdaQLCompileError with phase "LEXER" or "PARSER"
 *
 * @example
 * const ast = parseLambdaQL(`
 *   SELECT chunks
 *   FROM amaru.corpus
 *   WHERE sentra.faithfulness >= 0.95
 *     AND doctrine.grade >= 0.9
 *   EMIT lambda_receipt
 *   ANCHORED zenodo;
 * `);
 * // ast.kind === "SELECT"
 * // (ast as SelectStatement).anchor?.target === "zenodo"
 */
export function parseLambdaQL(query: string): LambdaQLStatement {
  return new LambdaQLParser(query).parse();
}
