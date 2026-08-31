/**
 * Almanac cycle advancer — implementation of the missing piece
 * `almanac_cycle_advancer` from `docs/research/ouroboros-runtime-contract.v2.json`.
 *
 * The almanac sits ABOVE the loop kernel and provides bounded periodic
 * coordination, mirroring the codex-inspired multi-cycle structure of the
 * Madrid Almanac, Paris long cycle, and Grolier schedule layers. The role
 * of these layers is **comparative structural inspiration only** — they are
 * not literal execution truth (per the codex_corpus_governance section of
 * the contract).
 *
 * Each cycle advances by a fixed `stepInterval` of loop steps. When a cycle
 * advances, a `CycleEvent` is emitted; consumers can subscribe (long-horizon
 * reassessment, schedule reconciliation, periodic review).
 */

export type CycleId =
  | 'madrid_almanac_cycle'
  | 'paris_long_cycle'
  | 'grolier_schedule_cycle'
  // v3 addition (review_cycle, step_interval=2) per ouroboros-runtime-contract.v3.json
  | 'review_cycle'
  // v4 rename of paris_long_cycle per ouroboros-runtime-contract.v4.json (interval 3 unchanged)
  | 'paris_cadence_cycle';

export interface CycleConfig {
  readonly cycleId: CycleId;
  readonly purpose: string;
  readonly stepInterval: number;
}

export const DEFAULT_CYCLES: readonly CycleConfig[] = Object.freeze([
  Object.freeze({
    cycleId: 'madrid_almanac_cycle',
    purpose: 'short_horizon_review_and_task_rotation',
    stepInterval: 1,
  }) as CycleConfig,
  Object.freeze({
    cycleId: 'paris_long_cycle',
    purpose: 'long_horizon_cadence_and_periodic_reassessment',
    stepInterval: 3,
  }) as CycleConfig,
  Object.freeze({
    cycleId: 'grolier_schedule_cycle',
    purpose: 'predetermined_schedule_constraints',
    stepInterval: 2,
  }) as CycleConfig,
]);

/**
 * v3 cycles — adds `review_cycle` (interval 2) for system-health review and
 * receipt checkpointing per ouroboros-runtime-contract.v3.json. Pass
 * V3_CYCLES into `advanceAlmanac`/`rebuildAlmanac` to enable.
 */
export const V3_CYCLES: readonly CycleConfig[] = Object.freeze([
  ...DEFAULT_CYCLES,
  Object.freeze({
    cycleId: 'review_cycle',
    purpose: 'system_health_review_and_receipt_checkpointing',
    stepInterval: 2,
  }) as CycleConfig,
]);

/**
 * v4 cycles — replaces `paris_long_cycle` with the v4-canonical
 * `paris_cadence_cycle` (interval 3, unchanged behavior). v3 → v4
 * normalization is available through `CYCLE_ID_V4_ALIASES` so consumers
 * holding either label still resolve to a known cycle.
 */
export const V4_CYCLES: readonly CycleConfig[] = Object.freeze([
  Object.freeze({
    cycleId: 'madrid_almanac_cycle',
    purpose: 'short_horizon_review_and_task_rotation',
    stepInterval: 1,
  }) as CycleConfig,
  Object.freeze({
    cycleId: 'paris_cadence_cycle',
    purpose: 'long_horizon_reassessment_and_review_cadence',
    stepInterval: 3,
  }) as CycleConfig,
  Object.freeze({
    cycleId: 'grolier_schedule_cycle',
    purpose: 'predetermined_schedule_constraints_for_bounded_execution',
    stepInterval: 2,
  }) as CycleConfig,
  Object.freeze({
    cycleId: 'review_cycle',
    purpose: 'system_health_and_receipt_checkpointing',
    stepInterval: 2,
  }) as CycleConfig,
]);

/**
 * Bidirectional v4 alias map: receipt-normalization tools translate
 * between the v3 (`paris_long_cycle`) and v4 (`paris_cadence_cycle`)
 * names. Every key is a known cycle id; every value is the v4-canonical
 * cycle id used in `V4_CYCLES`.
 */
export const CYCLE_ID_V4_ALIASES: Readonly<Record<string, CycleId>> = Object.freeze({
  paris_cadence_cycle: 'paris_cadence_cycle',
  paris_long_cycle: 'paris_cadence_cycle',
  madrid_almanac_cycle: 'madrid_almanac_cycle',
  grolier_schedule_cycle: 'grolier_schedule_cycle',
  review_cycle: 'review_cycle',
});

export type AlmanacState = Readonly<Record<CycleId, number>>;

export const INITIAL_ALMANAC_STATE: AlmanacState = Object.freeze({
  madrid_almanac_cycle: 0,
  paris_long_cycle: 0,
  paris_cadence_cycle: 0,
  grolier_schedule_cycle: 0,
  review_cycle: 0,
});

export interface CycleEvent {
  cycleId: CycleId;
  cyclePosition: number;
  loopStep: number;
  purpose: string;
}

export interface AlmanacAdvanceResult {
  state: AlmanacState;
  events: CycleEvent[];
}

/**
 * Advance the almanac by one loop step. Returns the next state and the list
 * of cycles that ticked at this step. Pure function: deterministic in
 * `(state, loopStep, cycles)` so the advancer is fully replayable.
 *
 * Cycle position is incremented when `(loopStep + 1) % stepInterval === 0`.
 * `loopStep` is 0-indexed: at loopStep=0 with interval=1, the madrid cycle
 * advances to position 1.
 */
export function advanceAlmanac(
  state: AlmanacState,
  loopStep: number,
  cycles: ReadonlyArray<CycleConfig> = DEFAULT_CYCLES,
): AlmanacAdvanceResult {
  const next: Record<CycleId, number> = { ...state };
  const events: CycleEvent[] = [];

  const stepCount = loopStep + 1;
  for (const cfg of cycles) {
    if (cfg.stepInterval <= 0) continue;
    if (stepCount % cfg.stepInterval !== 0) continue;
    const newPosition = next[cfg.cycleId] + 1;
    next[cfg.cycleId] = newPosition;
    events.push({
      cycleId: cfg.cycleId,
      cyclePosition: newPosition,
      loopStep,
      purpose: cfg.purpose,
    });
  }

  return { state: Object.freeze(next), events };
}

/**
 * Run the almanac forward to a specific loop step (e.g. for replay
 * verification). Returns the final state and every event emitted along the
 * way. Useful when verifying that a recorded trace's almanac state matches
 * deterministic re-execution.
 */
export function rebuildAlmanac(
  totalSteps: number,
  cycles: ReadonlyArray<CycleConfig> = DEFAULT_CYCLES,
): AlmanacAdvanceResult {
  let state: AlmanacState = INITIAL_ALMANAC_STATE;
  const events: CycleEvent[] = [];
  for (let i = 0; i < totalSteps; i++) {
    const r = advanceAlmanac(state, i, cycles);
    state = r.state;
    events.push(...r.events);
  }
  return { state, events };
}
