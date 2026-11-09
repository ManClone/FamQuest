import * as T from 'three'
import { GLTFLoader } from './vendor/GLTFLoader.js'
import {
  prepareJump,
  resetJump,
  applyJump,
  groundedBody,
  applyRear,
  applyFlight,
  applyChase,
  applyPlayBow,
  magicTiming,
} from './jump.js'
import { channels } from './motions.js'
import { applyShellPaws, prepareShellPaws, shellBounce } from './shell.js'
const defs = {
  egg: {
    file: 'Ei.glb',
    label: 'Schlüpfvariante',
    head: 27,
    neck: 28,
    tail: [],
    wings: [],
    scale: 0.82,
  },
  baby: {
    file: 'Baby.glb',
    label: 'Stufe 1 · Baby',
    head: 31,
    neck: 32,
    tail: [18, 17, 16, 15, 14],
    wings: [35, 38],
    scale: 0.86,
  },
  two: {
    file: 'Stufe-2.glb',
    label: 'Stufe 2',
    head: 39,
    neck: 40,
    tail: [18, 17, 16, 15, 14],
    wings: [25, 28],
    scale: 0.93,
  },
  three: {
    file: 'Stufe-3.glb',
    label: 'Stufe 3',
    head: 31,
    neck: 32,
    tail: [18, 17, 16, 15, 14],
    wings: [36, 40],
    scale: 1,
  },
  five: {
    file: 'Stufe-5-v2.glb',
    label: 'Stufe 5',
    head: 24,
    neck: 25,
    tail: [21, 20, 19, 18, 17, 16, 15],
    wings: [39, 42],
    scale: 1.07,
  },
  bridge: {
    file: 'Stufe-5.glb',
    label: 'Stufe 6',
    head: 23,
    neck: 25,
    tail: [20, 19, 18, 17, 16, 15],
    wings: [39, 42],
    scale: 1.09,
  },
  six: {
    file: 'Stufe-6.glb',
    label: 'Stufe 7',
    head: 36,
    neck: 37,
    tail: [22, 21, 20, 19, 18, 17],
    wings: [29, 32],
    scale: 1.1,
  },
  seven: {
    file: 'Stufe-7.glb',
    label: 'Stufe 8',
    head: 33,
    neck: 35,
    tail: [22, 21, 20, 19, 18, 17, 16],
    wings: [32, 29],
    scale: 1.13,
  },
  eight: {
    file: 'Stufe-8.glb',
    label: 'Stufe 9',
    head: 33,
    neck: 35,
    tail: [20, 19, 18, 17, 16, 15],
    wings: [41, 45],
    scale: 1.17,
  },
  nine: {
    file: 'Stufe-9.glb',
    label: 'Stufe 10',
    head: 22,
    neck: 24,
    tail: [19, 18, 17, 16, 15, 14],
    wings: [38, 41],
    scale: 1.21,
  },
  ten: {
    file: 'Stufe-10.glb',
    label: 'Stufe 11',
    head: 24,
    neck: 26,
    tail: [21, 20, 19, 18, 17, 16],
    wings: [43, 40],
    scale: 1.25,
  },
  four: {
    file: 'Stufe-4-v2.glb',
    label: 'Stufe 4',
    head: 12,
    neck: 14,
    tail: [50, 49, 48, 47, 46],
    wings: [27, 33],
    scale: 1.04,
  },
}
const host = document.querySelector('#view'),
  status = document.querySelector('#status'),
  caption = document.querySelector('#caption')
const renderer = new T.WebGLRenderer({ antialias: true, alpha: true })
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
renderer.toneMapping = T.ACESFilmicToneMapping
renderer.toneMappingExposure = 0.95
host.prepend(renderer.domElement)
const scene = new T.Scene(),
  camera = new T.PerspectiveCamera(36, 1, 0.01, 80)
scene.add(new T.HemisphereLight(0xfffbf5, 0x8896bc, 2))
for (const [p, e] of [
  [[-3, 5, 4], 2.5],
  [[3, 3, -2], 1.6],
]) {
  const l = new T.DirectionalLight(0xffffff, e)
  l.position.set(...p)
  scene.add(l)
}
const floor = new T.Mesh(
  new T.CircleGeometry(2.8, 80),
  new T.MeshStandardMaterial({ color: 0xe9e8fb, roughness: 1 }),
)
floor.rotation.x = -Math.PI / 2
floor.position.y = -0.04
scene.add(floor)
const shadow = new T.Mesh(
  new T.CircleGeometry(0.55, 48),
  new T.MeshBasicMaterial({ color: 0x817994, transparent: true, opacity: 0.12, depthWrite: false }),
)
shadow.rotation.x = -Math.PI / 2
shadow.scale.y = 0.72
shadow.position.y = -0.025
scene.add(shadow)
const starShape = new T.Shape()
for (let i = 0; i < 10; i++) {
  const a = (i * Math.PI) / 5 + Math.PI / 2,
    rad = i % 2 ? 0.45 : 1
  const x = Math.cos(a) * rad,
    y = Math.sin(a) * rad
  if (i) starShape.lineTo(x, y)
  else starShape.moveTo(x, y)
}
starShape.closePath()
const starGeo = new T.ShapeGeometry(starShape),
  particles = []
for (let i = 0; i < 140; i++) {
  const material = new T.MeshBasicMaterial({
    color: i % 3 ? 0xffc84d : 0xc7abff,
    side: T.DoubleSide,
    transparent: true,
    depthWrite: false,
  })
  const mesh = new T.Mesh(starGeo, material)
  mesh.visible = false
  scene.add(mesh)
  particles.push({ mesh })
}
const loader = new GLTFLoader(),
  cache = new Map()
let active,
  key = 'baby',
  motion = 'idle',
  clock = 0,
  paused = false,
  last = 0,
  request = 0,
  yaw = 0,
  pitch = 0.14,
  distance = 4.2,
  lifeClock = 0,
  transition = null,
  transitionAge = 0,
  idleVariationAt = 2,
  idleActionIndex = 0
const num = (n) => 'Bone_' + String(n).padStart(3, '0')
function view(instant = false) {
  const restingFit = active?.def.scale >= 1.07 ? 1.2 : 1
  const actionFit =
    motion === 'chase'
      ? 1.48
      : motion === 'fly'
        ? active?.def.scale >= 1.07
          ? 1.52
          : 1.38
        : motion === 'stars'
          ? 1.22
          : motion === 'rear' || motion === 'heart'
            ? 1.18
            : 1
  const d = distance * Math.max(restingFit, actionFit) * Math.max(1, 1 / camera.aspect)
  const lookYaw = motion === 'fly' ? -0.58 : yaw
  camera.position.lerp(
    new T.Vector3(
      Math.sin(lookYaw) * Math.cos(pitch) * d,
      0.86 + Math.sin(pitch) * d,
      Math.cos(lookYaw) * Math.cos(pitch) * d,
    ),
    instant ? 1 : 0.1,
  )
  camera.lookAt(
    0,
    motion === 'fly' ? 1.14 : ['rear', 'stars', 'heart'].includes(motion) ? 1.04 : 0.86,
    0,
  )
}
function trimCache(limit) {
  for (const [k, data] of cache) {
    if (cache.size <= limit) break
    if (data === active) continue
    scene.remove(data.group)
    scene.remove(data.helper)
    data.helper.geometry.dispose()
    data.helper.material.dispose()
    const textures = new Set(),
      materials = new Set()
    data.group.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) {
        for (const m of Array.isArray(o.material) ? o.material : [o.material]) materials.add(m)
      }
      if (o.skeleton) o.skeleton.dispose()
    })
    for (const material of materials) {
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value)
      material.dispose()
    }
    for (const texture of textures) {
      texture.dispose()
      texture.source?.data?.close?.()
    }
    cache.delete(k)
  }
}
async function getModel(k) {
  if (cache.has(k)) {
    const data = cache.get(k)
    cache.delete(k)
    cache.set(k, data)
    return data
  }
  trimCache(2)
  const g = await loader.loadAsync('./' + defs[k].file)
  const group = new T.Group()
  group.add(g.scene)
  scene.add(group)
  group.visible = false
  group.scale.setScalar(defs[k].scale)
  group.updateMatrixWorld(true)
  const skins = [],
    bones = {},
    rest = {},
    axes = {}
  g.scene.traverse((o) => {
    if (o.isSkinnedMesh) {
      skins.push(o)
      o.frustumCulled = false
    }
    if (o.isBone) {
      bones[o.name] = o
      rest[o.name] = o.quaternion.clone()
    }
  })
  for (const n in bones) {
    const inverse = bones[n].getWorldQuaternion(new T.Quaternion()).invert()
    axes[n] = [new T.Vector3(1, 0, 0), new T.Vector3(0, 1, 0), new T.Vector3(0, 0, 1)].map((v) =>
      v.applyQuaternion(inverse),
    )
  }
  const helper = new T.SkeletonHelper(g.scene)
  helper.visible = false
  helper.material.depthTest = false
  helper.renderOrder = 10
  scene.add(helper)
  const box = new T.Box3().setFromObject(group)
  group.position.y = -box.min.y
  const data = { group, skins, bones, rest, axes, helper, baseY: group.position.y, def: defs[k] }
  group.updateMatrixWorld(true)
  if (k === 'egg') prepareShellPaws(data)
  prepareJump(data, k)
  cache.set(k, data)
  return data
}
async function select(k) {
  const token = ++request
  status.textContent = 'Lädt ' + defs[k].label + ' …'
  try {
    const next = await getModel(k)
    if (token !== request) return
    if (active) {
      active.group.visible = false
      active.helper.visible = false
    }
    active = next
    transition = null
    key = k
    active.group.visible = true
    clock = 0
    document
      .querySelectorAll('[data-model]')
      .forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.model === k)))
    const wingButton = document.querySelector('[data-motion="wings"]')
    wingButton.disabled = k === 'egg'
    wingButton.title = k === 'egg' ? 'Die Flügel bleiben in der Schale.' : ''
    const rearButton = document.querySelector('[data-motion="rear"]')
    rearButton.disabled = k === 'egg'
    rearButton.title = k === 'egg' ? 'In der Schale bleibt Sternchen sitzen.' : ''
    document.querySelector('[data-motion="happy"]').textContent =
      k === 'egg' ? 'Freuen' : 'Freuen & hüpfen'
    document.querySelector('#skeleton').setAttribute('aria-pressed', 'false')
    status.textContent =
      defs[k].label + ' · ' + Object.keys(active.bones).length + ' Knochen · Animation läuft'
    setMotion((motion === 'wings' || motion === 'rear') && k === 'egg' ? 'hello' : motion)
    if (reduced) {
      pose(0, 0)
      renderer.render(scene, camera)
    }
    parent.postMessage({ type: 'dragon-ready' }, location.origin)
  } catch (e) {
    status.textContent = 'Laden fehlgeschlagen: ' + e.message
    parent.postMessage({ type: 'dragon-error' }, location.origin)
  }
}
function rotate(n, axis, angle) {
  const name = num(n)
  if (active.bones[name])
    active.bones[name].quaternion.multiply(
      new T.Quaternion().setFromAxisAngle(active.axes[name][axis], angle),
    )
}
function pose(t, life = t) {
  if (!active) return
  const d = active.def,
    youth =
      key === 'egg'
        ? 1
        : key === 'baby'
          ? 1.13
          : key === 'two'
            ? 1.1
            : key === 'three'
              ? 1.06
              : key === 'four'
                ? 1.03
                : 0.94
  for (const n in active.rest) active.bones[n].quaternion.copy(active.rest[n])
  resetJump(active)
  active.jumpState = null
  active.rearState = null
  active.magicState = null
  active.flightState = null
  active.chaseState = null
  active.playState = null
  active.shellState = null
  active.group.position.set(0, active.baseY, 0)
  active.group.rotation.set(0, 0, 0)
  const c = channels(motion === 'sad' ? 'calm' : motion, t, life, youth)
  if (motion === 'sad') {
    const dip = Math.sin(Math.PI * Math.min(t / 5, 1))
    c.pitch += 0.25 * dip
    c.neck += 0.12 * dip
    c.yaw *= 0.2
    c.roll *= 0.2
    c.tail *= 0.25
    c.left *= 0.2
    c.right *= 0.2
    c.drop *= 0.4
  }
  active.channels = c
  if (key === 'egg') applyShellPaws(motion, t, life, rotate)
  rotate(d.neck, 0, c.neck)
  rotate(d.neck, 1, c.neckYaw ?? 0)
  rotate(d.head, 0, c.pitch)
  rotate(d.head, 1, c.yaw)
  rotate(d.head, 2, c.roll)
  d.tail.forEach((n, i) => {
    const taper = 0.7 + (0.3 * i) / Math.max(1, d.tail.length - 1)
    if (c.tailCurl)
      rotate(
        n,
        1,
        (c.tailCurl * (0.65 + (0.65 * i) / Math.max(1, d.tail.length - 1))) / d.tail.length,
      )
    rotate(n, 1, Math.sin(life * c.tailSpeed - i * 0.55) * c.tail * taper)
    rotate(n, 0, Math.sin(life * 1.4 - i * 0.55) * Math.min(0.055, c.tail * 0.24) * taper)
  })
  let hop = 0,
    left = c.left,
    right = c.right
  if (c.flight !== undefined && key !== 'egg') {
    const flight = applyFlight(active, c.flight, rotate)
    active.flightState = flight
    hop = flight.height
    left = right = flight.flap
    c.foldLeft = c.foldRight = 0.14 * flight.flapping * Math.sin(flight.phase - 0.65)
  } else if (c.chase !== undefined && key !== 'egg') {
    active.chaseState = applyChase(active, c.chase, rotate)
  } else if (c.prance !== undefined && key !== 'egg') {
    const j = applyJump(active, c.prance, rotate, { height: c.pranceHeight, drop: 0.065 })
    active.jumpState = j
    hop = j.hop
    left += 1.2 * j.flap
    right += 1.2 * j.flap
    if (c.pranceTravel) {
      const segment = Math.floor(c.prance / 2.8)
      const u = T.MathUtils.smoothstep(j.phase, 0.48, 1.16)
      const step = segment === 0 ? u : segment === 1 ? 1 - u : 0
      active.group.position.x = (d.scale >= 1.2 ? 0.14 : 0.24) * d.scale * step
      active.group.rotation.y = (segment % 2 ? -1 : 1) * 0.18 * j.flight
      active.group.rotation.z = (segment % 2 ? 1 : -1) * 0.075 * j.flight
    }
  } else if (c.prance !== undefined) {
    rotate(d.head, 0, 0.13 * Math.sin(t * 4.2))
    rotate(d.head, 2, 0.09 * Math.sin(t * 3.1))
  } else if (c.heart !== undefined) {
    if (key !== 'egg') active.rearState = applyRear(active, c.heart, rotate, false, true)
    else groundedBody(active, c.drop)
  } else if (c.play !== undefined && key !== 'egg') {
    active.playState = applyPlayBow(active, c.play, rotate)
  } else if (c.magic !== undefined) {
    active.magicState =
      key === 'egg' ? magicTiming(c.magic) : applyRear(active, c.magic, rotate, true)
  } else if (c.rear !== undefined && key !== 'egg') {
    active.rearState = applyRear(active, c.rear, rotate)
  } else if (c.jump !== null && key !== 'egg') {
    const j = applyJump(active, c.jump, rotate)
    active.jumpState = j
    hop = j.hop
    left = right = j.flap
  } else if (c.jump !== null) {
    rotate(d.head, 0, 0.13 * Math.sin(t * 4.5) * Math.sin(t * 0.8) ** 2)
    rotate(d.head, 2, 0.08 * Math.sin(t * 2.1))
  } else groundedBody(active, c.drop + (motion === 'hello' ? 0.009 * Math.max(0, c.pitch) : 0))
  if (key === 'egg') {
    const bounce = shellBounce(motion, t, d.scale)
    active.shellState = bounce
    active.group.position.y += bounce.height
    active.group.rotation.z += bounce.rock
    hop = bounce.height
  }
  d.wings.forEach((n, i) => {
    rotate(n, 2, i === 0 ? -left : right)
    const elbow = active.bones[num(n)].children.find((b) => b.isBone)
    if (elbow)
      rotate(
        Number(elbow.name.split('_')[1]),
        2,
        (i === 0 ? -1 : 1) * (i === 0 ? c.foldLeft : c.foldRight),
      )
  })
  active.group.updateMatrixWorld(true)
  shadow.material.opacity = Math.max(0.035, 0.13 - hop * 0.15)
  shadow.position.x = active.group.position.x
  shadow.position.z = active.group.position.z
  shadow.scale.set(1 + hop * 0.6, 0.72 + hop * 0.45, 1)
  updateStars(t)
  updateHearts(t)
}
const glowCanvas = document.createElement('canvas')
glowCanvas.width = glowCanvas.height = 64
const glowContext = glowCanvas.getContext('2d'),
  glowGradient = glowContext.createRadialGradient(32, 32, 0, 32, 32, 32)
glowGradient.addColorStop(0, 'rgba(255,255,230,1)')
glowGradient.addColorStop(0.18, 'rgba(255,223,119,.8)')
glowGradient.addColorStop(0.5, 'rgba(255,194,70,.2)')
glowGradient.addColorStop(1, 'rgba(255,194,70,0)')
glowContext.fillStyle = glowGradient
glowContext.fillRect(0, 0, 64, 64)
const glowTexture = new T.CanvasTexture(glowCanvas),
  glows = []
for (let i = 0; i < 22; i++) {
  const sprite = new T.Sprite(
    new T.SpriteMaterial({
      map: glowTexture,
      color: i % 4 ? 0xffd069 : 0xcaa9ff,
      transparent: true,
      blending: T.AdditiveBlending,
      depthWrite: false,
    }),
  )
  sprite.visible = false
  scene.add(sprite)
  glows.push(sprite)
}
const magicStar = new T.Mesh(
  new T.ExtrudeGeometry(starShape, {
    depth: 0.14,
    bevelEnabled: true,
    bevelThickness: 0.035,
    bevelSize: 0.045,
    bevelSegments: 2,
    steps: 1,
  }),
  new T.MeshStandardMaterial({
    color: 0xffd264,
    metalness: 0.5,
    roughness: 0.28,
    emissive: 0xffa52e,
    emissiveIntensity: 0.28,
  }),
)
magicStar.visible = false
scene.add(magicStar)
const magicHalo = new T.Sprite(
  new T.SpriteMaterial({
    map: glowTexture,
    color: 0xffde85,
    transparent: true,
    blending: T.AdditiveBlending,
    depthWrite: false,
  }),
)
magicHalo.visible = false
scene.add(magicHalo)
const heartShape = new T.Shape()
heartShape.moveTo(0, -0.85)
heartShape.bezierCurveTo(-0.25, -0.6, -1.05, -0.1, -0.94, 0.5)
heartShape.bezierCurveTo(-0.85, 1.04, -0.24, 1.08, 0, 0.55)
heartShape.bezierCurveTo(0.24, 1.08, 0.85, 1.04, 0.94, 0.5)
heartShape.bezierCurveTo(1.05, -0.1, 0.25, -0.6, 0, -0.85)
const heartGeometry = new T.ExtrudeGeometry(heartShape, {
  depth: 0.13,
  bevelEnabled: true,
  bevelThickness: 0.06,
  bevelSize: 0.06,
  bevelSegments: 3,
  steps: 1,
  curveSegments: 20,
})
const hearts = Array.from({ length: 11 }, (_, i) => {
  const mesh = new T.Mesh(
    heartGeometry,
    new T.MeshStandardMaterial({
      color: i % 2 ? 0xff81b1 : 0xf54d91,
      roughness: 0.35,
      emissive: 0xde286e,
      emissiveIntensity: 0.32,
      transparent: true,
      depthWrite: false,
    }),
  )
  mesh.visible = false
  scene.add(mesh)
  return mesh
})
function updateHearts(t) {
  hearts.forEach((heart) => {
    heart.visible = false
  })
  if (!active || motion !== 'heart') return
  const s = active.def.scale
  const envelope = T.MathUtils.smoothstep(t, 1, 1.9) * (1 - T.MathUtils.smoothstep(t, 5.1, 6.3))
  const origin = magicOrigin().add(new T.Vector3(0, 0.08 * s, 0.18 * s))
  const main = hearts[0]
  main.visible = envelope > 0
  main.position.copy(origin)
  main.position.y += 0.025 * s * Math.sin(t * 3.1)
  main.quaternion.copy(camera.quaternion)
  main.rotateY(0.18 * Math.sin(t * 2))
  main.rotateZ(0.07 * Math.sin(t * 1.8))
  main.scale.setScalar(0.17 * s * envelope * (1 + 0.065 * Math.sin(t * 5)))
  main.material.opacity = envelope
  for (let i = 1; i < hearts.length; i++) {
    const age = t - 1.8 - (i - 1) * 0.27
    if (age <= 0 || age >= 2.1) continue
    const heart = hearts[i]
    const fade = Math.sin((Math.PI * age) / 2.1)
    heart.visible = true
    heart.position
      .copy(origin)
      .add(
        new T.Vector3(
          s * ((i % 2 ? 1 : -1) * (0.1 + age * 0.13) + 0.035 * Math.sin(age * 4 + i)),
          s * (0.08 + age * 0.35),
          0.04 * s * Math.sin(age * 2 + i),
        ),
      )
    heart.quaternion.copy(camera.quaternion)
    heart.rotateZ(0.25 * Math.sin(age * 2 + i))
    heart.scale.setScalar(s * (0.038 + (i % 3) * 0.009) * fade)
    heart.material.opacity = fade * 0.85
  }
}
function magicOrigin() {
  let paws
  if (active.jump) {
    paws = active.jump.legs.slice(0, 2).map((l) => l.foot.getWorldPosition(new T.Vector3()))
  } else {
    paws = [active.bones.Bone_020, active.bones.Bone_024].map((b) =>
      b.getWorldPosition(new T.Vector3()),
    )
  }
  const s = active.def.scale
  return paws[0]
    .add(paws[1])
    .multiplyScalar(0.5)
    .add(new T.Vector3(0, 0.13 * s, 0.12 * s))
}
function updateStars(t) {
  if (!active) return
  const enabled = motion === 'stars',
    s = active.def.scale,
    phase = magicTiming(t),
    origin = enabled ? magicOrigin() : new T.Vector3()
  const center = origin
    .clone()
    .add(
      new T.Vector3(
        0.5 * s * phase.float + 0.025 * Math.sin(phase.phase * 2) * phase.float,
        0.75 * s * phase.float,
        0.2 * s * phase.float,
      ),
    )
  const forming = enabled && phase.phase > 1.1 && phase.phase < 4.85,
    bursting = enabled && phase.phase >= 4.85 && phase.phase < 7.15
  magicStar.visible = forming
  magicHalo.visible = forming
  if (forming) {
    magicStar.position.copy(center)
    magicStar.scale.setScalar(s * 0.14 * phase.form * (1 + 0.055 * Math.sin(phase.phase * 5)))
    magicStar.quaternion.copy(camera.quaternion)
    magicStar.rotateY(0.25 * Math.sin(phase.phase * 1.4))
    magicStar.rotateZ(0.12 * Math.sin(phase.phase * 1.2))
    magicHalo.position.copy(center)
    magicHalo.scale.setScalar(s * 0.52 * phase.form)
    magicHalo.material.opacity = 0.42 + 0.06 * Math.sin(phase.phase * 4)
  }
  for (let i = 0; i < particles.length; i++) {
    const { mesh } = particles[i],
      angle = i * 2.399963,
      seed = ((i * 17) % 97) / 97
    mesh.visible = false
    if (forming && phase.form > 0.08 && i < 36) {
      const orbit = phase.phase * 1.7 + i * 0.28,
        radius = s * (0.11 + 0.04 * Math.sin(i))
      mesh.visible = true
      mesh.position
        .copy(center)
        .add(
          new T.Vector3(
            Math.cos(orbit) * radius,
            Math.sin(orbit) * radius,
            Math.sin(orbit * 0.8) * radius * 0.4,
          ),
        )
      mesh.scale.setScalar(s * 0.012 * phase.form)
      mesh.material.opacity = 0.45 + 0.25 * Math.sin(orbit) ** 2
    } else if (bursting) {
      const age = phase.burst,
        delay = seed * 0.16,
        a = Math.max(0, age - delay),
        lifetime = 1.65 + seed * 0.5
      if (a > lifetime || age < delay) continue
      const vertical = ((i % 17) / 16) * 1.4 - 0.35,
        speed = s * (0.32 + seed * 0.48)
      mesh.visible = true
      mesh.position
        .copy(center)
        .add(
          new T.Vector3(
            Math.cos(angle) * speed * a,
            (0.28 + vertical) * s * a - 0.48 * s * a * a,
            Math.sin(angle) * speed * a * 0.65,
          ),
        )
      mesh.scale.setScalar(
        s * (0.02 + (i % 5) * 0.006) * Math.sin(Math.PI * Math.min(1, a / lifetime)) ** 0.5,
      )
      mesh.material.opacity = Math.min(1, a * 12) * (1 - a / lifetime)
    }
    if (mesh.visible) {
      mesh.quaternion.copy(camera.quaternion)
      mesh.rotateZ(angle + t * (i % 2 ? 1.5 : -1.5))
    }
  }
  for (let i = 0; i < glows.length; i++) {
    const sprite = glows[i]
    sprite.visible = false
    if (!bursting) continue
    const age = phase.burst,
      lifetime = 1.4 + (i % 5) * 0.13
    if (age > lifetime) continue
    const angle = i * 2.399963,
      speed = s * (0.25 + (i % 6) * 0.07)
    sprite.visible = true
    sprite.position
      .copy(center)
      .add(
        new T.Vector3(
          Math.cos(angle) * speed * age,
          0.3 * s * age - 0.38 * s * age * age,
          Math.sin(angle) * speed * age * 0.65,
        ),
      )
    sprite.scale.setScalar(s * 0.12 * (1 - age / lifetime))
    sprite.material.opacity = 0.42 * (1 - age / lifetime)
  }
  active.particleStats = {
    stars: particles.filter((p) => p.mesh.visible).length,
    glows: glows.filter((p) => p.visible).length,
    mainStar: magicStar.visible,
    origin: origin.toArray(),
    center: center.toArray(),
  }
}
function capturePose() {
  if (!active) return null
  return {
    quaternions: Object.fromEntries(
      Object.entries(active.bones).map(([n, b]) => [n, b.quaternion.clone()]),
    ),
    root: active.jump?.root.position.clone(),
    position: active.group.position.clone(),
    orientation: active.group.quaternion.clone(),
  }
}
function blendTransition(alpha) {
  if (!transition || !active) return
  const a = alpha * alpha * (3 - 2 * alpha)
  for (const n in transition.quaternions) {
    const target = active.bones[n].quaternion.clone()
    active.bones[n].quaternion.copy(transition.quaternions[n]).slerp(target, a)
  }
  if (transition.root && active.jump) {
    const target = active.jump.root.position.clone()
    active.jump.root.position.copy(transition.root).lerp(target, a)
  }
  const targetPosition = active.group.position.clone()
  const targetOrientation = active.group.quaternion.clone()
  active.group.position.copy(transition.position).lerp(targetPosition, a)
  active.group.quaternion.copy(transition.orientation).slerp(targetOrientation, a)
  active.group.updateMatrixWorld(true)
  updateStars(clock)
}
function setMotion(m) {
  if (['fly', 'chase', 'play'].includes(m) && key === 'egg') m = 'hello'
  renderer.domElement.dataset.model = key
  renderer.domElement.dataset.motion = m
  transition = capturePose()
  transitionAge = 0
  motion = m
  clock = 0
  if (m === 'idle') idleVariationAt = 1.9 + Math.random() * 0.7
  view()
  const labels = {
    idle:
      key === 'egg'
        ? 'Lebendig · Atmen und Umschauen'
        : 'Lebendig · Atmen, Umschauen und Schwanzwedeln',
    hello:
      key === 'egg'
        ? 'Hallo! · Fröhliches Kopfnicken'
        : 'Hallo! · Nicken und mit einem Flügel winken',
    happy:
      key === 'egg'
        ? 'Freude · aufgeregtes Kopfwackeln'
        : 'Freude · Einfedern, Absprung und weiche Landung',
    curious: 'Neugierig · Kopf neigen und aufmerksam umschauen',
    wings: 'Flügelprobe · kräftiger Flügelschlag',
    rear: 'Aufbäumen · aufrichten und mit den Vorderpfoten tänzeln',
    stars: 'Sternenzauber · einen Stern formen, aufsteigen lassen und funkeln',
    heart: 'Herzmoment · ein Herz halten und ihm nachschauen',
    play: 'Spiel mit mir · ducken, mit den Pfoten tapsen und Schwanz wedeln',
  }
  caption.textContent = labels[m]
  document
    .querySelectorAll('[data-motion]')
    .forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.motion === m)))
  pose(0)
}
// The embedded view has no API access; the parent owns actions and progression.
host.onclick = () => parent.postMessage({ type: 'dragon-tap' }, location.origin)
let externallyPaused = false
let parentReaction = null
let parentSequence = null
let parentModel = null
let reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
const media = matchMedia('(prefers-reduced-motion: reduce)')
paused = reduced || externallyPaused
renderer.domElement.dataset.reduced = String(reduced)
media.addEventListener('change', () => {
  reduced = media.matches
  renderer.domElement.dataset.reduced = String(reduced)
  paused = reduced || externallyPaused
  setMotion('idle')
  transition = null
  pose(0, 0)
  renderer.render(scene, camera)
})
addEventListener('message', async (e) => {
  if (e.origin !== location.origin || e.source !== parent) return
  if (e.data?.type === 'dragon-action') {
    reduced = media.matches
    paused = externallyPaused || reduced
    if (['heart', 'play', 'fly', 'stretch', 'lookback', 'sway', 'chase'].includes(e.data.motion)) {
      setMotion(e.data.motion)
      if (paused || reduced) {
        transition = null
        pose(0, 0)
        renderer.render(scene, camera)
      }
    }
    return
  }
  if (e.data?.type !== 'dragon-state') return
  const state = e.data
  externallyPaused = state.paused === true
  paused = externallyPaused || reduced
  const reaction = `${state.model}:${state.motion}:${state.sequence}`
  if (Object.hasOwn(defs, state.model) && state.model !== key) await select(state.model)
  if (
    reaction !== parentReaction &&
    ['idle', 'hello', 'curious', 'wings', 'happy', 'rear', 'stars', 'sad', 'heart'].includes(
      state.motion,
    )
  ) {
    const fresh = state.sequence !== parentSequence || state.model !== parentModel
    parentReaction = reaction
    parentSequence = state.sequence
    parentModel = state.model
    const manual = ['heart', 'play', 'fly', 'stretch', 'lookback', 'sway', 'chase'].includes(motion)
    // Finishing an older event must not cancel a newer manual action.
    if (fresh || state.motion !== 'idle' || !manual) {
      setMotion(state.motion === 'rear' && key === 'egg' ? 'hello' : state.motion)
    }
  }
  // Visibility changes suspend the current pose, without restarting a manual flight.
  if (reduced) {
    transition = null
    pose(0, 0)
    renderer.render(scene, camera)
  }
})
renderer.domElement.addEventListener('webglcontextlost', (e) => {
  e.preventDefault()
  parent.postMessage({ type: 'dragon-error' }, location.origin)
})
new ResizeObserver(() => {
  renderer.setSize(host.clientWidth, host.clientHeight)
  camera.aspect = host.clientWidth / host.clientHeight
  camera.updateProjectionMatrix()
  view(true)
  renderer.render(scene, camera)
}).observe(host)
renderer.setAnimationLoop((now) => {
  const dt = last ? Math.min((now - last) / 1000, 0.06) : 0
  last = now
  if (document.hidden || paused) return
  if (!paused) {
    clock += dt
    lifeClock += dt
    const durations = {
      idle: 5,
      hello: 6.8,
      curious: 9.6,
      wings: 6.4,
      happy: 6,
      rear: 6.8,
      heart: 6.8,
      play: 6.8,
      stars: 8.8,
      sad: 5,
      fly: 10.4,
      chase: 10,
      stretch: 6,
      lookback: 6.2,
      sway: 6,
    }
    if (motion !== 'idle' && clock >= durations[motion]) setMotion('idle')
    else if (motion === 'idle' && clock >= idleVariationAt) {
      const choices =
        key === 'egg'
          ? ['sway', 'hello', 'happy', 'stretch', 'curious']
          : [
              'sway',
              'play',
              'happy',
              'wings',
              'hello',
              'chase',
              'rear',
              'fly',
              'stretch',
              'lookback',
            ]
      setMotion(choices[idleActionIndex++ % choices.length])
    }
    pose(clock, lifeClock)
    if (transition) {
      transitionAge += dt
      const alpha = Math.min(1, transitionAge / 0.45)
      blendTransition(alpha)
      if (alpha === 1) transition = null
    }
  }
  view()
  renderer.render(scene, camera)
})
const requestedMotion = new URLSearchParams(location.search).get('motion')
if (['idle', 'hello', 'curious', 'wings', 'happy', 'rear', 'stars'].includes(requestedMotion))
  motion = requestedMotion
const requestedModel = new URLSearchParams(location.search).get('model')
select(Object.hasOwn(defs, requestedModel) ? requestedModel : 'baby')
view(true)

addEventListener('pagehide', () => {
  renderer.setAnimationLoop(null)
  active = null
  trimCache(0)
  scene.traverse((o) => {
    o.geometry?.dispose()
    if (o.material) {
      for (const m of Array.isArray(o.material) ? o.material : [o.material]) m.dispose()
    }
  })
  glowTexture.dispose()
  renderer.dispose()
})

export function sampleAnimation(action, time) {
  if (!active) throw new Error('Model not ready')
  paused = true
  setMotion(action)
  transition = null
  pose(time, time)
  view(true)
  renderer.render(scene, camera)
  const bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity }
  let finite = true
  const point = new T.Vector3()
  for (const skin of [...active.skins, ...hearts.filter((heart) => heart.visible)]) {
    const count = skin.geometry.attributes.position.count
    for (let index = 0; index < count; index++) {
      skin.getVertexPosition(index, point).applyMatrix4(skin.matrixWorld)
      finite &&= Number.isFinite(point.x + point.y + point.z)
      point.project(camera)
      bounds.minX = Math.min(bounds.minX, point.x)
      bounds.maxX = Math.max(bounds.maxX, point.x)
      bounds.minY = Math.min(bounds.minY, point.y)
      bounds.maxY = Math.max(bounds.maxY, point.y)
    }
  }
  return {
    key,
    action: motion,
    position: active.group.position.toArray(),
    flight: active.flightState,
    jump: active.jumpState,
    chase: active.chaseState,
    play: active.playState,
    shell: active.shellState,
    heart: { visible: hearts[0].visible, small: hearts.slice(1).filter((h) => h.visible).length },
    shellPaws:
      key === 'egg'
        ? [19, 23].map((n) => active.bones[num(n)].getWorldPosition(new T.Vector3()).toArray())
        : null,
    finite,
    bounds,
    feet: active.jump?.legs.map((leg) => leg.foot.getWorldPosition(new T.Vector3()).toArray()),
    anchors: active.jump?.legs.map((leg) => [
      leg.anchor.x + active.group.position.x,
      leg.anchor.y,
      leg.anchor.z + active.group.position.z,
    ]),
  }
}

export function animationStatus() {
  return {
    motion,
    clock,
    lifeClock,
    paused,
    reduced,
    externallyPaused,
    hidden: document.hidden,
    camera: camera.position.toArray(),
    position: active?.group.position.toArray(),
  }
}
