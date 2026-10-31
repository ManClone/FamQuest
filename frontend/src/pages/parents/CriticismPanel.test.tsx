import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n'
import { mockApi } from '../../test/utils'
import { CriticismPanel } from './CriticismPanel'

const context = {
  date: '2026-10-31',
  week_start: '2026-10-26',
  allowance_cents: 500,
  earned_bonus_cents: 350,
  money_penalty_cents: 0,
  payable_bonus_cents: 350,
  total_cents: 850,
  closed: false,
  requires_review: false,
  spendable_stars: 20,
  levels: {
    conversation: { stars: 0, bonus_cents: 0 },
    light: { stars: 1, bonus_cents: 0 },
    heavy: { stars: 2, bonus_cents: 50 },
    severe: { stars: 3, bonus_cents: 100 },
  },
}

function mount(data = context) {
  const calls = mockApi({
    'GET /api/members/1/criticism': Response.json(data),
    'GET /api/members/1/consequences': Response.json([]),
    'POST /api/consequences': Response.json({ id: 5 }, { status: 201 }),
    'POST /api/members/1/weekly-bonus/close': Response.json({ ...data, closed: true }),
  })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <CriticismPanel memberId={1} />
    </QueryClientProvider>,
  )
  return calls
}

beforeEach(async () => {
  await i18n.changeLanguage('de')
})
afterEach(() => vi.unstubAllGlobals())

describe('Feste Kritikstufen und geschützter Wochenbonus', () => {
  it('erfordert konkrete Bestätigung und Grund, ohne Geld automatisch auszuwählen', async () => {
    const user = userEvent.setup()
    const calls = mount()
    await user.selectOptions(await screen.findByRole('combobox'), 'heavy')
    const money = screen.getByRole('checkbox', { name: /Zusätzlich/ })
    expect(money).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Entscheidung speichern' })).toBeDisabled()
    await user.type(screen.getByLabelText('Kurze Begründung'), 'Gemeinsame Entscheidung')
    await user.click(
      screen.getByRole('checkbox', {
        name: 'Ich bestätige diese konkrete Entscheidung und Begründung.',
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Entscheidung speichern' }))
    await waitFor(() =>
      expect(calls.some((call) => call.key === 'POST /api/consequences')).toBe(true),
    )
    const body = calls.find((call) => call.key === 'POST /api/consequences')!.body
    expect(body).toMatchObject({
      member_id: 1,
      severity: 'heavy',
      apply_money: false,
      confirmed: true,
      title: 'Gemeinsame Entscheidung',
      expected_bonus_cents: 350,
    })
    expect((body as { request_key: string }).request_key).toMatch(/^[a-f0-9]{32}$/)
  })

  it('zeigt vor der Bestätigung den verbleibenden Bonus und nimmt nur den festen Betrag', async () => {
    const user = userEvent.setup()
    const calls = mount()
    await user.selectOptions(await screen.findByRole('combobox'), 'heavy')
    await user.click(screen.getByRole('checkbox', { name: /Zusätzlich/ }))
    expect(screen.getByText(/Abzug: 2 Sterne und 0,50.*Danach verbleiben 3,00/)).toBeVisible()
    await user.type(screen.getByLabelText('Kurze Begründung'), 'Explizite Elternentscheidung')
    await user.click(screen.getByRole('checkbox', { name: /konkrete Entscheidung/ }))
    await user.click(screen.getByRole('button', { name: 'Entscheidung speichern' }))
    await waitFor(() =>
      expect(calls.find((call) => call.key === 'POST /api/consequences')?.body).toMatchObject({
        apply_money: true,
        expected_bonus_cents: 350,
      }),
    )
  })

  it('sperrt einen vollständigen Bonusentzug auch bei sehr schwerer Kritik', async () => {
    const user = userEvent.setup()
    mount({ ...context, earned_bonus_cents: 100, payable_bonus_cents: 100 })
    await user.selectOptions(await screen.findByRole('combobox'), 'severe')
    expect(screen.getByRole('checkbox', { name: /Zusätzlich/ })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /Zusätzlich/ })).not.toBeChecked()
  })

  it('schließt keine Abrechnung ohne gesonderte Zahlungsbestätigung', async () => {
    const user = userEvent.setup()
    const calls = mount()
    const button = await screen.findByRole('button', {
      name: 'Wochenabrechnung unveränderlich abschließen',
    })
    expect(button).toBeDisabled()
    expect(calls.some((call) => call.key.endsWith('/close'))).toBe(false)
    await user.click(screen.getByRole('checkbox', { name: /als ausgezahlt/ }))
    await user.click(button)
    await waitFor(() =>
      expect(calls.find((call) => call.key.endsWith('/close'))?.body).toEqual({
        date: '2026-10-31',
        confirmed: true,
        expected_total_cents: 850,
      }),
    )
  })

  it('zeigt abgeschlossene und nachträglich geänderte Wochen auch auf Englisch korrekt', async () => {
    await i18n.changeLanguage('en')
    const user = userEvent.setup()
    mount({ ...context, closed: true, requires_review: true })
    await user.selectOptions(await screen.findByRole('combobox'), 'severe')
    expect(screen.getByRole('checkbox', { name: /Also deduct/ })).toBeDisabled()
    expect(screen.getByText(/The confirmed statement stays unchanged/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Permanently close weekly statement' })).toBeNull()
  })
})
