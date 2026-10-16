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

function routes(accounts: unknown[] = []) {
  return {
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe({ parent_unlocked: true })),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/auth/accounts': Response.json(accounts),
  }
}

it('creates a person and credentials in one request', async () => {
  const user = userEvent.setup()
  const calls = mockApi({
    ...routes(),
    'POST /api/members': Response.json(makeMember({ id: 2, name: 'Tom', color: 'green' })),
  })
  renderApp('/parents/family')
  await user.click(await screen.findByRole('button', { name: 'Person hinzufügen' }))
  await user.type(screen.getByLabelText('Name'), 'Tom')
  await user.click(screen.getByRole('switch', { name: 'Eigenen Login einrichten' }))
  await user.type(screen.getByLabelText('E-Mail'), 'tom@example.org')
  await user.type(screen.getByLabelText('Passwort'), 'test-password-123')
  await user.click(screen.getByRole('button', { name: 'Speichern' }))
  await screen.findByRole('status')
  expect(calls.find((call) => call.key === 'POST /api/members')?.body).toMatchObject({
    name: 'Tom',
    role: 'child',
    login: { email: 'tom@example.org', password: 'test-password-123' },
  })
})

it('edits the linked email without overwriting an unchanged password', async () => {
  const user = userEvent.setup()
  const calls = mockApi({
    ...routes([{ id: 4, email: 'lena@example.org', role: 'child', member_id: 1 }]),
    'PUT /api/members/1': Response.json(makeMember()),
  })
  renderApp('/parents/family')
  await screen.findByText('lena@example.org')
  await user.click(screen.getByRole('button', { name: 'Lena bearbeiten' }))
  expect(await screen.findByLabelText('E-Mail')).toHaveValue('lena@example.org')
  await user.clear(screen.getByLabelText('E-Mail'))
  await user.type(screen.getByLabelText('E-Mail'), 'new@example.org')
  await user.click(screen.getByRole('button', { name: 'Speichern' }))
  await screen.findByRole('status')
  expect(calls.find((call) => call.key === 'PUT /api/members/1')?.body).toMatchObject({
    login: { email: 'new@example.org' },
  })
  expect(
    (calls.find((call) => call.key === 'PUT /api/members/1')?.body as { login: object }).login,
  ).not.toHaveProperty('password')
})

it('offers existing unassigned accounts for explicit assignment', async () => {
  const user = userEvent.setup()
  const calls = mockApi({
    ...routes([{ id: 4, email: 'lena@example.org', role: 'child', member_id: null }]),
    'PUT /api/members/1': Response.json(makeMember()),
  })
  renderApp('/parents/family')
  await user.click(await screen.findByRole('button', { name: 'Lena bearbeiten' }))
  await user.click(screen.getByRole('switch', { name: 'Eigenen Login einrichten' }))
  await user.selectOptions(await screen.findByLabelText('Login zuordnen'), '4')
  await user.click(screen.getByRole('button', { name: 'Speichern' }))
  await screen.findByRole('status')
  expect(calls.find((call) => call.key === 'PUT /api/members/1')?.body).toMatchObject({
    login: { account_id: 4 },
  })
})

it('no longer offers separate account creation in settings', async () => {
  mockApi(routes())
  renderApp('/parents/profile')
  await screen.findByText(/mama@example.org/)
  expect(screen.queryByText('Benutzerkonten')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Konto anlegen' })).not.toBeInTheDocument()
})
