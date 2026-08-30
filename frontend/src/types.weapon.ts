/** A stat shown as base and quirk-adjusted value. */
export interface StatPair {
  base: number
  final: number
  changed: boolean
}

export interface AppliedEffect {
  name: string
  /** Which aspects this quirk touched: cooldown, range, heat… */
  effects: readonly string[]
  /** Magnitude of the effect, in the direction its family uses. */
  value: number
  /** The quirk's own signed value, matching how it reads in the quirk list. */
  quirk_value: number
  harmful: boolean
  sources: readonly string[]
}

export interface WeaponTooltip {
  id: number
  name: string
  category: string
  hardpoint_type: string
  tons: number
  slots: number
  damage: StatPair
  heat: StatPair
  cooldown: StatPair
  expected_cooldown?: StatPair
  duration?: StatPair
  optimal_range?: StatPair
  max_range?: StatPair
  min_range?: StatPair
  velocity?: StatPair
  spread?: StatPair
  jam_chance?: StatPair
  jam_duration?: StatPair
  critical_chance?: readonly number[]
  rates: { dps?: StatPair; dph?: StatPair; hps?: StatPair }
  shots: string
  shot_interval: number | null
  continuous: boolean
  applied_effects: readonly AppliedEffect[]
}
