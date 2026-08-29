<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { loadMechIndex } from '@/engine/client'

const counts = ref<Record<string, number> | null>(null)
const source = ref('')

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
      <RouterView />
    </main>
  </div>
</template>
