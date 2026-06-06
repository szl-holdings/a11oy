// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// Doctrine v7
/**
 * vite.config.ts — library-mode build for `@szl-holdings/rosie-widget`.
 *
 * Outputs an ESM bundle (`rosie-widget.js`) and a UMD bundle
 * (`rosie-widget.umd.cjs`). `lit` is bundled in so a plain `<script
 * type="module">` host gets a self-contained widget; consumers that already
 * use Lit can dedupe at the application layer.
 *
 * The `@szl-holdings/a11oy-receipt-substrate` import is type-only (erased at
 * build), so it never needs resolving at runtime. To keep `tsc` and the editor
 * happy without requiring the package to be published first, a local ambient
 * declaration is aliased in (see tsconfig.json `paths` and
 * `src/types/a11oy-receipt-substrate.d.ts`).
 */

import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'RosieWidget',
      formats: ['es', 'umd'],
      fileName: (format) =>
        format === 'es' ? 'rosie-widget.js' : 'rosie-widget.umd.cjs',
    },
    sourcemap: true,
    // No externals: lit is bundled so the widget drops in without a build step.
    rollupOptions: {},
  },
});
