// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * rosie-widget.ts — `<rosie-widget>`, the ambient operator widget.
 *
 * The single custom element a host embeds. It renders the floating launcher,
 * expands into the slide-in panel on click or ⌘K/Ctrl-K, derives its accent
 * from the host `app`, and constructs the typed api-client.
 *
 * Framework-agnostic by construction: it is a standard custom element with
 * Shadow DOM (Lit default), so it drops into React (a11oy), Gradio (rosie),
 * iframes, or plain HTML without a host framework. It works inside an iframe
 * because everything is `position: fixed` relative to the iframe viewport.
 *
 * Global-listener discipline: the ONLY global listener it registers is a
 * `keydown` handler on `window` for ⌘K / Ctrl-K. That listener is removed in
 * `disconnectedCallback`, so the widget leaves no trace when unmounted.
 *
 * Session discipline: the widget never reads or writes `document.cookie`. The
 * api-client uses `credentials: 'include'` so the browser reuses the host's
 * existing session; an optional `token` attribute is passed through verbatim.
 *
 * Attributes:
 *   app       (required) a11oy | amaru | sentra | vessels | rosie
 *   api-base  (required for live use) rosie-api URL; empty => offline message
 *   position  bottom-right (default) | bottom-left
 *   theme     accent override; default auto-derived from `app`
 *   token     optional bearer token, passed through to the api-client
 */

import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  baseTokens,
  accentFor,
  THEME_LABELS,
  type HostApp,
  type Position,
} from './styles.js';
import { RosieApiClient } from './api-client.js';
import { RosieFab } from './components/floating-button.js';
import { RosieWidgetPanel } from './components/rosie-panel.js';

// Value-reference the child element classes so their `@customElement`
// registration side effects survive tree-shaking in production bundles.
if (!RosieFab || !RosieWidgetPanel) throw new Error("child elements missing");

@customElement('rosie-widget')
export class RosieWidget extends LitElement {
  static override styles = [
    baseTokens,
    css`
      :host {
        /* The element itself occupies no layout space; children are fixed. */
        display: contents;
      }
    `,
  ];

  /** Which app is hosting. Drives receipt filter + accent. */
  @property({ type: String }) app: HostApp = 'rosie';

  /** rosie-api base URL. Empty => offline; widget shows a configure message. */
  @property({ type: String, attribute: 'api-base' }) apiBase = '';

  /** Docking corner. */
  @property({ type: String }) position: Position = 'bottom-right';

  /** Accent override; default derived from `app`. */
  @property({ type: String }) theme = '';

  /** Optional bearer token passed through to the api-client. */
  @property({ type: String }) token = '';

  /** Custom z-index passthrough for the `--rosie-z-index` token. */
  @property({ type: String, attribute: 'z-index' }) zIndex = '';

  @state() private _open = false;
  @state() private _paletteOpen = false;

  #client?: RosieApiClient;

  // Keep a stable bound reference so we can add AND remove the same function.
  #onGlobalKeydown = (e: KeyboardEvent) => {
    // ⌘K on macOS, Ctrl-K elsewhere. Ignore when typing in a host input is
    // already focused — except our own fields, which live in shadow roots and
    // are not visible to this `document`-level check.
    const isPalette = (e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K');
    if (!isPalette) return;
    e.preventDefault();
    this._open = true;
    this._paletteOpen = true;
  };

  override connectedCallback(): void {
    super.connectedCallback();
    this.#rebuildClient();
    // The single permitted global listener.
    window.addEventListener('keydown', this.#onGlobalKeydown);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    // Leave no trace on the host page.
    window.removeEventListener('keydown', this.#onGlobalKeydown);
  }

  override willUpdate(changed: Map<string, unknown>): void {
    if (
      changed.has('apiBase') ||
      changed.has('app') ||
      changed.has('token')
    ) {
      this.#rebuildClient();
    }
  }

  #rebuildClient(): void {
    this.#client = new RosieApiClient({
      apiBase: this.apiBase,
      app: this.app,
      token: this.token || undefined,
    });
  }

  #open = () => {
    this._open = true;
  };

  #close = () => {
    this._open = false;
    this._paletteOpen = false;
    // Return focus to the launcher for keyboard + screen-reader continuity.
    this.updateComplete.then(() => {
      this.renderRoot
        .querySelector('rosie-fab')
        ?.shadowRoot?.querySelector<HTMLElement>('button')
        ?.focus();
    });
  };

  override render() {
    const accent = this.theme || accentFor(this.app);
    // Apply the per-host accent + optional z-index as inline custom props so a
    // host can still override them from its own stylesheet if it wants.
    const hostStyle = `--rosie-accent:${accent};${
      this.zIndex ? `--rosie-z-index:${this.zIndex};` : ''
    }`;
    const label = `Open the Rosie assistant for ${THEME_LABELS[this.app] ?? this.app}`;
    return html`
      <div style=${hostStyle}>
        ${this._open
          ? html`<rosie-widget-panel
              .app=${this.app}
              .position=${this.position}
              .client=${this.#client}
              .paletteOpen=${this._paletteOpen}
              @rosie-close=${this.#close}
            ></rosie-widget-panel>`
          : html`<rosie-fab
              .position=${this.position}
              .label=${label}
              @rosie-open=${this.#open}
            ></rosie-fab>`}
        ${nothing}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-widget': RosieWidget;
  }
}
