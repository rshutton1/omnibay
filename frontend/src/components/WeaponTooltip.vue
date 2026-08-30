<script setup lang="ts">
/**
 * Hover card for a weapon.
 *
 * Shows what the weapon does *on this mech*, not in the abstract: every row
 * that a quirk changed is highlighted and the base value shown alongside, and
 * the effects that did the changing are listed underneath. Values come from the
 * Python engine, so nothing is recomputed here.
 */
import { computed } from 'vue'
import type { ItemTooltip, StatPair } from '@/types.weapon'

const props = defineProps<{
  tooltip: ItemTooltip
  /** Viewport position of the pointer. */
  x: number
  y: number
}>()

/** Card dimensions, used to flip it away from the viewport edges. */
const WIDTH = 268
const ESTIMATED_HEIGHT = 380
const MARGIN = 12

const position = computed(() => {
  const flipLeft = props.x + WIDTH + MARGIN * 2 > window.innerWidth
  const left = flipLeft ? props.x - WIDTH - MARGIN : props.x + MARGIN
  const maxTop = window.innerHeight - ESTIMATED_HEIGHT - MARGIN
  const top = Math.max(MARGIN, Math.min(props.y - 20, Math.max(MARGIN, maxTop)))
  return { left: `${Math.max(MARGIN, left)}px`, top: `${top}px` }
})

/** Narrowed view for the weapon-only sections. */
const weapon = computed(() => (props.tooltip.kind === 'weapon' ? props.tooltip : null))

interface Row {
  label: string
  pair?: StatPair
  text?: string
  places?: number
  suffix?: string
  /** Lower is better, so a decrease should read as an improvement. */
  inverted?: boolean
}

function fmt(value: number, places = 2, suffix = '') {
  return `${value.toFixed(places)}${suffix}`
}

const rows = computed<Row[]>(() => {
  const t = weapon.value
  if (!t) return []
  const out: Row[] = [
    { label: 'Tons', text: String(t.tons) },
    { label: 'Slots', text: String(t.slots) },
    { label: 'Damage', pair: t.damage, places: 2 },
    { label: 'Heat', pair: t.heat, places: 2, inverted: true },
    { label: 'Cooldown', pair: t.cooldown, places: 2, suffix: ' s', inverted: true },
  ]
  if (t.expected_cooldown) {
    out.push({
      label: 'Expected cooldown',
      pair: t.expected_cooldown,
      places: 2,
      suffix: ' s',
      inverted: true,
    })
  }
  if (t.duration) out.push({ label: 'Burn time', pair: t.duration, places: 2, suffix: ' s', inverted: true })
  if (t.min_range) out.push({ label: 'Minimum range', pair: t.min_range, places: 0, suffix: ' m' })
  if (t.optimal_range) out.push({ label: 'Optimal range', pair: t.optimal_range, places: 0, suffix: ' m' })
  if (t.max_range) out.push({ label: 'Max range', pair: t.max_range, places: 0, suffix: ' m' })
  if (t.velocity) out.push({ label: 'Velocity', pair: t.velocity, places: 0, suffix: ' m/s' })
  if (t.spread) out.push({ label: 'Spread', pair: t.spread, places: 2, inverted: true })
  out.push({ label: 'Shots', text: t.shots })
  if (t.shot_interval) out.push({ label: 'Shot interval', text: fmt(t.shot_interval, 2, ' s') })
  if (t.jam_chance) {
    out.push({
      label: 'Jam chance',
      text: `${(t.jam_chance.final * 100).toFixed(1)}%`,
      inverted: true,
    })
  }
  if (t.jam_duration) out.push({ label: 'Jam duration', pair: t.jam_duration, places: 1, suffix: ' s', inverted: true })
  if (t.critical_chance?.length) {
    out.push({
      label: 'Critical chance',
      text: t.critical_chance.map((c) => (c < 0 ? '—' : `${(c * 100).toFixed(1)}%`)).join(' / '),
    })
  }
  return out
})

const rateRows = computed(() => {
  if (!weapon.value) return []
  const r = weapon.value.rates
  const out: Row[] = []
  if (r.dps) out.push({ label: weapon.value.continuous ? 'DPS (sustained)' : 'DPS', pair: r.dps })
  if (r.dph) out.push({ label: 'Damage per heat', pair: r.dph })
  if (r.hps) out.push({ label: 'Heat per second', pair: r.hps, inverted: true })
  return out
})

/** Improved or worsened, accounting for stats where lower is better. */
function toneOf(row: Row): string {
  if (!row.pair?.changed) return ''
  const better = row.inverted ? row.pair.final < row.pair.base : row.pair.final > row.pair.base
  return better ? 'better' : 'worse'
}

function valueOf(row: Row): string {
  if (row.text !== undefined) return row.text
  if (!row.pair) return '—'
  return fmt(row.pair.final, row.places ?? 2, row.suffix ?? '')
}

function baseOf(row: Row): string | null {
  if (!row.pair?.changed) return null
  return fmt(row.pair.base, row.places ?? 2, row.suffix ?? '')
}

/** Formatted like the quirk list, so the same quirk reads the same everywhere. */
function effectValue(value: number): string {
  const percent = value * 100
  return `${percent > 0 ? '+' : ''}${percent.toFixed(1).replace(/\.0$/, '')}%`
}
</script>

<template>
  <Teleport to="body">
    <aside class="tip panel" :class="`cat-${tooltip.category}`" :style="position">
      <header>
        <span class="name">{{ tooltip.name }}</span>
      </header>

      <p v-if="tooltip.description" class="desc faint">{{ tooltip.description }}</p>

      <dl v-if="tooltip.kind === 'equipment'">
        <template v-for="row in tooltip.rows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd class="mono">{{ row.value }}</dd>
        </template>
      </dl>

      <template v-if="tooltip.kind === 'equipment' && tooltip.grants.length">
        <h4>Grants to weapons</h4>
        <dl>
          <template v-for="row in tooltip.grants" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd class="mono better">{{ row.value }}</dd>
          </template>
        </dl>
      </template>

      <dl v-if="weapon">
        <template v-for="row in rows" :key="row.label">
          <dt>{{ row.label }}</dt>
          <dd class="mono" :class="toneOf(row)">
            <s v-if="baseOf(row)" class="was">{{ baseOf(row) }}</s>
            {{ valueOf(row) }}
          </dd>
        </template>
      </dl>

      <template v-if="weapon && rateRows.length">
        <h4>Rates</h4>
        <dl>
          <template v-for="row in rateRows" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd class="mono" :class="toneOf(row)">
              <s v-if="baseOf(row)" class="was">{{ baseOf(row) }}</s>
              {{ valueOf(row) }}
            </dd>
          </template>
        </dl>
      </template>

      <template v-if="weapon && weapon.applied_effects.length">
        <h4>Applied effects</h4>
        <ul class="effects">
          <li v-for="effect in weapon.applied_effects" :key="effect.name">
            <span class="effect-name">{{ effect.name }}</span>
            <span class="effect-what faint">{{ effect.effects.join(', ') }}</span>
            <span class="mono" :class="effect.harmful ? 'worse' : 'better'">
              {{ effectValue(effect.quirk_value) }}
            </span>
          </li>
        </ul>
      </template>

      <!-- Installed equipment that changes this weapon, listed per device. -->
      <template v-for="source in weapon?.equipment_effects ?? []" :key="source.id">
        <h4>{{ source.name }}</h4>
        <ul class="effects">
          <li v-for="effect in source.effects" :key="effect.label" class="equipment">
            <span class="effect-name">{{ effect.label }}</span>
            <span class="mono better">{{ effect.value_text }}</span>
          </li>
        </ul>
      </template>

      <p
        v-if="weapon && !weapon.applied_effects.length && !weapon.equipment_effects.length"
        class="none faint"
      >
        Nothing on this mech modifies this weapon.
      </p>
    </aside>
  </Teleport>
</template>

<style scoped>
.tip {
  position: fixed;
  z-index: 900;
  width: 268px;
  max-height: calc(100vh - 24px);
  overflow-y: auto;
  padding: 0 0 8px;
  pointer-events: none;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
  border-color: var(--border-strong);
}
header {
  padding: 6px 10px;
  background: var(--tone, var(--c-equipment));
  color: #0d1014;
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
h4 {
  margin: 8px 10px 4px;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  border-top: 1px solid var(--border);
  padding-top: 7px;
}
dl {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 1px 10px;
  margin: 7px 10px 0;
  font-size: 10.5px;
}
dt {
  color: var(--text-dim);
}
dd {
  margin: 0;
  text-align: right;
}
/* The pre-quirk value, struck through beside the value in effect. */
.was {
  color: var(--text-faint);
  margin-right: 5px;
  font-size: 9px;
}
.better {
  color: var(--ok);
}
.worse {
  color: var(--warn);
}
.effects {
  list-style: none;
  margin: 0;
  padding: 0 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 9.5px;
}
.effects li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px;
  align-items: baseline;
}
/* Equipment rows have no "which stat" column, so they span it. */
.effects li.equipment {
  grid-template-columns: minmax(0, 1fr) auto;
}
.effect-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.effect-what {
  font-size: 8.5px;
}
.none {
  margin: 8px 10px 0;
  font-size: 10px;
}
.desc {
  margin: 7px 10px 0;
  font-size: 9.5px;
  line-height: 1.35;
}

.cat-weapon-energy { --tone: var(--c-energy); }
.cat-weapon-ballistic { --tone: var(--c-ballistic); }
.cat-weapon-missile { --tone: var(--c-missile); }
.cat-weapon-ams { --tone: var(--c-ams); }
.cat-weapon-other { --tone: var(--c-equipment); }
.cat-ammo { --tone: var(--c-ammo); }
.cat-heatsink { --tone: var(--c-heatsink); }
.cat-engine { --tone: var(--c-engine); }
.cat-jumpjet { --tone: var(--c-jumpjet); }
.cat-masc { --tone: var(--c-masc); }
.cat-equipment { --tone: var(--c-equipment); }
.cat-internal { --tone: var(--c-internal); }
</style>
