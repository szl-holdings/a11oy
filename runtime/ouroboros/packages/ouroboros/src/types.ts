/**
 * Ouroboros — bounded loops with measurable convergence.
 *
 * Types are deliberately structural and minimal. The kernel must remain
 * runtime-agnostic (no React, no Node-only APIs in this file).
 */

/** Reason the loop terminated. */
export type ExitReason =
  | 'converged'           // adjacent-state delta fell at or below convergenceThreshold
  | 'consistent'          // ONLINE PROXY: two successive intermediate outputs agreed
                          // at or above earlyExitConsistency. The true cross-step
                          // (intermediate-vs-final) consistency is computed
                          // retroactively into LoopStep.consistency after exit.
  | 'budgetExhausted'     // hit maxSteps
  | 'aborted';            // step function returned { abort: true }

/** A single iteration of the loop. */
export interface LoopStep<S, O = unknown> {
  /** 0-indexed step number. */
  index: number;
  /** State after applying the step function. */
  state: S;
  /** Optional intermediate output emitted by this step. */
  output?: O;
  /**
   * Magnitude of change from the previous step (0 = unchanged).
   * Computed via the user-supplied delta function. Step 0 always has 0.
   */
  deltaMagnitude: number;
  /**
   * Cross-step consistency: agreement between this step's output and the
   * (eventual) final output, computed in [0, 1] where 1 = perfect agreement.
   * Populated only after the loop terminates and consistency scoring runs.
   */
  consistency?: number;
  /** Wall-clock duration of this step in milliseconds. */
  durationMs: number;
}

/**
 * The full trace of an Ouroboros loop. This is the *primary product* of the
 * primitive — every loop emits a trace, and downstream consumers read the
 * trace rather than the bare final output.
 */
export interface LoopTrace<S, O = unknown> {
  /** Stable identifier for this loop run. */
  id: string;
  /** Logical label for the loop ("agent.refine", "threat.score", etc.). */
  label: string;
  /** Ordered list of steps. */
  steps: LoopStep<S, O>[];
  /** Final state at termination. */
  finalState: S;
  /** Final output (if any). */
  finalOutput?: O;
  /** Why the loop ended. */
  exitReason: ExitReason;
  /** Effective depth used vs configured budget. */
  stepsRun: number;
  maxSteps: number;
  /**
   * The earliest step at which the system *would have* been safe to early-exit
   * given the consistency threshold. Useful for retroactively scoring
   * efficiency and tuning thresholds. -1 if no such step exists.
   */
  earliestSafeExit: number;
  /** Total wall-clock duration. */
  totalDurationMs: number;
}

/** Configuration accepted by runLoop(). */
export interface LoopConfig {
  /** Maximum number of iterations. Default 8. */
  maxSteps?: number;
  /** If deltaMagnitude falls at or below this value, exit as 'converged'. Default 1e-3. */
  convergenceThreshold?: number;
  /**
   * If two successive intermediate outputs agree at or above this value
   * (online step-stability proxy for cross-step consistency), exit as
   * 'consistent'. Default 1.01 — i.e. disabled by default. Set to a value
   * in [0, 1] (e.g. 0.98) to enable. Note: this is the step-to-step proxy;
   * the true intermediate-vs-final cross-step consistency is computed
   * retroactively after the loop terminates.
   */
  earlyExitConsistency?: number;
  /**
   * Threshold used to compute `earliestSafeExit` retroactively. The
   * earliest step whose intermediate output agreed with the final output at
   * or above this threshold is reported as the step at which the loop
   * could have safely short-circuited. Default 0.95.
   */
  safeExitConsistency?: number;
  /** Optional stable id; auto-generated if not provided. */
  id?: string;
  /** Logical label for the trace. */
  label?: string;
}

/**
 * The user-supplied step function. Receives the current state and step index,
 * returns the next state plus an optional intermediate output. May return
 * `{ abort: true }` to stop the loop with exitReason='aborted'.
 */
export type StepFn<S, O = unknown> = (
  state: S,
  index: number,
) => StepResult<S, O> | Promise<StepResult<S, O>>;

export type StepResult<S, O = unknown> =
  | { state: S; output?: O; abort?: false }
  | { abort: true };

/**
 * Distance function: returns the magnitude of change between two states in
 * [0, ∞). Smaller = more converged. Caller-supplied because state shape is
 * arbitrary.
 */
export type DeltaFn<S> = (prev: S, next: S) => number;

/**
 * Consistency function: returns agreement between two outputs, in [0, 1].
 * Used in two places at runtime:
 *   1. RETROACTIVELY (primary): each intermediate output is scored against
 *      the final output to populate LoopStep.consistency and to compute
 *      `earliestSafeExit` against `safeExitConsistency`.
 *   2. ONLINE (proxy): two successive intermediate outputs are compared as
 *      a step-stability proxy; if their agreement meets `earlyExitConsistency`,
 *      the loop exits with reason 'consistent'. Both outputs must be defined.
 * Optional — omit if the caller does not emit intermediate outputs.
 */
export type ConsistencyFn<O> = (a: O | undefined, b: O | undefined) => number;
