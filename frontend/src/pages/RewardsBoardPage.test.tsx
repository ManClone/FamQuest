import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import {
  makeMe,
  makeMember,
  makeReward,
  makeToday,
  mockApi,
  renderApp,
  setupDone,
} from '../test/utils'

afterEach(() => vi.unstubAllGlobals())
it('only allows the linked adult to redeem while keeping the other adult board visible', async () => {
  await i18n.changeLanguage('en')
  const user = userEvent.setup()
  const calls = mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({ member_id: 1, family: { ...makeMe().family, default_language: 'en' } }),
    ),
    'GET /api/members': Response.json([
      makeMember({ id: 1, name: 'Flo', role: 'parent' }),
      makeMember({ id: 2, name: 'Viola', role: 'parent', color: 'purple' }),
    ]),
    'GET /api/today': Response.json(
      makeToday({
        points: [
          { member_id: 1, today: 0, total: 30 },
          { member_id: 2, today: 0, total: 30 },
        ],
      }),
    ),
    'GET /api/rewards': Response.json([
      makeReward({ id: 1, member_id: 1, name: 'Coffee', cost: 10 }),
      makeReward({ id: 2, member_id: 2, name: 'Cinema', cost: 10 }),
    ]),
    'GET /api/redemptions': Response.json({ redemptions: [], has_more: false }),
  })
  renderApp('/rewards/board')
  expect(await screen.findByRole('button', { name: 'Redeem Coffee' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: /Viola/ }))
  expect(await screen.findByRole('button', { name: 'Redeem Cinema' })).toBeDisabled()
  expect(
    screen.getByText(
      'Only this person can redeem their rewards. Progress and history remain visible.',
    ),
  ).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Redeem Cinema' }))
  expect(calls.some((call) => call.key.startsWith('POST'))).toBe(false)
  await user.click(screen.getByRole('button', { name: /Flo/ }))
  expect(await screen.findByRole('button', { name: 'Redeem Coffee' })).toBeEnabled()
})
