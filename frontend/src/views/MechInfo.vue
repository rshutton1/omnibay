<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { engine } from '@/engine/client'
import EngineBoot from '@/components/EngineBoot.vue'
import { engineIsReady } from '@/engine/runtime'
import type { MechDetail, Quirk } from '@/types'

const props = defineProps<{ reference: string }>()

const mech = ref<MechDetail | null>(null)
const error = ref<string | null>(null)
const booting = ref(!engineIsReady())

async function load() {
  error.value = null
  booting.value = !engineIsReady()
  try {
    mech.value = await engine.mech(props.reference)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    booting.value = false
  }
}

onMounted(load)
watch(() => props.reference, load)

const MOVEMENT_ROWS = [
  ['MaxMovementSpeed', 'Top speed factor'],
  ['ReverseSpeedMultiplier', 'Reverse multiplier'],
  ['TorsoTurnSpeedYaw', 'Torso yaw speed'],
  ['TorsoTurnSpeedPitch', 'Torso pitch speed'],
  ['MaxTorsoAngleYaw', 'Torso yaw range'],
  ['MaxTorsoAnglePitch', 'Torso pitch range'],
  ['ArmTurnSpeedYaw', 'Arm yaw speed'],
  ['MaxArmRotationYaw', 'Arm yaw range'],
] as const

// A negative cooldown or heat quirk is a benefit, so colour by the engine's
// classification rather than by the sign of the number.
function quirkClass(quirk: Quirk) {
  if (quirk.beneficial === true) return 'ok-text'
  if (quirk.beneficial === false) return 'warn-text'
  return 'muted'
}

const componentRows = computed(() =>
  mech.value
    ? Object.entries(mech.value.components).map(([name, component]) => ({
        name,
        ...component,
        hardpointSummary: component.hardpoints
          .map((hp) => `${hp.weapon_slots ?? 1}${hp.hardpoint_type[0].toUpperCase()}`)
          .join(' '),
      }))
    : [],
)
</script>

<template>
  <p v-if="error" class="danger-text">{{ error }}</p>
  <EngineBoot v-else-if="booting && !mech" />
  <div v-else-if="mech" class="info">
    <div class="header">
      <div>
        <h2>{{ mech.display_name }}</h2>
        <span class="muted">
          {{ mech.chassis }} · {{ mech.max_tons }}t · {{ mech.weight_class }} ·
          {{ mech.faction }}
        </span>
      </div>
      <RouterLink :to="`/mechlab/${mech.name}`">Open in mech lab</RouterLink>
    </div>

    <div class="columns">
      <section class="panel">
        <h3>Chassis</h3>
        <table>
          <tbody>
            <tr><td>Engine rating</td><td class="mono">{{ mech.engine_range[0] }}–{{ mech.engine_range[1] }}</td></tr>
            <tr><td>Jump jets</td><td class="mono">{{ mech.jump_jets }}</td></tr>
            <tr><td>Chassis type</td><td>{{ mech.is_omnimech ? 'Omnimech' : 'Battlemech' }}</td></tr>
            <tr v-for="[key, label] in MOVEMENT_ROWS" :key="key">
              <td>{{ label }}</td>
              <td class="mono">{{ mech.movement[key] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <h3>Components</h3>
        <table>
          <thead>
            <tr><th>Component</th><th>Slots</th><th>Structure</th><th>Max armor</th><th>Hardpoints</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in componentRows" :key="row.name">
              <td>{{ row.name.replace(/_/g, ' ') }}</td>
              <td class="mono">{{ row.slots }}</td>
              <td class="mono">{{ row.hp }}</td>
              <td class="mono">{{ row.max_armor }}</td>
              <td class="mono">{{ row.hardpointSummary || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <section v-if="mech.quirks.length" class="panel">
      <h3>Stock quirks</h3>
      <table>
        <thead><tr><th>Quirk</th><th>Value</th></tr></thead>
        <tbody>
          <tr v-for="quirk in mech.quirks" :key="quirk.name">
            <td>{{ quirk.display_name }}</td>
            <td class="mono" :class="quirkClass(quirk)">{{ quirk.value_text }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
.header h2 {
  margin: 0;
  font-size: 20px;
}
.columns {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 2fr;
  gap: 12px;
  align-items: start;
}
section {
  padding: 10px 12px;
}
h3 {
  margin: 0 0 8px;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-dim);
}
@media (max-width: 900px) {
  .columns {
    grid-template-columns: 1fr;
  }
}
</style>
