<script setup lang="ts">
/** The item following the cursor mid-drag. Teleported so no column clips it. */
import { useEquipmentDrag } from '@/composables/useEquipmentDrag'

const { drag } = useEquipmentDrag()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="drag.active && drag.payload"
      class="ghost mono"
      :class="[`cat-${drag.payload.category}`, { landing: drag.hovered }]"
      :style="{ transform: `translate3d(${drag.x + 12}px, ${drag.y + 12}px, 0)` }"
    >
      <span class="spine" />
      <span class="label">{{ drag.payload.label }}</span>
      <span class="meta faint">{{ drag.payload.slots }}s · {{ drag.payload.tons }}t</span>
    </div>
  </Teleport>
</template>

<style scoped>
.ghost {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 999;
  pointer-events: none;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 7px 3px 0;
  font-size: 10.5px;
  background: var(--bg-raised);
  border: 1px solid var(--border-strong);
  border-radius: 2px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.55);
  opacity: 0.6;
  transition: opacity 0.1s;
}
.ghost.landing {
  opacity: 1;
  border-color: var(--accent);
}
.spine {
  width: 3px;
  align-self: stretch;
  background: var(--tone, var(--c-equipment));
}
.label {
  color: var(--tone, var(--text));
  padding-left: 3px;
}
.meta {
  font-size: 9px;
}

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
</style>
