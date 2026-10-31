import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DEFAULT_LAYOUT } from '../../api/home'
import i18n from '../../i18n'
import {
  makeMe,
  makeMember,
  makeToday,
  makeChorePlan,
  mockApi,
  renderApp,
  setupDone,
} from '../../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('en')
})
afterEach(() => vi.unstubAllGlobals())

it('gives a separate heart and restores reasoned star deductions on the dashboard', async () => {
  const user = userEvent.setup()
  let hearts = 0
  const calls = mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({ family: { ...makeMe().family, default_language: 'en' } }),
    ),
    'GET /api/members': Response.json([makeMember({ id: 1, name: 'Tim', role: 'child' })]),
    'GET /api/today': Response.json(makeToday()),
    'GET /api/home/layout': Response.json(DEFAULT_LAYOUT),
    'GET /api/approvals': Response.json([]),
    'GET /api/chores': Response.json(makeChorePlan()),
    'GET /api/members/1/progress': () => Response.json({ praise_count: hearts }),
    'POST /api/members/1/praise': () => {
      hearts++
      return Response.json({ id: 1 })
    },
    'GET /api/members/1/criticism': Response.json({
      date: '2026-10-31',
      spendable_stars: 8,
      payable_bonus_cents: 50,
      total_cents: 50,
      levels: { light: { stars: 1, bonus_cents: 0 }, conversation: { stars: 0, bonus_cents: 0 } },
    }),
    'GET /api/members/1/consequences': Response.json([]),
    'POST /api/consequences': Response.json({ id: 1 }, { status: 201 }),
  })
  renderApp('/')
  const panel = await screen.findByRole('region', { name: 'Praise & discipline' })
  expect(within(panel).queryByLabelText('Reason')).not.toBeInTheDocument()
  await user.click(within(panel).getByRole('button', { name: 'Give praise' }))
  await user.type(within(panel).getByLabelText('Reason'), 'Great help')
  await user.click(within(panel).getAllByRole('button', { name: 'Give praise' }).at(-1)!)
  expect(await within(panel).findByLabelText('1 praise')).toBeVisible()
  expect(calls.find((call) => call.key === 'POST /api/members/1/praise')?.body).toMatchObject({
    reason: 'Great help',
  })
  await user.click(within(panel).getByRole('button', { name: 'Deduct stars' }))
  await user.selectOptions(await within(panel).findByRole('combobox'), 'light')
  await user.type(within(panel).getByLabelText('Brief reason'), 'Correction')
  await user.click(within(panel).getByRole('checkbox', { name: /confirm this specific/ }))
  await user.click(within(panel).getByRole('button', { name: 'Save decision' }))
  expect(await within(panel).findByText('Decision saved.')).toBeVisible()
  expect(calls.find((call) => call.key === 'POST /api/consequences')?.body).toMatchObject({
    severity: 'light',
    apply_money: false,
    confirmed: true,
  })
  expect(calls.some((call) => call.key === 'POST /api/members/1/points')).toBe(false)
})
