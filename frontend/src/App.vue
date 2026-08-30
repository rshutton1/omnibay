<script setup lang="ts">
import { onErrorCaptured, onMounted, ref } from 'vue'
import { loadMechIndex } from '@/engine/client'

const counts = ref<Record<string, number> | null>(null)
const source = ref('')

// An error boundary. Without one, a throw during render tears down the tree and
// leaves a blank page with no indication of what happened.
const fatal = ref<string | null>(null)
onErrorCaptured((error) => {
  fatal.value = error instanceof Error ? error.message : String(error)
  console.error('[omnibay] render error', error)
  return false
})

function reload() {
  window.location.reload()
}

onMounted(async () => {
  try {
    const { meta } = await loadMechIndex()
    counts.value = meta.counts
    source.value = meta.generated_from
  } catch {
    // The header stat is decoration; a failure here must not block the app.
  }
})
</script>

<template>
  <div class="app">
    <header class="topbar">
      <h1>Omni<span>Bay</span></h1>
      <nav>
        <RouterLink to="/mechs">Mechs</RouterLink>
      </nav>
      <span v-if="counts" class="muted" style="margin-left: auto; font-size: 12px">
        {{ counts.mechs }} variants · {{ counts.items }} items · {{ source }}
      </span>
    </header>
    <main>
      <section v-if="fatal" class="fatal panel">
        <h2>Something broke</h2>
        <p class="mono">{{ fatal }}</p>
        <p class="muted">
          This is a bug. Reloading usually clears it; if it happens again the message
          above is the useful part.
        </p>
        <button class="primary" @click="fatal = null">Dismiss</button>
        <button @click="reload()">Reload</button>
      </section>
      <RouterView v-else />
    </main>
  </div>
</template>

<style scoped>
.fatal {
  max-width: 640px;
  margin: 48px auto;
  padding: 20px 24px;
  border-color: var(--danger);
}
.fatal h2 {
  margin: 0 0 10px;
  font-size: 16px;
  color: var(--danger);
}
.fatal p {
  margin: 0 0 10px;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.fatal button + button {
  margin-left: 6px;
}
</style>
