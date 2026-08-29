<script setup lang="ts">
import type { BuildState, UpgradeOption } from '@/types'

defineProps<{
  upgrades: Record<string, UpgradeOption[]>
  build: BuildState
}>()

const emit = defineEmits<{
  (event: 'set', category: 'armor' | 'structure' | 'heatsinks', itemId: number): void
  (event: 'artemis', value: boolean): void
}>()

const CATEGORIES = [
  { key: 'armor', label: 'Armor' },
  { key: 'structure', label: 'Structure' },
  { key: 'heatsinks', label: 'Heat sinks' },
] as const
</script>

<template>
  <div class="upgrades panel">
    <label v-for="category in CATEGORIES" :key="category.key">
      <span>{{ category.label }}</span>
      <select
        :value="build.upgrades[category.key] ?? ''"
        @change="
          emit('set', category.key, Number(($event.target as HTMLSelectElement).value))
        "
      >
        <option v-for="option in upgrades[category.key] ?? []" :key="option.id" :value="option.id">
          {{ option.display_name }}
        </option>
      </select>
    </label>
    <label class="check">
      <input
        type="checkbox"
        :checked="build.upgrades.artemis"
        @change="emit('artemis', ($event.target as HTMLInputElement).checked)"
      />
      <span>Artemis</span>
    </label>
  </div>
</template>

<style scoped>
.upgrades {
  display: flex;
  gap: 12px;
  padding: 8px 10px;
  align-items: center;
  flex-wrap: wrap;
}
label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
label > span {
  color: var(--text-dim);
}
select {
  font-size: 12px;
}
.check {
  gap: 4px;
}
</style>
