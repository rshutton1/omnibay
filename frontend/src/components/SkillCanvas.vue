<script setup lang="ts">
/**
 * One skill category, drawn the way the game lays it out.
 *
 * The extracted data carries each node's real grid coordinates, so positions
 * are read from them rather than invented: odd columns sit half a row lower,
 * which is what produces the tree's characteristic zigzag as a chain descends.
 * Connectors are drawn behind the nodes from each node to its predecessor.
 */
import { computed } from 'vue'
import type { SkillBranch, SkillCategory, SkillNode } from '@/types.skills'

const props = defineProps<{
  category: SkillCategory
  /** Points still unspent, used to grey out chains that are out of reach. */
  remaining: number
}>()

const emit = defineEmits<{ (event: 'toggle', node: SkillNode, branch: SkillBranch): void }>()

const COLUMN_WIDTH = 88
const ROW_HEIGHT = 78
const NODE_WIDTH = 74
const NODE_HEIGHT = 66
const LABEL_HEIGHT = 26
const PADDING = 14

interface Placed {
  node: SkillNode
  branch: SkillBranch
  x: number
  y: number
  cx: number
  cy: number
}

const columnOrigin = computed(() =>
  Math.min(...props.category.branches.flatMap((b) => b.nodes.map((n) => n.column))),
)

/** Grid coordinates to pixels, with the half-row offset on odd columns. */
function place(node: SkillNode): { x: number; y: number } {
  const x = (node.column - columnOrigin.value) * COLUMN_WIDTH
  const y = (node.row + (node.column % 2 === 1 ? 0.5 : 0)) * ROW_HEIGHT + LABEL_HEIGHT
  return { x, y }
}

const placed = computed<Placed[]>(() =>
  props.category.branches.flatMap((branch) =>
    branch.nodes.map((node) => {
      const { x, y } = place(node)
      return {
        node,
        branch,
        x,
        y,
        cx: x + NODE_WIDTH / 2,
        cy: y + NODE_HEIGHT / 2,
      }
    }),
  ),
)

const byName = computed(() => new Map(placed.value.map((p) => [p.node.name, p])))

/** One connector per chain step, so the branch reads as a path. */
const connectors = computed(() =>
  placed.value
    .filter((entry) => entry.node.requires)
    .map((entry) => {
      const from = byName.value.get(entry.node.requires as string)
      if (!from) return null
      return {
        key: `${from.node.name}->${entry.node.name}`,
        x1: from.cx,
        y1: from.cy,
        x2: entry.cx,
        y2: entry.cy,
        // A link reads as live once the earlier node is taken.
        live: from.node.selected,
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null),
)

/** Branch headings sit above the first node of each chain. */
const labels = computed(() =>
  props.category.branches
    .map((branch) => {
      const first = branch.nodes[0]
      if (!first) return null
      const top = branch.nodes.reduce(
        (best, node) => (place(node).y < place(best).y ? node : best),
        first,
      )
      const { x, y } = place(top)
      const taken = branch.nodes.filter((n) => n.selected).length
      return {
        key: branch.key,
        label: branch.label,
        taken,
        total: branch.nodes.length,
        x: x - 6,
        y: y - LABEL_HEIGHT,
      }
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null),
)

const size = computed(() => ({
  width: Math.max(...placed.value.map((p) => p.x)) + NODE_WIDTH + PADDING * 2,
  height: Math.max(...placed.value.map((p) => p.y)) + NODE_HEIGHT + PADDING * 2,
}))

/** Points a click would spend: the node plus any unselected chain above it. */
function chainCost(node: SkillNode, branch: SkillBranch): number {
  return branch.nodes.filter((n) => n.order <= node.order && !n.selected && n.usable).length
}

/**
 * Four states, because "can I click this" and "is this the next step" are
 * different questions. Any affordable node is clickable — the chain fills in —
 * but the node whose prerequisite is already met is the one to highlight.
 */
function stateOf(node: SkillNode, branch: SkillBranch): string {
  if (!node.usable) return 'gated'
  if (node.selected) return 'selected'
  if (chainCost(node, branch) > props.remaining) return 'nopoints'
  return node.available ? 'next' : 'reachable'
}

/** Short caption inside the hex: the branch name is already above the chain. */
function caption(node: SkillNode, branch: SkillBranch): string {
  return `${branch.label} ${node.order}`
}

function value(node: SkillNode): string {
  if (!node.effects.length) return ''
  if (node.effects.length === 1) return node.effects[0].value_text
  const distinct = new Set(node.effects.map((e) => e.value_text))
  return distinct.size === 1 ? [...distinct][0] : `${node.effects.length}x`
}

function title(node: SkillNode, branch: SkillBranch): string {
  if (!node.usable) return `${node.name} — ${node.blocked_reason}`
  const shown = node.effects.slice(0, 8).map((e) => `${e.display_name} ${e.value_text}`)
  const extra = node.effects.length - shown.length
  if (extra > 0) shown.push(`… and ${extra} more`)
  const cost = chainCost(node, branch)
  const head = cost > 1 ? `${node.name} (${cost} points)` : node.name
  return shown.length ? `${head} — ${shown.join(', ')}` : head
}

function onClick(node: SkillNode, branch: SkillBranch) {
  if (!node.usable) return
  if (!node.selected && chainCost(node, branch) > props.remaining) return
  emit('toggle', node, branch)
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
          v-for="link in connectors"
          :key="link.key"
          :x1="link.x1 + PADDING"
          :y1="link.y1 + PADDING"
          :x2="link.x2 + PADDING"
          :y2="link.y2 + PADDING"
          :class="{ live: link.live }"
        />
      </svg>

      <span
        v-for="label in labels"
        :key="label.key"
        class="branch-label"
        :style="{ left: `${label.x + PADDING}px`, top: `${label.y + PADDING}px` }"
      >
        {{ label.label }}
        <em class="mono">{{ label.taken }}/{{ label.total }}</em>
      </span>

      <button
        v-for="entry in placed"
        :key="entry.node.name"
        class="hex"
        :class="stateOf(entry.node, entry.branch)"
        :style="{
          left: `${entry.x + PADDING}px`,
          top: `${entry.y + PADDING}px`,
          width: `${NODE_WIDTH}px`,
          height: `${NODE_HEIGHT}px`,
        }"
        :title="title(entry.node, entry.branch)"
        @click="onClick(entry.node, entry.branch)"
      >
        <span class="caption">{{ caption(entry.node, entry.branch) }}</span>
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
  /* Category tint, faint enough to read nodes against. */
  background:
    radial-gradient(120% 90% at 20% 0%, color-mix(in srgb, var(--cat) 9%, transparent), transparent 70%),
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
  opacity: 0.75;
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
  padding: 0 9px;
  border: none;
  border-radius: 0;
  background: #1b222c;
  /* The game's node shape. */
  clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
  cursor: pointer;
  transition: background 0.12s, transform 0.08s, filter 0.12s;
}
.hex:hover:not(.gated):not(.nopoints) {
  transform: scale(1.07);
  z-index: 2;
}
.caption {
  font-size: 7.5px;
  line-height: 1.1;
  color: var(--text-faint);
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.value {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}

/* Taken: filled with the category colour. */
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

/* Next up: prerequisite already met, so it reads as the live edge. */
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

/* Further along the same chain: clickable, but not the immediate step. */
.hex.reachable {
  background: #1b222c;
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
