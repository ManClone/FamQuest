import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { makeMe, mockApi, renderApp, setupDone } from '../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('de')
  vi.unstubAllGlobals()
})

describe('Elternbereich ohne PIN', () => {
  it('ist für angemeldete Eltern direkt über Einstellungen erreichbar', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /api/setup/status': setupDone, 'GET /api/auth/me': Response.json(makeMe()) })
    renderApp('/')

    await user.click(await screen.findByRole('link', { name: 'Einstellungen' }))
    expect(await screen.findByRole('heading', { name: 'Einstellungen' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Eltern-PIN eingeben' })).not.toBeInTheDocument()
  })

  it('öffnet den Elternbereich ohne PIN-Entsperraufruf', async () => {
    const calls = mockApi({
      'GET /api/setup/status': setupDone,
      'GET /api/auth/me': Response.json(makeMe()),
    })
    renderApp('/parents')

    expect(await screen.findByRole('heading', { name: 'Elternbereich' })).toBeVisible()
    expect(calls.some((call) => call.key === 'POST /api/parent/unlock')).toBe(false)
  })

  it('zeigt Kindern keine Elternverwaltung', async () => {
    mockApi({
      'GET /api/setup/status': setupDone,
      'GET /api/auth/me': Response.json(makeMe({ user: { ...makeMe().user, role: 'child' } })),
    })
    renderApp('/parents')

    expect(await screen.findByRole('navigation', { name: 'Hauptnavigation' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Elternbereich' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Einstellungen' })).toHaveAttribute('href', '/settings')
  })
})
