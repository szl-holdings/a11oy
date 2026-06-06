// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * api-client.ts — typed fetch wrapper for the rosie-api endpoints.
 *
 * The widget IS a client of the receipt substrate. Receipt shapes are imported
 * **type-only** from `@szl-holdings/a11oy-receipt-substrate` (the same package
 * the a11oy wiring PR publishes). A type-only import is erased at build time by
 * the TypeScript/Vite pipeline, so the widget bundle never carries the
 * substrate runtime and does not require the substrate to be published before
 * the widget can be built. The host application supplies the running rosie-api
 * at `api-base`; this client only describes the wire contract.
 *
 * Network discipline:
 *  - No request is issued until a non-empty `apiBase` is configured.
 *  - `credentials: 'include'` reuses the host page's existing cookies/session.
 *    The widget never reads, copies, or stores `document.cookie`; it relies on
 *    the browser to attach the host's credentials to same-origin (or
 *    CORS-allowed) requests. No tokens are persisted by the widget.
 *  - An optional bearer token may be passed through by the host via the
 *    `token` option; if present it is sent as `Authorization: Bearer …` and
 *    never logged.
 */

import type {
  OperationalReceipt,
  VerifyResult,
} from '@szl-holdings/a11oy-receipt-substrate';

import type { HostApp } from './styles.js';

export type { OperationalReceipt, VerifyResult };

/** A consequential action the assistant proposes to execute. */
export interface ProposedAction {
  /** Stable identifier the server assigns to this proposal. */
  readonly actionId: string;
  /** Verb, e.g. "deploy", "verify", "rotate-key". */
  readonly action: string;
  /** What the action operates on, e.g. "amaru@v0.4.1". */
  readonly target: string;
  /** Human summary rendered in the confirm dialog. */
  readonly summary: string;
  /** Preview of the receipt that signing this action would emit. */
  readonly receiptPreview: OperationalReceipt;
}

/** Result of asking the assistant a question. */
export interface AskResult {
  /** Free-text answer to render in the thread. */
  readonly answer: string;
  /** Receipts the answer references (rendered as cards). */
  readonly receipts?: readonly OperationalReceipt[];
  /** A consequential action awaiting human confirmation, if any. */
  readonly proposedAction?: ProposedAction;
}

/** Result of confirming + signing an action. */
export interface ConfirmResult {
  readonly ok: boolean;
  readonly receipt?: OperationalReceipt;
  readonly error?: string;
}

export interface ApiClientOptions {
  /** rosie-api base URL. Empty string => unconfigured (no network calls). */
  readonly apiBase: string;
  /** Which host app — sent as the receipt filter on every request. */
  readonly app: HostApp;
  /** Optional bearer token passed through from the host. */
  readonly token?: string;
}

export class ApiNotConfiguredError extends Error {
  constructor() {
    super('rosie-widget: api-base is not configured');
    this.name = 'ApiNotConfiguredError';
  }
}

/**
 * Typed client. Construct once per `<rosie-widget>` instance. All methods
 * reject with {@link ApiNotConfiguredError} when `apiBase` is empty so the UI
 * can show its "configure api-base" message instead of attempting a fetch.
 */
export class RosieApiClient {
  readonly #apiBase: string;
  readonly #app: HostApp;
  readonly #token?: string;

  constructor(opts: ApiClientOptions) {
    // Trim a trailing slash so `${base}/v1/...` is always well-formed.
    this.#apiBase = (opts.apiBase ?? '').replace(/\/+$/, '');
    this.#app = opts.app;
    this.#token = opts.token;
  }

  /** True once a host has supplied an api-base. */
  get configured(): boolean {
    return this.#apiBase.length > 0;
  }

  #headers(extra?: Record<string, string>): Headers {
    const h = new Headers({ Accept: 'application/json', ...extra });
    if (this.#token) h.set('Authorization', `Bearer ${this.#token}`);
    return h;
  }

  #url(path: string, params?: Record<string, string>): string {
    const u = new URL(this.#apiBase + path, this.#apiBase || 'http://invalid.local');
    u.searchParams.set('app', this.#app);
    if (params) {
      for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
    }
    return u.toString();
  }

  #assertConfigured(): void {
    if (!this.configured) throw new ApiNotConfiguredError();
  }

  /** Ask the assistant a question scoped to the current app. */
  async ask(prompt: string, signal?: AbortSignal): Promise<AskResult> {
    this.#assertConfigured();
    const res = await fetch(this.#url('/v1/ask'), {
      method: 'POST',
      credentials: 'include',
      headers: this.#headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ app: this.#app, prompt }),
      signal,
    });
    if (!res.ok) throw new Error(`ask failed: HTTP ${res.status}`);
    return (await res.json()) as AskResult;
  }

  /** Fetch recent receipts for the current app (used as the initial list). */
  async recentReceipts(
    limit = 20,
    signal?: AbortSignal,
  ): Promise<readonly OperationalReceipt[]> {
    this.#assertConfigured();
    const res = await fetch(
      this.#url('/v1/receipts', { limit: String(limit) }),
      { credentials: 'include', headers: this.#headers(), signal },
    );
    if (!res.ok) throw new Error(`receipts failed: HTTP ${res.status}`);
    return (await res.json()) as OperationalReceipt[];
  }

  /** Verify a receipt's signature/chain server-side. */
  async verify(receiptId: string, signal?: AbortSignal): Promise<VerifyResult> {
    this.#assertConfigured();
    const res = await fetch(this.#url(`/v1/receipts/${encodeURIComponent(receiptId)}/verify`), {
      credentials: 'include',
      headers: this.#headers(),
      signal,
    });
    if (!res.ok) throw new Error(`verify failed: HTTP ${res.status}`);
    return (await res.json()) as VerifyResult;
  }

  /** Confirm + sign a proposed action. Human-in-the-loop gate. */
  async confirmAction(actionId: string, signal?: AbortSignal): Promise<ConfirmResult> {
    this.#assertConfigured();
    const res = await fetch(this.#url('/v1/actions/confirm'), {
      method: 'POST',
      credentials: 'include',
      headers: this.#headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ app: this.#app, actionId }),
      signal,
    });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    return (await res.json()) as ConfirmResult;
  }

  /**
   * Build the SSE URL for the receipt stream. The component opens the
   * `EventSource` itself (so it can manage lifecycle and `withCredentials`);
   * the client only owns URL construction so the contract stays in one place.
   */
  receiptStreamUrl(): string {
    this.#assertConfigured();
    return this.#url('/v1/receipts/stream');
  }
}
