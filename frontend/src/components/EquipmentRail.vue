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
  (event: 'hover-weapon', itemId: number | null, x: number, y: number): void
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

/**
 * Shelves within a tab, in MechDB's order. Weapon and ammo shelves are keyed
 * by hardpoint class and only appear when the mech can mount that class, so
 * the list answers "what can this mech carry?" rather than listing the game.
 */
const SHELVES: Record<string, { key: string; label: string; tone: string; hardpoint?: string }[]> = {
  weapon: [
    { key: 'energy', label: 'Energy', tone: 'cat-weapon-energy', hardpoint: 'energy' },
    { key: 'ballistic', label: 'Ballistic', tone: 'cat-weapon-ballistic', hardpoint: 'ballistic' },
    { key: 'missile', label: 'Missile', tone: 'cat-weapon-missile', hardpoint: 'missile' },
    { key: 'ams', label: 'AMS', tone: 'cat-weapon-ams', hardpoint: 'ams' },
  ],
  ammo: [
    { key: 'ballistic', label: 'Ballistic ammo', tone: 'cat-weapon-ballistic', hardpoint: 'ballistic' },
    { key: 'missile', label: 'Missile ammo', tone: 'cat-weapon-missile', hardpoint: 'missile' },
    { key: 'ams', label: 'AMS ammo', tone: 'cat-weapon-ams', hardpoint: 'ams' },
  ],
  module: [
    { key: 'ecm', label: 'ECM', tone: 'cat-ecm' },
    { key: 'sensor', label: 'Sensor', tone: 'cat-equipment' },
    { key: 'misc', label: 'Misc', tone: 'cat-equipment' },
  ],
  engine: [{ key: 'engine', label: 'Engines', tone: 'cat-engine' }],
  jumpjet: [{ key: 'jumpjet', label: 'Jump jets', tone: 'cat-jumpjet' }],
  masc: [{ key: 'masc', label: 'MASC', tone: 'cat-masc' }],
}

function mechHasHardpoint(type: string): boolean {
  return Object.values(props.result.components).some(
    (component) => (component.hardpoint_capacity[type] ?? 0) > 0,
  )
}

const shelves = computed(() => {
  const defs = SHELVES[category.value] ?? [{ key: 'other', label: 'Other', tone: 'cat-equipment' }]
  const byGroup = new Map<string, EquipmentItem[]>()
  for (const item of visible.value) {
    const list = byGroup.get(item.group) ?? []
    list.push(item)
    byGroup.set(item.group, list)
  }
  return defs
    .filter((shelf) => !shelf.hardpoint || mechHasHardpoint(shelf.hardpoint))
    .map((shelf) => ({ ...shelf, items: byGroup.get(shelf.key) ?? [] }))
    .filter((shelf) => shelf.items.length)
})

/** Shelves the user has folded shut. Keyed by tab so folding ammo leaves weapons alone. */
const collapsed = ref(new Set<string>())

function shelfId(key: string): string {
  return `${category.value}:${key}`
}

function toggleShelf(key: string) {
  const id = shelfId(key)
  const next = new Set(collapsed.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  collapsed.value = next
}

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

function onRowHover(event: MouseEvent, item: EquipmentItem) {
  emit('hover-weapon', item.id, event.clientX, event.clientY)
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
      category: item.category,
      slots: item.slots,
      tons: item.tons,
      origin: null,
    },
    event,
  )
}

/** Colour the row by what kind of thing it is, matching the slot grid. */
function toneFor(item: EquipmentItem): string {
  return `cat-${item.category}`
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

      <div class="shelves" @mouseleave="emit('hover-targets', [])">
        <section v-for="shelf in shelves" :key="shelf.key" class="shelf" :class="shelf.tone">
          <button
            class="shelf-head"
            :class="{ folded: collapsed.has(shelfId(shelf.key)) }"
            :aria-expanded="!collapsed.has(shelfId(shelf.key))"
            @click="toggleShelf(shelf.key)"
          >
            <span class="chevron" aria-hidden="true">▾</span>
            <span class="shelf-label">{{ shelf.label }}</span>
            <span class="shelf-count mono">{{ shelf.items.length }}</span>
            <span class="shelf-col mono">slots</span>
            <span class="shelf-col mono">tons</span>
          </button>
          <ul v-show="!collapsed.has(shelfId(shelf.key))" class="items">
            <li
              v-for="item in shelf.items"
              :key="item.id"
              :class="[toneFor(item), { draggable: targetsFor(item).length }]"
              @mouseenter="emit('hover-targets', targetsFor(item))"
              @mousemove="onRowHover($event, item)"
              @mouseleave="emit('hover-weapon', null, 0, 0)"
              @pointerdown="onRowPointerDown($event, item)"
            >
              <div class="row">
                <span class="spine" />
                <span class="name">{{ item.display_name }}</span>
                <span class="stat mono faint">{{ item.slots }}</span>
                <span class="stat mono faint">{{ item.tons }}</span>
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
          </ul>
        </section>
        <p v-if="!shelves.length" class="none faint">
          {{ visible.length ? 'This mech has no hardpoints for these.' : 'Nothing matches.' }}
        </p>
      </div>
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

.shelves {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 5px;
  max-height: 620px;
  overflow-y: auto;
}
/* Solid class-coloured bar with dark text, as MechDB's warehouse headers.
   The columns line up with the slots/tons figures in the rows below. */
.shelf-head {
  width: 100%;
  display: grid;
  grid-template-columns: 10px 1fr auto 30px 34px;
  align-items: center;
  gap: 5px;
  padding: 3px 6px 3px 4px;
  border: none;
  border-radius: 2px;
  background: var(--tone, var(--c-equipment));
  color: var(--c-slot-text-dark);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-align: left;
  cursor: pointer;
}
/* Outranks the global button:hover, which would otherwise dim the bar. */
.shelf-head:hover:not(:disabled) {
  background: var(--tone, var(--c-equipment));
  border: none;
  filter: brightness(1.08);
}
.chevron {
  font-size: 10px;
  line-height: 1;
  transition: transform 0.12s;
}
.shelf-head.folded .chevron {
  transform: rotate(-90deg);
}
.shelf-count {
  font-weight: 400;
  font-size: 9px;
  opacity: 0.7;
}
.shelf-col {
  font-weight: 400;
  font-size: 8.5px;
  letter-spacing: 0;
  text-transform: none;
  text-align: right;
  opacity: 0.75;
}
.items {
  list-style: none;
  margin: 0;
  padding: 3px 0 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
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
.stat {
  font-size: 9.5px;
  white-space: nowrap;
  text-align: right;
  flex: none;
}
.stat:nth-last-child(2) {
  width: 30px;
}
.stat:last-child {
  width: 34px;
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
  margin: 0;
  padding: 6px 4px;
  font-size: 11px;
}


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
