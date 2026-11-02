import { expect, it } from 'vitest'
import { euroCents, euroInput } from './euro-input'

it('converts German or English decimal amounts to exact integer cents', () => {
  expect(euroCents('0,50')).toBe(50)
  expect(euroCents('3.50')).toBe(350)
  expect(euroCents('5')).toBe(500)
  expect(euroCents('0.29')).toBe(29)
  expect(euroCents('')).toBe(0)
  expect(euroInput(350)).toBe('3,50')
  expect(euroInput(1)).toBe('0,01')
})
it('rejects negative, excessive, incomplete and overprecise amounts', () => {
  for (const input of ['-1', '1000,01', '0.001', '1e2', '1.', '1,', 'NaN', '1,2.3']) {
    expect(euroCents(input)).toBeNull()
  }
})
