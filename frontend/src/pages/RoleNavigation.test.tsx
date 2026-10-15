import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import {
  makeChorePlan,
  makeMe,
  makeMember,
  makeToday,
  makeTodayTask,
  mockApi,
  renderApp,
  setupDone,
} from '../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => {
  vi.unstubAllGlobals()
})

function routes(child: boolean) {
  return {
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(
      makeMe({
        member_id: 1,
        user: { email: 'lena@example.org', role: child ? 'child' : 'parent', language: null },
      }),
    ),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/today': Response.json(makeToday({ tasks: [makeTodayTask({ title: 'Katzenklo' })] })),
    'GET /api/tasks': Response.json([]),
    'GET /api/approvals': Response.json([]),
    'GET /api/chores': Response.json(makeChorePlan()),
    'GET /api/profile': Response.json({ email: 'lena@example.org', member: makeMember() }),
  }
}

it('gives children exactly four tabs and no household request', async () => {
  const calls = mockApi(routes(true))
  renderApp('/')
  const nav = within(await screen.findByRole('navigation'))
  expect(nav.getAllByRole('link').map((link) => link.textContent)).toEqual([
    'Heute',
    'Aufgaben',
    'Belohnungen',
    'Einstellungen',
  ])
  expect(nav.queryByRole('link', { name: 'Haushalt' })).not.toBeInTheDocument()
  expect(calls.some((call) => call.key === 'GET /api/chores')).toBe(false)
})

it('gives parents dashboard, household, rewards and settings', async () => {
  mockApi(routes(false))
  renderApp('/')
  await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
  expect(
    within(screen.getByRole('navigation'))
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['Dashboard', 'Haushalt', 'Belohnungen', 'Einstellungen'])
})

it('lets children edit only their own profile and device settings', async () => {
  const user = userEvent.setup()
  const calls = mockApi({
    ...routes(true),
    'PUT /api/profile': Response.json({
      email: 'lena@example.org',
      member: makeMember({ name: 'Leni' }),
    }),
  })
  renderApp('/settings')
  const name = await screen.findByLabelText('Name')
  await user.clear(name)
  await user.type(name, 'Leni')
  await user.click(screen.getByRole('button', { name: 'Speichern' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Profil gespeichert.')
  expect(calls.find((call) => call.key === 'PUT /api/profile')?.body).toEqual({ name: 'Leni' })
  expect(screen.queryByText('Familie verwalten')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Haushalt' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Bisheriges Passwort')).toBeVisible()
})

it('redirects children away from household and family management', async () => {
  const calls = mockApi(routes(true))
  renderApp('/parents/family')
  await screen.findByRole('heading', { name: 'Heute', level: 1 })
  expect(calls.some((call) => call.key === 'GET /api/auth/accounts')).toBe(false)
})
