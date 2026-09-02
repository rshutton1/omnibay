// The build editor's state.
//
// The store owns the build; the Python engine (running in Pyodide) owns every
// derived number. Recalculation is a synchronous in-process call — roughly
// 14 ms — so there is no debounce and no request race to guard against.
import { defineStore } from 'pinia'
import { engine } from '@/engine/client'
import { bootEngine } from '@/engine/runtime'
import type { BuildState, CalcResult, EquipmentItem, MechDetail, UpgradeOption } from '@/types'
import type { SkillTree } from '@/types.skills'

interface State {
  mech: MechDetail | null
  build: BuildState | null
  result: CalcResult | null
  equipment: EquipmentItem[]
  upgrades: Record<string, UpgradeOption[]>
  loading: boolean
  error: string | null
  exportedCode: string | null
  skillTree: SkillTree | null
  skillsLoading: boolean
}

export const useMechlabStore = defineStore('mechlab', {
  state: (): State => ({
    mech: null,
    build: null,
    result: null,
    equipment: [],
    upgrades: {},
    loading: false,
    error: null,
    exportedCode: null,
    skillTree: null,
    skillsLoading: false,
  }),

  getters: {
    skillPointsSpent: (state) => state.build?.skills?.length ?? 0,
    skillPointsMax: (state) => state.skillTree?.max_points ?? 91,
    isOverweight: (state) => state.result?.tonnage.overweight ?? false,
    warnings: (state) => state.result?.warnings ?? [],
  },

  actions: {
    /**
     * Load a mech, or keep what is already there.
     *
     * Views call this on mount, so navigating between the lab and the skill
     * tree would otherwise reset the build - and silently discard the pilot's
     * skill selection. Pass `force` to deliberately start over.
     */
    async loadMech(reference: string, force = false) {
      if (!force && this.mech?.name === reference && this.build) return
      this.loading = true
      this.error = null
      this.exportedCode = null
      try {
        await bootEngine()
        const [mech, stock] = await Promise.all([
          engine.mech(reference),
          engine.stockBuild(reference),
        ])
        this.mech = mech
        this.build = stock.build
        this.result = stock.result
        if (!this.equipment.length) {
          const catalogue = await engine.catalogue()
          this.equipment = catalogue.equipment
          this.upgrades = catalogue.upgrades
        }
        this.skillTree = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
      } finally {
        this.loading = false
      }
    },

    async loadSkillTree() {
      if (!this.mech) return
      this.skillsLoading = true
      try {
        this.skillTree = await engine.skillTree(this.mech.name, this.build)
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
      } finally {
        this.skillsLoading = false
      }
    },

    /**
     * Toggle a skill node. The engine owns the graph, so it decides what else
     * comes along (prerequisites) or falls away (dependents).
     */
    async toggleSkill(node: { name: string }) {
      if (!this.mech || !this.build) return
      try {
        const response = await engine.toggleSkill(this.mech.name, this.build, node.name)
        this.build = response.build
        this.result = response.result
        this.exportedCode = null
        this.error = null
        await this.loadSkillTree()
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
      }
    },

    async clearSkills() {
      await this.applySkills([])
    },

    async applySkills(selection: string[]) {
      if (!this.mech || !this.build) return
      try {
        const response = await engine.setSkills(this.mech.name, this.build, selection)
        this.build = response.build
        this.result = response.result
        this.exportedCode = null
        this.error = null
        await this.loadSkillTree()
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
      }
    },

    /** Recalculate in place. Synchronous, so callers need not await. */
    recalculate() {
      if (!this.mech || !this.build) return
      try {
        const response = engine.calculateSync(this.mech.name, this.build)
        this.build = response.build
        this.result = response.result
        this.exportedCode = null
        this.error = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
      }
    },

    addItem(component: string, itemId: number) {
      if (!this.build) return
      this.build.components[component].items.push({ item_id: itemId, weapon_group: null })
      this.recalculate()
    },

    /**
     * Relocate an installed item between components.
     *
     * Done as one mutation so the engine recalculates once, rather than
     * flashing through an intermediate state where the item exists in neither
     * component (or briefly in both).
     */
    moveItem(from: string, index: number, to: string) {
      if (!this.build || from === to) return
      const source = this.build.components[from]
      const target = this.build.components[to]
      if (!source || !target) return
      const [entry] = source.items.splice(index, 1)
      if (!entry) return
      target.items.push(entry)
      this.recalculate()
    },

    removeItem(component: string, index: number) {
      if (!this.build) return
      this.build.components[component].items.splice(index, 1)
      this.recalculate()
    },

    setArmor(component: string, value: number, rear = false) {
      if (!this.build) return
      const target = this.build.components[component]
      const cap = this.result?.components[component]?.max_armor ?? 0
      const other = rear ? target.armor : target.rear_armor
      const clamped = Math.max(0, Math.min(value, Math.max(0, cap - other)))
      if (rear) target.rear_armor = clamped
      else target.armor = clamped
      this.recalculate()
    },

    /** Fill every component to its cap, splitting torso armor 75/25 front to rear. */
    maximiseArmor() {
      if (!this.build || !this.result) return
      for (const [name, component] of Object.entries(this.result.components)) {
        const target = this.build.components[name]
        const cap = component.max_armor
        if (name.endsWith('_torso')) {
          target.armor = Math.round(cap * 0.75)
          target.rear_armor = cap - target.armor
        } else {
          target.armor = cap
          target.rear_armor = 0
        }
      }
      this.recalculate()
    },

    stripArmor() {
      if (!this.build) return
      for (const component of Object.values(this.build.components)) {
        component.armor = 0
        component.rear_armor = 0
      }
      this.recalculate()
    },

    setUpgrade(category: 'armor' | 'structure' | 'heatsinks', itemId: number) {
      if (!this.build) return
      this.build.upgrades[category] = itemId
      this.recalculate()
    },

    toggleArtemis(value: boolean) {
      if (!this.build) return
      this.build.upgrades.artemis = value
      this.recalculate()
    },

    setOmnipod(component: string, podId: number | null) {
      if (!this.build) return
      this.build.components[component].omnipod = podId
      this.recalculate()
    },

    async resetToStock() {
      if (!this.mech) return
      const stock = await engine.stockBuild(this.mech.name)
      this.skillTree = null
      this.build = stock.build
      this.result = stock.result
      this.exportedCode = null
    },

    async exportCode() {
      if (!this.mech || !this.build) return
      const { code } = await engine.exportCode(this.mech.name, this.build)
      this.exportedCode = code
      return code
    },

    async importCode(code: string) {
      this.loading = true
      this.error = null
      try {
        const response = await engine.importCode(code)
        this.mech = await engine.mech(response.mech.name)
        this.build = response.build
        this.result = response.result
        this.exportedCode = code
        return response.mech.name
      } catch (error) {
        this.error = error instanceof Error ? error.message : String(error)
        return null
      } finally {
        this.loading = false
      }
    },
  },
})
