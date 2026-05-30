// a11oy.vite.config.ts — BLUEPRINT (NEW — none exists in repo)
//
// Founder correction: "a11oy is a full application; vite.config.ts + Dockerfile need
// to be authored." This is the vite config draft. Intended target path in-repo:
//   web/vite.config.ts
//
// DRAFT — DO NOT PUSH. Modeled after the vessels web app config conventions
// (React + Tailwind, dist output, alias to src). Pin plugin versions via the
// pnpm catalog already used in web/package.json (@vitejs/plugin-react, @tailwindcss/vite).
//
// Companion blocker: web/index.html references /src/main.tsx but web/src/ has only
// App.tsx. Author web/src/main.tsx that mounts <App/> into #root, e.g.:
//
//   import { StrictMode } from "react";
//   import { createRoot } from "react-dom/client";
//   import App from "./App";
//   createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
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
