/**
 * @file runtime/src/rae1/schema.ts
 * @description RAE-1 v1.0 — Receipt-Attested Evaluation Protocol
 *
 * DSSE envelope schema and RAE-1 payload types.
 *
 * Lean ref:  SZL.AGI.PACBayes.capability_improvement_rate_bound
 * Lean file: Lutar/PACBayes/CapabilityImprovementRate.lean
 * Lean commit: c4d1379568... (pinned at proof time)
 * Lean repo:   szl-holdings/lutar-lean
 * Lean build:  sorry_disclosed (2 named sorries: AsymptoticTightness, KLMonotonicity)
 *
 * Protocol spec: RAE_1_PROTOCOL.md §2
 * Schema version: rae1.0
 *
 * Doctrine v6 — no fake lake-green, no new axioms.
 * Signed-off-by: SZL Engineering <eng@szl-holdings.com>
 */

// ─── Constants ───────────────────────────────────────────────────────────────

/** Current RAE-1 protocol schema version. Bump minor for backward-compatible extensions. */
export const RAE1_SCHEMA_VERSION = "rae1.0" as const;

/** MIME type for the DSSE payload. MUST match exactly across all implementations. */
export const RAE1_PAYLOAD_TYPE = "application/vnd.szl.rae1+json" as const;

/** Minimum number of judges required for a RAE-1-compliant ensemble (§3.1). */
export const RAE1_MIN_JUDGES = 3 as const;

/** Lean theorem name referenced in all receipts. Verified at commit c4d1379568. */
export const LEAN_THEOREM_NAME = "SZL.AGI.PACBayes.capability_improvement_rate_bound" as const;

/** Lean file path within szl-holdings/lutar-lean. */
export const LEAN_THEOREM_FILE = "Lutar/PACBayes/CapabilityImprovementRate.lean" as const;

/** Genesis sentinel for the first receipt in any chain. */
export const CHAIN_GENESIS = "GENESIS" as const;

// ─── Judge Types ──────────────────────────────────────────────────────────────

/** System prompt variant that defines a judge's evaluation bias. */
export type JudgePromptVariant = "rigorous" | "creative" | "verification";

/** Verdict options for a single judge or the ensemble. */
export type Verdict = "SOLVED" | "UNCLEAR" | "WRONG";

/**
 * Single judge evaluation record.
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 *
 * Per RAE-1 §3.1: judges MUST run in parallel (non-collusion property).
 */
export interface RAE1JudgeRecord {
  /** Unique identifier for this judge invocation, e.g. "judge-0-rigorous". */
  judge_id: string;

  /** Model name with version, e.g. "claude-3-5-sonnet-20241022". */
  model_name: string;

  /**
   * System prompt variant used. Determines evaluation bias:
   * - rigorous: conservative, strict correctness, prefer UNCLEAR over WRONG
   * - creative: liberal, accepts non-standard approaches
   * - verification: answer-extraction + arithmetic check
   */
  system_prompt_variant: JudgePromptVariant;

  /** This judge's verdict on the problem. */
  verdict: Verdict;

  /** Calibrated confidence in [0.0, 1.0]. */
  confidence_01: number;

  /** Wall-clock latency for this judge call in milliseconds. */
  latency_ms: number;

  /** Token usage breakdown for this call. */
  token_usage: {
    input: number;
    output: number;
    total: number;
  };
}

// ─── RAE-1 Payload ───────────────────────────────────────────────────────────

/**
 * Inner JSON payload, base64url-encoded inside the DSSE envelope.
 *
 * This is the attestation record for a single benchmark problem evaluation.
 * Every field is required unless marked optional; validators MUST reject
 * receipts with missing required fields (see validate.ts).
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 *
 * Schema: RAE_1_PROTOCOL.md §2.2
 */
export interface RAE1Payload {
  // ── Schema identification ─────────────────────────────────────────────────

  /** Protocol version. MUST equal "rae1.0". */
  schema_version: typeof RAE1_SCHEMA_VERSION;

  // ── Run-level metadata ───────────────────────────────────────────────────

  /** UUIDv4 — unique per evaluation run (all receipts in a run share this). */
  run_id: string;

  /** ISO 8601 UTC timestamp of this evaluation run, e.g. "2026-05-27T18:34:00Z". */
  run_timestamp: string;

  /** Benchmark name, e.g. "bench-2024". */
  benchmark_name: string;

  /** Benchmark year as a number, e.g. 2024. */
  benchmark_year: number;

  /** Evaluation harness semver, e.g. "v2.0.0". */
  harness_version: string;

  /** Git SHA of the harness code at run time (allows deterministic replay). */
  harness_commit_sha: string;

  // ── Problem-level fields ─────────────────────────────────────────────────

  /** Problem identifier, e.g. "bench-2024-A1". */
  problem_id: string;

  /**
   * SHA-256 hex digest of the UTF-8 problem text.
   * Allows auditors to verify the exact problem version evaluated.
   */
  problem_sha256: string;

  /** Domain classifier output, e.g. "combinatorics". */
  domain: string;

  // ── Judge ensemble ───────────────────────────────────────────────────────

  /**
   * Judge records — MUST have length >= RAE1_MIN_JUDGES (3).
   * Judges MUST run in parallel to ensure non-collusion (§3.3).
   */
  judges: RAE1JudgeRecord[];

  // ── Ensemble decision ────────────────────────────────────────────────────

  /** Majority-vote verdict. Ties → "UNCLEAR". */
  ensemble_verdict: Verdict;

  /** Count of judges that voted SOLVED. */
  votes_solved: number;

  /** Count of judges that voted UNCLEAR. */
  votes_unclear: number;

  /** Count of judges that voted WRONG. */
  votes_wrong: number;

  // ── Score contribution ───────────────────────────────────────────────────

  /** True iff ensemble_verdict === "SOLVED". Contributes 1 to n_solved. */
  is_solved: boolean;

  // ── Receipt chain linkage ────────────────────────────────────────────────

  /**
   * SHA-256 hex digest of the previous receipt's raw JSON line (compact),
   * or "GENESIS" for the first receipt in a run.
   *
   * Chain integrity: hash(R_i) = SHA-256(JSON.stringify(envelope_i))
   *                  R_{i+1}.payload.prev_hash = hex(hash(R_i))
   * See RAE_1_PROTOCOL.md §4.1
   */
  prev_hash: string;

  /** 0-based position of this receipt in the chain. MUST equal line index. */
  receipt_index: number;

  // ── Lean theorem reference ───────────────────────────────────────────────

  /**
   * Name of the Lean theorem bounding what this score means.
   *
   * MUST be "SZL.AGI.PACBayes.capability_improvement_rate_bound"
   * for RAE-1 v1.0 compliant receipts.
   *
   * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
   *           commit: c4d1379568
   */
  lean_theorem_name: string;

  /** Path to the theorem file within lean_repo, e.g. "Lutar/PACBayes/CapabilityImprovementRate.lean". */
  lean_theorem_file: string;

  /** Git SHA of szl-holdings/lutar-lean at the time this receipt was created. */
  lean_commit_sha: string;

  /** GitHub slug of the Lean repository, e.g. "szl-holdings/lutar-lean". */
  lean_repo: string;

  /**
   * Build status of the Lean file at lean_commit_sha.
   *
   * Doctrine v6: "sorry_undisclosed" is FORBIDDEN and will cause validation failure.
   *
   * - "green": all proofs complete, 0 sorries
   * - "sorry_disclosed": sorries present but named and documented with discharge routes
   * - "sorry_undisclosed": FORBIDDEN by Doctrine v6
   * - "failed": build did not exit 0
   */
  lean_build_status: "green" | "sorry_disclosed" | "sorry_undisclosed" | "failed";

  /**
   * Number of sorry occurrences in the Lean file.
   * MUST be 0 if lean_build_status === "green".
   * MUST match the actual grep count of sorry in the file.
   */
  lean_sorry_count: number;

  // ── Staged advisory flag ─────────────────────────────────────────────────

  /**
   * True if this claim is pre-production and should be treated with caution.
   * MUST be true when MOCK_JUDGES=1 or no real API keys are present.
   */
  staged_advisory: boolean;

  /** Explanation of why staged_advisory is true, if applicable. */
  staged_notes?: string;
}

// ─── DSSE Envelope ───────────────────────────────────────────────────────────

/**
 * DSSE (Dead Simple Signing Envelope) outer wrapper.
 *
 * Per the DSSE spec (github.com/secure-systems-lab/dsse) and RAE-1 §2.1.
 *
 * PAE (Pre-Authentication Encoding):
 *   PAE(type, payload) = LE64(2) || LE64(len(type)) || type
 *                      || LE64(len(payload)) || payload
 *
 * The sig field is base64url(HMAC-SHA-256(key, PAE(payloadType, payload))).
 *
 * Lean ref: SZL.AGI.PACBayes.capability_improvement_rate_bound
 *           file: Lutar/PACBayes/CapabilityImprovementRate.lean
 *           commit: c4d1379568
 */
export interface DSSEEnvelope {
  /** MUST equal RAE1_PAYLOAD_TYPE = "application/vnd.szl.rae1+json". */
  payloadType: typeof RAE1_PAYLOAD_TYPE;

  /** Base64url-encoded JSON of RAE1Payload. */
  payload: string;

  /**
   * Array of signatures. Each entry has:
   * - keyid: HMAC key ID in format "hmac-sha256:<sha256-of-key-material>"
   * - sig:   base64url(HMAC-SHA-256(key, PAE(payloadType, payload)))
   */
  signatures: Array<{
    keyid: string;
    sig: string;
  }>;
}

// ─── Chain Summary ────────────────────────────────────────────────────────────

/**
 * Published after every complete benchmark run.
 * Committed to runtime/bench-2025/latest.json and tagged with Zenodo DOI.
 *
 * See RAE_1_PROTOCOL.md §4.3
 */
export interface ChainSummary {
  run_id: string;
  run_timestamp: string;
  benchmark_name: string;
  n_problems: number;
  n_solved: number;
  score_01: number;
  chain_root: string;
  chain_head: string;
  receipts_jsonl_sha256: string;
  lean_repo: string;
  lean_commit_sha: string;
  lean_theorem: string;
  lean_build_status: RAE1Payload["lean_build_status"];
  lean_sorry_count: number;
  staged_advisory: boolean;
  zenodo_doi?: string;
}
