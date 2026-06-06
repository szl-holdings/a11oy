// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * command-palette.ts — `<rosie-command-palette>`, the Cmd-K / Ctrl-K palette.
 *
 * Fuzzy-search across canned commands. Spawns into the same panel (rendered
 * inside the panel body, not as a separate overlay). Arrow keys move the
 * selection; Enter runs the highlighted command; Esc closes the palette.
 *
 * Emits `rosie-command` with the selected command's prompt, which the panel
 * feeds into the assistant as if the operator had typed it.
 */

import { LitElement, html, nothing } from 'lit';
import { customElement, property, state, query } from 'lit/decorators.js';
import { baseTokens, focusRing, paletteStyles } from '../styles.js';

export interface CannedCommand {
  readonly id: string;
  readonly label: string;
  /** The prompt sent to the assistant when this command is chosen. */
  readonly prompt: string;
  /** Short right-aligned descriptor. */
  readonly hint: string;
  readonly icon: string;
}

/** The default canned commands available in every host. */
export const DEFAULT_COMMANDS: readonly CannedCommand[] = Object.freeze([
  {
    id: 'show-receipts',
    label: 'Show receipts',
    prompt: 'Show me the recent receipts for this app',
    hint: 'recent',
    icon: '🧾',
  },
  {
    id: 'verify-signature',
    label: 'Verify signature',
    prompt: 'Verify the signature on the latest receipt',
    hint: 'verify',
    icon: '🔐',
  },
  {
    id: 'deploy-package',
    label: 'Deploy package',
    prompt: 'Deploy the current package',
    hint: 'action',
    icon: '🚀',
  },
  {
    id: 'mesh-health',
    label: 'Show mesh health',
    prompt: 'Show the mesh health summary',
    hint: 'status',
    icon: '📊',
  },
]);

/**
 * Tiny subsequence fuzzy matcher. Returns a score (higher is better) or -1 if
 * the query is not a subsequence of the target. Contiguous and word-boundary
 * hits score higher. Deterministic, dependency-free.
 */
export function fuzzyScore(query: string, target: string): number {
  const q = query.toLowerCase().trim();
  const t = target.toLowerCase();
  if (q.length === 0) return 0;
  let qi = 0;
  let score = 0;
  let streak = 0;
  let prevMatch = -2;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      streak = ti === prevMatch + 1 ? streak + 1 : 1;
      score += streak;
      if (ti === 0 || t[ti - 1] === ' ') score += 3; // word-boundary bonus
      prevMatch = ti;
      qi++;
    }
  }
  return qi === q.length ? score : -1;
}

@customElement('rosie-command-palette')
export class RosieCommandPalette extends LitElement {
  static override styles = [baseTokens, focusRing, paletteStyles];

  @property({ attribute: false }) commands: readonly CannedCommand[] =
    DEFAULT_COMMANDS;

  @state() private _query = '';
  @state() private _selected = 0;

  @query('input') private _input?: HTMLInputElement;

  override firstUpdated(): void {
    this._input?.focus();
  }

  private get _filtered(): readonly CannedCommand[] {
    if (!this._query.trim()) return this.commands;
    return this.commands
      .map((c) => ({ c, s: Math.max(fuzzyScore(this._query, c.label), fuzzyScore(this._query, c.hint)) }))
      .filter((x) => x.s >= 0)
      .sort((a, b) => b.s - a.s)
      .map((x) => x.c);
  }

  #onInput = (e: Event) => {
    this._query = (e.target as HTMLInputElement).value;
    this._selected = 0;
  };

  #choose(cmd: CannedCommand): void {
    this.dispatchEvent(
      new CustomEvent('rosie-command', {
        detail: { command: cmd },
        bubbles: true,
        composed: true,
      }),
    );
  }

  #close(): void {
    this.dispatchEvent(
      new CustomEvent('rosie-palette-close', { bubbles: true, composed: true }),
    );
  }

  #onKeydown = (e: KeyboardEvent) => {
    const items = this._filtered;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this._selected = Math.min(this._selected + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this._selected = Math.max(this._selected - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const cmd = items[this._selected];
      if (cmd) this.#choose(cmd);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      this.#close();
    }
  };

  override render() {
    const items = this._filtered;
    return html`
      <div class="palette" role="dialog" aria-label="Command palette">
        <input
          type="text"
          placeholder="Search commands…"
          autocomplete="off"
          spellcheck="false"
          .value=${this._query}
          @input=${this.#onInput}
          @keydown=${this.#onKeydown}
          aria-label="Search commands"
          role="combobox"
          aria-expanded="true"
          aria-controls="rosie-cmd-list"
        />
        <ul id="rosie-cmd-list" role="listbox" aria-label="Commands">
          ${items.length === 0
            ? html`<li class="noresults" role="option" aria-selected="false">
                No matching commands
              </li>`
            : nothing}
          ${items.map(
            (cmd, i) => html`
              <li
                role="option"
                aria-selected=${i === this._selected}
                @click=${() => this.#choose(cmd)}
                @mouseenter=${() => (this._selected = i)}
              >
                <span class="pico" aria-hidden="true">${cmd.icon}</span>
                <span>${cmd.label}</span>
                <span class="pdesc">${cmd.hint}</span>
              </li>
            `,
          )}
        </ul>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-command-palette': RosieCommandPalette;
  }
}
