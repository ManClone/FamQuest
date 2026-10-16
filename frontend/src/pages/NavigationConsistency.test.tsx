import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import { DEFAULT_LAYOUT } from '../api/home'
import {
  makeMe,
  makeMember,
  makeReward,
  makeToday,
  mockApi,
  renderApp,
  setupDone,
} from '../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('en')
})
afterEach(() => {
  vi.unstubAllGlobals()
})
function setup(path = '/') {
  mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({ family: { ...makeMe().family, name: 'Grasser', default_language: 'en' } }),
    ),
    'GET /api/members': Response.json([makeMember(), makeMember({ id: 2, name: 'Tom' })]),
    'GET /api/today': Response.json(makeToday({ points: [{ member_id: 1, today: 0, total: 32 }] })),
    'GET /api/home/layout': Response.json(DEFAULT_LAYOUT),
    'GET /api/approvals': Response.json([]),
    'GET /api/chores': Response.json({
      date: '2026-10-16',
      rooms: [],
      chores: [],
      todos: [],
      shares: [],
      share_days: 30,
    }),
    'GET /api/rewards': Response.json([
      makeReward({ name: 'A film' }),
      makeReward({ id: 2, member_id: 2, name: 'Zoo' }),
    ]),
    'GET /api/redemptions': Response.json({ redemptions: [], has_more: false }),
    'GET /api/profile': Response.json({ email: 'parent@example.org', member: null }),
  })
  renderApp(path)
}

it('opens a rewards board in everyday navigation rather than entering settings', async () => {
  const user = userEvent.setup()
  setup()
  const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
  expect(screen.queryByRole('button', { name: i18n.t('home.customize') })).toBeNull()
  await user.click(within(nav).getByRole('link', { name: 'Rewards' }))
  await screen.findByRole('heading', { name: 'Rewards', level: 1 })
  expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBe(nav)
  expect(screen.queryByRole('button', { name: 'To the start page' })).toBeNull()
  expect(screen.queryByRole('navigation', { name: 'Parent area sections' })).toBeNull()
  expect(await screen.findByRole('button', { name: /Redeem.*A film/ })).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Tom' }))
  expect(await screen.findByRole('heading', { name: 'Zoo' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'A film' })).toBeNull()
})

it('identifies the settings area beside the home control on every management page', async () => {
  const user = userEvent.setup()
  setup('/parents/profile')
  const header = await screen.findByTestId('settings-header')
  expect(within(header).getByText('Settings')).toBeVisible()
  expect(within(header).getByRole('button', { name: 'To the start page' })).toBeVisible()
  await user.click(screen.getByRole('link', { name: 'Family' }))
  expect(screen.getByTestId('settings-header')).toBe(header)
  expect(within(header).getByText('Settings')).toBeVisible()
})
