import * as T from 'three'

// Each imported rig has its own anatomical mapping: shoulder/hip, knee, ankle, paw.
const chains = {
  baby: [
    [25, 24, 23, 22],
    [30, 29, 28, 27],
    [8, 7, 6, 5],
    [13, 12, 11, 10],
  ],
  two: [
    [33, 32, 31, 30],
    [38, 37, 36, 35],
    [8, 7, 6, 5],
    [13, 12, 11, 10],
  ],
  three: [
    [25, 24, 23, 22],
    [30, 29, 28, 27],
    [6, 5, 4, 3],
    [13, 12, 11, 10],
  ],
  four: [
    [11, 10, 9, 8],
    [21, 20, 19, 18],
    [39, 38, 37, 36],
    [45, 44, 43, 42],
  ],
  bridge: [
    [31, 30, 29, 28],
    [36, 35, 34, 33],
    [9, 8, 7, 6],
    [14, 13, 12, 11],
  ],
  five: [
    [31, 30, 29, 28],
    [36, 35, 34, 33],
    [9, 8, 7, 6],
    [14, 13, 12, 11],
  ],
  six: [
    [43, 42, 41, 40],
    [49, 48, 47, 46],
    [11, 10, 9, 8],
    [16, 15, 14, 13],
  ],
  seven: [
    [42, 41, 40, 39],
    [47, 46, 45, 44],
    [10, 9, 8, 7],
    [15, 14, 13, 12],
  ],
  eight: [
    [27, 26, 25, 24],
    [32, 31, 30, 29],
    [9, 8, 7, 6],
    [14, 13, 12, 11],
  ],
  nine: [
    [30, 29, 28, 27],
    [35, 34, 33, 32],
    [8, 7, 6, 5],
    [13, 12, 11, 10],
  ],
  ten: [
    [32, 31, 30, 29],
    [37, 36, 35, 34],
    [10, 9, 8, 7],
    [15, 14, 13, 12],
  ],
}
const name = (n) => 'Bone_' + String(n).padStart(3, '0')
// Hip-to-chest order differs between the imported rigs. Keep the pelvis stable.
const chaseSpines = {
  baby: [3, 2],
  two: [3, 2, 22],
  three: [8, 7],
  four: [3, 2, 15],
  five: [4, 3, 2, 26],
  bridge: [4, 3, 2, 26],
  six: [6, 5, 4, 3, 2],
  seven: [5, 4, 3, 2],
  eight: [4, 3, 2, 37],
  nine: [3, 2, 25],
  ten: [5, 4, 3, 2, 27],
}
const smooth = (x) => {
  x = T.MathUtils.clamp(x, 0, 1)
  return x * x * (3 - 2 * x)
}
const worldX = new T.Vector3(1, 0, 0),
  worldY = new T.Vector3(0, 1, 0)

export function prepareJump(data, key) {
  if (!chains[key]) return
  const root = data.bones[name(0)],
    scale = data.def.scale
  const legs = chains[key].map((ids, index) => {
    const bones = ids.map((n) => data.bones[name(n)])
    if (bones.some((b) => !b)) throw new Error('Incomplete leg rig: ' + key)
    return {
      joints: bones.slice(0, -1),
      foot: bones.at(-1),
      anchor: bones.at(-1).getWorldPosition(new T.Vector3()),
      orientation: bones.at(-1).getWorldQuaternion(new T.Quaternion()),
      front: index < 2,
    }
  })
  data.jump = {
    root,
    rootPosition: root.position.clone(),
    legs,
    chaseSpine: chaseSpines[key],
    scale,
    vertical: worldY
      .clone()
      .applyQuaternion(root.parent.getWorldQuaternion(new T.Quaternion()).invert())
      .divide(root.parent.getWorldScale(new T.Vector3())),
  }
  data.jump.rearPivot = legs[2].joints[0]
    .getWorldPosition(new T.Vector3())
    .add(legs[3].joints[0].getWorldPosition(new T.Vector3()))
    .multiplyScalar(0.5)
}

export function jumpTiming(t) {
  const phase = ((t % 2.8) + 2.8) % 2.8
  let crouch = 0,
    flight = 0,
    tuck = 0,
    push = 0,
    land = 0
  if (phase < 0.34) crouch = smooth(phase / 0.34)
  else if (phase < 0.48) {
    push = smooth((phase - 0.34) / 0.14)
    crouch = 1 - push
  } else if (phase < 1.16) {
    const u = (phase - 0.48) / 0.68
    flight = 4 * u * (1 - u)
    tuck = Math.sin(Math.PI * u) ** 2
  } else if (phase < 1.32) {
    land = smooth((phase - 1.16) / 0.16)
    crouch = 0.8 * land
  } else if (phase < 1.78) {
    land = 1 - smooth((phase - 1.32) / 0.46)
    crouch = 0.8 * land
  }
  return { phase, crouch, flight, tuck, push, land, grounded: phase < 0.48 || phase >= 1.16 }
}

export function resetJump(data) {
  if (data.jump) data.jump.root.position.copy(data.jump.rootPosition)
}

export function applyJump(data, t, rotate, options = {}) {
  const j = data.jump,
    s = jumpTiming(t)
  if (!j) return { ...s, hop: 0, flap: 0 }
  const hop = (options.height ?? 0.29) * s.flight,
    bodyDrop = (options.drop ?? 0.085) * j.scale * s.crouch
  data.group.position.y = data.baseY + hop
  j.root.position.copy(j.rootPosition).addScaledVector(j.vertical, -bodyDrop)
  rotate(data.def.neck, 0, 0.1 * s.crouch - 0.1 * s.flight + 0.08 * s.land)
  rotate(data.def.head, 0, -0.07 * s.crouch + 0.045 * s.flight - 0.035 * s.land)
  // The tail follows with a delay instead of moving in lockstep with the chest.
  data.def.tail.forEach((n, i) =>
    rotate(
      n,
      0,
      0.035 *
        Math.sin((s.phase - 0.1 - i * 0.045) * Math.PI * 2) *
        Math.max(s.crouch, s.flight, s.land),
    ),
  )
  data.group.updateMatrixWorld(true)
  solveLegs(data, hop, s.tuck, s.grounded)
  return {
    ...s,
    hop,
    flap: -0.16 * s.crouch + 0.3 * s.flight * Math.sin((Math.PI * (s.phase - 0.48)) / 0.68),
  }
}

// One finite flight: anticipation, climb, a small banked circuit, approach, landing.
export function flightTiming(t) {
  const lift = smooth((t - 1.05) / 1.35)
  const approach = smooth((t - 6.8) / 1.8)
  const air = lift * (1 - approach)
  const course = smooth((t - 2.4) / 4.3)
  const crouch = smooth(t / 0.5) * (1 - smooth((t - 0.65) / 0.4))
  const landing = smooth((t - 8.6) / 0.18) * (1 - smooth((t - 8.9) / 0.9))
  const flapping = smooth((t - 0.3) / 0.6) * (1 - smooth((t - 8.6) / 0.8))
  const tuck = smooth((t - 1.25) / 1.15) * (1 - smooth((t - 6.6) / 1.4))
  return { air, course, crouch, landing, flapping, tuck, grounded: t <= 1.05 || t >= 8.6 }
}

export function applyFlight(data, t, rotate) {
  const j = data.jump
  const state = flightTiming(t)
  if (!j) return { ...state, height: 0, flap: 0 }
  const phase = (t - 0.35) * 6.8
  const stroke = Math.sin(phase) + 0.2 * Math.sin(2 * phase + 0.45)
  // Lift responds a little after the wing downstroke, rather than bobbing arbitrarily.
  const height = j.scale * state.air * (0.52 + 0.028 * Math.sin(phase - 0.65))
  const drop = j.scale * (0.065 * state.crouch + 0.06 * state.landing)
  data.group.position.y = data.baseY + height
  j.root.position.copy(j.rootPosition).addScaledVector(j.vertical, -drop)
  rotate(data.def.neck, 0, 0.06 * state.crouch - 0.07 * state.air + 0.07 * state.landing)
  rotate(data.def.head, 0, -0.04 * state.crouch + 0.035 * state.air - 0.04 * state.landing)
  data.group.updateMatrixWorld(true)
  solveLegs(data, height, state.tuck, state.grounded)
  const arc = state.course * Math.PI * 2
  // Transform the complete rig after solving the tucked legs. All four paws travel with it.
  data.group.position.x = 0.46 * j.scale * Math.sin(arc) * state.air
  data.group.position.z = 0.15 * j.scale * (1 - Math.cos(arc)) * state.air
  data.group.rotation.set(
    state.air * (-0.075 + 0.025 * state.flapping * Math.sin(phase - 0.6)),
    0.28 * Math.cos(arc) * Math.sin(Math.PI * state.course) * state.air,
    0.075 * Math.sin(arc + 0.35) * state.air,
  )
  data.def.tail.forEach((n, i) =>
    rotate(n, 0, 0.045 * state.air * Math.sin(phase * 0.45 - i * 0.55)),
  )
  return { ...state, height, flap: state.flapping * (0.12 + 0.49 * stroke), phase }
}

// A short trotting circle: alternating diagonal paws lift while the rig turns.
export function applyChase(data, t, rotate) {
  const j = data.jump
  if (!j) return null
  const run = smooth((t - 0.8) / 0.8) * (1 - smooth((t - 8) / 1.1))
  const progress = smooth((t - 1.1) / 7)
  const angle = 4 * Math.PI * progress
  data.group.updateMatrixWorld(true)
  const hips = j.legs.map((leg) => ({
    position: leg.joints[0].getWorldPosition(new T.Vector3()),
    rotation: leg.joints[0].getWorldQuaternion(new T.Quaternion()),
  }))
  // Bend through the torso instead of rotating a rigid silhouette. The small
  // release on each stride makes the dragon reach for its escaping tail.
  const curl = smooth(t / 0.8) * (1 - smooth((t - 8.1) / 1.4))
  const bend = curl * (0.57 + 0.07 * Math.sin(t * 4.5))
  j.chaseSpine.forEach((n) => rotate(n, 1, bend / j.chaseSpine.length))
  data.group.updateMatrixWorld(true)
  const frames = j.legs.map((leg, i) => ({
    rotation: leg.joints[0]
      .getWorldQuaternion(new T.Quaternion())
      .multiply(hips[i].rotation.clone().invert()),
    position: leg.joints[0].getWorldPosition(new T.Vector3()),
  }))
  const targets = j.legs.map((leg, i) => {
    const phase = (((t * 1.8 + (i === 0 || i === 3 ? 0 : 0.5)) % 1) + 1) % 1
    const swing = phase > 0.58
    const u = swing ? (phase - 0.58) / 0.42 : phase / 0.58
    const forward = swing ? -0.5 + smooth(u) : 0.5 - u
    return leg.anchor
      .clone()
      .sub(hips[i].position)
      .applyQuaternion(frames[i].rotation)
      .add(frames[i].position)
      .add(
        new T.Vector3(
          0,
          swing ? 0.13 * j.scale * Math.sin(Math.PI * u) * run : 0,
          0.18 * j.scale * forward * run,
        ),
      )
  })
  j.root.position
    .copy(j.rootPosition)
    .addScaledVector(
      j.vertical,
      -0.035 * j.scale * run * (0.5 + 0.5 * Math.sin(t * 1.8 * Math.PI * 4)),
    )
  data.group.updateMatrixWorld(true)
  solveLegs(data, 0, 0, true, targets, 0, 0, frames)
  const radius = 0.22 * j.scale
  data.group.position.x = radius * (1 - Math.cos(angle))
  data.group.position.z = radius * Math.sin(angle)
  data.group.rotation.y = angle
  data.group.rotation.z = 0.045 * Math.sin(angle) * run
  return { run, progress, angle, curl, bend }
}

export function groundedBody(data, drop) {
  const j = data.jump
  if (!j) return
  j.root.position.copy(j.rootPosition).addScaledVector(j.vertical, -drop * j.scale)
  data.group.updateMatrixWorld(true)
  solveLegs(data, 0, 0, true)
}

export function rearTiming(t) {
  const p = ((t % 6.8) + 6.8) % 6.8
  const rise = smooth((p - 0.35) / 1.0) * (1 - smooth((p - 4.25) / 1.25))
  const pawing = smooth((p - 1.25) / 0.5) * (1 - smooth((p - 3.9) / 0.45))
  return { phase: p, rise, pawing }
}

export function magicTiming(t) {
  const phase = ((t % 8.8) + 8.8) % 8.8
  return {
    phase,
    rise: smooth((phase - 0.25) / 1.05) * (1 - smooth((phase - 7.1) / 1.3)),
    pawing: 0,
    form: smooth((phase - 1.1) / 1.35),
    float: smooth((phase - 2.8) / 1.9),
    burst: Math.max(0, phase - 4.85),
  }
}

export function applyRear(data, t, rotate, magic = false, affection = false) {
  const j = data.jump,
    s = magic ? magicTiming(t) : rearTiming(t)
  if (!j) return s
  data.group.updateMatrixWorld(true)
  const angle = (affection ? -0.66 : -0.86) * s.rise,
    rotation = new T.Quaternion().setFromAxisAngle(worldX, angle),
    root = j.root
  const position = root
    .getWorldPosition(new T.Vector3())
    .sub(j.rearPivot)
    .applyQuaternion(rotation)
    .add(j.rearPivot)
  const orientation = rotation.clone().multiply(root.getWorldQuaternion(new T.Quaternion()))
  root.position.copy(root.parent.worldToLocal(position))
  root.quaternion.copy(
    root.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(orientation),
  )
  const small = j.scale < 1
  rotate(data.def.neck, 0, (small ? 0.32 : 0.22) * s.rise)
  rotate(data.def.head, 0, (small ? 0.32 : 0.2) * s.rise)
  data.def.tail.forEach((n, i) =>
    rotate(n, 0, -0.025 * s.rise * (1 - i / Math.max(1, data.def.tail.length))),
  )
  data.group.updateMatrixWorld(true)
  const targets = j.legs.map((leg, i) => {
    if (!leg.front) return leg.anchor.clone()
    const target = leg.anchor.clone().sub(j.rearPivot).applyQuaternion(rotation).add(j.rearPivot)
    const cycle = t * 5.4 + i * Math.PI
    target.y +=
      j.scale *
      ((magic || affection ? 0.15 : 0.105) * s.rise +
        (affection ? 0.025 : 0.065) * s.pawing * Math.sin(cycle))
    target.z += j.scale * (-0.08 * s.rise + (affection ? 0.035 : 0.07) * s.pawing * Math.cos(cycle))
    return target
  })
  solveLegs(data, 0, 0, true, targets, (magic ? -0.18 : 0.42) * s.rise, s.rise)
  return { ...s, angle }
}

export function applyPlayBow(data, t, rotate) {
  const j = data.jump
  if (!j) return null
  const bow = smooth((t - 0.15) / 0.9) * (1 - smooth((t - 4.9) / 1.6))
  const rock = bow * Math.sin(t * 4.6)
  const angle = 0.28 * bow + 0.025 * rock
  const rotation = new T.Quaternion().setFromAxisAngle(worldX, angle)
  data.group.updateMatrixWorld(true)
  const position = j.root
    .getWorldPosition(new T.Vector3())
    .sub(j.rearPivot)
    .applyQuaternion(rotation)
    .add(j.rearPivot)
  const orientation = rotation.clone().multiply(j.root.getWorldQuaternion(new T.Quaternion()))
  j.root.position.copy(j.root.parent.worldToLocal(position))
  j.root.quaternion.copy(
    j.root.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(orientation),
  )
  rotate(data.def.neck, 0, -0.2 * bow)
  rotate(data.def.head, 0, -0.16 * bow)
  data.group.updateMatrixWorld(true)
  const targets = j.legs.map((leg, i) => {
    const target = leg.anchor.clone()
    if (leg.front) {
      target.z += j.scale * (0.1 * bow + 0.018 * rock)
      // Alternate a tiny inviting paw lift, with both paws settling before rising.
      target.y += 0.025 * j.scale * bow * Math.max(0, Math.sin(t * 4.6 + i * Math.PI))
    }
    return target
  })
  solveLegs(data, 0, 0, true, targets)
  return { bow, angle }
}

function solveLegs(
  data,
  hop,
  tuck,
  grounded,
  targets = null,
  frontAngle = 0,
  rise = 0,
  frames = null,
) {
  const j = data.jump
  for (const [legIndex, leg] of j.legs.entries()) {
    const target = targets ? targets[legIndex].clone() : leg.anchor.clone()
    if (!targets) {
      target.y += hop + 0.12 * j.scale * tuck
      target.z += (leg.front ? -0.065 : 0.045) * j.scale * tuck
    }
    const totalAngles = leg.joints.map(() => 0)
    const bendAxis = frames ? worldX.clone().applyQuaternion(frames[legIndex].rotation) : worldX
    // Sagittal-plane CCD keeps the paw planted without sideways knee twisting.
    const limit = targets ? 1.1 : 0.85
    for (let iteration = 0; iteration < (targets ? 36 : 18); iteration++) {
      if (leg.foot.getWorldPosition(new T.Vector3()).distanceTo(target) < 0.00025) break
      for (let i = leg.joints.length - 1; i >= 0; i--) {
        const joint = leg.joints[i],
          origin = joint.getWorldPosition(new T.Vector3())
        const end = leg.foot.getWorldPosition(new T.Vector3()).sub(origin),
          goal = target.clone().sub(origin)
        const angle = Math.atan2(
          end.clone().cross(goal).dot(bendAxis),
          end.dot(goal) - end.dot(bendAxis) * goal.dot(bendAxis),
        )
        const next = T.MathUtils.clamp(
            totalAngles[i] + T.MathUtils.clamp(angle, -0.16, 0.16),
            -limit,
            limit,
          ),
          delta = next - totalAngles[i]
        totalAngles[i] = next
        const axis = bendAxis
          .clone()
          .applyQuaternion(joint.getWorldQuaternion(new T.Quaternion()).invert())
        joint.quaternion.multiply(new T.Quaternion().setFromAxisAngle(axis, delta))
        joint.updateWorldMatrix(false, true)
      }
    }
    const footRotation = leg.orientation.clone()
    if (frames) footRotation.premultiply(frames[legIndex].rotation)
    if (leg.front && rise > 0)
      footRotation.premultiply(new T.Quaternion().setFromAxisAngle(worldX, frontAngle))
    if (!grounded) {
      const sign = leg.front ? 1 : -1
      footRotation.premultiply(new T.Quaternion().setFromAxisAngle(worldX, sign * 0.24 * tuck))
    }
    leg.foot.quaternion.copy(
      leg.foot.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(footRotation),
    )
    leg.foot.updateWorldMatrix(false, true)
    leg.target = target
  }
}
