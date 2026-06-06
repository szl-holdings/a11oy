// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7
import type { Preview } from '@storybook/web-components-vite';

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: 'szl-navy',
      values: [{ name: 'szl-navy', value: '#060b14' }],
    },
    controls: { expanded: true },
  },
};

export default preview;
