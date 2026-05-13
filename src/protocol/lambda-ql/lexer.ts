/**
 * Λ-QL Lexer — Token stream from Λ-QL source
 * File: a11oy/src/protocol/lambda-ql/lexer.ts
 *
 * Doctrine v2 binding. Zero dependencies. Runs in Node.js, Deno, and browser.
 * Produces Token[] consumed by parser.ts.
 *
 * Source: phd5_protocol.md §5.1 EBNF grammar + §5.7 reference stubs
 */

import type { Token, TokenKind } from "./types.js";

// ─── Keyword registry ─────────────────────────────────────────────────────────

/**
 * All Λ-QL keywords. Case-insensitive match at lex time; stored as UPPERCASE.
 * Some identifiers that are also reserved context keywords (e.g. "sentra",
 * "doctrine", "amaru", "chunks") are included so the parser can distinguish
 * them; they are emitted as KEYWORD tokens.
 */
const KEYWORDS: ReadonlySet<string> = new Set([
  // DML
  "SELECT", "FROM", "WHERE", "ORDER", "BY", "LIMIT", "BUDGET", "WITH",
  "EMIT", "ANCHORED",
  // Statement kinds
  "EXPLAIN", "VERIFY", "RECEIPT", "AGAINST", "CORPUS",
  // Predicates / logic
  "AND", "OR", "NOT", "IN", "EXISTS", "AS", "JOIN", "ON",
  // Ordering
  "ASC", "DESC", "SCORE", "DOCTRINE_GRADE", "INGEST_TIME",
  // Similarity
  "SIMILAR_TO",
  // Emit/anchor values — treated as keywords for unambiguous parsing
  "LAMBDA_RECEIPT", "NO_RECEIPT", "ZENODO", "IPFS",
  // WITH option tokens
  "RECEIPT_OPT",  // internal placeholder — not user-facing
  "EXPLANATION", "LEAN_PROOF", "CORPUS_SNAPSHOT",
  "INCLUDE_CHUNK_HASHES", "INCLUDE_RERANKER_LOGITS",
  "INCLUDE_EMBEDDING_SHA", "INCLUDE_CONTEXT_WINDOW_SHA", "INCLUDE_LEAN_OBLIGATION_SHA",
  "MERKLE_ALGORITHM", "RECEIPT_VERSION",
  // Namespace identifiers (reserved for compile-time resolution)
  "SENTRA", "DOCTRINE", "AMARU", "CHUNKS",
  // Budget keys
  "LATENCY_MS", "MAX_CHUNKS", "MAX_TOKENS", "MAX_HOPS", "COST_CENTS",
]);

/**
 * Mixed-case keywords that must be preserved exactly as written.
 * Lower-case forms map to these values after normalization.
 */
const LOWERCASE_KW_MAP: Readonly<Record<string, string>> = {
  "lambda_receipt": "LAMBDA_RECEIPT",
  "no_receipt": "NO_RECEIPT",
  "zenodo": "ZENODO",
  "ipfs": "IPFS",
  "explanation": "EXPLANATION",
  "lean_proof": "LEAN_PROOF",
  "corpus_snapshot": "CORPUS_SNAPSHOT",
  "include_chunk_hashes": "INCLUDE_CHUNK_HASHES",
  "include_reranker_logits": "INCLUDE_RERANKER_LOGITS",
  "include_embedding_sha": "INCLUDE_EMBEDDING_SHA",
  "include_context_window_sha": "INCLUDE_CONTEXT_WINDOW_SHA",
  "include_lean_obligation_sha": "INCLUDE_LEAN_OBLIGATION_SHA",
  "merkle_algorithm": "MERKLE_ALGORITHM",
  "receipt_version": "RECEIPT_VERSION",
  "sentra": "SENTRA",
  "doctrine": "DOCTRINE",
  "amaru": "AMARU",
  "chunks": "CHUNKS",
  "latency_ms": "LATENCY_MS",
  "max_chunks": "MAX_CHUNKS",
  "max_tokens": "MAX_TOKENS",
  "max_hops": "MAX_HOPS",
  "cost_cents": "COST_CENTS",
  "doctrine_grade": "DOCTRINE_GRADE",
  "ingest_time": "INGEST_TIME",
  "similar_to": "SIMILAR_TO",
};

// ─── Lexer class ──────────────────────────────────────────────────────────────

export class Lexer {
  private pos: number = 0;
  private line: number = 1;
  private col: number = 1;

  constructor(private readonly input: string) {}

  /** Tokenize the entire input. The last token is always EOF. */
  tokenize(): Token[] {
    const tokens: Token[] = [];

    while (this.pos < this.input.length) {
      this.skipWhitespaceAndComments();
      if (this.pos >= this.input.length) break;

      const tok = this.nextToken();
      if (tok !== null) tokens.push(tok);
    }

    tokens.push({
      kind: "EOF",
      value: "",
      pos: this.pos,
      line: this.line,
      col: this.col,
    });
    return tokens;
  }

  // ── Private helpers ──────────────────────────────────────────────────────────

  private ch(offset = 0): string {
    return this.input[this.pos + offset] ?? "";
  }

  private advance(count = 1): string {
    let result = "";
    for (let i = 0; i < count; i++) {
      if (this.pos < this.input.length) {
        if (this.input[this.pos] === "\n") {
          this.line++;
          this.col = 1;
        } else {
          this.col++;
        }
        result += this.input[this.pos++];
      }
    }
    return result;
  }

  private skipWhitespaceAndComments(): void {
    while (this.pos < this.input.length) {
      const c = this.ch();
      // Whitespace
      if (c === " " || c === "\t" || c === "\r" || c === "\n") {
        this.advance();
        continue;
      }
      // Single-line comment: -- to end of line
      if (c === "-" && this.ch(1) === "-") {
        while (this.pos < this.input.length && this.ch() !== "\n") {
          this.advance();
        }
        continue;
      }
      // Block comment: /* ... */
      if (c === "/" && this.ch(1) === "*") {
        this.advance(2);
        while (this.pos < this.input.length) {
          if (this.ch() === "*" && this.ch(1) === "/") {
            this.advance(2);
            break;
          }
          this.advance();
        }
        continue;
      }
      break;
    }
  }

  private makeToken(kind: TokenKind, value: string, startPos: number, startLine: number, startCol: number): Token {
    return { kind, value, pos: startPos, line: startLine, col: startCol };
  }

  private nextToken(): Token | null {
    const startPos = this.pos;
    const startLine = this.line;
    const startCol = this.col;
    const c = this.ch();

    // ── String literals ──────────────────────────────────────────────────────
    if (c === '"' || c === "'") {
      const quote = c;
      this.advance(); // consume opening quote
      let s = "";
      while (this.pos < this.input.length && this.ch() !== quote) {
        if (this.ch() === "\\") {
          this.advance(); // skip backslash
          const escaped = this.advance();
          switch (escaped) {
            case "n": s += "\n"; break;
            case "t": s += "\t"; break;
            case "r": s += "\r"; break;
            case "\\": s += "\\"; break;
            case "'": s += "'"; break;
            case '"': s += '"'; break;
            default: s += "\\" + escaped;
          }
        } else {
          s += this.advance();
        }
      }
      if (this.pos >= this.input.length) {
        throw new LexerError(`Unterminated string literal starting at line ${startLine}:${startCol}`);
      }
      this.advance(); // consume closing quote
      return this.makeToken("STRING", s, startPos, startLine, startCol);
    }

    // ── Numeric literals ─────────────────────────────────────────────────────
    if (isDigit(c) || (c === "." && isDigit(this.ch(1)))) {
      let s = "";
      while (this.pos < this.input.length && (isDigit(this.ch()) || this.ch() === ".")) {
        s += this.advance();
      }
      // Optional exponent
      if (this.ch() === "e" || this.ch() === "E") {
        s += this.advance();
        if (this.ch() === "+" || this.ch() === "-") s += this.advance();
        while (this.pos < this.input.length && isDigit(this.ch())) s += this.advance();
      }
      return this.makeToken("NUMBER", s, startPos, startLine, startCol);
    }

    // ── Identifiers, keywords, booleans, null ────────────────────────────────
    if (isLetter(c)) {
      let s = "";
      while (this.pos < this.input.length && isIdentChar(this.ch())) {
        s += this.advance();
      }
      const upper = s.toUpperCase();
      const lowerMapped = LOWERCASE_KW_MAP[s.toLowerCase()];

      if (upper === "TRUE" || upper === "FALSE") {
        return this.makeToken("BOOLEAN", s, startPos, startLine, startCol);
      }
      if (upper === "NULL") {
        return this.makeToken("NULL", s, startPos, startLine, startCol);
      }
      // Keyword: exact match (upper) or lower-case mapped
      if (KEYWORDS.has(upper) || lowerMapped) {
        const kwValue = lowerMapped ?? upper;
        return this.makeToken("KEYWORD", kwValue, startPos, startLine, startCol);
      }
      return this.makeToken("IDENT", s, startPos, startLine, startCol);
    }

    // ── Multi-char operators ──────────────────────────────────────────────────
    if (c === "<" && this.ch(1) === "=") { this.advance(2); return this.makeToken("LTE", "<=", startPos, startLine, startCol); }
    if (c === ">" && this.ch(1) === "=") { this.advance(2); return this.makeToken("GTE", ">=", startPos, startLine, startCol); }
    if (c === "!" && this.ch(1) === "=") { this.advance(2); return this.makeToken("NEQ", "!=", startPos, startLine, startCol); }
    if (c === "<" && this.ch(1) === ">") { this.advance(2); return this.makeToken("NEQ", "<>", startPos, startLine, startCol); }

    // ── Single-char tokens ────────────────────────────────────────────────────
    const singleMap: Partial<Record<string, TokenKind>> = {
      ".": "DOT", ",": "COMMA", ";": "SEMI",
      "(": "LPAREN", ")": "RPAREN",
      "*": "STAR",
      "=": "EQ", "<": "LT", ">": "GT",
      ":": "COLON", "@": "AT",
      "[": "LBRACKET", "]": "RBRACKET",
      "+": "PLUS", "-": "MINUS", "/": "SLASH",
    };
    const kind = singleMap[c];
    if (kind !== undefined) {
      this.advance();
      return this.makeToken(kind, c, startPos, startLine, startCol);
    }

    throw new LexerError(
      `Unexpected character '${c}' (U+${c.charCodeAt(0).toString(16).padStart(4, "0")}) at line ${this.line}:${this.col}`
    );
  }
}

// ─── Character predicates ─────────────────────────────────────────────────────

function isDigit(c: string): boolean {
  return c >= "0" && c <= "9";
}

function isLetter(c: string): boolean {
  return (c >= "a" && c <= "z") || (c >= "A" && c <= "Z") || c === "_";
}

function isIdentChar(c: string): boolean {
  return isLetter(c) || isDigit(c);
}

// ─── Error ────────────────────────────────────────────────────────────────────

export class LexerError extends Error {
  constructor(message: string) {
    super(`[Λ-QL LEXER] ${message}`);
    this.name = "LexerError";
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Tokenize a Λ-QL source string into a token stream.
 *
 * @param input - Raw Λ-QL query text
 * @returns Array of tokens, terminated by EOF token
 * @throws LexerError on illegal characters
 *
 * @example
 * const tokens = tokenize(
 *   "SELECT chunks FROM amaru.corpus WHERE sentra.faithfulness >= 0.95 EMIT lambda_receipt ANCHORED zenodo;"
 * );
 */
export function tokenize(input: string): Token[] {
  return new Lexer(input).tokenize();
}
