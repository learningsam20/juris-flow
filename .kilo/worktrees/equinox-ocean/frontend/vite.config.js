import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5274,
    hmr: {
      overlay: false,
    },
    proxy: {
      '/api': { target: 'http://localhost:5273', changeOrigin: true },
      '/media': { target: 'http://localhost:5273', changeOrigin: true },
    },
  },
  test: {
    testTimeout: 15000,
  },
});