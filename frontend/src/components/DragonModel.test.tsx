import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { DragonModel } from './DragonModel'

beforeEach(async () => {
  await i18n.changeLanguage('de')
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function message(frame: HTMLIFrameElement, type: string, origin = location.origin) {
  act(() =>
    window.dispatchEvent(
      new MessageEvent('message', {
        origin,
        source: frame.contentWindow,
        data: { type },
      }),
    ),
  )
}

it.each([
  [1, 'egg'],
  [5, 'egg'],
  [6, 'baby'],
  [19, 'baby'],
  [20, 'two'],
  [29, 'three'],
  [36, 'four'],
  [42, 'five'],
  [48, 'bridge'],
  [53, 'six'],
  [58, 'seven'],
  [62, 'eight'],
  [66, 'nine'],
  [70, 'ten'],
])('loads level %i as %s', (level, model) => {
  render(<DragonModel level={Number(level)} onError={vi.fn()} />)
  expect(screen.getByTitle('Dein Drache in 3D')).toHaveAttribute(
    'src',
    `/dragon3d/index.html?model=${model}`,
  )
})

it('waits for the trusted viewer, sends initial state, supports play and tap, and remounts on growth', () => {
  const fail = vi.fn()
  const { rerender } = render(<DragonModel level={1} onError={fail} />)
  const frame = screen.getByTitle('Dein Drache in 3D') as HTMLIFrameElement
  const send = vi.spyOn(frame.contentWindow!, 'postMessage')
  expect(screen.getByRole('button', { name: 'Spielen' })).toBeDisabled()
  message(frame, 'dragon-ready', 'https://untrusted.example')
  expect(screen.getByRole('button')).toBeDisabled()
  message(frame, 'dragon-ready')
  expect(send).toHaveBeenCalledWith(
    { type: 'dragon-state', model: 'egg', paused: false },
    location.origin,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Spielen' }))
  expect(send).toHaveBeenLastCalledWith({ type: 'dragon-action', motion: 'heart' }, location.origin)
  rerender(<DragonModel level={6} onError={fail} />)
  const baby = screen.getByTitle('Dein Drache in 3D') as HTMLIFrameElement
  expect(baby).not.toBe(frame)
  const babySend = vi.spyOn(baby.contentWindow!, 'postMessage')
  message(baby, 'dragon-ready')
  message(baby, 'dragon-tap')
  expect(babySend).toHaveBeenLastCalledWith(
    { type: 'dragon-action', motion: 'play' },
    location.origin,
  )
})

it('reports viewer errors and a timed out load, cleaning the timeout after readiness', () => {
  vi.useFakeTimers()
  const fail = vi.fn()
  const { unmount } = render(<DragonModel level={6} onError={fail} />)
  const frame = screen.getByTitle('Dein Drache in 3D') as HTMLIFrameElement
  message(frame, 'dragon-error')
  expect(fail).toHaveBeenCalledOnce()
  fail.mockClear()
  message(frame, 'dragon-ready')
  act(() => vi.advanceTimersByTime(45000))
  expect(fail).not.toHaveBeenCalled()
  unmount()
  render(<DragonModel level={6} onError={fail} />)
  act(() => vi.advanceTimersByTime(45000))
  expect(fail).toHaveBeenCalledOnce()
})

it('pauses offscreen and hidden viewers without restarting the model', () => {
  let observe!: (entries: { isIntersecting: boolean }[]) => void
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback: typeof observe) {
        observe = callback
      }
      observe() {}
      disconnect() {}
    },
  )
  render(<DragonModel level={6} onError={vi.fn()} />)
  const frame = screen.getByTitle('Dein Drache in 3D') as HTMLIFrameElement
  const send = vi.spyOn(frame.contentWindow!, 'postMessage')
  message(frame, 'dragon-ready')
  act(() => observe([{ isIntersecting: false }]))
  expect(send).toHaveBeenLastCalledWith(
    { type: 'dragon-state', model: 'baby', paused: true },
    location.origin,
  )
  act(() => observe([{ isIntersecting: true }]))
  expect(send).toHaveBeenLastCalledWith(
    { type: 'dragon-state', model: 'baby', paused: false },
    location.origin,
  )
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  fireEvent(document, new Event('visibilitychange'))
  expect(send).toHaveBeenLastCalledWith(
    { type: 'dragon-state', model: 'baby', paused: true },
    location.origin,
  )
  hidden.mockRestore()
})
