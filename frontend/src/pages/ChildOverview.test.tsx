import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '../i18n'
import {
  makeMe,
  makeMember,
  makeToday,
  makeTodayTask,
  makeReward,
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
function setup(path = '/tasks') {
  let redeemed = false
  let pendingChore = false
  const member = makeMember({ name: 'Tim' })
  const calls = mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({
        member_id: 1,
        user: { ...makeMe().user, role: 'child' },
        family: { ...makeMe().family, default_language: 'en' },
      }),
    ),
    'GET /api/members': Response.json([member]),
    'GET /api/chores/mine': () =>
      Response.json([
        {
          id: 20,
          title: 'Clean litter box',
          icon: 'fluent-emoji-flat:cat',
          points: 4,
          repeatable: true,
          days_left: 0,
          done_today: false,
          count: pendingChore ? 1 : 0,
          pending: pendingChore ? 1 : 0,
        },
      ]),
    'PUT /api/chores/mine/20/done': () => {
      pendingChore = true
      return Response.json([
        {
          id: 20,
          title: 'Clean litter box',
          icon: 'fluent-emoji-flat:cat',
          points: 4,
          repeatable: true,
          days_left: 0,
          done_today: false,
          count: 1,
          pending: 1,
        },
      ])
    },
    'GET /api/today': () =>
      Response.json(
        makeToday({
          tasks: [makeTodayTask({ title: 'Brush teeth' })],
          points: [{ member_id: 1, today: 5, total: redeemed ? 22 : 32 }],
        }),
      ),
    'GET /api/members/1/progress': Response.json({
      earned_xp: 132,
      level: 2,
      level_progress: 32,
      level_size: 100,
      remaining_xp: 68,
    }),
    'GET /api/tasks/week': Response.json({
      start: '2026-09-28',
      today: '2026-10-03',
      tasks: [],
      days: Array.from({ length: 7 }, (_, index) => ({
        date: `2026-10-${String(index + 1).padStart(2, '0')}`,
        entries: [],
      })),
    }),
    'GET /api/rewards': Response.json([makeReward({ name: 'A film', cost: 10 })]),
    'GET /api/redemptions': () =>
      Response.json({
        redemptions: redeemed
          ? [
              {
                id: 1,
                reward_id: 1,
                member_id: 1,
                status: 'redeemed',
                reward_name: 'A film',
                reward_icon: 'fluent-emoji-flat:clapper-board',
                cost: 10,
                created_at: '2026-10-03T10:15:00Z',
              },
            ]
          : [],
        has_more: false,
      }),
    'POST /api/rewards/1/redeem': () => {
      redeemed = true
      return Response.json(
        {
          id: 1,
          reward_id: 1,
          member_id: 1,
          status: 'redeemed',
          reward_name: 'A film',
          reward_icon: 'fluent-emoji-flat:clapper-board',
          cost: 10,
          created_at: '2026-10-03T10:15:00Z',
        },
        { status: 201 },
      )
    },
  })
  renderApp(path)
  return calls
}

it('keeps the same personal progress above day/week and removes the duplicate task list', async () => {
  const user = userEvent.setup()
  setup()
  const overview = await screen.findByRole('region', { name: 'My adventure' })
  expect(await within(overview).findByText('Level 2')).toBeVisible()
  const level = within(overview).getByRole('progressbar')
  expect(level).toHaveAttribute('aria-valuenow', '32')
  expect(screen.getAllByText('Brush teeth')).toHaveLength(1)
  expect(screen.queryByRole('heading', { name: 'All my tasks' })).toBeNull()
  await user.click(
    within(screen.getByRole('navigation', { name: 'View' })).getByRole('link', { name: 'Week' }),
  )
  await screen.findByRole('heading', { name: /October/, level: 2 })
  expect(screen.getByRole('region', { name: 'My adventure' })).toBe(overview)
  expect(within(overview).getByRole('progressbar')).toBe(level)
  expect(screen.getByRole('heading', { name: 'Tim', level: 1 })).toBeVisible()
  expect(within(overview).getByText('32 stars')).toBeVisible()
})

it('shows own redemption history and a working back destination for children', async () => {
  const user = userEvent.setup()
  setup('/rewards/1')
  expect(await screen.findByRole('heading', { name: 'Your redeemed rewards' })).toBeVisible()
  await user.click(await screen.findByRole('button', { name: /Redeem.*A film/ }))
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Yes, redeem' }))
  const history = screen.getByRole('region', { name: 'Your redeemed rewards' })
  expect(await within(history).findByText('A film')).toBeVisible()
  expect(within(history).getByText(/12:15/)).toBeVisible()
  expect(within(history).queryByRole('button', { name: 'Cancel redemption' })).toBeNull()
  await user.keyboard('{Escape}')
  const back = screen.getByRole('link', { name: /Back/ })
  expect(back).toHaveAttribute('href', '/tasks')
  await user.click(back)
  expect(await screen.findByRole('heading', { name: 'Tim', level: 1 })).toBeVisible()
  expect(await screen.findByText('Level 2')).toBeVisible()
  expect(screen.getByText('22 stars')).toBeVisible()
})

it('zeigt automatisch zugeteilte Hausarbeit separat und wartet auf die Eltern', async () => {
  const user = userEvent.setup()
  const calls = setup()
  const household = await screen.findByRole('region', { name: 'Household' })
  expect(await within(household).findByText('Clean litter box')).toBeVisible()
  await user.click(within(household).getByRole('button', { name: 'Done!' }))
  expect(await within(household).findByText('1 completions awaiting approval')).toBeVisible()
  expect(screen.getByText('32 stars')).toBeVisible()
  expect(calls.some((call) => call.key === 'GET /api/chores')).toBe(false)
})
