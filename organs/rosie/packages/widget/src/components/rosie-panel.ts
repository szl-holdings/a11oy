// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * rosie-panel.ts — `<rosie-widget-panel>`, the slide-in panel.
 *
 * Sections:
 *  (a) chat input at the bottom (composer)
 *  (b) message thread + receipt cards (body)
 *  (c) action history with confirm buttons (surfaced via the confirm dialog)
 *
 * The panel owns the conversational state and the focus trap. It renders the
 * command palette inside its body when asked, and the confirm dialog as a
 * modal layer when the assistant proposes a consequential action.
 *
 * Accessibility: `role="dialog"`, `aria-modal="true"`, focus is trapped within
 * the panel, Esc closes it (emitting `rosie-close`), and focus is returned to
 * the launcher button by the parent element.
 */

import { LitElement, html, nothing } from 'lit';
import { customElement, property, state, query } from 'lit/decorators.js';
import {
  baseTokens,
  focusRing,
  panelStyles,
  threadStyles,
  type HostApp,
  type Position,
  THEME_LABELS,
} from '../styles.js';
import type {
  OperationalReceipt,
  ProposedAction,
  RosieApiClient,
} from '../api-client.js';
import { RosieReceiptStream } from './receipt-stream.js';
import {
  RosieCommandPalette,
  DEFAULT_COMMANDS,
  type CannedCommand,
} from './command-palette.js';
import { RosieConfirmDialog } from './confirm-dialog.js';

// Value-reference the child element classes so their `@customElement`
// registration side effects survive tree-shaking in production bundles.
if (!RosieReceiptStream || !RosieCommandPalette || !RosieConfirmDialog) throw new Error("child elements missing");

interface ChatMessage {
  readonly role: 'user' | 'assistant';
  readonly text: string;
  readonly receipts?: readonly OperationalReceipt[];
}

@customElement('rosie-widget-panel')
export class RosieWidgetPanel extends LitElement {
  static override styles = [baseTokens, focusRing, panelStyles, threadStyles];

  @property({ type: String }) app: HostApp = 'rosie';
  @property({ type: String }) position: Position = 'bottom-right';

  /** API client supplied by the host element. May be unconfigured. */
  @property({ attribute: false }) client?: RosieApiClient;

  /** When true, the palette is shown inside the body. */
  @property({ type: Boolean }) paletteOpen = false;

  /** Anchor scrim + panel to a positioned ancestor instead of the viewport
   * (stories, previews, scoped iframe panels). */
  @property({ type: Boolean }) embedded = false;

  @state() private _messages: ChatMessage[] = [];
  @state() private _draft = '';
  @state() private _busy = false;
  @state() private _pendingAction?: ProposedAction;

  @query('textarea') private _textarea?: HTMLTextAreaElement;
  @query('.panel') private _panel?: HTMLElement;

  override firstUpdated(): void {
    // Land focus inside the panel — on the palette input if open, else composer.
    if (!this.paletteOpen) this._textarea?.focus();
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has('paletteOpen') && !this.paletteOpen) {
      this._textarea?.focus();
    }
  }

  #close = () => {
    this.dispatchEvent(
      new CustomEvent('rosie-close', { bubbles: true, composed: true }),
    );
  };

  #onKeydown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      // If a modal/palette is open, let it handle Esc; otherwise close panel.
      if (this._pendingAction || this.paletteOpen) return;
      e.stopPropagation();
      this.#close();
      return;
    }
    if (e.key !== 'Tab' || !this._panel) return;
    const focusable = this._panel.querySelectorAll<HTMLElement>(
      'button, textarea, input, [href], [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = (this.renderRoot as ShadowRoot).activeElement as
      | HTMLElement
      | null;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  #onDraft = (e: Event) => {
    this._draft = (e.target as HTMLTextAreaElement).value;
  };

  #onComposerKeydown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void this.#send();
    }
  };

  async #send(text = this._draft): Promise<void> {
    const prompt = text.trim();
    if (!prompt || this._busy) return;
    this._messages = [...this._messages, { role: 'user', text: prompt }];
    this._draft = '';

    if (!this.client?.configured) {
      this._messages = [
        ...this._messages,
        {
          role: 'assistant',
          text:
            'I am not connected yet. A host needs to set the `api-base` ' +
            'attribute on <rosie-widget> so I can reach the rosie-api.',
        },
      ];
      return;
    }

    this._busy = true;
    try {
      const res = await this.client.ask(prompt);
      this._messages = [
        ...this._messages,
        { role: 'assistant', text: res.answer, receipts: res.receipts },
      ];
      if (res.proposedAction) this._pendingAction = res.proposedAction;
    } catch (err) {
      this._messages = [
        ...this._messages,
        { role: 'assistant', text: `Request failed: ${(err as Error).message}` },
      ];
    } finally {
      this._busy = false;
    }
  }

  #onCommand = (e: CustomEvent<{ command: CannedCommand }>) => {
    this.paletteOpen = false;
    void this.#send(e.detail.command.prompt);
  };

  #onPaletteClose = () => {
    this.paletteOpen = false;
  };

  async #onConfirm(e: CustomEvent<{ actionId: string }>): Promise<void> {
    const action = this._pendingAction;
    this._pendingAction = undefined;
    if (!action || !this.client?.configured) return;
    try {
      const res = await this.client.confirmAction(e.detail.actionId);
      this._messages = [
        ...this._messages,
        {
          role: 'assistant',
          text: res.ok
            ? `Confirmed and signed "${action.action}" on ${action.target}.`
            : `Could not execute: ${res.error ?? 'unknown error'}`,
          receipts: res.receipt ? [res.receipt] : undefined,
        },
      ];
    } catch (err) {
      this._messages = [
        ...this._messages,
        { role: 'assistant', text: `Execution failed: ${(err as Error).message}` },
      ];
    }
  }

  #onCancel = () => {
    this._pendingAction = undefined;
    this._textarea?.focus();
  };

  /** Seed messages for stories / demos without a live API. */
  seedMessages(messages: ChatMessage[]): void {
    this._messages = messages;
  }

  /** Show the confirm dialog for a given action (stories / demos). */
  showAction(action: ProposedAction): void {
    this._pendingAction = action;
  }

  #renderBody() {
    if (this.paletteOpen) {
      return html`<rosie-command-palette
        .commands=${DEFAULT_COMMANDS}
        @rosie-command=${this.#onCommand}
        @rosie-palette-close=${this.#onPaletteClose}
      ></rosie-command-palette>`;
    }
    if (this._messages.length === 0) {
      const configured = this.client?.configured ?? false;
      return html`
        <div class="empty">
          <div class="glyph" aria-hidden="true">◎</div>
          ${configured
            ? html`<p>
                Ask me about receipts, signatures, deployments, or mesh health
                for <strong>${THEME_LABELS[this.app]}</strong>. Press
                <span class="kbd">⌘K</span> for the command palette.
              </p>`
            : html`<p>
                I am ready, but not connected. Set
                <code>api-base</code> on
                <code>&lt;rosie-widget&gt;</code> to point me at the rosie-api,
                then ask me anything.
              </p>`}
        </div>
      `;
    }
    return html`
      ${this._messages.map((m) =>
        m.role === 'user'
          ? html`<div class="msg user">${m.text}</div>`
          : html`
              <div class="msg assistant">${m.text}</div>
              ${m.receipts?.map((r) => RosieReceiptStream.renderCard(r)) ??
              nothing}
            `,
      )}
      ${this._busy
        ? html`<div class="msg assistant" aria-live="polite">…thinking</div>`
        : nothing}
    `;
  }

  override render() {
    const left = this.position === 'bottom-left';
    return html`
      <div
        class="scrim ${this.embedded ? 'embedded' : ''}"
        @click=${this.#close}
        aria-hidden="true"
      ></div>
      <section
        class="panel ${left ? 'left' : ''} ${this.embedded ? 'embedded' : ''}"
        role="dialog"
        aria-modal="true"
        aria-label=${`Rosie assistant for ${THEME_LABELS[this.app]}`}
        @keydown=${this.#onKeydown}
      >
        <div class="header">
          <span class="badge" aria-hidden="true"></span>
          <h2>Rosie</h2>
          <span class="host">· ${THEME_LABELS[this.app]}</span>
          <span class="spacer"></span>
          <button
            class="iconbtn"
            type="button"
            aria-label="Open command palette"
            title="Command palette (⌘K / Ctrl-K)"
            @click=${() => (this.paletteOpen = !this.paletteOpen)}
          >
            ⌘
          </button>
          <button
            class="iconbtn"
            type="button"
            aria-label="Close assistant"
            title="Close (Esc)"
            @click=${this.#close}
          >
            ✕
          </button>
        </div>

        <div class="body">${this.#renderBody()}</div>

        <div class="composer">
          <textarea
            placeholder="Ask Rosie…  (Enter to send, Shift+Enter for newline)"
            rows="1"
            aria-label="Message Rosie"
            .value=${this._draft}
            @input=${this.#onDraft}
            @keydown=${this.#onComposerKeydown}
          ></textarea>
          <button
            class="send"
            type="button"
            ?disabled=${this._busy || this._draft.trim().length === 0}
            @click=${() => this.#send()}
          >
            Send
          </button>
        </div>
        <div class="hint">
          <span class="kbd">⌘K</span> commands
          <span class="kbd">Esc</span> close
        </div>

        ${this._pendingAction
          ? html`<rosie-confirm-dialog
              .action=${this._pendingAction}
              @rosie-confirm=${(e: CustomEvent<{ actionId: string }>) =>
                this.#onConfirm(e)}
              @rosie-cancel=${this.#onCancel}
            ></rosie-confirm-dialog>`
          : nothing}
      </section>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-widget-panel': RosieWidgetPanel;
  }
}
