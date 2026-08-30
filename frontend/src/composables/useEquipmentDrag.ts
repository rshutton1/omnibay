/**
 * Pointer-driven drag and drop for equipment.
 *
 * Uses Pointer Events rather than HTML5 drag-and-drop: the native API cannot
 * style its drag image, fires no useful events over invalid targets, and
 * behaves inconsistently across browsers for what is essentially an in-page
 * rearrangement. Pointer events give a real ghost, live target highlighting,
 * and touch support for free.
 *
 * A drag only begins after the pointer moves past a small threshold, so a
 * click on an install chip still registers as a click.
 */
import { computed, reactive, readonly } from 'vue'

/** Movement in px before a press becomes a drag rather than a click. */
const DRAG_THRESHOLD = 4

export interface DragPayload {
  itemId: number
  label: string
  category: string
  slots: number
  tons: number
  /** Where it came from, or null when dragged out of the catalogue. */
  origin: { component: string; index: number } | null
}

interface DragState {
  /** Pressed, but not yet past the movement threshold. */
  pending: boolean
  /** Past the threshold — a ghost is visible and drops will land. */
  active: boolean
  payload: DragPayload | null
  x: number
  y: number
  /** Components this payload may legally be dropped into. */
  validTargets: string[]
  /** The component currently under the pointer, if any. */
  hovered: string | null
}

const state = reactive<DragState>({
  pending: false,
  active: false,
  payload: null,
  x: 0,
  y: 0,
  validTargets: [],
  hovered: null,
})

let startX = 0
let startY = 0
let pointerId: number | null = null
let onCommit: ((target: string, payload: DragPayload) => void) | null = null

/** Registered drop zones, keyed by component name. */
const zones = new Map<string, HTMLElement>()

export function registerDropZone(component: string, element: HTMLElement | null) {
  if (element) zones.set(component, element)
  else zones.delete(component)
}

function targetUnder(x: number, y: number): string | null {
  for (const [component, element] of zones) {
    const rect = element.getBoundingClientRect()
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return component
    }
  }
  return null
}

function reset() {
  state.pending = false
  state.active = false
  state.payload = null
  state.validTargets = []
  state.hovered = null
  pointerId = null
  onCommit = null
  document.body.classList.remove('dragging-equipment')
}

function onPointerMove(event: PointerEvent) {
  if (pointerId !== null && event.pointerId !== pointerId) return
  state.x = event.clientX
  state.y = event.clientY

  if (state.pending) {
    const moved = Math.hypot(event.clientX - startX, event.clientY - startY)
    if (moved < DRAG_THRESHOLD) return
    state.pending = false
    state.active = true
    document.body.classList.add('dragging-equipment')
  }

  if (!state.active) return
  const over = targetUnder(event.clientX, event.clientY)
  state.hovered = over && state.validTargets.includes(over) ? over : null
}

function onPointerUp(event: PointerEvent) {
  if (pointerId !== null && event.pointerId !== pointerId) return
  const wasActive = state.active
  const target = state.hovered
  const payload = state.payload
  const commit = onCommit

  detach()
  if (wasActive && target && payload && commit) commit(target, payload)
  reset()
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    detach()
    reset()
  }
}

function attach() {
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
  window.addEventListener('keydown', onKeyDown)
}

function detach() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerUp)
  window.removeEventListener('keydown', onKeyDown)
}

/**
 * Begin a potential drag. Call from `pointerdown`; it becomes a real drag only
 * once the pointer moves far enough, so ordinary clicks are unaffected.
 */
export function beginDrag(
  event: PointerEvent,
  payload: DragPayload,
  validTargets: string[],
  commit: (target: string, payload: DragPayload) => void,
) {
  if (!event.isPrimary || event.button !== 0) return
  reset()
  startX = event.clientX
  startY = event.clientY
  pointerId = event.pointerId
  state.pending = true
  state.payload = payload
  state.x = event.clientX
  state.y = event.clientY
  state.validTargets = validTargets
  onCommit = commit
  attach()
}

export function useEquipmentDrag() {
  return {
    drag: readonly(state),
    isDragging: computed(() => state.active),
    beginDrag,
    registerDropZone,
  }
}
