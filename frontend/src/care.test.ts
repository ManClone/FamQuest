import { describe, expect, it } from 'vitest'

import { careShares } from './care'
import { makeMember } from './test/utils'

const mama = makeMember({ id: 1, name: 'Mama', role: 'parent', color: 'blue' })
const papa = makeMember({ id: 2, name: 'Papa', role: 'parent', color: 'orange' })
const oma = makeMember({ id: 3, name: 'Oma', role: 'parent', color: 'teal' })
const lena = makeMember({ id: 4, name: 'Lena' })
const tom = makeMember({ id: 5, name: 'Tom', color: 'green' })

const shares = (counts: Record<number, number>) =>
  Object.entries(counts).map(([id, count]) => ({
    member_id: Number(id),
    count,
    estimated_minutes: count,
  }))

describe('Faire Verteilung', () => {
  it('teilt den Putzplan unter denen auf, die etwas erledigt haben', () => {
    const result = careShares([mama, papa, lena, tom], shares({ 1: 6, 2: 9, 4: 5 }))
    // Tom hat nichts gemacht und ist ein Kind: Er steht nicht dabei.
    expect(result?.map((share) => [share.member.name, share.minutes, share.percent])).toEqual([
      ['Mama', 6, 40],
      ['Papa', 9, 60],
      ['Lena', 5, 0],
    ])
  })

  it('zeigt Erwachsene auch mit 0 und ergibt zusammen immer 100 Prozent', () => {
    expect(
      careShares([mama, papa, oma], shares({ 1: 1, 2: 1, 3: 1 }))?.map((share) => share.percent),
    ).toEqual([34, 33, 33])
    expect(careShares([mama, papa], shares({ 1: 2 }))?.map((share) => share.percent)).toEqual([
      100, 0,
    ])
  })

  it('zeigt nichts, solange niemand angetippt wurde oder nur eine Person dabei ist', () => {
    expect(careShares([mama, papa], shares({}))).toBeNull()
    expect(careShares([mama, lena], shares({ 1: 5 }))).toBeNull()
  })

  it('weights time instead of execution counts and invents no time for untimed to-dos', () => {
    const result = careShares(
      [mama, papa, lena],
      [
        { member_id: 1, count: 1, estimated_minutes: 60 },
        { member_id: 2, count: 4, estimated_minutes: 20 },
        { member_id: 4, count: 10, estimated_minutes: 0 },
      ],
    )
    expect(result?.map((share) => [share.member.name, share.minutes, share.percent])).toEqual([
      ['Mama', 60, 75],
      ['Papa', 20, 25],
      ['Lena', 0, 0],
    ])
    expect(careShares([mama, papa], [{ member_id: 1, count: 20 }])).toBeNull()
  })

  it('allocates all rounding remainders and keeps child counts separate', () => {
    const fourth = makeMember({ id: 6, name: 'Opa', role: 'parent', color: 'green' })
    const result = careShares(
      [mama, papa, oma, fourth, lena],
      shares({ 1: 1, 2: 1, 3: 1, 6: 3, 4: 20 }),
    )
    expect(result?.map((share) => share.percent)).toEqual([17, 17, 16, 50, 0])
    expect(result?.find((share) => share.member.id === 4)?.count).toBe(20)
  })
})
