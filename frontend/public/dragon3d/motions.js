const clamp = (x) => Math.max(0, Math.min(1, x))
const ease = (x) => {
  x = clamp(x)
  return x * x * x * (x * (x * 6 - 15) + 10)
}
const pulse = (t, a, b, c, d) => ease((t - a) / (b - a)) * (1 - ease((t - c) / (d - c)))

// Held poses and pauses give each action an intention, rather than perpetual wobbling.
export function channels(mode, t, life = t, youth = 1) {
  const breathe = Math.sin(life * 1.65) + 0.22 * Math.sin(life * 2.83 + 0.7)
  const stretch = pulse(life % 17, 10, 11.1, 11.7, 13.4)
  const c = {
    pitch: 0.027 * breathe - 0.045 * stretch,
    yaw: 0.012 * Math.sin(life * 0.61),
    roll: 0.01 * Math.sin(life * 0.73 + 0.4),
    neck: 0.024 * breathe,
    left: 0.025 * breathe + 0.2 * stretch,
    right: 0.025 * breathe + 0.155 * stretch,
    foldLeft: 0,
    foldRight: 0,
    tail: 0.14,
    tailSpeed: 1.65,
    drop: 0.006 * (0.5 + (0.5 * breathe) / 1.22),
    star: 0,
    jump: null,
  }
  const gain = ease(t / 0.38)
  if (mode === 'idle') {
    c.prance = t
    c.pranceHeight = 0.17
    const beat = life % 7.2
    const bounce = pulse(beat, 0.2, 0.6, 2.0, 2.6)
    const flutter = pulse(beat, 0.3, 0.6, 1.35, 1.8)
    const peek = pulse(beat, 4.3, 4.9, 5.8, 6.8)
    c.drop += 0.075 * bounce * (0.5 + 0.5 * Math.sin(life * 7))
    c.pitch += 0.095 * bounce * Math.sin(life * 3.5 - 0.4) - 0.1 * peek
    c.neck += 0.05 * bounce * Math.sin(life * 3.5 - 0.7) - 0.06 * peek
    c.yaw += 0.015 * Math.sin(life * 1.25)
    c.roll += 0.015 * Math.sin(life * 1.7 + 0.5)
    c.left += 0.32 * flutter * Math.sin(life * 6)
    c.right += 0.29 * flutter * Math.sin(life * 6 + 0.15)
    c.foldLeft = 0.09 * flutter * Math.sin(life * 6 - 0.5)
    c.foldRight = 0.08 * flutter * Math.sin(life * 6 - 0.35)
    c.tail = 0.25
    c.tailSpeed = 2.5
  } else if (mode === 'heart') {
    const affection = pulse(t, 0.2, 1.3, 4.5, 6.3)
    c.heart = t
    c.pitch -= 0.1 * affection
    c.neck -= 0.045 * affection
    c.yaw = 0.08 * affection * Math.sin(t * 1.8)
    c.roll = 0.08 * affection * Math.sin(t * 1.4)
    c.left += 0.19 * affection + 0.055 * affection * Math.sin(t * 3)
    c.right += 0.19 * affection + 0.055 * affection * Math.sin(t * 3 + 0.25)
    c.tail = 0.2
    c.tailSpeed = 2.8
  } else if (mode === 'play') {
    const invitation = pulse(t, 0.1, 1, 4.9, 6.5)
    c.play = t
    c.yaw = 0.11 * invitation * Math.sin(t * 2.3)
    c.roll = 0.035 * invitation * Math.sin(t * 2.3)
    c.left += 0.12 * invitation
    c.right += 0.12 * invitation
    c.tail = 0.34
    c.tailSpeed = 5
  } else if (mode === 'chase') {
    const watch = pulse(t, 0.1, 0.7, 8.1, 9.5)
    c.chase = t
    c.yaw = 0.46 * watch
    c.neckYaw = 0.3 * watch
    c.roll = 0.035 * watch
    c.pitch -= 0.06 * watch
    c.tailCurl = -1.95 * watch
    c.tail = 0.13 * watch
    c.tailSpeed = 4.2
    c.left += 0.13 * watch
    c.right += 0.08 * watch
  } else if (mode === 'fly') {
    c.flight = t
    c.yaw *= 0.3
    c.roll *= 0.3
    c.tail = 0.09
    c.tailSpeed = 1.6
  } else if (mode === 'stretch') {
    const reach = pulse(t, 0.2, 1.7, 3.1, 5.5)
    c.neck -= 0.15 * reach
    c.pitch -= 0.13 * reach
    c.left += 0.57 * reach
    c.right += 0.46 * reach
    c.foldLeft = 0.11 * reach
    c.foldRight = 0.075 * reach
    c.drop += 0.05 * reach
    c.tail = 0.18
    c.tailSpeed = 1.2
  } else if (mode === 'lookback') {
    const left = pulse(t, 0.15, 0.85, 1.7, 2.6)
    const right = pulse(t, 2.6, 3.35, 4.3, 5.8)
    c.yaw += 0.6 * (left - right)
    c.roll += 0.18 * (left - right)
    c.neck += 0.045 * (left + right)
    c.pitch -= 0.055 * (left + right)
    c.tail = 0.22
    c.tailSpeed = 2
  } else if (mode === 'sway') {
    c.prance = t
    c.pranceHeight = 0.24
    c.pranceTravel = true
    const play = pulse(t, 0.15, 0.8, 4.4, 5.8)
    c.drop += 0.08 * play * (0.5 + 0.5 * Math.sin(t * 4.1))
    c.pitch += 0.2 * play * Math.sin(t * 2.05)
    c.roll += 0.13 * play * Math.sin(t * 2.05 + 0.6)
    c.left += 0.22 * play * Math.sin(t * 4.1)
    c.right += 0.18 * play * Math.sin(t * 4.1 + 0.4)
    c.tail = 0.28
    c.tailSpeed = 3.2
  } else if (mode === 'hello') {
    const p = t % 6.8,
      bow = pulse(p, 0, 0.55, 0.85, 1.5),
      wave = pulse(p, 1, 1.45, 3.1, 3.8),
      lift = pulse(p, 1, 1.5, 3.2, 4.1)
    c.pitch += gain * (0.18 * bow - 0.055 * lift)
    c.neck += gain * 0.085 * bow
    c.yaw *= 0.3
    c.roll += gain * 0.11 * Math.sin(p * 2) * lift
    c.left += gain * (0.32 * lift + 0.48 * wave * Math.sin((p - 1.1) * 7))
    c.right += gain * 0.12 * lift
    c.foldLeft = 0.08 * wave * Math.sin((p - 1.25) * 7)
    c.tail = 0.23
    c.tailSpeed = 3.2
    c.drop += 0.04 * bow
  } else if (mode === 'curious') {
    const p = t % 9.6,
      left = pulse(p, 0.2, 1.1, 2.2, 3.6),
      right = pulse(p, 3.4, 4.5, 5.7, 7.2),
      sniff = pulse(p, 7, 7.7, 8, 9.1)
    c.yaw += gain * (0.58 * left - 0.55 * right)
    c.roll += gain * (0.22 * left - 0.19 * right)
    c.pitch -= gain * (0.04 * (left + right) + 0.1 * sniff)
    c.neck -= gain * 0.055 * sniff
    c.tail = 0.13
    c.left *= 0.5
    c.right *= 0.5
  } else if (mode === 'wings') {
    const p = t % 6.4,
      envelope = pulse(p, 0.25, 1, 4.1, 5.4),
      phase = (p - 0.7) * 4.8
    // A quick downstroke and a longer recovery, with a small delayed bend at the elbow.
    const stroke = Math.sin(phase) + 0.22 * Math.sin(2 * phase + 0.5)
    c.left += gain * envelope * (0.65 * stroke + 0.04)
    c.right += gain * envelope * (0.65 * stroke + 0.04)
    c.foldLeft = c.foldRight = 0.105 * envelope * Math.sin(phase - 0.6)
    c.neck += 0.06 * envelope
    c.drop += 0.055 * envelope * (0.5 + 0.5 * Math.sin(phase))
    c.pitch -= 0.07 * envelope
    c.tail = 0.055
    c.tailSpeed = 1.7
  } else if (mode === 'happy') {
    c.jump = t * (0.92 + 0.12 * youth)
    c.tail = 0.2
    c.tailSpeed = 3.5
    c.roll *= 0.4
  } else if (mode === 'rear') {
    c.yaw *= 0.25
    c.roll *= 0.3
    c.tail = 0.065
    c.tailSpeed = 1.7
    c.rear = t
    const support = pulse(t % 6.8, 0.25, 1.35, 4.2, 5.5)
    c.left += 0.18 * support
    c.right += 0.18 * support
    c.foldLeft = c.foldRight = 0.035 * support
  } else if (mode === 'stars') {
    const p = t % 8.8,
      support = pulse(p, 0.25, 1.3, 6.2, 7.65),
      follow = pulse(p, 2.7, 4.5, 5.6, 6.7)
    c.magic = t
    c.pitch += 0.055 * support - 0.15 * follow
    c.neck -= 0.045 * follow
    c.yaw = c.yaw * 0.1 + 0.1 * follow
    c.roll *= 0.15
    c.left += 0.14 * support + 0.045 * follow
    c.right += 0.14 * support + 0.045 * follow
    c.foldLeft = c.foldRight = 0.03 * support
    c.tail = 0.04
    c.tailSpeed = 1.15
  }
  // Turn toward a point, hold the look, then attend to the other side.
  if (['idle', 'sway', 'hello', 'happy', 'wings', 'stretch'].includes(mode)) {
    const attention = life % 12
    const scan = pulse(attention, 3.2, 3.65, 4, 4.5) - pulse(attention, 8.2, 8.65, 9, 9.5)
    c.yaw += 0.22 * scan
    c.roll += 0.025 * scan
  }
  if (!['fly', 'stars', 'rear', 'calm', 'chase'].includes(mode)) {
    const look = Math.max(-0.72, Math.min(0.72, c.yaw))
    c.roll *= 0.35
    c.neckYaw = 0.23 * look
    c.yaw = 0.77 * look
  }
  c.tail *= youth
  return c
}
