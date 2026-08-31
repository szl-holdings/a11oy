import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["a11oy-core/tests/**/*.test.ts", "formulas/tests/**/*.test.ts"],
    root: ".",
  },
});
