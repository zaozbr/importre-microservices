import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  root: __dirname,
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8767',
      '/aria2': {
        target: 'http://127.0.0.1:6800',
        rewrite: (p) => p.replace(/^\/aria2/, '/jsonrpc'),
      },
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../orchestrator/public'),
    emptyOutDir: true,
  },
});
