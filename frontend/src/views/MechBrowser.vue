<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { loadMechIndex } from '@/engine/client'
import { warmEngine } from '@/engine/runtime'
import type { MechSummary } from '@/types'

// The browser reads a precomputed index, so it renders without booting the
// Python engine. Filtering 1,278 records in memory is instant.
const all = ref<MechSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const search = ref('')
const faction = ref('')
const weightClass = ref('')
const omniOnly = ref<'' | 'true' | 'false'>('')

const factions = ref<string[]>([])
const weightClasses = ref<string[]>([])

onMounted(async () => {
  try {
    const index = await loadMechIndex()
    all.value = index.mechs
    factions.value = index.meta.factions
    weightClasses.value = index.meta.weight_classes
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
    // Browsing is the natural window in which to pay the engine's start-up
    // cost, so the mech lab opens without a wait.
    warmEngine()
  }
})

const mechs = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return all.value.filter((mech) => {
    if (needle && !mech.name.toLowerCase().includes(needle) && !mech.chassis.toLowerCase().includes(needle)) return false
    if (faction.value && mech.faction !== faction.value) return false
    if (weightClass.value && mech.weight_class !== weightClass.value) return false
    if (omniOnly.value && mech.is_omnimech !== (omniOnly.value === 'true')) return false
    return true
  })
})

const total = computed(() => mechs.value.length)

const grouped = computed(() => {
  const groups = new Map<string, MechSummary[]>()
  for (const mech of mechs.value) {
    const list = groups.get(mech.weight_class) ?? []
    list.push(mech)
    groups.set(mech.weight_class, list)
  }
  return [...groups.entries()]
})

const HARDPOINTS = ['energy', 'ballistic', 'missile', 'ams', 'ecm'] as const
</script>

<template>
  <div class="browser">
    <div class="filters panel">
      <input v-model="search" type="search" placeholder="Search chassis or variant…" />
      <select v-model="faction">
        <option value="">All factions</option>
        <option v-for="f in factions" :key="f" :value="f">{{ f }}</option>
      </select>
      <select v-model="weightClass">
        <option value="">All weights</option>
        <option v-for="w in weightClasses" :key="w" :value="w">{{ w }}</option>
      </select>
      <select v-model="omniOnly">
        <option value="">All chassis types</option>
        <option value="true">Omnimechs</option>
        <option value="false">Battlemechs</option>
      </select>
      <span class="muted">{{ total }} matching</span>
    </div>

    <p v-if="error" class="danger-text">{{ error }}</p>
    <p v-else-if="loading" class="muted">Loading…</p>

    <section v-for="[weight, list] in grouped" :key="weight" class="group">
      <h2>{{ weight }} <span class="muted">({{ list.length }})</span></h2>
      <div class="grid">
        <article v-for="mech in list" :key="mech.id" class="card panel">
          <header>
            <strong>{{ mech.display_name }}</strong>
            <span class="muted">{{ mech.max_tons }}t</span>
          </header>
          <div class="hardpoints">
            <template v-for="type in HARDPOINTS" :key="type">
              <span v-if="mech.hardpoints[type]" :class="`hp-${type}`">
                {{ mech.hardpoints[type] }}{{ type[0].toUpperCase() }}
              </span>
            </template>
            <span v-if="mech.jump_jets" class="muted">{{ mech.jump_jets }}JJ</span>
          </div>
          <footer>
            <span class="muted tag">{{ mech.is_omnimech ? 'Omni' : mech.faction }}</span>
            <RouterLink :to="`/mechlab/${mech.name}`">Build</RouterLink>
            <RouterLink :to="`/info/${mech.name}`">Info</RouterLink>
          </footer>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  gap: var(--gap);
  align-items: center;
  padding: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filters input[type='search'] {
  min-width: 240px;
}
.group h2 {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  margin: 18px 0 8px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: var(--gap);
}
.card {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.card header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.hardpoints {
  display: flex;
  gap: 8px;
  font-size: 12px;
  font-family: ui-monospace, Menlo, monospace;
  min-height: 16px;
}
.card footer {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  border-top: 1px solid var(--border);
  padding-top: 6px;
}
.tag {
  margin-right: auto;
}
</style>
