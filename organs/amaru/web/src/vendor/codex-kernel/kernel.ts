// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — packages/codex-kernel/src/kernel.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Codex-Kernel — `runLoop()` executor.
 *
 * Single source of truth for governed iteration:
 *  1. Pull the next StepProposal.
 *  2. Compute proposed_delta from prev_state.
 *  3. Merge → next_state, hash → next_hash.
 *  4. Run validators. Hard fail → halt.
 *  5. Resolve approval. Hard fail → halt.
 *  6. Run evidence_provenance against the receipt. Hard fail → halt.
 *  7. Append trace event + ledger entry.
 *  8. Repeat until: budgets exhausted, convergence, or hard stop.
 *
 * Behaviour with `governance_enabled = false`:
 *  - Validators are still RUN but their results are recorded as advisory only.
 *  - Receipts are still BUILT (we always know why we did something) but evidence_provenance and human_gate hard-stops are demoted to soft fails.
 *  - This is the A/B test surface: same loop, governance off vs. on.
 */

import {
  DEFAULT_DEPTH_ALLOCATOR_CONFIG,
  decideDepth,
  type AllocatorStepRecord,
  type DepthAllocatorResult,
} from './depth-allocator.js';
import { canonicalize, chainHash, hashJson } from './hash.js';
import { ProofLedger } from './ledger.js';
import { finalizeReceipt } from './receipts.js';
import {
  type ApprovalEvent,
  type ApprovalStatus,
  type DecisionReceipt,
  type Hex,
  type ISO8601,
  type Json,
  type KernelConfig,
  type KernelRunResult,
  type ProofLedgerEntry,
  type RunSummary,
  type StopReason,
  type TraceEvent,
  type ValidationContext,
  type ValidatorResult,
} from './types.js';
import { evidenceProvenance, humanGate } from './validators.js';

const ZERO_HASH: Hex = '0'.repeat(32);

function defaultNow(): ISO8601 {
  return new Date().toISOString();
}

/**
 * Lightweight deep-merge: scalar/array fields in `delta` overwrite `prev`;
 * object fields recurse. We do NOT clone arrays element-wise — replace whole.
 */
function applyDelta<S extends Json>(prev: S, delta: Json): S {
  if (
    prev === null ||
    typeof prev !== 'object' ||
    Array.isArray(prev) ||
    delta === null ||
    typeof delta !== 'object' ||
    Array.isArray(delta)
  ) {
    return delta as S;
  }
  const out: Record<string, Json> = { ...(prev as Record<string, Json>) };
  for (const k of Object.keys(delta as Record<string, Json>)) {
    const next = (delta as Record<string, Json>)[k];
    const cur = out[k];
    if (
      cur !== null &&
      typeof cur === 'object' &&
      !Array.isArray(cur) &&
      next !== null &&
      typeof next === 'object' &&
      !Array.isArray(next)
    ) {
      out[k] = applyDelta(cur, next) as Json;
    } else {
      out[k] = next;
    }
  }
  return out as S;
}

export function runLoop<S extends Json>(cfg: KernelConfig<S>): KernelRunResult<S> {
  const now = cfg.now ?? defaultNow;
  const trace: TraceEvent[] = [];
  const ledger = new ProofLedger();
  const receipts: DecisionReceipt[] = [];
  const approvals: ApprovalEvent[] = [];
  let hard_failures = 0;
  let soft_failures = 0;

  let state: S = cfg.initial_state;
  let prev_hash: Hex = hashJson(state as Json);
  // Seed prev_hash with a deterministic root so the chain has a defined head.
  const root_hash = chainHash(ZERO_HASH, null, state as Json);
  prev_hash = root_hash;

  const start_ms = Date.now();
  let stop_reason: StopReason = null;
  let step = 0;

  // v3 §3.2 — EntropyDepthAllocator state. Only consulted when
  // `loop_policy.adaptive_depth.enabled === true`. Keeping this allocated
  // unconditionally (but only *consulted* when enabled) makes the with/
  // without paths share the same control flow.
  const adaptive_enabled = cfg.loop_policy.adaptive_depth.enabled === true;
  const allocator_cfg = cfg.depth_allocator_config ?? DEFAULT_DEPTH_ALLOCATOR_CONFIG;
  const allocator_history: AllocatorStepRecord[] = [];
  let effective_step_ceiling = cfg.budgets.step_budget;
  let adaptive_extensions = 0;

  while (true) {
    if (step >= effective_step_ceiling) {
      stop_reason = 'budget_exhausted';
      break;
    }
    if (Date.now() - start_ms > cfg.budgets.time_budget_ms) {
      stop_reason = 'budget_exhausted';
      break;
    }

    const next = cfg.steps.next(state);
    if (next.done) {
      stop_reason = stop_reason ?? 'convergence';
      break;
    }
    const proposal = next.value;
    step += 1;

    const proposed_delta = proposal.proposeDelta(state);
    const next_state = applyDelta(state, proposed_delta);
    const next_hash = chainHash(prev_hash, proposed_delta, next_state as Json);
    const delta_hash = hashJson(proposed_delta);

    const ctx: ValidationContext<S> = {
      step,
      prev_state: state,
      proposed_delta,
      next_state,
      prev_hash,
      delta_hash,
      next_hash,
      policy_version: cfg.policy_version,
    };

    // Convergence check: if next_hash === prev_hash we have a no-op.
    if (canonicalize(next_state as Json) === canonicalize(state as Json)) {
      stop_reason = 'no_state_change_needed';
      // Emit a terminal trace marker (no commit).
      trace.push({
        ts: now(),
        step,
        pipeline_stage: proposal.pipeline_stage,
        state_prev_hash: prev_hash,
        observation: proposal.observation,
        proposed_delta,
        validator_results: [
          {
            name: 'convergence_detector',
            severity: 'pass',
            summary: 'no state change proposed',
          },
        ],
        decision_receipt: null,
        state_next_hash: prev_hash,
        stop_reason,
      });
      break;
    }

    // 1. Run user-supplied validators.
    const validator_results: ValidatorResult[] = [];
    for (const v of proposal.validators) {
      validator_results.push(v(ctx));
    }

    // 2. Resolve approval.
    const required: ApprovalStatus = proposal.requireApproval
      ? proposal.requireApproval(ctx)
      : 'not_required';
    let approval_status: ApprovalStatus = required;
    let approval_ref: string | null = null;
    if (required === 'pending' || required === 'approved') {
      const ev = cfg.resolveApproval ? cfg.resolveApproval(ctx) : null;
      if (ev) {
        approvals.push(ev);
        approval_ref = ev.approval_id;
        approval_status = ev.decision === 'approved' ? 'approved' : 'rejected';
      } else {
        // Step asked for approval but no event was resolved. Even if the step
        // declared 'approved', a kernel-internal "approved" with no backing
        // ApprovalEvent is a governance bypass — force it to 'pending' so the
        // human_gate validator hard-stops the loop.
        approval_status = 'pending';
      }
    } else if (required === 'rejected') {
      // 'rejected' must be backed by an ApprovalEvent too.
      const ev = cfg.resolveApproval ? cfg.resolveApproval(ctx) : null;
      if (ev) {
        approvals.push(ev);
        approval_ref = ev.approval_id;
      }
    }
    // Final invariant: any non-{not_required} status MUST be backed by an
    // ApprovalEvent. Otherwise demote to 'pending' so human_gate halts.
    if (approval_status !== 'not_required' && approval_ref === null) {
      approval_status = 'pending';
    }
    validator_results.push(humanGate(approval_status));

    // 3. Build receipt.
    const partial = proposal.buildReceipt(ctx);
    const receipt = partial
      ? finalizeReceipt(
          {
            ...partial,
            approval_status,
            approval_ref: approval_ref ?? partial.approval_ref,
          },
          { experiment_id: cfg.experiment_id, step, now: now() },
        )
      : null;

    // 4. Run evidence provenance check on the receipt itself.
    validator_results.push(evidenceProvenance(ctx, receipt));

    // 5. Apply governance policy to validator severities.
    const effective = validator_results.map((r) => effectiveSeverity(r, cfg.governance_enabled));

    // Hard stop?
    const firstHardFail = effective.find((r) => r.severity === 'hard_fail');
    soft_failures += effective.filter((r) => r.severity === 'soft_fail').length;
    if (firstHardFail) {
      hard_failures += 1;
      stop_reason =
        firstHardFail.name === 'human_gate'
          ? 'human_gate_required'
          : 'validator_hard_stop';
      trace.push({
        ts: now(),
        step,
        pipeline_stage: proposal.pipeline_stage,
        state_prev_hash: prev_hash,
        observation: proposal.observation,
        proposed_delta,
        validator_results: effective,
        decision_receipt: receipt,
        state_next_hash: prev_hash,
        stop_reason,
      });
      break;
    }

    // 6. Commit.
    if (receipt) receipts.push(receipt);
    const ledgerEntry: ProofLedgerEntry = {
      ts: now(),
      step,
      state_hash: next_hash,
      delta_hash,
      receipt_id: receipt?.receipt_id ?? `rcpt-trivial-${step}`,
      policy_version: cfg.policy_version,
      approval_ref,
    };
    ledger.append(ledgerEntry);

    // 6a. v3 EntropyDepthAllocator — pure-function controller, opt-in.
    let adaptive_verdict: DepthAllocatorResult | null = null;
    if (adaptive_enabled) {
      allocator_history.push({
        step,
        state_hash: next_hash,
        validator_severities: effective.map((r) => r.severity),
      });
      adaptive_verdict = decideDepth(
        { history: allocator_history, current_max_steps: effective_step_ceiling },
        allocator_cfg,
      );
      if (adaptive_verdict.verdict === 'extend' && adaptive_verdict.details.extended_max_steps) {
        effective_step_ceiling = adaptive_verdict.details.extended_max_steps;
        adaptive_extensions += 1;
      }
    }

    const baseEvent: TraceEvent = {
      ts: now(),
      step,
      pipeline_stage: proposal.pipeline_stage,
      state_prev_hash: prev_hash,
      observation: proposal.observation,
      proposed_delta,
      validator_results: effective,
      decision_receipt: receipt,
      state_next_hash: next_hash,
      stop_reason: null,
    };
    if (adaptive_verdict) {
      baseEvent.adaptive_depth_verdict = {
        verdict: adaptive_verdict.verdict,
        reason: adaptive_verdict.reason,
        delta_witness: adaptive_verdict.details.delta_witness,
        entropy: adaptive_verdict.details.entropy,
        soft_fail_rate: adaptive_verdict.details.soft_fail_rate,
        extended_max_steps: adaptive_verdict.details.extended_max_steps,
      };
    }

    state = next_state;
    prev_hash = next_hash;

    // 6b. Honour an early-exit verdict from the allocator. Stamp the stop
    // reason on the trace event we just pushed so the proof shape stays:
    //   "the step that triggered the stop carries the stop_reason".
    if (
      adaptive_verdict &&
      (adaptive_verdict.verdict === 'early_exit_converged' ||
        adaptive_verdict.verdict === 'early_exit_entropy')
    ) {
      stop_reason =
        adaptive_verdict.verdict === 'early_exit_converged'
          ? 'adaptive_depth_converged'
          : 'adaptive_depth_entropy_settled';
      baseEvent.stop_reason = stop_reason;
      trace.push(baseEvent);
      break;
    }
    trace.push(baseEvent);
  }

  if (!stop_reason) stop_reason = 'convergence';

  const summary: RunSummary = {
    experiment_id: cfg.experiment_id,
    status: hard_failures > 0 ? 'halted' : 'ok',
    steps_executed: step,
    hard_stop_failures: hard_failures,
    soft_failures,
    budget_used: {
      time_ms: Date.now() - start_ms,
      steps: step,
      retries: 0,
    },
    stop_reason,
    replay_status: 'not_run',
    final_state_hash: prev_hash,
    adaptive_depth_used: adaptive_enabled,
    adaptive_depth_extensions: adaptive_extensions,
    adaptive_depth_effective_max_steps: effective_step_ceiling,
  };

  return {
    summary,
    final_state: state,
    trace,
    ledger: [...ledger.toArray()],
    receipts,
    approvals,
  };
}

/**
 * When governance is disabled, hard fails on `evidence_provenance` and
 * `human_gate` are demoted to soft fails (everything else stays as-is).
 * This is the surface that makes the A/B test legible: same iteration,
 * different policy posture.
 */
function effectiveSeverity(
  r: ValidatorResult,
  governance_enabled: boolean,
): ValidatorResult {
  if (governance_enabled) return r;
  if (r.severity !== 'hard_fail') return r;
  if (r.name === 'evidence_provenance' || r.name === 'human_gate') {
    return { ...r, severity: 'soft_fail', summary: `(governance off) ${r.summary}` };
  }
  return r;
}
