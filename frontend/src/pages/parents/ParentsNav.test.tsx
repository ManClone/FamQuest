import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { makeMe, makeMember, makeToday, mockApi, renderApp, setupDone } from '../../test/utils'

function api(pending = 0) {
  return mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe()),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/tasks': Response.json([]),
    'GET /api/rewards': Response.json([]),
    'GET /api/approvals': Response.json([]),
    'GET /api/today': Response.json(makeToday({ pending_approvals: pending })),
    'GET /api/profile': Response.json({ email: 'parent@example.org', member: null }),
  })
}

beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Single navigation in parent management', () => {
  it.each(['family', 'tasks', 'household', 'rewards', 'settings'])(
    'keeps only the four main tabs on %s',
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
      ).toEqual(['Dashboard', 'Haushalt', 'Belohnungen', 'Einstellungen'])
      expect(screen.queryByRole('button', { name: 'Mehr' })).toBeNull()
    },
  )

  it('opens rewards directly without a second management menu', async () => {
    const user = userEvent.setup()
    api()
    renderApp('/settings')
    const nav = await screen.findByRole('navigation')
    await user.click(within(nav).getByRole('link', { name: 'Belohnungen' }))
    await screen.findByRole('heading', { name: 'Belohnungen verwalten', level: 1 })
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Einstellungen' })).toBeNull()
  })

  it('returns from family configuration to personal settings', async () => {
    const user = userEvent.setup()
    api()
    renderApp('/parents/family')
    await user.click(await screen.findByRole('button', { name: 'Einstellungen' }))
    expect(await screen.findByRole('heading', { name: 'Einstellungen', level: 1 })).toBeVisible()
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
  })

  it('keeps the approval badge on the main dashboard tab', async () => {
    api(3)
    renderApp('/parents/family')
    expect(await screen.findByRole('link', { name: /Dashboard,.*3/ })).toBeVisible()
    expect(screen.getAllByRole('navigation')).toHaveLength(1)
  })
})
