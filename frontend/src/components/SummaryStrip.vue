<script setup lang="ts">
import type { CalcResult } from '@/types'

defineProps<{ result: CalcResult }>()
</script>

<template>
  <div class="strip panel">
    <div class="pill" :class="{ bad: result.tonnage.overweight }">
      <strong>{{ result.tonnage.used.toFixed(2) }} / {{ result.tonnage.max }}</strong>
      <span>tons</span>
    </div>
    <div class="pill" :class="{ bad: result.slots.used > result.slots.total }">
      <strong>{{ result.slots.used }} / {{ result.slots.total }}</strong>
      <span>slots</span>
    </div>
    <div class="pill">
      <strong>{{ result.armor.points }} / {{ result.armor.max_points }}</strong>
      <span>armor</span>
    </div>
    <div class="pill">
      <strong>{{ result.firepower.alpha_damage.toFixed(1) }}</strong>
      <span>alpha</span>
    </div>
    <div class="pill">
      <strong>{{ result.heat.alpha_heat.toFixed(1) }}</strong>
      <span>heat</span>
    </div>
    <div class="pill">
      <strong>{{ result.heat.heat_sinks }}{{ result.heat.double ? ' (D)' : '' }}</strong>
      <span>sinks</span>
    </div>
    <div class="pill">
      <strong>{{ result.heat.dissipation.toFixed(2) }}</strong>
      <span>dissipation</span>
    </div>
    <div class="pill">
      <strong>{{ result.engine?.rating ?? '—' }}</strong>
      <span>engine</span>
    </div>
    <div class="pill" :class="result.valid ? 'good' : 'bad'">
      <strong>{{ result.valid ? 'OK' : `${result.warnings.length} issue(s)` }}</strong>
      <span>status</span>
    </div>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  gap: 1px;
  overflow-x: auto;
  background: var(--border);
  padding: 1px;
}
.pill {
  display: flex;
  flex-direction: column;
  padding: 6px 14px;
  background: var(--bg-raised);
  min-width: 92px;
  flex: 1;
}
.pill strong {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 15px;
}
.pill span {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.pill.bad strong {
  color: var(--danger);
}
.pill.good strong {
  color: var(--ok);
}
</style>
