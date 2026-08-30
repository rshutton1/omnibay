<script setup lang="ts">
/**
 * The left rail: what the mech *is*, at a glance.
 *
 * The two numbers a build is always fighting — tonnage and slots — get real
 * meters rather than bare fractions, so being near the limit is visible
 * peripherally instead of requiring you to read and compare digits.
 */
import { computed } from 'vue'
import type { CalcResult } from '@/types'

const props = defineProps<{ result: CalcResult }>()

// Derived rather than read from the payload, for the same reason as in MechLab:
// the render must not depend on a field the engine might not send.
const overBy = computed(() =>
  Math.max(0, props.result.tonnage.used - props.result.tonnage.max),
)

const tonnagePercent = computed(() =>
  props.result.tonnage.max
    ? Math.min(100, (props.result.tonnage.used / props.result.tonnage.max) * 100)
    : 0,
)
const slotPercent = computed(() =>
  props.result.slots.total ? Math.min(100, (props.result.slots.used / props.result.slots.total) * 100) : 0,
)
const armorPercent = computed(() =>
  props.result.armor.max_points
    ? (props.result.armor.points / props.result.armor.max_points) * 100
    : 0,
)

/** Alphas you can fire before the heat scale fills. */
const alphasToOverheat = computed(() => {
  const heat = props.result.heat.alpha_heat
  if (heat <= 0) return null
  return props.result.heat.capacity / heat
})

const general = computed(() => [
  { label: 'Engine', value: props.result.engine ? `${props.result.engine.display_name}` : '—' },
  {
    label: 'Heat sinks',
    value: `${props.result.heat.heat_sinks}${props.result.heat.double ? ' (double)' : ''}`,
  },
  {
    label: 'Jump jets',
    value: `${props.result.jump_jets.installed} / ${props.result.jump_jets.limit}`,
  },
  { label: 'Chassis', value: props.result.mech.is_omnimech ? 'Omnimech' : 'Battlemech' },
])

const firepower = computed(() => [
  { label: 'Alpha damage', value: props.result.firepower.alpha_damage.toFixed(1) },
  { label: 'Alpha heat', value: props.result.heat.alpha_heat.toFixed(1) },
  { label: 'Heat capacity', value: props.result.heat.capacity.toFixed(1) },
  { label: 'Dissipation', value: `${props.result.heat.dissipation.toFixed(2)} /s` },
  {
    label: 'Alphas to overheat',
    value: alphasToOverheat.value === null ? '—' : alphasToOverheat.value.toFixed(1),
  },
  { label: 'Ammo shots', value: String(props.result.firepower.ammo_shots) },
])
</script>

<template>
  <aside class="rail">
    <section class="panel clip meters">
      <div class="meter" :class="{ bad: result.tonnage.overweight }">
        <div class="meter-head">
          <span class="rail-heading">Tonnage</span>
          <span class="mono value">
            {{ result.tonnage.used.toFixed(2) }}<span class="faint"> / {{ result.tonnage.max }}</span>
          </span>
        </div>
        <div class="track"><div class="fill" :style="{ width: `${tonnagePercent}%` }" /></div>
        <div class="split mono" :class="result.tonnage.overweight ? 'danger-text' : 'faint'">
          <template v-if="result.tonnage.overweight">
            over by {{ overBy.toFixed(2) }}t — build is invalid
          </template>
          <template v-else>
            equipment {{ result.tonnage.equipment.toFixed(1) }} · structure
            {{ result.tonnage.structure.toFixed(1) }} · armor {{ result.tonnage.armor.toFixed(1) }}
          </template>
        </div>
      </div>

      <div class="meter" :class="{ bad: result.slots.used > result.slots.total }">
        <div class="meter-head">
          <span class="rail-heading">Critical slots</span>
          <span class="mono value">
            {{ result.slots.used }}<span class="faint"> / {{ result.slots.total }}</span>
          </span>
        </div>
        <div class="track"><div class="fill" :style="{ width: `${slotPercent}%` }" /></div>
      </div>

      <div class="meter">
        <div class="meter-head">
          <span class="rail-heading">Armor</span>
          <span class="mono value">
            {{ result.armor.points }}<span class="faint"> / {{ result.armor.max_points }}</span>
          </span>
        </div>
        <div class="track"><div class="fill armor" :style="{ width: `${armorPercent}%` }" /></div>
      </div>
    </section>

    <section class="panel clip block">
      <h3 class="rail-heading">General</h3>
      <dl>
        <template v-for="row in general" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd class="mono">{{ row.value }}</dd>
        </template>
      </dl>
    </section>

    <section class="panel clip block">
      <h3 class="rail-heading">Firepower &amp; heat</h3>
      <dl>
        <template v-for="row in firepower" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd class="mono">{{ row.value }}</dd>
        </template>
      </dl>
    </section>

    <section v-if="result.quirks.length" class="panel clip block">
      <h3 class="rail-heading">Quirks ({{ result.quirks.length }})</h3>
      <dl class="quirks">
        <template v-for="quirk in result.quirks" :key="quirk.name">
          <dt>{{ quirk.display_name }}</dt>
          <dd
            class="mono"
            :class="
              quirk.beneficial === true
                ? 'ok-text'
                : quirk.beneficial === false
                  ? 'warn-text'
                  : 'faint'
            "
          >
            {{ quirk.value_text }}
          </dd>
        </template>
      </dl>
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
.meters {
  padding: 10px 11px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.meter-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.meter-head .rail-heading {
  margin: 0;
}
.value {
  font-size: 14px;
  font-weight: 600;
}
.meter.bad .value {
  color: var(--danger);
}
.track {
  height: 4px;
  background: var(--bg-sunken);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 4px;
}
.fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.15s ease;
}
.fill.armor {
  background: var(--info);
}
.meter.bad .fill {
  background: var(--danger);
}
.split {
  font-size: 9px;
  margin-top: 4px;
}

.block {
  padding: 9px 11px;
}
.block h3 {
  margin-bottom: 6px;
}
dl {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 2px 8px;
  margin: 0;
  font-size: 10.5px;
}
dt {
  color: var(--text-dim);
}
dd {
  margin: 0;
  text-align: right;
  /* Long values (engine names) wrap rather than truncate the label. */
  overflow-wrap: anywhere;
}
.quirks {
  max-height: 320px;
  overflow-y: auto;
  font-size: 10px;
}
</style>
