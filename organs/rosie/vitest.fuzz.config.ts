import { defineConfig } from 'vitest/config';

// Dedicated config for property-based fuzz tests (fast-check).
// Kept separate from vitest.config.ts so `npm test` stays fast and
// `npm run test:fuzz` runs only the fuzz suite under fuzz/.
export default defineConfig({
  test: {
    include: ['fuzz/**/*.fuzz.ts'],
    environment: 'node',
    // Property tests can take longer than unit tests; give each room.
    testTimeout: 60_000,
  },
});
