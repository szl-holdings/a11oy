// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * floating-button.ts — `<rosie-fab>`, the always-visible circular launcher.
 *
 * Ambient, calm, one tap to expand. Emits a `rosie-open` event on click or
 * keyboard activation. Carries an ARIA label and is a real `<button>` so it is
 * reachable by keyboard and announced by screen readers.
 */

import { LitElement, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import {
  baseTokens,
  focusRing,
  floatingButtonStyles,
  type Position,
} from '../styles.js';

@customElement('rosie-fab')
export class RosieFab extends LitElement {
  static override styles = [baseTokens, focusRing, floatingButtonStyles];

  /** Docking corner. */
  @property({ type: String }) position: Position = 'bottom-right';

  /** Accessible label, derived from the host app by the parent element. */
  @property({ type: String }) label = 'Open the Rosie assistant';

  /** Anchor to a positioned ancestor instead of the viewport (stories,
   * previews, scoped iframe panels). */
  @property({ type: Boolean }) embedded = false;

  #emitOpen = () => {
    this.dispatchEvent(
      new CustomEvent('rosie-open', { bubbles: true, composed: true }),
    );
  };

  override render() {
    const left = this.position === 'bottom-left';
    return html`
      <button
        class="fab ${left ? 'left' : ''} ${this.embedded ? 'embedded' : ''}"
        type="button"
        aria-label=${this.label}
        title=${this.label}
        @click=${this.#emitOpen}
      >
        <span class="pulse" aria-hidden="true"></span>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle class="ring" cx="12" cy="12" r="8.5" stroke-width="1.6" />
          <circle class="dot" cx="12" cy="12" r="2.4" />
          <path
            class="ring"
            d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-fab': RosieFab;
  }
}
