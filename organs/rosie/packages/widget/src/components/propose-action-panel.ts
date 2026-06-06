// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * propose-action-panel.ts — `<rosie-propose-action-panel>`, the operator's
 * "Propose Action" surface (Wire D).
 *
 * The operator describes a consequential action; this panel asks a11oy for a
 * REAL policy verdict (a11oy /v1/policy/evaluate, which folds in sentra's
 * immune verdict) before it offers a "Confirm + sign" button. The decision and
 * its rationale are shown so the human-in-the-loop sees WHY an action is
 * allowed or blocked. The verdict logic lives in propose-action-controller.ts
 * (framework-agnostic, integration-tested under node); this element is the thin
 * Lit view over that controller.
 *
 * Accessibility: `role="form"`; the Confirm button is disabled until a11oy
 * allows; the status line is an `aria-live` region so verdicts are announced.
 */

import { LitElement, html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { baseTokens, focusRing } from '../styles.js';
import {
  evaluateForPanel,
  INITIAL_VIEW,
  type ProposeActionViewModel,
} from '../propose-action-controller.js';
import type { PolicyActionInput } from '../a11oy-policy-client.js';

@customElement('rosie-propose-action-panel')
export class RosieProposeActionPanel extends LitElement {
  static override styles = [baseTokens, focusRing];

  /** a11oy mesh-serve base URL supplied by the host. Empty => panel disabled. */
  @property({ type: String, attribute: 'a11oy-base' }) a11oyBase = '';

  /** Optional bearer token passed through from the host. */
  @property({ type: String }) token?: string;

  /** traceparent of the operator session span; forwarded to a11oy (Wire E). */
  @property({ type: String }) traceparent?: string;

  @state() private _view: ProposeActionViewModel = INITIAL_VIEW;
  @state() private _busy = false;

  /** Evaluate a proposed action against a11oy and update the view-model. */
  async evaluate(action: PolicyActionInput): Promise<void> {
    if (!this.a11oyBase) {
      this._view = {
        phase: 'idle',
        canConfirm: false,
        status: 'a11oy base URL is not configured.',
      };
      return;
    }
    this._busy = true;
    this._view = { ...this._view, phase: 'evaluating', status: 'Asking a11oy…' };
    try {
      this._view = await evaluateForPanel(action, {
        a11oyBase: this.a11oyBase,
        token: this.token,
        traceparent: this.traceparent,
      });
    } finally {
      this._busy = false;
    }
  }

  #confirm = () => {
    if (!this._view.canConfirm || !this._view.action) return;
    this.dispatchEvent(
      new CustomEvent('rosie-propose-confirm', {
        detail: { action: this._view.action, decision: this._view.decision },
        bubbles: true,
        composed: true,
      }),
    );
  };

  override render() {
    const v = this._view;
    return html`
      <section role="form" aria-label="Propose action">
        <p aria-live="polite" class="status status-${v.phase}">${v.status}</p>
        ${v.decision
          ? html`<dl class="verdict">
              <dt>Decision</dt><dd>${v.decision.decision}</dd>
              <dt>Decided by</dt><dd>${v.decision.decidedBy}</dd>
              <dt>Receipt</dt><dd>${v.decision.receiptHash || '—'}</dd>
            </dl>`
          : nothing}
        <button
          class="btn primary"
          ?disabled=${!v.canConfirm || this._busy}
          @click=${this.#confirm}
        >
          Confirm + sign
        </button>
      </section>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-propose-action-panel': RosieProposeActionPanel;
  }
}
