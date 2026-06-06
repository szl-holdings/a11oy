import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Only include tests written in vitest describe/it format.
    // tests/*.test.ts and src/qec/css_ingress.test.ts are node:assert
    // run-style suites (self-running with process.exit()); they are executed
    // by ci.yml's `test` job via `node --experimental-strip-types`, not here.
    // (css_ingress.test.ts was previously orphaned by the ci.yml glob and is
    // now explicitly included there — keep it out of this vitest include set.)
    include: [
      'test/h0_connectivity.test.ts',
      'tests/server/events.test.ts',
    ],
    environment: 'node',
  },
});
