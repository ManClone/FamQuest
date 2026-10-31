import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PointHistory, PointTransaction } from '../../api/points'
import i18n from '../../i18n'
import { makeMe, makeMember, makeToday, mockApi, renderApp, setupDone } from '../../test/utils'

const lena = makeMember()
const tom = makeMember({ id: 2, name: 'Tom', color: 'green' })

function makeTransaction(overrides: Partial<PointTransaction> = {}): PointTransaction {
  return {
    id: 1,
    amount: 2,
    kind: 'task_completed',
    reason: 'Zähne putzen',
    icon: 'fluent-emoji-flat:toothbrush',
    task_date: '2026-10-03',
    created_at: '2026-10-03T05:30:00Z',
    ...overrides,
  }
}

const history: PointHistory = {
  total: 7,
  transactions: [
    makeTransaction({
      id: 3,
      amount: 5,
      kind: 'manual',
      reason: 'Beim Aufräumen geholfen',
      icon: null,
      task_date: null,
    }),
    makeTransaction({ id: 2, amount: -2, kind: 'task_undone' }),
    makeTransaction({ id: 1 }),
  ],
  has_more: false,
}

function api(extra: Record<string, Response | ((body: unknown) => Response)> = {}) {
  return mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe({ parent_unlocked: true })),
    'GET /api/members': Response.json([lena, tom]),
    'GET /api/tasks': Response.json([]),
    'GET /api/today': Response.json(
      makeToday({
        points: [
          { member_id: 1, today: 2, total: 7 },
          { member_id: 2, today: 0, total: 0 },
        ],
      }),
    ),
    'GET /api/members/1/activity': Response.json(history),
    'GET /api/members/1/criticism': Response.json({
      date: '2026-10-31',
      week_start: '2026-10-26',
      allowance_cents: 0,
      earned_bonus_cents: 0,
      money_penalty_cents: 0,
      payable_bonus_cents: 0,
      total_cents: 0,
      closed: false,
      requires_review: false,
      spendable_stars: 7,
      levels: {
        conversation: { stars: 0, bonus_cents: 0 },
        light: { stars: 1, bonus_cents: 0 },
        heavy: { stars: 2, bonus_cents: 50 },
        severe: { stars: 3, bonus_cents: 100 },
      },
    }),
    'GET /api/members/1/consequences': Response.json([]),
    ...extra,
  })
}

async function openLena() {
  const user = userEvent.setup()
  renderApp('/parents/family')
  await user.click(await screen.findByRole('button', { name: 'Lena bearbeiten' }))
  await screen.findByRole('heading', { name: 'Punkte gutschreiben und korrigieren' })
  return user
}

beforeEach(async () => {
  await i18n.changeLanguage('de')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Punkte im Elternbereich', () => {
  it('öffnet die Punkteverwaltung direkt beim Kind unter Familie', async () => {
    api()
    await openLena()
    expect(
      await screen.findByRole('heading', { name: 'Punkte gutschreiben und korrigieren' }),
    ).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Punkte von Lena' })).toBeNull()
    expect(screen.getByText(/Punktestand:/)).toHaveTextContent('7')
    expect(screen.queryByRole('button', { name: /^Zurück$/ })).toBeNull()
  })

  it('zeigt Punktestand und Buchungshistorie einer Person', async () => {
    api()
    await openLena()

    expect(await screen.findByText('Beim Aufräumen geholfen')).toBeVisible()
    const rows = screen.getAllByRole('listitem').map((row) => row.textContent)
    expect(rows).toEqual([
      expect.stringMatching(/Beim Aufräumen geholfen.*Von Eltern gebucht.*\+5/),
      expect.stringMatching(/Zähne putzen.*Erledigung zurückgenommen.*−2$/),
      expect.stringMatching(/Zähne putzen.*Aufgabe erledigt.*\+2$/),
    ])
    // Uhrzeit in der Zeitzone der Familie (Berlin, UTC+2), nicht in UTC.
    expect(rows[2]).toContain('07:30')
  })

  it('schreibt Punkte mit Begründung gut', async () => {
    const calls = api({
      'POST /api/members/1/points': Response.json({ ...history, total: 10 }, { status: 201 }),
    })
    const user = await openLena()

    await user.click(screen.getByRole('button', { name: 'Mehr Punkte' }))
    await user.click(screen.getByRole('button', { name: 'Mehr Punkte' }))
    await user.type(screen.getByLabelText('Begründung'), '  Tisch gedeckt ')
    await user.click(screen.getByRole('button', { name: '3 Punkte gutschreiben' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Lena hat 3 Punkte bekommen.')
    const post = calls.find((call) => call.key === 'POST /api/members/1/points')
    expect(post?.body).toEqual({ amount: 3, reason: 'Tisch gedeckt' })
    expect(screen.getByLabelText('Begründung')).toHaveValue('')
  })

  it('bietet beim Kind nur Gutschriften und keine parallele Kritik- oder Geldverwaltung an', async () => {
    api()
    await openLena()
    expect(screen.queryByRole('radio', { name: 'Abziehen' })).toBeNull()
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.queryByText('Grundtaschengeld einstellen')).toBeNull()
  })

  it('nimmt eine einzelne manuelle Gutschrift mit Begründung zurück', async () => {
    let reversed = false
    const calls = api({
      'GET /api/members/1/activity': () =>
        Response.json({
          ...history,
          transactions: [
            { ...history.transactions[0], reversed_at: reversed ? '2026-10-31T12:00:00Z' : null },
          ],
        }),
      'POST /api/members/1/points/3/reverse': () => {
        reversed = true
        return Response.json({ transaction_id: 3 })
      },
    })
    const user = await openLena()
    await user.click(await screen.findByRole('button', { name: /Beim Aufräumen geholfen/ }))
    const confirm = screen.getByRole('button', { name: 'Gutschrift mit Begründung zurücknehmen' })
    expect(confirm).toBeDisabled()
    await user.type(screen.getByLabelText('Grund der Korrektur'), 'Versehentlich gebucht')
    await user.click(confirm)
    await screen.findByText(/Storniert/)
    expect(calls.find((call) => call.key.endsWith('/points/3/reverse'))?.body).toEqual({
      reason: 'Versehentlich gebucht',
    })
    expect(screen.queryByRole('button', { name: 'Gutschrift korrigieren' })).toBeNull()
  })

  it.each(['task', 'chore'] as const)(
    'korrigiert %s direkt in der einzigen Buchungsliste',
    async (source) => {
      let undone = false
      const route = source === 'task' ? 'approvals' : 'chore-approvals'
      const calls = api({
        'GET /api/members/1/activity': () =>
          Response.json({
            total: undone ? 0 : 2,
            has_more: false,
            transactions: [
              {
                ...makeTransaction(),
                undo_source: undone ? null : source,
                undo_id: undone ? null : 41,
              },
            ],
          }),
        [`DELETE /api/${route}/41/confirmed`]: () => {
          undone = true
          return new Response(null, { status: 204 })
        },
      })
      const user = await openLena()
      expect(screen.queryByText('Erledigte Kinderaufgaben')).toBeNull()
      expect(screen.queryByText('Bestätigte Erledigungen')).toBeNull()
      await user.click(await screen.findByRole('button', { name: /Zähne putzen/ }))
      expect(calls.some((call) => call.key.startsWith('DELETE'))).toBe(false)
      await user.click(screen.getByRole('button', { name: 'Ja, rückgängig machen' }))
      await vi.waitFor(() =>
        expect(screen.queryByRole('button', { name: /Zähne putzen/ })).toBeNull(),
      )
      expect(calls.filter((call) => call.key.startsWith('DELETE')).map((call) => call.key)).toEqual(
        [`DELETE /api/${route}/41/confirmed`],
      )
    },
  )

  it('verlangt eine Begründung', async () => {
    const calls = api()
    const user = await openLena()

    await user.click(screen.getByRole('button', { name: '1 Punkt gutschreiben' }))

    expect(screen.getByLabelText('Begründung')).toHaveAccessibleDescription('Bitte ausfüllen')
    expect(calls.some((call) => call.key.startsWith('POST'))).toBe(false)
  })

  it('lädt ältere Buchungen nach', async () => {
    const firstPage = {
      ...history,
      transactions: history.transactions.slice(0, 1),
      has_more: true,
      next_cursor: 'older',
    }
    const secondPage = { ...history, transactions: history.transactions.slice(1) }
    let page = 0
    api({
      'GET /api/members/1/activity': () => Response.json(++page === 1 ? firstPage : secondPage),
    })
    const requested: string[] = []
    const mockedFetch = globalThis.fetch
    vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) => {
      requested.push(String(input))
      return mockedFetch(input, init)
    })
    const user = await openLena()

    await screen.findByText('Beim Aufräumen geholfen')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Ältere Buchungen laden' }))

    await vi.waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(3))
    expect(requested).toContain('/api/members/1/activity?cursor=older')
    expect(screen.queryByRole('button', { name: 'Ältere Buchungen laden' })).toBeNull()
  })
})
