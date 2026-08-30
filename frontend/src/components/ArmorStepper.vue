<script setup lang="ts">
/**
 * Armor allocation for one face of a component.
 *
 * A range slider is the wrong control here: armor is a whole number you nudge
 * a point or two at a time, and dragging a 200px track to move by 1 is
 * fiddly. This is a typed number with steppers, and holding a stepper repeats
 * — same interaction model as the reference client.
 */
import { computed, onUnmounted, ref } from 'vue'

const props = defineProps<{
  label: string
  value: number
  /** Highest value this face may take, given what the other face holds. */
  max: number
  /** Points still unallocated on this component. */
  available: number
}>()

const emit = defineEmits<{ (event: 'set', value: number): void }>()

// Hold to repeat: a pause before the first repeat so a single click stays a
// single click, then a steady stream.
const HOLD_DELAY_MS = 350
const HOLD_INTERVAL_MS = 90

let holdDelay: ReturnType<typeof setTimeout> | null = null
let holdInterval: ReturnType<typeof setInterval> | null = null

// A pointer press already stepped the value, and the browser will follow it
// with a click. Keyboard activation (Enter/Space) fires click *without* a
// pointer sequence, so click is handled too — this flag stops it double-firing.
let pointerHandled = false
let releaseTimer: ReturnType<typeof setTimeout> | null = null

const editing = ref<string | null>(null)

const canIncrease = computed(() => props.value < props.max)
const canDecrease = computed(() => props.value > 0)

function clamp(value: number): number {
  if (!Number.isFinite(value)) return props.value
  return Math.max(0, Math.min(Math.round(value), props.max))
}

function step(delta: number) {
  const next = clamp(props.value + delta)
  if (next !== props.value) emit('set', next)
  return next !== props.value
}

function stopHold() {
  if (holdDelay) clearTimeout(holdDelay)
  if (holdInterval) clearInterval(holdInterval)
  holdDelay = null
  holdInterval = null
  window.removeEventListener('pointerup', stopHold)
  window.removeEventListener('pointercancel', stopHold)
  // Release the click guard after the browser's synthetic click has passed.
  if (releaseTimer) clearTimeout(releaseTimer)
  releaseTimer = setTimeout(() => {
    pointerHandled = false
  }, 0)
}

/** Keyboard activation only; pointer presses are handled by startHold. */
function onClick(delta: number) {
  if (pointerHandled) return
  step(delta)
}

function startHold(delta: number) {
  stopHold()
  pointerHandled = true
  if (!step(delta)) return

  // End the hold on the window, not the button. Re-rendering after each step
  // perturbs the button's boundary events, and a pointerleave listener would
  // cancel the repeat immediately — as it would for any user whose cursor
  // drifts a pixel while holding.
  window.addEventListener('pointerup', stopHold)
  window.addEventListener('pointercancel', stopHold)

  holdDelay = setTimeout(() => {
    holdInterval = setInterval(() => {
      if (!step(delta)) stopHold()
    }, HOLD_INTERVAL_MS)
  }, HOLD_DELAY_MS)
}

onUnmounted(() => {
  stopHold()
  if (releaseTimer) clearTimeout(releaseTimer)
})

function commit(raw: string) {
  editing.value = null
  const parsed = Number(raw)
  const next = clamp(parsed)
  if (next !== props.value) emit('set', next)
}

/** Arrow keys nudge; the field is a number, so let it behave like one. */
function onKey(event: KeyboardEvent) {
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    step(1)
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    step(-1)
  } else if (event.key === 'Enter') {
    ;(event.target as HTMLInputElement).blur()
  }
}
</script>

<template>
  <div class="armor-row">
    <span class="side faint mono">{{ label }}</span>
    <button
      class="step"
      :disabled="!canDecrease"
      :aria-label="`Decrease ${label} armor`"
      @pointerdown.prevent="startHold(-1)"
      @click="onClick(-1)"
    >
      −
    </button>
    <input
      class="value mono"
      type="number"
      inputmode="numeric"
      :min="0"
      :max="max"
      :value="editing ?? value"
      :aria-label="`${label} armor`"
      @input="editing = ($event.target as HTMLInputElement).value"
      @blur="commit(($event.target as HTMLInputElement).value)"
      @keydown="onKey"
    />
    <button
      class="step"
      :disabled="!canIncrease"
      :aria-label="`Increase ${label} armor`"
      @pointerdown.prevent="startHold(1)"
      @click="onClick(1)"
    >
      +
    </button>
    <span class="avail mono" :class="{ none: available <= 0 }" :title="'Unallocated points'">
      {{ available }}
    </span>
  </div>
</template>

<style scoped>
.armor-row {
  display: grid;
  grid-template-columns: 0.9em 1.15em minmax(0, 1fr) 1.15em 1.7em;
  align-items: center;
  gap: 2px;
  font-size: 10px;
}
.side {
  text-align: center;
}
.step {
  padding: 0;
  height: 15px;
  line-height: 1;
  font-size: 11px;
  background: var(--bg-sunken);
  border-color: var(--border);
  color: var(--text-dim);
  /* Holding to repeat must not start a text selection. */
  user-select: none;
  touch-action: none;
}
.step:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent-dim);
  background: #202832;
}
.step:disabled {
  opacity: 0.3;
}
.value {
  min-width: 0;
  height: 15px;
  padding: 0 2px;
  text-align: center;
  font-size: 10px;
  background: var(--bg-sunken);
  border-color: var(--border);
  /* Spinners duplicate the steppers and steal width. */
  -moz-appearance: textfield;
  appearance: textfield;
}
.value::-webkit-outer-spin-button,
.value::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.avail {
  text-align: right;
  color: var(--text-faint);
}
.avail.none {
  color: var(--accent-dim);
}
</style>
