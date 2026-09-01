// Boots the Python engine inside Pyodide and exposes it to the app.
//
// The engine is the same code the test suite runs — `engine/omnibay/` is copied
// into `public/engine/` at build time, staged into Pyodide's in-memory
// filesystem here, and imported unmodified. There is no second implementation
// of the game math.
//
// Booting costs a couple of seconds, so it is deferred: the mech browser reads
// a precomputed index and never touches this module. Only the mech lab and the
// info view need the engine, and they await `bootEngine()`.

const BASE = import.meta.env.BASE_URL

/**
 * The engine's module list comes from a manifest the bundle builder writes,
 * rather than being repeated here. A hardcoded copy silently omits new modules
 * and fails at import time in the browser.
 */
async function manifest(): Promise<{ modules: string[]; data: string[] }> {
  const response = await fetchOrThrow(`${BASE}engine/manifest.json`)
  const parsed = (await response.json()) as { modules?: string[]; data?: string[] }
  if (!parsed.modules?.length || !parsed.data?.length) {
    throw new EngineError('Engine manifest is incomplete — run `npm run bundle`.')
  }
  return { modules: parsed.modules, data: parsed.data }
}


export type BootPhase = 'idle' | 'runtime' | 'data' | 'indexing' | 'ready' | 'failed'

export interface BootProgress {
  phase: BootPhase
  /** 0–1, for a determinate progress bar. */
  fraction: number
  message: string
}

/** The functions `omnibay.bridge` exposes. Each returns a JSON string. */
interface BridgeModule {
  init(dataDir: string): string
  meta(): string
  list_mechs(): string
  get_mech(reference: string): string
  get_omnipods(reference: string): string
  list_equipment(): string
  stock_build(reference: string): string
  weapon_stats(reference: string, itemId: number, buildJson: string): string
  get_skill_tree(reference: string, buildJson: string): string
  set_skills(reference: string, buildJson: string, selectionJson: string): string
  calculate(reference: string, buildJson: string): string
  export_code(reference: string, buildJson: string): string
  import_code(code: string): string
}

interface Envelope<T> {
  ok: boolean
  data?: T
  error?: string
  detail?: string
}

export class EngineError extends Error {
  constructor(
    message: string,
    readonly detail?: string,
  ) {
    super(message)
    this.name = 'EngineError'
  }
}

let bridge: BridgeModule | null = null
let booting: Promise<BridgeModule> | null = null
let listeners: ((progress: BootProgress) => void)[] = []
let lastProgress: BootProgress = { phase: 'idle', fraction: 0, message: 'Not started' }

export function onBootProgress(listener: (progress: BootProgress) => void): () => void {
  listeners.push(listener)
  listener(lastProgress)
  return () => {
    listeners = listeners.filter((candidate) => candidate !== listener)
  }
}

function report(phase: BootPhase, fraction: number, message: string) {
  lastProgress = { phase, fraction, message }
  for (const listener of listeners) listener(lastProgress)
}

export function engineIsReady(): boolean {
  return bridge !== null
}

/**
 * Start booting without blocking, for views that do not need the engine yet.
 *
 * The browse view is interactive in a fraction of a second while the engine
 * takes several seconds on a first visit, and most visitors browse before they
 * build. Warming it during that window turns the wait into background time.
 * Deferred to idle so it never competes with the first paint.
 */
export function warmEngine(): void {
  if (bridge || booting) return
  const start = () => void bootEngine().catch(() => undefined)
  if ('requestIdleCallback' in window) {
    ;(window as Window & { requestIdleCallback: (cb: () => void, o?: object) => void })
      .requestIdleCallback(start, { timeout: 2000 })
  } else {
    setTimeout(start, 800)
  }
}

/**
 * Boot the engine. Safe to call repeatedly — the first call does the work and
 * every later caller awaits the same promise.
 */
export function bootEngine(): Promise<BridgeModule> {
  if (bridge) return Promise.resolve(bridge)
  if (booting) return booting
  booting = boot().catch((error) => {
    // Let a later call retry rather than caching the failure forever.
    booting = null
    report('failed', 0, error instanceof Error ? error.message : String(error))
    throw error
  })
  return booting
}

async function boot(): Promise<BridgeModule> {
  report('runtime', 0.05, 'Starting Python runtime…')

  // The game data and engine source do not depend on Pyodide, so they download
  // concurrently with the much larger WebAssembly runtime instead of queueing
  // behind it.
  const manifestPromise = manifest()
  const dataPromise = manifestPromise.then((m) =>
    Promise.all(
      m.data.map(async (file) => ({
        file,
        bytes: new Uint8Array(await (await fetchOrThrow(`${BASE}data/${file}`)).arrayBuffer()),
      })),
    ),
  )
  const sourcePromise = manifestPromise.then((m) =>
    Promise.all(
      m.modules.map(async (file) => ({
        file,
        text: await (await fetchOrThrow(`${BASE}engine/omnibay/${file}`)).text(),
      })),
    ),
  )
  manifestPromise.catch(() => undefined)
  // Neither is awaited yet; swallow rejections here so a failure surfaces at
  // the await below rather than as an unhandled promise rejection.
  dataPromise.catch(() => undefined)
  sourcePromise.catch(() => undefined)

  const { loadPyodide } = await import(/* @vite-ignore */ `${BASE}pyodide/pyodide.mjs`)
  const pyodide = await loadPyodide({ indexURL: `${BASE}pyodide/` })

  report('data', 0.6, 'Loading game data…')
  pyodide.FS.mkdir('/data')
  for (const { file, bytes } of await dataPromise) {
    pyodide.FS.writeFile(`/data/${file}`, bytes)
  }

  report('data', 0.7, 'Loading engine…')
  pyodide.FS.mkdir('/engine')
  pyodide.FS.mkdir('/engine/omnibay')
  for (const { file, text } of await sourcePromise) {
    pyodide.FS.writeFile(`/engine/omnibay/${file}`, text)
  }

  report('indexing', 0.75, 'Indexing 1,278 variants…')
  pyodide.runPython(`import sys\nsys.path.insert(0, '/engine')`)
  const module = pyodide.pyimport('omnibay.bridge') as BridgeModule
  unwrap<unknown>(module.init('/data'))

  bridge = module
  report('ready', 1, 'Ready')
  return module
}

async function fetchOrThrow(url: string): Promise<Response> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new EngineError(`Could not load ${url} (${response.status})`)
  }
  return response
}

/** Unpack the bridge's `{ok, data}` envelope, raising on the error case. */
function unwrap<T>(raw: string): T {
  const envelope = JSON.parse(raw) as Envelope<T>
  if (!envelope.ok) {
    throw new EngineError(envelope.error ?? 'Engine error', envelope.detail)
  }
  return envelope.data as T
}

/** Call a bridge function and unwrap the result. */
export async function callEngine<T>(
  invoke: (module: BridgeModule) => string,
): Promise<T> {
  const module = await bootEngine()
  return unwrap<T>(invoke(module))
}

/**
 * Call the engine synchronously. Only valid once `engineIsReady()` is true;
 * used on the hot recalculation path where an await would add a frame.
 */
export function callEngineSync<T>(invoke: (module: BridgeModule) => string): T {
  if (!bridge) throw new EngineError('Engine is not ready yet')
  return unwrap<T>(invoke(bridge))
}
