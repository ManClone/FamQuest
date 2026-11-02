import { afterEach, expect, it, vi } from 'vitest'
import { newRequestKey } from './request-key'

afterEach(() => vi.unstubAllGlobals())

it('creates the full action key even when randomUUID is unavailable', () => {
  vi.stubGlobal('crypto', {
    getRandomValues: (bytes: Uint8Array) => {
      expect(bytes.length).toBe(16)
      bytes.forEach((_, index) => {
        bytes[index] = index
      })
      return bytes
    },
  })
  expect(newRequestKey()).toBe('000102030405060708090a0b0c0d0e0f')
})
