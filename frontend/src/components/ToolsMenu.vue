<script setup lang="ts">
/**
 * Whole-build operations behind one button, so the header stays a header.
 *
 * Closes on outside click, Escape, or picking an item. Arrow keys walk the
 * list so it behaves like a menu rather than a pile of buttons.
 *
 * The list is teleported to <body> and positioned under the button: the
 * header panel is clip-path'd for its cut corner, which would clip anything
 * that hangs below it.
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

export interface ToolAction {
  key: string;
  label: string;
  hint?: string;
  /** Visually separates this item from the one above. */
  divider?: boolean;
  run: () => void | Promise<void>;
}

defineProps<{ actions: ToolAction[] }>();

const open = ref(false);
const root = ref<HTMLElement | null>(null);
const list = ref<HTMLElement | null>(null);
const anchor = ref({ top: 0, right: 0 });

function place() {
  const rect = root.value?.getBoundingClientRect();
  // Right-aligned to the button: it lives at the header's right edge.
  if (rect) anchor.value = { top: rect.bottom + 4, right: window.innerWidth - rect.right };
}

function itemsIn(): HTMLElement[] {
  return list.value
    ? Array.from(list.value.querySelectorAll<HTMLElement>('[role="menuitem"]'))
    : [];
}

async function toggle() {
  open.value = !open.value;
  if (open.value) {
    place();
    await nextTick();
    itemsIn()[0]?.focus();
  }
}

function close(refocus = false) {
  if (!open.value) return;
  open.value = false;
  if (refocus) root.value?.querySelector<HTMLElement>("button")?.focus();
}

async function pick(action: ToolAction) {
  close(true);
  await action.run();
}

function onKeydown(event: KeyboardEvent) {
  if (!open.value) return;
  const items = itemsIn();
  const index = items.indexOf(document.activeElement as HTMLElement);
  if (event.key === "Escape") {
    event.preventDefault();
    close(true);
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    items[(index + 1) % items.length]?.focus();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    items[(index - 1 + items.length) % items.length]?.focus();
  }
}

function onPointerDown(event: PointerEvent) {
  const target = event.target as Node;
  if (
    open.value &&
    !root.value?.contains(target) &&
    !list.value?.contains(target)
  )
    close();
}

function onViewportChange() {
  if (open.value) close();
}

onMounted(() => {
  document.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("resize", onViewportChange);
  window.addEventListener("scroll", onViewportChange, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onPointerDown);
  window.removeEventListener("resize", onViewportChange);
  window.removeEventListener("scroll", onViewportChange, true);
});
</script>

<template>
  <div ref="root" class="tools" @keydown="onKeydown">
    <button
      :aria-expanded="open"
      aria-haspopup="menu"
      :class="{ open }"
      @click="toggle()"
    >
      Tools <span class="caret" aria-hidden="true">▾</span>
    </button>
    <Teleport to="body">
      <ul
        v-if="open"
        ref="list"
        class="menu panel"
        role="menu"
        :style="{ top: `${anchor.top}px`, right: `${anchor.right}px` }"
        @keydown="onKeydown"
      >
        <li
          v-for="action in actions"
          :key="action.key"
          role="menuitem"
          tabindex="-1"
          :class="{ divider: action.divider }"
          @click="pick(action)"
          @keydown.enter.prevent="pick(action)"
          @keydown.space.prevent="pick(action)"
        >
          <span>{{ action.label }}</span>
          <span v-if="action.hint" class="hint faint">{{ action.hint }}</span>
        </li>
      </ul>
    </Teleport>
  </div>
</template>

<style scoped>
.tools {
  position: relative;
}
.tools > button.open {
  border-color: var(--border-hot);
  background: #1d2530;
}
.caret {
  font-size: 9px;
  margin-left: 2px;
}
.menu {
  position: fixed;
  z-index: 30;
  min-width: 170px;
  margin: 0;
  padding: 4px;
  list-style: none;
  border-color: var(--border-strong);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
}
.menu li {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 5px 8px;
  border-radius: 2px;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.menu li:hover,
.menu li:focus {
  outline: none;
  color: #12160c;
  background: var(--accent);
}
.menu li:hover .hint,
.menu li:focus .hint {
  color: rgba(18, 22, 12, 0.7);
}
.menu li.divider {
  margin-top: 4px;
  border-top: 1px solid var(--border);
  padding-top: 8px;
}
.hint {
  font-size: 10px;
}
</style>
