import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages serves a project site from /<repo>/, so every asset URL needs
// that prefix. Set OMNIBAY_BASE at build time; defaults to '/' for local dev.
const base = process.env.OMNIBAY_BASE ?? '/'

export default defineConfig({
  base,
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    // The Pyodide runtime and game data are copied into public/ verbatim; they
    // must not be inlined or hashed.
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1024,
  },
  server: { port: 5173 },
  // Pyodide is loaded at runtime from public/, not bundled.
  optimizeDeps: { exclude: ['pyodide'] },
})
