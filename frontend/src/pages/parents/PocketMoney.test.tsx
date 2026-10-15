import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeMe, makeMember, mockApi, renderApp, setupDone } from '../../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => {
  vi.unstubAllGlobals()
})

it('configures automatic pocket money without offering a manual credit', async () => {
  const user = userEvent.setup()
  const calls = mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe({ parent_unlocked: true })),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/auth/accounts': Response.json([]),
    'GET /api/members/1/money': Response.json({ allowance_cents: 500, bonus_cents: 100 }),
    'GET /api/members/1/money/settings': Response.json({ weekly_amount_cents: null }),
    'PUT /api/members/1/money/settings': Response.json({ weekly_amount_cents: 500 }),
    'GET /api/members/1/money/allowance-payment-status': Response.json({
      expected_cents: 500,
      received_cents: 0,
      missing_cents: 500,
      bank_connected: false,
    }),
    'GET /api/members/1/money/bank-balances': Response.json([]),
    'GET /api/members/1/money/bank-transactions': Response.json([]),
  })
  renderApp('/parents/family')
  await screen.findByText('Automatisches wöchentliches Taschengeld')
  expect(screen.queryByText(/manuell gutschreiben/)).not.toBeInTheDocument()
  expect(screen.queryByText(/Grundtaschengeld/)).not.toBeInTheDocument()
  expect(await screen.findByText(/Zahlungseingang ist noch nicht bestätigt/)).toBeVisible()
  await user.type(screen.getByLabelText('Wochenbetrag in Euro'), '5,00')
  await user.click(screen.getByRole('button', { name: 'Wochenbetrag speichern' }))
  await screen.findByRole('status')
  expect(calls.find((call) => call.key === 'PUT /api/members/1/money/settings')?.body).toEqual({
    weekly_amount_cents: 500,
  })
  expect(
    calls.some((call) => call.key.includes('POST') && call.key.includes('weekly-allowance')),
  ).toBe(false)
})
