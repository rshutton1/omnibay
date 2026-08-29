// Vendor the Pyodide runtime into public/ so the deployed site is fully
// self-contained: no CDN dependency, and it works offline once cached.
import { copyFileSync, mkdirSync, existsSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = join(here, '..', 'node_modules', 'pyodide')
const target = join(here, '..', 'public', 'pyodide')

// Only what the browser needs to boot. The .map and .d.ts files are dev-only,
// and the bundled scientific packages are irrelevant — the engine is stdlib.
const FILES = [
  'pyodide.mjs',
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json',
]

mkdirSync(target, { recursive: true })
let total = 0
for (const file of FILES) {
  const from = join(source, file)
  if (!existsSync(from)) {
    console.error(`missing ${file} — run npm install`)
    process.exit(1)
  }
  copyFileSync(from, join(target, file))
  total += statSync(from).size
}
console.log(`pyodide   ${FILES.length} files, ${(total / 1048576).toFixed(1)} MB`)
