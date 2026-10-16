import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DEFAULT_LAYOUT } from '../api/home'
import i18n from '../i18n'
import {
  makeChore,
  makeChorePlan,
  makeMe,
  makeMember,
  makeToday,
  makeTodayTask,
  makeTodo,
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

function setup() {
  const overdue = makeChore({ title: 'Water plants', days_left: -2, level: 'due', ratio: 1.5 })
  const current = makeChore({
    id: 2,
    title: 'Clean litter box',
    days_left: 0,
    level: 'due',
    ratio: 1,
  })
  let marked = false
  const calls = mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({ family: { ...makeMe().family, default_language: 'en' } }),
    ),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/today': Response.json(
      makeToday({ tasks: [makeTodayTask({ title: 'Child task' })], pending_approvals: 1 }),
    ),
    'GET /api/home/layout': Response.json(DEFAULT_LAYOUT),
    'GET /api/chores': () =>
      Response.json(
        makeChorePlan({
          chores: [
            marked ? { ...overdue, done_today: true, days_left: 14, level: 'ok' } : overdue,
            current,
          ],
          todos: [makeTodo({ title: 'Buy food' })],
        }),
      ),
    'GET /api/approvals': Response.json([
      {
        id: 7,
        task_id: 1,
        title: 'Awaiting review',
        icon: 'fluent-emoji-flat:toothbrush',
        points: 2,
        member_id: 1,
        date: '2026-10-03',
        completed_at: '2026-10-03T10:00:00Z',
      },
    ]),
    'GET /api/weather': Response.json({ place: null, current: null, days: [] }),
    'PUT /api/chores/1/done': () => {
      marked = true
      return Response.json({ ...overdue, done_today: true, days_left: 14, level: 'ok' })
    },
  })
  renderApp('/')
  return calls
}

it('restores the dashboard header and actionable chores without child task lists', async () => {
  const user = userEvent.setup()
  const calls = setup()
  await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
  expect(screen.getByText(makeMe().family.name)).toBeVisible()
  expect(document.querySelector('time')).toBeInTheDocument()
  const overdue = await screen.findByRole('button', { name: /Water plants/ })
  expect(await screen.findByRole('button', { name: /Clean litter box/ })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Buy food' })).toBeVisible()
  expect(screen.queryByText('Child task')).toBeNull()
  expect(await screen.findByText('Awaiting review')).toBeVisible()
  await user.click(overdue)
  await waitFor(() =>
    expect(calls.some((call) => call.key === 'PUT /api/chores/1/done')).toBe(true),
  )
  await waitFor(() => expect(screen.queryByRole('button', { name: /Water plants/ })).toBeNull())
})

it('keeps the parent dashboard free of the customization gear', async () => {
  setup()
  await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
  expect(screen.queryByRole('button', { name: /Customise|Customize/ })).toBeNull()
})
