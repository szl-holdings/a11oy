// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — packages/codex-kernel/src/dresden-venus.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Dresden Codex Venus emulator — the canonical reference run for the
 * Codex-Kernel.
 *
 * The pre-Columbian Maya astronomers tracked the synodic period of Venus
 * (the time between successive identical apparent positions, ~583.92
 * earth days) in the Dresden Codex with a row-by-row table. They knew the
 * idealized 584-day cycle drifted from observation, and engineered a
 * correction system: subtract days at fixed intervals to keep the table
 * aligned with the sky.
 *
 * This emulator reproduces that pattern as a deterministic governed loop:
 *  - 584-day idealized period per row
 *  - small per-step drift accumulation (configurable; default 0)
 *  - drift correction must be EXPLICITLY proposed when |drift| ≥ warning
 *  - decision receipt required for any correction (cites the codex pattern)
 *
 * It is the "hello world" of replay-grade governance.
 */

import {
  type DecisionReceipt,
  type Json,
  type StepProposal,
  type ValidationContext,
} from './types.js';
import { driftBounds, stateTransitionRule } from './validators.js';

export type VenusRow = {
  row_index: number;
  epoch_label: string;
  cycle_position: number;
  day_index: number;
  drift_days: number;
  correction_applied: number;
  notes: string;
};

export type VenusState = {
  epoch_label: string;
  day_index: number;
  cycle_position: number;
  drift_days: number;
  table_rows_emitted: number;
  row_history: VenusRow[];
};

export const DRESDEN_INITIAL_STATE: VenusState = {
  epoch_label: 'demo_epoch',
  day_index: 0,
  cycle_position: 0,
  drift_days: 0,
  table_rows_emitted: 0,
  row_history: [],
};

/**
 * Drift can either accumulate continuously (`drift_per_cycle` added every
 * advance) or be applied in discrete bumps on a schedule (e.g. "+1 day every
 * 5 rows"). The payload-driven runner uses the discrete form so we don't
 * lossily collapse `every_n_rows` into a fractional rate.
 */
export type DresdenDriftSchedule =
  | { type: 'every_n_rows'; n: number; increment: number };

export interface DresdenSimConfig {
  /** Days per synodic cycle (Maya idealized to 584; reality is ~583.92). */
  cycle_days: number;
  /** Days of drift accumulated per cycle. Set to 0 for trivial demo. */
  drift_per_cycle: number;
  /**
   * Optional discrete drift schedule. When set, drift on each advance is:
   *   schedule.increment when (emitted_attempts % schedule.n === 0), else 0.
   * Applied IN ADDITION to drift_per_cycle (so the two are composable).
   */
  drift_schedule?: DresdenDriftSchedule;
  /** Threshold at which a correction MUST be proposed (warning). */
  warning_threshold: number;
  /** Threshold above which the loop hard-stops (e.g. operator inattention). */
  hard_threshold: number;
  /** Total rows to attempt to emit. */
  rows_to_emit: number;
  /** When |drift| >= this, the next step is a CORRECTION instead of advance. */
  correct_when_drift_ge: number;
}

export const DRESDEN_DEFAULT_CONFIG: DresdenSimConfig = {
  cycle_days: 584,
  drift_per_cycle: 0,
  warning_threshold: 2,
  hard_threshold: 5,
  rows_to_emit: 10,
  correct_when_drift_ge: 2,
};

/** Marker key on a delta indicating the step was a correction. */
const CORRECTION_KEY = '__correction_days';

function isCorrection(delta: Json): boolean {
  return (
    delta !== null &&
    typeof delta === 'object' &&
    !Array.isArray(delta) &&
    CORRECTION_KEY in delta
  );
}

/** Advance one Venus row OR apply a drift correction, whichever the rule says. */
export function* dresdenSteps(
  cfg: DresdenSimConfig = DRESDEN_DEFAULT_CONFIG,
): Generator<StepProposal<VenusState>, void, VenusState> {
  let emitted_attempts = 0;
  while (emitted_attempts < cfg.rows_to_emit) {
    emitted_attempts += 1;
    const proposal: StepProposal<VenusState> = {
      pipeline_stage: 'Execution',
      observation: {
        cycle_index: emitted_attempts,
        rule: 'advance OR correct based on drift',
      },
      proposeDelta: (prev: VenusState): Json => {
        const need_correction = Math.abs(prev.drift_days) >= cfg.correct_when_drift_ge;
        if (need_correction) {
          // Subtract drift to bring it back to zero.
          const correction = -prev.drift_days;
          const new_drift = 0;
          const new_row: VenusRow = {
            row_index: prev.table_rows_emitted + 1,
            epoch_label: prev.epoch_label,
            cycle_position: prev.cycle_position,
            day_index: prev.day_index + correction,
            drift_days: new_drift,
            correction_applied: correction,
            notes: `correction: ${correction > 0 ? '+' : ''}${correction}d`,
          };
          return {
            day_index: prev.day_index + correction,
            drift_days: new_drift,
            table_rows_emitted: prev.table_rows_emitted + 1,
            row_history: [...prev.row_history, new_row],
            [CORRECTION_KEY]: correction,
          } as unknown as Json;
        }
        // Standard advance.
        const new_cycle = prev.cycle_position + 1;
        const new_day = prev.day_index + cfg.cycle_days;
        const continuous_drift = cfg.drift_per_cycle;
        // Discrete schedule: e.g. "+increment days every n rows".
        // emitted_attempts is 1-indexed within this generator and tracks the
        // advance attempt count, so `% n === 0` triggers on the n-th, 2n-th, ...
        let scheduled_drift = 0;
        if (cfg.drift_schedule && cfg.drift_schedule.type === 'every_n_rows') {
          const { n, increment } = cfg.drift_schedule;
          if (n > 0 && emitted_attempts % n === 0) scheduled_drift = increment;
        }
        const new_drift = prev.drift_days + continuous_drift + scheduled_drift;
        const new_row: VenusRow = {
          row_index: prev.table_rows_emitted + 1,
          epoch_label: prev.epoch_label,
          cycle_position: new_cycle,
          day_index: new_day,
          drift_days: new_drift,
          correction_applied: 0,
          notes: 'advance',
        };
        return {
          cycle_position: new_cycle,
          day_index: new_day,
          drift_days: new_drift,
          table_rows_emitted: prev.table_rows_emitted + 1,
          row_history: [...prev.row_history, new_row],
        } as unknown as Json;
      },
      validators: [
        stateTransitionRule,
        driftBounds<VenusState>({
          read: (s) => s.drift_days,
          warning_threshold: cfg.warning_threshold,
          hard_threshold: cfg.hard_threshold,
          correction_applied: isCorrection,
        }),
      ],
      buildReceipt: (
        ctx: ValidationContext<VenusState>,
      ): Omit<DecisionReceipt, 'receipt_id' | 'step' | 'timestamp'> | null => {
        const corrected = isCorrection(ctx.proposed_delta);
        const decision_type = corrected ? 'drift_correction' : 'cycle_advance';
        const summary = corrected
          ? `Applied drift correction of ${
              (ctx.proposed_delta as Record<string, number>)[CORRECTION_KEY]
            }d to restore alignment.`
          : `Advanced one synodic cycle (+${cfg.cycle_days}d).`;
        return {
          decision_type,
          summary,
          assumptions: corrected
            ? [
                'Drift exceeded warning threshold and required correction per Dresden table convention.',
                `cycle_days = ${cfg.cycle_days} (Maya idealized; observed ~583.92d).`,
              ]
            : [
                `cycle_days = ${cfg.cycle_days} (Maya idealized).`,
                `drift_per_cycle = ${cfg.drift_per_cycle} (configured).`,
              ],
          evidence: [
            {
              kind: 'archaeological_reference',
              ref: 'Dresden Codex pp. 24, 46–50 (Venus tables)',
              mocked: false,
            },
            {
              kind: 'astronomical_constant',
              ref: 'IAU synodic period of Venus = 583.92d',
              mocked: false,
            },
          ],
          policy_version: 'covenant-v1',
          approval_status: 'not_required',
          mocked: false,
        };
      },
    };
    yield proposal;
  }
}
