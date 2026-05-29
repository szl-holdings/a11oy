import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  esbuild: {
    tsconfigRaw: {
      compilerOptions: {
        target: 'es2022',
        module: 'esnext',
        moduleResolution: 'bundler',
        esModuleInterop: true,
        strict: true,
        skipLibCheck: true,
        verbatimModuleSyntax: false,
      },
    },
  },
  resolve: {
    alias: {
      '@a11oy/connection': path.resolve(__dirname, '../a11oy-connection/src/index.ts'),
    },
  },
  test: {
    include: ['src/governance/__tests__/lid-check.test.ts'],
  },
});
