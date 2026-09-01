// Shapes returned by the Python API. Kept deliberately close to the JSON so
// there is one obvious place to look when the backend changes.

export interface MechSummary {
  id: number
  name: string
  display_name: string
  chassis: string
  faction: string
  weight_class: string
  max_tons: number
  is_omnimech: boolean
  hardpoints: Record<string, number>
  jump_jets: number
  engine_range: [number, number]
}

export interface Hardpoint {
  ID?: number
  Type?: number
  hardpoint_type: string
  weapon_slots?: number
}

export interface MechDetail extends MechSummary {
  stats: Record<string, number | string>
  movement: Record<string, number>
  quirks: Quirk[]
  components: Record<
    string,
    { slots: number; hp: number; hardpoints: Hardpoint[]; max_armor: number }
  >
}

export interface Quirk {
  name: string
  display_name: string
  value: number
  value_text: string
  /** The stat the quirk acts on, e.g. "cooldown". */
  family?: string
  /** Whether the quirk helps the pilot; null when the value is zero. */
  beneficial?: boolean | null
  sources?: string[]
  source_text?: string
}

export interface ItemEntry {
  item_id: number
  weapon_group: number | null
}

export interface ComponentState {
  armor: number
  rear_armor: number
  omnipod: number | null
  items: ItemEntry[]
}

export interface BuildState {
  components: Record<string, ComponentState>
  upgrades: {
    armor: number | null
    structure: number | null
    heatsinks: number | null
    artemis: boolean
  }
  engine_heat_sinks: ItemEntry[]
  actuator_state: number
  /** Selected skill node names. */
  skills: string[]
}

export interface DescribedItem {
  /** Coarse class used to colour the item, decided by the engine. */
  category: string
  id: number
  name: string
  display_name: string
  item_type: string
  family: string
  slots: number
  tons: number
  heat: number
  hardpoint_type: string
  damage: number | null
  weapon_group?: number | null
  source?: string
}

export interface ComponentResult {
  name: string
  label: string
  abbreviation: string
  /** Quirks scoped to this component, e.g. `armor_rt_additive`. */
  quirks: Quirk[]
  engine_side_slots: number
  fixed_engine_slots: number
  internal_slots: number
  fixed_slots: number
  slot_limit: number
  slots: number
  free_slots: number
  hardpoints: Record<string, number>
  hardpoint_capacity: Record<string, number>
  armor: number
  rear_armor: number
  max_armor: number
  structure: number
  /** Armor and structure after durability quirks and skills. */
  effective_armor: number
  effective_rear_armor: number
  effective_structure: number
  omnipod: number | null
  items: DescribedItem[]
  fixed_items: DescribedItem[]
  internals: DescribedItem[]
  warnings: string[]
  occupied_upgrade_slots: number
  structure_slots: number
  armor_slots: number
}

export interface CalcResult {
  mech: {
    id: number
    name: string
    display_name: string
    chassis: string
    faction: string
    weight_class: string
    max_tons: number
    is_omnimech: boolean
  }
  tonnage: {
    max: number
    used: number
    free: number
    equipment: number
    structure: number
    armor: number
    /** Tons above the chassis limit; 0 when legal. */
    over_by: number
    overweight: boolean
  }
  slots: {
    total: number
    used: number
    free: number
    structure_upgrade: number
    armor_upgrade: number
  }
  armor: { points: number; max_points: number; tons: number; per_ton: number }
  heat: {
    alpha_heat: number
    heat_sinks: number
    engine_heat_sinks: number
    external_heat_sinks: number
    double: boolean
    dissipation: number
    capacity: number
  }
  firepower: { alpha_damage: number; ammo_shots: number }
  engine: {
    id: number
    display_name: string
    rating: number
    tons: number
    slots: number
    side_slots: number
    included_heat_sinks: number
    heat_sink_capacity: number
  } | null
  jump_jets: { installed: number; limit: number }
  components: Record<string, ComponentResult>
  quirks: Quirk[]
  warnings: string[]
  valid: boolean
}

export interface EquipmentItem {
  id: number
  name: string
  display_name: string
  item_type: string
  family: string
  faction: string
  slots: number
  tons: number
  heat: number
  hardpoint_type: string
  stats: Record<string, number | string>
}

export interface UpgradeOption {
  id: number
  display_name: string
  faction: string
  stats: Record<string, number | string>
}

export interface BuildResponse {
  build: BuildState
  result: CalcResult
}
