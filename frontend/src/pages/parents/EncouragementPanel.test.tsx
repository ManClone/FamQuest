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
    'POST /api/members/1/points': Response.json({ total: 8, transactions: [], has_more: false }),
  })
  renderApp('/')
  const panel = await screen.findByRole('region', { name: 'Praise & stars' })
  await user.type(within(panel).getByLabelText('Reason'), 'Great help')
  await user.click(within(panel).getAllByRole('button', { name: 'Give praise' }).at(-1)!)
  expect(await within(panel).findByLabelText('1 praises')).toBeVisible()
  expect(calls.find((call) => call.key === 'POST /api/members/1/praise')?.body).toMatchObject({
    reason: 'Great help',
  })
  await user.click(within(panel).getByRole('button', { name: 'Deduct stars' }))
  await user.type(within(panel).getByLabelText('Reason'), 'Correction')
  await user.click(within(panel).getAllByRole('button', { name: 'Deduct stars' }).at(-1)!)
  expect(await within(panel).findByRole('status')).toHaveTextContent('Saved.')
  expect(calls.find((call) => call.key === 'POST /api/members/1/points')?.body).toMatchObject({
    amount: -1,
    reason: 'Correction',
  })
})
