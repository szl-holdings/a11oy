// The locked CLI belongs to packages/a11oy-knowledge; this historical subtree
// is outside the workspace, so the config must not import a local Vitest module.
export default {
  test: {
    include: ['src/**/*.test.ts', 'packages/**/src/**/*.test.ts'],
    environment: 'node',
  },
};
