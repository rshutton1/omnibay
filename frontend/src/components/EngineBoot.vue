<script setup lang="ts">
// Shown while Pyodide starts. The engine is ~6 MB of WebAssembly, so the first
// visit takes a couple of seconds; afterwards it comes from the browser cache.
import { onUnmounted, ref } from 'vue'
import { onBootProgress, type BootProgress } from '@/engine/runtime'

const progress = ref<BootProgress>({ phase: 'idle', fraction: 0, message: '' })
const stop = onBootProgress((value) => (progress.value = value))
onUnmounted(stop)
</script>

<template>
  <div class="boot panel">
    <div class="label">
      <span>{{ progress.message }}</span>
      <span class="muted small">
        {{ progress.phase === 'failed' ? '' : 'Python engine · first load only' }}
      </span>
    </div>
    <div class="bar">
      <div
        class="fill"
        :class="{ failed: progress.phase === 'failed' }"
        :style="{ width: `${Math.round(progress.fraction * 100)}%` }"
      />
    </div>
  </div>
</template>

<style scoped>
.boot {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 420px;
  margin: 40px auto;
}
.label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
}
.small {
  font-size: 11px;
}
.bar {
  height: 4px;
  background: var(--bg-sunken);
  border-radius: 2px;
  overflow: hidden;
}
.fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.25s ease;
}
.fill.failed {
  background: var(--danger);
}
</style>
