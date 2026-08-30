/**
 * Hover state for the weapon detail card.
 *
 * Fetching goes through Pyodide, so results are cached per (mech, weapon,
 * build) and a short hover delay avoids firing a request for every weapon the
 * pointer crosses on its way somewhere else.
 */
import { reactive, readonly } from 'vue'
import { engine } from '@/engine/client'
import { engineIsReady } from '@/engine/runtime'
import type { BuildState } from '@/types'
import type { ItemTooltip } from '@/types.weapon'

/** Pointer must rest on a weapon this long before the card is fetched. */
const HOVER_DELAY_MS = 180

interface TooltipState {
  tooltip: ItemTooltip | null
  x: number
  y: number
}

const state = reactive<TooltipState>({ tooltip: null, x: 0, y: 0 })

let hoverTimer: ReturnType<typeof setTimeout> | null = null
/** Guards against a slow response for a weapon the pointer has already left. */
let requestToken = 0
const cache = new Map<string, ItemTooltip>()

function cancelPending() {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = null
  requestToken += 1
}

export function hideWeaponTooltip() {
  cancelPending()
  state.tooltip = null
}

export function moveWeaponTooltip(x: number, y: number) {
  state.x = x
  state.y = y
}

/** Invalidate cached cards after the build changes, since quirks may differ. */
export function resetWeaponTooltipCache() {
  cache.clear()
  hideWeaponTooltip()
}

export function showWeaponTooltip(
  mech: string,
  itemId: number,
  build: BuildState | null,
  x: number,
  y: number,
) {
  cancelPending()
  state.x = x
  state.y = y
  if (!engineIsReady()) return

  const key = `${mech}:${itemId}`
  const cached = cache.get(key)
  if (cached) {
    state.tooltip = cached
    return
  }

  const token = requestToken
  hoverTimer = setTimeout(() => {
    void engine
      .weaponStats(mech, itemId, build)
      .then((tooltip) => {
        if (token !== requestToken) return
        cache.set(key, tooltip)
        state.tooltip = tooltip
      })
      .catch(() => {
        // A weapon the engine cannot describe simply gets no card.
      })
  }, HOVER_DELAY_MS)
}

export function useWeaponTooltip() {
  return {
    weaponTooltip: readonly(state),
    showWeaponTooltip,
    hideWeaponTooltip,
    moveWeaponTooltip,
    resetWeaponTooltipCache,
  }
}
