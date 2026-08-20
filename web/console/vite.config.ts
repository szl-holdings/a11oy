// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The a11oy operator console SPA. In dev, /v1, /healthz and /readyz are proxied
// to a local `a11oy serve` instance (default :8080) so the SPA reads real
// receipts. Override with VITE_A11OY_BASE_URL for a remote substrate.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/v1": "http://127.0.0.1:8080",
      "/healthz": "http://127.0.0.1:8080",
      "/readyz": "http://127.0.0.1:8080",
    },
  },
});
