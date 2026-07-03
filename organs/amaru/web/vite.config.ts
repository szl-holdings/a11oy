import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

const vitePort = Number(process.env.VITE_PORT) || 5300;
const basePath = process.env.BASE_PATH || '/';
const apiTarget = process.env.API_TARGET || 'http://localhost:6810';

export default defineConfig({
  base: basePath,
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '@workspace/a11oy-orchestration/client': path.resolve(import.meta.dirname, 'src/_stubs/a11oy-orchestration/index.ts'),
      '@workspace/ouroboros/react': path.resolve(import.meta.dirname, 'src/_stubs/ouroboros-react/index.tsx'),
      '@workspace/ouroboros': path.resolve(import.meta.dirname, 'src/_stubs/ouroboros/index.ts'),
      '@workspace/codex-kernel': path.resolve(import.meta.dirname, 'src/vendor/codex-kernel/index.ts'),
      '@szl-holdings/szl-doctrine/panels': path.resolve(import.meta.dirname, 'src/_stubs/szl-doctrine-panels/index.tsx'),
      '@szl-holdings/szl-doctrine': path.resolve(import.meta.dirname, 'src/_stubs/szl-doctrine/index.ts'),
      '@szl-holdings/shared-ui/ui/badge': path.resolve(import.meta.dirname, 'src/_stubs/shared-ui/badge.tsx'),
      '@szl-holdings/shared-ui/ui/button': path.resolve(import.meta.dirname, 'src/_stubs/shared-ui/button.tsx'),
      '@szl-holdings/shared-ui/ui/card': path.resolve(import.meta.dirname, 'src/_stubs/shared-ui/card.tsx'),
      '@szl-holdings/shared-ui/ui/skeleton': path.resolve(import.meta.dirname, 'src/_stubs/shared-ui/skeleton.tsx'),
      '@szl-holdings/shared-ui/contact-modal': path.resolve(import.meta.dirname, 'src/_stubs/shared-ui/contact-modal.tsx'),
      '@szl-holdings/design-system/tokens/css': path.resolve(import.meta.dirname, 'src/_stubs/design-system/tokens.css'),
    },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist'),
    sourcemap: 'hidden',
    emptyOutDir: true,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks(id): string | undefined {
          if (id.includes('node_modules')) {
            if (id.includes('/recharts/')) return 'vendor-recharts';
            if (id.includes('/d3-')) return 'vendor-d3';
            if (id.includes('framer-motion')) return 'vendor-motion';
            if (id.includes('@tanstack')) return 'vendor-tanstack';
            if (id.includes('lucide-react')) return 'vendor-icons';
            if (id.includes('react-dom')) return 'vendor-react';
            if (id.includes('react/')) return 'vendor-react';
          }
          return undefined;
        },
      },
    },
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'framer-motion',
      'lucide-react',
      '@tanstack/react-query',
      'recharts',
    ],
  },
  server: {
    port: vitePort,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api/amaru': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api\/amaru/, ''),
      },
    },
  },
  preview: {
    port: vitePort,
    host: '0.0.0.0',
    allowedHosts: true,
  },
});
