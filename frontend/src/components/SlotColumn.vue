<script setup lang="ts">
/**
 * One component rendered as a column of discrete critical slots.
 *
 * MWO's critical slots are physical cells, so this draws them as cells: every
 * slot is visible, multi-slot equipment is one contiguous block spanning the
 * cells it occupies, and free space is literally empty. A numbered ruler runs
 * down the edge so slot counts can be read off directly rather than inferred
 * from a "10/12" label.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ArmorStepper from '@/components/ArmorStepper.vue'
import { useEquipmentDrag, type DragPayload } from '@/composables/useEquipmentDrag'
import type { ComponentResult, DescribedItem } from '@/types'

const props = defineProps<{
  component: ComponentResult
  hasRearArmor: boolean
  /** Highlights this column while an equipment row offers it as a target. */
  targeted?: boolean
}>()

const emit = defineEmits<{
  (event: 'remove-item', index: number): void
  (event: 'set-armor', value: number, rear: boolean): void
  (event: 'lift-item', payload: DragPayload, pointerEvent: PointerEvent): void
  (event: 'hover-weapon', itemId: number | null, x: number, y: number): void
}>()

const { drag, registerDropZone } = useEquipmentDrag()

// The whole column is the drop zone; register it so the drag layer can hit-test.
const root = ref<HTMLElement | null>(null)
watch(root, (element) => registerDropZone(props.component.name, element))
onBeforeUnmount(() => registerDropZone(props.component.name, null))

const isDropTarget = computed(
  () => drag.active && drag.validTargets.includes(props.component.name),
)
const isHovered = computed(() => drag.active && drag.hovered === props.component.name)
const isRejected = computed(() => drag.active && !isDropTarget.value)

interface Block {
  key: string
  label: string
  category: string
  slots: number
  /** Index into the component's editable item list, if it can be removed. */
  removableIndex: number | null
  detail: string
}

/**
 * Lay the component out top to bottom in the order the game fills it:
 * structural internals, chassis/omnipod fixtures, engine, then player
 * equipment, then whatever floating upgrade slots landed here.
 */
const blocks = computed<Block[]>(() => {
  const component = props.component
  const result: Block[] = []

  component.internals.forEach((item, index) => {
    result.push(toBlock(item, `int-${index}`, Math.max(1, item.slots), null, 'fixed'))
  })

  component.fixed_items.forEach((item, index) => {
    // Centre-torso heat sinks live inside the engine and cost no slots; they
    // are surfaced under the engine block instead.
    if (component.name === 'centre_torso' && item.category === 'heatsink') return
    result.push(toBlock(item, `fix-${index}`, Math.max(1, item.slots), null, item.source || 'fixed'))
  })

  if (component.fixed_engine_slots > 0) {
    result.push({
      key: 'engine-fixed',
      label: 'Engine',
      category: 'engine',
      slots: component.fixed_engine_slots,
      removableIndex: null,
      detail: 'fixed',
    })
  }
  if (component.engine_side_slots > 0) {
    result.push({
      key: 'engine-side',
      label: 'Engine (side)',
      category: 'engine',
      slots: component.engine_side_slots,
      removableIndex: null,
      detail: 'fixed',
    })
  }

  component.items.forEach((item, index) => {
    result.push(toBlock(item, `item-${index}`, Math.max(1, item.slots), index, `${item.tons}t`))
  })

  if (component.occupied_upgrade_slots > 0) {
    result.push({
      key: 'upgrade',
      label: 'Upgrade slots',
      category: 'upgrade',
      slots: component.occupied_upgrade_slots,
      removableIndex: null,
      detail: 'structure / armor',
    })
  }

  return result
})

function toBlock(
  item: DescribedItem,
  key: string,
  slots: number,
  removableIndex: number | null,
  detail: string,
): Block {
  return {
    key,
    label: item.display_name,
    category: item.category,
    slots,
    removableIndex,
    detail,
  }
}

const usedSlots = computed(() => blocks.value.reduce((total, b) => total + b.slots, 0))
const emptySlots = computed(() => Math.max(0, props.component.slot_limit - usedSlots.value))
const overflowing = computed(() => usedSlots.value > props.component.slot_limit)

/** Ruler ticks, one per critical slot. */
const ruler = computed(() =>
  Array.from({ length: props.component.slot_limit }, (_, index) => index + 1),
)

const hardpoints = computed(() =>
  Object.entries(props.component.hardpoint_capacity)
    .filter(([, capacity]) => capacity > 0)
    .map(([type, capacity]) => ({
      type,
      capacity,
      used: props.component.hardpoints[type] ?? 0,
    })),
)

// Front and rear armor draw from one pool, so each caps at what the other leaves.
const unallocatedArmor = computed(() =>
  Math.max(0, props.component.max_armor - props.component.armor - props.component.rear_armor),
)

/** Weapons get a detail card; everything else is self-explanatory. */
function onBlockHover(event: MouseEvent, block: Block) {
  if (!block.category.startsWith('weapon-') || block.removableIndex === null) return
  const item = props.component.items[block.removableIndex]
  if (item) emit('hover-weapon', item.id, event.clientX, event.clientY)
}

/** Installed equipment can be lifted out and dropped into another component. */
function onBlockPointerDown(event: PointerEvent, block: Block) {
  if (block.removableIndex === null) return
  const item = props.component.items[block.removableIndex]
  if (!item) return
  emit(
    'lift-item',
    {
      itemId: item.id,
      label: item.display_name,
      category: item.category,
      slots: item.slots,
      tons: item.tons,
      origin: { component: props.component.name, index: block.removableIndex },
    },
    event,
  )
}

const frontMax = computed(() => props.component.max_armor - props.component.rear_armor)
const rearMax = computed(() => props.component.max_armor - props.component.armor)
const armorTotal = computed(() => props.component.armor + props.component.rear_armor)
const armorPercent = computed(() =>
  props.component.max_armor ? (armorTotal.value / props.component.max_armor) * 100 : 0,
)
const frontShare = computed(() =>
  armorTotal.value ? (props.component.armor / props.component.max_armor) * 100 : 0,
)
</script>

<template>
  <article
    ref="root"
    class="column panel clip"
    :class="{
      targeted,
      over: overflowing,
      'drop-ok': isDropTarget,
      'drop-hover': isHovered,
      'drop-no': isRejected,
    }"
  >
    <header>
      <span class="abbr mono">{{ component.abbreviation }}</span>
      <span class="name">{{ component.label }}</span>
      <span class="hardpoints mono">
        <span v-for="hp in hardpoints" :key="hp.type" :class="`hp-${hp.type}`">
          {{ hp.used }}/{{ hp.capacity }}{{ hp.type.charAt(0).toUpperCase() }}
        </span>
      </span>
    </header>

    <!-- Armor: one bar, front filled solid and rear hatched, against the cap. -->
    <div class="armor">
      <div class="armor-bar" :title="`${armorTotal} of ${component.max_armor}`">
        <div class="armor-fill" :style="{ width: `${armorPercent}%` }" />
        <div class="armor-front" :style="{ width: `${frontShare}%` }" />
      </div>
      <div class="armor-controls">
        <ArmorStepper
          label="F"
          :value="component.armor"
          :max="frontMax"
          :available="unallocatedArmor"
          @set="(value) => emit('set-armor', value, false)"
        />
        <ArmorStepper
          v-if="hasRearArmor"
          label="R"
          :value="component.rear_armor"
          :max="rearMax"
          :available="unallocatedArmor"
          @set="(value) => emit('set-armor', value, true)"
        />
      </div>
    </div>

    <!-- The slot grid. Ruler on the left, blocks on the right. -->
    <div class="grid">
      <div class="ruler mono" aria-hidden="true">
        <span v-for="n in ruler" :key="n" :class="{ free: n > usedSlots }">{{ n }}</span>
      </div>
      <ul class="slots">
        <li
          v-for="block in blocks"
          :key="block.key"
          class="block"
          :class="[`cat-${block.category}`, { removable: block.removableIndex !== null }]"
          :style="{ height: `calc(var(--cell) * ${block.slots})` }"
          :title="`${block.label} — ${block.slots} slot${block.slots === 1 ? '' : 's'}`"
          @pointerdown="onBlockPointerDown($event, block)"
          @mouseenter="onBlockHover($event, block)"
          @mousemove="onBlockHover($event, block)"
          @mouseleave="emit('hover-weapon', null, 0, 0)"
        >
          <span class="spine" />
          <span class="text">
            <span class="label">{{ block.label }}</span>
            <span v-if="block.slots > 1" class="detail faint mono">{{ block.detail }}</span>
          </span>
          <button
            v-if="block.removableIndex !== null"
            class="strip"
            title="Remove"
            @click="emit('remove-item', block.removableIndex)"
          >
            ×
          </button>
        </li>
        <li
          v-for="n in emptySlots"
          :key="`empty-${n}`"
          class="empty"
          :style="{ height: 'var(--cell)' }"
        />
      </ul>
    </div>

    <footer v-if="component.quirks.length" class="quirks mono">
      <span v-for="quirk in component.quirks" :key="quirk.name" class="quirk">
        <span class="faint">{{ quirk.display_name }}</span>
        <span :class="quirk.beneficial === false ? 'warn-text' : 'ok-text'">
          {{ quirk.value_text }}
        </span>
      </span>
    </footer>
  </article>
</template>

<style scoped>
.column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-color: var(--border);
}
.column.targeted {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-dim);
}
.column.over {
  border-color: var(--danger);
}

header {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 5px 7px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-raised);
}
.abbr {
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--accent);
}
.name {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-faint);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hardpoints {
  display: flex;
  gap: 5px;
  font-size: 10px;
}

/* ---- armor ---- */
.armor {
  padding: 5px 7px;
  border-bottom: 1px solid var(--border);
}
.armor-bar {
  position: relative;
  height: 5px;
  background: var(--bg-sunken);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 3px;
}
.armor-fill {
  position: absolute;
  inset: 0 auto 0 0;
  /* Rear armor reads as the hatched remainder of the filled span. */
  background: repeating-linear-gradient(
    -45deg,
    var(--accent-dim) 0 3px,
    transparent 3px 6px
  );
  background-color: #2f3947;
}
.armor-front {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--accent);
}
.armor-controls {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Drag feedback: viable targets lift, the one under the cursor is unmistakable,
   and anything that cannot take the item recedes. */
.column.drop-ok {
  border-color: var(--border-hot);
}
.column.drop-hover {
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent-dim);
}
.column.drop-no {
  opacity: 0.4;
}
.block.removable {
  cursor: grab;
}

/* ---- slot grid ---- */
.grid {
  display: flex;
  gap: 3px;
  padding: 5px 7px 6px;
  flex: 1;
}
.ruler {
  display: flex;
  flex-direction: column;
  font-size: 8px;
  color: var(--text-faint);
  text-align: right;
  width: 1.4em;
  flex: none;
  user-select: none;
}
.ruler span {
  height: var(--cell);
  line-height: var(--cell);
  opacity: 0.75;
}
.ruler span.free {
  opacity: 0.3;
}
.slots {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.block {
  position: relative;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 4px 0 0;
  border-radius: 2px;
  background: var(--bg-cell);
  overflow: hidden;
  font-size: 10.5px;
  min-width: 0;
}
.spine {
  width: 3px;
  align-self: stretch;
  flex: none;
  background: var(--tone, var(--c-equipment));
}
.text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* Top-aligned so a tall multi-slot block still reads from its first row. */
  justify-content: flex-start;
  line-height: 1.15;
  padding: 2px 0 0 3px;
}
.label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--tone, var(--text));
}
.detail {
  font-size: 8.5px;
}
.strip {
  opacity: 0;
  padding: 0 4px;
  font-size: 12px;
  line-height: 1;
  background: none;
  border: none;
  color: var(--text-dim);
  flex: none;
}
.block:hover .strip {
  opacity: 1;
}
.strip:hover {
  color: var(--danger);
  background: none;
}
.empty {
  border: 1px dashed #2b3441;
  border-radius: 2px;
  background: repeating-linear-gradient(
    -45deg,
    rgba(255, 255, 255, 0.012) 0 4px,
    transparent 4px 8px
  );
}

/* Category tones drive both the spine and the label colour. */
.cat-weapon-energy { --tone: var(--c-energy); }
.cat-weapon-ballistic { --tone: var(--c-ballistic); }
.cat-weapon-missile { --tone: var(--c-missile); }
.cat-weapon-ams { --tone: var(--c-ams); }
.cat-ammo { --tone: var(--c-ammo); }
.cat-heatsink { --tone: var(--c-heatsink); }
.cat-engine { --tone: var(--c-engine); }
.cat-jumpjet { --tone: var(--c-jumpjet); }
.cat-masc { --tone: var(--c-masc); }
.cat-equipment { --tone: var(--c-equipment); }
.cat-internal { --tone: var(--c-internal); }
.cat-upgrade { --tone: var(--c-upgrade); }

.cat-internal,
.cat-upgrade {
  background: #151a21;
}
.cat-internal .label,
.cat-upgrade .label {
  color: var(--text-faint);
}

/* ---- quirks ---- */
.quirks {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 8px;
  padding: 4px 7px 5px;
  border-top: 1px solid var(--border);
  font-size: 9px;
}
.quirk {
  display: inline-flex;
  gap: 3px;
}
</style>
