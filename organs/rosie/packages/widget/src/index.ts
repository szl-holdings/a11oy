// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * index.ts — public entry for `@szl-holdings/rosie-widget`.
 *
 * Importing this module registers every custom element as a side effect. It
 * also re-exports the element classes and the API types so a TypeScript host
 * can reference them directly.
 */

export { RosieWidget } from './rosie-widget.js';
export { RosieWidgetPanel } from './components/rosie-panel.js';
export { RosieFab } from './components/floating-button.js';
export {
  RosieCommandPalette,
  DEFAULT_COMMANDS,
  fuzzyScore,
  type CannedCommand,
} from './components/command-palette.js';
export { RosieConfirmDialog } from './components/confirm-dialog.js';
export { RosieReceiptStream } from './components/receipt-stream.js';

export {
  RosieApiClient,
  ApiNotConfiguredError,
  type ApiClientOptions,
  type AskResult,
  type ConfirmResult,
  type ProposedAction,
  type OperationalReceipt,
  type VerifyResult,
} from './api-client.js';

export {
  THEME_ACCENTS,
  THEME_LABELS,
  accentFor,
  type HostApp,
  type Position,
} from './styles.js';

// Wire D — rosie -> a11oy policy evaluation ("Propose Action" surface).
export { RosieProposeActionPanel } from './components/propose-action-panel.js';
export {
  evaluateForPanel,
  isScreened,
  INITIAL_VIEW,
  type ProposeActionViewModel,
  type ProposalPhase,
} from './propose-action-controller.js';
export {
  evaluateProposal,
  A11oyNotConfiguredError,
  type PolicyActionInput,
  type PolicyDecision,
  type PolicyClientOptions,
} from './a11oy-policy-client.js';
