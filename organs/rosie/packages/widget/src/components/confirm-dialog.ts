// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * confirm-dialog.ts — `<rosie-confirm-dialog>`, the human-in-the-loop gate.
 *
 * Pops when the assistant proposes a consequential action. Shows the action,
 * the target, and a preview of the signed receipt that confirming would emit.
 * Two buttons: "Confirm + sign" and "Cancel".
 *
 * Accessibility: a real modal — `role="dialog"`, `aria-modal="true"`,
 * focus moves to the dialog on open, Tab is trapped within it, Esc cancels,
 * and focus is restored by the parent panel when the dialog closes. Emits
 * `rosie-confirm` (with the actionId) or `rosie-cancel`.
 */

import { LitElement, html } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
import { baseTokens, focusRing, confirmDialogStyles } from '../styles.js';
import type { ProposedAction } from '../api-client.js';

@customElement('rosie-confirm-dialog')
export class RosieConfirmDialog extends LitElement {
  static override styles = [baseTokens, focusRing, confirmDialogStyles];

  /** The action awaiting confirmation. */
  @property({ attribute: false }) action!: ProposedAction;

  @query('.modal') private _modal?: HTMLElement;

  override firstUpdated(): void {
    // Move focus into the dialog so keyboard + screen-reader users land here.
    this._modal?.querySelector<HTMLElement>('.btn.primary')?.focus();
  }

  #confirm = () => {
    this.dispatchEvent(
      new CustomEvent('rosie-confirm', {
        detail: { actionId: this.action.actionId },
        bubbles: true,
        composed: true,
      }),
    );
  };

  #cancel = () => {
    this.dispatchEvent(
      new CustomEvent('rosie-cancel', { bubbles: true, composed: true }),
    );
  };

  #onKeydown = (ev: KeyboardEvent) => {
    if (ev.key === 'Escape') {
      ev.stopPropagation();
      this.#cancel();
      return;
    }
    if (ev.key !== 'Tab' || !this._modal) return;
    // Focus trap: cycle within the focusable elements of the dialog.
    const focusable = this._modal.querySelectorAll<HTMLElement>(
      'button, [href], input, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = (this.renderRoot as ShadowRoot).activeElement as HTMLElement | null;
    if (ev.shiftKey && active === first) {
      ev.preventDefault();
      last.focus();
    } else if (!ev.shiftKey && active === last) {
      ev.preventDefault();
      first.focus();
    }
  };

  override render() {
    const a = this.action;
    const preview = JSON.stringify(a.receiptPreview, null, 2);
    return html`
      <div class="modal-scrim" @click=${this.#cancel}>
        <div
          class="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="rosie-confirm-title"
          @click=${(e: Event) => e.stopPropagation()}
          @keydown=${this.#onKeydown}
        >
          <header>
            <span class="warn" aria-hidden="true">⚠</span>
            <h3 id="rosie-confirm-title">Confirm action</h3>
          </header>
          <div class="content">
            <p>${a.summary}</p>
            <div class="kv">
              <span class="k">action</span><span class="v">${a.action}</span>
              <span class="k">target</span><span class="v">${a.target}</span>
              <span class="k">tool</span>
              <span class="v">${a.receiptPreview.tool_name}</span>
            </div>
            <div>
              <div class="k" style="margin-bottom:6px;color:var(--rosie-text-faint)">
                signed receipt preview
              </div>
              <pre aria-label="Signed receipt preview">${preview}</pre>
            </div>
          </div>
          <div class="actions">
            <button class="btn" type="button" @click=${this.#cancel}>
              Cancel
            </button>
            <button class="btn primary" type="button" @click=${this.#confirm}>
              Confirm + sign
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-confirm-dialog': RosieConfirmDialog;
  }
}
