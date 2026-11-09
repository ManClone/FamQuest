export { prepareShellPaws } from './shell-bind.js'

const ease = (value) => {
  const x = Math.max(0, Math.min(1, value))
  return x * x * (3 - 2 * x)
}
const hold = (t, start, raised, release, end) =>
  ease((t - start) / (raised - start)) * (1 - ease((t - release) / (end - release)))

// Only the two front-arm chains move. Pelvis, shell and hidden hind legs stay at rest.
// The shoulder starts each gesture; the elbow and wrist follow with a small delay.
export function applyShellPaws(mode, t, life, rotate) {
  const awake = !['sad', 'calm'].includes(mode)
  const settle = ease(t / 0.45)
  for (const [i, chain] of [
    [22, 21, 20],
    [26, 25, 24],
  ].entries()) {
    const side = i === 0 ? -1 : 1
    const beat = (life + i * 1.25) % 4.2
    const tap = awake ? hold(beat, 0.25, 0.65, 0.9, 1.4) * settle : 0
    let lift = 0.15 * tap
    let bend = 0.23 * tap
    let spread = 0.025 * Math.sin(life * 1.8 + i)
    let wrist = 0.1 * tap
    if (mode === 'hello' && i === 1) {
      const greeting = hold(t, 0.35, 1.2, 3.4, 4.6)
      lift += 0.8 * greeting
      bend += 0.8 * hold(t, 0.5, 1.4, 3.4, 4.8)
      spread += 0.32 * greeting
      wrist += 0.28 * greeting * Math.sin((t - 1.2) * 6.5)
    } else if (mode === 'happy' || mode === 'sway') {
      const joy = hold(t % 6, 0.1, 0.65, 3.8, 5.4)
      const pat = 0.5 + 0.5 * Math.sin(t * 5.2 + i * 0.7)
      lift += joy * (0.3 + 0.17 * pat)
      bend += joy * (0.38 + 0.16 * Math.sin(t * 5.2 - 0.4 + i * 0.7))
      spread += 0.13 * joy
      wrist += 0.15 * joy * Math.sin(t * 5.2 - 0.8 + i * 0.7)
    } else if (mode === 'heart' || mode === 'stars') {
      const cuddle = hold(t, 0.3, 1.25, mode === 'heart' ? 4.6 : 6.2, mode === 'heart' ? 6.3 : 8.3)
      lift += 0.38 * cuddle
      bend += 0.55 * cuddle
      spread -= 0.06 * cuddle
      wrist += 0.1 * cuddle * Math.sin(t * 2.4 + i * 0.3)
    } else if (mode === 'stretch' || mode === 'wings') {
      const reach = hold(t, 0.2, 1.4, 3.2, 5.5)
      lift += 0.45 * reach
      bend += 0.35 * reach
      spread += 0.18 * reach
    } else if (mode === 'curious') {
      const wonder = hold(t, 0.6 + i * 3.3, 1.4 + i * 3.3, 2.1 + i * 3.3, 3 + i * 3.3)
      lift += 0.28 * wonder
      bend += 0.4 * wonder
    }
    rotate(chain[0], 0, -lift * 0.75)
    rotate(chain[0], 2, side * spread * settle)
    rotate(chain[1], 0, -bend * 0.65)
    rotate(chain[2], 0, -0.3 * bend - 0.15 * tap)
    rotate(chain[2], 2, side * wrist)
  }
}

// Move the whole shell and dragon together: no hidden legs or detached shell.
export function shellBounce(mode, t, scale) {
  const jumps =
    mode === 'happy'
      ? [
          [0.45, 0.75, 0.24],
          [1.8, 0.85, 0.3],
          [3.3, 0.7, 0.2],
        ]
      : mode === 'sway'
        ? [
            [0.8, 0.7, 0.12],
            [2.3, 0.8, 0.16],
          ]
        : mode === 'hello'
          ? [[0.35, 0.7, 0.09]]
          : mode === 'idle'
            ? [[0.85, 0.55, 0.045]]
            : []
  let height = 0,
    rock = 0
  for (const [start, duration, peak] of jumps) {
    const u = (t - start) / duration
    if (u >= 0 && u <= 1) {
      height += 4 * u * (1 - u) * peak * scale
      rock += 0.065 * Math.sin(Math.PI * u) * Math.sin(t * 5)
    }
    const anticipation = hold(t, start - 0.25, start - 0.1, start - 0.05, start)
    rock += 0.04 * anticipation
    const landed = t - start - duration
    if (landed > 0 && landed < 0.65)
      rock += 0.055 * Math.sin(landed * 18) * Math.exp(-landed * 7) * (1 - ease(landed / 0.65))
  }
  return { height, rock }
}
