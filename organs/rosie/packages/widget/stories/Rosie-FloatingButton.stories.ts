// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7
/**
 * Rosie-FloatingButton — the launcher in all five host accents.
 */
import { html } from 'lit';
import type { Meta, StoryObj } from '@storybook/web-components-vite';
import { RosieFab } from '../src/components/floating-button.js';
import { THEME_ACCENTS, THEME_LABELS, type HostApp } from '../src/styles.js';

// Value-reference so the element's `@customElement` registration is retained.
if (!RosieFab) throw new Error("rosie-fab missing");

const meta: Meta = {
  title: 'Rosie/FloatingButton',
  parameters: { layout: 'fullscreen' },
};
export default meta;
type Story = StoryObj;

const APPS: HostApp[] = ['a11oy', 'amaru', 'sentra', 'vessels', 'rosie'];

export const FiveThemes: Story = {
  name: 'Five themes',
  render: () => html`
    <div
      style="display:flex;gap:28px;flex-wrap:wrap;padding:56px 40px;background:#060b14;min-height:200px;align-items:center;justify-content:center;"
    >
      ${APPS.map(
        (app) => html`
          <div
            style="position:relative;width:120px;height:140px;text-align:center;--rosie-accent:${THEME_ACCENTS[
              app
            ]};"
          >
            <!-- embedded => the fab anchors (bottom-left, 22px) to this tile -->
            <rosie-fab
              embedded
              .position=${'bottom-left'}
              .label=${`Open Rosie for ${THEME_LABELS[app]}`}
            ></rosie-fab>
            <span
              style="position:absolute;top:6px;left:0;right:0;color:#8aa0b8;font:13px system-ui;"
              >${THEME_LABELS[app]}</span
            >
          </div>
        `,
      )}
    </div>
  `,
};
