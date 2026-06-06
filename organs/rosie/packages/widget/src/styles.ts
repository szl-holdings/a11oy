// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * styles.ts — shared design tokens and Lit `css` template literals for the
 * rosie-widget widget.
 *
 * Tokens follow the amaru-platform landing template (the gold-standard
 * surface): deep navy base, high-contrast text, one accent per host. The
 * accent is supplied at runtime via the `--rosie-accent` custom property so
 * a host page can override it without rebuilding the widget. Defaults are
 * derived from the `app` attribute (see THEME_ACCENTS).
 *
 * All styles live inside the component Shadow DOM, so none of these rules
 * leak into the host page and none of the host page's rules leak in
 * (except inherited custom properties, which is intentional and documented
 * in docs/HOST_INTEGRATION.md).
 */

import { css } from 'lit';

/** Host app identifiers. `rosie` is the standalone console embedding case. */
export type HostApp = 'a11oy' | 'amaru' | 'sentra' | 'vessels' | 'rosie';

/** Panel docking position. */
export type Position = 'bottom-right' | 'bottom-left';

/**
 * Per-host accent colors. Sourced from each module's published landing page:
 *  - a11oy  cyan        #00d4ff
 *  - amaru  gold        #f5b32a
 *  - sentra green        #3ddc84
 *  - vessels ocean-cyan #0099cc
 *  - rosie  coral        #ff7a59
 */
export const THEME_ACCENTS: Readonly<Record<HostApp, string>> = Object.freeze({
  a11oy: '#00d4ff',
  amaru: '#f5b32a',
  sentra: '#3ddc84',
  vessels: '#0099cc',
  rosie: '#ff7a59',
});

/** Human-readable host labels for ARIA and headings. */
export const THEME_LABELS: Readonly<Record<HostApp, string>> = Object.freeze({
  a11oy: 'A11oy',
  amaru: 'Amaru',
  sentra: 'Sentra',
  vessels: 'Vessels',
  rosie: 'Rosie',
});

/**
 * Resolve the accent for a host app, falling back to the rosie coral if the
 * attribute is unrecognised (defensive — never throws on a bad host string).
 */
export function accentFor(app: string | null | undefined): string {
  if (app && app in THEME_ACCENTS) {
    return THEME_ACCENTS[app as HostApp];
  }
  return THEME_ACCENTS.rosie;
}

/**
 * Base tokens shared by every component. Hosts can override `--rosie-accent`
 * and `--rosie-z-index`; everything else is internal.
 */
export const baseTokens = css`
  :host {
    --rosie-z-index: 2147483000;
    --rosie-bg: #0a0f1a;
    --rosie-bg-raised: #111a2b;
    --rosie-bg-input: #0d1424;
    --rosie-border: rgba(255, 255, 255, 0.1);
    --rosie-border-strong: rgba(255, 255, 255, 0.18);
    --rosie-text: #e8eef6;
    --rosie-text-dim: #8aa0b8;
    --rosie-text-faint: #5b7088;
    --rosie-danger: #ff5d5d;
    --rosie-ok: #3ddc84;
    --rosie-radius: 14px;
    --rosie-radius-sm: 9px;
    --rosie-shadow: 0 18px 60px rgba(0, 0, 0, 0.55);
    --rosie-font: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto,
      Helvetica, Arial, sans-serif;
    --rosie-mono: ui-monospace, 'SF Mono', 'JetBrains Mono', 'Fira Code',
      Menlo, monospace;

    /* Respect users who ask for reduced motion. */
    --rosie-ease: cubic-bezier(0.22, 1, 0.36, 1);
    --rosie-dur: 280ms;

    box-sizing: border-box;
    font-family: var(--rosie-font);
    color: var(--rosie-text);
  }

  :host *,
  :host *::before,
  :host *::after {
    box-sizing: border-box;
  }

  @media (prefers-reduced-motion: reduce) {
    :host {
      --rosie-dur: 0ms;
    }
  }
`;

/** Focus-ring style reused on every interactive element. */
export const focusRing = css`
  :focus-visible {
    outline: 2px solid var(--rosie-accent, #ff7a59);
    outline-offset: 2px;
    border-radius: var(--rosie-radius-sm);
  }
`;

/** Floating-button styles. */
export const floatingButtonStyles = css`
  .fab {
    position: fixed;
    bottom: 22px;
    right: 22px;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 1px solid var(--rosie-border-strong);
    background: radial-gradient(
        120% 120% at 30% 25%,
        color-mix(in srgb, var(--rosie-accent, #ff7a59) 32%, var(--rosie-bg-raised)) 0%,
        var(--rosie-bg-raised) 70%
      );
    color: var(--rosie-text);
    cursor: pointer;
    z-index: var(--rosie-z-index);
    box-shadow: var(--rosie-shadow),
      0 0 0 0 color-mix(in srgb, var(--rosie-accent, #ff7a59) 60%, transparent);
    display: grid;
    place-items: center;
    transition: transform var(--rosie-dur) var(--rosie-ease),
      box-shadow var(--rosie-dur) var(--rosie-ease);
  }
  .fab.left {
    right: auto;
    left: 22px;
  }
  /* Embedded mode: anchor to a positioned ancestor instead of the viewport.
     Used for stories, previews, and tightly-scoped iframe panels. */
  .fab.embedded {
    position: absolute;
  }
  .fab:hover {
    transform: translateY(-2px) scale(1.04);
    box-shadow: var(--rosie-shadow),
      0 0 0 6px color-mix(in srgb, var(--rosie-accent, #ff7a59) 22%, transparent);
  }
  .fab:active {
    transform: scale(0.97);
  }
  .fab svg {
    width: 26px;
    height: 26px;
  }
  .fab .ring {
    stroke: var(--rosie-accent, #ff7a59);
  }
  .fab .dot {
    fill: var(--rosie-accent, #ff7a59);
  }
  /* Soft ambient pulse so the assistant reads as "present" but is calm. */
  .pulse {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--rosie-accent, #ff7a59) 50%, transparent);
    animation: rosie-pulse 3.4s var(--rosie-ease) infinite;
    pointer-events: none;
  }
  @keyframes rosie-pulse {
    0% {
      transform: scale(1);
      opacity: 0.7;
    }
    70% {
      transform: scale(1.5);
      opacity: 0;
    }
    100% {
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pulse {
      animation: none;
      display: none;
    }
  }
`;

/** Slide-in panel styles. */
export const panelStyles = css`
  .scrim {
    position: fixed;
    inset: 0;
    background: rgba(4, 8, 16, 0.45);
    backdrop-filter: blur(2px);
    z-index: calc(var(--rosie-z-index) - 1);
    opacity: 0;
    animation: rosie-fade-in var(--rosie-dur) var(--rosie-ease) forwards;
  }
  .panel {
    position: fixed;
    top: 0;
    right: 0;
    height: 100%;
    width: min(420px, 100vw);
    background: var(--rosie-bg);
    border-left: 1px solid var(--rosie-border);
    box-shadow: var(--rosie-shadow);
    z-index: var(--rosie-z-index);
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    animation: rosie-slide-in var(--rosie-dur) var(--rosie-ease) forwards;
  }
  .panel.left {
    right: auto;
    left: 0;
    border-left: none;
    border-right: 1px solid var(--rosie-border);
    transform: translateX(-100%);
    animation-name: rosie-slide-in-left;
  }
  /* Embedded mode: panel + scrim anchor to a positioned ancestor (e.g. a
     story frame or a scoped iframe container) rather than the viewport. */
  .panel.embedded,
  .scrim.embedded {
    position: absolute;
  }
  @keyframes rosie-slide-in {
    to {
      transform: translateX(0);
    }
  }
  @keyframes rosie-slide-in-left {
    to {
      transform: translateX(0);
    }
  }
  @keyframes rosie-fade-in {
    to {
      opacity: 1;
    }
  }
  .header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--rosie-border);
  }
  .header .badge {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--rosie-accent, #ff7a59);
    box-shadow: 0 0 10px var(--rosie-accent, #ff7a59);
    flex: none;
  }
  .header h2 {
    font-size: 14px;
    font-weight: 600;
    margin: 0;
    letter-spacing: 0.01em;
  }
  .header .host {
    font-size: 11px;
    color: var(--rosie-text-dim);
    margin-left: 2px;
  }
  .header .spacer {
    flex: 1;
  }
  .iconbtn {
    background: transparent;
    border: 1px solid transparent;
    color: var(--rosie-text-dim);
    cursor: pointer;
    border-radius: var(--rosie-radius-sm);
    width: 30px;
    height: 30px;
    display: grid;
    place-items: center;
    font-size: 16px;
    line-height: 1;
  }
  .iconbtn:hover {
    color: var(--rosie-text);
    border-color: var(--rosie-border);
    background: var(--rosie-bg-raised);
  }
  .body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .empty {
    margin: auto;
    text-align: center;
    color: var(--rosie-text-dim);
    max-width: 280px;
  }
  .empty .glyph {
    font-size: 30px;
    margin-bottom: 8px;
    color: var(--rosie-accent, #ff7a59);
  }
  .empty code {
    font-family: var(--rosie-mono);
    color: var(--rosie-accent, #ff7a59);
    background: var(--rosie-bg-input);
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 12px;
  }
  .composer {
    border-top: 1px solid var(--rosie-border);
    padding: 12px 14px;
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }
  .composer textarea {
    flex: 1;
    resize: none;
    min-height: 40px;
    max-height: 120px;
    background: var(--rosie-bg-input);
    border: 1px solid var(--rosie-border);
    border-radius: var(--rosie-radius-sm);
    color: var(--rosie-text);
    padding: 10px 12px;
    font-family: var(--rosie-font);
    font-size: 13px;
    line-height: 1.4;
  }
  .composer textarea::placeholder {
    color: var(--rosie-text-faint);
  }
  .composer textarea:focus {
    border-color: var(--rosie-accent, #ff7a59);
    outline: none;
  }
  .send {
    background: var(--rosie-accent, #ff7a59);
    color: #06101c;
    border: none;
    border-radius: var(--rosie-radius-sm);
    height: 40px;
    padding: 0 14px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    flex: none;
  }
  .send:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .hint {
    padding: 0 14px 10px;
    font-size: 11px;
    color: var(--rosie-text-faint);
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .kbd {
    font-family: var(--rosie-mono);
    border: 1px solid var(--rosie-border);
    border-radius: 5px;
    padding: 1px 5px;
    font-size: 10px;
    color: var(--rosie-text-dim);
  }
`;

/** Message-thread and receipt-card styles. */
export const threadStyles = css`
  .msg {
    max-width: 88%;
    padding: 10px 12px;
    border-radius: var(--rosie-radius-sm);
    font-size: 13px;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .msg.user {
    align-self: flex-end;
    background: color-mix(in srgb, var(--rosie-accent, #ff7a59) 18%, var(--rosie-bg-raised));
    border: 1px solid color-mix(in srgb, var(--rosie-accent, #ff7a59) 35%, transparent);
  }
  .msg.assistant {
    align-self: flex-start;
    background: var(--rosie-bg-raised);
    border: 1px solid var(--rosie-border);
  }
  .receipt-card {
    background: var(--rosie-bg-raised);
    border: 1px solid var(--rosie-border);
    border-left: 3px solid var(--rosie-accent, #ff7a59);
    border-radius: var(--rosie-radius-sm);
    padding: 10px 12px;
    font-size: 12px;
  }
  .receipt-card .rc-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .receipt-card .rc-tool {
    font-weight: 600;
    color: var(--rosie-text);
  }
  .receipt-card .rc-type {
    font-size: 10px;
    color: var(--rosie-bg);
    background: var(--rosie-accent, #ff7a59);
    padding: 1px 6px;
    border-radius: 999px;
    font-weight: 600;
  }
  .receipt-card dl {
    margin: 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2px 10px;
  }
  .receipt-card dt {
    color: var(--rosie-text-faint);
  }
  .receipt-card dd {
    margin: 0;
    font-family: var(--rosie-mono);
    color: var(--rosie-text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .receipt-card .verify-ok {
    color: var(--rosie-ok);
  }
  .receipt-card .verify-bad {
    color: var(--rosie-danger);
  }
`;

/** Command-palette styles (rendered inside the panel body). */
export const paletteStyles = css`
  .palette {
    background: var(--rosie-bg-raised);
    border: 1px solid var(--rosie-border-strong);
    border-radius: var(--rosie-radius);
    overflow: hidden;
  }
  .palette input {
    width: 100%;
    background: var(--rosie-bg-input);
    border: none;
    border-bottom: 1px solid var(--rosie-border);
    color: var(--rosie-text);
    padding: 12px 14px;
    font-size: 14px;
    font-family: var(--rosie-font);
  }
  .palette input:focus {
    outline: none;
    border-bottom-color: var(--rosie-accent, #ff7a59);
  }
  .palette ul {
    list-style: none;
    margin: 0;
    padding: 6px;
    max-height: 260px;
    overflow-y: auto;
  }
  .palette li {
    padding: 9px 10px;
    border-radius: var(--rosie-radius-sm);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }
  .palette li[aria-selected='true'] {
    background: color-mix(in srgb, var(--rosie-accent, #ff7a59) 20%, transparent);
  }
  .palette li .pico {
    color: var(--rosie-accent, #ff7a59);
    flex: none;
  }
  .palette li .pdesc {
    color: var(--rosie-text-faint);
    font-size: 11px;
    margin-left: auto;
  }
  .palette .noresults {
    padding: 14px;
    color: var(--rosie-text-faint);
    font-size: 13px;
    text-align: center;
  }
`;

/** Confirm-dialog (modal) styles. */
export const confirmDialogStyles = css`
  .modal-scrim {
    position: fixed;
    inset: 0;
    background: rgba(4, 8, 16, 0.62);
    z-index: calc(var(--rosie-z-index) + 1);
    display: grid;
    place-items: center;
    padding: 18px;
  }
  .modal {
    width: min(440px, 100%);
    background: var(--rosie-bg-raised);
    border: 1px solid var(--rosie-border-strong);
    border-radius: var(--rosie-radius);
    box-shadow: var(--rosie-shadow);
    overflow: hidden;
  }
  .modal header {
    padding: 14px 16px;
    border-bottom: 1px solid var(--rosie-border);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .modal header .warn {
    color: var(--rosie-accent, #ff7a59);
    font-size: 18px;
  }
  .modal header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
  .modal .content {
    padding: 16px;
    font-size: 13px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .modal .kv {
    display: grid;
    grid-template-columns: 84px 1fr;
    gap: 4px 12px;
  }
  .modal .kv .k {
    color: var(--rosie-text-faint);
  }
  .modal .kv .v {
    font-family: var(--rosie-mono);
    word-break: break-all;
  }
  .modal pre {
    margin: 0;
    background: var(--rosie-bg-input);
    border: 1px solid var(--rosie-border);
    border-radius: var(--rosie-radius-sm);
    padding: 10px 12px;
    font-family: var(--rosie-mono);
    font-size: 11px;
    color: var(--rosie-text-dim);
    max-height: 160px;
    overflow: auto;
  }
  .modal .actions {
    display: flex;
    gap: 10px;
    padding: 14px 16px;
    border-top: 1px solid var(--rosie-border);
    justify-content: flex-end;
  }
  .btn {
    border-radius: var(--rosie-radius-sm);
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid var(--rosie-border);
    background: var(--rosie-bg-input);
    color: var(--rosie-text);
  }
  .btn.primary {
    background: var(--rosie-accent, #ff7a59);
    color: #06101c;
    border-color: transparent;
  }
  .btn:hover {
    filter: brightness(1.08);
  }
`;
