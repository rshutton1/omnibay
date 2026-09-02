<script setup lang="ts">
/**
 * The pilot skill tree.
 *
 * Branches read top to bottom as chains: taking a node takes everything above
 * it, dropping one drops everything below. The engine enforces that and the
 * 91-point cap, so a click can be optimistic without going out of sync.
 */
import { computed, onMounted, ref, watch } from 'vue'
import EngineBoot from '@/components/EngineBoot.vue'
import SkillCanvas from '@/components/SkillCanvas.vue'
import { engineIsReady } from '@/engine/runtime'
import { useMechlabStore } from '@/stores/mechlab'
import type { SkillCategory } from '@/types.skills'

const props = defineProps<{ reference: string }>()
const store = useMechlabStore()

const active = ref<string>('firepower')

async function ensureLoaded() {
  await store.loadMech(props.reference)
  if (!store.skillTree) await store.loadSkillTree()
}

onMounted(ensureLoaded)
watch(() => props.reference, ensureLoaded)

const category = computed(
  () => store.skillTree?.categories.find((c) => c.key === active.value) ?? null,
)

const spent = computed(() => store.build?.skills?.length ?? 0)
const max = computed(() => store.skillTree?.max_points ?? 91)
const remaining = computed(() => max.value - spent.value)

/** Points committed inside a category, for its tab badge. */
function categorySpend(entry: SkillCategory): number {
  return entry.nodes.filter((n) => n.selected).length
}
</script>

<template>
  <EngineBoot v-if="!engineIsReady() && !store.skillTree" />
  <p v-else-if="store.error && !store.skillTree" class="danger-text">{{ store.error }}</p>
  <div v-else-if="store.mech && store.skillTree" class="skills">
    <header class="bar panel clip">
      <div class="identity">
        <h2>{{ store.mech.display_name }}</h2>
        <span class="faint mono">Pilot skills</span>
      </div>

      <div class="readout mono" :class="{ full: remaining === 0 }">
        <strong>{{ spent }} / {{ max }}</strong>
        <span class="faint">points</span>
      </div>
      <div class="budget">
        <div class="track">
          <div class="fill" :style="{ width: `${(spent / max) * 100}%` }" />
        </div>
      </div>

      <div class="actions">
        <RouterLink :to="`/mechlab/${store.mech.name}`">Back to lab</RouterLink>
        <button :disabled="!spent" @click="store.clearSkills()">Clear all</button>
      </div>
    </header>

    <nav class="cats">
      <button
        v-for="entry in store.skillTree.categories"
        :key="entry.key"
        :class="{ active: entry.key === active }"
        @click="active = entry.key"
      >
        {{ entry.name }}
        <span class="count mono">{{ categorySpend(entry) }}</span>
      </button>
    </nav>

    <SkillCanvas
      v-if="category"
      :category="category"
      :remaining="remaining"
      @toggle="(node) => store.toggleSkill(node)"
    />

    <section v-if="store.skillTree.effects.length" class="totals panel clip">
      <h3>Resulting bonuses</h3>
      <dl>
        <template v-for="effect in store.skillTree.effects" :key="effect.name">
          <dt>{{ effect.display_name }}</dt>
          <dd class="mono">{{ effect.value_text }}</dd>
        </template>
      </dl>
    </section>
  </div>
</template>

<style scoped>
.skills {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
}
.bar {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 8px 14px;
  flex-wrap: wrap;
}
.identity {
  margin-right: auto;
}
.identity h2 {
  margin: 0;
  font-size: 19px;
  letter-spacing: 0.04em;
}
.identity span {
  font-size: 10px;
}
.readout {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.1;
}
.readout strong {
  font-size: 16px;
  font-weight: 600;
}
.readout.full strong {
  color: var(--accent);
}
.readout span {
  font-size: 8.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.budget {
  width: 180px;
}
.track {
  height: 4px;
  background: var(--bg-sunken);
  border-radius: 2px;
  overflow: hidden;
}
.fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.15s ease;
}
.actions {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
}

.cats {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
}
.cats button {
  font-size: 11px;
  padding: 5px 12px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.cats button.active {
  color: var(--accent);
  border-color: var(--accent-dim);
  background: #1e242e;
}
.cats .count {
  font-size: 9px;
  opacity: 0.7;
  margin-left: 4px;
}






/* Chain link between consecutive nodes. */











.totals {
  padding: 9px 12px;
}
.totals h3 {
  margin: 0 0 6px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
}
.totals dl {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 1px 14px;
  margin: 0;
  font-size: 10.5px;
}
.totals dt {
  color: var(--text-dim);
}
.totals dd {
  margin: 0 0 0 auto;
  color: var(--ok);
}
</style>
