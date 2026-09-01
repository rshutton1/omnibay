/** A single skill node, with its value resolved for the current mech. */
export interface SkillNode {
  name: string
  /** Position in its branch chain, 1-based. */
  order: number
  column: number
  row: number
  selected: boolean
  /** Selectable right now — usable, and its prerequisite is taken. */
  available: boolean
  /** Applies to this mech at all (jump jet nodes need jump jets). */
  usable: boolean
  blocked_reason: string
  requires: string | null
  effects: readonly {
    name: string
    display_name: string
    value: number
    value_text: string
  }[]
}

export interface SkillBranch {
  key: string
  subcategory: string
  label: string
  nodes: readonly SkillNode[]
}

export interface SkillCategory {
  key: string
  name: string
  branches: readonly SkillBranch[]
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

export interface SkillSelectionResult {
  build: unknown
  result: unknown
  skills: {
    selected: string[]
    dropped: string[]
    spent: number
    max_points: number
  }
}
