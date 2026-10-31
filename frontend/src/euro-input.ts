/** Parse decimal user input into integer cents without floating point rounding. */
export function euroCents(value: string): number | null {
  if (value.trim() === '') return 0
  const match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(value.trim())
  if (!match) return null
  const cents = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'))
  return Number.isSafeInteger(cents) && cents <= 100_000 ? cents : null
}

export function euroInput(cents: number): string {
  return `${Math.floor(cents / 100)},${String(cents % 100).padStart(2, '0')}`
}
