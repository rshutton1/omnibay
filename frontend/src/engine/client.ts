// Typed wrapper over the Python bridge, plus the precomputed mech index.
//
// The index is a plain JSON file emitted at build time, so the mech browser
// renders immediately without booting Pyodide. Everything else goes through
// the engine.
import type { ItemTooltip } from '@/types.weapon'
import type { SkillTree } from '@/types.skills'
import type {
  BuildResponse,
  BuildState,
  EquipmentItem,
  MechDetail,
  MechSummary,
  UpgradeOption,
} from '@/types'
import { callEngine, callEngineSync } from './runtime'

const BASE = import.meta.env.BASE_URL

export interface MechIndex {
  meta: {
    counts: Record<string, number>
    factions: string[]
    weight_classes: string[]
    generated_from: string
  }
  mechs: MechSummary[]
}

let indexPromise: Promise<MechIndex> | null = null

/** The precomputed browse index. Needs no Python. */
export function loadMechIndex(): Promise<MechIndex> {
  if (!indexPromise) {
    indexPromise = fetch(`${BASE}mech-index.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`Could not load the mech index (${response.status})`)
        return response.json() as Promise<MechIndex>
      })
      .catch((error) => {
        indexPromise = null
        throw error
      })
  }
  return indexPromise
}

export const engine = {
  mech: (reference: string) => callEngine<MechDetail>((m) => m.get_mech(reference)),

  stockBuild: (reference: string) => callEngine<BuildResponse>((m) => m.stock_build(reference)),

  catalogue: () =>
    callEngine<{ equipment: EquipmentItem[]; upgrades: Record<string, UpgradeOption[]> }>(
      (m) => m.list_equipment(),
    ),

  /** Hot path: the engine is already booted by the time a build can be edited. */
  calculateSync: (reference: string, build: BuildState) =>
    callEngineSync<BuildResponse>((m) => m.calculate(reference, JSON.stringify(build))),

  weaponStats: (reference: string, itemId: number, build: BuildState | null) =>
    callEngine<ItemTooltip>((m) =>
      m.weapon_stats(reference, itemId, build ? JSON.stringify(build) : ''),
    ),

  skillTree: (reference: string, build: BuildState | null) =>
    callEngine<SkillTree>((m) => m.get_skill_tree(reference, build ? JSON.stringify(build) : '')),

  /** The engine fills in chains and enforces the point cap, then recalculates. */
  setSkills: (reference: string, build: BuildState, selection: string[]) =>
    callEngine<BuildResponse & { skills: { selected: string[]; dropped: string[]; spent: number; max_points: number } }>(
      (m) => m.set_skills(reference, JSON.stringify(build), JSON.stringify(selection)),
    ),

  /** Add or remove one node; the engine resolves prerequisites and dependents. */
  toggleSkill: (reference: string, build: BuildState, nodeName: string) =>
    callEngine<BuildResponse & { skills: { selected: string[]; dropped: string[]; spent: number; max_points: number } }>(
      (m) => m.toggle_skill(reference, JSON.stringify(build), nodeName),
    ),

  exportCode: (reference: string, build: BuildState) =>
    callEngine<{ code: string }>((m) => m.export_code(reference, JSON.stringify(build))),

  importCode: (code: string) =>
    callEngine<BuildResponse & { mech: MechSummary }>((m) => m.import_code(code)),
}
