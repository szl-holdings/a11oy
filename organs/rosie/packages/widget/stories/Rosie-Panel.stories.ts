// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7
/**
 * Rosie-Panel stories: Empty, Chat, and Execute-Confirm.
 *
 * Each story wraps the panel in a fixed-size frame and uses the panel's
 * `embedded` mode so its (otherwise viewport-fixed) scrim + panel anchor to
 * the frame and are screenshottable. No live api-base is supplied; fixtures
 * are injected once the custom element has upgraded and finished its first
 * render (via `customElements.whenDefined` + `updateComplete`).
 */
import { html } from 'lit';
import { ref } from 'lit/directives/ref.js';
import type { Meta, StoryObj } from '@storybook/web-components-vite';
import { RosieWidgetPanel } from '../src/components/rosie-panel.js';

// Value-reference the element classes so the bundler keeps their
// `@customElement` registration side effects (a bare side-effect import is
// tree-shaken in the Storybook production build).
if (!RosieWidgetPanel) throw new Error("panel missing");
import { RosieApiClient } from '../src/api-client.js';
import { THEME_ACCENTS, type HostApp } from '../src/styles.js';
import { sampleExchanges, sampleAction } from './fixtures.js';

const meta: Meta = {
  title: 'Rosie/Panel',
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj;

/** A frame that anchors the embedded panel and sets the accent. */
function frame(app: HostApp, inner: unknown) {
  return html`
    <div
      style="position:relative;width:480px;height:680px;background:#060b14;overflow:hidden;border:1px solid #1c2740;border-radius:12px;--rosie-accent:${THEME_ACCENTS[
        app
      ]};"
    >
      ${inner}
    </div>
  `;
}

/** A configured client so the empty-state shows the connected copy. */
const liveClient = new RosieApiClient({
  apiBase: 'https://demo.szl.local/api',
  app: 'a11oy',
});

/** Run `fn` once the panel element has upgraded and first-rendered. */
function whenReady(fn: (panel: RosieWidgetPanel) => void) {
  return ref((el?: Element) => {
    if (!el) return;
    customElements.whenDefined('rosie-widget-panel').then(async () => {
      const panel = el as RosieWidgetPanel;
      await panel.updateComplete;
      fn(panel);
    });
  });
}

export const Empty: Story = {
  name: 'Empty',
  render: () =>
    frame(
      'a11oy',
      html`<rosie-widget-panel
        embedded
        .app=${'a11oy' as HostApp}
        .client=${liveClient}
      ></rosie-widget-panel>`,
    ),
};

export const Chat: Story = {
  name: 'Chat',
  render: () =>
    frame(
      'amaru',
      html`<rosie-widget-panel
        embedded
        .app=${'amaru' as HostApp}
        .client=${liveClient}
        ${whenReady((p) => p.seedMessages([...sampleExchanges]))}
      ></rosie-widget-panel>`,
    ),
};

export const ExecuteConfirm: Story = {
  name: 'Execute confirm',
  render: () =>
    frame(
      'sentra',
      html`<rosie-widget-panel
        embedded
        .app=${'sentra' as HostApp}
        .client=${liveClient}
        ${whenReady((p) => {
          p.seedMessages([...sampleExchanges]);
          p.showAction(sampleAction);
        })}
      ></rosie-widget-panel>`,
    ),
};
