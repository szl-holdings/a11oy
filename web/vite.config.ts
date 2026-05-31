// web/vite.config.ts — a11oy web SPA build config.
//
// React + Vite. Aliases the Node built-ins that the real
// `@szl-holdings/a11oy-receipt-substrate` library imports (`node:crypto`,
// `node:fs`) to small browser shims so the verifier runs the SAME hashing and
// chain-verification code in the browser as on the CLI — no reimplementation,
// no mock. The crypto shim is backed by `js-sha3` (SHA3-256/512) and Web Crypto
// (SHA-256). The fs shim is empty: the SPA reads files via the File API / fetch,
// never from disk.
//
// SPDX-License-Identifier: Apache-2.0

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      // Browser shims so the real receipt-substrate library imports unchanged.
      "node:crypto": path.resolve(__dirname, "src/lib/shims/crypto.ts"),
      "node:fs": path.resolve(__dirname, "src/lib/shims/fs.ts"),
    },
  },
  build: {
    // Matches the Dockerfile runner stage: COPY --from=builder /app/web/dist
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  preview: {
    host: "0.0.0.0",
    port: 8080,
  },
});
