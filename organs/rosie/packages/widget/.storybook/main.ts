// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7
import type { StorybookConfig } from '@storybook/web-components-vite';

const config: StorybookConfig = {
  stories: ['../stories/**/*.stories.ts'],
  framework: {
    name: '@storybook/web-components-vite',
    options: {},
  },
  core: { disableTelemetry: true },
  // The `@customElement` decorator registers an element as a module side
  // effect. Tell Rollup to treat every widget source module as having side
  // effects so production minification never drops those registrations.
  viteFinal: async (cfg) => {
    cfg.build = cfg.build ?? {};
    cfg.build.rollupOptions = cfg.build.rollupOptions ?? {};
    cfg.build.rollupOptions.treeshake = {
      moduleSideEffects: (id: string) =>
        id.includes('/src/components/') || id.endsWith('/src/rosie-widget.ts'),
    };
    return cfg;
  },
};

export default config;
