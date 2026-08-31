/**
 * Output paths — implementation of the v4 missing piece
 * `output_paths` from `docs/research/ouroboros-runtime-contract.v4.json`.
 *
 * The runtime emits trace, receipt, proof-ledger, and final-state
 * artifacts to deterministic file paths so replay tooling, golden-run
 * regression, and the distillation pipeline can find them without
 * configuration. These are constants — runners must not redirect or
 * rename, or replay-verifier breaks.
 */

export const OUTPUT_PATHS = Object.freeze({
  traceJsonl: 'output/trace.jsonl',
  decisionReceipt: 'output/decision_receipt.json',
  proofLedgerJsonl: 'output/proof_ledger.jsonl',
  finalStateJson: 'output/final_state.json',
  runSummaryJson: 'output/run_summary.json',
  goldenRunReportJson: 'output/golden_run_report.json',
  sentraRiskSummaryJson: 'output/sentra_risk_summary.json',
  amaruConsistencyReportJson: 'output/amaru_consistency_report.json',
} as const);

export type OutputPathKey = keyof typeof OUTPUT_PATHS;

/**
 * Resolve an output-path key to its canonical relative path. Throws if
 * the key is unknown so misconfigured runners fail loudly instead of
 * writing artifacts where replay tooling cannot find them.
 */
export function resolveOutputPath(key: OutputPathKey): string {
  const path = OUTPUT_PATHS[key];
  if (!path) {
    throw new Error(`Unknown output path key: ${String(key)}`);
  }
  return path;
}
