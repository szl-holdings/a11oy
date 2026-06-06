// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * propose-action-controller.ts — the logic behind the "Propose Action" panel.
 *
 * The operator types/selects a consequential action. Before the panel offers a
 * "Confirm + sign" button, the controller asks a11oy for a real policy verdict
 * (Wire D, via a11oy-policy-client.ts → a11oy /v1/policy/evaluate, which itself
 * folds in sentra's immune verdict). Confirm is offered ONLY when a11oy allows.
 *
 * This module is framework-agnostic so it can be unit/integration-tested under
 * node and mounted by the Lit `<rosie-propose-action-panel>` element. It holds
 * no DOM references; it returns a plain view-model the element renders.
 */

import {
  evaluateProposal,
  type PolicyActionInput,
  type PolicyClientOptions,
  type PolicyDecision,
} from './a11oy-policy-client.js';

export type ProposalPhase = 'idle' | 'evaluating' | 'allowed' | 'denied';

/** What the panel renders. */
export interface ProposeActionViewModel {
  readonly phase: ProposalPhase;
  /** Whether the Confirm + sign button is enabled. */
  readonly canConfirm: boolean;
  /** The proposed action under evaluation, if any. */
  readonly action?: PolicyActionInput;
  /** a11oy's verdict, once evaluated. */
  readonly decision?: PolicyDecision;
  /** Operator-facing status line. */
  readonly status: string;
}

export const INITIAL_VIEW: ProposeActionViewModel = {
  phase: 'idle',
  canConfirm: false,
  status: 'Describe an action to propose.',
};

/**
 * Evaluate a proposed action against a11oy and produce the next view-model.
 * Confirm is gated on a11oy's verdict: allowed → confirmable; deny → blocked.
 */
export async function evaluateForPanel(
  action: PolicyActionInput,
  opts: PolicyClientOptions,
): Promise<ProposeActionViewModel> {
  const decision = await evaluateProposal(action, opts);
  if (decision.decision === 'allow') {
    return {
      phase: 'allowed',
      canConfirm: true,
      action,
      decision,
      status: `Allowed by ${decision.decidedBy}: ${decision.rationale}`,
    };
  }
  return {
    phase: 'denied',
    canConfirm: false,
    action,
    decision,
    status: `Blocked by ${decision.decidedBy}: ${decision.rationale}`,
  };
}

/** A confirmable proposal MUST carry an a11oy receipt hash proving it was screened. */
export function isScreened(vm: ProposeActionViewModel): boolean {
  return (
    vm.phase === 'allowed' &&
    vm.canConfirm &&
    !!vm.decision &&
    vm.decision.reachedA11oy &&
    vm.decision.receiptHash.length > 0
  );
}
