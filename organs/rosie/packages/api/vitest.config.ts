import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      // index.ts is the runtime bootstrap (binds a port) and is excluded from
      // unit coverage; it is exercised indirectly via app.ts in tests.
      exclude: ['src/index.ts', 'src/types/**', 'src/lib/env.ts'],
      reporter: ['text', 'json-summary'],
      thresholds: {
        lines: 80,
        statements: 80,
      },
    },
  },
});
