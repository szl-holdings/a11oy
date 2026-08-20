import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/sentra/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@szl-holdings/design-system/tokens/css': path.resolve(__dirname, '../stubs/szl-holdings-design-system/tokens/css.css'),
    },
    dedupe: ['react', 'react-dom'],
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    environment: 'node',
    passWithNoTests: true,
  },
});
