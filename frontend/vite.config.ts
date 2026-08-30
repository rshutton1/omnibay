import { execFileSync } from 'node:child_process'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages serves a project site from /<repo>/, so every asset URL needs
// that prefix. Set OMNIBAY_BASE at build time; defaults to '/' for local dev.
const base = process.env.OMNIBAY_BASE ?? '/'

/**
 * Keep the browser's copy of the Python engine in step with its source.
 *
 * The engine is copied into `public/` by the bundle step, which normally runs
 * once before the dev server starts. Vite hot-reloads `.vue` and `.ts` on save
 * but knows nothing about `engine/omnibay/*.py`, so editing Python used to
 * leave a stale engine paired with a fresh UI — a mismatch that surfaced as a
 * confusing runtime failure rather than an obvious error. This re-bundles and
 * reloads whenever the Python changes.
 */
function watchPythonEngine(): Plugin {
  const engineDir = fileURLToPath(new URL('../engine', import.meta.url))
  const bundler = fileURLToPath(new URL('../engine/tools/build_web_bundle.py', import.meta.url))

  return {
    name: 'omnibay:watch-python-engine',
    apply: 'serve',
    configureServer(server) {
      // Chokidar 4 (used by Vite 6) dropped glob support, so this must be a
      // plain directory path rather than a `**/*.py` pattern.
      server.watcher.add(`${engineDir}/omnibay`)
      server.watcher.on('change', (file) => {
        if (!file.startsWith(engineDir) || !file.endsWith('.py')) return
        try {
          execFileSync('python3', [bundler], { stdio: 'pipe' })
          server.config.logger.info(
            `\x1b[32m[omnibay]\x1b[0m re-bundled engine after ${file.split('/').pop()}`,
          )
          server.ws.send({ type: 'full-reload' })
        } catch (error) {
          server.config.logger.error(
            `\x1b[31m[omnibay]\x1b[0m engine bundle failed: ${(error as Error).message}`,
          )
        }
      })
    },
  }
}

export default defineConfig({
  base,
  plugins: [vue(), watchPythonEngine()],
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
