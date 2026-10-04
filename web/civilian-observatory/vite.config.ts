import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import fs from "node:fs";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "dependency-chunk-scope",
      generateBundle(_options, bundle) {
        const roots = new Set<string>();
        for (const entry of Object.values(bundle)) {
          if (entry.type !== "chunk" || entry.name !== "dependencies") continue;
          const authored = Object.keys(entry.modules).filter(
            (id) => !id.includes("/node_modules/") && id !== "\0commonjsHelpers.js",
          );
          if (authored.length) this.error("Authored modules entered the dependency-only chunk");
          for (const id of Object.keys(entry.modules)) {
            const marker = "/node_modules/";
            const at = id.lastIndexOf(marker);
            if (at < 0) continue;
            const parts = id.slice(at + marker.length).split("/");
            const packageName = parts.slice(0, parts[0].startsWith("@") ? 2 : 1).join("/");
            roots.add(id.replace(/^\0/, "").slice(0, id.replace(/^\0/, "").lastIndexOf(marker) + marker.length) + packageName);
          }
        }
        for (const font of ["geist", "geist-mono"]) {
          roots.add(path.resolve(import.meta.dirname, "node_modules/@fontsource-variable", font));
        }
        const notices = new Map<string, string>();
        for (const root of roots) {
          const metadata = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
          const licenseFiles = fs.readdirSync(root).filter((name) => /^licen[cs]e(?:[.-].*)?$|^copying(?:[.-].*)?$/i.test(name));
          const fallback = path.resolve(import.meta.dirname, "licenses", `${metadata.name.replaceAll("/", "-")}.txt`);
          const text = licenseFiles.sort().map((name) => fs.readFileSync(path.join(root, name), "utf8")).join("\n") ||
            (fs.existsSync(fallback) ? fs.readFileSync(fallback, "utf8") : "");
          if (!text && metadata.license !== "Unlicense") this.error(`Missing redistribution notice for ${metadata.name}`);
          notices.set(`${metadata.name}@${metadata.version}`, `${metadata.name}@${metadata.version}\nLicense: ${metadata.license}\n\n${text || "The published package declares Unlicense and includes no separate license file."}`);
        }
        this.emitFile({
          type: "asset", fileName: "third-party-notices.txt",
          source: "Redistributed dependency notices for this pinned interface build.\n\n" +
            [...notices.entries()].sort(([a], [b]) => a.localeCompare(b, "en")).map(([, text]) => text.replace(/\r\n?/g, "\n")).join("\n\n========================================\n\n"),
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  root: path.resolve(import.meta.dirname, "client"),
  base: "./",
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Keep dependency-only bytes distinct from authored application claims.
        manualChunks(id) {
          if (id.includes("/node_modules/")) return "dependencies";
        },
      },
    },
  },
  server: {
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
  },
});
