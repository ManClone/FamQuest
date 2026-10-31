import { describe, expect, it } from 'vitest'
import { oauthReturnPath } from './oauth-return'

describe('OAuth login continuation', () => {
  it('keeps the local consent request and its client state', () => {
    const target = '/authorize?client_id=abc&state=some%2Bstate'
    expect(oauthReturnPath(`?next=${encodeURIComponent(target)}`)).toBe(target)
  })
  it('rejects other pages, external destinations and ambiguous paths', () => {
    for (const value of [
      '//evil.invalid/authorize?x=1',
      'https://evil.invalid/authorize?x=1',
      '/settings',
      '/authorize/../settings?x=1',
      '/authorize?x=1\\evil',
      '/authorize?x=1\n',
    ]) {
      expect(oauthReturnPath(`?next=${encodeURIComponent(value)}`)).toBeNull()
    }
    expect(oauthReturnPath('')).toBeNull()
  })
})
