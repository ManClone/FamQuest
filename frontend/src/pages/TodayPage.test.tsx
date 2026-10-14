import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { DEFAULT_LAYOUT } from '../api/home'
import i18n from '../i18n'
import { makeChorePlan, makeMe, makeMember, makeToday, mockApi, renderApp, setupDone } from '../test/utils'

beforeEach(async () => {
  await i18n.changeLanguage('de')
})

function setup(tiles = DEFAULT_LAYOUT.tiles) {
  mockApi({
    'GET /api/setup/status': setupDone,
    'GET /api/auth/me': Response.json(makeMe({ parent_unlocked: true })),
    'GET /api/members': Response.json([makeMember()]),
    'GET /api/today': Response.json(makeToday()),
    'GET /api/home/layout': Response.json({ ...DEFAULT_LAYOUT, tiles }),
    'GET /api/chores': Response.json(makeChorePlan()),
    'GET /api/tasks': Response.json([]),
    'GET /api/routines': Response.json([]),
    'GET /api/rewards': Response.json([]),
    'GET /api/weather': Response.json({ place: null, current: null, days: [] }),
  })
  renderApp('/')
}

describe('Startseite Heute', () => {
  it('zeigt die Familie und die Aufgabenansicht ohne entfernte Bereiche', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1 })).toBeVisible()
    expect(screen.queryByRole('link', { name: /Kalender|Essensplan|Einkauf/ })).toBeNull()
  })

  it('respektiert ausgeblendete Aufgaben und Haushalt', async () => {
    setup(DEFAULT_LAYOUT.tiles.map((tile) => ({ ...tile, visible: false })))
    expect(await screen.findByRole('heading', { level: 1 })).toBeVisible()
    await waitFor(() => {
      expect(screen.queryAllByRole('link', { name: /Aufgaben öffnen|Haushalt öffnen/ })).toHaveLength(0)
    })
  })
})
