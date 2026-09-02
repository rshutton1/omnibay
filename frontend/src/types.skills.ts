/** A single skill node, positioned and valued for the current mech. */
export interface SkillNode {
  name: string
  /** The game's display name, e.g. "Speed Tweak 1". */
  label: string
  /** The branch heading it sits under, e.g. "Speed Tweak". */
  branch: string
  /** Position within its category, in the game's own units. */
  x: number
  y: number
  selected: boolean
  /** Prerequisite already taken, so this is the next step. */
  available: boolean
  /** Applies to this mech at all (jump jet nodes need jump jets). */
  usable: boolean
  blocked_reason: string
  requires: string | null
  /** Points a click would spend, including any unmet prerequisites. */
  cost: number
  effects: readonly {
    name: string
    display_name: string
    value: number
    value_text: string
  }[]
}

export interface SkillBranchLabel {
  label: string
  x: number
  y: number
  taken: number
  total: number
}

export interface SkillCategory {
  key: string
  name: string
  width: number
  height: number
  nodes: readonly SkillNode[]
  /** Prerequisite links, as [from, to] node names. */
  edges: readonly (readonly [string, string])[]
  branches: readonly SkillBranchLabel[]
}

export interface SkillTree {
  max_points: number
  spent: number
  categories: readonly SkillCategory[]
  effects: readonly {
    name: string
    display_name: string
    value: number
    value_text: string
    source_text: string
  }[]
}
