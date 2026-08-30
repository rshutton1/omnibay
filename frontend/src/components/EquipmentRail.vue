<script setup lang="ts">
/**
 * The right rail: what you can add.
 *
 * Instead of a destination dropdown, each row shows a chip per component and
 * only lights the ones that can actually take the item right now — the answer
 * to "where does this fit?" is visible before you commit, and installing is a
 * single click on the destination you want.
 */
import { computed, ref } from 'vue'
import type { DragPayload } from '@/composables/useEquipmentDrag'
import type { BuildState, CalcResult, EquipmentItem, UpgradeOption } from '@/types'

const props = defineProps<{
  equipment: EquipmentItem[]
  upgrades: Record<string, UpgradeOption[]>
  build: BuildState
  result: CalcResult
  faction: string
}>()

const emit = defineEmits<{
  (event: 'install', component: string, itemId: number): void
  (event: 'hover-targets', components: string[]): void
  (event: 'lift-item', payload: DragPayload, pointerEvent: PointerEvent): void
  (event: 'set-upgrade', category: 'armor' | 'structure' | 'heatsinks', itemId: number): void
  (event: 'artemis', value: boolean): void
}>()

const CATEGORIES = [
  { value: 'weapon', label: 'Weapons' },
  { value: 'ammo', label: 'Ammo' },
  { value: 'module', label: 'Equipment' },
  { value: 'engine', label: 'Engines' },
  { value: 'jumpjet', label: 'Jump jets' },
  { value: 'masc', label: 'MASC' },
] as const

const UPGRADE_CATEGORIES = [
  { key: 'armor', label: 'Armor' },
  { key: 'structure', label: 'Structure' },
  { key: 'heatsinks', label: 'Heat sinks' },
] as const

const search = ref('')
const category = ref<string>('weapon')

function matchesFaction(item: EquipmentItem): boolean {
  if (!item.faction) return true
  const wanted = props.faction.toLowerCase().replace(/\s/g, '')
  return item.faction
    .toLowerCase()
    .split(',')
    .some((part) => part.replace(/\s/g, '') === wanted)
}

const visible = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return props.equipment
    .filter((item) => item.item_type === category.value)
    .filter(matchesFaction)
    .filter((item) => !needle || item.display_name.toLowerCase().includes(needle))
    .sort((a, b) => a.display_name.localeCompare(b.display_name))
})

/** Ordered so the chips read left to right like the mirrored mech diagram. */
const componentOrder = [
  'right_arm',
  'right_torso',
  'head',
  'centre_torso',
  'left_torso',
  'left_arm',
  'right_leg',
  'left_leg',
]

function fitsIn(item: EquipmentItem, componentName: string): boolean {
  const component = props.result.components[componentName]
  if (!component) return false
  if (component.free_slots < Math.max(1, item.slots)) return false
  if (!item.hardpoint_type) return true
  const capacity = component.hardpoint_capacity[item.hardpoint_type] ?? 0
  const used = component.hardpoints[item.hardpoint_type] ?? 0
  return used < capacity
}

function targetsFor(item: EquipmentItem): string[] {
  return componentOrder.filter((name) => fitsIn(item, name))
}

/** Start a drag out of the catalogue. Clicks on the chips are unaffected. */
function onRowPointerDown(event: PointerEvent, item: EquipmentItem) {
  // Chips are buttons; let them handle their own clicks.
  if ((event.target as HTMLElement).closest('button')) return
  emit(
    'lift-item',
    {
      itemId: item.id,
      label: item.display_name,
      category: item.item_type === 'weapon' && item.hardpoint_type
        ? `weapon-${item.hardpoint_type}`
        : item.item_type,
      slots: item.slots,
      tons: item.tons,
      origin: null,
    },
    event,
  )
}

/** Colour the row by what kind of thing it is, matching the slot grid. */
function toneFor(item: EquipmentItem): string {
  if (item.item_type === 'ammo') return 'cat-ammo'
  if (item.item_type === 'engine') return 'cat-engine'
  if (item.item_type === 'jumpjet') return 'cat-jumpjet'
  if (item.item_type === 'masc') return 'cat-masc'
  if (item.hardpoint_type) return `cat-weapon-${item.hardpoint_type}`
  return 'cat-equipment'
}
</script>

<template>
  <aside class="rail">
    <section class="panel clip catalogue">
      <div class="controls">
        <div class="tabs">
          <button
            v-for="entry in CATEGORIES"
            :key="entry.value"
            :class="{ active: category === entry.value }"
            @click="category = entry.value"
          >
            {{ entry.label }}
          </button>
        </div>
        <input v-model="search" type="search" placeholder="Filter…" />
      </div>

      <ul class="items" @mouseleave="emit('hover-targets', [])">
        <li
          v-for="item in visible"
          :key="item.id"
          :class="[toneFor(item), { draggable: targetsFor(item).length }]"
          @mouseenter="emit('hover-targets', targetsFor(item))"
          @pointerdown="onRowPointerDown($event, item)"
        >
          <div class="row">
            <span class="spine" />
            <span class="name">{{ item.display_name }}</span>
            <span class="stats mono faint">{{ item.slots }}s · {{ item.tons }}t</span>
          </div>
          <div class="targets">
            <button
              v-for="name in componentOrder"
              :key="name"
              class="chip mono"
              :disabled="!fitsIn(item, name)"
              :title="
                fitsIn(item, name)
                  ? `Install in ${result.components[name].label}`
                  : `Will not fit in ${result.components[name].label}`
              "
              @click="emit('install', name, item.id)"
            >
              {{ result.components[name].abbreviation }}
            </button>
          </div>
        </li>
        <li v-if="!visible.length" class="none faint">Nothing matches.</li>
      </ul>
    </section>

    <section class="panel clip upgrades">
      <h3 class="rail-heading">Upgrades</h3>
      <label v-for="entry in UPGRADE_CATEGORIES" :key="entry.key">
        <span class="faint">{{ entry.label }}</span>
        <select
          :value="build.upgrades[entry.key] ?? ''"
          @change="emit('set-upgrade', entry.key, Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="option in upgrades[entry.key] ?? []" :key="option.id" :value="option.id">
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
        <span class="faint">Artemis guidance</span>
      </label>
    </section>
  </aside>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  min-width: 0;
}
.catalogue {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.controls {
  padding: 7px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
.tabs button {
  font-size: 10px;
  padding: 3px 7px;
  color: var(--text-dim);
  background: var(--bg-sunken);
}
.tabs button.active {
  color: var(--accent);
  border-color: var(--accent-dim);
  background: #1e242e;
}
.controls input {
  font-size: 11px;
}

.items {
  list-style: none;
  margin: 0;
  padding: 5px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 620px;
  overflow-y: auto;
}
.items li {
  background: var(--bg-cell);
  border-radius: 2px;
  padding: 4px 5px 5px;
}
.items li.draggable .name {
  cursor: grab;
}
.row {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
}
.spine {
  width: 3px;
  height: 11px;
  border-radius: 2px;
  background: var(--tone, var(--c-equipment));
  flex: none;
}
.name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--tone, var(--text));
}
.stats {
  font-size: 9.5px;
  white-space: nowrap;
}
.targets {
  display: flex;
  gap: 2px;
  margin-top: 3px;
}
.chip {
  flex: 1;
  padding: 1px 0;
  font-size: 8.5px;
  letter-spacing: 0.04em;
  background: var(--bg-sunken);
  border-color: var(--border);
  color: var(--text-faint);
}
.chip:not(:disabled) {
  color: var(--text);
  border-color: var(--border-strong);
  background: #202832;
}
.chip:not(:disabled):hover {
  background: var(--accent);
  border-color: var(--accent);
  color: #12160c;
}
/* Kept legible rather than nearly invisible: a row of dim chips is the answer
   to "where does this fit?" (nowhere), not a rendering failure. */
.chip:disabled {
  opacity: 0.5;
  border-style: dashed;
}
.none {
  background: none;
  font-size: 11px;
}

.cat-weapon-energy { --tone: var(--c-energy); }
.cat-weapon-ballistic { --tone: var(--c-ballistic); }
.cat-weapon-missile { --tone: var(--c-missile); }
.cat-weapon-ams { --tone: var(--c-ams); }
.cat-ammo { --tone: var(--c-ammo); }
.cat-engine { --tone: var(--c-engine); }
.cat-jumpjet { --tone: var(--c-jumpjet); }
.cat-masc { --tone: var(--c-masc); }
.cat-equipment { --tone: var(--c-equipment); }

.upgrades {
  padding: 9px 11px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.upgrades label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}
.upgrades select {
  flex: 1;
  min-width: 0;
  font-size: 10.5px;
  padding: 3px 5px;
}
.check {
  justify-content: flex-start;
  gap: 5px;
}
</style>
