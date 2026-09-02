<script setup lang="ts">
/**
 * One skill category, drawn at the game's own coordinates.
 *
 * Positions and prerequisite links come from the engine, which reads them from
 * `data/skill-graph.json` — the real tree, including the links that cross
 * between branches (Kinetic Burst unlocks Speed Tweak). Nothing about the
 * layout is inferred here; this scales the supplied coordinates and draws them.
 */
import { computed } from 'vue'
import type { SkillCategory, SkillNode } from '@/types.skills'

const props = defineProps<{
  category: SkillCategory
  /** Points still unspent, used to grey out chains that are out of reach. */
  remaining: number
}>()

const emit = defineEmits<{ (event: 'toggle', node: SkillNode): void }>()

/** The source coordinates assume 80px nodes on a 112.5 x 75 grid. */
const SCALE = 0.74
const NODE = 80 * SCALE
const PADDING = 16
const LABEL_SPACE = 46

const nodes = computed(() =>
  props.category.nodes.map((node) => ({
    node,
    x: node.x * SCALE,
    y: node.y * SCALE + LABEL_SPACE,
  })),
)

const positions = computed(() => new Map(nodes.value.map((entry) => [entry.node.name, entry])))

const links = computed(() =>
  props.category.edges
    .map(([from, to]) => {
      const a = positions.value.get(from)
      const b = positions.value.get(to)
      if (!a || !b) return null
      return {
        key: `${from}>${to}`,
        x1: a.x + NODE / 2 + PADDING,
        y1: a.y + NODE / 2 + PADDING,
        x2: b.x + NODE / 2 + PADDING,
        y2: b.y + NODE / 2 + PADDING,
        // A link reads as live once the earlier node is taken.
        live: a.node.selected,
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null),
)

/**
 * Label width, estimated from character count. The font and letter-spacing are
 * uniform, and measurement against rendered labels put this at ~7.4-8.3px per
 * character; the upper end is used so the estimate never runs short and lets a
 * collision through.
 */
function labelWidth(branch: { label: string; taken: number; total: number }): number {
  const text = `${branch.label}${branch.taken}/${branch.total}`.replace(/\s+/g, '')
  return text.length * 8.4
}

const LABEL_HEIGHT = 18
const LABEL_LIFT = 22

function overlaps(
  a: { x: number; y: number; w: number; h: number },
  b: { x: number; y: number; w: number; h: number },
): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
}

/**
 * Branch headings sit above their first node where there is room. Where a tree
 * branches sideways that spot is often taken, so each label searches outward
 * from its ideal position and takes the nearest clear slot. If nothing is clear
 * the heading is dropped rather than drawn over a node — every node already
 * shows its own name, so only the taken/total count is lost.
 */
const labels = computed(() => {
  const nodeRects = nodes.value.map((entry) => ({
    x: entry.x + PADDING,
    y: entry.y + PADDING,
    w: NODE,
    h: NODE,
  }))
  const placed: { x: number; y: number; w: number; h: number }[] = []

  return props.category.branches
    .map((branch) => {
      const w = labelWidth(branch)
      const anchorX = branch.x * SCALE + PADDING - 4
      const anchorY = branch.y * SCALE + LABEL_SPACE + PADDING

      // Offsets ordered by how far they stray from directly-above.
      const candidates: { x: number; y: number; cost: number }[] = []
      for (const dy of [-LABEL_LIFT, -LABEL_LIFT - 21, -LABEL_LIFT - 42, NODE + 6]) {
        for (const dx of [0, NODE + 10, -w - 10, (NODE + 10) * 2, -(w + 10) * 2]) {
          candidates.push({
            x: anchorX + dx,
            y: anchorY + dy,
            cost: Math.abs(dy + LABEL_LIFT) + Math.abs(dx) * 0.6,
          })
        }
      }
      candidates.sort((a, b) => a.cost - b.cost)

      const spot = candidates.find((candidate) => {
        if (candidate.x < 0) return false
        const rect = { x: candidate.x, y: candidate.y, w, h: LABEL_HEIGHT }
        return (
          !nodeRects.some((node) => overlaps(rect, node)) &&
          !placed.some((other) => overlaps(rect, other))
        )
      })
      if (!spot) return null

      placed.push({ x: spot.x, y: spot.y, w, h: LABEL_HEIGHT })
      return { ...branch, left: spot.x, top: spot.y }
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
})

const size = computed(() => {
  const base = {
    width: props.category.width * SCALE + NODE + PADDING * 2,
    height: props.category.height * SCALE + NODE + LABEL_SPACE + PADDING * 2,
  }
  // A label pushed sideways can reach past the rightmost node.
  const widest = Math.max(base.width, ...labels.value.map((l) => l.left + labelWidth(l) + PADDING))
  return { width: widest, height: base.height }
})

/**
 * Four states, because "can I click this" and "is this the next step" are
 * different questions. Any affordable node is clickable — its prerequisites
 * come along — but the one whose prerequisite is already met is the live edge.
 */
function stateOf(node: SkillNode): string {
  if (!node.usable) return 'gated'
  if (node.selected) return 'selected'
  if (node.cost > props.remaining) return 'nopoints'
  return node.available ? 'next' : 'reachable'
}

function value(node: SkillNode): string {
  if (!node.effects.length) return ''
  if (node.effects.length === 1) return node.effects[0].value_text
  const distinct = new Set(node.effects.map((e) => e.value_text))
  return distinct.size === 1 ? [...distinct][0] : `${node.effects.length}x`
}

function title(node: SkillNode): string {
  if (!node.usable) return `${node.label} — ${node.blocked_reason}`
  const shown = node.effects.slice(0, 8).map((e) => `${e.display_name} ${e.value_text}`)
  const extra = node.effects.length - shown.length
  if (extra > 0) shown.push(`… and ${extra} more`)
  const head = node.selected
    ? node.label
    : node.cost > 1
      ? `${node.label} (${node.cost} points)`
      : node.label
  return shown.length ? `${head} — ${shown.join(', ')}` : head
}

function onClick(node: SkillNode) {
  if (!node.usable) return
  if (!node.selected && node.cost > props.remaining) return
  emit('toggle', node)
}
</script>

<template>
  <div class="canvas-scroll">
    <div
      class="canvas"
      :class="`cat-${category.key}`"
      :style="{ width: `${size.width}px`, height: `${size.height}px` }"
    >
      <svg class="links" :width="size.width" :height="size.height" aria-hidden="true">
        <line
          v-for="link in links"
          :key="link.key"
          :x1="link.x1"
          :y1="link.y1"
          :x2="link.x2"
          :y2="link.y2"
          :class="{ live: link.live }"
        />
      </svg>

      <span
        v-for="branch in labels"
        :key="branch.label"
        class="branch-label"
        :style="{ left: `${branch.left}px`, top: `${branch.top}px` }"
      >
        {{ branch.label }}
        <em class="mono">{{ branch.taken }}/{{ branch.total }}</em>
      </span>

      <button
        v-for="entry in nodes"
        :key="entry.node.name"
        class="hex"
        :class="stateOf(entry.node)"
        :style="{
          left: `${entry.x + PADDING}px`,
          top: `${entry.y + PADDING}px`,
          width: `${NODE}px`,
          height: `${NODE}px`,
        }"
        :title="title(entry.node)"
        @click="onClick(entry.node)"
      >
        <span class="caption">{{ entry.node.label }}</span>
        <span class="value mono">{{ value(entry.node) }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.canvas-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 6px;
}
.canvas {
  position: relative;
  background:
    radial-gradient(120% 90% at 15% 0%, color-mix(in srgb, var(--cat) 9%, transparent), transparent 70%),
    var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  --cat: var(--accent);
}
.cat-firepower { --cat: #e8a33d; }
.cat-survival { --cat: #7fd18b; }
.cat-mobility { --cat: #5ec8f2; }
.cat-jumpjets { --cat: #b493e6; }
.cat-operations { --cat: #6f9fe0; }
.cat-sensors { --cat: #f2789a; }
.cat-auxiliary { --cat: #57c9b8; }

.links {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.links line {
  stroke: #2b3441;
  stroke-width: 2;
}
.links line.live {
  stroke: var(--cat);
  opacity: 0.8;
}

.branch-label {
  position: absolute;
  font-size: 8.5px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--text-dim);
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 2px 6px;
  white-space: nowrap;
  pointer-events: none;
  z-index: 3;
}
.branch-label em {
  font-style: normal;
  color: var(--text-faint);
  margin-left: 4px;
  font-size: 8px;
}

.hex {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  padding: 0 7px;
  border: none;
  border-radius: 0;
  background: #1b222c;
  /* The game's node shape. */
  clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
  cursor: pointer;
  transition: background 0.12s, transform 0.08s;
}
.hex:hover:not(.gated):not(.nopoints) {
  transform: scale(1.08);
  z-index: 2;
}
.caption {
  font-size: 7px;
  line-height: 1.05;
  color: var(--text-faint);
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.value {
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}

.hex.selected {
  background: color-mix(in srgb, var(--cat) 30%, #10141a);
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--cat) 45%, transparent));
}
.hex.selected .value {
  color: color-mix(in srgb, var(--cat) 88%, white);
}
.hex.selected .caption {
  color: color-mix(in srgb, var(--cat) 65%, var(--text));
}

.hex.next {
  background: #262f3b;
  filter: drop-shadow(0 0 3px color-mix(in srgb, var(--cat) 30%, transparent));
}
.hex.next .caption {
  color: var(--text-dim);
}
.hex.next:hover {
  background: color-mix(in srgb, var(--cat) 20%, #262f3b);
}

.hex.reachable .value {
  color: var(--text-dim);
}
.hex.reachable:hover {
  background: color-mix(in srgb, var(--cat) 14%, #1b222c);
}

.hex.nopoints {
  opacity: 0.4;
  cursor: not-allowed;
}
.hex.gated {
  opacity: 0.2;
  cursor: not-allowed;
}
</style>
