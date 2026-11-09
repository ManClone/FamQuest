import * as T from 'three'

// The source is one connected surface: per-vertex arm weights stretch crystal
// triangles across the shell. Split at triangle boundaries, then keep crystal
// faces stationary and bind the small blue front-paw surface to its own chain.
export function prepareShellPaws(data) {
  const ids = [
    [22, 21, 20, 19],
    [26, 25, 24, 23],
  ]
  const name = (n) => 'Bone_' + String(n).padStart(3, '0')
  const armNames = new Set(ids.flat().map(name))
  const chains = ids.map((chain) =>
    chain.map((n) => data.bones[name(n)].getWorldPosition(new T.Vector3())),
  )
  const segments = chains.map((chain) =>
    chain.slice(0, -1).map((p, i) => new T.Line3(p, chain[i + 1])),
  )
  const nearest = (point, chainIndex) => {
    let best = { distance: Infinity, segment: 0, t: 0 }
    for (const [i, line] of segments[chainIndex].entries()) {
      const t = line.closestPointToPointParameter(point, true)
      const distance = line.at(t, new T.Vector3()).distanceTo(point)
      if (distance < best.distance) best = { distance, segment: i, t }
    }
    return best
  }
  for (const skin of data.skins) {
    skin.skeleton.update()
    const original = skin.geometry
    skin.geometry = original.index ? original.toNonIndexed() : original.clone()
    original.dispose()
    const { skinIndex: indices, skinWeight: weights, uv } = skin.geometry.attributes
    const root = skin.skeleton.bones.findIndex((bone) => bone.name === 'Bone_000')
    const boneIndices = ids.map((chain) =>
      chain.map((n) => skin.skeleton.bones.findIndex((bone) => bone.name === name(n))),
    )
    const image = skin.material.map.image
    const canvas = document.createElement('canvas')
    canvas.width = image.width
    canvas.height = image.height
    const context = canvas.getContext('2d')
    context.drawImage(image, 0, 0)
    const pixels = context.getImageData(0, 0, image.width, image.height).data
    const color = (i) => {
      const x = T.MathUtils.clamp(Math.floor(uv.getX(i) * image.width), 0, image.width - 1)
      const y = T.MathUtils.clamp(Math.floor(uv.getY(i) * image.height), 0, image.height - 1)
      const p = (y * image.width + x) * 4
      const r = pixels[p],
        g = pixels[p + 1],
        b = pixels[p + 2]
      return {
        blue: b > r * 1.25 && g > r * 1.15 && g > b * 0.54,
        dark: r + g + b < 180 && b > r * 1.2,
      }
    }
    for (let i = 0; i < indices.count; i += 3) {
      const points = [0, 1, 2].map((j) =>
        skin.getVertexPosition(i + j, new T.Vector3()).applyMatrix4(skin.matrixWorld),
      )
      const center = points.reduce((sum, p) => sum.add(p), new T.Vector3()).multiplyScalar(1 / 3)
      const colors = [0, 1, 2].map((j) => color(i + j))
      const blue = colors.filter((c) => c.blue).length,
        dark = colors.filter((c) => c.dark).length
      const distances = chains.map((_, chain) => nearest(center, chain).distance)
      const chain = distances[0] < distances[1] ? 0 : 1
      const movable =
        (blue >= 2 || (blue >= 1 && dark >= 2)) &&
        distances[chain] < 0.105 * data.def.scale &&
        points.every((p) => p.y - data.baseY > 0.535 * data.def.scale) &&
        center.z < chains[chain][3].z + 0.07 * data.def.scale
      for (let j = 0; j < 3; j++) {
        const index = i + j
        if (movable) {
          const n = nearest(points[j], chain)
          indices.setXYZW(
            index,
            boneIndices[chain][n.segment],
            boneIndices[chain][n.segment + 1],
            root,
            root,
          )
          weights.setXYZW(index, 1 - n.t, n.t, 0, 0)
        } else {
          const merged = new Map()
          for (let k = 0; k < 4; k++) {
            const old = indices.getComponent(index, k)
            const bone = armNames.has(skin.skeleton.bones[old].name) ? root : old
            merged.set(bone, (merged.get(bone) ?? 0) + weights.getComponent(index, k))
          }
          const entries = [...merged]
          const total = entries.reduce((sum, [, w]) => sum + w, 0)
          for (let k = 0; k < 4; k++) {
            indices.setComponent(index, k, entries[k]?.[0] ?? root)
            weights.setComponent(index, k, (entries[k]?.[1] ?? 0) / total)
          }
        }
      }
    }
    indices.needsUpdate = weights.needsUpdate = true
  }
}
