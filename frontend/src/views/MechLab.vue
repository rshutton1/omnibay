<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DragGhost from '@/components/DragGhost.vue'
import EngineBoot from '@/components/EngineBoot.vue'
import EquipmentRail from '@/components/EquipmentRail.vue'
import SlotColumn from '@/components/SlotColumn.vue'
import StatsRail from '@/components/StatsRail.vue'
import WeaponTooltipCard from '@/components/WeaponTooltip.vue'
import { engineIsReady } from '@/engine/runtime'
import { beginDrag, type DragPayload } from '@/composables/useEquipmentDrag'
import { useWeaponTooltip } from '@/composables/useWeaponTooltip'
import { useMechlabStore } from '@/stores/mechlab'

const props = defineProps<{ reference: string }>()
const store = useMechlabStore()
const router = useRouter()

const codeInput = ref('')
const importError = ref<string | null>(null)
const copied = ref(false)
/** Components an equipment row is currently offering as a destination. */
const targets = ref<string[]>([])

onMounted(() => store.loadMech(props.reference))
watch(
  () => props.reference,
  (reference) => store.loadMech(reference),
)

// Anatomical and mirrored, the way every mech lab draws it: you are facing the
// mech, so its right side is on your left. Arms sit outboard, torsos inboard,
// head centred, legs beneath their own torso side.
const LAYOUT = [
  ['right_arm', 'right_torso', 'head', 'left_torso', 'left_arm'],
  ['', 'right_leg', 'centre_torso', 'left_leg', ''],
]

const hasRearArmor = (name: string) => name.endsWith('_torso')

async function copyCode() {
  const code = await store.exportCode()
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    // Clipboard permission denied; the code is still shown for manual copy.
  }
}

async function importCode() {
  importError.value = null
  const name = await store.importCode(codeInput.value.trim())
  if (name) {
    codeInput.value = ''
    if (name !== props.reference) router.push(`/mechlab/${name}`)
  } else {
    importError.value = store.error
  }
}

// Derived from `used` and `max` rather than read from the engine payload: a
// missing field would otherwise throw during render and blank the page.
const tonnageOverBy = computed(() => {
  const tonnage = store.result?.tonnage
  if (!tonnage) return 0
  return Math.max(0, tonnage.used - tonnage.max)
})

const {
  weaponTooltip,
  showWeaponTooltip,
  hideWeaponTooltip,
  resetWeaponTooltipCache,
} = useWeaponTooltip()

function onHoverWeapon(itemId: number | null, x: number, y: number) {
  if (itemId === null || !store.mech) {
    hideWeaponTooltip()
    return
  }
  showWeaponTooltip(store.mech.name, itemId, store.build, x, y)
}

// Quirks can change with omnipods and upgrades, so cached cards go stale
// whenever the build does.
watch(
  () => store.result,
  () => resetWeaponTooltipCache(),
)

/**
 * Which components could take this payload right now.
 *
 * An item already installed somewhere is being *moved*, so its own component
 * always qualifies (dropping it back is a no-op) and the slots it currently
 * occupies do not count against a move within the same component.
 */
function targetsForPayload(payload: DragPayload): string[] {
  const result = store.result
  if (!result) return []
  const item = store.equipment.find((candidate) => candidate.id === payload.itemId)
  const hardpointType = item?.hardpoint_type ?? ''

  return Object.values(result.components)
    .filter((component) => {
      if (payload.origin?.component === component.name) return true
      if (component.free_slots < Math.max(1, payload.slots)) return false
      if (!hardpointType) return true
      const capacity = component.hardpoint_capacity[hardpointType] ?? 0
      const used = component.hardpoints[hardpointType] ?? 0
      return used < capacity
    })
    .map((component) => component.name)
}

/** Begin dragging, whether from the catalogue or out of a component. */
function onLiftItem(payload: DragPayload, event: PointerEvent) {
  const targets = targetsForPayload(payload)
  if (!targets.length) return
  beginDrag(event, payload, targets, (target, dropped) => {
    if (dropped.origin) {
      if (dropped.origin.component === target) return
      store.moveItem(dropped.origin.component, dropped.origin.index, target)
    } else {
      store.addItem(target, dropped.itemId)
    }
  })
}

const armorPct = computed(() =>
  store.result && store.result.armor.max_points
    ? Math.round((store.result.armor.points / store.result.armor.max_points) * 100)
    : 0,
)
</script>

<template>
  <EngineBoot v-if="!engineIsReady() && !store.result" />
  <div v-else-if="store.loading && !store.result" class="muted">Loading…</div>
  <p v-else-if="store.error && !store.result" class="danger-text">{{ store.error }}</p>

  <div v-else-if="store.mech && store.build && store.result" class="lab">
    <header class="bar panel clip">
      <div class="identity">
        <h2>{{ store.mech.display_name }}</h2>
        <span class="faint mono">
          {{ store.mech.chassis }} · {{ store.mech.max_tons }}t · {{ store.mech.weight_class }} ·
          {{ store.mech.is_omnimech ? 'Omnimech' : store.mech.faction }}
        </span>
      </div>

      <div class="readout mono" :class="{ bad: store.result.tonnage.overweight }">
        <strong>
          {{
            store.result.tonnage.overweight
              ? `+${tonnageOverBy.toFixed(2)}`
              : store.result.tonnage.free.toFixed(2)
          }}
        </strong>
        <span class="faint">{{ store.result.tonnage.overweight ? 'tons OVER' : 'tons free' }}</span>
      </div>
      <div class="readout mono" :class="{ bad: store.result.slots.free < 0 }">
        <strong>{{ store.result.slots.free }}</strong>
        <span class="faint">slots free</span>
      </div>
      <div class="readout mono">
        <strong>{{ armorPct }}%</strong>
        <span class="faint">armor</span>
      </div>
      <div class="readout mono status" :class="store.result.valid ? 'good' : 'bad'">
        <strong>{{ store.result.valid ? 'OK' : 'INVALID' }}</strong>
        <span class="faint">
          {{ store.result.valid ? 'status' : `${store.result.warnings.length} issue${store.result.warnings.length === 1 ? '' : 's'}` }}
        </span>
      </div>

      <div class="actions">
        <RouterLink :to="`/info/${store.mech.name}`">Info</RouterLink>
        <RouterLink :to="`/skills/${store.mech.name}`" class="skills-link">
          Skills<span v-if="store.skillPointsSpent" class="mono"> {{ store.skillPointsSpent }}</span>
        </RouterLink>
        <button @click="store.maximiseArmor()">Max armor</button>
        <button @click="store.stripArmor()">Strip</button>
        <button @click="store.resetToStock()">Stock</button>
        <button class="primary" @click="copyCode()">
          {{ copied ? 'Copied' : 'Copy code' }}
        </button>
      </div>
    </header>

    <ul v-if="store.warnings.length" class="warnings panel clip">
      <li v-for="warning in store.warnings" :key="warning">{{ warning }}</li>
    </ul>

    <div class="workspace">
      <StatsRail :result="store.result" />

      <div class="diagram">
        <div v-for="(row, rowIndex) in LAYOUT" :key="rowIndex" class="row">
          <template v-for="(name, columnIndex) in row" :key="`${rowIndex}-${columnIndex}`">
            <div v-if="!name" class="spacer" />
            <SlotColumn
              v-else
              :component="store.result.components[name]"
              :has-rear-armor="hasRearArmor(name)"
              :targeted="targets.includes(name)"
              @remove-item="(index) => store.removeItem(name, index)"
              @set-armor="(value, rear) => store.setArmor(name, value, rear)"
              @lift-item="onLiftItem"
              @hover-weapon="onHoverWeapon"
            />
          </template>
        </div>

        <div class="code-row panel clip">
          <input
            v-model="codeInput"
            class="mono"
            placeholder="Paste an MWO loadout code to import…"
            @keyup.enter="importCode()"
          />
          <button :disabled="!codeInput.trim()" @click="importCode()">Import</button>
          <code v-if="store.exportedCode" class="mono exported">{{ store.exportedCode }}</code>
          <span v-if="importError" class="danger-text">{{ importError }}</span>
        </div>
      </div>

      <EquipmentRail
        :equipment="store.equipment"
        :upgrades="store.upgrades"
        :build="store.build"
        :result="store.result"
        :faction="store.mech.faction"
        @install="store.addItem"
        @hover-targets="(components) => (targets = components)"
        @lift-item="onLiftItem"
        @hover-weapon="onHoverWeapon"
        @set-upgrade="store.setUpgrade"
        @artemis="store.toggleArtemis"
      />
    </div>

    <DragGhost />
    <WeaponTooltipCard
      v-if="weaponTooltip.tooltip"
      :tooltip="weaponTooltip.tooltip"
      :x="weaponTooltip.x"
      :y="weaponTooltip.y"
    />
  </div>
</template>

<style scoped>
.lab {
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
  display: flex;
  flex-direction: column;
  gap: 1px;
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
  min-width: 58px;
}
.readout strong {
  font-size: 16px;
  font-weight: 600;
}
.readout span {
  font-size: 8.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.readout.bad strong {
  color: var(--danger);
}
.readout.status {
  min-width: 76px;
}
/* An invalid build should register before you read anything. */
.readout.status.bad strong {
  animation: flag 1.1s ease-in-out 3;
}
@keyframes flag {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
@media (prefers-reduced-motion: reduce) {
  .readout.status.bad strong {
    animation: none;
  }
}
.readout.good strong {
  color: var(--ok);
}
.actions {
  display: flex;
  gap: 5px;
  align-items: center;
  font-size: 12px;
}
.skills-link .mono {
  color: var(--accent);
}

.warnings {
  list-style: none;
  margin: 0;
  padding: 7px 14px;
  font-size: 11px;
  color: var(--warn);
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-color: #4a3a1c;
}

.workspace {
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr) 254px;
  gap: var(--gap);
  align-items: start;
}
/* Grid items default to min-width:auto, which would stop the centre column
   shrinking and push the rails off-screen. */
.workspace > * {
  min-width: 0;
}
.diagram {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
}
.row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--gap);
  align-items: start;
}
.row > * {
  min-width: 0;
}
.spacer {
  visibility: hidden;
}

.code-row {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 7px 9px;
  flex-wrap: wrap;
}
.code-row input {
  flex: 1;
  min-width: 220px;
  font-size: 11px;
}
.exported {
  font-size: 10px;
  color: var(--text-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 34ch;
}

@media (max-width: 1400px) {
  .workspace {
    grid-template-columns: 214px minmax(0, 1fr) 236px;
  }
}
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
