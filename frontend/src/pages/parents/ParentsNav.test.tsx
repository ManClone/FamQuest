import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '../../i18n'
import { makeMe, makeMember, makeToday, mockApi, renderApp, setupDone } from '../../test/utils'

function api() {
  return mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe()),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/tasks': Response.json([]),
    'GET /api/rewards': Response.json([]),
    'GET /api/approvals': Response.json([]),
    'GET /api/today': Response.json(makeToday()),
    'GET /api/profile': Response.json({ email: 'parent@example.org', member: makeMember() }),
  })
}
beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Management replaces everyday navigation', () => {
  it.each(['profile', 'family', 'tasks', 'household', 'rewards'])(
    'shows only management tabs on %s, with a way home',
    async (area) => {
      api()
      renderApp(`/parents/${area}`)
      await screen.findByRole('heading', { level: 1 })
      const navs = screen.getAllByRole('navigation')
      expect(navs).toHaveLength(1)
      expect(
        within(navs[0])
          .getAllByRole('link')
          .map((link) => link.textContent),
      ).toEqual(['Profil', 'Familie', 'Aufgaben', 'Haushalt', 'Belohnungen'])
      expect(screen.queryByRole('navigation', { name: 'Hauptnavigation' })).toBeNull()
      expect(screen.queryByRole('link', { name: 'Einstellungen' })).toBeNull()
      expect(screen.getByRole('button', { name: 'Zur Startseite' })).toBeVisible()
    },
  )

  it('opens personal settings directly in the profile tab', async () => {
    api()
    renderApp('/settings')
    await screen.findByRole('heading', { name: 'Profil', level: 1 })
    expect(screen.getByRole('link', { name: 'Profil' })).toHaveAttribute('aria-current', 'page')
    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(headings).toEqual(['Mein Profil', 'Mein Zugang', 'Dieses Gerät', 'Konto'])
    expect(screen.queryByText('Familie verwalten')).toBeNull()
  })

  it('groups family details first and weather below members', async () => {
    api()
    renderApp('/parents/settings')
    await screen.findByRole('heading', { name: 'Familie verwalten', level: 1 })
    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(headings).toEqual(['Familie', 'Familienmitglieder', 'Wetter', 'Taschengeld'])
    expect(screen.queryByRole('heading', { name: 'Dieses Gerät' })).toBeNull()
  })

  it('returns from management to the four everyday tabs', async () => {
    const user = userEvent.setup()
    api()
    renderApp('/parents/rewards')
    await user.click(await screen.findByRole('button', { name: 'Zur Startseite' }))
    await screen.findByRole('heading', { name: 'Dashboard', level: 1 })
    expect(screen.getByRole('navigation', { name: 'Hauptnavigation' })).toBeVisible()
    expect(screen.queryByRole('navigation', { name: 'Bereiche des Elternbereichs' })).toBeNull()
  })

  it('keeps navigation and the home button during editing and leaves the editor when switching tab', async () => {
    const user = userEvent.setup()
    api()
    renderApp('/parents/tasks')
    await user.click(await screen.findByRole('button', { name: 'Aufgabe hinzufügen' }))
    expect(screen.getByRole('button', { name: 'Zur Startseite' })).toBeVisible()
    await user.click(screen.getByRole('link', { name: 'Profil' }))
    await screen.findByRole('heading', { name: 'Profil', level: 1 })
    expect(screen.queryByRole('button', { name: 'Abbrechen' })).toBeNull()
  })
})
