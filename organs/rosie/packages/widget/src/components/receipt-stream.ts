// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * receipt-stream.ts — `<rosie-receipt-stream>`, an SSE consumer that connects
 * to `/v1/receipts/stream?app=<app>` and renders incoming receipts as cards.
 *
 * Accessibility: the stream region is an `aria-live="polite"` log so a screen
 * reader announces each new receipt as it arrives. Each card exposes its tool
 * name, event type, sequence, and a truncated payload hash.
 *
 * Lifecycle: the `EventSource` is opened on `connectedCallback` only when a
 * `streamUrl` is set, and closed on `disconnectedCallback`. No global state.
 */

import { LitElement, html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { baseTokens, threadStyles } from '../styles.js';
import type { OperationalReceipt } from '../api-client.js';

@customElement('rosie-receipt-stream')
export class RosieReceiptStream extends LitElement {
  static override styles = [baseTokens, threadStyles];

  /** SSE endpoint. Empty => no connection (unconfigured state). */
  @property({ type: String, attribute: 'stream-url' }) streamUrl = '';

  /** When true, the EventSource is opened with credentials (host session). */
  @property({ type: Boolean }) withCredentials = true;

  /** Seed receipts (e.g. from the initial REST fetch or a story fixture). */
  @property({ attribute: false }) seed: readonly OperationalReceipt[] = [];

  @state() private _receipts: OperationalReceipt[] = [];
  @state() private _error = '';

  #source: EventSource | null = null;

  override connectedCallback(): void {
    super.connectedCallback();
    this._receipts = [...this.seed];
    this.#openStream();
  }

  override updated(changed: Map<string, unknown>): void {
    if (changed.has('streamUrl')) this.#openStream();
    if (changed.has('seed') && this._receipts.length === 0) {
      this._receipts = [...this.seed];
    }
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this.#closeStream();
  }

  #closeStream(): void {
    this.#source?.close();
    this.#source = null;
  }

  #openStream(): void {
    this.#closeStream();
    if (!this.streamUrl) return;
    // EventSource is unavailable in some test/SSR contexts; guard defensively.
    if (typeof EventSource === 'undefined') return;
    try {
      const es = new EventSource(this.streamUrl, {
        withCredentials: this.withCredentials,
      });
      es.onmessage = (ev: MessageEvent) => {
        try {
          const receipt = JSON.parse(ev.data) as OperationalReceipt;
          // Newest first; cap to avoid unbounded growth in long sessions.
          this._receipts = [receipt, ...this._receipts].slice(0, 100);
        } catch {
          /* ignore malformed frames; the server contract is canonical JSON */
        }
      };
      es.onerror = () => {
        this._error = 'stream interrupted — will retry automatically';
      };
      this.#source = es;
    } catch (err) {
      this._error = `cannot open stream: ${(err as Error).message}`;
    }
  }

  /** Public helper so the panel can inject a receipt without a live stream. */
  push(receipt: OperationalReceipt): void {
    this._receipts = [receipt, ...this._receipts].slice(0, 100);
  }

  static renderCard(r: OperationalReceipt) {
    const shortHash = (r.payload_hash ?? '').slice(0, 18);
    const shortRoot = (r.merkle_root ?? '').slice(0, 18);
    return html`
      <article
        class="receipt-card"
        aria-label=${`Receipt ${r.receipt_id} from tool ${r.tool_name}, event ${r.event_type}`}
      >
        <div class="rc-head">
          <span class="rc-tool">${r.tool_name}</span>
          <span class="rc-type">${r.event_type}</span>
        </div>
        <dl>
          <dt>receipt</dt>
          <dd title=${r.receipt_id}>${r.receipt_id}</dd>
          <dt>seq</dt>
          <dd>${r.sequence}</dd>
          <dt>actor</dt>
          <dd title=${r.actor_id}>${r.actor_id}</dd>
          <dt>payload</dt>
          <dd title=${r.payload_hash}>${shortHash}…</dd>
          <dt>merkle</dt>
          <dd title=${r.merkle_root}>${shortRoot}…</dd>
          <dt>time</dt>
          <dd>${r.timestamp_iso8601}</dd>
        </dl>
      </article>
    `;
  }

  override render() {
    return html`
      <div role="log" aria-live="polite" aria-label="Receipt stream">
        ${this._receipts.map((r) => RosieReceiptStream.renderCard(r))}
        ${this._error
          ? html`<p class="receipt-card verify-bad">${this._error}</p>`
          : nothing}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'rosie-receipt-stream': RosieReceiptStream;
  }
}
