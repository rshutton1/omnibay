// Share links: a build carried entirely in the URL, so no server is needed.
//
//   #/mechlab/<mech>?code=<MWO loadout code>&s=<skills>
//
// The loadout is the game's own code, so a shared link and the in-game import
// box agree. MWO codes carry no skills, so those ride alongside as a bitmask
// over the skill graph's node names, sorted for stability.

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

/**
 * Pack a skill selection as `<node count, base 36>.<6 bits per character>`.
 *
 * The node count is a guard: if the skill graph changes between sharing and
 * opening, the bits no longer line up and the skills are dropped rather than
 * misread.
 */
export function encodeSkills(allNodes: readonly string[], selected: readonly string[]): string {
  if (!selected.length) return ''
  const names = [...allNodes].sort()
  const chosen = new Set(selected)
  let packed = ''
  for (let start = 0; start < names.length; start += 6) {
    let bits = 0
    for (let offset = 0; offset < 6 && start + offset < names.length; offset++) {
      if (chosen.has(names[start + offset])) bits |= 1 << offset
    }
    packed += ALPHABET[bits]
  }
  return `${names.length.toString(36)}.${packed.replace(/A+$/, '')}`
}

/** The inverse of `encodeSkills`; `null` when the link does not fit this graph. */
export function decodeSkills(allNodes: readonly string[], encoded: string): string[] | null {
  const [count, packed = ''] = encoded.split('.')
  const names = [...allNodes].sort()
  if (parseInt(count, 36) !== names.length) return null
  const selected: string[] = []
  for (let index = 0; index < packed.length; index++) {
    const bits = ALPHABET.indexOf(packed[index])
    if (bits < 0) return null
    for (let offset = 0; offset < 6; offset++) {
      const name = names[index * 6 + offset]
      if (name && bits & (1 << offset)) selected.push(name)
    }
  }
  return selected
}
